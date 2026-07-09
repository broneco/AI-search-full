# AI Search Full-Stack Application

Tato aplikace představuje podnikovou AI vyhledávací platformu (RAG) běžící na **Python / FastAPI** backendu, **Next.js / React / TypeScript** frontendu, **Azure Database for PostgreSQL (s pgvector)** a modelech **Azure OpenAI / AI Foundry**. Umožňuje plně zabezpečené, sémantické vyhledávání nad firemními dokumenty (včetně českých diakritických znaků) se zobrazením přesných citací a čísel stránek.

---

## 🚀 Jak aplikaci spustit a otestovat

### 1. Příprava prostředí a konfigurace
Ujistěte se, že máte v kořenovém adresáři vytvořen a správně vyplněn soubor `.env` (můžete se inspirovat v `.env.example`). Virtuální prostředí pro backend se nachází ve složce `.venv`.

Pro aktivaci cloudu (Azure Blob Storage) přidejte do souboru `.env` následující klíče:
```env
AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;"
AZURE_BLOB_CONTAINER_ORIGINALS="originals"
```
*(Pokud tyto proměnné chybí, aplikace automaticky přepne do lokálního sandbox režimu a bude číst/ukládat PDF soubory z lokální složky `data/`).*

---

### 2. Import dokumentů (Ingest)
Pro nahrání souborů z adresáře `data/` do databáze v Azure a případné nahrání na Azure Blob Storage máte k dispozici dva skripty:

* **Přírůstkový import (Incremental Ingest):** Nahraje pouze nově přidané nebo změněné soubory (kontroluje se SHA-256 checksum).
  ```powershell
  .venv\Scripts\python.exe ingest.py
  ```

* **Úplný import (Full Refresh Ingest):** Nejdříve vymaže všechny tabulky v databázi a provede kompletní import všech souborů znovu od nuly.
  ```powershell
  .venv\Scripts\python.exe full_refresh_ingest.py
  ```

*Během importu se v terminálu zobrazují podrobné, přehledné vizuální kroky jednotlivých fází (parsování PDF, dělení na fragmenty, generování embeddingů, nahrávání na Azure Blob Storage, zápis do PostgreSQL).*

---

### 3. Spuštění lokálního webového API serveru (Backend)
Pro spuštění backendové API služby:
```powershell
.venv\Scripts\uvicorn app.main:app --port 8000 --reload
```
* **Swagger interaktivní dokumentace:** 👉 **[http://localhost:8000/docs](http://localhost:8000/docs)**
* **Důležité endpointy:**
  * `POST /api/chat` — RAG vyhledávací endpoint (sémantické/hybridní)
  * `GET /api/documents/list` — Výpis přístupných souborů s počtem pasáží
  * `GET /api/documents/view/{document_id}` — Endpoint pro inline streamování PDF z Azure Blob / lokálního disku

---

### 4. Spuštění klientského dashboardu (Frontend)
Klientská Next.js aplikace se nachází ve složce `frontend/`. 

Pro její spuštění v režimu vývoje:
1. Přejděte do složky:
   ```powershell
   cd frontend
   ```
2. Nainstalujte balíčky a spusťte server:
   ```powershell
   npm install
   npm run dev
   ```
3. Otevřete prohlížeč na adrese:
   👉 **[http://localhost:3000](http://localhost:3000)**

---

### 5. Automatizované nasazení backendu do Azure (Cloud Deployment)
Pro rychlé sestavení a nasazení změn v kódu backendu do Azure Container Apps slouží automatizovaný PowerShell skript `deploy_backend.ps1`. Skript využívá cloudový build (`az acr build`), takže **nemusíte mít na počítači spuštěný lokální Docker**.

* **Standardní nasazení (s výchozími hodnotami):**
  Spusťte PowerShell s dočasným povolením spouštění lokálních skriptů:
  ```powershell
  powershell -ExecutionPolicy Bypass -File .\deploy_backend.ps1
  ```
  *(Skript automaticky zkontroluje vaše přihlášení do Azure CLI, sestaví image v cloudu s unikátním časovým razítkem, provede rolling update Container App `dolphin-ai-search-backend` a aktualizuje CORS pravidla).*

* **Konfigurace a změna parametrů:**
  Výchozí hodnoty (Resource Group, Registry Name, Container App Name, Region) jsou definovány na začátku skriptu v sekci `param(...)` a můžete je tam trvale přepsat.
  Případně je můžete jednorázově přepsat přímo z příkazové řádky:
  ```powershell
  powershell -ExecutionPolicy Bypass -File .\deploy_backend.ps1 -ResourceGroup "Můj_RG" -ContainerAppName "moje-container-app"
  ```

---

## 🧪 Jak dashboard testovat a ověřovat funkčnost

Po otevření adresy `http://localhost:3000` můžete testovat následující scénáře:

### Scénář A: Testování přístupových práv (Security ACL)
1. **Změna role:** V záhlaví stránky přepněte dropdown **Uživatel** na **Standard User**. V seznamu souborů na levé straně automaticky zmizí citlivé směrnice o rozpočtu a pracovní době.
2. **Blokování vyhledávání:** Vyhledejte *"registr smluv"*. Platforma odmítne zobrazit výsledky a vrátí bezpečnostní hlášku: *"I'm sorry, I could not find any relevant information..."*.
3. **Povýšení práv:** Přepněte dropdown **Uživatel** na **Personální (HR Specialist)** nebo **Finanční (Finance Auditor)**. Vyhledejte *"registr smluv"* znovu. Výsledky se úspěšně vrátí a zobrazí se citované pasáže.

### Scénář B: Testování čerstvosti (Freshness Filter)
1. V panelu nad chatem přepněte filtr **Platnost (Freshness)** na **Jen 2026** nebo **Jen platné**.
2. Spusťte vyhledávání. Výsledky se dynamicky přizpůsobí zvolenému filtru (např. odfiltrují se starší archivované verze z roku 2024).

### Scénář C: Přímé odkazy a skroling na konkrétní stranu PDF
1. Klikněte na libovolnou citaci v pravém Citacím panelu (např. kliknutím na odkaz dokumentu).
2. Prohlížeč otevře zdrojový PDF soubor v nové záložce (nativně streamovaný z Azure Blob Storage) a **automaticky odskroluje přímo na stranu, ze které citovaná pasáž pochází** (např. `#page=4`).

---

## 📁 Architektura projektu

* **`app/`** — Zdrojový kód backendu
  * **`api/`** — HTTP endpointy a routy (healthcheck, chat, documents)
  * **`core/`** — Konfigurace a nastavení (`config.py` načítající `.env`)
  * **`ingestion/`** — Zpracování dokumentů (parsování PDF, text chunking, orchestrátor)
  * **`providers/`** — Integrace na Azure OpenAI (LLM, embeddings) a Azure Blob Storage
  * **`retrieval/`** — Hybridní vyhledávání (FTS + Vector pgvector) s aplikací ACL a Freshness filtrů
  * **`storage/`** — Databázové modely (SQLAlchemy) a inicializace schématu
* **`frontend/`** — Next.js / React / TypeScript single-page dashboard aplikace
* **`data/`** — Složka s lokálními PDF dokumenty pro lokální sandbox režim
* **`tests/`** — Automatická testovací sada (pytest)
