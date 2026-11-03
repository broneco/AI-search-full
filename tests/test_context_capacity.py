"""Authorized index samples and read-only summary filtering, without model calls."""
import asyncio
from unittest.mock import Mock
import uuid
import pytest
from sqlalchemy import select, update
from app.retrieval.context_capacity import reference_encoding
from app.retrieval.vector import VectorRetriever
from app.retrieval.summary_context import without_ai_summary
from app.core.search_config import SearchConfigManager, SearchConfigSchema
from app.storage.models import DBChunk, DBModelAccess
from app.storage.vector_store import vector_table, index_profile, provision_index
from test_search_access import access_engine, access_db, api_client, document, chunk, context, user
from test_admin_indexes import experiment
from test_index_jobs import jobs, run
from test_index_corpora import originals
from test_index_editor import initialize, save


@pytest.mark.parametrize('only_matched',[True,False])
def test_search_config_controls_neighbor_summaries_without_modifying_chunks(access_db,only_matched):
    db=access_db;doc=document(db)
    left=chunk(db,doc,index=0,content='[AI Shrnutí: LEFT SUMMARY]\n\nleft body')
    anchor=chunk(db,doc,index=1,content='[AI Shrnutí: MATCH SUMMARY]\n\nuniqueanchor')
    right=chunk(db,doc,index=2,content='[AI Shrnutí: RIGHT SUMMARY]\n\nright body')
    db.commit();original={c.chunk_id:c.content for c in [left,anchor,right]}
    result=VectorRetriever(db)._retrieve(context().model_copy(update={'query':'uniqueanchor'}),search_config={
        'search_strategy':'keyword','final_limit':1,'context_expansion':'siblings','context_expansion_size':1,
        'summaries_only_for_matched_chunk':only_matched})
    assert len(result)==1
    assert 'MATCH SUMMARY' in result[0].content and 'left body' in result[0].content and 'right body' in result[0].content
    assert ('LEFT SUMMARY' in result[0].content)==(not only_matched)
    assert ('RIGHT SUMMARY' in result[0].content)==(not only_matched)
    assert set(result[0].metadata['context_chunk_ids'])=={str(c.chunk_id) for c in [left,anchor,right]}
    db.expire_all();assert original=={ident:db.get(DBChunk,ident).content for ident in original}


def test_summary_prefix_only_and_persisted_setting(access_db,monkeypatch):
    assert without_ai_summary('Normal text\n[AI Shrnutí: quoted]\n\nbody')=='Normal text\n[AI Shrnutí: quoted]\n\nbody'
    assert without_ai_summary('[AI Shrnutí: one\n[two] three]\n\nbody')=='body'
    assert SearchConfigSchema().summaries_only_for_matched_chunk is True
    manager=SearchConfigManager();monkeypatch.setattr(manager.blob_provider,'is_configured',lambda:False)
    values={**manager.get_defaults(),'summaries_only_for_matched_chunk':False}
    asyncio.run(manager.save_config(values))
    assert asyncio.run(manager.load_config())['summaries_only_for_matched_chunk'] is False


def model_id(e):
    from app.core.local_model_registry import model_catalog
    return model_catalog(e.db,'alpha').defaults['chat']


def test_sample_is_exact_token_count_for_one_index_and_has_no_text_or_writes(experiment,api_client):
    e=experiment;before={c.chunk_id:(c.content,c.content_hash) for c in e.db.scalars(select(DBChunk))}
    response=api_client.get(f'/api/search-indexes/{e.old.index_id}/context-sample',params={'model_id':model_id(e)},headers=e.headers)
    assert response.status_code==200,response.text
    data=response.json();sample=data['sample'];stored=e.db.get(DBChunk,uuid.UUID(sample['chunk_id']))
    assert sample['tokens']==len(reference_encoding().encode(stored.content,disallowed_special=()))
    assert sample['characters']==len(stored.content)
    assert stored.content not in response.text and 'content' not in sample
    assert before=={c.chunk_id:(c.content,c.content_hash) for c in e.db.scalars(select(DBChunk))}
    assert data['model']['max_input_chars']>0 and data['tokenizer']=='o200k_base'
    e.cloud.embed_query.assert_not_called();e.cloud.embed_documents.assert_not_called()


def test_sample_honors_current_logical_generation(originals,api_client,monkeypatch):
    from app.ingestion import index_jobs
    e=originals;initialize(api_client,e,monkeypatch)
    e.cloud.embed_documents.side_effect=lambda texts:[[1.0]+[0.0]*(e.azure.dimensions-1) for _ in texts]
    monkeypatch.setattr(index_jobs,'catalog_embedding_provider',lambda *a,**k:e.cloud)
    job=save(api_client,e,index=e.old,size=700)
    assert run(e,job)['state']=='completed'
    data=api_client.get(f'/api/search-indexes/{e.old.index_id}/context-sample',params={'model_id':model_id(e)},headers=e.headers).json()
    assert data['current_index_id']==job['index_id']
    assert e.db.get(DBChunk,uuid.UUID(data['sample']['chunk_id'])).corpus_id.startswith('index-')


def test_sample_rejects_foreign_index_user_and_model_policy_before_tokenizing(experiment,api_client,monkeypatch):
    from app.api.routes.auth import create_token
    e=experiment;ident=model_id(e)
    def forbidden():pytest.fail('Unauthorized requests must not tokenize text')
    monkeypatch.setattr('app.retrieval.context_capacity.reference_encoding',forbidden)
    foreign=provision_index(e.db,'beta',e.azure,native=False);e.db.commit()
    url=f'/api/search-indexes/{foreign.index_id}/context-sample'
    assert api_client.get(url,params={'model_id':ident},headers=e.headers).status_code==404
    ordinary=user(e.db,groups=['User']);e.db.commit()
    headers={'Authorization':'Bearer '+create_token(ordinary)}
    url=f'/api/search-indexes/{e.old.index_id}/context-sample'
    assert api_client.get(url,params={'model_id':ident},headers=headers).status_code==403
    e.db.add(DBModelAccess(tenant_id='alpha',model_id=ident,allowed_groups=['HR'],revision=1,updated_by=str(e.manager.user_id)));e.db.commit()
    assert api_client.get(url,params={'model_id':ident},headers=e.headers).status_code==403


def test_stale_vectors_do_not_supply_a_sample(experiment,api_client,monkeypatch):
    e=experiment;table=vector_table(e.old,index_profile(e.db,e.old))
    e.db.execute(update(table).values(input_revision='0'*64));e.db.commit()
    monkeypatch.setattr('app.retrieval.context_capacity.reference_encoding',lambda:pytest.fail('No valid sample'))
    response=api_client.get(f'/api/search-indexes/{e.old.index_id}/context-sample',params={'model_id':model_id(e)},headers=e.headers)
    assert response.status_code==200 and response.json()['sample'] is None
