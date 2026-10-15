# AI Search Full-Stack Application

Tato aplikace představuje podnikovou AI vyhledávací platformu (RAG) běžící na **Python / FastAPI** backendu, dvoudílném **Next.js / React / TypeScript** frontendu (`frontend-user` a `frontend-admin`), **Azure SQL Database** a modelech **Azure OpenAI / AI Foundry**. Umožňuje zabezpečené, sémantické vyhledávání nad firemními dokumenty (včetně českých diakritických znaků) se zobrazením přesných citací a čísel stránek.

---

## Lokální vývoj ve VS Code

Pro spuštění lokální SQL databáze, backendu a uživatelského frontendu použij **Terminal → Run Task… → AI Search: start local app**. První spuštění vyžaduje Docker Desktop, Python závislosti v `.venv` a `npm install` ve složce `frontend-user`. Podrobný postup, izolované testy a zachování lokálních dat popisuje [návod pro lokální vývoj](docs/development/local-setup.md).

Vyhledávání a dokumentové náhledy nyní vyžadují bearer token a používají serverové skupiny; veřejná registrace nepřiděluje Management. [Ověření slice 2](docs/development/search-slice-2-testing.md) popisuje lokální testy a ruční akceptaci; před Azure nasazením je nutná migrace podle odkazovaného handoffu.

[Ověření slice 4](docs/development/search-slice-4-testing.md) popisuje explicitní exact/ANN režimy, lokální kontraktové testy a diagnostiku. Výchozí režim zůstává exact; nativní Azure exact/DiskANN integrace a recall/latence čekají na slice 5. Současný Docker je stále SQL Server 2022 s přesnou JSON referencí.

[Benchmark slice 5](docs/development/search-slice-5-testing.md) odděluje přípravu query cache od read-only měření retrievalu, počítá recall/p95 a připraví report s branami pro lidskou aktivaci. Přiložený dataset osmi českých otázek slouží lokálnímu smoke; skutečné Azure integrační a výkonové brány zůstávají otevřené. Výsledky/cache patří do ignorované `.local/benchmarks/`.

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

## 🏛️ Konfigurace Tenantů (Víceklientové prostředí)

Aplikace podporuje rychlé přepínání tenantů pro více firem a institucí:
- **`dolphin`**: Dolphin Consulting (Podnikový vyhledávač znalostí s přesnými citacemi)
- **`alzbeta`**: Nemocnice sv. Alžběty (Vyhledávání v lékařských směrnicích a SOP)
- **`jhu`**: Jihočeská Univerzita v Českých Budějovicích (Vyhledávání ve studijních řádech a předpisech JČU) — ***Výchozí tenant pro lokální experimenty!***

### ⚙️ Kde nastavit tenant pro lokální spuštění:

1. **Backend (`TENANT_ID`)**: V souboru **`.env`** (nebo `.env.dev`) nastavte proměnnou `TENANT_ID`:
   ```env
   TENANT_ID=jhu-dev
   ```
   *(Dostupné hodnoty: `jhu-dev`, `dolphin-dev`, `alzbeta-dev`)*

2. **Frontend (`NEXT_PUBLIC_CLIENT_THEME`)**: V prostředí nebo `.env` pro frontend můžete nastavit vizuální téma:
   ```env
   NEXT_PUBLIC_CLIENT_THEME=jhu
   ```
   *(Kód aplikací `frontend-user` i `frontend-admin` má výchozí vizuální téma nastaveno na **`jhu`**)*

3. **Loga a vizuální prvky:** Všechna loga tenantů jsou přehledně umístěna ve složkách:
   - `frontend-user/public/logos/`
   - `frontend-admin/public/logos/`
   *(Obsahuje soubory `logo-JHU.webp`, `logo-dolphin-symbol.png`, `logo-nemocnice-alzbeta-2023.png`)*

4. **Složky s dokumenty tenantů:** Dokumentové podklady jsou organizovány ve složce `data - full backup/`:
   - `data - full backup/jhu/`
   - `data - full backup/dolphin/`
   - `data - full backup/alzbeta/`
   *(Tato složka i veškerý její obsah je automaticky ignorována verzovacím systémem Git skrze `.gitignore`)*

---

## 🚀 Jak aplikaci spustit lokálně

### 1. Spuštění backendu (FastAPI)
```powershell
# Výchozí DEV režim:
.venv\Scripts\uvicorn app.main:app --port 8000 --reload
```
- **Interaktivní Swagger API dokumentace**: 👉 **[http://localhost:8000/docs](http://localhost:8000/docs)**

### 2. Ingestace a obnova dokumentů (Full Refresh)
Pro kompletní re-indexaci všech souborů ze složky `data/` spusťte:
```powershell
python full_refresh_ingest.py
```
- **Co skript dělá:** Provede promazání tabulek dokumentů (`documents` a `chunks`), zkontoluje/vytvoří schémata a Full-Text katalog a znovu naindexuje všechny dokumenty ve složce `data/`.
- **Zachování uživatelských účtů:** Uživatelské účty, hesla a role (`users` tabulka) zůstávají **100% zachovány a netknuty**.
- **Auto-seeding:** Při prvním spuštění se v databázi automaticky zaloguje výchozí demo účet (`user@dolphin.cz`).

### 3. Spuštění uživatelské vyhledávací aplikace (`frontend-user`)
```powershell
cd frontend-user
npm install
npm run dev
```
Otevřete v prohlížeči na adrese: 👉 **[http://localhost:3000](http://localhost:3000)**

### 4. Spuštění administrativní konzole (`frontend-admin`)
```powershell
cd frontend-admin
npm install
npm run dev
```
Otevřete v prohlížeči na adrese: 👉 **[http://localhost:3001](http://localhost:3001)**

---

## ☁️ Automatizované nasazení do Azure

Backend release, databázové migrace a nasazení frontendů jsou oddělené kroky. Před změnami schvalte konkrétní cíl a migrační postup; JHU má aktuální [handoff](.agents/inbox/2026-10-15-jhu-search-rollout-handoff.md). Kombinovaný `deploy_all.ps1` je blokovaný.

### Backend (Azure Container Apps)
```powershell
# Pouze čtecí plán vývojového prostředí (DEV):
powershell -ExecutionPolicy Bypass -File .\deploy_backend.ps1 -Client dolphin -Environment dev

# Pouze čtecí plán produkčního prostředí (PROD):
powershell -ExecutionPolicy Bypass -File .\deploy_backend.ps1 -Client dolphin -Environment prod
```

Výchozí spuštění neprovádí build ani zápis do Azure. `-Apply` vyžaduje `-ExpectedSubscriptionId`, `-ExpectedAzureTenantId`, `-ExpectedCurrentImage`, `-MigrationConfirmed`, `-JwtMigrationConfirmed` a vyřešené blokery plánu. Aktualizuje pouze image existujícího kontejneru; nespouští ingestaci a nemění runtime konfiguraci, secrets, identitu ani kapacitu. Modely, embeddingový profil a soukromý JWT klíč musí být předem správně nastavené za běhu: tenant `.env` soubory se do image nekopírují. Odkazy na secrets je nutné funkčně ověřit a při změně JWT zároveň vyřešit přihlašovací hesla.

JWT a přechod starých hesel mají samostatný [JHU handoff](.agents/inbox/2026-10-15-jhu-jwt-password-migration-handoff.md). Nový kód může načíst podpisový klíč z existujícího Key Vaultu přes `AZURE_KEY_VAULT_SECRET_JWT_SIGNING_KEY` (volitelně připnutá `AZURE_KEY_VAULT_SECRET_JWT_SIGNING_KEY_VERSION`). Staré heslo lze zachovat s doloženým původním klíčem přes oddělený `AZURE_KEY_VAULT_SECRET_LEGACY_PASSWORD`: úspěšný login jej převede na Argon2id. Nová hesla už na JWT nezávisí. Starý image Argon2 nezná, proto musí připravený rollback image zachovat nový verifier. Žádné hodnoty secrets do repozitáře ani chatu.

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
