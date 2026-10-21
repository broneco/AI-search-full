"""Explicit, tenant-scoped corpus refresh; default invocation is a read-only plan."""
import argparse
import asyncio
import json


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", help="Exact configured TENANT_ID, including environment suffix")
    parser.add_argument("--data-dir", help="Explicit PDF/TXT source directory")
    parser.add_argument("--summary-model-id")
    parser.add_argument("--classification-model-id")
    parser.add_argument("--apply", action="store_true", help="Apply replacements and remove stale documents after success")
    parser.add_argument("--expect-host")
    parser.add_argument("--expect-db")
    parser.add_argument("--expect-tenant")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    from app.core.config import settings
    from app.ingestion.refresh import refresh_files, refresh_documents

    tenant = args.tenant or settings.TENANT_ID
    files = refresh_files(tenant, args.data_dir)
    host = settings.AZURE_SQL_HOST if settings.USE_AZURE_SQL else settings.POSTGRES_HOST
    database = settings.AZURE_SQL_DB if settings.USE_AZURE_SQL else settings.POSTGRES_DB
    print(json.dumps({"tenant": tenant, "host": host, "database": database,
                      "source_files": len(files), "apply": args.apply}))
    if not args.apply:
        return 0
    if args.expect_tenant != tenant:
        raise ValueError("Apply requires --expect-tenant matching the configured TENANT_ID.")
    if settings.APP_ENV not in {"local", "test"} and (
        not args.expect_host or not args.expect_db
    ):
        raise ValueError("Cloud apply requires --expect-host and --expect-db.")
    if args.expect_host is not None and args.expect_host != host:
        raise ValueError("Database host differs from the reviewed target.")
    if args.expect_db is not None and args.expect_db != database:
        raise ValueError("Database name differs from the reviewed target.")
    asyncio.run(refresh_documents(tenant, files, model_selection={"summary_model_id": args.summary_model_id, "classification_model_id": args.classification_model_id}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as error:
        raise SystemExit(str(error)) from None
