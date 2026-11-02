"""Read-only plan / guarded additive schema for durable administrative index jobs."""
import argparse
import json


def console_script(host, database, tenant):
    """Generate reviewed DDL usable in a previous image without the new ORM class."""
    from sqlalchemy.dialects import mssql
    from sqlalchemy.schema import CreateTable
    from app.storage.models import DBIndexPreparationJob
    if not all(isinstance(value,str) and value for value in (host,database,tenant)):
        raise ValueError("Console script requires all three explicit target guards.")
    ddl=str(CreateTable(DBIndexPreparationJob.__table__).compile(dialect=mssql.dialect()))
    return f'''# Generated from the canonical ORM schema; execution writes only the additive jobs table.
import json
from sqlalchemy import inspect
from app.core.config import settings
from app.storage.db import engine
if (settings.AZURE_SQL_HOST,settings.AZURE_SQL_DB,settings.TENANT_ID)!={repr((host,database,tenant))}:
    raise ValueError("Index-job migration target mismatch")
if settings.DATABASE_BACKEND!="azure_sql" or engine.dialect.name!="mssql":
    raise ValueError("This console migration requires Azure SQL")
with engine.begin() as connection:
    if not inspect(connection).has_table("index_preparation_jobs"):
        connection.exec_driver_sql({repr(ddl)})
print(json.dumps({{"table":"index_preparation_jobs","migration":"verified"}}))
'''


def migrate(engine):
    from app.storage.models import DBIndexPreparationJob
    with engine.begin() as connection:
        DBIndexPreparationJob.__table__.create(connection, checkfirst=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expect-host")
    parser.add_argument("--expect-db")
    parser.add_argument("--expect-tenant")
    parser.add_argument("--console-script", action="store_true", help="Generate guarded SQL for the previous cloud image; does not execute it")
    args = parser.parse_args(argv)
    if args.console_script:
        print(console_script(args.expect_host,args.expect_db,args.expect_tenant))
        return
    from app.core.config import settings
    from app.storage.db import engine
    target = (settings.AZURE_SQL_HOST, settings.AZURE_SQL_DB, settings.TENANT_ID)
    if args.apply and (args.expect_host, args.expect_db, args.expect_tenant) != target:
        raise ValueError("Apply requires exact expected host, database and tenant.")
    print(json.dumps(dict(host=target[0], database=target[1], tenant=target[2],
                          table="index_preparation_jobs", apply=args.apply)))
    if args.apply:
        migrate(engine)


if __name__ == "__main__":
    main()
