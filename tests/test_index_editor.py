"""Logical index editing keeps a working generation until the replacement is complete."""
from unittest.mock import AsyncMock
import uuid
import pytest
from sqlalchemy import select
from app.storage.models import DBChunk, DBSearchIndex, DBIndexSettings, DBActiveSearchIndex
from app.storage.vector_store import coverage, active_index, tenant_key
from app.core.search_index_selection import selected_index
from app.ingestion import index_jobs
from test_search_access import access_engine, access_db, api_client, user
from test_admin_indexes import experiment
from test_index_jobs import jobs, run
from test_index_corpora import originals, pair, fill


def initialize(client,e,monkeypatch):
    monkeypatch.setattr('app.ingestion.index_editor.SearchConfigManager.load_config_sync',lambda self:{'chunk_size':300,'chunk_overlap':40})
    response=client.post('/api/search-indexes/initialize-settings',headers=e.headers)
    assert response.status_code==200,response.text
    return response.json()


def save(client,e,*,index=None,size=800,name='Upravený index',revision=None,profile=None,status=202):
    payload={'name':name,'chunking':{'chunk_size':size,'chunk_overlap':40,'chunk_splitter_type':'character'}}
    if index is not None:
        payload.update(index_id=str(index.index_id),expected_revision=revision if revision is not None else e.db.get(DBIndexSettings,index.index_id).revision)
    if profile:payload['embedding_profile']=profile
    response=client.post('/api/search-indexes/editor',headers=e.headers,json=payload)
    assert response.status_code==status,response.text
    return response.json().get('job',response.json())


def test_legacy_initialization_is_explicit_once_and_preserves_vectors(originals,api_client,monkeypatch):
    e=originals;before=coverage(e.db,e.old)
    renamed=api_client.patch(f'/api/search-indexes/{e.old.index_id}',headers=e.headers,
        json={'name':'Původní pojmenovaný','expected_revision':0})
    assert renamed.status_code==200,renamed.text
    assert initialize(api_client,e,monkeypatch)['initialized']==1
    e.db.expire_all();spec=e.db.get(DBIndexSettings,e.old.index_id)
    assert spec.settings_origin=='assumed' and spec.chunking['chunk_size']==300
    monkeypatch.setattr('app.ingestion.index_editor.SearchConfigManager.load_config_sync',lambda self:{'chunk_size':900,'chunk_overlap':40})
    assert api_client.post('/api/search-indexes/initialize-settings',headers=e.headers).json()['initialized']==0
    e.db.expire_all();assert spec.chunking['chunk_size']==300 and coverage(e.db,e.old)==before
    e.local.embed_documents.assert_not_called()


def test_create_is_one_operation_and_update_keeps_logical_identity(originals,api_client):
    e=originals
    created=save(api_client,e,profile='jhu-nomic',size=300)
    assert created['action']=='backfill'
    root_id=uuid.UUID(created['logical_index_id']);root=e.db.get(DBSearchIndex,root_id)
    assert run(e,created)['state']=='completed'
    before_chunks={c.chunk_id for c in e.db.scalars(select(DBChunk).where(DBChunk.corpus_id==root.corpus_id))}
    assert selected_index(e.db,'alpha',root_id).index_id==root_id
    edited=save(api_client,e,index=root,size=900,name='Přejmenovaný')
    assert edited['logical_index_id']==str(root_id) and edited['index_id']!=str(root_id)
    assert selected_index(e.db,'alpha',root_id).index_id==root_id
    assert run(e,edited)['state']=='completed'
    head=selected_index(e.db,'alpha',root_id)
    assert head.index_id!=root_id and coverage(e.db,head)[0]<len(before_chunks)
    assert all(e.db.get(DBChunk,cid) is not None for cid in before_chunks)
    listing=api_client.get('/api/search-indexes',headers=e.headers).json()['indexes']
    assert len(listing)==2  # one original default, one logical editor index; physical versions are hidden
    row=next(i for i in listing if i['index_id']==str(root_id))
    assert row['name']=='Přejmenovaný' and row['chunking']['chunk_size']==900 and row['settings_revision']==2
    assert coverage(e.db,e.old)==(2,2)
    assert api_client.delete(f'/api/search-indexes/{root_id}?expected_revision=2',headers=e.headers).status_code==200
    e.db.expire_all();assert e.db.get(DBSearchIndex,head.index_id) is None
    assert all(e.db.get(DBChunk,cid) is not None for cid in before_chunks)


def test_failed_edit_keeps_working_version_and_retry_resumes_same_pending_generation(originals,api_client):
    from app.core.model_config import ModelError
    e=originals;root=pair(api_client,e);fill(api_client,e,root)
    e.local.embed_documents.side_effect=ModelError('embedding_input_rejected','synthetic',422)
    failed=save(api_client,e,index=root,size=700)
    result=run(e,failed);assert result['state']=='failed'
    assert selected_index(e.db,'alpha',root.index_id).index_id==root.index_id
    assert coverage(e.db,root)[0]>0
    e.local.embed_documents.side_effect=lambda texts:[[1.0]+[0.0]*767 for _ in texts]
    retry=save(api_client,e,index=root,size=700)
    assert retry['index_id']==failed['index_id']
    assert run(e,retry)['state']=='completed'
    assert selected_index(e.db,'alpha',root.index_id).index_id==uuid.UUID(retry['index_id'])


def test_default_edit_preserves_ingestion_and_is_available_to_ordinary_users(originals,api_client,monkeypatch):
    from app.api.routes.auth import create_token
    e=originals;initialize(api_client,e,monkeypatch)
    e.cloud.embed_documents.side_effect=lambda texts:[[1.0]+[0.0]*(e.azure.dimensions-1) for _ in texts]
    monkeypatch.setattr(index_jobs,'catalog_embedding_provider',lambda *a,**k:e.cloud)
    edited=save(api_client,e,index=e.old,size=700)
    assert run(e,edited)['state']=='completed'
    assert e.db.get(DBActiveSearchIndex,tenant_key('alpha')).index_id==e.old.index_id
    assert coverage(e.db,e.old)==(2,2)
    assert active_index(e.db,'alpha',e.azure).index_id==uuid.UUID(edited['index_id'])
    ordinary=user(e.db,groups=['User']);e.db.commit()
    headers={'Authorization':'Bearer '+create_token(ordinary)}
    indexes=api_client.get('/api/search-indexes/available',headers=headers)
    assert indexes.status_code==200,indexes.text
    assert any(i['index_id']==str(e.old.index_id) and i['ingestion_default'] for i in indexes.json()['indexes'])
    answer=api_client.post('/api/chat',headers=headers,json={'query':'Dovolená','search_strategy':'vector'})
    assert answer.status_code==200,answer.text
    assert answer.json()['metadata']['search_index_id']==edited['index_id']
    lexical=api_client.post('/api/chat',headers=headers,json={'query':'Dovolená','search_strategy':'keyword'})
    assert lexical.status_code==200,lexical.text
    assert lexical.json()['sources']
    assert all(e.db.get(DBChunk,uuid.UUID(s['chunk_id'])).corpus_id!='tenant-chunks-v1'
        and e.db.get(DBChunk,uuid.UUID(s['chunk_id'])).corpus_id is not None for s in lexical.json()['sources'])
    assert api_client.delete(f'/api/search-indexes/{e.old.index_id}?expected_revision=2',headers=e.headers).status_code==409


def test_editor_rejects_stale_revision_and_model_substitution(originals,api_client,monkeypatch):
    e=originals;initialize(api_client,e,monkeypatch)
    before=e.db.scalar(select(__import__('sqlalchemy').func.count()).select_from(DBSearchIndex))
    save(api_client,e,index=e.old,profile='jhu-nomic',status=422)
    save(api_client,e,index=e.old,revision=99,status=409)
    assert e.db.scalar(select(__import__('sqlalchemy').func.count()).select_from(DBSearchIndex))==before


def test_editor_schema_upgrades_existing_settings_table_without_rewriting_values(originals):
    from sqlalchemy import text,inspect
    from app.storage.index_corpus_schema import migrate,SETTINGS_COLUMNS
    e=originals
    e.db.add(DBIndexSettings(index_id=e.old.index_id,tenant_id='alpha',name='Zachovat název',chunking=None));e.db.commit()
    for column in SETTINGS_COLUMNS:
        e.db.execute(text(f'ALTER TABLE index_settings DROP COLUMN {column}'))
    e.db.commit()
    migrate(e.db.connection());migrate(e.db.connection());e.db.commit();e.db.expire_all()
    row=e.db.get(DBIndexSettings,e.old.index_id)
    assert row.name=='Zachovat název' and row.chunking is None and row.current_index_id is None
    assert set(SETTINGS_COLUMNS)<={c['name'] for c in inspect(e.db.connection()).get_columns('index_settings')}
