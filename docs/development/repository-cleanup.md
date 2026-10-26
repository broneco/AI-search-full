# Inventura a úklid repozitáře — 2026-10-15

Úklid navazuje na vydané v0.1.4; jde o samostatnou údržbu pracovního stromu, nikoli nové nasazení nebo změnu vyhledávání. Z kořene zůstává README, CLI, agentový vstup a soubory nutné pro Python/Docker. Aktuální návody jsou v [README](../../README.md).

Následující inventura zachycuje první úklid. Navazující audit přenositelnosti a opravy shrnuje [ADR-0029](../adr/ADR-0029-safe-maintenance-and-portable-installation.md); novější výsledky jsou v [changelogu](../CHANGELOG.md). Full refresh již nepředmazává korpus a frontend deployment má výchozí čtecí plán. Starší počty souborů/testů níže nejsou závěrečnou verifikací těchto oprav.

Původní úplný veřejný export měl **304 souborů**. Následný požadavek omezil předávací ZIP na **JHU, 282 souborů**: pouze `tenants/jhu`, kompletní konfigurace bez default složky a jediný JHU motiv/logo obou frontendů. Neobsahuje Git historii, soukromé env, data ani závislosti. Offline sada nad JHU exportem včetně balíčku prošla (**261 passed / 85 skipped**), stejně jako TypeScript obou frontendů. Ostatní tenanty v původním repozitáři zůstávají zachované. ZIP je pracovní artefakt v ignorované `.local/hardening-20261015/source-export.zip`, nevkládat jej zpět do zdrojového Gitu.

## Přesunuté soubory

| Původně | Nyní | Důvod |
|---|---|---|
| `CHANGELOG.md` | `docs/CHANGELOG.md` | Historie patří k ostatní dokumentaci; upravené odkazy a agentová pravidla |
| `docker-compose.yml` | `infra/legacy/docker-compose.postgres.yml` | Starý PostgreSQL setup není současné lokální prostředí; aktuální je kořenový `docker-compose.local.yml` |
| `scratch/jhu_rollout.py` | `.local/operations/jhu_rollout.py` | Uchovat vazbu na chráněné JHU snapshoty a návrat nasazení |
| `scratch/jhu_ann_release.py` | `.local/operations/jhu_ann_release.py` | Uchovat dosavadní ANN diagnostiku a nedokončené provozní ověření |
| `scratch/run_jhu_prod_ingest.ps1` | `.local/operations/run_jhu_prod_ingest.ps1` | Uchovat historický operátorský postup, nespouštět ho jako běžný release |

Poslední tři soubory zůstávají neveřejné a ignorované Gitem. Při přesunu byl opraven výpočet kořene projektu v Python operátoru; sousední import obou operátorů zůstává možný. Jejich migrace ani cloudové fáze se během úklidu nespouštěly. Staré zmínky o `scratch/` v historických poznámkách označují původní umístění.

Přesunutý PostgreSQL Compose je archiv, nikoli doporučený testovací setup. Před případným použitím je třeba opravit odloženou PostgreSQL cestu a explicitně ověřit původní Compose project/volume: jiný adresář souboru může změnit výchozí jméno projektu. Úklid žádný Docker kontejner ani volume nemaže.

## Co se smazalo a proč

| Skupina | Posouzení |
|---|---|
| Zbytek `scratch/` | Jednorázové debug dotazy, obnovování starých AI editací, kopie `page_at_398.tsx`, raw JSON/logy a pomocníci předchozí publikace; aplikace ani pytest je neimportují |
| `check_diff.py` | Jednorázová diagnostika konkrétní soukromé PDF cesty, nikoli obecný nástroj spuštění aplikace |
| `temp_instructions.md` | Ignorovaný starý návod doporučující nyní blokovaný `deploy_all.ps1`; nahrazen README |
| `ai_search_app.egg-info/` | Generovaná a zastaralá Python metadata, která nemají být verzovaná |
| `infra/main.json` | Generovaný ARM výstup; zdrojem je Bicep a žádný současný skript tento soubor nepoužívá |
| `.github/workflows/azure-static-web-apps-calm-sea-05badcc03.yml` | Staré automatické nasazení jedné aplikace z neexistujícího `frontend/`; neslouží ani jednomu současnému frontendu |
| `frontend/` | Obsahoval jen starou `.next` cache, žádné zdroje |
| `frontend-admin/public/{file,globe,next,vercel,window}.svg` | Nepoužité výchozí Next.js ilustrace; žádný aktuální zdroj na ně neodkazuje |
| `docs/tests_explained/test_keyvault_config_explained.md` | Zastaralé duplicitní vysvětlení; současné chování zůstává v `test_keyvault_config.md` |
| Kořenové `.tmp-pytest*/`, `.pytest_cache/`, `.local/pytest-*/` | Ukončené testovací běhy a jejich kopie fixture; znovu vytvořitelné |
| Python `__pycache__/` v kořeni/app/tests | Odvozený bytecode; podle potřeby se znovu vytvoří |
| `.local/release-v014-check/`, stará commit message | Jednorázové validační artefakty dokončeného release |

První úklid odstranil **1 802 souborů, přibližně 14,06 MiB** včetně ignorovaných testovacích artefaktů. Počet zahrnuje i generované cache; počet změn v Gitu je menší. Testy mohou následně znovu vytvořit cache. Verze v0.1.4 uchovává historii dříve verzovaných odstraněných souborů.

Pytest nyní používá ignorovanou `.local/pytest-cache`; nová cache tak nevzniká v kořeni. Závěrečné ověření cílených skriptových/deployment/vector regresí: **43 passed**. První pokus v sandboxu skončil na oprávnění k dočasnému adresáři; stejná sada mimo sandbox prošla. Statická kontrola potvrdila odkazy aktualizovaných návodů, mapu všech 291 aktuálních zdrojových souborů, zachování 13 kořenových CLI, syntaxi a kořen privátních operátorů a zachované soukromé oblasti.

## Zachované soubory a další kandidáti

Aktualizace 2026-10-26: odstraněno dalších **53 kořenových `.tmp-pytest*` adresářů**, 50 816 souborů o souhrnné logické velikosti přibližně 221 MiB. Před smazáním byly ověřené přímé cesty uvnitř workspace, absence sledovaných souborů, symbolických odkazů/junctions a běžících pytest procesů. Soukromé env, korpus, `.local/deployments/`, závislosti a Docker volumes zůstaly zachované.

`tests/conftest.py` nyní pro standardní spuštění směruje pytest do `.local/tmp/pytest/`. Používá běžné číslování, zámky a retenci tří relací pytest; operátorovy explicitní temp volby respektuje. Při běžných bězích nepoužívej ruční `--basetemp`, který obchází automatickou retenci a svůj cíl před použitím maže. `dev.ps1` omezuje autoreload na `app/`, aby změny testovacích kopií nezpůsobovaly nové starty backendu.

| Cesta | Co s ní |
|---|---|
| `.env.local`, `tenants/*/.env*` | Zachovat: lokální heslo a skutečná neveřejná připojení; žádné env se během úklidu nemění |
| `data/`, `data - full backup/` | Zachovat: vlastní korpus a původní dokumenty; nejsou nahrazené dvěma fiktivními fixtures |
| `.local/deployments/` | Zachovat: checkpointy a DPAPI zálohy pro návrat JHU; smazání by odstranilo původní snímky |
| `.local/benchmarks/` | Zachovat: cache dotazů a naměřené výsledky; část souvisí s otevřeným ANN/performance ověřením |
| `.local/test/` | Zachovat: lokální konfigurační overlay; běžný pytest používá vlastní dočasný overlay |
| `.venv/`, `frontend-*/node_modules/` | Používané závislosti; lze znovu vytvořit, ale jejich smazání přeruší okamžité spouštění |
| `frontend-user/.next/`, `frontend-admin/.next/`, `frontend-*/out/`, `*.tsbuildinfo` | Další bezpečně obnovitelné kandidáty, pokud neběží dev/build/deploy; nyní zachované jako používané pracovní výstupy |
| `full_refresh_ingest.py`, `reset_users_db.py` | Samostatná údržba mimo běžný start/release: refresh má plán a chráněný Apply, reset účtů je destruktivní |
| `deploy_all.ps1` | Zachovaný blokující vstup se srozumitelnou chybou pro staré postupy |
| `infra/`, historické ADR a deployment reporty | Zachovat zdroje/rozhodnutí a historii; jejich stáří samo nedokazuje nepotřebnost |

Nevytváří se automatický plošný cleaner ani `git clean -xfd`: ignorované složky obsahují i data a secrets, která se nesmějí zaměnit s cache. Neprováděl se build/deployment ani zásah do Azure, účtů nebo databází. Další technický slice zůstává reprezentativní JHU benchmark a optimalizace změřeného nákladu před aktivací ANN.

Naměřené zbývající frontendové výstupy: user `.next` 57,39 MiB a `out` 0,97 MiB; admin `.next` 65,85 MiB a `out` 1,30 MiB. Jejich případné smazání uvolní dalších přibližně 126 MiB a vyžádá nový build. Aktivní instalace závislostí se do tohoto čísla nepočítá.
