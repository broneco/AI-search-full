# app_database_usage_info_dump

Tento dokument slouží jako **kompletní architektura a specifikace využití databáze** v projektu **AI Search Application**.
Je určen pro vývojáře, architekty i AI modely jako podklad k posouzení vhodnosti stávajícího databázového řešení (PostgreSQL) a případné úvaze o alternativních databázových či vyhledávacích platformách.

---

## 1. Přehled a role databáze v aplikaci

Aplikace využívá databázi jako **jediné primární datové úložiště** pro:
1. **RAG Knowledge Base**: Ukládání a vyhledávání textových pasáží (chunků) a jejich 1536-dimenzionálních vektorových reprezentací (vektorový search).
2. **Plnotextové vyhledávání (FTS)**: Lexikální vyhledávání nad textovým obsahem s podporou české stemmatizace.
3. **Relacionální doménové entity**: Ukládání registru dokumentů, správu uživatelských účtů, historii konverzačních vláken a zpráv.
4. **ACL & Security Enforcement**: Rychlé filtrování přístupových práv (skupin) a stavu platnosti (freshness) přímo na úrovni SQL dotazů.

Stávající databázový stroj: **Azure Database for PostgreSQL Flexible Server** (lokálně standardní PostgreSQL 15+).

---

## 2. Použité PostgreSQL rozšíření (Extensions)

| Rozšíření | Účel použití v aplikaci |
| :--- | :--- |
| **`pgvector`** | Ukládání 1536-dimenzionálních vektorových embeddingů (`Vector(1536)`) z Azure OpenAI (`text-embedding-3-large`) a výpočet kosinové vzdálenosti (`cosine_distance`). |
| **`uuid-ossp`** | Generování unikátních primárních klíčů typu UUIDv4 (`UUID(as_uuid=True)`). |

---

## 3. Kompaktní schéma databáze & Datové modely

Databáze se skládá z **5 hlavních tabulek** spravovaných přes SQLAlchemy ORM (soubor [`app/storage/models.py`](file:///c:/Users/ondrej.bronec/OneDrive%20-%20dolphinconsulting.cz/Documents/Projekty/WIP%20-%20AI%20Search%20Full/app/storage/models.py)):

```mermaid
erDiagram
    documents ||--o{ chunks : "1 : N (CASCADE)"
    users ||--o{ chat_threads : "1 : N (CASCADE)"
    chat_threads ||--o{ chat_messages : "1 : N (CASCADE)"

    documents {
        uuid document_id PK
        string tenant_id IX
        string source_type
        string source_uri
        string title
        string document_type
        string language
        string owner
        datetime created_at
        datetime updated_at
        date valid_from
        date valid_to
        string version
        string checksum
        string freshness_status
        jsonb security_acl
        datetime ingested_at
        jsonb metadata
    }

    chunks {
        uuid chunk_id PK
        string tenant_id IX
        uuid document_id FK
        int chunk_index
        text content
        string content_hash
        vector_1536 embedding
        string language
        string section_title
        int page_number
        datetime created_at
        datetime updated_at
        date valid_from
        date valid_to
        string freshness_status
        jsonb security_acl
        jsonb metadata
    }

    users {
        uuid user_id PK
        string tenant_id IX
        string email IX
        string username
        string password_hash
        string role
        jsonb groups
        datetime created_at
    }

    chat_threads {
        uuid thread_id PK
        string tenant_id IX
        uuid user_id FK
        string title
        datetime created_at
        datetime updated_at
    }

    chat_messages {
        uuid message_id PK
        string tenant_id IX
        uuid thread_id FK
        string role
        string content
        jsonb sources
        datetime created_at
    }
```

### Detailní popis tabulek:

#### A. `documents` (Registr dokumentů)
- **Primární klíč**: `document_id` (`UUID`)
- **Tenant Scope**: `tenant_id` (`VARCHAR`, indexován)
- **Metadata**: `title`, `source_uri`, `source_type` (pdf/docx), `document_type`, `version`, `checksum` (SHA-256), `freshness_status` (current/outdated/archived), `valid_from`, `valid_to`.
- **Flexibilní pole**: `security_acl` (`JSONB`, např. `{"allowed_groups": ["User", "Management"]}`) a `metadata` (`JSONB`, libovolná další klientská metadata jako oddělení, nahrazovaný dokument apod.).

#### B. `chunks` (Pasáže a vektorový index)
- **Primární klíč**: `chunk_id` (`UUID`)
- **Cizí klíč**: `document_id` -> `documents.document_id` (`ON DELETE CASCADE`)
- **Obsah**: `content` (`TEXT`), `content_hash` (MD5/SHA256).
- **Vektor**: `embedding` (`Vector(1536)` pro kosinové hledání).
- **Struktura**: `section_title`, `page_number`, `chunk_index`.
- **Zděděná metadata**: `security_acl` (`JSONB`), `freshness_status`, `valid_from`, `valid_to`, `metadata` (`JSONB`).

#### C. `users` (Uživatelé a ACL přístupy)
- **Primární klíč**: `user_id` (`UUID`)
- **Atributy**: `email` (indexován), `username`, `password_hash` (SHA-256 s salt), `role` (`User`/`Management`/`Admin`), `groups` (`JSONB` pole skupin).

#### D. `chat_threads` & `chat_messages` (Konverzační paměť)
- **Uživatel k vláknům**: `user_id` -> `users.user_id` (`ON DELETE CASCADE`).
- **Vlákno ke zprávám**: `thread_id` -> `chat_threads.thread_id` (`ON DELETE CASCADE`, řazeno podle `created_at ASC`).
- **Citace zpráv**: `sources` (`JSONB` pole použitých citací z RAG retrievalu).

---

## 4. Klíčové databázové dotazy a vyhledávací mechaniky

### A. Vektorové vyhledávání (`pgvector`)
Model používá kosinovou vzdálenost nad vektory s integrovaným SQL pre-filteringem (soubor [`app/retrieval/vector.py`](file:///c:/Users/ondrej.bronec/OneDrive%20-%20dolphinconsulting.cz/Documents/Projekty/WIP%20-%20AI%20Search%20Full/app/retrieval/vector.py)):

```sql
SELECT chunks.*, documents.*
FROM chunks
JOIN documents ON chunks.document_id = documents.document_id
WHERE documents.tenant_id IN ('alzbeta', 'alzbeta-prod')
  AND documents.security_acl->'allowed_groups' ?| ARRAY['User', 'Management']
  AND chunks.security_acl->'allowed_groups' ?| ARRAY['User', 'Management']
ORDER BY chunks.embedding <=> :query_embedding
LIMIT 50;
```

### B. Plnotextové vyhledávání (PostgreSQL FTS)
Využívá PostgreSQL `to_tsvector` a `to_tsquery` s podporou české stemmatizace (`cs` konfigurace v `pg_ts_config` s fallbackem na `simple`):

```sql
SELECT chunks.*, documents.*, ts_rank_cd(to_tsvector('cs', chunks.content), to_tsquery('cs', :q)) AS fts_rank
FROM chunks
JOIN documents ON chunks.document_id = documents.document_id
WHERE to_tsvector('cs', chunks.content) @@ to_tsquery('cs', :q)
  AND documents.tenant_id IN ('alzbeta', 'alzbeta-prod')
ORDER BY fts_rank DESC
LIMIT 50;
```

### C. GIN Index pro Plnotext
Při startu aplikace (v [`app/storage/db.py`](file:///c:/Users/ondrej.bronec/OneDrive%20-%20dolphinconsulting.cz/Documents/Projekty/WIP%20-%20AI%20Search%20Full/app/storage/db.py)) se automaticky vytváří GIN index:
```sql
CREATE INDEX IF NOT EXISTS chunks_fts_idx ON chunks USING gin(to_tsvector('cs', content));
```

### D. JSONB Pole & Operátor `?|` (Array Overlaps)
Pro bleskové vyhodnocení přístupových práv (ACL) se na úrovni databáze používá speciální PostgreSQL JSONB operátor `?|` (zda JSONB pole obsahuje alespoň jeden prvek ze zadaného SQL pole skupin).

---

## 5. Multitenancy a databázová izolace

Aplikace využívá **dvouúrovňovou multitenantní architekturu**:

1. **Fyzická izolace (Primary Boundary)**:
   - Každý klient / prostředí má **vlastní samostatnou PostgreSQL databázi**:
     - `dolphin_ai_search_dev`
     - `dolphin_ai_search_prod`
     - `alzbeta_ai_search_prod`
   - Databázový spojovací řetězec (`POSTGRES_DB`) v Azure Container Apps fyzicky odděluje data jednotlivých klientů.

2. **Logická izolace (Secondary Boundary)**:
   - Každá tabulka obsahuje sloupec `tenant_id` s B-Tree indexem (`ix_documents_tenant_id`, `ix_chunks_tenant_id`).
   - Všechny SQL dotazy obsahují pre-filter `tenant_id IN (...)` pro případ sdíleného prostředí.

---

## 6. Provozní a Výkonnostní Nároky (Operational Demands)

| Oblasti / Parametr | Současné řešení a nároky |
| :--- | :--- |
| **Dimenze vektorů** | `1536` float32 hodnot na chunk (zhruba 6 KB na 1 vektor). |
| **Velikost dat** | 100+ dokumentů per tenant, tisíce chunků. |
| **Konzistence dat (ACID)** | **Vysoká (Kritická)**. Ingestní pipeline provádí atomické operace (např. smazání starých chunků a vložení nových v rámci jedné DB transakce `db.commit()`). |
| **Latence vyhledávání** | Cílová latence retrievalu < 200 ms pro kombinovaný Hybrid Search (Vector + FTS + ACL Filter). |
| **Integrovanost (Single DB)** | PostgreSQL drží vektory, plnotextový index, relace uživatelů i historii chatu v jedné databázi bez nutnosti synchronizace mezi více službami. |

---

## 7. Shrnutí architektury pro posouzení alternativ

Současný systém spoléhá na PostgreSQL jako na **hybridní více-modelovou databázi** (Relace + Vektory + FTS + JSON Document Store). 

Případné nahrazení jinou databází by muselo vyřešit:
1. **Kde budou uložena relacionální a konverzační data** (`users`, `chat_threads`, `chat_messages`).
2. **Kde budou uloženy vektory** (vektorová databáze např. Qdrant, Azure AI Search, Pinecone, Milvus).
3. **Kde bude probíhat plnotextové vyhledávání** (Elasticsearch, Azure AI Search, Meilisearch).
4. **Jak bude zajištěno SQL ACL pre-filtrování** (`?|` operátor nad JSONB).
