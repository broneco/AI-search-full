"""Real isolated database checkpoints, two vector spaces and destructive-change detection."""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy import create_engine, event, insert, select, update
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import Session, sessionmaker

import verify_deployment as audit
from test_search_access import access_db, access_engine
from app.core.config import settings
from app.providers.embeddings import EmbeddingProfile
from app.storage.models import (Base, DBUser, DBChatThread, DBChatMessage, DBDocument, DBChunk,
    DBSearchIndex, DBEmbeddingProfile, DBModelDescription)
from app.storage.tenant_settings import write_setting
from app.storage.vector_store import provision_index, activate_index, write_embeddings, vector_table, revision

TENANT = "alpha"


def seed(db):
    user = DBUser(tenant_id=TENANT, email="private@example.test", username="Private User",
                  password_hash="synthetic-private-password-hash", groups=["Management", "HR"], role="Management")
    doc = DBDocument(tenant_id=TENANT, title="Private document", source_type="azure_blob",
        source_uri="azure://originals/private.pdf", document_type="policy", security_acl={"allowed_groups": ["HR"]})
    db.add_all([user, doc]); db.flush()
    chunk = DBChunk(tenant_id=TENANT, document_id=doc.document_id, chunk_index=0,
        content="Private contents", content_hash=revision("Private contents"), security_acl={"allowed_groups": ["HR"]})
    thread = DBChatThread(tenant_id=TENANT, user_id=user.user_id, title="Private history")
    db.add_all([chunk, thread]); db.flush()
    message = DBChatMessage(tenant_id=TENANT, thread_id=thread.thread_id, role="assistant", content="Private answer")
    db.add(message)
    indexes = []
    for name, dimensions in (("test-azure", 1536), ("nomic-embed-text:latest", 768)):
        profile = EmbeddingProfile(name, "synthetic-v1", dimensions)
        index = provision_index(db, TENANT, profile, native=False)
        write_embeddings(db, index, profile, [dict(chunk_id=chunk.chunk_id, input_revision=chunk.content_hash,
                                                   embedding=[1.0] + [0.0] * (dimensions - 1))])
        indexes.append((index, profile))
    activate_index(db, indexes[0][0])
    for name, payload in {"prompts.json": {"cs": "Private cs {context_str}", "en": "Private en"},
        "search_config.json": {"chunk_size": 2300, "summary_custom_prompt": "Private summary"},
        "classification_config.json": {"categories": [], "analysis_rules": "Private classification"}}.items():
        write_setting(db, TENANT, name, payload)
    db.add(DBModelDescription(tenant_key=revision(TENANT), tenant_id=TENANT, model_id="test-model",
                             description={"cs": "Private model description"}, updated_by=str(user.user_id)))
    db.commit()
    return SimpleNamespace(user=user, doc=doc, chunk=chunk, thread=thread, message=message, indexes=indexes)


@pytest.fixture
def seeded(access_db, monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_BACKEND", "sqlserver")
    return access_db, seed(access_db)


def checkpoint(db, *, revision_name="revision-before", config=None):
    return dict(schema=1, target=dict(host="synthetic-host", database="synthetic-db", tenant=TENANT),
        context=dict(revision=revision_name, replica=revision_name + "-replica", app_version="test"),
        runtime=audit.runtime_fingerprints(config or settings),
        state=audit.capture_state(db, TENANT, require_settings=True), blobs=None)


def test_capture_is_read_only_private_and_includes_both_spaces(seeded):
    db, data = seeded
    statements = []
    def observed(_conn, _cursor, statement, *_):
        statements.append(statement.lstrip().upper())
    event.listen(db.bind, "before_cursor_execute", observed)
    try:
        value = checkpoint(db)
    finally:
        event.remove(db.bind, "before_cursor_execute", observed)
    audit.validate_checkpoint(value)
    assert statements and all(statement.startswith("SELECT") for statement in statements)
    assert len(value["state"]["indexes"]) == 2
    assert sorted(item["dimensions"] for item in value["state"]["indexes"].values()) == [768, 1536]
    assert all(item["coverage"] == [1, 1] for item in value["state"]["indexes"].values())
    assert sum(item["ingestion_default"] for item in value["state"]["indexes"].values()) == 1
    serialized = json.dumps(value)
    for secret in ("private@example.test", "Private contents", "Private answer", "synthetic-private-password-hash",
                   "Private cs", "Private summary", "Private classification", "Private model description", "private.pdf"):
        assert secret not in serialized


@pytest.mark.parametrize("mutation,expected", [
    ("password", "tables:users"), ("groups", "tables:users"), ("history", "tables:chat_messages"),
    ("document", "tables:documents"), ("chunk", "tables:chunks"),
    ("vector", "vectors:"), ("model", "tables:model_descriptions"), ("setting", "settings:prompts.json")])
def test_detects_overwrites_without_count_changes(seeded, mutation, expected):
    db, data = seeded
    before = checkpoint(db)
    if mutation == "password": data.user.password_hash = "reset-hash"
    elif mutation == "groups": data.user.groups = ["User"]
    elif mutation == "history": data.message.content = "reset answer"
    elif mutation == "document": data.doc.title = "reset title"
    elif mutation == "chunk":
        # Simulate a destructive bulk script outside ORM's vector-invalidation hooks.
        db.execute(DBChunk.__table__.update().where(DBChunk.chunk_id == data.chunk.chunk_id).values(content="reset text"))
    elif mutation == "model":
        db.execute(update(DBModelDescription).values(description={"cs": "reset description"}))
    elif mutation == "setting":
        write_setting(db, TENANT, "prompts.json", {"cs": "reset cs", "en": "reset en"})
    else:
        index, profile = data.indexes[1]
        table = vector_table(index, profile)
        db.execute(update(table).values(embedding=json.dumps([0.0, 1.0] + [0.0] * 766)))
    db.commit()
    after = checkpoint(db, revision_name="revision-after")
    assert {k:v["count"] for k,v in before["state"]["tables"].items()} == {
        k:v["count"] for k,v in after["state"]["tables"].items()}
    result = audit.compare(before, after, require_new_revision=True)
    assert not result["state_preserved"]
    assert any(expected in name for name in result["changes"])


def test_exact_tenant_case_and_trailing_space_are_excluded(seeded):
    db, _ = seeded
    before = checkpoint(db)
    for tenant in ("ALPHA", "alpha ", "beta"):
        db.add(DBUser(tenant_id=tenant, email="other@example.test", username="Other", password_hash="other"))
        doc = DBDocument(tenant_id=tenant, title="Other", source_type="local", source_uri="other", document_type="test")
        db.add(doc); db.flush()
        db.add(DBChunk(tenant_id=tenant, document_id=doc.document_id, chunk_index=0, content="Other contents"))
        write_setting(db, tenant, "prompts.json", {"cs": "Other cs", "en": "Other en"})
        profile = EmbeddingProfile("other-model-" + tenant, "1", 2)
        provision_index(db, tenant, profile, native=False)
    db.commit()
    assert audit.compare(before, checkpoint(db))["state_preserved"]


def test_required_indexes_settings_and_foreign_vectors_fail_closed(seeded):
    db, data = seeded
    ids = [str(item[0].index_id) for item in data.indexes]
    audit.capture_state(db, TENANT, require_indexes=ids, require_settings=True)
    with pytest.raises(audit.AuditError, match="required_index"):
        audit.capture_state(db, TENANT, require_indexes=[str(uuid.uuid4())])
    index, profile = data.indexes[1]
    table = vector_table(index, profile)
    other = DBDocument(tenant_id="beta", title="Other", source_type="local", source_uri="other", document_type="test")
    db.add(other); db.flush()
    chunk = DBChunk(tenant_id="beta", document_id=other.document_id, chunk_index=0, content="Other")
    db.add(chunk); db.flush()
    db.execute(insert(table).values(chunk_id=chunk.chunk_id, input_revision=revision("Other"), embedding="[1,0]"))
    db.commit()
    with pytest.raises(audit.AuditError, match="foreign_vector_rows"):
        audit.capture_state(db, TENANT)


def test_blob_bytes_are_streamed_and_failures_never_use_cache(seeded):
    db, _ = seeded
    config = SimpleNamespace(TENANT_ID=TENANT, AZURE_BLOB_CONTAINER_ORIGINALS="originals")
    class Blob:
        content = [b"%PDF-", b"private bytes"]
        def get_blob_client(self, *, container, blob):
            assert (container, blob) == ("originals", "private.pdf")
            return self
        def download_blob(self): return self
        def chunks(self): return iter(self.content)
    blob = Blob()
    before = audit.blob_fingerprint(db, config, client=blob)
    assert before["count"] == 1 and before["bytes"] == len(b"%PDF-private bytes")
    blob.content = [b"%PDF-", b"changed bytes"]
    assert audit.blob_fingerprint(db, config, client=blob)["sha256"] != before["sha256"]
    def failed(): raise RuntimeError("private storage exception")
    blob.download_blob = failed
    with pytest.raises(RuntimeError): audit.blob_fingerprint(db, config, client=blob)
    config.AZURE_BLOB_CONTAINER_ORIGINALS = "different"
    with pytest.raises(audit.AuditError, match="blob_container_mismatch"):
        audit.blob_fingerprint(db, config, client=blob)


def test_compare_requires_a_new_revision_and_rejects_wrong_target(seeded):
    db, _ = seeded
    before = checkpoint(db)
    assert audit.compare(before, deepcopy(before))["state_preserved"]
    assert not audit.compare(before, deepcopy(before), require_new_revision=True)["state_preserved"]
    after = deepcopy(before)
    after["context"].update(revision="new-revision", replica="new-replica", app_version="new-version")
    assert audit.compare(before, after, require_new_revision=True)["state_preserved"]
    after["runtime"]["JWT_SECRET"] = audit.fingerprint("different key")
    assert audit.compare(before, after)["changes"] == ["runtime"]
    after["target"]["tenant"] = "different"
    with pytest.raises(audit.AuditError, match="checkpoint_target_mismatch"):
        audit.compare(before, after)


@pytest.mark.parametrize("damage", ["empty", "missing-table", "invalid-hash", "missing-index", "no-runtime"])
def test_malformed_or_truncated_receipt_cannot_pass(seeded, damage):
    db, _ = seeded
    value = checkpoint(db)
    if damage == "empty": value = {}
    elif damage == "missing-table": del value["state"]["tables"]["users"]
    elif damage == "invalid-hash": value["state"]["tables"]["users"]["sha256"] = "invalid"
    elif damage == "missing-index": value["state"]["indexes"].clear()
    else: value["runtime"].clear()
    with pytest.raises(audit.AuditError): audit.compare(value, value)


def test_cli_wrong_target_and_safe_errors_never_emit_private_values(monkeypatch, capsys):
    monkeypatch.setattr(settings, "DATABASE_BACKEND", "sqlserver")
    args = ["capture", "--output", "-", "--expect-host", "wrong-host", "--expect-db", "wrong-db",
            "--expect-tenant", "wrong-tenant"]
    assert audit.main(args) == 2
    assert json.loads(capsys.readouterr().err) == {"error": "target_mismatch"}
    def failed(_): raise RuntimeError("PASSWORD=synthetic-secret; private document contents")
    monkeypatch.setattr(audit, "capture", failed)
    assert audit.main(args) == 2
    output = capsys.readouterr()
    assert not output.out and json.loads(output.err) == {"error": "deployment_check_failed"}


def test_checkpoint_file_refuses_overwrite_before_database_access(tmp_path, monkeypatch):
    path = tmp_path / "before.json"
    audit.write_checkpoint(str(path), {"keep": True})
    def unexpected(_): pytest.fail("existing checkpoint must not open SQL")
    monkeypatch.setattr(audit, "capture", unexpected)
    args = ["capture", "--output", str(path), "--expect-host", "x", "--expect-db", "x", "--expect-tenant", "x"]
    assert audit.main(args) == 2
    assert json.loads(path.read_text(encoding="utf-8")) == {"keep": True}


def test_console_bundle_runs_without_installation_or_private_environment(tmp_path, monkeypatch):
    stub = tmp_path / "public_tool.py"
    stub.write_text("import json,sys\nprint(json.dumps(sys.argv))\n", encoding="utf-8")
    monkeypatch.setattr(audit, "__file__", str(stub))
    args = SimpleNamespace(expect_host="host", expect_db="db", expect_tenant="alpha",
        require_index=[str(uuid.uuid4())], require_settings=True, blobs=True)
    script = audit.console_script(args)
    python = "\n".join(script.splitlines()[2:-1])
    result = subprocess.run([sys.executable, "-c", python], capture_output=True, text=True, check=True)
    argv = json.loads(result.stdout)
    assert argv[:4] == ["verify_deployment.py", "capture", "--output", "-"]
    assert args.require_index[0] in argv and "--require-settings" in argv and "--blobs" in argv


def test_native_fingerprint_casts_vector_and_uses_exact_parameterized_tenant():
    ident = uuid.uuid4()
    profile = EmbeddingProfile("synthetic", "1", 768)
    index = DBSearchIndex(index_id=ident, tenant_id="alpha", profile_id=profile.profile_id,
        table_name="chunk_vectors_" + ident.hex, storage_kind="native")
    sql = audit.row_statement(vector_table(index, profile), "alpha ", "mssql", native=True).compile(dialect=mssql.dialect())
    assert "CAST(audit_rows.embedding AS nvarchar(max))" in str(sql)
    assert "HASHBYTES" in str(sql).upper() and "DATALENGTH" in str(sql).upper() and "Latin1_General_100_BIN2" in str(sql)
    assert "alpha " not in str(sql) and "alpha " in sql.params.values()


def test_two_indexes_and_custom_settings_survive_new_engine_and_image_defaults(tmp_path, monkeypatch):
    from app.core import tenant_config
    from app.core.prompts import get_tenant_prompts_map
    from app.core.search_config import SearchConfigManager
    from app.storage import db as db_module
    monkeypatch.setattr(settings, "DATABASE_BACKEND", "sqlserver")
    monkeypatch.setattr(settings, "TENANT_ID", TENANT)
    path = "sqlite:///" + str(tmp_path / "persistent.db")
    engine = create_engine(path)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        seed(db)
        before = checkpoint(db)
    engine.dispose()
    new_engine = create_engine(path)
    factory = sessionmaker(bind=new_engine)
    monkeypatch.setattr(db_module, "engine", new_engine)
    monkeypatch.setattr(db_module, "SessionLocal", factory)
    monkeypatch.setattr(settings, "APP_ENV", "prod")
    monkeypatch.setattr(settings, "DATABASE_BACKEND", "azure_sql")
    defaults = tmp_path / "new-image" / "default"
    defaults.mkdir(parents=True)
    for name in audit.CONFIG_FILES:
        (defaults / name).write_text("{}", encoding="utf-8")
    monkeypatch.setattr(tenant_config, "TENANTS_DIR", str(defaults.parent))
    db_module.init_db(); db_module.init_db()
    assert get_tenant_prompts_map(TENANT)["cs"] == "Private cs {context_str}"
    assert SearchConfigManager().load_config_sync()["summary_custom_prompt"] == "Private summary"
    # Compare SQL state across the independent engine; test-only backend setting changes are excluded here.
    with factory() as db:
        after = checkpoint(db, revision_name="new-revision")
    after["runtime"] = before["runtime"]
    assert audit.compare(before, after, require_new_revision=True)["state_preserved"]
    new_engine.dispose()
