"""Explicit vector migration CLI; audit is default, no Azure auto deployment."""
import argparse
import asyncio
import json
import uuid

from sqlalchemy import inspect, select

from app.core.config import settings
from app.providers.factory import catalog_embedding_provider
from app.core.embedding_config import embedding_entry
from app.storage.db import engine, SessionLocal
from app.storage.models import DBEmbeddingProfile, DBSearchIndex, DBActiveSearchIndex
from app.storage.vector_store import provision_index, coverage, activate_index, index_profile, tenant_key, SearchIndexError
from app.ingestion.index_backfill import backfill_index
from app.storage.ann_search import ann_index_status, create_ann_index
from dataclasses import asdict


async def run(args):
    target = {"host": settings.AZURE_SQL_HOST, "database": settings.AZURE_SQL_DB, "tenant": settings.TENANT_ID}
    print(json.dumps(target))
    mutation = args.create or args.reembed or args.proven_legacy or args.activate or args.create_ann
    if mutation and (args.expect_host, args.expect_db, args.expect_tenant) != (
        settings.AZURE_SQL_HOST, settings.AZURE_SQL_DB, settings.TENANT_ID
    ):
        raise SearchIndexError("Explicit --expect-host/--expect-db/--expect-tenant must match the target before writes.")
    if settings.DATABASE_BACKEND not in {"sqlserver", "azure_sql"}:
        raise SearchIndexError("Vector migration CLI supports SQL Server/Azure SQL only.")
    selected = getattr(args, "embedding_profile", None)
    with SessionLocal() as profile_session:
        entry = embedding_entry(settings.TENANT_ID, selected, session=profile_session) if args.create or selected else None
    if mutation:
        with engine.begin() as connection:
            DBEmbeddingProfile.__table__.create(connection, checkfirst=True)
            DBSearchIndex.__table__.create(connection, checkfirst=True)
            DBActiveSearchIndex.__table__.create(connection, checkfirst=True)
    elif not inspect(engine).has_table("search_indexes"):
        print("No vector catalog; audit only, nothing changed.")
        return
    with SessionLocal() as session:
        if args.create:
            index = provision_index(session, settings.TENANT_ID, entry.space(),
                                    native=settings.DATABASE_BACKEND == "azure_sql")
            session.commit()
        elif args.index:
            index = session.get(DBSearchIndex, uuid.UUID(args.index))
            if index is None or index.tenant_id != settings.TENANT_ID:
                raise SearchIndexError("Index is unavailable for this tenant.")
            if entry is not None and entry.space() != index_profile(session, index):
                raise SearchIndexError("Selected embedding profile differs from the existing index.")
        else:
            active = session.get(DBActiveSearchIndex, tenant_key(settings.TENANT_ID))
            indexes = session.scalars(select(DBSearchIndex)).all()
            for index in indexes:
                if index.tenant_id == settings.TENANT_ID:
                    space = index_profile(session, index)
                    result = {"index_id": str(index.index_id), "profile_id": index.profile_id,
                              "model": space.model_id, "dimensions": space.dimensions,
                              "storage": index.storage_kind, "coverage": coverage(session, index),
                              "active": bool(active and active.tenant_id == settings.TENANT_ID and active.index_id == index.index_id)}
                    if args.ann_status:
                        status = ann_index_status(session, index)
                        result["ann_index"] = asdict(status) if status else None
                    print(json.dumps(result))
            if mutation:
                raise SearchIndexError("Select --index or --create before backfill/activation.")
            return
        if args.reembed or args.proven_legacy:
            provider = catalog_embedding_provider(settings.TENANT_ID, space=index_profile(session, index), session=session) if args.reembed else None
            count = await backfill_index(session, index, provider=provider, proven_legacy=args.proven_legacy)
            print(json.dumps({"backfilled_chunks": count}))
        if args.activate:
            # Do not activate an index that this runtime cannot query.
            catalog_embedding_provider(settings.TENANT_ID, space=index_profile(session, index), session=session)
            activate_index(session, index)
            session.commit()
        if args.create_ann:
            # All requested writes above commit explicitly. End only the remaining CLI read
            # transaction; CREATE VECTOR INDEX must use its own autocommit connection.
            session.rollback()
            status = create_ann_index(session, index)
            print(json.dumps({"ann_index": asdict(status)}))
        elif args.ann_status:
            status = ann_index_status(session, index)
            print(json.dumps({"ann_index": asdict(status) if status else None}))
        print(json.dumps({"index_id": str(index.index_id), "profile_id": index.profile_id,
                          "storage": index.storage_kind, "coverage": coverage(session, index),
                          "activation_requested": args.activate}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--create", action="store_true")
    parser.add_argument("--index")
    parser.add_argument("--embedding-profile", help="Tenant embedding_config profile ID, e.g. jhu-nomic")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--reembed", action="store_true")
    group.add_argument("--proven-legacy", action="store_true")
    parser.add_argument("--activate", action="store_true")
    parser.add_argument("--create-ann", action="store_true", help="Explicit DiskANN DDL; does not enable ANN queries")
    parser.add_argument("--ann-status", action="store_true", help="Read native vector index version/metric status")
    for field in ("host", "db", "tenant"):
        parser.add_argument(f"--expect-{field}")
    args = parser.parse_args()
    if args.index and args.create:
        parser.error("Choose --index OR --create.")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
