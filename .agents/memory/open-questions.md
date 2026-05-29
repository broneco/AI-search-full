# Open Questions Memory

## Product and data

1. What are the first document sources for the technical spike?
2. What document types must be supported first: PDF, DOCX, MD, HTML, JSON, or TXT?
3. What is the expected MVP document/chunk volume?
4. How should source-system permissions map to chunk/document ACL metadata?
5. What is the target latency budget for `flash` and `thinking` mode?

## Azure and deployment

1. Which Azure subscription/resource group/region should the pilot use?
2. Which Azure AI Foundry deployments will be used for `flash`, `thinking`, and `embedding` profiles?
3. Should PostgreSQL use password auth initially or managed identity from the beginning?
4. What networking restrictions are required for MVP?

## Evaluation

1. Who owns the first retrieval eval dataset?
2. What are 20 representative company questions for recall/freshness/citation testing?
3. What is acceptable recall@k for the pilot?
