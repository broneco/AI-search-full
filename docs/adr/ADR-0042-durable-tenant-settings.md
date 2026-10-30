# ADR-0042: Trvalá tenantová nastavení oddělená od image

- Status: accepted
- Date: 2026-10-29
- Owners: AI Search

## Context

Účty, konverzace a dokumentové metadata již používají trvalé SQL. Správní prompty se však zapisovaly do souborů image; search/classification kombinovaly tyto soubory s Blob kopiemi a synchronní načítání se lišilo od async API. Výměna revize tak mohla ztratit nastavení nebo změnit jeho účinnou hodnotu.

## Decision

Cloudové `dev/prod` změny tří dokumentů (`prompts.json`, `search_config.json`, `classification_config.json`) ukládat do jedné tabulky `tenant_settings` stávající SQL databáze. Identitou je hash přesného tenantu + název dokumentu, s kontrolou uložené nezkrácené identity, JSON payloadem a interní revizí. Alias konfigurační složky nesmí spojovat SQL nastavení různých prostředí.

Bundled JSON zůstává celosouborovým výchozím nastavením pouze pro chybějící řádek. Nový release neseeduje a nepřepisuje existující nastavení. Chyba SQL nebo uloženého payloadu se nezaměňuje za chybějící override. Stejný resolver používají API, prompty, retrieval a ingestace. Lokální/testovací overlaye zůstávají zachované.

První převod vyžaduje guarded aditivní migraci a explicitní insert-only import všech zkontrolovaných současných dokumentů. Legacy Blob hodnoty se nevybírají automaticky; konflikt se soubory musí být vyřešen před releasem. Cloudový startup tabulku nevytváří.

## Options considered

Persistentní filesystem zachovává souborové zápisy, vyžaduje ale další mount/provozní závislost a neřeší rozdílné sync/async zdroje. Samotný Blob je již částečně implementovaný, avšak vyžadoval by nové synchronní čtení/cache a přesné tenantové klíče. Stávající SQL přirozeně sdílí životnost s účty a historií bez další služby.

## Consequences

Release může měnit výchozí soubory bez přepsání správních hodnot; uložení je potvrzené až po commitu a import nezničí novější nastavení. Přibývá krátké SQL čtení při načítání konfigurace. DB nedostupnost nyní nastavení explicitně znepřístupní. Zatím nepřidáváme cache, klientské CAS revize, historii nastavení, univerzální schema-migration framework ani automatickou obnovu záloh. Nové schéma nastavení vyžaduje explicitní kompatibilní migraci; uchování JSON samo nezaručuje kompatibilitu zásadně jiné verze.

## Implementation notes and follow-up

[Provozní pravidla, import a rollback](../development/non-destructive-updates.md). Rollback aplikace neodstraňuje SQL tabulku a stará verze SQL overrides nečte. JHU řízený převod s checkpointem, zachováním účtů/historie/korpusu a skutečným save/restart testem je [dokončený](../deployments/2026-10-29-durable-settings-rollout.md). Další prostředí potřebují vlastní migraci a akceptaci. Následujícím provozním krokem je izolovaný test obnovy zálohy.
