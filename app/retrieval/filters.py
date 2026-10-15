"""Shared parameterized eligibility predicates, applied before ranking/limits."""
import datetime
import json

from sqlalchemy import Boolean, String, Unicode, and_, exists, func, literal, or_, select
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import FunctionElement

from app.retrieval.base import QueryContext
from app.storage.models import DBChunk, DBChunkACL, DBDocument, DBDocumentACL


CONTROL_KEYS = {
    "freshness_filter", "search_strategy", "hybrid_strategy", "vector_weight", "keyword_weight",
    "rrf_k", "vector_limit", "keyword_limit", "final_limit", "vector_final_limit",
    "keyword_final_limit", "score_threshold", "freshness_boost", "context_expansion",
    "context_expansion_size", "chunk_size", "chunk_overlap", "context_max_tokens",
}
FILTER_COLUMNS = {
    "title": [DBDocument.title], "document_type": [DBDocument.document_type],
    "language": [DBDocument.language, DBChunk.language], "owner": [DBDocument.owner],
    "source_type": [DBDocument.source_type], "source_uri": [DBDocument.source_uri],
    "freshness_status": [DBDocument.freshness_status, DBChunk.freshness_status],
    "version": [DBDocument.version], "section_title": [DBChunk.section_title],
    "page_number": [DBChunk.page_number], "chunk_index": [DBChunk.chunk_index],
}


def validate_filters(filters: dict) -> None:
    if filters.get("freshness_filter", "all") not in {"all", "latest", "this_year"}:
        raise ValueError("Unsupported freshness filter.")
    for key, value in filters.items():
        if key in CONTROL_KEYS:
            continue
        if not isinstance(key, str) or not key or len(key) > 255:
            raise ValueError("Invalid metadata filter key.")
        values = value if isinstance(value, list) else [value]
        if any(item is not None and type(item) not in (str, int, float, bool) for item in values):
            raise ValueError("Metadata filters support scalar values or arrays of scalars.")
        # Also rejects NaN/Infinity instead of silently broadening a query.
        json.dumps(value, allow_nan=False)


class MetadataEquals(FunctionElement):
    type = Boolean()
    inherit_cache = True


@compiles(MetadataEquals, "sqlite")
def _sqlite_metadata_equals(element, compiler, **kwargs):
    column, expected = [compiler.process(item, **kwargs) for item in element.clauses]
    # json_each decodes strings and preserves array ordinal/type/value semantics.
    return f"""EXISTS (SELECT 1 FROM json_each({column}) actual
        JOIN json_each({expected}) expected ON actual.key = expected.key
        WHERE (actual.type = expected.type OR
               (actual.type IN ('integer','real') AND expected.type IN ('integer','real')))
        AND ((actual.type != 'array' AND actual.value IS expected.value)
          OR (actual.type = 'array'
            AND NOT EXISTS (SELECT key, type, value FROM json_each(CASE WHEN actual.type = 'array' THEN actual.value ELSE '[]' END)
                            EXCEPT SELECT key, type, value FROM json_each(CASE WHEN expected.type = 'array' THEN expected.value ELSE '[]' END))
            AND NOT EXISTS (SELECT key, type, value FROM json_each(CASE WHEN expected.type = 'array' THEN expected.value ELSE '[]' END)
                            EXCEPT SELECT key, type, value FROM json_each(CASE WHEN actual.type = 'array' THEN actual.value ELSE '[]' END)))))"""


@compiles(MetadataEquals, "mssql")
def _mssql_metadata_equals(element, compiler, **kwargs):
    column, expected = [compiler.process(item, **kwargs) for item in element.clauses]
    binary = "COLLATE Latin1_General_100_BIN2"
    # Scalar values retain OPENJSON's type (string/number/bool/null). Arrays
    # compare decoded values and ordinal keys, avoiding whitespace differences.
    return f"""CASE WHEN EXISTS (SELECT 1 FROM OPENJSON(CASE WHEN ISJSON({column}) = 1 THEN {column} ELSE N'{{}}' END) actual
        JOIN OPENJSON({expected}) expected ON actual.[key] {binary} = expected.[key] {binary}
          AND DATALENGTH(actual.[key]) = DATALENGTH(expected.[key])
        WHERE actual.[type] = expected.[type] AND
        ((actual.[type] = 0) OR
         (actual.[type] NOT IN (0,4) AND actual.[value] {binary} = expected.[value] {binary}
           AND DATALENGTH(actual.[value]) = DATALENGTH(expected.[value])) OR
         (actual.[type] = 4
          AND NOT EXISTS (SELECT [key] {binary}, [type], [value] {binary}, DATALENGTH([value]) FROM OPENJSON(CASE WHEN actual.[type] = 4 THEN actual.[value] ELSE N'[]' END)
                          EXCEPT SELECT [key] {binary}, [type], [value] {binary}, DATALENGTH([value]) FROM OPENJSON(CASE WHEN expected.[type] = 4 THEN expected.[value] ELSE N'[]' END))
          AND NOT EXISTS (SELECT [key] {binary}, [type], [value] {binary}, DATALENGTH([value]) FROM OPENJSON(CASE WHEN expected.[type] = 4 THEN expected.[value] ELSE N'[]' END)
                          EXCEPT SELECT [key] {binary}, [type], [value] {binary}, DATALENGTH([value]) FROM OPENJSON(CASE WHEN actual.[type] = 4 THEN actual.[value] ELSE N'[]' END)))))
        THEN 1 ELSE 0 END"""


@compiles(MetadataEquals, "postgresql")
def _postgres_metadata_equals(element, compiler, **kwargs):
    column, expected = [compiler.process(item, **kwargs) for item in element.clauses]
    return f"EXISTS (SELECT 1 FROM jsonb_each(CAST({expected} AS jsonb)) e WHERE (CAST({column} AS jsonb) -> e.key) = e.value)"


def exact_string(column, dialect):
    if dialect == "mssql":
        return column.collate("Latin1_General_100_BIN2")
    return column


def exact_value(column, value, dialect):
    comparison = exact_string(column, dialect) == value
    if dialect == "mssql" and (isinstance(value, str) or isinstance(getattr(value, "type", None), String)):
        # SQL Server pads strings for equality even with BIN2 collation. Length
        # must also match, otherwise tenant 'alpha ' can equal tenant 'alpha'.
        expected = literal(value, type_=column.type) if isinstance(value, str) else value
        return and_(comparison, func.datalength(column) == func.datalength(expected))
    return comparison


def document_filters(context: QueryContext, dialect: str) -> list:
    filters = [exact_value(DBDocument.tenant_id, context.tenant_id, dialect)]
    if "Management" not in context.acl_groups:
        groups = sorted(set(context.acl_groups) | {"User"})
        filters.append(exists(select(1).where(
            DBDocumentACL.document_id == DBDocument.document_id,
            DBDocumentACL.group_name.in_(groups),
        )))
    return filters


def eligibility_filters(context: QueryContext, dialect: str, *, metadata=True) -> list:
    filters = document_filters(context, dialect)
    filters.append(exact_value(DBChunk.tenant_id, context.tenant_id, dialect))
    if "Management" not in context.acl_groups:
        groups = sorted(set(context.acl_groups) | {"User"})
        filters.append(exists(select(1).where(
            DBChunkACL.chunk_id == DBChunk.chunk_id, DBChunkACL.group_name.in_(groups),
        )))
    if not metadata:
        return filters
    validate_filters(context.filters)
    freshness = context.filters.get("freshness_filter", "all")
    if freshness == "latest":
        filters.append(exact_value(DBDocument.freshness_status, "current", dialect))
    elif freshness == "this_year":
        year = datetime.datetime.now(datetime.timezone.utc).year
        filters.extend([DBDocument.created_at >= datetime.datetime(year, 1, 1),
                        DBDocument.created_at < datetime.datetime(year + 1, 1, 1)])
    for key, value in context.filters.items():
        if key in CONTROL_KEYS:
            continue
        expected = literal(json.dumps({key: value}, ensure_ascii=False, allow_nan=False), type_=Unicode())
        matches = [MetadataEquals(DBDocument.metadata_json, expected),
                   MetadataEquals(DBChunk.metadata_json, expected)]
        if not isinstance(value, list):
            for column in FILTER_COLUMNS.get(key, []):
                matches.append(exact_value(column, value, dialect) if isinstance(column.type, String) else column == value)
        filters.append(or_(*matches))
    return filters
