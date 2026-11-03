"""Read-only plan / additive migration for independent chunking/index pairs."""
import argparse
import json
from app.storage.index_corpus_schema import migrate


def console_script(host: str, database: str, tenant: str) -> str:
    from app.storage.index_corpus_schema import SETTINGS_COLUMNS
    from sqlalchemy.schema import CreateTable
    from sqlalchemy.dialects import mssql
    from app.storage.models import DBIndexSettings, DBIndexDocument
    if not all(isinstance(v, str) and v for v in (host, database, tenant)):
        raise ValueError("All three explicit target guards are required.")
    ddls = [(t.__tablename__, str(CreateTable(t.__table__).compile(dialect=mssql.dialect()))) for t in (DBIndexSettings, DBIndexDocument)]
    return f'''import json
from sqlalchemy import inspect
from app.core.config import settings
from app.storage.db import engine
if (settings.AZURE_SQL_HOST,settings.AZURE_SQL_DB,settings.TENANT_ID)!={repr((host,database,tenant))}:
    raise ValueError("Index corpus migration target mismatch")
if settings.DATABASE_BACKEND!="azure_sql" or engine.dialect.name!="mssql":
    raise ValueError("Azure SQL required")
with engine.begin() as connection:
    if "corpus_id" not in {{c["name"] for c in inspect(connection).get_columns("chunks")}}:
        connection.exec_driver_sql("ALTER TABLE dbo.chunks ADD corpus_id VARCHAR(64) NULL")
    for name,ddl in {repr(ddls)}:
        if not inspect(connection).has_table(name):
            connection.exec_driver_sql(ddl)
    columns = {{c["name"] for c in inspect(connection).get_columns("index_settings")}}
    for name, sql_type in {repr(SETTINGS_COLUMNS)}.items():
        if name not in columns:
            connection.exec_driver_sql("ALTER TABLE dbo.index_settings ADD " + name + " " + sql_type + " NULL")
print(json.dumps({{"migration":"verified","tables":["index_settings","index_documents"],"original_rows_rewritten":False}}))
'''


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--console-script", action="store_true")
    for name in ("host", "db", "tenant"):
        parser.add_argument("--expect-" + name)
    args = parser.parse_args(argv)
    if args.console_script:
        print(console_script(args.expect_host, args.expect_db, args.expect_tenant)); return
    from app.core.config import settings
    from app.storage.db import engine
    target = (settings.AZURE_SQL_HOST, settings.AZURE_SQL_DB, settings.TENANT_ID)
    if args.apply and target != (args.expect_host, args.expect_db, args.expect_tenant):
        raise ValueError("Apply requires exact expected host, DB and tenant.")
    print(json.dumps(dict(host=target[0], database=target[1], tenant=target[2], apply=args.apply,
        operation="add nullable chunks.corpus_id and two tables; preserve all original rows")))
    if args.apply:
        with engine.begin() as connection:
            migrate(connection)


if __name__ == "__main__":main()
