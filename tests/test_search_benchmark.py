"""Metric/policy correctness, real local reference workloads and drift protection."""
import asyncio
from dataclasses import asdict, replace
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.orm import sessionmaker

import app.evaluation.search_benchmark as evaluation
from app.evaluation.search_benchmark import (BenchmarkError, Case, Dataset, QueryCache, acceptance_gates,
    corpus_snapshot, dataset_hash, distribution, load_phase, percentile, prepare_cache, quality_summary,
    recall_at_30, resolve_context, run_benchmark, write_report)
from app.storage.models import DBChunk
from app.storage.vector_store import SearchIndexError, activate_index, active_index, provision_index, write_embeddings
from test_search_access import access_engine, access_db, document, user
from test_vector_store import PROFILE, vector_db, add_vectors, profile_index


@pytest.fixture
def anyio_backend():
    return "asyncio"


def dataset():
    return Dataset(cases=[Case(case_id="one", query="PRIVATE question", filters={"tag": "wanted"}),
                          Case(case_id="empty", query="No matching document", filters={"tag": "absent"})])


def cache_for(data, profile=PROFILE):
    return QueryCache(profile=asdict(profile), profile_id=profile.profile_id, dataset_hash=dataset_hash(data),
                      vectors={case.case_id: [1.0] + [0.0] * (profile.dimensions - 1) for case in data.cases})


def test_recall_handles_short_and_empty_reference_without_inflation():
    assert recall_at_30(["one", "two"], ["two"]) == .5
    assert recall_at_30(["one"], ["one"]) == 1
    assert recall_at_30(["one"], []) == 0
    assert recall_at_30([], []) is None
    with pytest.raises(BenchmarkError, match="empty"):
        recall_at_30([], ["unauthorized"])
    assert recall_at_30([str(i) for i in range(40)], [str(i) for i in range(30)]) == 1


def test_percentiles_include_slow_failed_requests():
    assert percentile(list(range(1, 201)), .95) == 190
    summary = distribution([{"latency_ms": 1, "error": None}, {"latency_ms": 2000, "error": "search_timeout"}])
    assert summary["p95_ms"] == 2000 and summary["errors"] == 1
    assert percentile([], .95) is None


def test_dataset_and_cache_reject_profiles_duplicates_permissions_and_changed_input():
    data = dataset()
    cache = cache_for(data)
    cache.validate_for(data, PROFILE)
    for profile in (replace(PROFILE, model_revision="other"), replace(PROFILE, dimensions=3)):
        with pytest.raises(BenchmarkError, match="profile"):
            cache.validate_for(data, profile)
    changed = data.model_copy(deep=True)
    changed.cases[0].filters = {"tag": "different"}
    with pytest.raises(BenchmarkError, match="dataset"):
        cache.validate_for(changed, PROFILE)
    with pytest.raises(ValueError):
        Dataset(cases=[data.cases[0], data.cases[0]])
    with pytest.raises(ValueError, match="Duplicate query"):
        Dataset(cases=[data.cases[0], data.cases[0].model_copy(update={"case_id": "another-id"})])
    with pytest.raises(ValueError):
        Case(case_id="injection", query="x", acl_groups=["Management"])
    with pytest.raises(ValueError):
        Case(case_id="invalid", query="x", filters={"tag": {"nested": 1}})
    cache.vectors["one"] = [0.0, 0.0]
    with pytest.raises(BenchmarkError, match="zero"):
        cache.validate_for(data, PROFILE)


@pytest.mark.anyio
async def test_query_cache_embeds_queries_once_and_never_calls_document_mode():
    data = Dataset(cases=[Case(case_id="a", query="same"), Case(case_id="b", query="same", filters={"tag": 1})])
    provider = SimpleNamespace(profile=PROFILE, embed_query=AsyncMock(return_value=[1.0, 0.0]), embed_documents=AsyncMock())
    cache = await prepare_cache(data, provider)
    assert cache.vectors["a"] == cache.vectors["b"]
    provider.embed_query.assert_awaited_once_with("same")
    provider.embed_documents.assert_not_awaited()
    provider.embed_query.side_effect = RuntimeError("PRIVATE provider detail")
    with pytest.raises(BenchmarkError) as caught:
        await prepare_cache(data, provider)
    assert "PRIVATE" not in str(caught.value)


def test_quality_strata_and_duplicate_questions_cannot_pass_sample_gate():
    cases = [{"case_id": str(i), "query_hash": "same question", "selectivity": "le_1_percent",
              "recall_at_30": 1, "error": None} for i in range(100)]
    cases.append({"case_id": "empty", "query_hash": "empty", "selectivity": "empty", "recall_at_30": None, "error": None})
    summary = quality_summary(cases)
    assert summary["nonempty_measured"] == 100 and summary["distinct_nonempty_queries"] == 1
    assert summary["by_selectivity"]["empty"]["mean_recall_at_30"] is None
    assert evaluation.selectivity(1, 1000) == "le_1_percent"
    assert evaluation.selectivity(50, 1000) == "le_10_percent"
    assert evaluation.selectivity(200, 1000) == "broad"


def passing_report():
    snapshot = {"storage": "native", "coverage": [1000, 1000], "corpus_hash": "same"}
    return {"quality": {"summary": {"distinct_nonempty_queries": 100, "mean_recall_at_30": .95, "errors": 0}},
        "config_load_included": True,
        "modes": ["exact", "ann"], "ann_version": 3, "snapshot_before": snapshot, "snapshot_after": dict(snapshot),
        "first_requests": [{"error": None}], "warmups": [], "performance": [
            {"mode": "ann", "concurrency": concurrency, "summary": {"requests": 200, "p95_ms": 1000},
             "samples": [{"error": None}] * 200} for concurrency in (1, 3)]}


def test_measured_gates_never_grant_automatic_cloud_activation():
    report = passing_report()
    assert acceptance_gates(report)["measurements_passed"]
    assert acceptance_gates(report)["activation"] == "human_review_required"
    assert acceptance_gates(report)["cloud_acceptance"].startswith("pending")
    mutations = [lambda r: r.update(ann_version=2), lambda r: r["snapshot_after"].update(corpus_hash="changed"),
        lambda r: r["snapshot_before"].update(storage="local_json"),
        lambda r: r["quality"]["summary"].update(distinct_nonempty_queries=99),
        lambda r: r["quality"]["summary"].update(mean_recall_at_30=.949),
        lambda r: r.update(config_load_included=False),
        lambda r: r["performance"][1]["summary"].update(p95_ms=1001),
        lambda r: r["performance"][1]["summary"].update(requests=199),
        lambda r: r["performance"][0]["samples"][0].update(error="search_timeout")]
    for mutate in mutations:
        report = passing_report()
        mutate(report)
        assert acceptance_gates(report)["activation"] == "blocked"


@pytest.mark.anyio
async def test_load_arrivals_include_event_loop_wait_and_abort_failures():
    data, active, maximum = dataset(), 0, 0
    async def request(case, vector, mode, **kwargs):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(.001)
        active -= 1
        return {"ids": [], "diagnostics": {}}
    samples = await load_phase(SimpleNamespace(execute=request), data, cache_for(data), "exact", 3, 8)
    assert len(samples) == 8 and maximum == 3
    assert all(sample["latency_ms"] >= 1 for sample in samples)
    failed = SimpleNamespace(execute=AsyncMock(side_effect=SearchIndexError("PRIVATE SQL")))
    samples = await load_phase(failed, data, cache_for(data), "ann", 3, 200)
    assert len(samples) == 3 and all(sample["error"] == "invalid_search" for sample in samples)
    assert "PRIVATE" not in json.dumps(samples)


@pytest.mark.anyio
async def test_blocking_sql_queue_time_is_not_hidden(monkeypatch):
    # A deterministic fake clock proves arrival is captured before dispatch.
    clock = [0.0]
    monkeypatch.setattr(evaluation.time, "perf_counter", lambda: clock[0])
    async def blocking(case, vector, mode, **kwargs):
        clock[0] += .1
        return {"ids": [], "diagnostics": {}}
    data = dataset()
    samples = await load_phase(SimpleNamespace(execute=blocking), data, cache_for(data), "exact", 3, 3)
    assert [round(sample["latency_ms"]) for sample in samples] == [100, 200, 300]


def test_report_refuses_overwrite(tmp_path):
    output = tmp_path / "report.json"
    write_report(output, {"kind": "new"})
    with pytest.raises(FileExistsError):
        write_report(output, {"kind": "overwrite"})
    assert json.loads(output.read_text(encoding="utf-8"))["kind"] == "new"


def test_snapshot_detects_metadata_acl_input_and_index_change(vector_db):
    db = vector_db
    doc = document(db, metadata={"tag": "wanted"})
    add_vectors(db, doc, [[1.0, 0.0]])
    index = profile_index(db)
    activate_index(db, index)
    db.commit()
    before = corpus_snapshot(db, "alpha", PROFILE)
    doc.metadata_json = {"tag": "different"}
    db.commit()
    assert corpus_snapshot(db, "alpha", PROFILE) != before
    prior = corpus_snapshot(db, "alpha", PROFILE)
    doc.security_acl = {"allowed_groups": ["HR"]}
    db.commit()
    assert corpus_snapshot(db, "alpha", PROFILE) != prior
    chunk = db.query(DBChunk).first()
    chunk.content = "Changed text"
    db.commit()
    with pytest.raises(BenchmarkError, match="coverage"):
        corpus_snapshot(db, "alpha", PROFILE)


@pytest.mark.anyio
async def test_real_local_benchmark_is_read_only_nonqualifying_and_redacted(vector_db, tmp_path):
    db = vector_db
    normal = user(db)
    hidden_user = user(db, tenant="beta", email="foreign@example.test")
    doc = document(db, metadata={"tag": "wanted"})
    add_vectors(db, doc, [[1.0, 0.0], [0.0, 1.0]])
    hidden = document(db, acl={"allowed_groups": ["HR"]}, metadata={"tag": "wanted"}, title="SECRET")
    add_vectors(db, hidden, [[1.0, 0.0]])
    activate_index(db, profile_index(db))
    db.commit()
    sessions = sessionmaker(bind=db.bind)
    data = dataset()
    runner = evaluation.BenchmarkRunner(sessions, "alpha", PROFILE, normal.user_id,
        {"search_strategy": "vector"}, str(profile_index(db).index_id))
    visible = await runner.execute(data.cases[0], [1.0, 0.0], "exact", candidates=True)
    assert len(visible["ids"]) == 2
    assert not set(visible["ids"]) & {str(item.chunk_id) for item in hidden.chunks}
    with pytest.raises(BenchmarkError, match="tenant"):
        resolve_context(db, data.cases[0], "alpha", hidden_user.user_id)
    before = corpus_snapshot(db, "alpha", PROFILE)
    report = await run_benchmark(sessions, data, cache_for(data), PROFILE, "alpha", normal.user_id,
        {"search_strategy": "hybrid", "summary_custom_prompt": "PRIVATE prompt"}, requests=4, warmups=0)
    assert report["snapshot_before"] == report["snapshot_after"] == before
    assert report["gates"]["activation"] == "blocked"
    assert not report["cold_start_measured"] and report["quality"]["status"] == "ann_not_requested"
    assert [phase["summary"]["requests"] for phase in report["performance"]] == [4, 4]
    assert "PRIVATE" not in json.dumps(report) and "SECRET" not in json.dumps(report)
    write_report(tmp_path / "actual-local-report.json", report)
    with pytest.raises(SearchIndexError, match="missing"):
        await run_benchmark(sessions, data, cache_for(data), PROFILE, "alpha", normal.user_id,
                            {"search_strategy": "vector"}, modes=("exact", "ann"), requests=1)


@pytest.mark.anyio
async def test_comparison_orchestration_keeps_empty_cases_separate_and_detects_drift(monkeypatch):
    data = Dataset(cases=[Case(case_id=f"q{i}", query=f"Distinct question {i}") for i in range(100)] +
                        [Case(case_id="empty", query="Empty reference")])
    state = {"storage": "native", "coverage": [1000, 1000], "corpus_hash": "before", "index_id": str(uuid.uuid4())}
    snapshots = [dict(state), dict(state)]
    monkeypatch.setattr(evaluation, "corpus_snapshot", lambda *args, **kwargs: snapshots.pop(0))
    class Session:
        def __enter__(self): return self
        def __exit__(self, *args): pass
    monkeypatch.setattr(evaluation, "resolve_context", lambda *args: None)
    monkeypatch.setattr(evaluation, "prepare_vector_search", lambda *args: SimpleNamespace(ann_index=SimpleNamespace(version=3)))
    class FakeRunner:
        def __init__(self, *args): pass
        async def execute(self, case, vector, mode, **kwargs):
            ids = [] if case.case_id == "empty" else [str(i) for i in range(30)]
            if mode == "ann" and ids:
                ids[-1] = "different"
            return {"ids": ids, "diagnostics": {}}
        def eligible_count(self, case):
            return 0 if case.case_id == "empty" else 5 if case.case_id == "q0" else 1000
    monkeypatch.setattr(evaluation, "BenchmarkRunner", FakeRunner)
    report = await run_benchmark(Session, data, cache_for(data), PROFILE, "alpha", uuid.uuid4(),
        {"search_strategy": "hybrid"}, modes=("exact", "ann"), requests=200, warmups=1,
        config_loader=AsyncMock(return_value={"search_strategy": "hybrid"}))
    summary = report["quality"]["summary"]
    assert summary["distinct_nonempty_queries"] == 100
    assert summary["mean_recall_at_30"] == pytest.approx(29 / 30)
    assert summary["by_selectivity"]["empty"]["cases"] == 1
    assert summary["by_selectivity"]["le_1_percent"]["cases"] == 1
    assert report["gates"]["measurements_passed"]
    assert report["gates"]["activation"] == "human_review_required"
    snapshots.extend([dict(state), {**state, "corpus_hash": "changed"}])
    report = await run_benchmark(Session, data, cache_for(data), PROFILE, "alpha", uuid.uuid4(),
        {"search_strategy": "vector"}, modes=("exact", "ann"), requests=1, warmups=0)
    assert not report["gates"]["checks"]["complete_stable_corpus"]


@pytest.mark.anyio
async def test_cli_confirms_target_before_reading_files_or_providers(monkeypatch):
    import benchmark_search as cli
    arguments = SimpleNamespace(expect_host="wrong", expect_db="wrong", expect_tenant="wrong")
    with pytest.raises(BenchmarkError, match="Confirm exact"):
        await cli.run(arguments)


@pytest.mark.anyio
async def test_prepare_and_run_cli_roundtrip_uses_cache_not_models(vector_db, tmp_path, monkeypatch):
    import benchmark_search as cli
    db = vector_db
    normal = user(db)
    add_vectors(db, document(db, metadata={"tag": "wanted"}), [[1.0, 0.0]])
    activate_index(db, profile_index(db))
    db.commit()
    monkeypatch.setattr(cli, "SessionLocal", sessionmaker(bind=db.bind))
    monkeypatch.setattr(cli, "create_embedding_profile", lambda: PROFILE)
    provider = SimpleNamespace(profile=PROFILE, embed_query=AsyncMock(return_value=[1.0, 0.0]))
    monkeypatch.setattr(cli, "create_embedding_provider", lambda: provider)
    monkeypatch.setattr(cli.SearchConfigManager, "load_config", AsyncMock(return_value={"search_strategy": "vector"}))
    source, cache, output = (tmp_path / name for name in ("dataset.json", "cache.json", "result.json"))
    write_report(source, dataset().model_dump(mode="json"))
    args = SimpleNamespace(command="prepare", dataset=source, output=cache, index=None,
        expect_host=cli.settings.AZURE_SQL_HOST, expect_db=cli.settings.AZURE_SQL_DB, expect_tenant=cli.settings.TENANT_ID)
    await cli.run(args)
    assert provider.embed_query.await_count == 2
    provider.embed_query.side_effect = AssertionError("Timed benchmark must not call models")
    args.command, args.output, args.cache = "run", output, cache
    args.user_id, args.compare_ann, args.requests, args.warmups = normal.user_id, False, 2, 0
    report = await cli.run(args)
    assert output.is_file() and report["gates"]["activation"] == "blocked"
    assert provider.embed_query.await_count == 2
    with pytest.raises(BenchmarkError, match="exists"):
        await cli.run(args)


@pytest.mark.anyio
async def test_inactive_index_is_evaluated_without_activating_it(vector_db):
    db = vector_db
    normal = user(db)
    items = add_vectors(db, document(db, metadata={"tag": "wanted"}), [[1.0, 0.0]])
    previous = profile_index(db)
    activate_index(db, previous)
    other_profile = replace(PROFILE, model_revision="experiment")
    candidate = provision_index(db, "alpha", other_profile, native=False)
    write_embeddings(db, candidate, other_profile, [{"chunk_id": items[0].chunk_id,
        "input_revision": items[0].content_hash, "embedding": [0.5, 0.5]}])
    db.commit()
    data = dataset()
    report = await run_benchmark(sessionmaker(bind=db.bind), data, cache_for(data, other_profile), other_profile,
        "alpha", normal.user_id, {"search_strategy": "vector"}, selected_index=candidate.index_id, requests=1, warmups=0)
    assert report["snapshot_before"]["index_id"] == str(candidate.index_id)
    assert active_index(db, "alpha", PROFILE).index_id == previous.index_id
    with pytest.raises(BenchmarkError, match="profile mismatch"):
        evaluation.benchmark_plan(db, "alpha", PROFILE, "exact", candidate.index_id)


@pytest.mark.anyio
async def test_per_request_config_io_is_measured_and_drift_rejected(vector_db):
    db = vector_db
    normal = user(db)
    add_vectors(db, document(db), [[1.0, 0.0]])
    activate_index(db, profile_index(db))
    db.commit()
    loader = AsyncMock(return_value={"search_strategy": "vector"})
    runner = evaluation.BenchmarkRunner(sessionmaker(bind=db.bind), "alpha", PROFILE, normal.user_id,
        {"search_strategy": "vector"}, str(profile_index(db).index_id), config_loader=loader)
    case = Case(case_id="config", query="query")
    sample = await evaluation.timed_request(runner, case, [1.0, 0.0], "exact")
    assert sample["error"] is None
    loader.assert_awaited_once()
    loader.return_value = {"search_strategy": "vector", "vector_limit": 100}
    with pytest.raises(BenchmarkError, match="configuration changed"):
        await runner.execute(case, [1.0, 0.0], "exact")


def test_local_benchmark_artifacts_and_credentials_are_excluded_from_docker():
    exclusions = Path(".dockerignore").read_text(encoding="utf-8").splitlines()
    assert all(path in exclusions for path in (".local", ".env.local", ".env.test", ".env.native-test"))


def test_ci_exit_code_blocks_failed_measurements(monkeypatch, capsys):
    import benchmark_search as cli
    monkeypatch.setattr(sys, "argv", ["benchmark_search.py", "run", "--dataset", "input.json", "--cache", "cache.json",
        "--output", "output.json", "--expect-host", "test", "--expect-db", "test", "--expect-tenant", "test",
        "--user-id", str(uuid.uuid4()), "--require-gates"])
    monkeypatch.setattr(cli, "run", AsyncMock(return_value={"gates": {"measurements_passed": False, "activation": "blocked"},
        "quality": {"summary": {}}, "performance": []}))
    with pytest.raises(SystemExit) as caught:
        cli.main()
    assert caught.value.code == 3
    assert "blocked" in capsys.readouterr().out


def test_shipped_university_dataset_is_a_smoke_not_100_query_evaluation():
    shipped = Dataset.model_validate_json(Path("fixtures/local-university/search-smoke.json").read_text(encoding="utf-8"))
    assert len(shipped.cases) == 8
    assert any(case.case_id == "empty" for case in shipped.cases)
