# Průvodce navigací v repozitáři (`navigation_guide.md`)

Tento dokument poskytuje přehled a organizační strukturu repozitáře projektu **AI Search Full**. U každé složky i zdrojového a konfiguračního souboru je uveden výstižný jednovětý popis vysvětlující jeho účel a roli v projektu. Složka `data/` je uváděna výhradně jako kořenový adresář.

> [!IMPORTANT]
> **Pravidlo pro vývoj a AI agenty:** Tento dokument představuje kanonický katalog struktury projektu. Příslušná pravidla v `.agents/AGENTS.md` a `.agents/rules/documentation-policy.md` stanovují povinnost aktualizovat tento soubor **při každém vytvoření nového souboru nebo složky** kdekoliv v repozitáři (s výjimkou obsahu složky `data/`). Položky jsou uváděny v čistém reliktním formátu v zpětných uvozovkách bez absolutních odkazů.

---

## 1. Kořenové soubory a skripty projektu (`/`)

- 📁 `.agents/` — Hlavní složka obsahující systém instrukcí, pravidel a paměti pro vývojové AI agenty.
- 📄 `.dockerignore` — Konfigurační soubor definující ignorované soubory při sestavování Docker image.
- 📄 `.env` — Soubor lokálních proměnných prostředí a konfigurace přístupů (neverzuje se).
- 📄 `.env.dev` — Šablona konfiguračních proměnných prostředí pro vývojové prostředí DEV.
- 📄 `.env.example` — Vzorová šablona proměnných prostředí sloužící jako návod pro lokální nastavení.
- 📄 `.env.prod` — Šablona konfiguračních proměnných prostředí pro produkční prostředí PROD.
- 📁 `.github/` — Složka konfiguračních souborů a pracovních postupů pro GitHub.
- 📄 `.gitignore` — Konfigurační soubor určující, které soubory a složky má Git ignorovat.
- 📄 `AGENTS.md` — Klíčový dokument definující provozní kontrakt, pravidla a role vývojových AI agentů v repozitáři.
- 📄 `CHANGELOG.md` — Changelog projektových změn, nových funkcí a oprav chyb strukturovaný dle verzí.
- 📄 `Dockerfile` — Recept pro sestavení Docker kontejneru backendové FastAPI aplikace.
- 📄 `README.md` — Hlavní úvodní dokumentace repozitáře popisující architekturu, spuštění a nasazení.
- 📁 `ai_search_app.egg-info/` — Složka s metadaty Python balíčku vygenerovaná při instalaci.
- 📁 `app/` — Hlavní složka zdrojového kódu backendové FastAPI aplikace.
- 📄 `ask.py` — Pomocný CLI skript pro rychlé testování dotazů vůči RAG vyhledávacímu backendu.
- 📄 `check_diff.py` — Pomocný skript pro porovnání změn a kontrolu konzistence kódu.
- 📁 `data/` — Složka podkladových zdrojových PDF dokumentů určených k indexaci.
- 📄 `deploy_backend.ps1` — PowerShell skript pro automatizované nasazení backendové aplikace do Azure Container Apps.
- 📄 `deploy_frontend.ps1` — PowerShell skript pro automatizované nasazení frontendových aplikací do Azure Static Web Apps.
- 📄 `docker-compose.yml` — Podkladový PDF dokument nemocniční směrnice určený k indexaci (docker-compose.yml).
- 📁 `docs/` — Hlavní složka projektové dokumentace, architektonických rozhodnutí a návodů.
- 📁 `frontend/` — Složka s podkladovými nemocničními směrnicemi a řády (frontend).
- 📁 `frontend-admin/` — Složka zdrojového kódu administrační Next.js frontend aplikace.
- 📁 `frontend-user/` — Složka zdrojového kódu uživatelské Next.js frontend aplikace AI Vyhledávače.
- 📄 `full_refresh_ingest.py` — Podkladový PDF dokument nemocniční směrnice určený k indexaci (full_refresh_ingest.py).
- 📁 `infra/` — Složka infrastruktury jako kódu (IaC) obsahující Bicep šablony pro Azure.
- 📄 `ingest.py` — Podkladový PDF dokument nemocniční směrnice určený k indexaci (ingest.py).
- 📄 `ingest_documents.ps1` — PowerShell skript pro spuštění indexace a vektorizace dokumentů pro zadaného klienta a prostředí.
- 📄 `logo-dolphin-blue-background.jpg` — Grafické logo společnosti Dolphin Consulting s modrým pozadím.
- 📄 `logo-dolphin-symbol.png` — Grafická ikona symbolem delfína v transparentním PNG formátu.
- 📄 `logo-nemocnice-alzbeta-2023.png` — Grafické logo Nemocnice sv. Alžběty v PNG formátu pro branding.
- 📄 `pyproject.toml` — Konfigurační soubor projektu Python a nástroje pytest.
- 📄 `requirements.txt` — Seznam závislostí a knihoven Python potřebných pro chod backendové aplikace.
- 📁 `tests/` — Složka automatizovaných unit a integračních testů (pytest).

---

## 2. Agentní systém a instrukce (`.agents/`)

  - 📄 `AGENTS.md` — Hlavní provozní kontrakt a hierarchie pravidel pro AI agenty.
  - 📄 `README.md` — Úvodní popis struktury a použití složky .agents.
  - 📁 `inbox/` — Složka obsahující instrukční soubory pro manuální úkony v Azure.
    - 📄 `2026-06-08-dolphin-consulting-db-storage-handoff.md` — Handoff soubor s pokyny pro manuální nastavení Azure infrastruktury (2026-06-08-dolphin-consulting-db-storage-handoff.md).
    - 📄 `azure-openai-handoff.md` — Handoff soubor s pokyny pro manuální nastavení Azure infrastruktury (azure-openai-handoff.md).
    - 📄 `azure-postgres-handoff.md` — Handoff soubor s pokyny pro manuální nastavení Azure infrastruktury (azure-postgres-handoff.md).
    - 📄 `azure-storage-blob-setup-handoff.md` — Handoff soubor s pokyny pro manuální nastavení Azure infrastruktury (azure-storage-blob-setup-handoff.md).
  - 📁 `memory/` — Složka uchovávající dlouhodobou paměť projektu, stav a architektonické úmluvy.
    - 📄 `implementation-notes.md` — Dokumentace trvalých poznámek k implementaci a technickým řešením.
    - 📄 `open-questions.md` — Přehled otevřených architektonických a vývojových otázek.
    - 📄 `project-state.md` — Dokument zachycující aktuální stav projektu, fázi vývoje a nejbližší kroky.
    - 📄 `style-decisions.md` — Záznam rozhodnutí o kódovacím stylu a konvencích projektu.
  - 📁 `rules/` — Složka s jednotlivými pravidly a politikami pro vývoj (bezpečnost, testování, architektura).
    - 📄 `architecture-boundaries.md` — Pravidla definující architektonické hranice a zakázané závislosti.
    - 📄 `azure-deployment-handshake.md` — Pravidla pro předávání manuálních Azure úkonů lidskému operátorovi.
    - 📄 `coding-style.md` — Pravidla pro kódovací styl, typové anotace a strukturu kódové báze.
    - 📄 `documentation-policy.md` — Pravidla pro vedení a povinnou aktualizaci projektové dokumentace.
    - 📄 `iteration-policy.md` — Pravidla pro postup v malých testovatelných a reverzibilních krocích.
    - 📄 `retrieval-and-ai-policy.md` — Pravidla pro implementaci RAG vyhledávání a AI orchestrace.
    - 📄 `security-and-secrets.md` — Pravidla pro správu secrets, přístupových práv (ACL) a zabezpečení dat.
    - 📄 `testing-policy.md` — Pravidla pro psaní a spouštění automatizovaných testů.
  - 📁 `templates/` — Složka obsahující šablony pro ADR, úkoly a Azure handoff dokumenty.
    - 📄 `adr-template.md` — Šablona pro vytváření nových architektonických rozhodnutí (ADR).
    - 📄 `azure-deployment-handoff-template.md` — Šablona pro vytváření předávacích protokolů Azure úkonů.
    - 📄 `task-slice-template.md` — Šablona pro specifikaci dílčího vývojového úkolu.
  - 📁 `workflows/` — Složka obsahující postupy a pracovní návody pro opakované vývojářské činnosti.
    - 📄 `azure-manual-deploy.md` — Pracovní postup pro manuální nasazování Azure zdrojů.
    - 📄 `documentation-update.md` — Pracovní postup pro aktualizaci projektové dokumentace.
    - 📄 `implement-slice.md` — Pracovní postup pro implementaci vývojového kroku.
    - 📄 `resume-after-handoff.md` — Pracovní postup pro pokračování práce po dokončení Azure úkonu.
    - 📄 `write-adr.md` — Pracovní postup pro sepsání nového architektonického rozhodnutí.

---

## 3. GitHub CI/CD a automatizace (`.github/`)

  - 📁 `workflows/` — Složka definující automatizované GitHub Actions workflows.
    - 📄 `azure-static-web-apps-calm-sea-05badcc03.yml` — GitHub Actions workflow soubor pro automatické nasazení na Azure (azure-static-web-apps-calm-sea-05badcc03.yml).

---

## 4. Backendová aplikace Python & FastAPI (`app/`)

  - 📁 `api/` — Složka obsahující API rozhraní, routy a závislosti.
    - 📄 `dependencies.py` — Modul závislostí FastAPI (získání databázových relací, ověření tokenů a tenantů).
    - 📁 `routes/` — Složka s definicemi jednotlivých koncových bodů (endpoints) API.
      - 📄 `auth.py` — API endpointy pro autentizaci uživatelů, přihlášení a registrace.
      - 📄 `chat.py` — API endpointy pro RAG vyhledávání, chatové dotazy a generování odpovídajících citací.
      - 📄 `documents.py` — API endpointy pro správu, nahrávání a mazání dokumentů.
      - 📄 `health.py` — API endpointy pro kontrolu stavu a zdraví aplikace (liveness/readiness).
      - 📄 `threads.py` — API endpointy pro správu konverzčních vláken a historie rozhovorů.
  - 📁 `core/` — Složka s jádrem konfigurace, nastavením vyhledávání a klasifikací dokumentů.
    - 📄 `classification_config.json` — Konfigurační soubor definující kategorie dokumentů a jejich přístupová práva (ACL).
    - 📄 `config.py` — Hlavní modul proměnných prostředí a nastavení aplikace pomocí Pydantic BaseSettings.
    - 📄 `prompts.py` — Podkladový PDF dokument nemocniční směrnice určený k indexaci (prompts.py).
    - 📄 `search_config.json` — Konfigurační soubor parametrů vyhledávání (RRF váhy, limity, práhy skóre).
    - 📄 `search_config.py` — Modul pro načítání a práci s konfigurací vyhledávání.
  - 📁 `ingestion/` — Složka modulů pro zpracování, dělení a indexaci dokumentů.
    - 📄 `chunking.py` — Modul pro dělení textu dokumentů na kontextové pasáže (chunks).
    - 📄 `extraction.py` — Modul pro extrakci textu z PDF dokumentů strana po straně.
    - 📁 `loaders/` — Složka loaderů pro načítání dokumentů z různých zdrojů.
      - 📄 `local.py` — Loader pro načítání a procházení dokumentů z lokálního souborového systému.
    - 📄 `pipeline.py` — Řídicí pipeline pro kompletní proces zpracování a uložení dokumentu.
    - 📄 `tagger.py` — Modul pro automatickou klasifikaci a tagování metadat dokumentů.
  - 📄 `main.py` — Vstupní bod FastAPI aplikace inicializující routy, CORS a middleware.
  - 📁 `providers/` — Složka s poskytovateli služeb (Azure OpenAI, Blob Storage, LLM rozhraní).
    - 📄 `azure_openai.py` — Poskytovatel rozhraní pro Azure OpenAI modely a klienty.
    - 📄 `blob_storage.py` — Poskytovatel pro práci s Azure Blob Storage úložistěm.
    - 📄 `embeddings.py` — Modul pro generování vektorových embeddingů pomocí Azure OpenAI.
    - 📄 `llm.py` — Modul pro generování textových odpovědí LLM modelu.
  - 📁 `retrieval/` — Složka vyhledávacích modulů pro vektorové i klíčové vyhledávání.
    - 📄 `base.py` — Abstraktní základní třída a rozhraní vyhledávače (VectorRetriever base).
    - 📄 `vector.py` — Implementace hybridního vyhledávání (pgvector + full-text RRF fúze).
  - 📁 `schemas/` — Složka Pydantic schémat pro validaci vstupních a výstupních dat API.
    - 📄 `chat.py` — Pydantic schémata pro chatové dotazy, odpovědi a citace.
    - 📄 `documents.py` — Pydantic schémata pro dokumenty, pasáže a metadata.
  - 📁 `storage/` — Složka pro práci s databází PostgreSQL a ORM modely.
    - 📄 `db.py` — Modul pro inicializaci SQLAlchemy databázového připojení a relací.
    - 📄 `models.py` — SQLAlchemy ORM modely reprezentující tabulky dokumentů, pasáží a uživatelů.

---

## 5. Uživatelská Frontend Aplikace (`frontend-user/`)

  - 📄 `.env.development` — Konfigurační soubor uživatelského frontendu (.env.development).
  - 📄 `.env.production` — Konfigurační soubor uživatelského frontendu (.env.production).
  - 📁 `app/` — Adresář app v aplikaci uživatelského frontendu.
    - 📁 `components/` — Adresář components v aplikaci uživatelského frontendu.
      - 📄 `AuthModal.tsx` — Zdrojový soubor komponenty nebo stránky uživatelského frontendu (AuthModal.tsx).
      - 📄 `PdfViewerModal.tsx` — Zdrojový soubor komponenty nebo stránky uživatelského frontendu (PdfViewerModal.tsx).
      - 📄 `ThreadSidebar.tsx` — Zdrojový soubor komponenty nebo stránky uživatelského frontendu (ThreadSidebar.tsx).
    - 📁 `config/` — Adresář config v aplikaci uživatelského frontendu.
      - 📄 `themes.ts` — Zdrojový soubor komponenty nebo stránky uživatelského frontendu (themes.ts).
    - 📄 `globals.css` — Zdrojový soubor komponenty nebo stránky uživatelského frontendu (globals.css).
    - 📄 `layout.tsx` — Zdrojový soubor komponenty nebo stránky uživatelského frontendu (layout.tsx).
    - 📄 `page.tsx` — Zdrojový soubor komponenty nebo stránky uživatelského frontendu (page.tsx).
    - 📄 `translations.ts` — Zdrojový soubor komponenty nebo stránky uživatelského frontendu (translations.ts).
  - 📄 `next-env.d.ts` — Konfigurační soubor uživatelského frontendu (next-env.d.ts).
  - 📄 `next.config.ts` — Konfigurační soubor uživatelského frontendu (next.config.ts).
  - 📄 `package-lock.json` — Konfigurační soubor uživatelského frontendu (package-lock.json).
  - 📄 `package.json` — Konfigurační soubor uživatelského frontendu (package.json).
  - 📄 `postcss.config.mjs` — Konfigurační soubor uživatelského frontendu (postcss.config.mjs).
  - 📁 `public/` — Statický veřejný soubor nebo logo uživatelského frontendu (public).
    - 📁 `logos/` — Statický veřejný soubor nebo logo uživatelského frontendu (logos).
      - 📄 `logo-dolphin-blue-background.jpg` — Statický veřejný soubor nebo logo uživatelského frontendu (logo-dolphin-blue-background.jpg).
      - 📄 `logo-dolphin-symbol.png` — Statický veřejný soubor nebo logo uživatelského frontendu (logo-dolphin-symbol.png).
      - 📄 `logo-nemocnice-alzbeta-2023.png` — Statický veřejný soubor nebo logo uživatelského frontendu (logo-nemocnice-alzbeta-2023.png).
  - 📄 `tsconfig.json` — Konfigurační soubor uživatelského frontendu (tsconfig.json).

---

## 6. Administrační Frontend Aplikace (`frontend-admin/`)

  - 📄 `.env.development` — Konfigurační soubor administračního frontendu (.env.development).
  - 📄 `.env.production` — Konfigurační soubor administračního frontendu (.env.production).
  - 📄 `.gitignore` — Konfigurační soubor administračního frontendu (.gitignore).
  - 📄 `AGENTS.md` — Konfigurační soubor administračního frontendu (AGENTS.md).
  - 📄 `CLAUDE.md` — Konfigurační soubor administračního frontendu (CLAUDE.md).
  - 📄 `README.md` — Konfigurační soubor administračního frontendu (README.md).
  - 📁 `app/` — Adresář app v aplikaci administračního frontendu.
    - 📁 `components/` — Adresář components v aplikaci administračního frontendu.
      - 📄 `AuthModal.tsx` — Zdrojový soubor komponenty nebo stránky administračního frontendu (AuthModal.tsx).
    - 📁 `config/` — Adresář config v aplikaci administračního frontendu.
      - 📄 `themes.ts` — Zdrojový soubor komponenty nebo stránky administračního frontendu (themes.ts).
    - 📄 `favicon.ico` — Zdrojový soubor komponenty nebo stránky administračního frontendu (favicon.ico).
    - 📄 `globals.css` — Zdrojový soubor komponenty nebo stránky administračního frontendu (globals.css).
    - 📄 `layout.tsx` — Zdrojový soubor komponenty nebo stránky administračního frontendu (layout.tsx).
    - 📄 `page.tsx` — Zdrojový soubor komponenty nebo stránky administračního frontendu (page.tsx).
    - 📄 `translations.ts` — Zdrojový soubor komponenty nebo stránky administračního frontendu (translations.ts).
  - 📄 `eslint.config.mjs` — Konfigurační soubor administračního frontendu (eslint.config.mjs).
  - 📄 `next-env.d.ts` — Konfigurační soubor administračního frontendu (next-env.d.ts).
  - 📄 `next.config.ts` — Konfigurační soubor administračního frontendu (next.config.ts).
  - 📄 `package-lock.json` — Konfigurační soubor administračního frontendu (package-lock.json).
  - 📄 `package.json` — Konfigurační soubor administračního frontendu (package.json).
  - 📄 `postcss.config.mjs` — Konfigurační soubor administračního frontendu (postcss.config.mjs).
  - 📁 `public/` — Statický veřejný soubor administračního frontendu (public).
    - 📄 `file.svg` — Statický veřejný soubor administračního frontendu (file.svg).
    - 📄 `globe.svg` — Statický veřejný soubor administračního frontendu (globe.svg).
    - 📁 `logos/` — Statický veřejný soubor administračního frontendu (logos).
      - 📄 `logo-dolphin-blue-background.jpg` — Statický veřejný soubor administračního frontendu (logo-dolphin-blue-background.jpg).
      - 📄 `logo-dolphin-symbol.png` — Statický veřejný soubor administračního frontendu (logo-dolphin-symbol.png).
      - 📄 `logo-nemocnice-alzbeta-2023.png` — Statický veřejný soubor administračního frontendu (logo-nemocnice-alzbeta-2023.png).
    - 📄 `next.svg` — Statický veřejný soubor administračního frontendu (next.svg).
    - 📄 `vercel.svg` — Statický veřejný soubor administračního frontendu (vercel.svg).
    - 📄 `window.svg` — Statický veřejný soubor administračního frontendu (window.svg).
  - 📄 `tsconfig.json` — Konfigurační soubor administračního frontendu (tsconfig.json).
  - 📄 `tsconfig.tsbuildinfo` — Konfigurační soubor administračního frontendu (tsconfig.tsbuildinfo).

---

## 7. Infrastruktura jako kód / IaC Bicep (`infra/`)

  - 📄 `README.md` — Soubor infrastruktury Azure Bicep (README.md).
  - 📄 `deploy_infra.ps1` — Soubor infrastruktury Azure Bicep (deploy_infra.ps1).
  - 📄 `main.bicep` — Soubor infrastruktury Azure Bicep (main.bicep).
  - 📄 `main.bicepparam` — Soubor infrastruktury Azure Bicep (main.bicepparam).
  - 📄 `main.json` — Soubor infrastruktury Azure Bicep (main.json).
  - 📁 `modules/` — Složka s Bicep moduly pro jednotlivé Azure zdroje (Postgres, Storage, ACA, OpenAI).
    - 📄 `acr.bicep` — Bicep modul pro nasazení Azure zdroje (acr.bicep).
    - 📄 `containerapp.bicep` — Bicep modul pro nasazení Azure zdroje (containerapp.bicep).
    - 📄 `log_analytics.bicep` — Bicep modul pro nasazení Azure zdroje (log_analytics.bicep).
    - 📄 `openai.bicep` — Bicep modul pro nasazení Azure zdroje (openai.bicep).
    - 📄 `postgres.bicep` — Bicep modul pro nasazení Azure zdroje (postgres.bicep).
    - 📄 `staticwebapp.bicep` — Bicep modul pro nasazení Azure zdroje (staticwebapp.bicep).
    - 📄 `storage.bicep` — Bicep modul pro nasazení Azure zdroje (storage.bicep).

---

## 8. Projektová dokumentace a ADR (`docs/`)

  - 📁 `adr/` — Složka obsahující záznamy architektonických rozhodnutí (Architectural Decision Records).
    - 📄 `ADR-0001-template.md` — Indexový a šablonový dokument pro vedení architektonických rozhodnutí.
    - 📄 `ADR-0002-use-postgresql-pgvector-for-mvp.md` — Záznam architektonického rozhodnutí: ADR-0002-use-postgresql-pgvector-for-mvp.md.
    - 📄 `ADR-0003-ingestion-pipeline.md` — Záznam architektonického rozhodnutí: ADR-0003-ingestion-pipeline.md.
    - 📄 `ADR-0004-nextjs-frontend-framework.md` — Záznam architektonického rozhodnutí: ADR-0004-nextjs-frontend-framework.md.
    - 📄 `ADR-0005-weighted-rrf-hybrid-retrieval.md` — Záznam architektonického rozhodnutí: ADR-0005-weighted-rrf-hybrid-retrieval.md.
    - 📄 `ADR-0006-custom-hybrid-retrieval-vs-langchain.md` — Záznam architektonického rozhodnutí: ADR-0006-custom-hybrid-retrieval-vs-langchain.md.
    - 📄 `ADR-0007-azure-blob-storage-for-document-hosting.md` — Záznam architektonického rozhodnutí: ADR-0007-azure-blob-storage-for-document-hosting.md.
    - 📄 `ADR-0008-dynamic-pdf-annotations-highlighting.md` — Záznam architektonického rozhodnutí: ADR-0008-dynamic-pdf-annotations-highlighting.md.
    - 📄 `ADR-0009-automatic-tagging-metadata-and-archival-system.md` — Záznam architektonického rozhodnutí: ADR-0009-automatic-tagging-metadata-and-archival-system.md.
    - 📄 `ADR-0010-persistent-dynamic-classification-configuration-and-universal-ids.md` — Záznam architektonického rozhodnutí: ADR-0010-persistent-dynamic-classification-configuration-and-universal-ids.md.
    - 📄 `ADR-0011-subfolder-data-source-ingestion-and-filtering.md` — Záznam architektonického rozhodnutí: ADR-0011-subfolder-data-source-ingestion-and-filtering.md.
    - 📄 `ADR-0012-customizable-search-retrieval-parameters.md` — Záznam architektonického rozhodnutí: ADR-0012-customizable-search-retrieval-parameters.md.
    - 📄 `ADR-0013-hybrid-search-fusion-strategies.md` — Záznam architektonického rozhodnutí: ADR-0013-hybrid-search-fusion-strategies.md.
    - 📄 `ADR-0014-context-expansion-strategies.md` — Záznam architektonického rozhodnutí: ADR-0014-context-expansion-strategies.md.
    - 📄 `ADR-0015-multi-environment-dev-prod-architecture.md` — Záznam architektonického rozhodnutí: ADR-0015-multi-environment-dev-prod-architecture.md.
  - 📁 `deployments/` — Složka s návody a prameny pro nasazení do Azure cloudu.
    - 📄 `azure_bicep_provisioning_guide.md` — Dokumentace a návod k nasazení: azure_bicep_provisioning_guide.md.
    - 📄 `cloud_deployment_guide.md` — Dokumentace a návod k nasazení: cloud_deployment_guide.md.
  - 📁 `design/` — Složka s podrobnými návrhy architektury, multi-tenancy a frontendu.
    - 📄 `database_schema.md` — Architektonický návrhový dokument: database_schema.md.
    - 📄 `environments_and_tenancy.md` — Architektonický návrhový dokument: environments_and_tenancy.md.
    - 📄 `frontend_architecture.md` — Architektonický návrhový dokument: frontend_architecture.md.
    - 📄 `hybrid_search.md` — Architektonický návrhový dokument: hybrid_search.md.
    - 📄 `metadata_tagging_system.md` — Architektonický návrhový dokument: metadata_tagging_system.md.
  - 📄 `initial_design_doc.md` — Podkladový PDF dokument nemocniční směrnice určený k indexaci (initial_design_doc.md).
  - 📄 `navigation_guide.md` — Kompletní průvodce adresářovou strukturou repozitáře a popisem všech souborů.
  - 📁 `runbooks/` — Složka s podkladovými nemocničními směrnicemi a řády (runbooks).
    - 📄 `azure-first-deployment.md` — Podkladový PDF dokument nemocniční směrnice určený k indexaci (azure-first-deployment.md).
  - 📁 `tests_explained/` — Složka s detailním vysvětlením jednotlivých testů pro vývojáře.
    - 📄 `test_health.md` — Dokumentace s vysvětlením testovacího modulu test_health.md.
    - 📄 `test_hybrid_retrieval.md` — Dokumentace s vysvětlením testovacího modulu test_hybrid_retrieval.md.
    - 📄 `test_ingestion.md` — Dokumentace s vysvětlením testovacího modulu test_ingestion.md.
    - 📄 `test_metadata_tagging.md` — Dokumentace s vysvětlením testovacího modulu test_metadata_tagging.md.
    - 📄 `test_multi_tenant_auth.md` — Dokumentace s vysvětlením testovacího modulu test_multi_tenant_auth.md.
    - 📄 `test_pdf_annotations.md` — Dokumentace s vysvětlením testovacího modulu test_pdf_annotations.md.
    - 📄 `test_rag_pipeline.md` — Dokumentace s vysvětlením testovacího modulu test_rag_pipeline.md.
    - 📄 `test_rechunk.md` — Dokumentace s vysvětlením testovacího modulu test_rechunk.md.
    - 📄 `test_search_config.md` — Dokumentace s vysvětlením testovacího modulu test_search_config.md.
    - 📄 `test_security_freshness.md` — Dokumentace s vysvětlením testovacího modulu test_security_freshness.md.
    - 📄 `test_security_prefilter.md` — Dokumentace s vysvětlením testovacího modulu test_security_prefilter.md.
    - 📄 `test_tenant_prompts.md` — Dokumentace s vysvětlením testovacího modulu test_tenant_prompts.md.
    - 📄 `test_vector_db.md` — Dokumentace s vysvětlením testovacího modulu test_vector_db.md.

---

## 9. Automatizované Testy (`tests/`)

  - 📄 `conftest.py` — Testovací modul pytest ověřující funkčnost conftest.py.
  - 📄 `test_health.py` — Testovací modul pytest ověřující funkčnost test_health.py.
  - 📄 `test_hybrid_retrieval.py` — Testovací modul pytest ověřující funkčnost test_hybrid_retrieval.py.
  - 📄 `test_ingestion.py` — Testovací modul pytest ověřující funkčnost test_ingestion.py.
  - 📄 `test_metadata_tagging.py` — Testovací modul pytest ověřující funkčnost test_metadata_tagging.py.
  - 📄 `test_multi_tenant_auth.py` — Testovací modul pytest ověřující funkčnost test_multi_tenant_auth.py.
  - 📄 `test_pdf_annotations.py` — Testovací modul pytest ověřující funkčnost test_pdf_annotations.py.
  - 📄 `test_rag_pipeline.py` — Testovací modul pytest ověřující funkčnost test_rag_pipeline.py.
  - 📄 `test_rechunk.py` — Testovací modul pytest ověřující funkčnost test_rechunk.py.
  - 📄 `test_search_config.py` — Testovací modul pytest ověřující funkčnost test_search_config.py.
  - 📄 `test_security_freshness.py` — Testovací modul pytest ověřující funkčnost test_security_freshness.py.
  - 📄 `test_security_prefilter.py` — Testovací modul pytest ověřující funkčnost test_security_prefilter.py.
  - 📄 `test_tenant_prompts.py` — Testovací modul pytest ověřující funkčnost test_tenant_prompts.py.
  - 📄 `test_vector_db.py` — Testovací modul pytest ověřující funkčnost test_vector_db.py.

---

## 10. Metadatový balíček Python (`ai_search_app.egg-info/`)

  - 📄 `PKG-INFO` — Metadatový soubor Python balíčku PKG-INFO.
  - 📄 `SOURCES.txt` — Metadatový soubor Python balíčku SOURCES.txt.
  - 📄 `dependency_links.txt` — Metadatový soubor Python balíčku dependency_links.txt.
  - 📄 `requires.txt` — Metadatový soubor Python balíčku requires.txt.
  - 📄 `top_level.txt` — Metadatový soubor Python balíčku top_level.txt.

