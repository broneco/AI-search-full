# AI Search Full-Stack Application

Tato aplikace představuje podnikovou AI vyhledávací platformu (RAG) běžící na **Python / FastAPI**, **Azure Database for PostgreSQL (s pgvector)** a modelech **Azure OpenAI / AI Foundry**. Umožňuje plně zabezpečené, sémantické vyhledávání nad firemními dokumenty (včetně českých diakritických znaků) se zobrazením přesných citací a čísel stránek.

---

## 🚀 Jak aplikaci spustit a otestovat

### 1. Příprava prostředí a konfigurace
Ujistěte se, že máte v kořenovém adresáři vytvořen a správně vyplněn soubor `.env` (můžete se inspirovat v `.env.example`). Virtuální prostředí se nachází ve složce `.venv`.

### 2. Import dokumentů (Ingest)
Pro nahrání souborů z adresáře `data/` do databáze v Azure máte k dispozici dva skripty:

* **Přírůstkový import (Incremental Ingest):** Nahraje pouze nově přidané nebo změněné soubory (kontroluje se SHA-256 checksum).
  ```powershell
  .venv\Scripts\python.exe ingest.py
  ```

* **Úplný import (Full Refresh Ingest):** Nejdříve vymaže všechny tabulky v databázi a provede kompletní import všech souborů znovu od nuly.
  ```powershell
  .venv\Scripts\python.exe full_refresh_ingest.py
  ```

*Během importu se v terminálu zobrazují podrobné, přehledné vizuální kroky jednotlivých fází (parsování PDF, dělení na fragmenty, generování embeddingů, zápis do PostgreSQL).*

### 3. Rychlé testování dotazů v terminálu (`ask.py`)
Můžete klást sémantické dotazy přímo z příkazové řádky bez nutnosti spouštět webový server nebo otevírat prohlížeč:

* **S parametrem:**
  ```powershell
  .venv\Scripts\python.exe ask.py "Jaká jsou pravidla pro registr smluv?"
  ```
* **Interaktivně:**
  ```powershell
  .venv\Scripts\python.exe ask.py
  ```
  *(Program se vás sám zeptá na dotaz, vyhledá relevantní fragmenty v Azure PostgreSQL, odešle kontext do modelu GPT-5.4-mini a vypíše uzemněnou odpověď s přesnými citacemi).*

### 4. Spuštění lokálního webového API serveru
Pokud chcete spustit backendové API rozhraní:
```powershell
.venv\Scripts\uvicorn app.main:app --reload
```
Po spuštění je k dispozici interaktivní Swagger dokumentace na adrese:
👉 **[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)**

Zde můžete přímo přes webové formuláře testovat endpointy:
* `POST /api/chat` — Pro pokládání sémantických dotazů (RAG)
* `POST /api/documents/ingest` — Pro nahrání nového textového fragmentu

### 5. Spuštění automatických testů
Pro ověření integrity celého systému a spojení s Azure službami můžete spustit unit a integrační testy pomocí `pytest`:
```powershell
.venv\Scripts\pytest
```

---

## 📁 Architektura projektu

* **`app/`** — Zdrojový kód aplikace
  * **`api/`** — HTTP endpointy a routy (healthcheck, chat)
  * **`core/`** — Konfigurace a nastavení (`config.py` načítající `.env`)
  * **`ingestion/`** — Zpracování dokumentů (parsování PDF, text chunking, orchestrátor)
  * **`providers/`** — Integrace na Azure OpenAI (LLM, embeddings generátory)
  * **`retrieval/`** — Sémantické vyhledávání nad pgvector s aplikací filtrů a ACL
  * **`storage/`** — Databázové modely (SQLAlchemy) a inicializace schématu
* **`data/`** — Složka s lokálními PDF dokumenty určenými pro vyhledávání
* **`tests/`** — Automatická testovací sada (pytest)
