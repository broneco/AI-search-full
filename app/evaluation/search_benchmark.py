"""Offline query cache, filtered ANN reference metrics and retrieval load tests."""
import asyncio
from dataclasses import asdict
import datetime
import hashlib
import json
import math
from pathlib import Path
import platform
import time
from typing import Any, Awaitable, Callable
import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import DBAPIError

from app.core.search_config import SearchConfigSchema
from app.providers.embeddings import EmbeddingProfile, EmbeddingProvider
from app.retrieval.base import QueryContext
from app.retrieval.filters import eligibility_filters, exact_value, validate_filters
from app.retrieval.vector import VectorRetriever
from app.storage.ann_search import ann_index_status, execution_error, prepare_vector_search, sql_query_timeout, vector_candidates, SearchExecutionError, VectorSearchPlan
from app.storage.models import DBChunk, DBChunkACL, DBDocument, DBDocumentACL, DBSearchIndex, DBUser
from app.storage.vector_store import SearchIndexError, coverage, index_profile, vector_table
from app.core.config import settings


class BenchmarkError(ValueError):
    """Invalid or non-comparable benchmark inputs; never authorize activation."""


class Case(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    query: str = Field(min_length=1, max_length=10000)
    filters: dict[str, Any] = Field(default_factory=dict)
    user_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def valid_filters(self):
        if not self.query.strip():
            raise ValueError("Query must not be blank.")
        validate_filters(self.filters)
        return self


class Dataset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(default=1, ge=1, le=1)
    cases: list[Case] = Field(min_length=1, max_length=10000)

    @model_validator(mode="after")
    def unique_ids(self):
        if len({case.case_id for case in self.cases}) != len(self.cases):
            raise ValueError("Benchmark case IDs must be unique.")
        contexts = [digest({"query": case.query.strip().casefold(), "filters": case.filters,
                            "user_id": case.user_id}) for case in self.cases]
        if len(set(contexts)) != len(contexts):
            raise ValueError("Duplicate query/filter/user cases cannot inflate benchmark quality.")
        return self


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False, default=str).encode("utf-8")).hexdigest()


def dataset_hash(dataset: Dataset) -> str:
    return digest(dataset.model_dump(mode="json"))


class QueryCache(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(default=1, ge=1, le=1)
    dataset_hash: str
    profile_id: str
    profile: dict[str, Any]
    vectors: dict[str, list[float]]

    def validate_for(self, dataset: Dataset, profile: EmbeddingProfile) -> None:
        if (self.dataset_hash != dataset_hash(dataset) or self.profile_id != profile.profile_id or
                self.profile != asdict(profile)):
            raise BenchmarkError("Query cache dataset/profile mismatch; prepare a new cache.")
        if set(self.vectors) != {case.case_id for case in dataset.cases}:
            raise BenchmarkError("Query cache must cover exactly the dataset cases.")
        profile.validate_vectors(list(self.vectors.values()))
        if any(not any(vector) for vector in self.vectors.values()):
            raise BenchmarkError("Cosine query cache contains a zero vector.")


async def prepare_cache(dataset: Dataset, provider: EmbeddingProvider) -> QueryCache:
    """Explicit model stage; all timed requests subsequently reuse these vectors."""
    by_text = {}
    for case in dataset.cases:
        if case.query not in by_text:
            try:
                by_text[case.query] = await provider.embed_query(case.query)
            except Exception as error:
                raise BenchmarkError("Query embedding preparation failed; verify the configured provider.") from error
    cache = QueryCache(dataset_hash=dataset_hash(dataset), profile_id=provider.profile.profile_id,
        profile=asdict(provider.profile), vectors={case.case_id: by_text[case.query] for case in dataset.cases})
    cache.validate_for(dataset, provider.profile)
    return cache


def write_report(path: Path, payload: dict) -> None:
    """Never overwrite an input/cache/report; default outputs belong under .local/."""
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as output:
        output.write(encoded + "\n")


def recall_at_30(reference: list[str], approximate: list[str]) -> float | None:
    expected, actual = set(reference[:30]), set(approximate[:30])
    if not expected:
        if actual:
            raise BenchmarkError("ANN returned candidates where the exact reference was empty.")
        return None  # Empty cases cannot inflate average recall or the 100-query gate.
    return len(expected & actual) / len(expected)


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(quantile * len(ordered)) - 1)]


def distribution(samples: list[dict]) -> dict:
    elapsed = [sample["latency_ms"] for sample in samples]
    return {"requests": len(samples), "errors": sum(sample["error"] is not None for sample in samples),
        "p50_ms": percentile(elapsed, .5), "p95_ms": percentile(elapsed, .95),
        "max_ms": max(elapsed) if elapsed else None}


def resolve_context(session: Session, case: Case, tenant: str, default_user: uuid.UUID) -> QueryContext:
    """Use current server groups, never group names supplied in dataset/cache."""
    user = session.get(DBUser, case.user_id or default_user)
    if user is None or user.tenant_id != tenant:
        raise BenchmarkError("Benchmark user is missing or belongs to a different tenant.")
    if not isinstance(user.groups, list) or any(not isinstance(group, str) for group in user.groups):
        raise BenchmarkError("Invalid server-side benchmark user groups.")
    groups = sorted({group.strip() for group in user.groups if group.strip()} | {"User"})
    return QueryContext(query=case.query, tenant_id=tenant, user_id=str(user.user_id),
                        acl_groups=groups, filters=case.filters)


def benchmark_plan(session: Session, tenant: str, profile: EmbeddingProfile, mode: str,
                   selected_index: uuid.UUID | None = None) -> VectorSearchPlan:
    if selected_index is None:
        return prepare_vector_search(session, tenant, profile, mode)
    index = session.get(DBSearchIndex, selected_index)
    if index is None or index.tenant_id != tenant or index.corpus_id != "tenant-chunks-v1":
        raise BenchmarkError("Selected benchmark index does not belong to this tenant/corpus.")
    if index_profile(session, index) != profile:
        raise BenchmarkError("Selected benchmark index/provider profile mismatch.")
    if settings.DATABASE_BACKEND == "azure_sql" and index.storage_kind != "native":
        raise BenchmarkError("Azure benchmark requires native storage.")
    status = ann_index_status(session, index) if mode == "ann" else None
    plan = VectorSearchPlan(index, mode, status)
    plan.validate(tenant, profile, mode)
    return plan


def corpus_snapshot(session: Session, tenant: str, profile: EmbeddingProfile, *, include_ann: bool = False,
                    selected_index: uuid.UUID | None = None) -> dict:
    """Stream revision/metadata/ACL identities, not content/embeddings, outside timings."""
    index = benchmark_plan(session, tenant, profile, "exact", selected_index).index
    valid, total = coverage(session, index)
    if valid != total or total == 0:
        raise BenchmarkError("Benchmark requires nonempty complete current index coverage.")
    vectors = vector_table(index, profile)
    dialect = session.bind.dialect.name
    chunks = [column for column in DBChunk.__table__.c if column.name not in {"content", "embedding"}]
    statements = [
        select(*DBDocument.__table__.c).where(exact_value(DBDocument.tenant_id, tenant, dialect)).order_by(DBDocument.document_id),
        select(*chunks).where(exact_value(DBChunk.tenant_id, tenant, dialect)).order_by(DBChunk.chunk_id),
        select(vectors.c.vector_id, vectors.c.chunk_id, vectors.c.input_revision).order_by(vectors.c.vector_id),
        select(DBDocumentACL.document_id, DBDocumentACL.group_name).join(DBDocument).where(
            exact_value(DBDocument.tenant_id, tenant, dialect)).order_by(DBDocumentACL.document_id, DBDocumentACL.group_name),
        select(DBChunkACL.chunk_id, DBChunkACL.group_name).join(DBChunk).where(
            exact_value(DBChunk.tenant_id, tenant, dialect)).order_by(DBChunkACL.chunk_id, DBChunkACL.group_name),
        select(DBUser.user_id, DBUser.groups).where(exact_value(DBUser.tenant_id, tenant, dialect)).order_by(DBUser.user_id),
    ]
    state = hashlib.sha256()
    chunk_corpus_hash = None
    for number, statement in enumerate(statements):
        state.update(str(number).encode())
        cursor = session.execute(statement)
        try:
            for batch in cursor.partitions(200):
                for row in batch:
                    state.update(digest(list(row)).encode())
        finally:
            cursor.close()
        if number == 1:
            chunk_corpus_hash = state.hexdigest()
    status = ann_index_status(session, index) if include_ann else None
    return {"index_id": str(index.index_id), "profile_id": profile.profile_id,
        "storage": index.storage_kind, "coverage": [valid, total], "corpus_hash": state.hexdigest(),
        "chunk_corpus_hash": chunk_corpus_hash,
        "ann_index": asdict(status) if status else None}


class BenchmarkRunner:
    """Fresh session and authoritative identity for every measured request."""
    def __init__(self, session_factory: Callable[[], Session], tenant: str, profile: EmbeddingProfile,
                 user_id: uuid.UUID, config: dict, index_id: str, selected_index: uuid.UUID | None = None,
                 config_loader: Callable[[], Awaitable[dict]] | None = None):
        self.session_factory, self.tenant, self.profile = session_factory, tenant, profile
        self.user_id, self.index_id = user_id, index_id
        self.selected_index = selected_index
        self.config_loader = config_loader
        self.config = SearchConfigSchema(**config).model_dump()

    async def execute(self, case: Case, vector: list[float], mode: str, *, candidates: bool = False) -> dict:
        with self.session_factory() as session:
            context = resolve_context(session, case, self.tenant, self.user_id)
            if self.config_loader is not None:
                current = await self.config_loader()
                if retrieval_config(current) != retrieval_config(self.config):
                    raise BenchmarkError("Search configuration changed during the benchmark.")
            with sql_query_timeout(session, self.config["vector_query_timeout_seconds"]):
                plan = benchmark_plan(session, self.tenant, self.profile, mode, self.selected_index)
            if str(plan.index.index_id) != self.index_id:
                raise BenchmarkError("Active index changed during the benchmark.")
            if candidates:
                diagnostics = {}
                rows = vector_candidates(session, context, vector, self.profile, 30, mode,
                    diagnostics=diagnostics, plan=plan, timeout_seconds=self.config["vector_query_timeout_seconds"])
                return {"ids": [str(row[0].chunk_id) for row in rows], "diagnostics": diagnostics}
            retriever = VectorRetriever(session)
            results = await retriever.retrieve(context, limit=self.config["final_limit"], query_embedding=vector,
                query_profile=self.profile, search_config={**self.config, "vector_search_mode": mode}, vector_plan=plan)
            return {"ids": [item.chunk_id for item in results], "diagnostics": retriever.diagnostics}

    def eligible_count(self, case: Case) -> int:
        with self.session_factory() as session:
            context = resolve_context(session, case, self.tenant, self.user_id)
            plan = benchmark_plan(session, self.tenant, self.profile, "exact", self.selected_index)
            vectors = vector_table(plan.index, self.profile)
            return session.scalar(select(func.count()).select_from(DBChunk).join(DBDocument).join(
                vectors, vectors.c.chunk_id == DBChunk.chunk_id).where(
                *eligibility_filters(context, session.bind.dialect.name), vectors.c.input_revision == DBChunk.content_hash))


async def timed_request(runner, case: Case, vector: list[float], mode: str, *, candidates=False, arrived=None) -> dict:
    started = time.perf_counter() if arrived is None else arrived
    try:
        result = await runner.execute(case, vector, mode, candidates=candidates)
        return {"case_id": case.case_id, "mode": mode, "latency_ms": (time.perf_counter() - started) * 1000,
                "error": None, **result}
    except (SearchIndexError, ValueError, DBAPIError) as error:
        if isinstance(error, DBAPIError):
            error = execution_error(error, "benchmark_request")
        return {"case_id": case.case_id, "mode": mode, "latency_ms": (time.perf_counter() - started) * 1000,
            "error": error.code if isinstance(error, SearchExecutionError) else "invalid_search", "ids": [], "diagnostics": {}}


async def load_phase(runner, dataset: Dataset, cache: QueryCache, mode: str, concurrency: int, requests: int) -> list[dict]:
    """Offer batches concurrently to one event loop, like the current async backend.

    Capture arrival BEFORE task dispatch: synchronous SQL blocking the event loop
    must count in latency for the other outstanding requests, not disappear.
    """
    samples = []
    for offset in range(0, requests, concurrency):
        arrived = time.perf_counter()
        batch = []
        for number in range(offset, min(offset + concurrency, requests)):
            case = dataset.cases[number % len(dataset.cases)]
            batch.append(timed_request(runner, case, cache.vectors[case.case_id], mode, arrived=arrived))
        results = await asyncio.gather(*batch)
        samples.extend(results)
        if any(sample["error"] is not None for sample in results):
            break  # Abort this phase on failure; never hammer a timed-out Basic tier.
    return samples


def selectivity(eligible: int, total: int) -> str:
    if eligible == 0:
        return "empty"
    ratio = eligible / total
    return "le_1_percent" if ratio <= .01 else "le_10_percent" if ratio <= .1 else "broad"


def quality_summary(cases: list[dict]) -> dict:
    valid = [case for case in cases if case["error"] is None and case["recall_at_30"] is not None]
    groups = {}
    for bucket in ("empty", "le_1_percent", "le_10_percent", "broad"):
        selected = [case for case in cases if case["selectivity"] == bucket]
        measured = [case["recall_at_30"] for case in selected if case["error"] is None and case["recall_at_30"] is not None]
        groups[bucket] = {"cases": len(selected), "mean_recall_at_30": sum(measured) / len(measured) if measured else None}
    return {"cases": len(cases), "nonempty_measured": len(valid),
        "distinct_nonempty_queries": len({case["query_hash"] for case in valid}),
        "mean_recall_at_30": sum(case["recall_at_30"] for case in valid) / len(valid) if valid else None,
        "errors": sum(case["error"] is not None for case in cases), "by_selectivity": groups}


def acceptance_gates(report: dict) -> dict:
    quality = report["quality"]["summary"]
    tests = {"complete_stable_corpus": report["snapshot_before"] == report["snapshot_after"],
        "per_request_config_load": report["config_load_included"],
        "native_ann_v3": "ann" in report["modes"] and report["snapshot_before"]["storage"] == "native" and
                         bool(report["ann_version"] and report["ann_version"] >= 3),
        "quality_sample_size": quality["distinct_nonempty_queries"] >= 100,
        "recall_at_30": quality["mean_recall_at_30"] is not None and quality["mean_recall_at_30"] >= .95,
        "zero_errors": quality["errors"] == 0 and all(
            sample["error"] is None for phase in report["performance"] for sample in phase["samples"])
            and all(sample["error"] is None for sample in report["first_requests"] + report["warmups"]),
    }
    for concurrency in (1, 3):
        phases = [phase for phase in report["performance"] if phase["mode"] == "ann" and phase["concurrency"] == concurrency]
        tests[f"ann_p95_concurrency_{concurrency}"] = len(phases) == 1 and phases[0]["summary"]["requests"] >= 200 and (
            phases[0]["summary"]["p95_ms"] is not None and phases[0]["summary"]["p95_ms"] <= 1000)
    return {"checks": tests, "measurements_passed": all(tests.values()),
        "activation": "human_review_required" if all(tests.values()) else "blocked",
        "cloud_acceptance": "pending_native_integration_and_target_runtime_review"}


def retrieval_config(config: dict) -> dict:
    normalized = SearchConfigSchema(**config).model_dump()
    keys = {"search_strategy", "hybrid_strategy", "vector_search_mode", "vector_query_timeout_seconds",
        "vector_weight", "keyword_weight", "rrf_k", "vector_limit", "keyword_limit", "final_limit",
        "vector_final_limit", "keyword_final_limit", "score_threshold", "freshness_boost", "context_expansion",
        "context_expansion_size", "context_max_tokens"}
    return {key: normalized[key] for key in sorted(keys)}


async def run_benchmark(session_factory, dataset: Dataset, cache: QueryCache, profile: EmbeddingProfile,
                        tenant: str, user_id: uuid.UUID, config: dict, *, modes=("exact",), requests=200,
                        warmups=3, target: dict | None = None, selected_index: uuid.UUID | None = None,
                        config_loader: Callable[[], Awaitable[dict]] | None = None) -> dict:
    if tuple(modes) not in {("exact",), ("exact", "ann")}:
        raise BenchmarkError("Use exact, or exact followed by ann; no fake ANN or fallback mode.")
    if type(requests) is not int or not 1 <= requests <= 10000 or type(warmups) is not int or not 0 <= warmups <= 100:
        raise BenchmarkError("Invalid request/warmup count.")
    cache.validate_for(dataset, profile)
    normalized = SearchConfigSchema(**config).model_dump()
    if normalized["search_strategy"] not in {"vector", "hybrid"}:
        raise BenchmarkError("Whole-retrieval benchmark requires vector or hybrid strategy.")
    with session_factory() as session:
        before = corpus_snapshot(session, tenant, profile, include_ann="ann" in modes, selected_index=selected_index)
        for case in dataset.cases:
            resolve_context(session, case, tenant, user_id)
        plan = benchmark_plan(session, tenant, profile, modes[-1], selected_index)
        ann_version = plan.ann_index.version if plan.ann_index else None
    runner = BenchmarkRunner(session_factory, tenant, profile, user_id, normalized, before["index_id"], selected_index, config_loader)
    report = {"version": 1, "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "runtime": {"python": platform.python_version(), "system": platform.system(), "machine": platform.machine()},
        "target": target or {}, "dataset_hash": dataset_hash(dataset),
        "query_cache_hash": digest(cache.model_dump(mode="json")), "profile_id": profile.profile_id,
        "config": retrieval_config(normalized), "config_load_included": config_loader is not None,
        "modes": list(modes), "ann_version": ann_version, "snapshot_before": before,
        "index_selection": "explicit" if selected_index else "active",
        "execution_model": "single_event_loop_batch_arrivals", "scope": "in_process_retrieval_including_config_preflight_and_identity",
        "cold_start_measured": False, "first_requests": [], "warmups": [], "performance": [], "quality": {"cases": []}}
    for mode in modes:
        first = dataset.cases[0]
        report["first_requests"].append(await timed_request(runner, first, cache.vectors[first.case_id], mode))
        if report["first_requests"][-1]["error"] is not None:
            break
        for number in range(warmups):
            case = dataset.cases[number % len(dataset.cases)]
            report["warmups"].append(await timed_request(runner, case, cache.vectors[case.case_id], mode))
            if report["warmups"][-1]["error"] is not None:
                break
        if any(sample["error"] is not None for sample in report["warmups"]):
            break
        for concurrency in (1, 3):
            samples = await load_phase(runner, dataset, cache, mode, concurrency, requests)
            # IDs are unnecessary in performance output; never store text, vectors or raw errors.
            for sample in samples:
                sample.pop("ids")
            report["performance"].append({"mode": mode, "concurrency": concurrency,
                "requested": requests, "summary": distribution(samples), "samples": samples})
            if any(sample["error"] is not None for sample in samples):
                break
        if any(phase["summary"]["errors"] for phase in report["performance"]):
            break
    failed = any(sample["error"] for sample in report["first_requests"] + report["warmups"]) or any(
        phase["summary"]["errors"] for phase in report["performance"])
    report["quality"]["status"] = "skipped_after_failure" if failed else "measured" if "ann" in modes else "ann_not_requested"
    if "ann" in modes and not failed:
        for case in dataset.cases:
            eligible = runner.eligible_count(case)
            exact = await timed_request(runner, case, cache.vectors[case.case_id], "exact", candidates=True)
            approximate = (await timed_request(runner, case, cache.vectors[case.case_id], "ann", candidates=True)
                           if exact["error"] is None else {"ids": [], "error": "reference_unavailable"})
            error = exact["error"] or approximate["error"]
            recall = None
            if error is None:
                try:
                    recall = recall_at_30(exact["ids"], approximate["ids"])
                except BenchmarkError:
                    error = "empty_reference_mismatch"
            report["quality"]["cases"].append({"case_id": case.case_id, "query_hash": digest(case.query.strip().casefold()),
                "eligible_chunks": eligible, "selectivity": selectivity(eligible, before["coverage"][1]),
                "exact_count": len(exact["ids"]), "ann_count": len(approximate["ids"]), "recall_at_30": recall, "error": error})
            if error is not None:
                report["quality"]["status"] = "aborted_after_failure"
                break
    report["quality"]["summary"] = quality_summary(report["quality"]["cases"])
    try:
        with session_factory() as session:
            report["snapshot_after"] = corpus_snapshot(session, tenant, profile, include_ann="ann" in modes, selected_index=selected_index)
    except (SearchIndexError, BenchmarkError, DBAPIError):
        # Preserve the measured report, but a missing/changed/unreadable corpus can never pass.
        report["snapshot_after"] = {"error": "snapshot_unavailable_or_incomplete"}
    report["gates"] = acceptance_gates(report)
    # Remove result IDs even from first/warmup probes before serialization.
    for sample in report["first_requests"] + report["warmups"]:
        sample.pop("ids")
    return report
