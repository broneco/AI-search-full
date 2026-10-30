"""Real SQL persistence across application defaults/restarts; no private env or cloud calls."""
import asyncio
from contextlib import contextmanager
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core import tenant_config
from app.core.prompts import get_tenant_prompts_map, update_tenant_prompt
from app.core.search_config import SearchConfigManager
from app.ingestion.tagger import MetadataTagger
from app.storage import db as db_module
from app.storage.models import Base, DBTenantSetting, DBUser, DBChatThread, DBChatMessage, DBDocument, DBChunk
from app.storage.tenant_settings import TenantSettingsError, read_setting, write_setting, setting_key
from migrate_tenant_settings import load_import, main, migrate


def manager_token(factory):
    from app.api.routes.auth import create_token
    with factory.begin() as db:
        user = DBUser(tenant_id=settings.TENANT_ID, email="manager@example.test", username="Manager",
                      password_hash="synthetic-hash", role="Management", groups=["Management", "User"])
        db.add(user)
        db.flush()
        return {"Authorization": "Bearer " + create_token(user)}


@pytest.fixture
def cloud_settings(tmp_path, monkeypatch):
    """A disk database survives connection disposal, like an external app database."""
    engine = create_engine(f"sqlite:///{tmp_path / 'persistent.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(db_module, "SessionLocal", factory)
    monkeypatch.setattr(db_module, "engine", engine)
    import app.api.dependencies as dependencies
    monkeypatch.setattr(dependencies, "SessionLocal", factory)
    monkeypatch.setattr(settings, "APP_ENV", "prod")
    monkeypatch.setattr(settings, "JWT_SECRET", "synthetic-settings-test-key")
    monkeypatch.setattr(tenant_config, "LOCAL_TENANTS_DIR", None)
    bundled = tmp_path / "image-v1" / "default"
    bundled.mkdir(parents=True)
    monkeypatch.setattr(tenant_config, "TENANTS_DIR", str(bundled.parent))
    defaults = {"prompts.json": {"cs": "default cs", "en": "default en"},
                "search_config.json": {"chunk_size": 1500},
                "classification_config.json": {"categories": [], "analysis_rules": "default rules"}}
    for name, payload in defaults.items():
        (bundled / name).write_text(json.dumps(payload), encoding="utf-8")
    yield engine, factory, bundled
    engine.dispose()


def test_settings_survive_new_image_connections_and_repeated_initialization(cloud_settings, monkeypatch, tmp_path):
    engine, factory, bundled = cloud_settings
    tenant = settings.TENANT_ID
    with factory.begin() as db:
        user = DBUser(tenant_id=tenant, email="persistent@example.test", username="Persistent user",
                      password_hash="synthetic-hash", role="User", groups=["User"])
        doc = DBDocument(tenant_id=tenant, title="Keep document", source_type="local", source_uri="synthetic",
                         document_type="document")
        db.add_all([user, doc])
        db.flush()
        thread = DBChatThread(tenant_id=tenant, user_id=user.user_id, title="Keep thread")
        chunk = DBChunk(tenant_id=tenant, document_id=doc.document_id, chunk_index=0, content="Keep chunk")
        db.add_all([thread, chunk])
        db.flush()
        message = DBChatMessage(tenant_id=tenant, thread_id=thread.thread_id, role="assistant", content="Keep history")
        db.add(message)
        db.flush()
        ids = user.user_id, doc.document_id, thread.thread_id, chunk.chunk_id, message.message_id
    update_tenant_prompt(tenant, "cs", "Vlastní instrukce {context_str}")
    manager = SearchConfigManager()
    asyncio.run(manager.save_config({"chunk_size": 2300, "summary_custom_prompt": "Own summary"}))
    tagger = MetadataTagger(llm_provider=object())
    asyncio.run(tagger.save_config({"categories": [], "analysis_rules": "Own classification"}))
    # New image defaults differ completely; the old image's writable layer disappears.
    new_image = tmp_path / "image-v2" / "default"
    new_image.mkdir(parents=True)
    for file in bundled.iterdir():
        (new_image / file.name).write_text('{}', encoding="utf-8")
        file.unlink()
    monkeypatch.setattr(tenant_config, "TENANTS_DIR", str(new_image.parent))
    engine.dispose()
    db_module.init_db()
    db_module.init_db()
    assert get_tenant_prompts_map(tenant)["cs"] == "Vlastní instrukce {context_str}"
    assert manager.load_config_sync()["chunk_size"] == 2300
    assert asyncio.run(manager.load_config()) == manager.load_config_sync()
    assert asyncio.run(tagger.load_config())["analysis_rules"] == "Own classification"
    with factory() as db:
        for model, ident in zip((DBUser, DBDocument, DBChatThread, DBChunk, DBChatMessage), ids):
            assert db.get(model, ident) is not None
        assert db.get(DBUser, ids[0]).password_hash == "synthetic-hash"
        assert db.get(DBChatMessage, ids[-1]).content == "Keep history"


@pytest.mark.parametrize("tenant", ["ju-prod", "ju-dev", "jhu", "JU-prod", "ju-prod "])
def test_exact_tenant_identity_is_not_a_config_alias(cloud_settings, tenant):
    _, factory, _ = cloud_settings
    payload = {"cs": tenant, "en": "tenant specific"}
    tenant_config.save_tenant_json(tenant, "prompts.json", payload)
    assert tenant_config.load_tenant_json(tenant, "prompts.json") == payload
    with factory() as db:
        assert read_setting(db, "ju", "prompts.json") is None
        assert read_setting(db, tenant + "-other", "prompts.json") is None


def test_new_install_uses_bundled_defaults_without_seeding(cloud_settings):
    _, factory, bundled = cloud_settings
    assert tenant_config.load_tenant_json("new-prod", "search_config.json") == {"chunk_size": 1500}
    with factory() as db:
        assert list(db.scalars(select(DBTenantSetting))) == []
    assert json.loads((bundled / "search_config.json").read_text()) == {"chunk_size": 1500}


def test_cloud_config_does_not_read_or_write_legacy_blob(cloud_settings, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Cloud configuration must use the same SQL source for sync and async paths")
    from app.providers.blob_storage import BlobStorageProvider
    monkeypatch.setattr(BlobStorageProvider, "is_configured", forbidden)
    manager = SearchConfigManager()
    asyncio.run(manager.save_config({"chunk_size": 2900}))
    assert asyncio.run(manager.load_config()) == manager.load_config_sync()
    tagger = MetadataTagger(llm_provider=object())
    asyncio.run(tagger.save_config({"categories": [], "analysis_rules": "SQL rules"}))
    assert asyncio.run(tagger.load_config())["analysis_rules"] == "SQL rules"


def test_api_save_failure_is_503_without_file_fallback(cloud_settings):
    engine, factory, bundled = cloud_settings
    manager_headers = manager_token(factory)
    from app.main import app
    before = {path.name: path.read_bytes() for path in bundled.iterdir()}
    DBTenantSetting.__table__.drop(engine)
    client = TestClient(app, raise_server_exceptions=False)
    for method, url, payload in (
        ("get", "/api/prompts", None),
        ("put", "/api/prompts", {"locale": "cs", "prompt_text": "must not disappear"}),
        ("post", "/api/chat/config", {"chunk_size": 2200}),
    ):
        response = client.request(method, url, json=payload, headers=manager_headers)
        assert response.status_code == 503, response.text
        assert response.json()["code"] == "tenant_settings_unavailable"
        assert "persistent.db" not in response.text
    assert {path.name: path.read_bytes() for path in bundled.iterdir()} == before


def test_existing_admin_apis_persist_all_three_prompts_and_chunking(cloud_settings):
    _, factory, _ = cloud_settings
    from app.main import app
    client = TestClient(app)
    headers = manager_token(factory)
    assert client.put("/api/prompts", json={"locale": "cs", "prompt_text": "Own RAG"}, headers=headers).status_code == 200
    assert client.post("/api/chat/config", json={"chunk_size": 2700}, headers=headers).status_code == 200
    for purpose in ("summary", "classification"):
        response = client.put(f"/api/prompts/tasks/{purpose}", json={"prompt_text": f"Own {purpose}"}, headers=headers)
        assert response.status_code == 200, response.text
    assert client.get("/api/prompts").json()["prompts"]["cs"] == "Own RAG"
    cfg = client.get("/api/chat/config").json()
    assert cfg["chunk_size"] == 2700
    assert cfg["summary_custom_prompt"] == "Own summary"
    assert SearchConfigManager().load_config_sync() == cfg
    assert asyncio.run(MetadataTagger(llm_provider=object()).load_config())["analysis_rules"] == "Own classification"
    assert client.put("/api/prompts", json={"prompt_text": "anonymous"}).status_code == 401


def test_config_aliases_and_case_variants_have_independent_rows(cloud_settings):
    _, factory, _ = cloud_settings
    tenants = ["ju-prod", "ju-dev", "jhu", "JU-prod", "ju-prod "]
    for tenant in tenants:
        tenant_config.save_tenant_json(tenant, "prompts.json", {"cs": tenant, "en": tenant})
    with factory() as db:
        assert [read_setting(db, tenant, "prompts.json")["cs"] for tenant in tenants] == tenants


def test_sql_import_is_insert_only_transactional_and_preserves_other_tenants(cloud_settings):
    engine, factory, _ = cloud_settings
    documents = {"prompts.json": {"cs": "import cs", "en": "import en"},
                 "search_config.json": {"chunk_size": 2400},
                 "classification_config.json": {"categories": [], "analysis_rules": "import"}}
    assert set(migrate(engine, "ju-prod", documents).values()) == {"imported"}
    with factory.begin() as db:
        write_setting(db, "ju-prod", "prompts.json", {"cs": "newer admin edit", "en": "en"})
        write_setting(db, "ju-dev", "prompts.json", {"cs": "other tenant", "en": "en"})
    assert set(migrate(engine, "ju-prod", documents).values()) == {"preserved"}
    with factory() as db:
        assert read_setting(db, "ju-prod", "prompts.json")["cs"] == "newer admin edit"
        assert read_setting(db, "ju-dev", "prompts.json")["cs"] == "other tenant"
    with pytest.raises(ValueError):
        migrate(engine, "ju-prod", {**documents, "search_config.json": {"chunk_size": 0}})
    with factory() as db:
        assert read_setting(db, "ju-prod", "search_config.json")["chunk_size"] == 2400


def test_cli_plan_and_wrong_target_never_write(cloud_settings, monkeypatch, capsys):
    engine, _, _ = cloud_settings
    DBTenantSetting.__table__.drop(engine)
    main([])
    plan = json.loads(capsys.readouterr().out)
    assert plan["apply"] is False
    assert not inspect(engine).has_table("tenant_settings")
    with pytest.raises(ValueError, match="exact expected"):
        main(["--apply", "--expect-host", "wrong", "--expect-db", "wrong", "--expect-tenant", "ju"])
    assert not inspect(engine).has_table("tenant_settings")


def test_correct_target_cli_creates_only_additive_table_and_imports(cloud_settings, capsys, tmp_path):
    engine, factory, _ = cloud_settings
    DBTenantSetting.__table__.drop(engine)
    documents = {"prompts.json": {"cs": "private-import-text", "en": "en"},
                 "search_config.json": {"chunk_size": 2200},
                 "classification_config.json": {"categories": [], "analysis_rules": "rules"}}
    for name, payload in documents.items():
        (tmp_path / name).write_text(json.dumps(payload), encoding="utf-8")
    host = settings.AZURE_SQL_HOST if settings.USE_AZURE_SQL else settings.POSTGRES_HOST
    database = settings.AZURE_SQL_DB if settings.USE_AZURE_SQL else settings.POSTGRES_DB
    main(["--apply", "--expect-host", host, "--expect-db", database,
          "--expect-tenant", settings.TENANT_ID, "--import-dir", str(tmp_path)])
    output = capsys.readouterr().out
    assert "private-import-text" not in output
    assert '"imported"' in output
    with factory() as db:
        assert read_setting(db, settings.TENANT_ID, "prompts.json")["cs"] == "private-import-text"


def test_azure_startup_never_creates_runtime_settings_schema(cloud_settings, monkeypatch):
    calls = []
    class FakeEngine:
        dialect = SimpleNamespace(name="mssql")
        @contextmanager
        def begin(self):
            yield self
        connect = begin
        def execution_options(self, **kwargs):
            return self
        def execute(self, statement):
            calls.append(str(statement))
    created = []
    monkeypatch.setattr(db_module, "engine", FakeEngine())
    monkeypatch.setattr(settings, "DATABASE_BACKEND", "azure_sql")
    monkeypatch.setattr(settings, "USE_AZURE_SQL", True)
    monkeypatch.setattr(Base.metadata, "create_all", lambda **kwargs: created.extend(t.name for t in kwargs["tables"]))
    db_module.init_db()
    assert "users" in created
    assert "tenant_settings" not in created
    assert not any("DELETE" in statement or "DROP TABLE" in statement for statement in calls)


def test_cli_import_requires_all_reviewed_documents(tmp_path):
    (tmp_path / "prompts.json").write_text('{"cs":"cs", "en":"en"}', encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        load_import(tmp_path)


def test_failed_import_rolls_back_earlier_rows(cloud_settings, monkeypatch):
    engine, factory, _ = cloud_settings
    import app.storage.tenant_settings as repository
    original = repository.write_setting
    def fail_second(db, tenant, filename, data, **kwargs):
        if filename == "search_config.json":
            raise RuntimeError("synthetic second-row failure")
        return original(db, tenant, filename, data, **kwargs)
    monkeypatch.setattr(repository, "write_setting", fail_second)
    with pytest.raises(RuntimeError):
        migrate(engine, "ju-prod", {"prompts.json": {"cs": "cs", "en": "en"},
                                    "search_config.json": {"chunk_size": 2000}})
    with factory() as db:
        assert read_setting(db, "ju-prod", "prompts.json") is None


def test_invalid_sql_payload_never_silently_uses_defaults(cloud_settings):
    _, factory, _ = cloud_settings
    key, filename = setting_key("ju-prod", "prompts.json")
    with factory.begin() as db:
        db.add(DBTenantSetting(tenant_key=key, filename=filename, tenant_id="ju-prod", payload={"cs": 123}))
    with pytest.raises(TenantSettingsError):
        tenant_config.load_tenant_json("ju-prod", "prompts.json")


def test_local_overlay_still_preserves_public_defaults(cloud_settings, monkeypatch, tmp_path):
    _, factory, bundled = cloud_settings
    monkeypatch.setattr(settings, "APP_ENV", "local")
    monkeypatch.setattr(tenant_config, "LOCAL_TENANTS_DIR", str(tmp_path / "local-overlay"))
    tenant_config.save_tenant_json("ju-prod", "prompts.json", {"cs": "local", "en": "local"})
    assert tenant_config.load_tenant_json("ju-prod", "prompts.json")["cs"] == "local"
    assert json.loads((bundled / "prompts.json").read_text())["cs"] == "default cs"
    with factory() as db:
        assert read_setting(db, "ju-prod", "prompts.json") is None
