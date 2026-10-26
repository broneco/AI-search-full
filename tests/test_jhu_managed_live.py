"""Explicit managed helper + KV + actual service, isolated SQL only."""
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings, settings
from app.api.routes.auth import create_token
from app.providers.jhu_managed import reset_managed_connection
from app.storage.models import DBActiveSearchIndex, DBChunk, DBChatMessage, DBSearchIndex
from app.storage.vector_store import activate_index, coverage, tenant_key, write_chunks
from test_search_access import access_engine, access_db, api_client, document, user


def test_managed_discovery_embedding_index_and_cited_chat(access_db, api_client, monkeypatch):
    if os.getenv('RUN_JHU_MANAGED_TESTS') != '1' or access_db.bind.dialect.name != 'mssql':
        pytest.skip('Explicit RUN_JHU_MANAGED_TESTS=1 + RUN_LOCAL_SQL_TESTS=1; start managed helper first')
    root = Path(__file__).resolve().parents[1]
    local = Settings(_env_file=(root/'.env.jhu-model', root/'.env.local'), APP_ENV='local', TENANT_ID='jhu')
    public = dict(APP_ENV='local', TENANT_ID='jhu', DATABASE_BACKEND='sqlserver',
        AZURE_SQL_HOST='127.0.0.1', AZURE_SQL_DB='ai_search_local',
        JHU_CONNECTION_MODE='managed', JHU_LLM_ENDPOINT=local.JHU_LLM_ENDPOINT,
        JHU_LLM_ALLOW_HTTP=local.JHU_LLM_ALLOW_HTTP,
        JHU_KEY_VAULT_NAME=os.getenv('JHU_KEY_VAULT_NAME','ju-ai-search-kv-prod'),
        JHU_API_USERNAME_SECRET='ju-ai-search-jhu-api-username-prod',
        JHU_API_PASSWORD_SECRET='ju-ai-search-jhu-api-password-prod',
        JHU_HELPER_WORKSPACE=str(root), JHU_LLM_USERNAME=None, JHU_LLM_PASSWORD=None)
    for key,value in public.items():
        monkeypatch.setattr(settings,key,value)
    monkeypatch.setattr('app.storage.db.SessionLocal', sessionmaker(bind=access_db.bind))
    reset_managed_connection()
    try:
        manager = user(access_db, tenant='jhu', groups=['User','Management'])
        headers = {'Authorization':'Bearer '+create_token(manager)}
        scan = api_client.get('/api/models/discovery', headers=headers)
        assert scan.status_code == 200, scan.text
        found = scan.json()['models']
        small = next(m for m in found if m['name']=='llama3.2:3b')
        registered = api_client.post('/api/models/registry', headers=headers,
            json={'models':[{'name':small['name'],'digest':small['digest']}]})
        assert registered.status_code == 200, registered.text
        llm_id = registered.json()['models'][0]['id']

        from app.providers.factory import create_embedding_profile
        reference = create_embedding_profile()
        for i,content in enumerate(('Studijní oddělení přijímá žádosti v pondělí a ve středu.',
                                    'Univerzitní knihovna půjčuje knihy na třicet dnů.')):
            doc = document(access_db,tenant='jhu',title=f'Synthetic university {i}')
            write_chunks(access_db,[dict(document_id=doc.document_id, chunk_index=0, content=content,
                page_number=1, embedding=[1.0]+[0.0]*(reference.dimensions-1),
                security_acl={'allowed_groups':['User']})], reference)
        original = access_db.scalar(select(DBSearchIndex).where(DBSearchIndex.profile_id==reference.profile_id))
        activate_index(access_db,original)
        access_db.commit()
        ids = set(access_db.scalars(select(DBChunk.chunk_id)))
        prepared = api_client.post('/api/search-indexes/prepare', headers=headers,
                                  json={'embedding_profile':'jhu-nomic'})
        assert prepared.status_code == 200, prepared.text
        chosen = prepared.json()['index']['index_id']
        assert coverage(access_db,access_db.get(DBSearchIndex,uuid.UUID(chosen))) == (2,2)
        from app.api.routes import chat
        monkeypatch.setattr(chat.SearchConfigManager,'load_config',AsyncMock(return_value={
            'context_expansion':'none','final_limit':1}))
        result = api_client.post('/api/chat',headers=headers,json={
            'query':'Jak dlouho si mohu půjčit knihy? Odpověz česky a uveď citaci [1].',
            'model_id':llm_id,'search_strategy':'vector','search_index_id':chosen})
        assert result.status_code == 200, result.text
        body = result.json()
        assert body['answer'].strip() and '[1]' in body['answer']
        assert body['sources'][0]['title'] == 'Synthetic university 1'
        assert body['metadata']['model_id'] == llm_id
        assert body['metadata']['search_index_id'] == chosen
        saved = access_db.scalar(select(DBChatMessage).where(DBChatMessage.role=='assistant'))
        assert saved.sources['generation']['search_index_id'] == chosen
        assert saved.sources['generation']['model_id'] == llm_id
        assert set(access_db.scalars(select(DBChunk.chunk_id))) == ids
        assert access_db.get(DBActiveSearchIndex,tenant_key('jhu')).index_id == original.index_id
        print(json.dumps(dict(models=len(found), model=small['name'], embedding='jhu-nomic',
                              cited_chat=True, selected_index_preserved=True)))
    finally:
        reset_managed_connection()
