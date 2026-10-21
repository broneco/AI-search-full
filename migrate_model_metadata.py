"""Create the model description table; default is a read-only target plan."""
import argparse
import json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expect-host")
    parser.add_argument("--expect-db")
    parser.add_argument("--expect-tenant")
    args = parser.parse_args()
    from app.core.config import settings
    from app.storage.db import engine
    from app.storage.models import DBModelDescription
    host = settings.AZURE_SQL_HOST if settings.USE_AZURE_SQL else settings.POSTGRES_HOST
    database = settings.AZURE_SQL_DB if settings.USE_AZURE_SQL else settings.POSTGRES_DB
    print(json.dumps(dict(host=host, database=database, tenant=settings.TENANT_ID, apply=args.apply)))
    if args.apply:
        if (args.expect_host, args.expect_db, args.expect_tenant) != (host, database, settings.TENANT_ID):
            raise ValueError("Apply requires exact expected host, database and tenant.")
        with engine.begin() as connection:
            DBModelDescription.__table__.create(connection, checkfirst=True)


if __name__ == "__main__":
    main()
