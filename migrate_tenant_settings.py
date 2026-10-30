"""Plan/create tenant_settings and optionally import reviewed JSON without overwriting SQL rows."""
import argparse
import hashlib
import json
from pathlib import Path


def load_import(directory: Path | None) -> dict[str, dict]:
    """Require all three reviewed documents; never guess at bundled or legacy Blob values."""
    if directory is None:
        return {}
    from app.storage.tenant_settings import MUTABLE_CONFIG_FILES, validate_payload
    return {name: validate_payload(name, json.loads((directory / name).read_text(encoding="utf-8-sig")))
            for name in sorted(MUTABLE_CONFIG_FILES)}


def migrate(engine, tenant: str, documents: dict[str, dict]) -> dict[str, str]:
    from sqlalchemy.orm import Session
    from app.storage.models import DBTenantSetting
    from app.storage.tenant_settings import setting_key, validate_payload, write_setting
    # Reject every invalid input before DDL or the first row write.
    for name, data in documents.items():
        setting_key(tenant, name)
        validate_payload(name, data)
    with engine.begin() as connection:
        DBTenantSetting.__table__.create(connection, checkfirst=True)
        with Session(bind=connection) as db:
            result = {name: "imported" if write_setting(db, tenant, name, data, insert_only=True) else "preserved"
                      for name, data in documents.items()}
            db.flush()
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expect-host")
    parser.add_argument("--expect-db")
    parser.add_argument("--expect-tenant")
    parser.add_argument("--import-dir", type=Path)
    args = parser.parse_args(argv)
    from app.core.config import settings
    from app.storage.db import engine
    host = settings.AZURE_SQL_HOST if settings.USE_AZURE_SQL else settings.POSTGRES_HOST
    database = settings.AZURE_SQL_DB if settings.USE_AZURE_SQL else settings.POSTGRES_DB
    if args.apply and (args.expect_host, args.expect_db, args.expect_tenant) != (host, database, settings.TENANT_ID):
        raise ValueError("Apply requires exact expected host, database and tenant.")
    documents = load_import(args.import_dir)
    hashes = {name: hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
              for name, data in documents.items()}
    print(json.dumps(dict(host=host, database=database, tenant=settings.TENANT_ID, apply=args.apply,
                          table="tenant_settings", import_sha256=hashes)))
    if args.apply:
        print(json.dumps(migrate(engine, settings.TENANT_ID, documents)))


if __name__ == "__main__":
    main()
