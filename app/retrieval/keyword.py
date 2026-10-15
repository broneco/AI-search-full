"""Native SQL Server full-text queries with eligibility before final TOP K."""
import re

from sqlalchemy import Integer, String, Unicode, bindparam, literal_column, select, text
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import Session, defer
from sqlalchemy.sql.selectable import TextualSelect

from app.retrieval.base import QueryContext
from app.retrieval.filters import eligibility_filters
from app.storage.models import DBChunk, DBDocument


def fulltext_condition(query: str) -> str | None:
    """Treat input as words, never as the CONTAINS query language.

    Quoted OR terms retain Unicode, digits and diacritics. SQL Server uses the
    indexed column's language/stoplist; operators and punctuation are ordinary
    input rather than executable full-text syntax. This is word search, not the
    old arbitrary substring matching.
    """
    words = list(dict.fromkeys(re.findall(r"[^\W_]+", query, flags=re.UNICODE)))
    condition = " OR ".join('"' + word + '"' for word in words)
    if len(condition.encode("utf-16-le")) // 2 > 4000:
        raise ValueError("Keyword query exceeds the full-text condition limit of 4000 characters.")
    return condition or None


def fulltext_statement(context: QueryContext, condition: str, limit: int) -> TextualSelect:
    if type(limit) is not int or limit < 1:
        raise ValueError("Keyword limit must be a positive integer.")
    # ODBC can bind Unicode as NVARCHAR(MAX), which CONTAINSTABLE rejects.
    # Its grammar also rejects inline CAST. Declare a bounded server variable.
    compiled = select(literal_column("1")).select_from(DBChunk).join(DBDocument).where(
        *eligibility_filters(context, "mssql")).compile(
            dialect=mssql.dialect(paramstyle="named"), compile_kwargs={"render_postcompile": True})
    _, separator, predicates = str(compiled).partition("\nWHERE ")
    if not separator:
        raise ValueError("Cannot compile correlated keyword eligibility.")
    types = {name: bound.type for bound, name in compiled.bind_names.items()}
    for name, expanded in compiled.construct_expanded_state().parameter_expansion.items():
        for item in expanded:
            types[item] = types[name]
    def typed_parameter(match):
        original = types.get(match[1])
        if isinstance(original, String):
            sql_type = "NVARCHAR" if isinstance(original, Unicode) else "VARCHAR"
            return f"CAST(:{match[1]} AS {sql_type}(MAX))"
        return match[0]
    predicates = re.sub(r":([A-Za-z_][A-Za-z0-9_]*)\b", typed_parameter, predicates)
    # Do not pass top_n_by_rank to CONTAINSTABLE: a global cap would discard
    # eligible rows before tenant, document ACL, chunk ACL and metadata filters.
    sql = f"""DECLARE @fts_query NVARCHAR(4000) = CAST(:fts_condition AS NVARCHAR(4000));
        SELECT TOP (:keyword_limit) chunks.chunk_id, ft.[RANK] AS fts_rank
        FROM chunks INNER JOIN documents ON chunks.document_id = documents.document_id
        INNER JOIN CONTAINSTABLE([dbo].[chunks], [content], @fts_query) AS ft ON ft.[KEY] = chunks.chunk_id
        WHERE {predicates}
        ORDER BY ft.[RANK] DESC, chunks.chunk_id"""
    parameters = [bindparam(name, value, type_=types[name]) for name, value in compiled.params.items()]
    parameters += [bindparam("fts_condition", condition, type_=Unicode(4000)), bindparam("keyword_limit", limit, type_=Integer())]
    return text(sql).bindparams(*parameters).columns(chunk_id=DBChunk.chunk_id.type, fts_rank=Integer())


def fulltext_candidates(session: Session, context: QueryContext, condition: str, limit: int) -> list[tuple]:
    winners = session.execute(fulltext_statement(context, condition, limit)).all()
    if not winners:
        return []
    # Recheck current eligibility during hydration and omit legacy JSON vectors.
    rows = session.execute(select(DBChunk, DBDocument).join(DBDocument).where(
        DBChunk.chunk_id.in_([row[0] for row in winners]),
        *eligibility_filters(context, "mssql"))
        .options(defer(DBChunk.embedding, raiseload=True))).all()
    by_id = {row[0].chunk_id: row for row in rows}
    return [(by_id[cid][0], by_id[cid][1], rank) for cid, rank in winners if cid in by_id]
