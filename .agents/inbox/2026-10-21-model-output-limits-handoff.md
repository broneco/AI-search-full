# Azure handoff: správcovské limity výstupu modelů

- Status: draft; cloudové zápisy nejsou v tomto úkolu schválené.
- Created: 2026-10-21
- Related ADR: [ADR-0037](../../docs/adr/ADR-0037-editable-model-output-limits.md)

## Konkrétní změna

Ve stávající ověřené Azure SQL vytvořit pouze `model_runtime_settings`: PK `(tenant_key,model_id)`, přesný tenant_id, nullable integer max_output_tokens, revision, updated_by, updated_at. Použije existující databázi, nevyžaduje nový prostředek, SKU, klíče, KV/RBAC změny ani kapacitu. Není třeba embeddingů, reindexace nebo přepnutí indexu.

## Ověření cíle a provedení

Operátor použije existující soukromé cloudové prostředí, ověří subscription/directory a přesný host/databázi/tenant. Žádné credentials nevkládat do tohoto souboru ani logů. Lokální `.env.local` není cloudové prostředí.

```powershell
.venv\Scripts\python.exe migrate_model_limits.py
# Až po schválení konkrétního vypsaného cíle:
.venv\Scripts\python.exe migrate_model_limits.py --apply --expect-host '<ověřený-host>' --expect-db '<ověřená-DB>' --expect-tenant '<přesný-tenant>'
```

Bez Apply se pouze vypíše cíl. S neshodným expected cílem se nic nevytvoří. Migrace je idempotentní create-only. Operátor potřebuje CREATE TABLE, backend SELECT/INSERT/UPDATE podle existujícího SQL zabezpečení. Případný chybějící grant provede oprávněný správce, nikoli automatická změna KV/RBAC.

Cloud startup novou tabulku nevytváří. Bez ní fungují původní limity; zápis vrací řízený požadavek migrace. Ostatní SQL chyby nejsou tichý fallback.

## Release, validace a rollback

Po schválení připrav běžný image-only backend release a admin SWA release podle README, s ověřenou předchozí image/revizí a buildem. Ostatní runtime nastavení neměnit. Ověř 403 pro ordinary user, Management uložení syntetické hodnoty, nový katalog/provider limit, konflikt staré revize 409 a návrat na výchozí hodnotu s rostoucí revizí. Stejné ID modelu/digestu a indexy/chunky zůstanou. Vyzkoušej lokální kontextový limit a řízenou chybu dlouhého vstupu bez truncation; nejde o výkonový benchmark.

Rollback vrátí předchozí image a admin build. Tabulku ponechá jako kompatibilní přídavek; nic nemaže. Předchozí runtime používá původní katalogové limity. Zdrojová publikace a skutečná Azure aktivace jsou samostatné autorizované akce.
