# Initial Design Doc: Full-stack AI Search Application

## 1. Kontext a cíl projektu

Cílem projektu je vytvořit full-stack aplikaci pro AI vyhledávání nad firemními znalostmi a dokumenty. Aplikace bude poskytovat webové rozhraní a backend API, které umožní vyhledávání pomocí kombinace vektorové podobnosti, tradičního full-text vyhledávání, metadatových filtrů a následného zpracování výsledků pomocí AI modelu.

Projekt je navržen jako Azure-first řešení. Microsoft Azure je jediný akceptovaný vendor lock-in, protože firma má s Microsoftem silné partnerství a očekává se budoucí napojení na Microsoft 365 prostředí, například Teams, Outlook nebo Entra ID.

Architektura nesmí být pevně svázaná s jedním typem frontendu ani s jedním konkrétním LLM providerem. Webová aplikace bude první klient, ale backend musí být postavený tak, aby bylo možné později přidat další rozhraní, například Teams bot, Outlook add-in, interní portál nebo přímé API pro jiné systémy.

Primární jazyk backendu bude Python. Důvodem je silný ekosystém pro AI aplikace, dobrá podpora LangChain/LangGraph, jednoduchá integrace s Azure AI službami a rychlost vývoje.

---

## 2. Hlavní požadavky

### 2.1 Funkční požadavky

Aplikace musí podporovat:

- vyhledávání pomocí vektorové podobnosti,
- tradiční full-text vyhledávání,
- hybridní kombinaci vektorového a textového vyhledávání,
- práci s metadaty dokumentů a chunků,
- kontrolu aktuálnosti nalezených zdrojů před jejich použitím v odpovědi,
- obohacení dotazu o znalosti z interní knowledge base, například zkratky, termíny a aliasy,
- dva režimy AI agenta:
  - `flash` pro rychlé a levnější odpovědi,
  - `thinking` pro složitější dotazy a vícekrokové reasoning workflow,
- citace nebo reference na použité zdroje,
- možnost budoucího rozšíření na Teams, Outlook a další klienty,
- administrační nebo interní rozhraní pro správu dokumentů, ingest pipeline a knowledge base.

### 2.2 Nefunkční požadavky

Aplikace musí splňovat:

- Azure-first provozní model,
- minimální vendor lock-in mimo Microsoft Azure,
- modulární architekturu,
- možnost výměny LLM provideru, embedding modelu i search backendu,
- bezpečné filtrování výsledků podle oprávnění uživatele,
- auditovatelnost AI odpovědí,
- observability pro API, retrieval, LLM volání a ingestion,
- možnost verzování dokumentů a práce s aktuálností zdrojů,
- možnost horizontálního rozšiřování backendu a ingestion workerů.

---

## 3. Architektonické rozhodnutí

Pro první verzi bude jako hlavní datová a vyhledávací vrstva použit **Azure Database for PostgreSQL Flexible Server** s rozšířením **pgvector**.

PostgreSQL bude sloužit jako centrální úložiště pro:

- dokumenty,
- chunky,
- embeddings,
- metadata,
- ACL informace,
- audit logy,
- feedback,
- konfiguraci agentů,
- glossary a knowledge base záznamy,
- search sessions.

Toto rozhodnutí snižuje počet komponent v MVP a zároveň drží architekturu přenositelnou. PostgreSQL a pgvector jsou dostatečně obecné technologie, které nejsou pevně svázané s jednou proprietární search službou. Pokud se v pozdější fázi ukáže, že výkon nebo relevance PostgreSQL vrstvy nestačí, search vrstva bude rozšířitelná přes provider rozhraní o Qdrant, Azure AI Search, OpenSearch nebo jiný specializovaný backend.

Azure AI Search nebude součástí MVP. Důvodem je snížení provozní a nákladové komplexity první verze. Architektura ale nebude jeho budoucí použití blokovat.

Chroma nebude použitá jako produkční vector store. Může sloužit pro lokální experimenty nebo rychlé prototypování, ale produkční řešení bude stát na managed databázi v Azure.

Databricks nebude použitý jako primární search backend. Jeho využití dává smysl pouze v případě, že se budoucí firemní data platforma bude významně opírat o lakehouse architekturu a Databricks bude strategickou datovou platformou.

---

## 4. Cílový tech stack

### 4.1 Frontend

- **Next.js / React**
- TypeScript
- komponentové UI připravené na rozšíření o chat, search a admin obrazovky
- autentizace přes Microsoft Entra ID

Frontend bude první klient backendu. Backend API ale nebude navrženo specificky jen pro web. Stejné API musí být použitelné i pro budoucí Teams nebo Outlook klienty.

### 4.2 Backend

- **Python 3.11+**
- **FastAPI**
- Pydantic pro datové kontrakty
- SQLAlchemy nebo async SQL vrstva nad PostgreSQL
- samostatné moduly pro API, retrieval, ingestion, agent orchestration, providers a observability

Backend bude stateless tam, kde je to možné. Stav konverzací, audit logy, dokumenty a metadata budou uložené v PostgreSQL.

### 4.3 AI orchestrace

- **LangChain** jako integrační vrstva pro modely, retrievery a tooling
- **LangGraph** pro stavové agentní workflow
- vlastní aplikační abstrakce nad LLM, embeddings a retrieval providery

LangChain nebude přímo protékat celou aplikací jako pevná závislost doménového modelu. Bude použit uvnitř providerů a orchestrace. Aplikační kód bude komunikovat přes vlastní rozhraní.

### 4.4 AI modely

- Azure AI Foundry / Azure OpenAI-compatible model deployments
- samostatný model profile pro `flash` režim
- samostatný model profile pro `thinking` režim
- samostatný embedding model deployment

Konkrétní modely budou konfigurovatelné přes prostředí nebo administrační konfiguraci. Kód aplikace nesmí být pevně navázaný na konkrétní název modelu.

### 4.5 Datová vrstva

- **Azure Database for PostgreSQL Flexible Server**
- **pgvector** pro embeddings
- PostgreSQL full-text search pro textové vyhledávání v MVP
- relační tabulky pro dokumenty, chunky, audit, feedback a konfiguraci

### 4.6 Storage

- **Azure Blob Storage**
- ukládání originálních dokumentů
- ukládání extrahovaného textu nebo intermediate artefaktů ingest pipeline
- možnost zpětné dohledatelnosti zdroje chunku

### 4.7 Runtime

- **Azure Container Apps** pro backend API
- Azure Container Apps Jobs nebo samostatný worker pro ingestion
- Azure Container Registry pro images
- managed identity pro přístup k Azure službám

### 4.8 Security a observability

- Microsoft Entra ID
- Azure Key Vault
- Azure Monitor
- Application Insights
- strukturované logování
- audit logy v PostgreSQL

---

## 5. High-level architektura

```text
[Web Frontend / Future Teams Client / Future Outlook Client]
                         |
                         v
                  [Backend API - FastAPI]
                         |
                         v
                [Agent Orchestration Layer]
                  LangGraph / LangChain
                         |
        -------------------------------------
        |                  |                |
        v                  v                v
 [Hybrid Retrieval]   [LLM Provider]   [Knowledge Tools]
        |
        v
 [Search and Metadata Layer]
        |
        |-- Vector Search: PostgreSQL + pgvector
        |-- Full-text Search: PostgreSQL FTS
        |-- Metadata Filtering
        |-- ACL Filtering
        |-- Freshness Validation
        |
        v
 [PostgreSQL: Documents, Chunks, Embeddings, Metadata]
        |
        v
 [Azure Blob Storage: Original Documents and Artifacts]
```

Backend API je centrální integrační bod. Klienti nekomunikují přímo s AI modelem ani s databází. Veškerý retrieval, kontrola oprávnění, audit a model routing probíhá na backendu.

---

## 6. Modulární struktura aplikace

Předpokládaná struktura backend repository:

```text
app/
  api/
    routes/
      chat.py
      search.py
      feedback.py
      documents.py
      health.py
    dependencies.py

  core/
    config.py
    auth.py
    logging.py
    telemetry.py
    errors.py

  agents/
    graph.py
    flash_agent.py
    thinking_agent.py
    prompts.py
    state.py

  retrieval/
    base.py
    hybrid.py
    vector.py
    keyword.py
    fusion.py
    reranker.py
    freshness.py
    context_packing.py

  ingestion/
    pipeline.py
    loaders/
      blob.py
      local.py
      sharepoint.py
    extraction.py
    chunking.py
    embedding.py
    metadata.py

  knowledge/
    glossary.py
    abbreviations.py
    taxonomy.py
    source_rules.py

  providers/
    llm.py
    embeddings.py
    azure_foundry.py
    search.py

  storage/
    db.py
    documents_repo.py
    chunks_repo.py
    audit_repo.py
    feedback_repo.py

  schemas/
    chat.py
    search.py
    documents.py
    feedback.py

  workers/
    ingest_worker.py
```

Hlavní principy:

- API vrstva nesmí obsahovat business logiku retrievalu.
- Agent orchestration nesmí přímo sahat do databáze mimo definovaná retrieval/storage rozhraní.
- Search backend musí být vyměnitelný přes provider interface.
- LLM provider musí být vyměnitelný přes provider interface.
- Ingestion pipeline musí být oddělená od runtime chat/search API.

---

## 7. Datový model

### 7.1 Dokument

Tabulka `documents` bude držet dokument jako logický zdroj.

Příklad polí:

```text
document_id UUID primary key
source_type TEXT
source_uri TEXT
title TEXT
document_type TEXT
language TEXT
owner TEXT
created_at TIMESTAMP
updated_at TIMESTAMP
valid_from DATE
valid_to DATE NULL
version TEXT NULL
checksum TEXT
freshness_status TEXT
security_acl JSONB
ingested_at TIMESTAMP
metadata JSONB
```

### 7.2 Chunk

Tabulka `chunks` bude držet textové části dokumentů a jejich metadata.

Příklad polí:

```text
chunk_id UUID primary key
document_id UUID references documents(document_id)
chunk_index INT
content TEXT
content_hash TEXT
embedding VECTOR
language TEXT
section_title TEXT NULL
page_number INT NULL
created_at TIMESTAMP
updated_at TIMESTAMP
valid_from DATE NULL
valid_to DATE NULL
freshness_status TEXT
security_acl JSONB
metadata JSONB
```

### 7.3 Knowledge base

Tabulka `knowledge_entries` bude držet řízené znalosti použitelné před retrieval nebo během agentního workflow.

Příklad polí:

```text
entry_id UUID primary key
entry_type TEXT -- abbreviation, synonym, glossary, taxonomy, rule
key TEXT
value JSONB
language TEXT
priority INT
valid_from DATE NULL
valid_to DATE NULL
created_at TIMESTAMP
updated_at TIMESTAMP
```

### 7.4 Audit

Tabulka `query_audit_log` bude držet audit vyhledávání a odpovědí.

Příklad polí:

```text
audit_id UUID primary key
user_id TEXT
session_id UUID
query TEXT
mode TEXT
retrieval_strategy TEXT
model_profile TEXT
used_document_ids JSONB
used_chunk_ids JSONB
latency_ms INT
token_usage JSONB
created_at TIMESTAMP
```

### 7.5 Feedback

Tabulka `feedback` bude ukládat zpětnou vazbu uživatelů.

Příklad polí:

```text
feedback_id UUID primary key
session_id UUID
audit_id UUID
user_id TEXT
rating TEXT -- helpful, not_helpful, incorrect, unsafe, stale_source
comment TEXT NULL
created_at TIMESTAMP
```

---

## 8. Retrieval pipeline

Retrieval pipeline bude postavená jako hybridní proces.

```text
User query
  -> normalize query
  -> detect language
  -> enrich query using knowledge base
  -> extract metadata constraints
  -> run vector search
  -> run full-text search
  -> apply ACL filters
  -> apply metadata filters
  -> merge results
  -> rank fusion
  -> validate freshness
  -> optional reranking
  -> context packing
  -> send evidence to LLM
```

### 8.1 Query enrichment

Před vyhledáváním se dotaz obohatí o řízené znalosti z knowledge base.

Příklad:

```text
Dotaz: "Jak se ABC řeší v QBR?"
```

Knowledge base může obsahovat:

```json
{
  "ABC": ["Account Based Collaboration", "Azure Billing Center"],
  "QBR": ["Quarterly Business Review"]
}
```

Výsledkem query enrichment kroku může být více variant dotazu:

```text
ABC QBR
Account Based Collaboration Quarterly Business Review
Azure Billing Center Quarterly Business Review
```

Tento krok musí být auditovatelný. U každé odpovědi musí být možné dohledat, jaké zkratky nebo aliasy byly použity.

### 8.2 Vector search

Vector search poběží nad embeddingy uloženými v PostgreSQL pomocí pgvector. Dotaz se převede na embedding a následně se vyhledají nejbližší chunky podle zvolené similarity metriky.

Vector search musí podporovat metadata filtry, například:

- jazyk,
- typ dokumentu,
- oddělení,
- datum platnosti,
- zdroj,
- bezpečnostní oprávnění,
- stav aktuálnosti.

### 8.3 Full-text search

Full-text search bude v MVP implementovaný pomocí PostgreSQL full-text search.

Tato vrstva pokrývá případy, kde je přesná shoda termínů důležitější než sémantická podobnost, například:

- interní zkratky,
- názvy projektů,
- čísla dokumentů,
- specifické technické termíny,
- názvy zákazníků,
- kódy a identifikátory.

### 8.4 Hybrid ranking

Výsledky z vector search a full-text search se spojí v aplikační vrstvě. MVP použije jednoduchý rank fusion mechanismus, například weighted score fusion nebo reciprocal rank fusion.

Příklad interního skóre:

```text
final_score = vector_weight * vector_score
            + keyword_weight * keyword_score
            + freshness_weight * freshness_score
            + source_priority_weight * source_priority_score
```

Váhy budou konfigurovatelné podle typu dotazu a režimu agenta.

### 8.5 Freshness validation

Před předáním chunků do LLM se ověří aktuálnost dokumentu a chunku.

Kontrolované signály:

- `freshness_status`,
- `valid_from`,
- `valid_to`,
- `updated_at`,
- `version`,
- existence novější verze stejného dokumentu,
- source priority rules.

Chunky označené jako `archived`, `stale` nebo mimo platnost se standardně nepoužijí jako primární evidence. Mohou být použité pouze v případě, že dotaz explicitně míří na historický stav nebo pokud neexistuje aktuálnější zdroj. V takovém případě musí být tato skutečnost viditelná v odpovědi.

### 8.6 Context packing

Do LLM se neposílají syrové výsledky search engine. Před odesláním se vytvoří evidence balíček obsahující:

- obsah chunku,
- název dokumentu,
- identifikátor dokumentu,
- datum poslední aktualizace,
- stav aktuálnosti,
- verzi dokumentu,
- sekci nebo stránku,
- skóre relevance,
- metadata potřebná pro citace.

LLM má odpovídat pouze na základě dodané evidence, pokud systémový prompt nebo režim agenta neurčuje jinak.

---

## 9. Agent modes

Aplikace bude podporovat dva hlavní režimy agenta.

### 9.1 Flash mode

Flash mode je určený pro rychlé odpovědi s nižší latencí a nižší cenou.

Typický flow:

```text
query
  -> query enrichment
  -> hybrid retrieval
  -> freshness validation
  -> context packing
  -> fast model response
```

Použití:

- jednoduché otázky,
- rychlé dohledání faktů,
- navigace ke zdroji,
- krátké shrnutí jednoho nebo několika dokumentů.

### 9.2 Thinking mode

Thinking mode je určený pro složitější dotazy, kde je potřeba vícekrokové vyhledávání nebo reasoning nad více zdroji.

Typický flow:

```text
query
  -> classify intent
  -> build retrieval plan
  -> run first retrieval
  -> inspect evidence
  -> optionally run follow-up retrieval
  -> detect conflicts or missing evidence
  -> validate freshness and source priority
  -> synthesize answer
```

Použití:

- porovnání více dokumentů,
- odpovědi nad konfliktními zdroji,
- komplexní firemní policy otázky,
- dotazy s nejasnými zkratkami,
- otázky, kde je nutné rozlišit aktuální a historické informace.

### 9.3 Model profiles

Model nebude hardcodovaný v agentovi. Každý režim použije model profile.

Příklad konfigurace:

```json
{
  "flash": {
    "chat_model": "fast-model-deployment",
    "temperature": 0.1,
    "max_tokens": 1200
  },
  "thinking": {
    "chat_model": "reasoning-model-deployment",
    "temperature": 0.0,
    "max_tokens": 3000
  },
  "embedding": {
    "model": "embedding-model-deployment",
    "dimensions": 1536
  }
}
```

---

## 10. Ingestion pipeline

Ingestion pipeline je samostatná část systému. Jejím výstupem jsou dokumenty, chunky, embeddings a metadata uložená v PostgreSQL a Blob Storage.

```text
source document
  -> fetch/load
  -> store original in Blob Storage
  -> extract text
  -> normalize content
  -> detect language
  -> split into chunks
  -> enrich metadata
  -> generate embeddings
  -> store document and chunks
  -> index full-text fields
  -> run quality checks
```

### 10.1 Source loaders

První verze bude podporovat minimálně ruční nebo technický upload dokumentů do Blob Storage. Následně se doplní další loadery podle priorit.

Možné zdroje:

- Blob Storage,
- lokální upload přes admin UI,
- SharePoint,
- OneDrive,
- Confluence nebo jiná wiki,
- databázové exporty,
- statické knowledge base soubory.

### 10.2 Text extraction

Text extraction bude záviset na typu dokumentu.

Podporované typy v první fázi:

- `.txt`,
- `.md`,
- `.pdf`,
- `.docx`,
- `.html`,
- `.json`.

PDF a Office dokumenty mohou vyžadovat specializovanou extrakci, aby se správně zpracovaly nadpisy, odstavce, tabulky a stránky.

### 10.3 Chunking

Chunking nebude jednotný pro všechny dokumenty. Strategie bude záviset na typu zdroje.

Příklady:

| Typ dokumentu | Strategie chunkingu |
|---|---|
| FAQ / KB článek | podle otázek a sekcí |
| policy dokument | podle nadpisů a odstavců |
| technická dokumentace | podle headings, odstavců a code blocků |
| prezentace | slide-level chunking + speaker notes |
| tabulky | row-aware nebo section-aware chunking |
| email thread | po zprávách a logických blocích |

Každý chunk musí obsahovat dostatek metadat, aby bylo možné dohledat původní zdroj, stránku, sekci a verzi.

### 10.4 Reindexing

Ingestion pipeline musí podporovat:

- první indexaci dokumentu,
- reindex při změně dokumentu,
- označení starých verzí jako `stale` nebo `archived`,
- odstranění dokumentu a jeho chunků,
- přepočítání embeddingů při změně embedding modelu.

Embedding model version musí být uložená v metadatech, aby bylo možné bezpečně provést reindex při změně modelu nebo dimenze embeddingu.

---

## 11. Security model

Bezpečnostní model je součástí návrhu od první verze.

### 11.1 Autentizace

Uživatelé budou přihlašovaní přes Microsoft Entra ID. Backend bude pracovat s identitou uživatele a jeho skupinami nebo rolemi.

### 11.2 Autorizace dokumentů

Každý dokument a chunk bude mít metadata s informací o oprávnění.

Retrieval pipeline musí aplikovat ACL filtr před tím, než se chunk dostane do context packingu nebo LLM.

Základní pravidlo:

```text
LLM nesmí obdržet obsah, který uživatel nemá právo vidět.
```

Toto pravidlo platí i pro thinking mode a vícekrokové retrieval workflow.

### 11.3 Secrets

Secrets, connection stringy a API klíče budou uložené v Azure Key Vault. Aplikace bude používat managed identity všude, kde to Azure služby umožňují.

### 11.4 Audit

Systém bude logovat:

- uživatele,
- čas dotazu,
- dotaz,
- režim agenta,
- retrieval strategii,
- použité dokumenty a chunky,
- model profile,
- token usage,
- latency,
- feedback.

Audit nesmí ukládat citlivá data nad nezbytnou míru. Pro některé části odpovědi nebo promptu může být vhodné ukládat hash nebo redigovaný záznam.

---

## 12. API návrh

### 12.1 Chat endpoint

```http
POST /api/chat
```

Request:

```json
{
  "query": "Jak řešíme zkratku ABC v QBR dokumentech?",
  "mode": "thinking",
  "filters": {
    "language": "cs",
    "document_type": "policy"
  },
  "include_sources": true
}
```

Response:

```json
{
  "answer": "...",
  "sources": [
    {
      "document_id": "...",
      "chunk_id": "...",
      "title": "QBR Process",
      "section_title": "Terminology",
      "updated_at": "2026-03-12T10:00:00Z",
      "freshness_status": "current",
      "score": 0.87
    }
  ],
  "metadata": {
    "mode": "thinking",
    "retrieval_strategy": "hybrid_rrf",
    "model_profile": "thinking",
    "latency_ms": 2450
  }
}
```

### 12.2 Search endpoint

```http
POST /api/search
```

Endpoint vrací evidence bez generované AI odpovědi. Používá se pro debugging, admin obrazovky, evaluaci a případné klasické search UI.

### 12.3 Feedback endpoint

```http
POST /api/feedback
```

Request:

```json
{
  "audit_id": "...",
  "rating": "not_helpful",
  "comment": "Odpověď použila starý dokument."
}
```

### 12.4 Admin endpoints

```http
GET  /api/admin/documents
GET  /api/admin/documents/{document_id}
POST /api/admin/documents/ingest
POST /api/admin/documents/reindex
POST /api/admin/knowledge
GET  /api/admin/knowledge
```

Admin endpoints budou chráněné role-based autorizací.

---

## 13. Azure resources

### 13.1 MVP resources

| Resource | Účel |
|---|---|
| Azure AI Foundry project | model deployments, embeddings, AI governance |
| Azure Database for PostgreSQL Flexible Server | dokumenty, chunky, embeddings, metadata, audit |
| pgvector extension | vector similarity search |
| Azure Blob Storage | originální dokumenty a ingestion artefakty |
| Azure Container Apps | backend API a ingestion worker |
| Azure Container Registry | Docker images |
| Azure Key Vault | secrets a konfigurace |
| Microsoft Entra ID | autentizace a autorizace |
| Azure Monitor | metriky a logy |
| Application Insights | aplikační tracing a performance monitoring |

### 13.2 Pozdější resources

| Resource | Důvod přidání |
|---|---|
| Azure Cache for Redis | cache odpovědí, sessions, rate limiting |
| Azure Service Bus | robustní asynchronní ingestion a reindexing |
| Azure API Management | správa veřejnějšího nebo multi-client API |
| Private Endpoints | produkční síťová izolace |
| Azure Bot Service | Teams integrace |
| Azure AI Search | specializovaný enterprise search backend, pokud PostgreSQL vrstva nebude stačit |

---

## 14. Deployment model

První verze bude nasazená jako kontejnerizovaná aplikace.

```text
Git repository
  -> CI pipeline
  -> Docker build
  -> push to Azure Container Registry
  -> deploy to Azure Container Apps
```

Backend API a ingestion worker budou oddělené procesy nebo oddělené Container Apps.

```text
Container App: ai-search-api
Container App / Job: ai-search-ingestion-worker
PostgreSQL: ai-search-db
Blob Storage: ai-search-storage
Key Vault: ai-search-kv
```

Konfigurace bude řešená přes environment variables, Key Vault references a managed identity.

---

## 15. Observability a evaluace

### 15.1 Runtime observability

Sledované metriky:

- API latency,
- retrieval latency,
- LLM latency,
- počet dotazů,
- error rate,
- token usage,
- cena podle model profile,
- počet nalezených chunků,
- počet odpovědí bez zdrojů,
- počet odpovědí se stale zdrojem,
- feedback ratio.

### 15.2 Retrieval evaluace

Pro ladění relevance bude vytvořen eval dataset.

Každý eval případ bude obsahovat:

```text
question
expected_document_ids
expected_answer_notes
language
query_type
```

Měřené metriky:

- recall@k,
- precision@k,
- MRR,
- source freshness accuracy,
- answer groundedness,
- user feedback.

### 15.3 Prompt a agent evaluace

Prompt změny a změny retrieval strategie musí být testované proti eval datasetu. Cílem je zabránit regresím při úpravách agentního workflow.

---

## 16. MVP scope

### 16.1 Součást MVP

MVP bude obsahovat:

- webové UI pro chat/search,
- FastAPI backend,
- Entra ID autentizaci,
- ingestion pipeline pro základní dokumenty,
- ukládání originálních dokumentů do Blob Storage,
- PostgreSQL datový model,
- pgvector vector search,
- PostgreSQL full-text search,
- hybrid retrieval,
- knowledge base pro zkratky a aliasy,
- flash mode,
- thinking mode,
- citace zdrojů,
- freshness validation,
- základní audit log,
- user feedback,
- základní monitoring.

### 16.2 Mimo MVP

Mimo MVP zůstává:

- Teams klient,
- Outlook add-in,
- Azure AI Search backend,
- Qdrant backend,
- Databricks integrace,
- pokročilý admin portál,
- multi-tenant režim,
- fine-tuning modelů,
- autonomní akce typu vytváření ticketů nebo odesílání emailů,
- plnohodnotná data governance platforma.

---

## 17. Roadmap

### Phase 0: Technical spike

Cíl: ověřit technickou proveditelnost základního RAG flow.

Výstupy:

- FastAPI skeleton,
- PostgreSQL Flexible Server s pgvector,
- jednoduchá tabulka dokumentů a chunků,
- embedding jednoho dokumentu,
- vector query,
- jednoduchá odpověď přes Azure AI model,
- lokální nebo jednoduché web UI.

### Phase 1: Ingestion and retrieval

Cíl: vytvořit stabilní ingestion pipeline a hybrid search.

Výstupy:

- Blob Storage integration,
- document extraction,
- chunking,
- embeddings,
- full-text search,
- hybrid ranking,
- metadata filtering,
- základní eval dataset.

### Phase 2: Agent and productization

Cíl: vytvořit použitelnou aplikaci pro interní pilot.

Výstupy:

- flash agent,
- thinking agent,
- source citations,
- freshness validation,
- feedback,
- audit,
- základní frontend,
- Entra ID auth.

### Phase 3: Enterprise hardening

Cíl: připravit systém na širší nasazení.

Výstupy:

- ACL filtering,
- production monitoring,
- rate limiting,
- cost tracking,
- ingestion worker scaling,
- reindexing strategy,
- admin endpoints,
- security review.

### Phase 4: Channel expansion

Cíl: rozšířit aplikaci mimo web.

Výstupy:

- Teams interface,
- Outlook interface,
- API pro další interní systémy,
- případné rozšíření search backendu podle výsledků pilotu.

---

## 18. Otevřené otázky

Před implementací nebo během technického spike je nutné dořešit:

1. Jaké budou první zdroje dokumentů?
2. Jaký bude očekávaný objem dokumentů a chunků v MVP a v produkci?
3. Jak se bude mapovat oprávnění ze zdrojových systémů do ACL metadat?
4. Jaké typy dokumentů musí být podporované v první verzi?
5. Jaký je cílový latency budget pro flash a thinking mode?
6. Jaké modely budou použité pro flash, thinking a embeddings?
7. Jak se bude řešit vícejazyčnost, hlavně čeština a angličtina?
8. Jaká bude strategie pro staré, archivované nebo konfliktní dokumenty?
9. Jak se bude hodnotit kvalita odpovědí?
10. Kdo bude spravovat knowledge base zkratky, aliasy a glossary?
11. Jaké auditní informace je možné bezpečně ukládat?
12. Jaké prostředí bude cílové pro první pilot?

---

## 19. Hlavní rizika

| Riziko | Dopad | Mitigace |
|---|---|---|
| Nekvalitní chunking | nízká relevance odpovědí | typově specifický chunking a eval dataset |
| PostgreSQL full-text search nebude stačit | horší keyword relevance | provider rozhraní pro budoucí Qdrant, Azure AI Search nebo OpenSearch |
| Stale dokumenty v odpovědích | ztráta důvěry v systém | freshness metadata a validace před LLM |
| Chybné ACL filtrování | bezpečnostní incident | ACL jako součást retrieval pipeline od první verze |
| Příliš vysoká latency thinking mode | horší UX | flash jako default, thinking pro složitější dotazy |
| Rostoucí náklady na LLM | drahý provoz | model routing, caching, token budget, monitoring |
| Vendor lock-in v aplikační logice | horší přenositelnost | vlastní provider abstrakce |
| Chybějící evaluace | nelze měřit zlepšení/regrese | eval dataset a pravidelné testy retrievalu |

---

## 20. Shrnutí architektury

První verze aplikace bude postavená na Python/FastAPI backendu, Next.js frontendu, Azure AI Foundry modelech, PostgreSQL Flexible Serveru s pgvector, Azure Blob Storage a Azure Container Apps.

PostgreSQL bude sloužit jako hlavní knowledge store i jako první search backend. pgvector pokryje vektorové vyhledávání, PostgreSQL full-text search pokryje textové dotazy a aplikační hybrid retrieval vrstva spojí výsledky s metadaty, ACL a freshness validací.

LangChain a LangGraph budou použité pro AI orchestration, ale aplikační architektura bude stát na vlastních provider rozhraních. Díky tomu půjde v budoucnu měnit modely, embedding provider, search backend nebo klientské rozhraní bez zásadního přepisu celé aplikace.

MVP se soustředí na ověření kvality hybridního vyhledávání, práci s metadaty, citace zdrojů, kontrolu aktuálnosti a dva agentní režimy. Teams, Outlook a specializované search backendy zůstávají pro další fáze projektu.

