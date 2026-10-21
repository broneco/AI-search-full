"""DiskANN v3+ execution; explicit modes and no automatic full-scan retry."""
from dataclasses import dataclass
from contextlib import contextmanager
import json
import logging
import re
import time

from sqlalchemy import Float, Integer, String, Unicode, bindparam, literal_column, select, text
from sqlalchemy.dialects import mssql
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, defer
from app.core.config import settings

from app.providers.embeddings import EmbeddingProfile
from app.retrieval.filters import eligibility_filters
from app.storage.models import DBChunk, DBDocument, DBSearchIndex
from app.storage.vector_store import (
    SearchIndexError, active_index, coverage, exact_candidates, index_profile, vector_table,
)

logger = logging.getLogger(__name__)


class SearchExecutionError(SearchIndexError):
    def __init__(self, code: str, message: str, status_code: int = 503):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


@contextmanager
def sql_query_timeout(session: Session, seconds: int):
    """Bound new ODBC statements and restore pooled connection settings on exit."""
    if type(seconds) is not int or not 1 <= seconds <= 120:
        raise SearchIndexError("vector_query_timeout_seconds must be an integer in 1..120.")
    if session.bind.dialect.name != "mssql":
        yield
        return
    driver = session.connection().connection.driver_connection
    previous = driver.timeout
    driver.timeout = seconds
    try:
        yield
    finally:
        try:
            driver.timeout = previous
        except Exception:
            # An invalidated/closed connection will not reenter the pool.
            logger.debug("Timed-out vector SQL connection was closed and will not reenter the pool")


def execution_error(error: DBAPIError, operation: str) -> SearchExecutionError:
    # Never include SQL, query vectors, ACL values or driver connection details.
    state = str(error.orig.args[0]) if getattr(error.orig, "args", ()) else "unknown"
    if not re.fullmatch(r"[A-Z0-9]{5}", state):
        state = "unknown"
    timed_out = state in {"HYT00", "HYT01"}
    logger.warning("Vector SQL operation=%s sqlstate=%s", operation, state[:5])
    return SearchExecutionError("search_timeout" if timed_out else "search_unavailable",
        "Vector search timed out; no fallback scan was started." if timed_out else
        "Vector search is unavailable; verify the database/index configuration.", 504 if timed_out else 503)


@dataclass(frozen=True)
class AnnIndex:
    name: str
    version: int | None
    metric: str
    index_type: str
    disabled: bool

    def require_ready(self) -> None:
        if self.disabled or self.metric.lower() != "cosine" or self.index_type.lower() != "diskann":
            raise SearchIndexError("ANN requires an enabled cosine DiskANN index on embedding; use exact mode.")
        if self.version is None or self.version < 3:
            raise SearchIndexError("ANN requires vector index version >=3 for iterative filters and DML; use exact mode.")


def ann_index_status(session: Session, index: DBSearchIndex) -> AnnIndex | None:
    vector_table(index, index_profile(session, index))  # Validate server identifiers/profile first.
    if index.storage_kind != "native" or session.bind.dialect.name != "mssql":
        return None
    statement = text("""SELECT vi.name, JSON_VALUE(vi.build_parameters, '$.Version') AS version,
        vi.distance_metric, vi.vector_index_type, vi.is_disabled
        FROM sys.vector_indexes vi
        JOIN sys.index_columns ic ON ic.object_id = vi.object_id AND ic.index_id = vi.index_id
        JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
        WHERE vi.object_id = OBJECT_ID(:table_name) AND c.name = N'embedding'""")
    try:
        rows = session.execute(statement, {"table_name": "dbo." + index.table_name}).all()
    except DBAPIError as error:
        raise execution_error(error, "ann_catalog") from error
    if not rows:
        return None
    if len(rows) != 1:
        raise SearchIndexError("Ambiguous vector index metadata; use exact mode and audit the index.")
    name, version, metric, kind, disabled = rows[0]
    try:
        version = int(version) if version is not None else None
    except (TypeError, ValueError):
        version = None
    return AnnIndex(name, version, metric or "", kind or "", bool(disabled))


@dataclass(frozen=True)
class VectorSearchPlan:
    index: DBSearchIndex
    mode: str
    ann_index: AnnIndex | None = None

    def validate(self, tenant: str, profile: EmbeddingProfile, mode: str) -> None:
        if mode not in {"exact", "ann"}:
            raise SearchIndexError("vector_search_mode must be exact or ann.")
        if (self.index.tenant_id != tenant or self.index.profile_id != profile.profile_id or
                self.index.corpus_id != "tenant-chunks-v1" or self.mode != mode):
            raise SearchIndexError("Prepared vector search tenant/profile/mode mismatch.")
        if mode == "ann":
            if self.ann_index is None or self.index.storage_kind != "native":
                raise SearchIndexError("Prepared ANN search has no native index.")
            self.ann_index.require_ready()


def prepare_vector_search(session: Session, tenant: str, profile: EmbeddingProfile, mode: str,
                          *, selected_index: DBSearchIndex | None = None) -> VectorSearchPlan:
    if mode not in {"exact", "ann"}:
        raise SearchIndexError("vector_search_mode must be exact or ann.")
    try:
        index = selected_index if selected_index is not None else active_index(session, tenant, profile)
    except DBAPIError as error:
        raise execution_error(error, "active_catalog") from error
    VectorSearchPlan(index, "exact").validate(tenant, profile, "exact")
    if settings.DATABASE_BACKEND == "azure_sql" and index.storage_kind != "native":
        raise SearchIndexError("Azure search requires native index storage.")
    if mode == "exact":
        return VectorSearchPlan(index, mode)  # No vector-index catalog dependency.
    status = ann_index_status(session, index)
    if status is None:
        raise SearchIndexError("ANN index is missing or native storage is unavailable; select exact mode explicitly.")
    status.require_ready()
    return VectorSearchPlan(index, mode, status)


def create_ann_index(session: Session, index: DBSearchIndex) -> AnnIndex:
    """Operator-only autocommit DDL; never commits or rolls back caller writes."""
    if session.in_transaction():
        raise SearchIndexError("Finish the caller transaction explicitly before creating a DiskANN index.")
    # Preflight owns only the read transaction it opens here. Writers must be stopped.
    try:
        profile = index_profile(session, index)
        table = vector_table(index, profile)
        if index.storage_kind != "native" or session.bind.dialect.name != "mssql":
            raise SearchIndexError("DiskANN provisioning requires native SQL storage.")
        existing = ann_index_status(session, index)
        if existing is not None:
            existing.require_ready()
            return existing
        valid, total = coverage(session, index)
        if valid != total or valid < 100:
            raise SearchIndexError("DiskANN creation requires complete coverage and at least 100 current vectors.")
        name = "diskann_" + index.index_id.hex
        # Rollback expires attached objects; preserve only the validated catalog identity.
        selected = DBSearchIndex(index_id=index.index_id, tenant_id=index.tenant_id,
            profile_id=index.profile_id, table_name=index.table_name,
            storage_kind=index.storage_kind, corpus_id=index.corpus_id)
    finally:
        session.rollback()
    try:
        # Azure SQL error 574: CREATE VECTOR INDEX cannot run in a user transaction.
        with session.get_bind().connect() as connection:
            connection = connection.execution_options(isolation_level="AUTOCOMMIT")
            connection.execute(text(f"CREATE VECTOR INDEX [{name}] ON [dbo].[{table.name}] ([embedding]) "
                                    "WITH (METRIC = 'cosine', TYPE = 'DISKANN', MAXDOP = 1)"))
            with Session(connection) as verification:
                created = ann_index_status(verification, selected)
                if created is None:
                    raise SearchIndexError("Committed vector index creation could not be verified; inspect it and use exact mode.")
                created.require_ready()
                return created
    except DBAPIError as error:
        raise execution_error(error, "ann_create") from error


def _ann_batch(index: DBSearchIndex, profile: EmbeddingProfile, context, query: list[float], limit: int):
    """Bind all values; only validated catalog identifiers/dimensions enter SQL."""
    table = vector_table(index, profile)
    if index.storage_kind != "native":
        raise SearchIndexError("ANN SQL requires native storage.")
    # Reuse exactly the exact/keyword eligibility expressions, including ACL EXISTS.
    # Compile inside the same outer FROM context so ACL EXISTS remains correlated.
    # A standalone boolean expression adds documents/chunks inside its subqueries.
    compiled = select(literal_column("1")).select_from(DBChunk).join(DBDocument).where(
        *eligibility_filters(context, "mssql")).compile(
        dialect=mssql.dialect(paramstyle="named"), compile_kwargs={"render_postcompile": True})
    _, separator, predicate_sql = str(compiled).partition("\nWHERE ")
    if not separator:
        raise SearchIndexError("Could not compile correlated ANN filters.")
    parameter_types = {name: bound.type for bound, name in compiled.bind_names.items()}
    for name, expanded_names in compiled.construct_expanded_state().parameter_expansion.items():
        for expanded_name in expanded_names:
            parameter_types[expanded_name] = parameter_types[name]

    def typed_parameter(match):
        name = match[1]
        original = parameter_types.get(name)
        if isinstance(original, String):
            # Textual pyodbc parameters can still arrive as NVARCHAR despite String.
            # Match the predicate type explicitly, without truncating long filter values.
            sql_type = "NVARCHAR" if isinstance(original, Unicode) else "VARCHAR"
            return f"CAST(:{name} AS {sql_type}(MAX))"
        return match[0]

    predicates = re.sub(r":([A-Za-z_][A-Za-z0-9_]*)\b", typed_parameter, predicate_sql)
    sql = f"""SET NOCOUNT ON;
        DECLARE @query_vector VECTOR({profile.dimensions}) = CAST(CAST(:query_json AS NVARCHAR(MAX)) AS VECTOR({profile.dimensions}));
        DECLARE @eligible TABLE (chunk_id UNIQUEIDENTIFIER NOT NULL PRIMARY KEY, input_revision VARCHAR(128));
        INSERT INTO @eligible (chunk_id, input_revision)
        SELECT chunks.chunk_id, chunks.content_hash FROM chunks
        INNER JOIN documents ON documents.document_id = chunks.document_id
        WHERE {predicates};
        SELECT TOP (:top_k) WITH APPROXIMATE v.chunk_id, vs.distance, v.input_revision
        FROM VECTOR_SEARCH(TABLE = [dbo].[{table.name}] AS v, COLUMN = embedding,
            SIMILAR_TO = @query_vector, METRIC = 'cosine') AS vs WITH (FORCE_ANN_ONLY)
        INNER JOIN @eligible AS eligible ON eligible.chunk_id = v.chunk_id
            AND v.input_revision = eligible.input_revision
        ORDER BY vs.distance ASC"""
    # Preserve the predicate compiler's types, including expanded ACL IN bindings.
    # Turning VARCHAR tenants into NVARCHAR breaks the strict DATALENGTH check.
    parameters = [bindparam(name, value, type_=parameter_types[name])
                  for name, value in compiled.params.items()]
    parameters += [bindparam("query_json", json.dumps(query, allow_nan=False), type_=Unicode()),
                   bindparam("top_k", limit, type_=Integer())]
    return text(sql).bindparams(*parameters)


def _scoped_batch(statement):
    """Keep NOCOUNT inside sp_executesql scope, including errors/cancellation.

    Row-count messages from the eligibility INSERT must not hide the SELECT
    from ODBC. A pooled connection's caller settings must remain unchanged.
    Only compiler-generated SQL enters the batch; values remain bound params.
    """
    compiled = statement.compile(dialect=mssql.dialect(paramstyle="named"))
    definitions = []
    bindings = []
    for name, value in compiled.params.items():
        original = compiled.binds[name].type
        sql_type = ("NVARCHAR(MAX)" if isinstance(original, Unicode) else "VARCHAR(MAX)") if isinstance(original, String) else original.compile(dialect=mssql.dialect())
        definitions.append(f"@{name} {sql_type}")
        bindings.append(bindparam(name, value, type_=original))
    inner = re.sub(r":([A-Za-z_][A-Za-z0-9_]*)\b", lambda m: "@" + m[1], str(compiled))
    sql = "EXEC sys.sp_executesql N'" + inner.replace("'", "''") + "', N'" + ", ".join(definitions) + "'"
    if bindings:
        sql += ", " + ", ".join(f"@{bound.key} = :{bound.key}" for bound in bindings)
    return text(sql).bindparams(*bindings)


def ann_statement(index: DBSearchIndex, profile: EmbeddingProfile, context, query: list[float], limit: int):
    return _scoped_batch(_ann_batch(index, profile, context, query, limit)).columns(
        chunk_id=DBChunk.chunk_id.type, distance=Float(), input_revision=String(64))


def vector_candidates(session: Session, context, query: list[float], profile: EmbeddingProfile,
                      limit: int, mode: str = "exact", *, diagnostics: dict | None = None,
                      timeout_seconds: int = 10, plan: VectorSearchPlan | None = None):
    try:
        with sql_query_timeout(session, timeout_seconds):
            return _vector_candidates(session, context, query, profile, limit, mode, diagnostics=diagnostics, plan=plan)
    except DBAPIError as error:
        raise execution_error(error, mode) from error


def _vector_candidates(session: Session, context, query: list[float], profile: EmbeddingProfile,
                       limit: int, mode: str, *, diagnostics: dict | None = None, plan: VectorSearchPlan | None = None):
    started = time.perf_counter()
    if type(limit) is not int or limit < 1:
        raise SearchIndexError("Vector search limit must be a positive integer.")
    profile.validate_vector(query)
    if not any(value != 0 for value in query):
        raise SearchIndexError("Query cosine vector must be non-zero.")
    try:
        plan = plan or prepare_vector_search(session, context.tenant_id, profile, mode)
        plan.validate(context.tenant_id, profile, mode)
        index, status = plan.index, plan.ann_index
        if mode == "exact":
            rows = exact_candidates(session, context, query, profile, limit, index=index)
        else:
            # Fetch only IDs/distances, then authorized text; no JSON embeddings in the response.
            winners = session.execute(ann_statement(index, profile, context, query, limit)).all()
            if winners:
                vectors = vector_table(index, profile)
                hydrated = session.execute(select(DBChunk, DBDocument).join(DBDocument).join(
                    vectors, vectors.c.chunk_id == DBChunk.chunk_id).where(
                    DBChunk.chunk_id.in_([row[0] for row in winners]),
                    *eligibility_filters(context, session.bind.dialect.name), vectors.c.input_revision == DBChunk.content_hash
                ).options(defer(DBChunk.embedding)).execution_options(populate_existing=True)).all()
                by_id = {row[0].chunk_id: row for row in hydrated}
                rows = [(by_id[cid][0], by_id[cid][1], 0.0, 1.0 - float(distance))
                        for cid, distance, input_revision in winners
                        if cid in by_id and by_id[cid][0].content_hash == input_revision]
            else:
                rows = []
    except DBAPIError as error:
        raise execution_error(error, mode) from error
    if diagnostics is not None:
        diagnostics.update({"vector_mode": mode, "index_id": str(index.index_id), "profile_id": profile.profile_id,
            "storage": index.storage_kind, "ann_index_version": status.version if status else None,
            "vector_candidates": len(rows), "vector_latency_ms": round((time.perf_counter() - started) * 1000)})
    return rows
