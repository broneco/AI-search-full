# Implementation Notes Memory

Use this file for durable notes that future agents need but that are not obvious from code.

## Notes

- **Full-Text Search (FTS) Index Setup**: To prevent transaction aborted exceptions and ugly startup errors, `init_db()` in `app/storage/db.py` queries the system catalogs (`pg_ts_config`) proactively to see if the Czech (`'cs'`) configuration is available. If it is, the GIN index is created using `'cs'`; otherwise, it falls back to the standard `'simple'` text configuration.
- **Python Cosine Similarity Optimization**: Computing cosine similarity sequentially in a database query loop (`select(DBChunk.embedding.cosine_distance(...))`) inside candidate filters is a severe bottleneck for remote PostgreSQL setups. Instead, retrieval computes cosine similarity in pure Python over the loaded embedding lists. Since Azure OpenAI embeddings are L2 normalized, cosine similarity is calculated by dot product divided by vector norms, ensuring lightning-fast candidate evaluation without database network roundtrips.
