# ADR-0018: Sjednocená adresářová struktura `tenants/` a souborový fallback systém

* **Status:** Accepted
* **Datum:** 2026-09-30
* **Autor:** AI Search Implementation Team

---

## Kontext a Problém

V předchozích verzích byla tenant-specifická konfigurace roztroušena na několika místech:
- RAG prompty byly pevně zapsány ve slovníku v `app/core/prompts.py` a ukládány do `custom_prompts.json`.
- Metaparametry vyhledávání byly v `app/core/search_config.json`.
- Klasifikační pravidla byla v `app/core/classification_config.json`.
- Loga a branding byla uložena ve frontendových složkách `public/logos/` a `themes.ts`.

Tento stav ztěžoval přidávání nových klientů (tenantů) a způsoboval nekonzistenci při správě konfigurací a podkladů pro různé klienty.

---

## Rozhodnutí

Rozhodli jsme se sjednotit veškeré konfigurace tenantů do jediného kanonického místa v kořeni repozitáře v adresáři **`tenants/`**:

1. **Struktura složky `tenants/`:**
   Každý tenant má svou vlastní podsložku (`tenants/<tenant_id>/`), např. `tenants/dolphin/`, `tenants/alzbeta/`, `tenants/jhu/`.
   Složka `tenants/default/` je **povinný výchozí tenant**.

2. **Souborový fallback systém (`default`):**
   Vytvořili jsme modul `TenantConfigResolver` (`app/core/tenant_config.py`). Pokud pro daného tenanta chybí jakýkoliv konfigurační soubor (`prompts.json`, `search_config.json`, `classification_config.json`, `branding.json` nebo `logo.*`), systém automaticky načte **celý odpovídající soubor** ze složky `tenants/default/`.

3. **Souborové rozlišení:**
   Fallback funguje na úrovni celých souborů (file-level fallback).

---

## Důsledky

### Pozitivní
- **Přehlednost a modularita**: Přidání nového tenanta spočívá pouze ve vytvoření složky `tenants/<novy_tenant>/` a zadání rozdílových souborů.
- **Bezpečný fallback**: Pokud nový tenant nemá vlastní `search_config.json` nebo `classification_config.json`, aplikace bezchybně funguje s výchozí konfigurací z `tenants/default/`.
- **Kanonický zdroj pravdy**: AI agenti i vývojáři přesně vědí, kde hledat a upravovat tenant-specifická data.

### Rizika a mitigace
- Při úpravách konfigurace z Admin UI se úpravy ukládají do příslušné složky `tenants/<tenant_id>/<file>` a popřípadě synchronizují s Azure Blob Storage containerem.
