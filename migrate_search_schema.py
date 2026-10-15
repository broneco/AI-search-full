"""Explicit tenant/Unicode rollout migration; callers must stop application writers."""
from sqlalchemy import text


FIELDS = (("documents", "title", "NVARCHAR(512)", 1024),
          ("chunks", "content", "NVARCHAR(MAX)", -1),
          ("chat_threads", "title", "NVARCHAR(512)", 1024),
          ("chat_messages", "content", "NVARCHAR(MAX)", -1))


def quoted(name):
    return "[" + name.replace("]", "]]") + "]"


def exact(column, parameter):
    value = f"CAST(:{parameter} AS VARCHAR(255))"
    return f"{column} COLLATE Latin1_General_100_BIN2 = {value} COLLATE Latin1_General_100_BIN2 AND DATALENGTH({column})=DATALENGTH({value})"


def capture(engine):
    if engine.dialect.name != "mssql":
        raise ValueError("This rollout migration requires SQL Server/Azure SQL.")
    with engine.connect() as conn:
        fields = []
        for table, column, _, _ in FIELDS:
            row = conn.execute(text("SELECT TYPE_NAME(user_type_id) AS type,max_length,is_nullable FROM sys.columns WHERE object_id=OBJECT_ID(:table) AND name=:column"),
                {"table": "dbo." + table, "column": column}).mappings().one()
            fields.append(dict(row))
        ft = conn.execute(text("SELECT c.name AS catalog,i.name AS key_name,f.change_tracking_state_desc AS tracking,f.is_enabled,f.stoplist_id,s.name AS stoplist FROM sys.fulltext_indexes f JOIN sys.fulltext_catalogs c ON c.fulltext_catalog_id=f.fulltext_catalog_id JOIN sys.indexes i ON i.object_id=f.object_id AND i.index_id=f.unique_index_id LEFT JOIN sys.fulltext_stoplists s ON s.stoplist_id=f.stoplist_id WHERE f.object_id=OBJECT_ID('dbo.chunks')")).mappings().one_or_none()
        ftcols = conn.execute(text("SELECT c.name,fc.language_id,fc.type_column_id,fc.statistical_semantics FROM sys.fulltext_index_columns fc JOIN sys.columns c ON c.object_id=fc.object_id AND c.column_id=fc.column_id WHERE fc.object_id=OBJECT_ID('dbo.chunks')")).mappings().all()
        if ft and (len(ftcols) != 1 or ftcols[0]["name"] != "content" or ftcols[0]["type_column_id"] or ftcols[0]["statistical_semantics"]):
            raise ValueError("Unreviewed full-text definition; no migration performed.")
        if ft and ft["tracking"] not in {"AUTO", "MANUAL", "OFF"}:
            raise ValueError("Unreviewed full-text change tracking.")
        return {"columns": fields, "fulltext": dict(ft) if ft else None,
                "language": int(ftcols[0]["language_id"]) if ftcols else None}


def fulltext_sql(snapshot, table="chunks"):
    ft = snapshot["fulltext"]
    if not ft:
        return None
    stoplist = "OFF" if ft["stoplist_id"] is None else "SYSTEM" if ft["stoplist_id"] == 0 else quoted(ft["stoplist"])
    return (f"CREATE FULLTEXT INDEX ON dbo.{quoted(table)}([content] LANGUAGE {int(snapshot['language'])}) "
           f"KEY INDEX {quoted(ft['key_name'])} ON {quoted(ft['catalog'])} "
           f"WITH (CHANGE_TRACKING = {ft['tracking']}, STOPLIST = {stoplist})")


def restore_fulltext(engine, snapshot):
    ft = snapshot["fulltext"]
    if not ft:
        return
    sql = fulltext_sql(snapshot)
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        if not conn.scalar(text("SELECT COUNT(*) FROM sys.fulltext_indexes WHERE object_id=OBJECT_ID('dbo.chunks')")):
            conn.execute(text(sql))
            if not ft["is_enabled"]:
                conn.execute(text("ALTER FULLTEXT INDEX ON dbo.chunks DISABLE"))


def apply(engine, *, source, target, expected_documents, expected_chunks, writers_stopped=False):
    if not writers_stopped:
        raise ValueError("Writers must be stopped before this migration.")
    if not source or not target or source == target:
        raise ValueError("Distinct explicit tenant identities are required.")
    snapshot = capture(engine)
    needs_content = snapshot["columns"][1]["type"] != "nvarchar" or snapshot["columns"][1]["max_length"] != -1
    dropped = False
    if needs_content and snapshot["fulltext"]:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text("DROP FULLTEXT INDEX ON dbo.chunks"))
        dropped = True
    try:
        with engine.begin() as conn:
            conn.execute(text("SET XACT_ABORT ON; SET LOCK_TIMEOUT 10000"))
            mismatch = conn.scalar(text("SELECT COUNT_BIG(*) FROM dbo.chunks c JOIN dbo.documents d ON d.document_id=c.document_id WHERE c.tenant_id COLLATE Latin1_General_100_BIN2<>d.tenant_id COLLATE Latin1_General_100_BIN2 OR DATALENGTH(c.tenant_id)<>DATALENGTH(d.tenant_id)"))
            if mismatch:
                raise ValueError("Chunk/document tenant mismatch; transaction rolled back.")
            counts = []
            for table in ("documents", "chunks"):
                counts.append(conn.scalar(text(f"SELECT COUNT_BIG(*) FROM dbo.[{table}] WITH (UPDLOCK,HOLDLOCK) WHERE " + exact("tenant_id", "source")), {"source": source}))
            if counts != [expected_documents, expected_chunks]:
                raise ValueError("Source counts changed; transaction rolled back.")
            for (table, column, sql_type, size), current in zip(FIELDS, snapshot["columns"]):
                if current["type"] == "nvarchar" and (current["max_length"] == -1 or current["max_length"] >= size > 0):
                    continue
                if current["type"] not in {"varchar", "nvarchar", "text", "ntext"}:
                    raise ValueError("Unreviewed text column type; transaction rolled back.")
                nullable = "NULL" if current["is_nullable"] else "NOT NULL"
                conn.execute(text(f"ALTER TABLE dbo.[{table}] ALTER COLUMN [{column}] {sql_type} {nullable}"))
            for table in ("chunks", "documents"):
                changed = conn.execute(text(f"UPDATE dbo.[{table}] SET tenant_id=CAST(:target AS VARCHAR(255)) WHERE " + exact("tenant_id", "source")), {"target": target, "source": source})
                expected = expected_chunks if table == "chunks" else expected_documents
                if changed.rowcount != expected:
                    raise ValueError("Update count changed; transaction rolled back.")
    finally:
        # FTS DDL is autocommit, separately from the reversible data/type transaction.
        if dropped:
            restore_fulltext(engine, snapshot)
    return {"documents_moved": expected_documents, "chunks_moved": expected_chunks, "unicode_verified": True}
