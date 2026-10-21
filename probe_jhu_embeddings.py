"""Synthetic embedding probe using the configured profile and private JHU connection."""
import argparse
import asyncio
import json
import math
import os
import time


async def run(tenant, name):
    from app.providers.factory import catalog_embedding_provider
    provider = catalog_embedding_provider(tenant, name)
    texts = ["Studijní oddělení přijímá žádosti studentů v pondělí a ve středu.",
             "Univerzitní knihovna půjčuje knihy na třicet dnů."]
    started = time.monotonic()
    vectors = await provider.embed_documents(texts)
    documents_ms = round(1000 * (time.monotonic() - started))
    started = time.monotonic()
    query = await provider.embed_query("Kde mohu podat žádost o přerušení studia?")
    scores = [sum(a * b for a, b in zip(query, vector)) /
              (math.hypot(*query) * math.hypot(*vector)) for vector in vectors]
    print(json.dumps({"profile_id": provider.profile.profile_id, "model": provider.profile.model_id,
        "dimensions": len(query), "document_count": len(vectors), "documents_ms": documents_ms,
        "query_ms": round(1000 * (time.monotonic() - started)), "cosine_scores": scores,
        "nearest_document": scores.index(max(scores)) + 1}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", default="jhu")
    parser.add_argument("--embedding-profile", default="jhu-nomic")
    args = parser.parse_args()
    # A local probe must never load cloud tenant env or resolve Key Vault.
    os.environ["APP_ENV"] = "local"
    from app.core.model_config import ModelError
    try:
        asyncio.run(run(args.tenant, args.embedding_profile))
    except ModelError as error:
        print(json.dumps({"error": error.code, "message": str(error)}, ensure_ascii=False))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
