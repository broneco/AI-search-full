"""Index pairs own their chunks; exact original previews and guarded lifecycle preserve legacy data."""
import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
import uuid

import pytest
from sqlalchemy import select, func, inspect

from app.api.identity import Principal
from app.core.model_config import ModelError
from app.ingestion import sources
from app.storage.models import DBChunk, DBDocument, DBIndexSettings, DBIndexDocument
from app.storage.vector_store import coverage, SearchIndexError
from app.storage.index_settings import corpus_ready, corpus_filter
from test_search_access import access_engine, access_db, api_client, user, document
from test_admin_indexes import experiment
from test_index_jobs import jobs, submit, run


@pytest.fixture
def originals(jobs, tmp_path, monkeypatch):
    e=jobs
    monkeypatch.chdir(tmp_path)
    data=tmp_path/'data'; data.mkdir()
    for doc in e.db.scalars(select(DBDocument).where(DBDocument.tenant_id=='alpha')):
        content=('Dovolená musí být vyčerpána v březnu. '+doc.title+'\n')*40
        name=str(doc.document_id)+'.txt'
        (data/name).write_bytes(content.encode('utf-8'))
        doc.source_uri='file://'+name
        doc.checksum=hashlib.sha256(content.encode()).hexdigest()
    e.db.commit()
    return e


def pair(client,e,size=300,name='Dovolená — krátké chunky'):
    response=client.post('/api/search-indexes/jobs',headers=e.headers,json={
        'action':'create','embedding_profile':'jhu-nomic','name':name,
        'chunking':{'chunk_size':size,'chunk_overlap':40,'chunk_splitter_type':'character'}})
    assert response.status_code==202,response.text
    job=response.json()['job']; result=run(e,job)
    assert result['state']=='completed',result
    from app.storage.models import DBSearchIndex
    return e.db.get(DBSearchIndex,uuid.UUID(result['index_id']))


def fill(client,e,index):
    result=run(e,submit(client,e,action='backfill',index_id=index.index_id))
    assert result['state']=='completed',result
    return result


def test_two_configs_same_model_own_corpora_resume_and_leave_baseline(originals,api_client,monkeypatch):
    e=originals
    baseline={c.chunk_id:(c.content,c.content_hash,c.embedding) for c in e.db.scalars(select(DBChunk))}
    first=pair(api_client,e,300)
    # The old synchronous endpoint must not bypass durable corpus preparation/fencing.
    legacy=api_client.post('/api/search-indexes/prepare',headers=e.headers,
        json={'embedding_profile':'jhu-nomic','index_id':str(first.index_id)})
    assert legacy.status_code==409 and legacy.json()['code']=='index_preparation_requires_job'
    second=pair(api_client,e,900,'Delší')
    assert first.profile_id==second.profile_id and first.corpus_id!=second.corpus_id
    fill(api_client,e,first); fill(api_client,e,second)
    a,b=coverage(e.db,first),coverage(e.db,second)
    assert a[0]==a[1] and b[0]==b[1] and a[0]>b[0]>2
    assert coverage(e.db,e.old)==(2,2)
    assert baseline=={c.chunk_id:(c.content,c.content_hash,c.embedding) for c in e.db.scalars(select(DBChunk).where(corpus_filter()))}
    e.local.embed_documents.reset_mock()
    monkeypatch.setattr('app.ingestion.index_corpus.DocumentExtractor.extract',lambda *a:pytest.fail('Prepared documents must not be extracted again'))
    assert fill(api_client,e,first)['processed_chunks']==0
    e.local.embed_documents.assert_not_called()
    saved=e.db.get(DBIndexSettings,first.index_id)
    assert saved.chunking['chunk_size']==300
    saved.chunking={**saved.chunking,'chunk_size':400}
    with pytest.raises(SearchIndexError,match='immutable'):e.db.flush()
    e.db.rollback()


def test_pair_query_scopes_vectors_keywords_and_context_and_keeps_history_after_delete(originals,api_client):
    e=originals
    index=pair(api_client,e); fill(api_client,e,index)
    from app.retrieval.base import QueryContext
    from app.retrieval.vector import VectorRetriever
    from app.storage.ann_search import VectorSearchPlan
    from app.storage.vector_store import exact_candidates
    context=QueryContext(query='Dovolená',tenant_id='alpha',acl_groups=['User','Management'])
    selected=exact_candidates(e.db,context,[1.0]+[0.0]*767,e.nomic,100,index=index)
    assert selected and all(row[0].corpus_id==index.corpus_id for row in selected)
    # Test keyword predicates on both SQL dialects (native full-text is exercised by the broader suite).
    scoped=context.model_copy(update={'corpus_id':index.corpus_id})
    from app.retrieval.filters import eligibility_filters
    own=e.db.scalars(select(DBChunk).join(DBDocument).where(*eligibility_filters(scoped,e.db.bind.dialect.name))).all()
    assert own and all(c.corpus_id==index.corpus_id for c in own)
    retriever=VectorRetriever(e.db)
    keywords=retriever._get_fts_candidates('Dovolená',100,scoped)
    assert keywords and all(row[0].corpus_id==index.corpus_id for row in keywords)
    results=retriever._apply_filters(selected,scoped,None)
    expanded=retriever._expand_context(results[:1],'page',1,4000,context=scoped)
    assert expanded and expanded[0].metadata['context_chunk_ids']
    assert all(e.db.get(DBChunk,uuid.UUID(cid)).corpus_id==index.corpus_id for cid in expanded[0].metadata['context_chunk_ids'])
    response=api_client.post('/api/chat',headers=e.headers,json={'query':'Dovolená','search_strategy':'vector','search_index_id':str(index.index_id)})
    assert response.status_code==200,response.text
    body=response.json(); assert body['sources']
    ref=uuid.UUID(body['sources'][0]['chunk_id'])
    assert e.db.get(DBChunk,ref).corpus_id==index.corpus_id
    ident=str(index.index_id)
    assert api_client.delete('/api/search-indexes/'+ident+'?expected_revision=1',headers=e.headers).status_code==200
    e.db.expire_all()
    assert e.db.get(DBChunk,ref) is not None  # saved citations still have their evidence
    from app.storage.models import DBChatMessage
    from app.retrieval.access import history_is_visible
    messages=e.db.scalars(select(DBChatMessage).where(DBChatMessage.role=='assistant')).all()
    assert messages and all(history_is_visible(e.db,m,Principal(e.manager.user_id,'alpha',('User','Management'))) for m in messages)
    assert coverage(e.db,e.old)==(2,2)
    assert api_client.get('/api/search-indexes/'+ident,headers=e.headers).status_code==404


def test_names_cas_acl_default_and_busy_deletion(originals,api_client):
    e=originals; index=pair(api_client,e)
    url='/api/search-indexes/'+str(index.index_id)
    assert api_client.patch(url,headers=e.headers,json={'name':'Moje jméno','expected_revision':1}).status_code==200
    assert api_client.patch(url,headers=e.headers,json={'name':'Stará změna','expected_revision':1}).status_code==409
    info=api_client.get(url,headers=e.headers).json()['index']
    assert info['name']=='Moje jméno' and info['chunking']['chunk_size']==300 and info['settings_revision']==2
    assert api_client.delete(url+'?expected_revision=1',headers=e.headers).status_code==409
    assert api_client.delete('/api/search-indexes/'+str(e.old.index_id)+'?expected_revision=0',headers=e.headers).status_code==409
    from app.api.routes.auth import create_token
    outsider=user(e.db,tenant='beta',groups=['Management']);e.db.commit()
    headers={'Authorization':'Bearer '+create_token(outsider)}
    assert api_client.get(url,headers=headers).status_code==401
    assert api_client.delete(url+'?expected_revision=2',headers=headers).status_code==401
    pending=submit(api_client,e,action='backfill',index_id=index.index_id)
    assert api_client.delete(url+'?expected_revision=2',headers=e.headers).status_code==409


def test_preview_blob_exact_checksum_cleanup_and_acl_before_io(originals,api_client,monkeypatch):
    e=originals;doc=e.db.scalar(select(DBDocument).where(DBDocument.tenant_id=='alpha'))
    data=('Přesný originál z Blob Storage. '*40).encode()
    doc.source_uri='azure://originals/alpha/specific.txt';doc.checksum=hashlib.sha256(data).hexdigest();e.db.commit()
    monkeypatch.setattr(sources.settings,'AZURE_BLOB_CONTAINER_ORIGINALS','originals')
    provider=SimpleNamespace(is_configured=lambda:True,download_blob=AsyncMock(return_value=data))
    monkeypatch.setattr(sources,'BlobStorageProvider',lambda:provider)
    with sources.document_source(doc) as path:
        assert Path(path).read_bytes()==data
    assert not Path(path).exists()
    before=e.db.scalar(select(func.count()).select_from(DBChunk))
    response=api_client.post('/api/documents/preview-chunks',headers=e.headers,json={'document_id':str(doc.document_id),'chunk_size':300,'chunk_overlap':40})
    assert response.status_code==200 and response.json(),response.text
    provider.download_blob.assert_awaited_with('originals','alpha/specific.txt')
    assert e.db.scalar(select(func.count()).select_from(DBChunk))==before
    provider.download_blob.reset_mock()
    from app.api.routes.auth import create_token
    outsider=user(e.db,tenant='beta',groups=['Management']);e.db.commit()
    response=api_client.post('/api/documents/preview-chunks',headers={'Authorization':'Bearer '+create_token(outsider)},json={'document_id':str(doc.document_id)})
    assert response.status_code==401
    provider.download_blob.assert_not_called()
    doc.checksum='0'*64;e.db.commit()
    assert api_client.post('/api/documents/preview-chunks',headers=e.headers,json={'document_id':str(doc.document_id)}).status_code==409


@pytest.mark.parametrize('uri',['azure://other/alpha.txt','azure://originals/../alpha.txt','azure://originals/a//b.txt','https://example.test/a.txt','file://../outside.txt'])
def test_source_rejects_paths_without_storage_calls(uri,monkeypatch):
    monkeypatch.setattr(sources,'BlobStorageProvider',lambda:pytest.fail('Invalid source must not access storage'))
    with pytest.raises(ModelError):
        with sources.document_source(SimpleNamespace(source_uri=uri,checksum=None)):pass


def test_additive_schema_idempotent_and_legacy_unchanged(access_db):
    from app.storage.index_corpus_schema import migrate
    from sqlalchemy import text
    from app.storage.models import DBChunk
    from test_search_access import chunk
    db=access_db;doc=document(db,title='Původní');item=chunk(db,doc);db.commit();ident=doc.document_id;cid=item.chunk_id
    DBIndexDocument.__table__.drop(db.connection());DBIndexSettings.__table__.drop(db.connection())
    db.execute(text('DROP INDEX ix_chunks_corpus_id ON chunks' if db.bind.dialect.name=='mssql' else 'DROP INDEX ix_chunks_corpus_id'))
    db.execute(text('ALTER TABLE chunks DROP COLUMN corpus_id'));db.commit()
    migrate(db.connection());migrate(db.connection());db.commit()
    assert db.get(DBDocument,ident).title=='Původní'
    db.expire_all();assert db.get(DBChunk,cid).corpus_id is None
    assert inspect(db.connection()).has_table('index_documents')


def test_partial_chunk_acl_prevents_resegmentation_and_invalidates_ready_pair(originals,api_client):
    e=originals;index=pair(api_client,e);fill(api_client,e,index)
    assert corpus_ready(e.db,index)
    source_chunk=e.db.scalar(select(DBChunk).where(corpus_filter()))
    source_chunk.security_acl={'allowed_groups':['HR']};e.db.commit()
    assert not corpus_ready(e.db,index)
    e.local.embed_documents.reset_mock()
    result=run(e,submit(api_client,e,action='backfill',index_id=index.index_id))
    assert result['state']=='failed' and result['error_code']=='chunk_acl_mapping_required'
    e.local.embed_documents.assert_not_called()


def test_strict_semantic_never_silently_substitutes_character_splitting():
    from app.ingestion.chunking import RecursiveCharacterTextSplitter
    provider=SimpleNamespace(embed_documents=AsyncMock(side_effect=ModelError('embedding_input_rejected','synthetic',422)))
    splitter=RecursiveCharacterTextSplitter(chunking_strategy='semantic',embedding_provider=provider,
        semantic_params={'sentence_splitter':'simple_regex'},strict_processing=True)
    with pytest.raises(ModelError,match='Sémantické'):
        splitter._split_semantic('First sentence. Second sentence.')


def test_preview_real_pdf_from_exact_blob_original(jobs,api_client,monkeypatch):
    e=jobs;doc=e.db.scalar(select(DBDocument).where(DBDocument.tenant_id=='alpha'))
    data=(Path(__file__).resolve().parents[1]/'fixtures/local-university/studijni-rad.pdf').read_bytes()
    doc.source_uri='azure://originals/alpha/studijni-rad.pdf';doc.checksum=hashlib.sha256(data).hexdigest();e.db.commit()
    monkeypatch.setattr(sources.settings,'AZURE_BLOB_CONTAINER_ORIGINALS','originals')
    provider=SimpleNamespace(is_configured=lambda:True,download_blob=AsyncMock(return_value=data))
    monkeypatch.setattr(sources,'BlobStorageProvider',lambda:provider)
    response=api_client.post('/api/documents/preview-chunks',headers=e.headers,json={'document_id':str(doc.document_id),'chunk_size':300,'chunk_overlap':40})
    assert response.status_code==200,response.text
    assert response.json() and all(c['content'].strip() for c in response.json())
    assert any('stud' in c['content'].lower() for c in response.json())
    provider.download_blob.assert_awaited_once_with('originals','alpha/studijni-rad.pdf')


def test_missing_prepared_chunk_is_not_a_ready_index(originals,api_client):
    from sqlalchemy import delete
    e=originals;index=pair(api_client,e);fill(api_client,e,index)
    assert corpus_ready(e.db,index)
    item=e.db.scalar(select(DBChunk).where(DBChunk.corpus_id==index.corpus_id))
    e.db.execute(delete(DBChunk).where(DBChunk.chunk_id==item.chunk_id));e.db.commit()
    valid,total=coverage(e.db,index)
    assert valid==total and total>0  # coverage alone would wrongly say complete
    assert not corpus_ready(e.db,index)
