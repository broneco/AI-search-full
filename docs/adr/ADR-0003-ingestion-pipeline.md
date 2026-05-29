# ADR-0001: Local PDF Ingestion and Text Chunking Pipeline

- Status: accepted
- Date: 2026-05-28
- Owners: Antigravity Agent, USER
- Supersedes: None
- Superseded by: None

## Context

We need to ingestion-load local PDF corporate files, convert them to tokenizable textual representations, chunk them into contextual elements, calculate semantic embeddings vector representations via Azure OpenAI, and write them directly into the Azure PostgreSQL Flexible Server instance.

To extract text from PDF files inside our Python environment, we must select a robust, lightweight, and open-source PDF parsing library.

## Decision

We decide to:
1. Use **`pypdf`** as our primary local PDF parsing dependency. It is pure-Python, has no external binary OS dependencies, has a fast text extraction API, and handles standard Czech accents and layouts accurately.
2. Implement a **Recursive Paragraph Character Splitter** logic locally inside `app/ingestion/chunking.py`. For Phase 0/1 RAG, we will use standard default chunk constraints: chunk size of **800 characters** and overlap threshold of **150 characters**, which preserves textual semantic flow across overlapping boundaries.
3. Build a lightweight **CLI Ingestion script** (`ingest.py`) at the workspace root, allowing developers to copy local PDF files to a designated folder (e.g., `data/`) and instantly trigger pipeline execution.

## Options considered

### Option A: `pypdf` (Chosen)
- **Pros**: Pure-python, fast, requires no external C-libraries (such as poppler), highly stable, and actively maintained.
- **Cons**: Does not support sophisticated layout detection (e.g. multi-column reading order) out-of-the-box.

### Option B: `pdfplumber`
- **Pros**: Excellent for complex tabular grids and visual layout extraction.
- **Cons**: Slower performance and has complex underlying dependencies.

## Consequences

### Positive:
- Highly lightweight installation footprint with zero external OS software requirements.
- Extremely stable, predictable text parsing execution logs.
- Direct vector similarity index loading within milliseconds.

### Negative / trade-offs:
- Basic page text extraction order may mix headers/footers or read multi-column documents horizontally. This is acceptable for Phase 0 technical spikes and will be hardened in later enterprise ingestion phases.

## Implementation notes

Future agents should leverage `app/ingestion/loaders/local.py` and `app/ingestion/extraction.py` boundaries when incorporating more advanced remote ingestion drivers (such as SharePoint loader or Azure Blob Storage loader).

## Follow-ups

- [x] Add `pypdf` dependency to `pyproject.toml`.
- [x] Implement lokal PDF reader and recursive text splitter chunker.
- [x] Implement `ingest.py` script.
- [x] Verify PDF text ingestion on sample czech documents.
