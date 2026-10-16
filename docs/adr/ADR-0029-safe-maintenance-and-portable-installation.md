# ADR-0029: Bezpečná údržba tenantů a přenositelné spuštění

- Status: accepted
- Date: 2026-10-15

## Kontext

Audit čistého exportu odhalil neomezenou reindexaci, mazání korpusu před validací vstupu, zkrácení tenantí identity, neúplný wheel, neveřejné předpoklady testů a frontend deployment vracející úspěch po selhání. Uživatel schválil opravu všech osmi nálezů; pro soukromé env stačí jeden vyplněný tenant.

## Rozhodnutí

- Přesná databázová/tokenová identita se nepřepisuje. Společný `tenant_config_name` mapuje pouze konfiguraci `ju → jhu`.
- Fast reindex vybírá pouze přesný ověřený tenant. Relační detekce taggeru neposílá cizí názvy do modelu; modelové UUID vztahů se ověřují proti povolené sadě.
- Full refresh sdílí službu API/CLI, validuje zdroje před zápisy a neprovádí počáteční bulk clear. Jednotlivý dokument se nahradí až po embeddingu. Po úplném úspěchu se odstraní jen původní nezměněné stale řádky; nové uploady jsou mimo tuto sadu a souběžná změna ruší cleanup. Vztahy se přesměrují na nová UUID a zůstávají uvnitř tenantu.
- CLI refresh vypisuje plán; Apply vyžaduje potvrzený tenant, v cloudu i host/DB. Při chybě explicitního zdroje nevybírá jinou složku. API plný refresh používá tenantí podadresář, neskenuje společný kořen.
- `ask.py` komunikuje přes autentizované HTTP API. Nespouští DB inicializaci a neobchází FastAPI dependencies.
- Frontend deployment je existing-resource plan/apply, ověřuje subscription/directory a nativní exit kódy, nemá hardcoded backend fallback a nevytváří SWA. Token se nevypisuje.
- `pyproject.toml` je zdroj Python závislostí; `requirements.txt` instaluje `.[dev]`. Wheel obsahuje všechny app moduly a veřejné sibling namespace resources `tenants`/`fixtures`; package-data je explicitní a env/klíče se vylučují.
- Běžné testy mají syntetickou jednotenantovou konfiguraci. Volitelná strukturální kontrola skutečných env přijme alespoň jeden nakonfigurovaný tenant, ignoruje placeholdery a nepotřebuje credentials na čistém klonu.
- Aktuální kontrakt a krátká paměť popisují skutečnou implementaci. Historické provozní poznámky jsou archiv, nikoli instrukce k opakování migrace.

## Důsledky a ověření

Refresh není atomická transakce celého korpusu: při pozdější chybě zůstanou dřívější úspěšné náhrady, ale nepromaže se zbytek. Tím se vyhneme držení všech embeddingů v paměti a dlouhé korpusové transakci na malé databázi. Před explicitním použitím širšího zdroje operátor zkontroluje plán a hranice zdrojové složky.

Regrese pokrývají dva tenanty, selhání modelu, prázdné/chybějící zdroje, stale cleanup, vztahy nových UUID, HTTP autorizaci CLI, PowerShell chyby a skutečný import wheelu mimo checkout včetně resource a vyloučení env.

Není to cloudový rollout ani akceptace ANN/performance. PostgreSQL, OCR, section_title v hlavní pipeline a Blob/lokální unifikace zůstávají odložené.
