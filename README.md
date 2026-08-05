# AI Search Full-Stack Application

Tato aplikace představuje podnikovou AI vyhledávací platformu (RAG) běžící na **Python / FastAPI** backendu, dvoudílném **Next.js / React / TypeScript** frontendu (`frontend-user` a `frontend-admin`), **Azure Database for PostgreSQL (s pgvector)** a modelech **Azure OpenAI / AI Foundry**. Umožňuje plně zabezpečené, sémantické vyhledávání nad firemními dokumenty (včetně českých diakritických znaků) se zobrazením přesných citací a čísel stránek.

---

## 🏗️ Architektura a dvě webové aplikace

Aplikace se skládá ze dvou oddělených frontendových webových aplikací:

1. **Uživatelská vyhledávací aplikace (`frontend-user/`)**:
   - Konverzační AI vyhledávání určené pro běžné zaměstnance a uživatele.
   - **Kniha dokumentů (Document Library)**: Postranní vyhledávatelný seznam všech přístupných firemních dokumentů se štítky kategorií (`SOP`, `DPL`, `SM Z`), stavu platnosti (`PLATNÝ`/`ARCHIV`) a počtu pasáží.
   - **Interaktivní citace a PDF náhled**: Prohlížení citovaných stran přímo v integrovaném PDF panelu se žlutě zvýrazněnými pasážemi (`✨ Zvýrazněná pasáž`).
   - **Bohatý Markdown**: Automatické formátování odpovědí AI do tučných bloků (`**text**`), kurzívy a odrážkových seznamů.

2. **Administrativní konzole (`frontend-admin/`)**:
   - Webový portál určený pro administrátory a správce znalostní báze.
   - **Kategórie a Pravidla**: Nastavení pravidel automatického tagování, nahrazování verzí a archivace dokumentů.
   - **Konfigurace vyhledávání**: Živá správa vyhledávacích strategií (*Hybrid RRF, Vector, Keyword FTS*), vah a kontextového rozšiřování (*Siblings, Page, Section*).
   - **Konfigurace chunkování & Živý náhled**: Živý vizualizér rozpadu dokumentu na fragmenty (*Standard, Sémantické, Struktura, Tokenové, Agentní*).

---

## 🌐 Více prostředí (DEV vs. PROD)

Aplikace podporuje kompletní izolaci vývojového a produkčního prostředí:

- **DEV Prostředí (`APP_ENV=dev`)**: Načítá `.env.dev`, využívá databázi `dolphin_ai_search` (nebo `ai_search_dev`) a úložiště `dolphin-originals-dev`.
- **PROD Prostředí (`APP_ENV=prod`)**: Načítá `.env.prod`, využívá produkční databázi `ai_search_prod` a úložiště `dolphin-originals`.

---

## 🚀 Jak aplikaci spustit lokálně

### 1. Spuštění backendu (FastAPI)
```powershell
# Výchozí DEV režim:
.venv\Scripts\uvicorn app.main:app --port 8000 --reload
```
- **Interaktivní Swagger API dokumentace**: 👉 **[http://localhost:8000/docs](http://localhost:8000/docs)**

### 2. Spuštění uživatelské vyhledávací aplikace (`frontend-user`)
```powershell
cd frontend-user
npm install
npm run dev
```
Otevřete v prohlížeči na adrese: 👉 **[http://localhost:3000](http://localhost:3000)**

### 3. Spuštění administrativní konzole (`frontend-admin`)
```powershell
cd frontend-admin
npm install
npm run dev
```
Otevřete v prohlížeči na adrese: 👉 **[http://localhost:3001](http://localhost:3001)**

---

## ☁️ Automatizované nasazení do Azure

Pro sestavení a nasazení libovolného klienta a prostředí jsou k dispozici automatizované PowerShell skripty:

### Backend (Azure Container Apps)
```powershell
# Nasazení vývojového prostředí (DEV):
powershell -ExecutionPolicy Bypass -File .\deploy_backend.ps1 -Client dolphin -Environment dev

# Nasazení produkčního prostředí (PROD):
powershell -ExecutionPolicy Bypass -File .\deploy_backend.ps1 -Client dolphin -Environment prod
```

### Frontend (Azure Static Web Apps)
```powershell
# Nasazení uživatelské aplikace:
powershell -ExecutionPolicy Bypass -File .\deploy_frontend.ps1 -Client dolphin -Environment prod -AppType user

# Nasazení administrativní konzole:
powershell -ExecutionPolicy Bypass -File .\deploy_frontend.ps1 -Client dolphin -Environment prod -AppType admin
```

---

## 📁 Architektura složek projektu

* **`app/`** — Zdrojový kód Python/FastAPI backendu
  * **`api/`** — REST API endpointy (chat, documents, threads, config)
  * **`core/`** — Nastavení a konfigurace (`config.py` načítající `.env.dev` / `.env.prod`)
  * **`ingestion/`** — Dělení na fragmenty, embeddingy a metadata tagování
  * **`providers/`** — Integrace Azure OpenAI a Azure Blob Storage
  * **`retrieval/`** — Hybridní vyhledávání (FTS + Vector pgvector) s ACL a Freshness filtry
* **`frontend-user/`** — Next.js aplikace pro uživatelské vyhledávání
* **`frontend-admin/`** — Next.js aplikace pro administrativní konzoli
* **`docs/`** — Detailní architektura, návrhové dokumenty (design docs) a ADR záznamy
* **`tests/`** — Automatická testovací sada (pytest)
