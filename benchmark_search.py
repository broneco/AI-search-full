"""Prepare query embeddings separately; benchmark retrieval without chat/model calls."""
import argparse
import asyncio
import json
from pathlib import Path
import uuid

from sqlalchemy.exc import DBAPIError

from app.core.config import settings
from app.core.search_config import SearchConfigManager
from app.evaluation.search_benchmark import Dataset, QueryCache, BenchmarkError, benchmark_plan, prepare_cache, run_benchmark, write_report
from app.providers.factory import create_embedding_profile, create_embedding_provider
from app.storage.db import SessionLocal
from app.storage.vector_store import SearchIndexError


async def run(args) -> dict:
    target = {"host": settings.AZURE_SQL_HOST, "database": settings.AZURE_SQL_DB, "tenant": settings.TENANT_ID,
              "backend": settings.DATABASE_BACKEND, "port": settings.AZURE_SQL_PORT}
    if (args.expect_host, args.expect_db, args.expect_tenant) != (target["host"], target["database"], target["tenant"]):
        raise BenchmarkError("Confirm exact --expect-host/--expect-db/--expect-tenant before any DB/model work.")
    if args.output.exists():
        raise BenchmarkError("Output already exists; choose a new path.")
    dataset = Dataset.model_validate_json(args.dataset.read_text(encoding="utf-8-sig"))
    profile = create_embedding_profile()
    if args.command == "prepare":
        with SessionLocal() as session:
            benchmark_plan(session, settings.TENANT_ID, profile, "exact", args.index)
        # The DB read transaction is closed before provider network calls.
        cache = await prepare_cache(dataset, create_embedding_provider())
        payload = cache.model_dump(mode="json")
    else:
        cache = QueryCache.model_validate_json(args.cache.read_text(encoding="utf-8-sig"))
        manager = SearchConfigManager()
        config = await manager.load_config()
        payload = await run_benchmark(SessionLocal, dataset, cache, profile, settings.TENANT_ID, args.user_id,
            config, modes=("exact", "ann") if args.compare_ann else ("exact",), requests=args.requests,
            warmups=args.warmups, target=target, selected_index=args.index, config_loader=manager.load_config)
    write_report(args.output, payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("prepare", "run"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument("--dataset", type=Path, required=True)
        command_parser.add_argument("--output", type=Path, required=True)
        command_parser.add_argument("--index", type=uuid.UUID, help="Explicit profile index; can be evaluated before activation")
        for field in ("host", "db", "tenant"):
            command_parser.add_argument(f"--expect-{field}", required=True)
        if command == "run":
            command_parser.add_argument("--cache", type=Path, required=True)
            command_parser.add_argument("--user-id", type=uuid.UUID, required=True)
            command_parser.add_argument("--compare-ann", action="store_true")
            command_parser.add_argument("--requests", type=int, default=200, help="Requests per mode and concurrency")
            command_parser.add_argument("--warmups", type=int, default=3)
            command_parser.add_argument("--require-gates", action="store_true", help="Exit 3 if measured gates fail; still saves report")
    args = parser.parse_args()
    try:
        payload = asyncio.run(run(args))
    except (BenchmarkError, SearchIndexError) as error:
        parser.exit(2, f"Benchmark rejected: {error}\n")
    except (ValueError, OSError, DBAPIError):
        # Validation errors can contain the complete input; never dump them or driver secrets.
        parser.exit(2, "Benchmark rejected or unavailable. Check dataset/cache/profile, confirmed target, user, index and output path.\n")
    if args.command == "run":
        print(json.dumps({"gates": payload["gates"], "quality": payload["quality"]["summary"],
            "performance": [{key: phase[key] for key in ("mode", "concurrency", "summary")} for phase in payload["performance"]]}, indent=2))
        if args.require_gates and not payload["gates"]["measurements_passed"]:
            raise SystemExit(3)
    else:
        print(json.dumps({"profile_id": payload["profile_id"], "cached_queries": len(payload["vectors"])}))


if __name__ == "__main__":
    main()
