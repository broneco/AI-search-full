# ADR-0012: Customizable Search Retrieval Parameters

- Status: accepted
- Date: 2026-07-16
- Owners: Antigravity (AI Architect), Ondrej Bronec (Lead Developer)
- Supersedes: None
- Superseded by: None

## Context

Originally, the hybrid search parameter values (RRF weights, search limits, etc.) were hardcoded constants inside `VectorRetriever` and the FastAPI environment settings (`settings.RRF_WEIGHT_VECTOR`, `settings.RRF_WEIGHT_KEYWORD`). 

To optimize search relevance and grounded reasoning quality, business administrators need to tune and adjust these parameters in real time without restarting the application or rebuilding container images. They also need to save these configurations persistently.

## Decision

We decide to:
1. **Implement dynamic JSON Configuration (`search_config.json`)**:
   Store the configuration parameters in a structured JSON file on disk, which is loaded at retrieval time.
2. **Azure Blob Storage Syncing**:
   Use the `SearchConfigManager` to mirror `search_config.json` to the Azure Blob Storage container (`originals`) under key `config/search_config.json` for persistence across container scaling or restarts.
3. **Pydantic Validation**:
   Validate all settings in `SearchConfigSchema` using strict Pydantic range rules (weights `0.0`-`1.0`, limits `5`-`200`, window size `1`-`3`) before saving to ensure application stability.
4. **REST API endpoints**:
   Expose `GET /api/chat/config` and `POST /api/chat/config` routes.
5. **Split Configuration Tab on Frontend**:
   Modify the admin screen to render dynamic categories on the left and search configuration forms on the right.

## Consequences

* **Zero-downtime Tuning**: Administrators can tweak thresholds and limits live.
* **Storage Sync Resilience**: Restarts or scale-ups pull the latest saved configuration from Azure Blob.
* **Safety**: Invalid parameters (e.g. negative limits or weight totals) are rejected by Pydantic before writing.
