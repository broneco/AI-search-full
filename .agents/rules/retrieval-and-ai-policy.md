# Rule: Retrieval and AI Policy

## Retrieval pipeline target

Build toward this pipeline:

```text
user query
  -> normalize query
  -> detect language
  -> enrich with knowledge base
  -> extract metadata constraints
  -> vector search
  -> full-text search
  -> ACL filtering
  -> metadata filtering
  -> rank fusion
  -> freshness validation
  -> optional reranking
  -> context packing
  -> LLM answer with citations
```

## Evidence rule

LLM answers must be grounded in retrieved evidence unless a task explicitly asks for brainstorming or implementation help.

For product chat/search answers:

- include source citations when evidence is used
- distinguish current vs stale sources
- say when evidence is insufficient
- do not use chunks failing ACL filters

## Agent modes

`flash` mode:

- fast, cheaper, fewer steps
- use for simple factual lookup and short summaries

`thinking` mode:

- multi-step reasoning
- can run follow-up retrieval
- must detect conflicts and missing evidence
- must be more careful with freshness and source priority

## Model profiles

Never hardcode model deployment names.

Use model profiles:

- `flash`
- `thinking`
- `embedding`

Deployment names must come from environment/config/admin settings.
