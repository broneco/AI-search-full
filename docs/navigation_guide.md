# Průvodce navigací v repozitáři (`navigation_guide.md`)

Tento dokument poskytuje kompletní přehled a organizační strukturu celého repozitáře projektu **AI Search Full**. U každé složky i u každého zdrojového a konfiguračního souboru je uveden výstižný jednovětý popis vysvětlující jeho účel a roli v projektu. *(Podkladové PDF soubory uvnitř složky `data/` jsou spravovány hromadně na úrovni adresářů).*

> [!IMPORTANT]
> **Pravidlo pro vývoj a AI agenty:** Tento dokument představuje kanonický katalog struktury projektu. Příslušná pravidla v `.agents/AGENTS.md` a `.agents/rules/documentation-policy.md` stanovují povinnost aktualizovat tento soubor **při každém vytvoření nového souboru nebo složky** kdekoliv v repozitáři (s výjimkou vkládání podkladových PDF dokumentů do `data/`).

---

## 1. Kořenové soubory a skripty projektu (`/`)

Složky a konfigurační soubory umístěné v kořenovém adresáři repozitáře:

- 📁 [`.agents`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.agents) — Hlavní složka obsahující systém instrukcí, pravidel a paměti pro vývojové AI agenty.
- 📄 [`.dockerignore`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.dockerignore) — Konfigurační soubor definující ignorované soubory při sestavování Docker image.
- 📄 [`.env`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.env) — Soubor lokálních proměnných prostředí a konfigurace přístupů (neverzuje se).
- 📄 [`.env.dev`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.env.dev) — Šablona konfiguračních proměnných prostředí pro vývojové prostředí DEV.
- 📄 [`.env.example`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.env.example) — Vzorová šablona proměnných prostředí sloužící jako návod pro lokální nastavení.
- 📄 [`.env.prod`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.env.prod) — Šablona konfiguračních proměnných prostředí pro produkční prostředí PROD.
- 📁 [`.github`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.github) — Složka konfiguračních souborů a pracovních postupů pro GitHub.
- 📄 [`.gitignore`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.gitignore) — Konfigurační soubor určující, které soubory a složky má Git ignorovat.
- 📄 [`AGENTS.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\AGENTS.md) — Klíčový dokument definující provozní kontrakt, pravidla a role vývojových AI agentů v repozitáři.
- 📄 [`CHANGELOG.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\CHANGELOG.md) — Changelog projektových změn, nových funkcí a oprav chyb strukturovaný dle verzí.
- 📄 [`Dockerfile`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\Dockerfile) — Recept pro sestavení Docker kontejneru backendové FastAPI aplikace.
- 📄 [`README.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\README.md) — Hlavní úvodní dokumentace repozitáře popisující architekturu, spuštění a nasazení.
- 📁 [`ai_search_app.egg-info`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\ai_search_app.egg-info) — Složka s metadaty Python balíčku vygenerovaná při instalaci.
- 📁 [`app`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\app) — Hlavní složka zdrojového kódu backendové FastAPI aplikace.
- 📄 [`ask.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\ask.py) — Pomocný CLI skript pro rychlé testování dotazů vůči RAG vyhledávacímu backendu.
- 📄 [`check_diff.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\check_diff.py) — Pomocný skript pro porovnání změn a kontrolu konzistence kódu.
- 📁 [`data`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\data) — Složka podkladových zdrojových PDF dokumentů určených k indexaci.
- 📄 [`deploy_backend.ps1`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\deploy_backend.ps1) — PowerShell skript pro automatizované nasazení backendové aplikace do Azure Container Apps.
- 📄 [`deploy_frontend.ps1`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\deploy_frontend.ps1) — PowerShell skript pro automatizované nasazení frontendových aplikací do Azure Static Web Apps.
- 📄 [`docker-compose.yml`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docker-compose.yml) — Podkladový PDF dokument nemocniční směrnice určený k indexaci (docker-compose.yml).
- 📁 [`docs`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs) — Hlavní složka projektové dokumentace, architektonických rozhodnutí a návodů.
- 📁 [`frontend`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend) — Složka s podkladovými nemocničními směrnicemi a řády (frontend).
- 📁 [`frontend-admin`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-admin) — Složka zdrojového kódu administrační Next.js frontend aplikace.
- 📁 [`frontend-user`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-user) — Složka zdrojového kódu uživatelské Next.js frontend aplikace AI Vyhledávače.
- 📄 [`full_refresh_ingest.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\full_refresh_ingest.py) — Podkladový PDF dokument nemocniční směrnice určený k indexaci (full_refresh_ingest.py).
- 📁 [`infra`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\infra) — Složka infrastruktury jako kódu (IaC) obsahující Bicep šablony pro Azure.
- 📄 [`ingest.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\ingest.py) — Podkladový PDF dokument nemocniční směrnice určený k indexaci (ingest.py).
- 📄 [`ingest_documents.ps1`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\ingest_documents.ps1) — PowerShell skript pro spuštění indexace a vektorizace dokumentů pro zadaného klienta a prostředí.
- 📄 [`logo-dolphin-blue-background.jpg`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\logo-dolphin-blue-background.jpg) — Grafické logo společnosti Dolphin Consulting s modrým pozadím.
- 📄 [`logo-dolphin-symbol.png`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\logo-dolphin-symbol.png) — Grafická ikona symbolem delfína v transparentním PNG formátu.
- 📄 [`logo-nemocnice-alzbeta-2023.png`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\logo-nemocnice-alzbeta-2023.png) — Grafické logo Nemocnice sv. Alžběty v PNG formátu pro branding.
- 📄 [`pyproject.toml`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\pyproject.toml) — Konfigurační soubor projektu Python a nástroje pytest.
- 📄 [`requirements.txt`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\requirements.txt) — Seznam závislostí a knihoven Python potřebných pro chod backendové aplikace.
- 📁 [`tests`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\tests) — Složka automatizovaných unit a integračních testů (pytest).

---

## 2. Agentní systém a instrukce (`.agents/`)

Adresář uchovávající provozní pravidla, šablony, pracovní postupy a trvalou paměť pro vývojové AI agenty:

  - 📄 [`AGENTS.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.agents\AGENTS.md) — Hlavní provozní kontrakt a hierarchie pravidel pro AI agenty.
  - 📄 [`README.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.agents\README.md) — Úvodní popis struktury a použití složky .agents.
  - 📁 [`inbox`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.agents\inbox) — Složka obsahující instrukční soubory pro manuální úkony v Azure.
    - 📄 [`2026-06-08-dolphin-consulting-db-storage-handoff.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.agents\inbox\2026-06-08-dolphin-consulting-db-storage-handoff.md) — Handoff soubor s pokyny pro manuální nastavení Azure infrastruktury (2026-06-08-dolphin-consulting-db-storage-handoff.md).
    - 📄 [`azure-openai-handoff.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.agents\inbox\azure-openai-handoff.md) — Handoff soubor s pokyny pro manuální nastavení Azure infrastruktury (azure-openai-handoff.md).
    - 📄 [`azure-postgres-handoff.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.agents\inbox\azure-postgres-handoff.md) — Handoff soubor s pokyny pro manuální nastavení Azure infrastruktury (azure-postgres-handoff.md).
    - 📄 [`azure-storage-blob-setup-handoff.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.agents\inbox\azure-storage-blob-setup-handoff.md) — Handoff soubor s pokyny pro manuální nastavení Azure infrastruktury (azure-storage-blob-setup-handoff.md).
  - 📁 [`memory`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.agents\memory) — Složka uchovávající dlouhodobou paměť projektu, stav a architektonické úmluvy.
    - 📄 [`implementation-notes.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.agents\memory\implementation-notes.md) — Dokumentace trvalých poznámek k implementaci a technickým řešením.
    - 📄 [`open-questions.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.agents\memory\open-questions.md) — Přehled otevřených architektonických a vývojových otázek.
    - 📄 [`project-state.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.agents\memory\project-state.md) — Dokument zachycující aktuální stav projektu, fázi vývoje a nejbližší kroky.
    - 📄 [`style-decisions.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.agents\memory\style-decisions.md) — Záznam rozhodnutí o kódovacím stylu a konvencích projektu.
  - 📁 [`rules`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.agents\rules) — Složka s jednotlivými pravidly a politikami pro vývoj (bezpečnost, testování, architektura).
    - 📄 [`architecture-boundaries.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.agents\rules\architecture-boundaries.md) — Pravidla definující architektonické hranice a zakázané závislosti.
    - 📄 [`azure-deployment-handshake.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.agents\rules\azure-deployment-handshake.md) — Pravidla pro předávání manuálních Azure úkonů lidskému operátorovi.
    - 📄 [`coding-style.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.agents\rules\coding-style.md) — Pravidla pro kódovací styl, typové anotace a strukturu kódové báze.
    - 📄 [`documentation-policy.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.agents\rules\documentation-policy.md) — Pravidla pro vedení a povinnou aktualizaci projektové dokumentace.
    - 📄 [`iteration-policy.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.agents\rules\iteration-policy.md) — Pravidla pro postup v malých testovatelných a reverzibilních krocích.
    - 📄 [`retrieval-and-ai-policy.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.agents\rules\retrieval-and-ai-policy.md) — Pravidla pro implementaci RAG vyhledávání a AI orchestrace.
    - 📄 [`security-and-secrets.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.agents\rules\security-and-secrets.md) — Pravidla pro správu secrets, přístupových práv (ACL) a zabezpečení dat.
    - 📄 [`testing-policy.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.agents\rules\testing-policy.md) — Pravidla pro psaní a spouštění automatizovaných testů.
  - 📁 [`templates`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.agents\templates) — Složka obsahující šablony pro ADR, úkoly a Azure handoff dokumenty.
    - 📄 [`adr-template.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.agents\templates\adr-template.md) — Šablona pro vytváření nových architektonických rozhodnutí (ADR).
    - 📄 [`azure-deployment-handoff-template.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.agents\templates\azure-deployment-handoff-template.md) — Šablona pro vytváření předávacích protokolů Azure úkonů.
    - 📄 [`task-slice-template.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.agents\templates\task-slice-template.md) — Šablona pro specifikaci dílčího vývojového úkolu.
  - 📁 [`workflows`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.agents\workflows) — Složka obsahující postupy a pracovní návody pro opakované vývojářské činnosti.
    - 📄 [`azure-manual-deploy.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.agents\workflows\azure-manual-deploy.md) — Pracovní postup pro manuální nasazování Azure zdrojů.
    - 📄 [`documentation-update.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.agents\workflows\documentation-update.md) — Pracovní postup pro aktualizaci projektové dokumentace.
    - 📄 [`implement-slice.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.agents\workflows\implement-slice.md) — Pracovní postup pro implementaci vývojového kroku.
    - 📄 [`resume-after-handoff.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.agents\workflows\resume-after-handoff.md) — Pracovní postup pro pokračování práce po dokončení Azure úkonu.
    - 📄 [`write-adr.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.agents\workflows\write-adr.md) — Pracovní postup pro sepsání nového architektonického rozhodnutí.

---

## 3. GitHub CI/CD a automatizace (`.github/`)

Konfigurace GitHub Actions pro automatické sestavení a nasazování:

  - 📁 [`workflows`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.github\workflows) — Složka definující automatizované GitHub Actions workflows.
    - 📄 [`azure-static-web-apps-calm-sea-05badcc03.yml`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\.github\workflows\azure-static-web-apps-calm-sea-05badcc03.yml) — GitHub Actions workflow soubor pro automatické nasazení na Azure (azure-static-web-apps-calm-sea-05badcc03.yml).

---

## 4. Backendová aplikace Python & FastAPI (`app/`)

Zdrojový kód backendové REST API aplikace, RAG vyhledávače, vyhledávací logiky a databázových modelů:

  - 📁 [`api`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\app\api) — Složka obsahující API rozhraní, routy a závislosti.
    - 📄 [`dependencies.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\app\api\dependencies.py) — Modul závislostí FastAPI (získání databázových relací, ověření tokenů a tenantů).
    - 📁 [`routes`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\app\api\routes) — Složka s definicemi jednotlivých koncových bodů (endpoints) API.
      - 📄 [`auth.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\app\api\routes\auth.py) — API endpointy pro autentizaci uživatelů, přihlášení a registrace.
      - 📄 [`chat.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\app\api\routes\chat.py) — API endpointy pro RAG vyhledávání, chatové dotazy a generování odpovídajících citací.
      - 📄 [`documents.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\app\api\routes\documents.py) — API endpointy pro správu, nahrávání a mazání dokumentů.
      - 📄 [`health.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\app\api\routes\health.py) — API endpointy pro kontrolu stavu a zdraví aplikace (liveness/readiness).
      - 📄 [`threads.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\app\api\routes\threads.py) — API endpointy pro správu konverzčních vláken a historie rozhovorů.
  - 📁 [`core`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\app\core) — Složka s jádrem konfigurace, nastavením vyhledávání a klasifikací dokumentů.
    - 📄 [`classification_config.json`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\app\core\classification_config.json) — Konfigurační soubor definující kategorie dokumentů a jejich přístupová práva (ACL).
    - 📄 [`config.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\app\core\config.py) — Hlavní modul proměnných prostředí a nastavení aplikace pomocí Pydantic BaseSettings.
    - 📄 [`search_config.json`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\app\core\search_config.json) — Konfigurační soubor parametrů vyhledávání (RRF váhy, limity, práhy skóre).
    - 📄 [`search_config.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\app\core\search_config.py) — Modul pro načítání a práci s konfigurací vyhledávání.
  - 📁 [`ingestion`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\app\ingestion) — Složka modulů pro zpracování, dělení a indexaci dokumentů.
    - 📄 [`chunking.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\app\ingestion\chunking.py) — Modul pro dělení textu dokumentů na kontextové pasáže (chunks).
    - 📄 [`extraction.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\app\ingestion\extraction.py) — Modul pro extrakci textu z PDF dokumentů strana po straně.
    - 📁 [`loaders`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\app\ingestion\loaders) — Složka loaderů pro načítání dokumentů z různých zdrojů.
      - 📄 [`local.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\app\ingestion\loaders\local.py) — Loader pro načítání a procházení dokumentů z lokálního souborového systému.
    - 📄 [`pipeline.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\app\ingestion\pipeline.py) — Řídicí pipeline pro kompletní proces zpracování a uložení dokumentu.
    - 📄 [`tagger.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\app\ingestion\tagger.py) — Modul pro automatickou klasifikaci a tagování metadat dokumentů.
  - 📄 [`main.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\app\main.py) — Vstupní bod FastAPI aplikace inicializující routy, CORS a middleware.
  - 📁 [`providers`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\app\providers) — Složka s poskytovateli služeb (Azure OpenAI, Blob Storage, LLM rozhraní).
    - 📄 [`azure_openai.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\app\providers\azure_openai.py) — Poskytovatel rozhraní pro Azure OpenAI modely a klienty.
    - 📄 [`blob_storage.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\app\providers\blob_storage.py) — Poskytovatel pro práci s Azure Blob Storage úložistěm.
    - 📄 [`embeddings.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\app\providers\embeddings.py) — Modul pro generování vektorových embeddingů pomocí Azure OpenAI.
    - 📄 [`llm.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\app\providers\llm.py) — Modul pro generování textových odpovědí LLM modelu.
  - 📁 [`retrieval`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\app\retrieval) — Složka vyhledávacích modulů pro vektorové i klíčové vyhledávání.
    - 📄 [`base.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\app\retrieval\base.py) — Abstraktní základní třída a rozhraní vyhledávače (VectorRetriever base).
    - 📄 [`vector.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\app\retrieval\vector.py) — Implementace hybridního vyhledávání (pgvector + full-text RRF fúze).
  - 📁 [`schemas`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\app\schemas) — Složka Pydantic schémat pro validaci vstupních a výstupních dat API.
    - 📄 [`chat.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\app\schemas\chat.py) — Pydantic schémata pro chatové dotazy, odpovědi a citace.
    - 📄 [`documents.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\app\schemas\documents.py) — Pydantic schémata pro dokumenty, pasáže a metadata.
  - 📁 [`storage`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\app\storage) — Složka pro práci s databází PostgreSQL a ORM modely.
    - 📄 [`db.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\app\storage\db.py) — Modul pro inicializaci SQLAlchemy databázového připojení a relací.
    - 📄 [`models.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\app\storage\models.py) — SQLAlchemy ORM modely reprezentující tabulky dokumentů, pasáží a uživatelů.

---

## 5. Uživatelská Frontend Aplikace (`frontend-user/`)

Webová aplikace Next.js pro koncového uživatele poskytující vyhledávací konzoli, chat a prohlížeč PDF citací:

  - 📄 [`.env.development`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-user\.env.development) — Konfigurační soubor uživatelského frontendu (.env.development).
  - 📄 [`.env.production`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-user\.env.production) — Konfigurační soubor uživatelského frontendu (.env.production).
  - 📁 [`app`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-user\app) — Adresář app v aplikaci uživatelského frontendu.
    - 📁 [`components`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-user\app\components) — Adresář components v aplikaci uživatelského frontendu.
      - 📄 [`AuthModal.tsx`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-user\app\components\AuthModal.tsx) — Zdrojový soubor komponenty nebo stránky uživatelského frontendu (AuthModal.tsx).
      - 📄 [`PdfViewerModal.tsx`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-user\app\components\PdfViewerModal.tsx) — Zdrojový soubor komponenty nebo stránky uživatelského frontendu (PdfViewerModal.tsx).
      - 📄 [`ThreadSidebar.tsx`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-user\app\components\ThreadSidebar.tsx) — Zdrojový soubor komponenty nebo stránky uživatelského frontendu (ThreadSidebar.tsx).
    - 📁 [`config`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-user\app\config) — Adresář config v aplikaci uživatelského frontendu.
      - 📄 [`themes.ts`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-user\app\config\themes.ts) — Zdrojový soubor komponenty nebo stránky uživatelského frontendu (themes.ts).
    - 📄 [`globals.css`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-user\app\globals.css) — Zdrojový soubor komponenty nebo stránky uživatelského frontendu (globals.css).
    - 📄 [`layout.tsx`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-user\app\layout.tsx) — Zdrojový soubor komponenty nebo stránky uživatelského frontendu (layout.tsx).
    - 📄 [`page.tsx`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-user\app\page.tsx) — Zdrojový soubor komponenty nebo stránky uživatelského frontendu (page.tsx).
    - 📄 [`translations.ts`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-user\app\translations.ts) — Zdrojový soubor komponenty nebo stránky uživatelského frontendu (translations.ts).
  - 📄 [`next-env.d.ts`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-user\next-env.d.ts) — Konfigurační soubor uživatelského frontendu (next-env.d.ts).
  - 📄 [`next.config.ts`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-user\next.config.ts) — Konfigurační soubor uživatelského frontendu (next.config.ts).
  - 📄 [`package-lock.json`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-user\package-lock.json) — Konfigurační soubor uživatelského frontendu (package-lock.json).
  - 📄 [`package.json`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-user\package.json) — Konfigurační soubor uživatelského frontendu (package.json).
  - 📄 [`postcss.config.mjs`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-user\postcss.config.mjs) — Konfigurační soubor uživatelského frontendu (postcss.config.mjs).
  - 📁 [`public`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-user\public) — Statický veřejný soubor nebo logo uživatelského frontendu (public).
    - 📁 [`logos`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-user\public\logos) — Statický veřejný soubor nebo logo uživatelského frontendu (logos).
      - 📄 [`logo-dolphin-blue-background.jpg`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-user\public\logos\logo-dolphin-blue-background.jpg) — Statický veřejný soubor nebo logo uživatelského frontendu (logo-dolphin-blue-background.jpg).
      - 📄 [`logo-dolphin-symbol.png`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-user\public\logos\logo-dolphin-symbol.png) — Statický veřejný soubor nebo logo uživatelského frontendu (logo-dolphin-symbol.png).
      - 📄 [`logo-nemocnice-alzbeta-2023.png`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-user\public\logos\logo-nemocnice-alzbeta-2023.png) — Statický veřejný soubor nebo logo uživatelského frontendu (logo-nemocnice-alzbeta-2023.png).
  - 📄 [`tsconfig.json`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-user\tsconfig.json) — Konfigurační soubor uživatelského frontendu (tsconfig.json).

---

## 6. Administrační Frontend Aplikace (`frontend-admin/`)

Webová aplikace Next.js pro administrátory určena pro správu dokumentů, re-indexaci a konfiguraci vyhledávače:

  - 📄 [`.env.development`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-admin\.env.development) — Konfigurační soubor administračního frontendu (.env.development).
  - 📄 [`.env.production`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-admin\.env.production) — Konfigurační soubor administračního frontendu (.env.production).
  - 📄 [`.gitignore`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-admin\.gitignore) — Konfigurační soubor administračního frontendu (.gitignore).
  - 📄 [`AGENTS.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-admin\AGENTS.md) — Konfigurační soubor administračního frontendu (AGENTS.md).
  - 📄 [`CLAUDE.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-admin\CLAUDE.md) — Konfigurační soubor administračního frontendu (CLAUDE.md).
  - 📄 [`README.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-admin\README.md) — Konfigurační soubor administračního frontendu (README.md).
  - 📁 [`app`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-admin\app) — Adresář app v aplikaci administračního frontendu.
    - 📁 [`components`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-admin\app\components) — Adresář components v aplikaci administračního frontendu.
      - 📄 [`AuthModal.tsx`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-admin\app\components\AuthModal.tsx) — Zdrojový soubor komponenty nebo stránky administračního frontendu (AuthModal.tsx).
    - 📁 [`config`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-admin\app\config) — Adresář config v aplikaci administračního frontendu.
      - 📄 [`themes.ts`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-admin\app\config\themes.ts) — Zdrojový soubor komponenty nebo stránky administračního frontendu (themes.ts).
    - 📄 [`favicon.ico`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-admin\app\favicon.ico) — Zdrojový soubor komponenty nebo stránky administračního frontendu (favicon.ico).
    - 📄 [`globals.css`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-admin\app\globals.css) — Zdrojový soubor komponenty nebo stránky administračního frontendu (globals.css).
    - 📄 [`layout.tsx`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-admin\app\layout.tsx) — Zdrojový soubor komponenty nebo stránky administračního frontendu (layout.tsx).
    - 📄 [`page.tsx`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-admin\app\page.tsx) — Zdrojový soubor komponenty nebo stránky administračního frontendu (page.tsx).
    - 📄 [`translations.ts`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-admin\app\translations.ts) — Zdrojový soubor komponenty nebo stránky administračního frontendu (translations.ts).
  - 📄 [`eslint.config.mjs`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-admin\eslint.config.mjs) — Konfigurační soubor administračního frontendu (eslint.config.mjs).
  - 📄 [`next-env.d.ts`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-admin\next-env.d.ts) — Konfigurační soubor administračního frontendu (next-env.d.ts).
  - 📄 [`next.config.ts`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-admin\next.config.ts) — Konfigurační soubor administračního frontendu (next.config.ts).
  - 📄 [`package-lock.json`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-admin\package-lock.json) — Konfigurační soubor administračního frontendu (package-lock.json).
  - 📄 [`package.json`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-admin\package.json) — Konfigurační soubor administračního frontendu (package.json).
  - 📄 [`postcss.config.mjs`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-admin\postcss.config.mjs) — Konfigurační soubor administračního frontendu (postcss.config.mjs).
  - 📁 [`public`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-admin\public) — Statický veřejný soubor administračního frontendu (public).
    - 📄 [`file.svg`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-admin\public\file.svg) — Statický veřejný soubor administračního frontendu (file.svg).
    - 📄 [`globe.svg`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-admin\public\globe.svg) — Statický veřejný soubor administračního frontendu (globe.svg).
    - 📁 [`logos`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-admin\public\logos) — Statický veřejný soubor administračního frontendu (logos).
      - 📄 [`logo-dolphin-blue-background.jpg`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-admin\public\logos\logo-dolphin-blue-background.jpg) — Statický veřejný soubor administračního frontendu (logo-dolphin-blue-background.jpg).
      - 📄 [`logo-dolphin-symbol.png`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-admin\public\logos\logo-dolphin-symbol.png) — Statický veřejný soubor administračního frontendu (logo-dolphin-symbol.png).
      - 📄 [`logo-nemocnice-alzbeta-2023.png`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-admin\public\logos\logo-nemocnice-alzbeta-2023.png) — Statický veřejný soubor administračního frontendu (logo-nemocnice-alzbeta-2023.png).
    - 📄 [`next.svg`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-admin\public\next.svg) — Statický veřejný soubor administračního frontendu (next.svg).
    - 📄 [`vercel.svg`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-admin\public\vercel.svg) — Statický veřejný soubor administračního frontendu (vercel.svg).
    - 📄 [`window.svg`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-admin\public\window.svg) — Statický veřejný soubor administračního frontendu (window.svg).
  - 📄 [`tsconfig.json`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-admin\tsconfig.json) — Konfigurační soubor administračního frontendu (tsconfig.json).
  - 📄 [`tsconfig.tsbuildinfo`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend-admin\tsconfig.tsbuildinfo) — Konfigurační soubor administračního frontendu (tsconfig.tsbuildinfo).

---

## 7. Infrastruktura jako kód / IaC Bicep (`infra/`)

Azure Bicep šablony a skripty pro kompletní automatické zřízení cloudové infrastruktury:

  - 📄 [`README.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\infra\README.md) — Soubor infrastruktury Azure Bicep (README.md).
  - 📄 [`deploy_infra.ps1`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\infra\deploy_infra.ps1) — Soubor infrastruktury Azure Bicep (deploy_infra.ps1).
  - 📄 [`main.bicep`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\infra\main.bicep) — Soubor infrastruktury Azure Bicep (main.bicep).
  - 📄 [`main.bicepparam`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\infra\main.bicepparam) — Soubor infrastruktury Azure Bicep (main.bicepparam).
  - 📄 [`main.json`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\infra\main.json) — Soubor infrastruktury Azure Bicep (main.json).
  - 📁 [`modules`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\infra\modules) — Složka s Bicep moduly pro jednotlivé Azure zdroje (Postgres, Storage, ACA, OpenAI).
    - 📄 [`acr.bicep`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\infra\modules\acr.bicep) — Bicep modul pro nasazení Azure zdroje (acr.bicep).
    - 📄 [`containerapp.bicep`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\infra\modules\containerapp.bicep) — Bicep modul pro nasazení Azure zdroje (containerapp.bicep).
    - 📄 [`log_analytics.bicep`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\infra\modules\log_analytics.bicep) — Bicep modul pro nasazení Azure zdroje (log_analytics.bicep).
    - 📄 [`openai.bicep`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\infra\modules\openai.bicep) — Bicep modul pro nasazení Azure zdroje (openai.bicep).
    - 📄 [`postgres.bicep`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\infra\modules\postgres.bicep) — Bicep modul pro nasazení Azure zdroje (postgres.bicep).
    - 📄 [`staticwebapp.bicep`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\infra\modules\staticwebapp.bicep) — Bicep modul pro nasazení Azure zdroje (staticwebapp.bicep).
    - 📄 [`storage.bicep`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\infra\modules\storage.bicep) — Bicep modul pro nasazení Azure zdroje (storage.bicep).

---

## 8. Projektová dokumentace a ADR (`docs/`)

Detailní architektonická rozhodnutí (ADR), návody k nasazení, designové dokumenty a vysvětlení testů:

  - 📁 [`adr`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\adr) — Složka obsahující záznamy architektonických rozhodnutí (Architectural Decision Records).
    - 📄 [`ADR-0001-template.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\adr\ADR-0001-template.md) — Indexový a šablonový dokument pro vedení architektonických rozhodnutí.
    - 📄 [`ADR-0002-use-postgresql-pgvector-for-mvp.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\adr\ADR-0002-use-postgresql-pgvector-for-mvp.md) — Záznam architektonického rozhodnutí: ADR-0002-use-postgresql-pgvector-for-mvp.md.
    - 📄 [`ADR-0003-ingestion-pipeline.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\adr\ADR-0003-ingestion-pipeline.md) — Záznam architektonického rozhodnutí: ADR-0003-ingestion-pipeline.md.
    - 📄 [`ADR-0004-nextjs-frontend-framework.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\adr\ADR-0004-nextjs-frontend-framework.md) — Záznam architektonického rozhodnutí: ADR-0004-nextjs-frontend-framework.md.
    - 📄 [`ADR-0005-weighted-rrf-hybrid-retrieval.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\adr\ADR-0005-weighted-rrf-hybrid-retrieval.md) — Záznam architektonického rozhodnutí: ADR-0005-weighted-rrf-hybrid-retrieval.md.
    - 📄 [`ADR-0006-custom-hybrid-retrieval-vs-langchain.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\adr\ADR-0006-custom-hybrid-retrieval-vs-langchain.md) — Záznam architektonického rozhodnutí: ADR-0006-custom-hybrid-retrieval-vs-langchain.md.
    - 📄 [`ADR-0007-azure-blob-storage-for-document-hosting.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\adr\ADR-0007-azure-blob-storage-for-document-hosting.md) — Záznam architektonického rozhodnutí: ADR-0007-azure-blob-storage-for-document-hosting.md.
    - 📄 [`ADR-0008-dynamic-pdf-annotations-highlighting.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\adr\ADR-0008-dynamic-pdf-annotations-highlighting.md) — Záznam architektonického rozhodnutí: ADR-0008-dynamic-pdf-annotations-highlighting.md.
    - 📄 [`ADR-0009-automatic-tagging-metadata-and-archival-system.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\adr\ADR-0009-automatic-tagging-metadata-and-archival-system.md) — Záznam architektonického rozhodnutí: ADR-0009-automatic-tagging-metadata-and-archival-system.md.
    - 📄 [`ADR-0010-persistent-dynamic-classification-configuration-and-universal-ids.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\adr\ADR-0010-persistent-dynamic-classification-configuration-and-universal-ids.md) — Záznam architektonického rozhodnutí: ADR-0010-persistent-dynamic-classification-configuration-and-universal-ids.md.
    - 📄 [`ADR-0011-subfolder-data-source-ingestion-and-filtering.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\adr\ADR-0011-subfolder-data-source-ingestion-and-filtering.md) — Záznam architektonického rozhodnutí: ADR-0011-subfolder-data-source-ingestion-and-filtering.md.
    - 📄 [`ADR-0012-customizable-search-retrieval-parameters.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\adr\ADR-0012-customizable-search-retrieval-parameters.md) — Záznam architektonického rozhodnutí: ADR-0012-customizable-search-retrieval-parameters.md.
    - 📄 [`ADR-0013-hybrid-search-fusion-strategies.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\adr\ADR-0013-hybrid-search-fusion-strategies.md) — Záznam architektonického rozhodnutí: ADR-0013-hybrid-search-fusion-strategies.md.
    - 📄 [`ADR-0014-context-expansion-strategies.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\adr\ADR-0014-context-expansion-strategies.md) — Záznam architektonického rozhodnutí: ADR-0014-context-expansion-strategies.md.
    - 📄 [`ADR-0015-multi-environment-dev-prod-architecture.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\adr\ADR-0015-multi-environment-dev-prod-architecture.md) — Záznam architektonického rozhodnutí: ADR-0015-multi-environment-dev-prod-architecture.md.
  - 📁 [`deployments`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\deployments) — Složka s návody a prameny pro nasazení do Azure cloudu.
    - 📄 [`azure_bicep_provisioning_guide.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\deployments\azure_bicep_provisioning_guide.md) — Dokumentace a návod k nasazení: azure_bicep_provisioning_guide.md.
    - 📄 [`cloud_deployment_guide.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\deployments\cloud_deployment_guide.md) — Dokumentace a návod k nasazení: cloud_deployment_guide.md.
  - 📁 [`design`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\design) — Složka s podrobnými návrhy architektury, multi-tenancy a frontendu.
    - 📄 [`database_schema.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\design\database_schema.md) — Architektonický návrhový dokument: database_schema.md.
    - 📄 [`environments_and_tenancy.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\design\environments_and_tenancy.md) — Architektonický návrhový dokument: environments_and_tenancy.md.
    - 📄 [`frontend_architecture.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\design\frontend_architecture.md) — Architektonický návrhový dokument: frontend_architecture.md.
    - 📄 [`hybrid_search.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\design\hybrid_search.md) — Architektonický návrhový dokument: hybrid_search.md.
    - 📄 [`metadata_tagging_system.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\design\metadata_tagging_system.md) — Architektonický návrhový dokument: metadata_tagging_system.md.
  - 📄 [`initial_design_doc.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\initial_design_doc.md) — Podkladový PDF dokument nemocniční směrnice určený k indexaci (initial_design_doc.md).
  - 📁 [`runbooks`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\runbooks) — Složka s podkladovými nemocničními směrnicemi a řády (runbooks).
    - 📄 [`azure-first-deployment.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\runbooks\azure-first-deployment.md) — Podkladový PDF dokument nemocniční směrnice určený k indexaci (azure-first-deployment.md).
  - 📁 [`tests_explained`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\tests_explained) — Složka s detailním vysvětlením jednotlivých testů pro vývojáře.
    - 📄 [`test_health.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\tests_explained\test_health.md) — Dokumentace s vysvětlením testovacího modulu test_health.md.
    - 📄 [`test_hybrid_retrieval.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\tests_explained\test_hybrid_retrieval.md) — Dokumentace s vysvětlením testovacího modulu test_hybrid_retrieval.md.
    - 📄 [`test_ingestion.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\tests_explained\test_ingestion.md) — Dokumentace s vysvětlením testovacího modulu test_ingestion.md.
    - 📄 [`test_metadata_tagging.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\tests_explained\test_metadata_tagging.md) — Dokumentace s vysvětlením testovacího modulu test_metadata_tagging.md.
    - 📄 [`test_multi_tenant_auth.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\tests_explained\test_multi_tenant_auth.md) — Dokumentace s vysvětlením testovacího modulu test_multi_tenant_auth.md.
    - 📄 [`test_pdf_annotations.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\tests_explained\test_pdf_annotations.md) — Dokumentace s vysvětlením testovacího modulu test_pdf_annotations.md.
    - 📄 [`test_rag_pipeline.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\tests_explained\test_rag_pipeline.md) — Dokumentace s vysvětlením testovacího modulu test_rag_pipeline.md.
    - 📄 [`test_rechunk.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\tests_explained\test_rechunk.md) — Dokumentace s vysvětlením testovacího modulu test_rechunk.md.
    - 📄 [`test_search_config.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\tests_explained\test_search_config.md) — Dokumentace s vysvětlením testovacího modulu test_search_config.md.
    - 📄 [`test_security_freshness.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\tests_explained\test_security_freshness.md) — Dokumentace s vysvětlením testovacího modulu test_security_freshness.md.
    - 📄 [`test_security_prefilter.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\tests_explained\test_security_prefilter.md) — Dokumentace s vysvětlením testovacího modulu test_security_prefilter.md.
    - 📄 [`test_vector_db.md`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\docs\tests_explained\test_vector_db.md) — Dokumentace s vysvětlením testovacího modulu test_vector_db.md.

---

## 9. Automatizované Testy (`tests/`)

Sada pytest unit a integračních testů ověřujících RAG vyhledávání, ACL bezpečnost, dělení textu a databázi:

  - 📄 [`conftest.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\tests\conftest.py) — Testovací modul pytest ověřující funkčnost conftest.py.
  - 📄 [`test_health.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\tests\test_health.py) — Testovací modul pytest ověřující funkčnost test_health.py.
  - 📄 [`test_hybrid_retrieval.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\tests\test_hybrid_retrieval.py) — Testovací modul pytest ověřující funkčnost test_hybrid_retrieval.py.
  - 📄 [`test_ingestion.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\tests\test_ingestion.py) — Testovací modul pytest ověřující funkčnost test_ingestion.py.
  - 📄 [`test_metadata_tagging.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\tests\test_metadata_tagging.py) — Testovací modul pytest ověřující funkčnost test_metadata_tagging.py.
  - 📄 [`test_multi_tenant_auth.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\tests\test_multi_tenant_auth.py) — Testovací modul pytest ověřující funkčnost test_multi_tenant_auth.py.
  - 📄 [`test_pdf_annotations.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\tests\test_pdf_annotations.py) — Testovací modul pytest ověřující funkčnost test_pdf_annotations.py.
  - 📄 [`test_rag_pipeline.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\tests\test_rag_pipeline.py) — Testovací modul pytest ověřující funkčnost test_rag_pipeline.py.
  - 📄 [`test_rechunk.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\tests\test_rechunk.py) — Testovací modul pytest ověřující funkčnost test_rechunk.py.
  - 📄 [`test_search_config.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\tests\test_search_config.py) — Testovací modul pytest ověřující funkčnost test_search_config.py.
  - 📄 [`test_security_freshness.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\tests\test_security_freshness.py) — Testovací modul pytest ověřující funkčnost test_security_freshness.py.
  - 📄 [`test_security_prefilter.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\tests\test_security_prefilter.py) — Testovací modul pytest ověřující funkčnost test_security_prefilter.py.
  - 📄 [`test_vector_db.py`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\tests\test_vector_db.py) — Testovací modul pytest ověřující funkčnost test_vector_db.py.

---

## 10. Metadatový balíček Python (`ai_search_app.egg-info/`)

Vygenerovaná metadata při vývoji a instalaci balíčku aplikace:

  - 📄 [`PKG-INFO`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\ai_search_app.egg-info\PKG-INFO) — Metadatový soubor Python balíčku PKG-INFO.
  - 📄 [`SOURCES.txt`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\ai_search_app.egg-info\SOURCES.txt) — Metadatový soubor Python balíčku SOURCES.txt.
  - 📄 [`dependency_links.txt`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\ai_search_app.egg-info\dependency_links.txt) — Metadatový soubor Python balíčku dependency_links.txt.
  - 📄 [`requires.txt`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\ai_search_app.egg-info\requires.txt) — Metadatový soubor Python balíčku requires.txt.
  - 📄 [`top_level.txt`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\ai_search_app.egg-info\top_level.txt) — Metadatový soubor Python balíčku top_level.txt.

---

## 11. Podkladové PDF dokumenty pro indexaci (`data/`)

Adresářová struktura obsahující složky s podkladovými nemocničními směrnicemi, řády a operačními postupy:

- 📁 [`data`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\data) — Složka podkladových zdrojových PDF dokumentů určených k indexaci.
  - 📁 [`1. ŘÍDÍCÍ DOKUMENT 0 + TP`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\data\1. ŘÍDÍCÍ DOKUMENT 0 + TP) — Složka s podkladovými nemocničními směrnicemi a řády (1. ŘÍDÍCÍ DOKUMENT 0 + TP).
  - 📁 [`2. METODICKÉ POKYNY`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\data\2. METODICKÉ POKYNY) — Složka s podkladovými nemocničními směrnicemi a řády (2. METODICKÉ POKYNY).
  - 📁 [`3. ŘÁDY`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\data\3. ŘÁDY) — Složka s podkladovými nemocničními směrnicemi a řády (3. ŘÁDY).
  - 📁 [`4. PŘÍKAZ NADŘÍZENÉHO`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\data\4. PŘÍKAZ NADŘÍZENÉHO) — Složka s podkladovými nemocničními směrnicemi a řády (4. PŘÍKAZ NADŘÍZENÉHO).
  - 📁 [`5. SMĚRNICE`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\data\5. SMĚRNICE) — Složka s podkladovými nemocničními směrnicemi a řády (5. SMĚRNICE).
    - 📁 [`SMĚRNICE EKONOMICKÉ`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\data\5. SMĚRNICE\SMĚRNICE EKONOMICKÉ) — Složka s podkladovými nemocničními směrnicemi a řády (SMĚRNICE EKONOMICKÉ).
    - 📁 [`SMĚRNICE PERSONÁLNÍ`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\data\5. SMĚRNICE\SMĚRNICE PERSONÁLNÍ) — Složka s podkladovými nemocničními směrnicemi a řády (SMĚRNICE PERSONÁLNÍ).
    - 📁 [`SMĚRNICE TECHNICKÉ, IT`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\data\5. SMĚRNICE\SMĚRNICE TECHNICKÉ, IT) — Složka s podkladovými nemocničními směrnicemi a řády (SMĚRNICE TECHNICKÉ, IT).
    - 📁 [`SMĚRNICE ZDRAVOTNÍ`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\data\5. SMĚRNICE\SMĚRNICE ZDRAVOTNÍ) — Složka s podkladovými nemocničními směrnicemi a řády (SMĚRNICE ZDRAVOTNÍ).
    - 📁 [`SMĚRNICE ŘÍZENÍ`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\data\5. SMĚRNICE\SMĚRNICE ŘÍZENÍ) — Složka s podkladovými nemocničními směrnicemi a řády (SMĚRNICE ŘÍZENÍ).
  - 📁 [`6. SOP`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\data\6. SOP) — Složka s podkladovými nemocničními směrnicemi a řády (6. SOP).
  - 📁 [`7.DPL`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\data\7.DPL) — Složka s podkladovými nemocničními směrnicemi a řády (7.DPL).
  - 📁 [`temp_drafts`](file:///C:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\data\temp_drafts) — Složka s podkladovými nemocničními směrnicemi a řády (temp_drafts).

