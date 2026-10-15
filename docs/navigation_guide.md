# Průvodce navigací v repozitáři (`navigation_guide.md`)

Tento dokument poskytuje přehled a organizační strukturu repozitáře projektu **AI Search Full**. U každé složky i zdrojového a konfiguračního souboru je uveden výstižný jednovětý popis vysvětlující jeho účel a roli v projektu. Složka `data/` je uváděna výhradně jako kořenový adresář.

> [!IMPORTANT]
> **Pravidlo pro vývoj a AI agenty:** Tento dokument představuje kanonický katalog struktury projektu. Příslušná pravidla v `.agents/AGENTS.md` a `.agents/rules/documentation-policy.md` stanovují povinnost aktualizovat tento soubor **při každém vytvoření nového souboru nebo složky** kdekoliv v repozitáři (s výjimkou obsahu složky `data/`). Položky jsou uváděny v čistém reliktním formátu v zpětných uvozovkách bez absolutních odkazů.

---

## 1. Kořenové soubory a skripty projektu (`/`)

- 📁 `.agents/` — Hlavní složka obsahující systém instrukcí, pravidel a paměti pro vývojové AI agenty.
- 📄 `.dockerignore` — Konfigurační soubor definující ignorované soubory při sestavování Docker image.
- 📁 `.vscode/` — Sdílená konfigurace VS Code pro spouštění lokální aplikace a testů.
- 📄 `.vscode/tasks.json` — Úlohy VS Code pro SQL Server, backend, uživatelský frontend a izolované testy.
- 📄 `.env` — Soubor lokálních proměnných prostředí a konfigurace přístupů (neverzuje se).
- 📄 `.env.local` — Automaticky vytvořená lokální konfigurace s náhodným heslem pro SQL Server Developer.
- 📄 `.env.dev` — Šablona konfiguračních proměnných prostředí pro vývojové prostředí DEV.
- 📄 `.env.example` — Vzorová šablona proměnných prostředí sloužící jako návod pro lokální nastavení.
- 📄 `.env.ju-prod` — Konfigurační soubor proměnných prostředí vyhrazený pro produkční tenant JHU (ju-prod) v Azure.
- 📄 `.env.prod` — Šablona konfiguračních proměnných prostředí pro produkční prostředí PROD.
- 📁 `.github/` — Složka konfiguračních souborů a pracovních postupů pro GitHub.
- 📄 `.gitignore` — Konfigurační soubor určující, které soubory a složky má Git ignorovat.
- 📁 `.local/` — Ignorované runtime soubory a tenantí konfigurační overlay pro profily local a test.
- 📁 `.local/benchmarks/` — Ignorované query cache a JSON reporty lokálních nebo soukromých retrieval benchmarků.
- 📁 `.local/deployments/` — Ignorované provozní checkpointy a šifrované zálohy pro schválená nasazení.
- 📁 `.local/deployments/jhu-search-20261015/` — Uchovává ne-secret stav JHU rollout a Windows DPAPI snímky původní konfigurace a dotčených dat.
- 📁 `scratch/` — Ignorované jednorázové operátorské a diagnostické skripty v pracovním adresáři.
- 📄 `scratch/jhu_rollout.py` — Provádí schválené fáze JHU rollout s ochranou secrets, checkpointy a úklidem vlastních testovacích objektů.
- 📄 `docs/deployments/2026-10-15-jhu-search-rollout.md` — Zaznamenává dokončené JHU nasazení, skutečné cloudové důkazy, zachování dat, kompatibilní návrat a otevřený výkonový problém.
- 📄 `.env.showcase` — Konfigurační soubor proměnných prostředí vyhrazený pro Showcase tenant v Azure.
- 📄 `AGENTS.md` — Klíčový dokument definující provozní kontrakt, pravidla a role vývojových AI agentů v repozitáři.
- 📄 `CHANGELOG.md` — Changelog projektových změn, nových funkcí a oprav chyb strukturovaný dle verzí.
- 📁 `docs/releases/` — Uchovává souhrny vydaných verzí, ověřené výsledky a známá omezení.
- 📄 `docs/releases/v0.1.4.md` — Shrnuje všechny změny od v0.1.3 včetně lokálního vývoje, Azure SQL vyhledávání, zabezpečení a dosud vypnutého ANN.
- 📄 `Dockerfile` — Recept pro sestavení Docker kontejneru backendové FastAPI aplikace.
- 📄 `docker-compose.local.yml` — Lokální SQL Server Developer kontejner s databázovými daty v persistentním Docker volume.
- 📄 `dev.ps1` — Pomocný skript pro start lokální databáze, backendu, izolovaných testů a zastavení databáze.
- 📄 `migrate_search_acl.py` — Explicitní audit a ručně spouštěná migrace relační ACL projekce pro ověřený SQL Server cíl.
- 📄 `migrate_search_vectors.py` — Audituje, vytváří, doplňuje a explicitně aktivuje profilové indexy jen pro potvrzený databázový cíl.
- 📄 `migrate_search_schema.py` — Provádí explicitně schválený přesun identity korpusu a Unicode migraci s obnovou zachyceného Full-Text indexu.
- 📄 `benchmark_search.py` — Připravuje cache dotazových embeddingů a spouští read-only exact/ANN evaluaci s měřením a aktivačními branami.
- 📄 `README.md` — Hlavní úvodní dokumentace repozitáře popisující architekturu, spuštění a nasazení.
- 📁 `ai_search_app.egg-info/` — Složka s metadaty Python balíčku vygenerovaná při instalaci.
- 📁 `app/` — Hlavní složka zdrojového kódu backendové FastAPI aplikace.
- 📄 `ask.py` — Pomocný CLI skript pro rychlé testování dotazů vůči RAG vyhledávacímu backendu.
- 📄 `check_diff.py` — Pomocný skript pro porovnání změn a kontrolu konzistence kódu.
- 📁 `data/` — Složka podkladových zdrojových PDF dokumentů určených k indexaci.
- 📄 `deploy_all.ps1` — Blokuje původní kombinované nasazení, aby čtecí plán backendu nespustil zápisy frontendů.
- 📄 `deploy_backend.ps1` — Vypíše čtecí plán a po explicitním potvrzení aktualizuje pouze image ověřené existující Container App.
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
    - 📄 `2026-08-18-azure-sql-manual-setup-handoff.md` — Handoff soubor s pokyny pro manuální zřízení Azure SQL Serveru a Databáze (2026-08-18-azure-sql-manual-setup-handoff.md).
    - 📄 `2026-09-02-azure-resource-deployment-handoff.md` — Handoff soubor s pokyny pro ruční nastavení Azure zdrojů ve 3 Resource Group a DTU módu (2026-09-02-azure-resource-deployment-handoff.md).
    - 📄 `2026-09-02-azure-showcase-deployment-handoff.md` — Handoff soubor s vyhrazenými pokyny pro manuální zřízení Showcase prostředí v RG ai-search-showcase-rg-dev (2026-09-02-azure-showcase-deployment-handoff.md).
    - 📄 `2026-09-25-jhu-prod-azure-deployment-handoff.md` — Handoff soubor a registr zdrojů vyhrazený pro produkční tenant JHU v RG ju-ai-search-rg-prod (2026-09-25-jhu-prod-azure-deployment-handoff.md).
    - 📄 `2026-10-05-tenant-env-placeholder-handoff.md` — Handoff soubor s informacemi o 100% paritě tenantových .env souborů a seznamu zavedených placeholderů.
    - 📄 `2026-10-06-showcase-keyvault-deployment-handoff.md` — Handoff soubor s pokyny pro zřízení Key Vaultu a naplnění secretů pro Showcase tenant.
    - 📄 `2026-10-07-jhu-keyvault-rbac-handoff.md` — Handoff soubor s návodem pro schválení RBAC role Key Vault Secrets User a naplnění secretů pro JHU PROD tenant.
    - 📄 `2026-10-14-search-acl-migration-handoff.md` — Ruční Azure handoff pro tenant audit, grant tabulky, soukromý signing klíč a ověření slice 2 před nasazením.
    - 📄 `2026-10-14-native-vector-exact-search-handoff.md` — Ruční Azure handoff pro prázdnou native test DB, přesné VECTOR hledání, backfill a řízenou aktivaci slice 3.
    - 📄 `2026-10-14-diskann-search-handoff.md` — Odložený Azure handoff pro DiskANN verze alespoň 3, integrační bránu a provozní návrat do exact.
    - 📄 `2026-10-14-search-evaluation-activation-handoff.md` — Lidský handoff pro reprezentativní cloudový benchmark, native/runtime kontrolu, aktivaci ANN a rollback.
    - 📄 `2026-10-15-jhu-search-rollout-handoff.md` — Zachycuje skutečný JHU inventář, aliasy korpusu, blokery loginů a postup schvalovaného nasazení s rollbackem.
    - 📄 `2026-10-15-jhu-jwt-password-migration-handoff.md` — Popisuje dva oddělené secrets, přechod starých hesel a validaci i rollback přihlašování JHU bez nových rolí.
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
    - 📄 `tenant-configuration-policy.md` — Pravidla pro správa tenant konfigurací, promptů, metaparametrů a grafických podkladů ve složce tenants/.
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
    - 📄 `identity.py` — Ověření bearer identity přesného tenantu a aktuálních serverových skupin včetně Management dependency.
    - 📄 `dependencies.py` — Modul závislostí FastAPI (získání databázových relací, ověření tokenů a tenantů).
    - 📁 `routes/` — Složka s definicemi jednotlivých koncových bodů (endpoints) API.
      - 📄 `auth.py` — API endpointy pro autentizaci uživatelů, přihlášení a registrace.
      - 📄 `chat.py` — API endpointy pro RAG vyhledávání, chatové dotazy a generování odpovídajících citací.
      - 📄 `documents.py` — API endpointy pro správu, nahrávání a mazání dokumentů.
      - 📄 `health.py` — API endpointy pro kontrolu stavu a zdraví aplikace (liveness/readiness).
      - 📄 `prompts.py` — Podkladový PDF dokument nemocniční směrnice určený k indexaci (prompts.py).
      - 📄 `threads.py` — API endpointy pro správu konverzčních vláken a historie rozhovorů.
  - 📁 `core/` — Složka s jádrem konfigurace, nastavením vyhledávání a tenant resolverem.
    - 📄 `config.py` — Hlavní modul proměnných prostředí a nastavení aplikace pomocí Pydantic BaseSettings.
    - 📄 `passwords.py` — Ukládá Argon2id hesla nezávislá na JWT a explicitně ověřuje staré hashe pro řízený přechod při loginu.
    - 📄 `prompts.py` — Modul pro správu a načítání RAG systémových promptů.
    - 📄 `search_config.py` — Modul pro načítání a práci s konfigurací vyhledávání.
    - 📄 `tenant_config.py` — Hlavní resolver pro načítání konfigurací tenantů s automatickým fallbackem na tenants/default/.
  - 📁 `evaluation/` — Nástroje pro reprodukovatelné hodnocení kvality a výkonu retrievalu bez generování odpovědí.
    - 📄 `__init__.py` — Inicializuje balíček operátorské retrieval evaluace.
    - 📄 `search_benchmark.py` — Validuje dataset/cache, měří recall a zátěž a připravuje bezpečný report s branami pro lidské review.
  - 📁 `ingestion/` — Složka modulů pro zpracování, dělení a indexaci dokumentů.
    - 📄 `chunking.py` — Modul pro dělení textu dokumentů na kontextové pasáže (chunks).
    - 📄 `extraction.py` — Modul pro extrakci textu z PDF dokumentů strana po straně.
    - 📄 `local_demo.py` — Automaticky a idempotentně indexuje dvě české ukázky Aurora pouze do lokálního SQL Serveru.
    - 📄 `index_backfill.py` — Dávkově doplňuje profilové embeddingy ze současných chunků nebo doložených historických vektorů bez nové extrakce.
    - 📁 `loaders/` — Složka loaderů pro načítání dokumentů z různých zdrojů.
      - 📄 `local.py` — Loader pro načítání a procházení dokumentů z lokálního souborového systému.
    - 📄 `pipeline.py` — Řídicí pipeline pro kompletní proces zpracování a uložení dokumentu.
    - 📄 `tagger.py` — Modul pro automatickou klasifikaci a tagování metadat dokumentů.
  - 📄 `main.py` — Vstupní bod FastAPI aplikace inicializující routy, CORS a middleware.
  - 📁 `providers/` — Složka s poskytovateli služeb (Azure OpenAI, Blob Storage, LLM rozhraní).
    - 📄 `azure_openai.py` — Poskytovatel rozhraní pro Azure OpenAI modely a klienty.
    - 📄 `blob_storage.py` — Poskytovatel pro práci s Azure Blob Storage úložistěm.
    - 📄 `embeddings.py` — Rozhraní embedding provideru a neměnný profil popisující identitu vektorového prostoru.
    - 📄 `factory.py` — Centrální factory vytvářející nakonfigurované embeddingové a jazykové providery.
    - 📄 `llm.py` — Modul pro generování textových odpovědí LLM modelu.
  - 📁 `retrieval/` — Složka vyhledávacích modulů pro vektorové i klíčové vyhledávání.
    - 📄 `access.py` — Společné kontroly oprávnění náhledů a historie s transitivními referencemi na použité chunky.
    - 📄 `filters.py` — Parametrizované SQL prefiltry tenantů, relačních ACL, freshness a typovaných metadat pro obě větve.
    - 📄 `base.py` — Abstraktní základní třída a rozhraní vyhledávače (VectorRetriever base).
    - 📄 `vector.py` — Implementace hybridního vyhledávání (pgvector + full-text RRF fúze).
  - 📁 `schemas/` — Složka Pydantic schémat pro validaci vstupních a výstupních dat API.
    - 📄 `chat.py` — Pydantic schémata pro chatové dotazy, odpovědi a citace.
    - 📄 `documents.py` — Pydantic schémata pro dokumenty, pasáže a metadata.
  - 📁 `storage/` — Složka pro práci s databází PostgreSQL a ORM modely.
    - 📄 `acl.py` — Transakční synchronizace grantů při ORM zápisech, bezpečný bulk insert chunků a explicitní backfill projekce.
    - 📄 `vector_store.py` — Spravuje immutable profilové indexy, transakční vector zápisy, revize vstupu a přesné nativní i lokální hledání.
    - 📄 `ann_search.py` — Ověřuje DiskANN katalog, vykonává filtrované ANN hledání a řídí explicitní režimy, timeouty a diagnostiku.
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
      - 📄 `AuthenticatedPdf.tsx` — Autentizované načtení PDF přes bearer fetch a blob prohlížeč bez tokenu v URL.
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
      - 📄 `authenticatedPdf.ts` — Autentizované otevření PDF z administrace přes blob URL bez zveřejnění tokenu v odkazu.
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
  - 📄 `create_azure_resources.ps1` — Parametrizovaný skript pro automatické založení všech Azure zdrojů přes Azure CLI.
  - 📄 `deploy_infra.ps1` — Soubor infrastruktury Azure Bicep (deploy_infra.ps1).
  - 📄 `main.bicep` — Soubor infrastruktury Azure Bicep (main.bicep).
  - 📄 `main.bicepparam` — Soubor infrastruktury Azure Bicep (main.bicepparam).
  - 📄 `main.json` — Soubor infrastruktury Azure Bicep (main.json).
  - 📁 `modules/` — Složka s Bicep moduly pro jednotlivé Azure zdroje (Postgres, Storage, ACA, OpenAI).
    - 📄 `acr.bicep` — Bicep modul pro nasazení Azure zdroje (acr.bicep).
    - 📄 `azuresql.bicep` — Bicep modul pro nasazení Azure SQL Serveru a Databáze v DTU módu (azuresql.bicep).
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
    - 📄 `ADR-0016-azure-sql-database-migration.md` — Záznam architektonického rozhodnutí: ADR-0016-azure-sql-database-migration.md.
    - 📄 `ADR-0017-azure-sql-dtu-model-and-resource-group-architecture.md` — Záznam architektonického rozhodnutí: Přechod na Azure SQL DTU nákupní model a 3-tier Resource Group architekturu (ADR-0017-azure-sql-dtu-model-and-resource-group-architecture.md).
    - 📄 `ADR-0018-unified-tenant-directory-and-fallback-system.md` — Záznam architektonického rozhodnutí: Sjednocená adresářová struktura tenants/ a souborový fallback systém (ADR-0018-unified-tenant-directory-and-fallback-system.md).
    - 📄 `ADR-0019-embedding-profiles-and-provider-factories.md` — Rozhodnutí o identitě embeddingových profilů a centrálním výběru modelových providerů.
    - 📄 `ADR-0020-local-sqlserver-and-isolated-test-profile.md` — Rozhodnutí o lokálním SQL Serveru a bezpečném oddělení profilů local/test od cloudové konfigurace.
    - 📄 `ADR-0021-authoritative-search-identity-and-relational-acl.md` — Rozhodnutí o ověřené identitě, relačních ACL, SQL prefiltrech a ochraně náhledů i historie.
    - 📄 `ADR-0022-local-university-fixtures-and-unicode.md` — Rozhodnutí o automatických lokálních PDF ukázkách, profilech embeddingů a Unicode textech SQL Serveru.
    - 📄 `ADR-0023-profile-index-catalog-and-exact-vector-storage.md` — Rozhodnutí o profilovém katalogu, nativních vector tabulkách, revizích a úplném přesném hledání.
    - 📄 `ADR-0024-explicit-diskann-search-and-failure-policy.md` — Rozhodnutí o DiskANN verze alespoň 3, prefiltrech, explicitních režimech a chybách bez fallbacku.
    - 📄 `ADR-0025-reproducible-search-evaluation-and-human-activation.md` — Rozhodnutí o oddělení cache/modelů, benchmark metrikách, ochraně porovnatelnosti a lidské aktivaci.
    - 📄 `ADR-0026-reviewed-existing-app-releases.md` — Odděluje image release od migrací, secrets a ingestace s výchozím čtecím plánem.
    - 📄 `ADR-0027-keyvault-jwt-and-password-hash-migration.md` — Odděluje JWT a Argon2 hesla s explicitním legacy verifierem a transakčním přechodem při přihlášení.
  - 📁 `development/` — Návody pro lokální vývoj a běžné vývojářské úlohy.
    - 📄 `local-setup.md` — Postup pro první lokální spuštění ve VS Code, práci s databází a izolované testy.
    - 📄 `search-slice-2-testing.md` — Automatické i ruční ověření search slice 2 s lokálním SQL Serverem a Azure integrační hranicí.
    - 📄 `search-slice-3-testing.md` — Lokální migrace, akceptace přesného profilového hledání a bezpečné spuštění native Azure testu.
    - 📄 `search-slice-4-testing.md` — Návod k lokálním ANN kontraktům, diagnostice a pozdějšímu nativnímu Azure ověření.
    - 📄 `search-slice-5-testing.md` — Návod ke spuštění benchmark CLI z VS Code, interpretaci reportů a dokončení cloudových bran.
  - 📁 `architecture/` — Architektonické podklady a schválené plány dalšího vývoje aplikace.
    - 📄 `azure-sql-search-roadmap.md` — Schválený plán pěti sliců Azure SQL vyhledávání se stavem, podmínkami dokončení, testy a hranicemi rozsahu.
    - 📄 `app_database_usage_info_dump.md` — Podkladový PDF dokument nemocniční směrnice určený k indexaci (app_database_usage_info_dump.md).
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
  - 📄 `ai_search_marketing_summary.md` — Marketingové a technické shrnutí projektu AI Search v češtině.
  - 📄 `navigation_guide.md` — Kompletní průvodce adresářovou strukturou repozitáře a popisem všech souborů.
  - 📁 `runbooks/` — Složka s podkladovými nemocničními směrnicemi a řády (runbooks).
    - 📄 `azure-first-deployment.md` — Podkladový PDF dokument nemocniční směrnice určený k indexaci (azure-first-deployment.md).
  - 📁 `tests_explained/` — Složka s detailním vysvětlením jednotlivých testů pro vývojáře.
    - 📄 `conftest.md` — Vysvětlení izolované SQLite databáze, tenantích overlay a skutečných testovacích manager tokenů.
    - 📄 `test_search_access.md` — Vysvětlení SQLite a SQL Server regresí prefiltrů, identity, ACL a transitivní historie.
    - 📄 `test_vector_store.md` — Vysvětlení testů profilového katalogu, úplného hledání, životnosti embeddingů a native Azure integrační brány.
    - 📄 `test_rollout_schema.md` — Popisuje test přesné tenant/Unicode migrace, count guardů a samostatné Azure ověření FTS obnovy.
    - 📄 `test_ann_search.md` — Vysvětlení ANN SQL kontraktů, chybové politiky, ODBC timeoutů a odloženého cloudového testu.
    - 📄 `test_native_sql_harness.md` — Vysvětluje izolaci skutečných native testů ve vlastním schématu, Entra přihlášení a bezpečný úklid.
    - 📄 `test_search_benchmark.md` — Vysvětlení benchmark metrik, cache, identity, driftu, orchestrace a aktivačních bran.
    - 📄 `test_health.md` — Dokumentace s vysvětlením testovacího modulu test_health.md.
    - 📄 `test_hybrid_retrieval.md` — Dokumentace s vysvětlením testovacího modulu test_hybrid_retrieval.md.
    - 📄 `test_ingestion.md` — Dokumentace s vysvětlením testovacího modulu test_ingestion.md.
    - 📄 `test_keyvault_config.md` — Dokumentace s vysvětlením testovacího modulu test_keyvault_config.py pro Azure Key Vault integraci a 100% paritu klíčů.
    - 📄 `test_password_migration.md` — Vysvětluje ověření Argon2, tenant izolace, legacy přechodu, JWT rotace a rollbacku SQL zápisů.
    - 📄 `test_metadata_tagging.md` — Dokumentace s vysvětlením testovacího modulu test_metadata_tagging.md.
    - 📄 `test_multi_tenant_auth.md` — Dokumentace s vysvětlením testovacího modulu test_multi_tenant_auth.md.
    - 📄 `test_pdf_annotations.md` — Dokumentace s vysvětlením testovacího modulu test_pdf_annotations.md.
    - 📄 `test_prompts_api.md` — Dokumentace s vysvětlením testovacího modulu test_prompts_api.md.
    - 📄 `test_rag_pipeline.md` — Dokumentace s vysvětlením testovacího modulu test_rag_pipeline.md.
    - 📄 `test_rechunk.md` — Dokumentace s vysvětlením testovacího modulu test_rechunk.md.
    - 📄 `test_search_config.md` — Dokumentace s vysvětlením testovacího modulu test_search_config.md.
    - 📄 `test_security_freshness.md` — Dokumentace s vysvětlením testovacího modulu test_security_freshness.md.
    - 📄 `test_security_prefilter.md` — Dokumentace s vysvětlením testovacího modulu test_security_prefilter.md.
    - 📄 `test_tenant_config.md` — Dokumentace s vysvětlením testovacího modulu test_tenant_config.md pro ověření tenant resolveru a fallbacku.
    - 📄 `test_embedding_profiles.md` — Vysvětlení testů identity embeddingových profilů, validace vektorů, Azure adaptéru a provider factory.
    - 📄 `test_local_development_config.md` — Vysvětlení testů volby a validace lokálního SQL Server backendu.
    - 📄 `test_dev_script.md` — Vysvětlení regresních testů Docker stderr varování a exit kódů ve vývojovém PowerShell skriptu.
    - 📄 `test_backend_deployment.md` — Vysvětluje skutečné PowerShell testy read-only plánu, release guardů a image-only update s falešným Azure CLI.
    - 📄 `test_tenant_prompts.md` — Dokumentace s vysvětlením testovacího modulu test_tenant_prompts.md.
    - 📄 `test_vector_db.md` — Dokumentace s vysvětlením testovacího modulu test_vector_db.md.

---

## 9. Automatizované Testy (`tests/`)

  - 📄 `test_search_access.py` — Regresní scénáře autorizace a prefiltrů se skutečnou izolovanou lokální SQL Server variantou.
  - 📄 `test_vector_store.py` — Ověřuje profilové indexy, přesný top K, transakce a volitelnou skutečnou native Azure SQL cestu.
  - 📄 `test_ann_search.py` — Testuje DiskANN režimy, SQL prefiltry, diagnostiku, timeouty a volitelnou nativní Azure integraci.
  - 📄 `native_sql_harness.py` — Umožňuje native integraci přes Entra CLI v novém izolovaném schématu existující testovací databáze.
  - 📄 `test_native_sql_harness.py` — Ověřuje ochranné podmínky, překlad schématu a lokální MSSQL úklid bez zásahu do původních tabulek.
  - 📄 `test_search_benchmark.py` — Ověřuje read-only benchmark na SQLite i MSSQL, správnost metrik a bezpečné odmítnutí aktivace.

  - 📄 `conftest.py` — Testovací modul pytest ověřující funkčnost conftest.py.
  - 📄 `test_health.py` — Testovací modul pytest ověřující funkčnost test_health.py.
  - 📄 `test_hybrid_retrieval.py` — Testovací modul pytest ověřující funkčnost test_hybrid_retrieval.py.
  - 📄 `test_ingestion.py` — Testovací modul pytest ověřující funkčnost test_ingestion.py.
  - 📄 `test_keyvault_config.py` — Testovací modul pytest ověřující načítání sekretů z Azure Key Vault a 100% paritu klíčů v tenant environment souborech.
  - 📄 `test_password_migration.py` — Ověřuje bezpečný přechod hesel při loginu na SQLite a lokálním SQL Serveru bez změn v Azure.
  - 📄 `test_rollout_schema.py` — Ověřuje schema migraci na izolovaném lokálním SQL Serveru s ochranou podobně pojmenovaných tenantů a transakčním rollbackem.
  - 📄 `test_metadata_tagging.py` — Testovací modul pytest ověřující funkčnost test_metadata_tagging.py.
  - 📄 `test_multi_tenant_auth.py` — Testovací modul pytest ověřující funkčnost test_multi_tenant_auth.py.
  - 📄 `test_pdf_annotations.py` — Testovací modul pytest ověřující funkčnost test_pdf_annotations.py.
  - 📄 `test_prompts_api.py` — Testovací modul pytest ověřující funkčnost test_prompts_api.py.
  - 📄 `test_rag_pipeline.py` — Testovací modul pytest ověřující funkčnost test_rag_pipeline.py.
  - 📄 `test_rechunk.py` — Testovací modul pytest ověřující funkčnost test_rechunk.py.
  - 📄 `test_search_config.py` — Testovací modul pytest ověřující funkčnost test_search_config.py.
  - 📄 `test_security_freshness.py` — Testovací modul pytest ověřující funkčnost test_security_freshness.py.
  - 📄 `test_security_prefilter.py` — Testovací modul pytest ověřující funkčnost test_security_prefilter.py.
  - 📄 `test_tenant_config.py` — Testovací modul pytest ověřující funkčnost tenant resolveru, rezoluce souborů a fallbacku z default.
  - 📄 `test_tenant_prompts.py` — Testovací modul pytest ověřující funkčnost test_tenant_prompts.py.
  - 📄 `test_embedding_profiles.py` — Testy fingerprintu profilu, validace vektorů, zpracování dotazů a dokumentů a výběru providerů.
  - 📄 `test_local_development_config.py` — Testy izolované konfigurace lokální databáze SQL Server.
  - 📄 `test_dev_script.py` — Regresní testy skutečného vývojového skriptu v PowerShellu s nativní simulací Docker varování a chyb.
  - 📄 `test_backend_deployment.py` — Ověřuje plán, ochrany cíle a chyb, zachování runtime konfigurace a blokování kombinovaného deploymentu.
  - 📄 `test_vector_db.py` — Testovací modul pytest ověřující funkčnost test_vector_db.py.

---

## Testovací dokumenty (`fixtures/`)

- `fixtures/` — Verzované zdrojové dokumenty pro opakovatelné lokální testování aplikace.
  - `fixtures/local-university/` — Dva jednostránkové české PDF o fiktivní Vysoké škole Aurora určené pro lokální automatickou indexaci.
    - `fixtures/local-university/studijni-rad.pdf` — Ukázkový dokument popisující semestry, kredity, zápis předmětů, zkoušky a přerušení studia.
    - `fixtures/local-university/sluzby-studentum.pdf` — Ukázkový dokument popisující studijní oddělení, knihovnu, koleje, stipendium a Erasmus.
    - `fixtures/local-university/search-smoke.json` — Osm českých dotazů a filtrů pro lokální benchmark smoke nad ukázkami Aurora.

## 10. Metadatový balíček Python (`ai_search_app.egg-info/`)

  - 📄 `PKG-INFO` — Metadatový soubor Python balíčku PKG-INFO.
  - 📄 `SOURCES.txt` — Metadatový soubor Python balíčku SOURCES.txt.
  - 📄 `dependency_links.txt` — Metadatový soubor Python balíčku dependency_links.txt.
  - 📄 `requires.txt` — Metadatový soubor Python balíčku requires.txt.
  - 📄 `top_level.txt` — Metadatový soubor Python balíčku top_level.txt.

---

## 11. Sjednocená složka tenantů (`tenants/`)

  - 📁 `tenants/` — Hlavní kanonický adresář uchovávající konfigurace, RAG prompty, metaparametry, klasifikace, branding a loga jednotlivých klientů.
    - 📁 `default/` — Povinná podsložka výchozího tenanta s kompletními konfiguracemi sloužící jako záložní zdroj (fallback).
      - 📄 `branding.json` — Výchozí vizuální branding a barevná paleta.
      - 📄 `classification_config.json` — Výchozí kategorie dokumentů a ACL přístupové skupiny.
      - 📄 `logo.png` — Výchozí grafické logo.
      - 📄 `prompts.json` — Výchozí RAG systémové prompty (CZ a EN).
      - 📄 `search_config.json` — Výchozí metaparametry dělení textu a vyhledávání.
    - 📁 `dolphin/` — Podsložka pro tenanta Dolphin Consulting.
      - 📄 `branding.json` — Vizuální branding a barevná paleta Dolphin Consulting.
      - 📄 `classification_config.json` — Klasifikační kategorie a ACL skupiny Dolphin Consulting.
      - 📄 `logo.png` — Grafické logo Dolphin Consulting.
      - 📄 `prompts.json` — RAG systémové prompty pro Dolphin Consulting.
      - 📄 `search_config.json` — Metaparametry dělení textu a vyhledávání pro Dolphin Consulting.
    - 📁 `alzbeta/` — Podsložka pro tenanta Nemocnice sv. Alžběty na Slupi.
      - 📄 `branding.json` — Vizuální branding a barevná paleta Nemocnice sv. Alžběty.
      - 📄 `logo.png` — Grafické logo Nemocnice sv. Alžběty.
      - 📄 `prompts.json` — RAG systémové prompty a pravidla pro zdravotnické směrnice.
    - 📁 `jhu/` — Podsložka pro tenanta Jihočeská Univerzita v Českých Budějovicích.
      - 📄 `branding.json` — Vizuální branding a barevná paleta JČU.
      - 📄 `logo.webp` — Grafické logo JČU v WEBP formátu.
      - 📄 `prompts.json` — RAG systémové prompty a pravidla pro akademické směrnice.
    - 📁 `showcase/` — Podsložka pro ukázkového tenanta Showcase AI Search.
      - 📄 `.env.dev` — Konfigurační soubor proměnných prostředí pro DEV prostředí Showcase tenanta.
      - 📄 `.env.prod` — Konfigurační soubor proměnných prostředí pro PROD prostředí Showcase tenanta.
      - 📄 `branding.json` — Vizuální branding a barevné téma Showcase tenanta.
      - 📄 `classification_config.json` — Klasifikační kategorie a ACL skupiny Showcase tenanta.
      - 📄 `logo.png` — Grafické logo Showcase tenanta.
      - 📄 `prompts.json` — RAG systémové prompty pro Showcase tenanta.
      - 📄 `search_config.json` — Metaparametry dělení textu a vyhledávání pro Showcase tenanta.



## Doplnění v0.1.4

- `app/retrieval/keyword.py` — Sestavuje nativní SQL fulltext s bezpečnými parametry a oprávněními před top K.
- `tests/test_keyword_search.py` — Ověřuje fulltext SQL, chyby a izolované Azure české a ACL scénáře.
- `docs/tests_explained/test_keyword_search.md` — Vysvětluje ověření nové keyword větve a její skutečné Azure testování.
- `docs/adr/ADR-0028-native-keyword-and-jhu-ann-activation.md` — Popisuje nativní keyword větev a řízenou aktivaci ANN na JHU.
- `scratch/jhu_ann_release.py` — Provádí schválené fáze v0.1.4 na JHU se snapshoty, kontrolou cíle a bezpečným výstupem.
- `.local/deployments/jhu-ann-20261015/` — Uchovává ignorované nesekretní checkpointy a souhrn měření ANN pro tuto aktivaci.
