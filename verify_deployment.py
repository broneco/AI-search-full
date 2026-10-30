"""Read-only deployment preservation checkpoints; never deploys or repairs data."""
import argparse
import base64
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import sys
import uuid
import zlib


class AuditError(Exception):
    """Fixed public codes only: SQL/SDK exceptions can contain private values."""


STATE_TABLES = frozenset({"users", "chat_threads", "chat_messages", "documents", "chunks",
    "document_acl_grants", "chunk_acl_grants", "embedding_profiles", "search_indexes",
    "active_search_indexes", "tenant_settings", "model_access_policies", "tenant_model_registry",
    "model_descriptions", "model_runtime_settings"})
CONFIG_FILES = frozenset({"prompts.json", "search_config.json", "classification_config.json"})


def canonical(value):
    """Stable typed values, including JSON, dates and binary SQL results."""
    if isinstance(value, dict):
        return {key: canonical(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [canonical(item) for item in value]
    if isinstance(value, (datetime, date, uuid.UUID, Decimal)):
        return {"type": type(value).__name__, "value": str(value)}
    if isinstance(value, (bytes, memoryview)):
        return {"type": "bytes", "value": bytes(value).hex()}
    return value


def encoded(value) -> bytes:
    return json.dumps(canonical(value), sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def fingerprint(value) -> str:
    return hashlib.sha256(encoded(value)).hexdigest()


def validate_target(config, expected: dict) -> dict:
    target = dict(host=config.AZURE_SQL_HOST, database=config.AZURE_SQL_DB, tenant=config.TENANT_ID)
    if target != expected:
        raise AuditError("target_mismatch")
    if config.DATABASE_BACKEND not in {"azure_sql", "sqlserver"}:
        raise AuditError("unsupported_database_backend")
    return target


def runtime_fingerprints(config) -> dict:
    # A new version/revision is expected. Credentials, routes and identities must stay stable.
    names = ("APP_ENV", "DATABASE_BACKEND", "AZURE_SQL_HOST", "AZURE_SQL_DB", "AZURE_SQL_PORT",
             "AZURE_SQL_USER", "AZURE_SQL_PASSWORD", "JWT_SECRET", "LEGACY_PASSWORD_SECRET",
             "AZURE_STORAGE_ACCOUNT", "AZURE_STORAGE_CONNECTION_STRING", "AZURE_BLOB_CONTAINER_ORIGINALS",
             "AZURE_KEY_VAULT_NAME", "AZURE_KEY_VAULT_SECRET_JWT_SIGNING_KEY",
             "AZURE_KEY_VAULT_SECRET_JWT_SIGNING_KEY_VERSION", "AZURE_KEY_VAULT_SECRET_LEGACY_PASSWORD",
             "JHU_CONNECTION_MODE", "JHU_SIDECAR_APP_NAME", "JHU_KEY_VAULT_NAME", "JHU_LLM_ENDPOINT",
             "JHU_API_USERNAME_SECRET", "JHU_API_PASSWORD_SECRET", "JHU_GATEWAY_KEY_SECRET")
    return {name: fingerprint(getattr(config, name, None)) for name in names}


def scoped(alias, tenant: str, dialect: str):
    from sqlalchemy import select
    from app.retrieval.filters import exact_value
    from app.storage.models import DBChunk, DBDocument, DBSearchIndex
    if "tenant_id" in alias.c:
        return exact_value(alias.c.tenant_id, tenant, dialect)
    if alias.name == "audit_profiles":
        return alias.c.profile_id.in_(select(DBSearchIndex.profile_id).where(
            exact_value(DBSearchIndex.tenant_id, tenant, dialect)))
    if "document_id" in alias.c:
        return alias.c.document_id.in_(select(DBDocument.document_id).where(
            exact_value(DBDocument.tenant_id, tenant, dialect)))
    if "chunk_id" in alias.c:
        return alias.c.chunk_id.in_(select(DBChunk.chunk_id).where(
            exact_value(DBChunk.tenant_id, tenant, dialect)))
    raise AuditError("unsupported_table_scope")


def row_statement(table, tenant: str, dialect: str, *, profiles=False, native=False):
    """SQL Server hashes server-side, so content/password/vector values never leave SQL."""
    from sqlalchemy import func, literal, literal_column, select
    alias = table.alias("audit_profiles" if profiles else "audit_rows")
    predicate = scoped(alias, tenant, dialect)
    if dialect == "mssql":
        projection = "audit_profiles.*" if profiles else "audit_rows.*"
        if native:
            projection = ("audit_rows.vector_id,audit_rows.chunk_id,audit_rows.input_revision,"
                          "CAST(audit_rows.embedding AS nvarchar(max)) AS embedding")
        value = literal_column(f"(SELECT {projection} FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES)")
        statement = select(func.HASHBYTES(literal_column("'SHA2_256'"), value)).select_from(alias)
    else:
        statement = select(alias)
    return statement.where(predicate).order_by(*alias.primary_key)


def table_fingerprint(db, table, tenant: str, **options) -> dict:
    dialect = db.bind.dialect.name
    statement = row_statement(table, tenant, dialect, **options)
    digest, count = hashlib.sha256(), 0
    for row in db.execute(statement.execution_options(yield_per=256)):
        if dialect == "mssql" and row[0] is None:
            raise AuditError("null_row_fingerprint:" + table.name)
        value = bytes(row[0]) if dialect == "mssql" else hashlib.sha256(encoded(dict(row._mapping))).digest()
        if len(value) != 32:
            raise AuditError("invalid_row_fingerprint")
        digest.update(value)
        count += 1
    return dict(count=count, sha256=digest.hexdigest())


def blob_fingerprint(db, config, *, client=None) -> dict:
    """Stream exact referenced Blob bytes. Never falls back to a cache or fuzzy filename."""
    from sqlalchemy import select
    from app.retrieval.filters import exact_value
    from app.storage.models import DBDocument
    rows = db.execute(select(DBDocument.source_type, DBDocument.source_uri).where(
        exact_value(DBDocument.tenant_id, config.TENANT_ID, db.bind.dialect.name))).all()
    references = set()
    for kind, uri in rows:
        if kind != "azure_blob":
            raise AuditError("non_blob_document_source")
        path = uri.removeprefix("azure://").split("/", 1)
        container, name = path if len(path) == 2 else (config.AZURE_BLOB_CONTAINER_ORIGINALS, path[0])
        if container != config.AZURE_BLOB_CONTAINER_ORIGINALS or not name:
            raise AuditError("blob_container_mismatch")
        references.add((container, name))
    if client is None:
        from app.providers.blob_storage import BlobStorageProvider
        client = BlobStorageProvider().client
    if client is None:
        raise AuditError("blob_storage_unavailable")
    digest, byte_count = hashlib.sha256(), 0
    for container, name in sorted(references):
        content, size = hashlib.sha256(), 0
        for chunk in client.get_blob_client(container=container, blob=name).download_blob().chunks():
            content.update(chunk)
            size += len(chunk)
        digest.update(bytes.fromhex(fingerprint([container, name, content.hexdigest(), size])))
        byte_count += size
    return dict(count=len(references), bytes=byte_count, sha256=digest.hexdigest())


def capture_state(db, tenant: str, *, require_indexes=(), require_settings=False) -> dict:
    from sqlalchemy import func, select
    from app.retrieval.filters import exact_value
    from app.storage.models import Base, DBActiveSearchIndex, DBSearchIndex
    from app.storage.tenant_settings import MUTABLE_CONFIG_FILES, read_setting
    from app.storage.vector_store import coverage, index_profile, vector_table, tenant_key
    tables = {}
    for name, table in sorted(Base.metadata.tables.items()):
        if "tenant_id" in table.c or name in {"document_acl_grants", "chunk_acl_grants", "embedding_profiles"}:
            tables[name] = table_fingerprint(db, table, tenant, profiles=name == "embedding_profiles")
    indexes = {}
    active = db.get(DBActiveSearchIndex, tenant_key(tenant))
    if active is not None and active.tenant_id != tenant:
        raise AuditError("active_index_tenant_mismatch")
    for index in db.scalars(select(DBSearchIndex).where(
            exact_value(DBSearchIndex.tenant_id, tenant, db.bind.dialect.name))):
        profile = index_profile(db, index)
        table = vector_table(index, profile)  # validates UUID/table identity before building SQL
        alias = table.alias("audit_vectors")
        foreign = db.scalar(select(func.count()).select_from(alias).where(
            ~scoped(alias, tenant, db.bind.dialect.name)))
        if foreign:
            raise AuditError("foreign_vector_rows")
        valid, total = coverage(db, index)
        key = str(index.index_id)
        indexes[key] = dict(model=profile.model_id, dimensions=profile.dimensions,
                            profile_id=index.profile_id, storage=index.storage_kind, coverage=[valid, total],
                            ingestion_default=bool(active and active.index_id == index.index_id))
        tables["vectors:" + key] = table_fingerprint(db, table, tenant, native=index.storage_kind == "native")
    for ident in require_indexes:
        item = indexes.get(str(uuid.UUID(ident)))
        if item is None or not item["coverage"][1] or item["coverage"][0] != item["coverage"][1]:
            raise AuditError("required_index_missing_or_incomplete")
    if require_indexes and (active is None or str(active.index_id) not in indexes):
        raise AuditError("active_index_missing")
    configs = {}
    for filename in sorted(MUTABLE_CONFIG_FILES):
        value = read_setting(db, tenant, filename)
        if require_settings and value is None:
            raise AuditError("required_sql_setting_missing")
        configs[filename] = dict(source="default" if value is None else "sql", sha256=fingerprint(value))
    return dict(tables=tables, indexes=indexes, settings=configs)


def validate_checkpoint(value: dict) -> None:
    required = {"schema", "target", "context", "runtime", "state", "blobs"}
    if not isinstance(value, dict) or set(value) != required or value["schema"] != 1:
        raise AuditError("invalid_checkpoint")
    state = value["state"]
    if (not isinstance(state, dict) or set(state) != {"tables", "indexes", "settings"}
            or not isinstance(state["tables"], dict) or not state["tables"]
            or not all(isinstance(value[key], dict) for key in ("target", "context", "runtime"))
            or set(value["target"]) != {"host", "database", "tenant"}
            or not all(isinstance(item, str) and item for item in value["target"].values())
            or not isinstance(state["indexes"], dict) or not isinstance(state["settings"], dict)
            or not STATE_TABLES.issubset(state["tables"]) or set(state["settings"]) != CONFIG_FILES
            or not value["runtime"]):
        raise AuditError("invalid_checkpoint")
    def digest(item):
        return isinstance(item, str) and re.fullmatch(r"[0-9a-f]{64}", item) is not None
    for item in state["tables"].values():
        if (not isinstance(item, dict) or set(item) != {"count", "sha256"}
                or type(item["count"]) is not int or item["count"] < 0 or not digest(item["sha256"])):
            raise AuditError("invalid_checkpoint")
    for name, item in state["indexes"].items():
        if (str(uuid.UUID(name)) != name or not isinstance(item, dict)
                or set(item) != {"model", "dimensions", "profile_id", "storage", "coverage", "ingestion_default"}
                or not digest(item["profile_id"]) or type(item["dimensions"]) is not int
                or not 1 <= item["dimensions"] <= 1998 or type(item["ingestion_default"]) is not bool
                or not isinstance(item["coverage"], list) or len(item["coverage"]) != 2
                or any(type(n) is not int or n < 0 for n in item["coverage"])
                or item["coverage"][0] > item["coverage"][1]
                or "vectors:" + name not in state["tables"]):
            raise AuditError("invalid_checkpoint")
    if state["tables"]["search_indexes"]["count"] != len(state["indexes"]):
        raise AuditError("invalid_checkpoint")
    for item in state["settings"].values():
        if (not isinstance(item, dict) or set(item) != {"source", "sha256"}
                or item["source"] not in {"sql", "default"} or not digest(item["sha256"])):
            raise AuditError("invalid_checkpoint")
    if not all(digest(item) for item in value["runtime"].values()):
        raise AuditError("invalid_checkpoint")
    blob = value["blobs"]
    if blob is not None and (not isinstance(blob, dict) or set(blob) != {"count", "bytes", "sha256"}
            or any(type(blob[k]) is not int or blob[k] < 0 for k in ("count", "bytes"))
            or not digest(blob["sha256"])):
        raise AuditError("invalid_checkpoint")


def compare(before: dict, after: dict, *, require_new_revision=False) -> dict:
    for item in (before, after):
        validate_checkpoint(item)
    if before["target"] != after["target"]:
        raise AuditError("checkpoint_target_mismatch")
    if set(before["runtime"]) != set(after["runtime"]):
        raise AuditError("checkpoint_runtime_schema_mismatch")
    changes = []
    for field in ("runtime", "blobs"):
        if before[field] != after[field]:
            changes.append(field)
    for field in ("tables", "indexes", "settings"):
        old, new = before["state"][field], after["state"][field]
        for name in sorted(set(old) | set(new)):
            if old.get(name) != new.get(name):
                changes.append(field + ":" + name)
    old_revision, new_revision = before["context"].get("revision"), after["context"].get("revision")
    new_revision_observed = bool(old_revision and new_revision and old_revision != new_revision)
    if require_new_revision and not new_revision_observed:
        changes.append("new_revision_not_observed")
    return dict(state_preserved=not changes, changes=changes, new_revision_observed=new_revision_observed,
                blobs_checked=before["blobs"] is not None and after["blobs"] is not None,
                before_context=before["context"], after_context=after["context"])


def write_checkpoint(path: str, value: dict) -> None:
    payload = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if path == "-":
        print(payload, end="")
        return
    # Refuse overwrite/symlinks; restrict mode on systems that support POSIX permissions.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        output.write(payload)


def capture(args) -> dict:
    # Validate target before importing the module that constructs the database engine.
    from app.core.config import settings
    target = validate_target(settings, dict(host=args.expect_host, database=args.expect_db, tenant=args.expect_tenant))
    from sqlalchemy.orm import Session
    from app.storage.db import engine
    from app.storage.ann_search import sql_query_timeout
    result = dict(schema=1, target=target, runtime=runtime_fingerprints(settings),
        context=dict(captured_at=datetime.now(timezone.utc).isoformat(), app_version=settings.APP_VERSION,
            revision=os.environ.get("CONTAINER_APP_REVISION"), replica=os.environ.get("CONTAINER_APP_REPLICA_NAME")),
        state=None, blobs=None)
    # Frozen writes + one serializable read transaction. Never commits or calls init_db.
    with engine.connect().execution_options(isolation_level="SERIALIZABLE") as connection:
        transaction = connection.begin()
        try:
            with Session(bind=connection, autoflush=False) as db, sql_query_timeout(db, 30):
                result["state"] = capture_state(db, settings.TENANT_ID,
                    require_indexes=args.require_index, require_settings=args.require_settings)
                if args.blobs:
                    result["blobs"] = blob_fingerprint(db, settings)
        finally:
            transaction.rollback()
    return result


def console_script(args) -> str:
    """Run this exact public tool in an existing image, without installation or a new image."""
    argv = ["verify_deployment.py", "capture", "--output", "-", "--expect-host", args.expect_host,
            "--expect-db", args.expect_db, "--expect-tenant", args.expect_tenant]
    for ident in args.require_index:
        argv.extend(["--require-index", ident])
    if args.require_settings:
        argv.append("--require-settings")
    if args.blobs:
        argv.append("--blobs")
    source = base64.b64encode(zlib.compress(Path(__file__).read_bytes())).decode("ascii")
    chunks = "\n".join(repr(source[i:i+100]) for i in range(0, len(source), 100))
    return ("cd /app\npython - <<'DEPLOYMENT_AUDIT_PY'\nimport base64,sys,zlib\n"
            "sys.path.insert(0, '/app')\nsys.argv = " + repr(argv) + "\n"
            "exec(compile(zlib.decompress(base64.b64decode(\n" + chunks
            + "\n)), 'verify_deployment.py', 'exec'))\nDEPLOYMENT_AUDIT_PY\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    for action in ("capture", "console-script"):
        command = commands.add_parser(action)
        for field in ("host", "db", "tenant"):
            command.add_argument("--expect-" + field, required=True)
        command.add_argument("--require-index", action="append", default=[], type=str)
        command.add_argument("--require-settings", action="store_true")
        command.add_argument("--blobs", action="store_true", help="Hash all exact referenced Blob bytes (read-only)")
        if action == "capture":
            command.add_argument("--output", required=True, help="New private file, or - for JSON stdout")
    command = commands.add_parser("compare")
    command.add_argument("--before", required=True)
    command.add_argument("--after", required=True)
    command.add_argument("--require-new-revision", action="store_true")
    args = parser.parse_args(argv)
    # SDK/SQL loggers can log URIs, bound parameters and connection credentials.
    previous_logging = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        if args.action == "console-script":
            print(console_script(args), end="")
            return 0
        if args.action == "capture":
            if args.output != "-" and Path(args.output).exists():
                raise AuditError("checkpoint_already_exists")
            value = capture(args)
            validate_checkpoint(value)
            write_checkpoint(args.output, value)
            return 0
        before = json.loads(Path(args.before).read_text(encoding="utf-8-sig"))
        after = json.loads(Path(args.after).read_text(encoding="utf-8-sig"))
        result = compare(before, after, require_new_revision=args.require_new_revision)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["state_preserved"] else 1
    except AuditError as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
    except Exception:
        print(json.dumps({"error": "deployment_check_failed"}), file=sys.stderr)
    finally:
        logging.disable(previous_logging)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
