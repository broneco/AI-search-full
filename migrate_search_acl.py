"""Explicit ACL schema/backfill for a human-selected SQL Server/Azure SQL target."""
import argparse

from sqlalchemy import inspect, select, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.storage.db import engine
from app.storage.models import DBChunk, DBChunkACL, DBDocument, DBDocumentACL
from app.storage.acl import rebuild_acl_grants
from app.retrieval.filters import exact_string, exact_value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Create ACL tables and rebuild grants")
    parser.add_argument("--expect-host")
    parser.add_argument("--expect-db")
    parser.add_argument("--expect-tenant")
    args = parser.parse_args()
    if settings.DATABASE_BACKEND not in {"sqlserver", "azure_sql"}:
        parser.error("Choose an explicit sqlserver/azure_sql target using the environment.")
    if args.apply and (args.expect_host, args.expect_db, args.expect_tenant) != (
        settings.AZURE_SQL_HOST, settings.AZURE_SQL_DB, settings.TENANT_ID
    ):
        parser.error("--apply requires matching --expect-host, --expect-db and --expect-tenant.")
    print(f"Target: {settings.AZURE_SQL_HOST} / {settings.AZURE_SQL_DB}; tenant={settings.TENANT_ID}")
    if not {"documents", "chunks"} <= set(inspect(engine).get_table_names()):
        parser.error("Existing document/chunk schema is required; no source database is created.")
    with Session(engine) as session:
        mismatch = session.scalar(select(func.count()).select_from(DBChunk).join(DBDocument).where(
            ~exact_value(DBChunk.tenant_id, DBDocument.tenant_id, engine.dialect.name)
        ))
        tenant_column = exact_string(DBDocument.tenant_id, engine.dialect.name)
        tenants = session.execute(select(tenant_column, func.count()).group_by(
            tenant_column, func.datalength(tenant_column)
        )).all()
        print("Document tenant counts:", tenants)
        print("Chunk/document tenant mismatches:", mismatch)
        if mismatch:
            parser.error("Resolve tenant mismatches with verified provenance before migration; no automatic reassignment.")
    if not args.apply:
        print("Audit only. Quiesce ingestion/writes before --apply and follow the Azure handoff.")
        return
    with engine.begin() as connection:
        DBDocumentACL.__table__.create(connection, checkfirst=True)
        DBChunkACL.__table__.create(connection, checkfirst=True)
    with Session(engine) as session, session.begin():
        rebuild_acl_grants(session)
        for grant in (DBDocumentACL, DBChunkACL):
            projected = session.scalar(select(func.count()).select_from(grant))
            print(f"{grant.__tablename__}: {projected} grants")
    print("ACL projection committed. Deploy matching application and run acceptance tests before activation.")


if __name__ == "__main__":
    main()
