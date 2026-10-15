# Azure Deployment Handoff: JHU JWT a přechod hesel

- Status: completed (uživatel schválil provedení agentem; secrets/runtime a skutečné auth/legacy smoke prošly)
- Created: 2026-10-15
- Related task: příprava JHU search deploymentu bez nových rolí
- Related ADR: `docs/adr/ADR-0027-keyvault-jwt-and-password-hash-migration.md`
- Related branch/PR: pracovní strom, bez nového commitu/PR

## Proč tento handoff existuje

**Provedený výsledek:** záznam integrace je v `docs/deployments/2026-10-15-jhu-search-rollout.md`. Nový JWT a oddělený původní password klíč jsou v existujícím KV, backend je skutečně načítá; vlastní nový i legacy účet se přihlásily a byly odstraněné. Původních7uživatelů a jejich heslové hashe se při rollout nezměnily, nové session tokeny vyžadují nové přihlášení. Revize0000007 je nový kompatibilní baseline. Další části jsou historický postup/specifikace, nikoli čekající žádost o opětovné schválení nebo opakované vytvoření secrets.

Uživatel povolil pokračovat v lokální přípravě; před úpravami Azure chce konkrétní souhlas. Má možnost vytvářet secrets, nikoli udělovat role. JHU backend už má na `ju-ai-search-kv-prod` Key Vault Secrets User (ověřeno pouze čtením ARM/RBAC), ale konkrétní get_secret z běžícího kontejneru ještě nebyl ověřen. Tento krok nevytváří novou aplikaci/databázi/identitu a nemění kapacitu.

## Cíl a rozsah prostředků

| Prostředek | Následný konkrétní zásah po domluvě |
|---|---|
| `ju-ai-search-kv-prod` | člověk vytvoří nový signing secret a případně oddělený legacy password secret podle níže uvedené specifikace |
| `ju-ai-search-ca-prod` | samostatně schválené doplnění názvů/verze secrets do runtime konfigurace a matching image release |
| `ju-ai-search-sqldb-prod` | po schváleném rollout se při úspěšném loginu jednotlivě modernizují hashe v přesném tenantu; žádný hromadný reset, merge ani DDL v tomto slice |
| Backend identity `ccacbf26-dcd6-4f7b-af7b-e3e769137de8` | zachovat existující identitu a roli, žádný role assignment/access policy |

Directory `c35f5da4-9a03-44e6-8bf9-92833634f6a7`, subscription `24e4a9a6-bab0-43f7-ba20-3b774704fade`, RG `ju-ai-search-rg-prod`. Runtime tenant `ju-prod` zachovat; korpus `ju` a smíšené uživatele řeší samostatný hlavní JHU handoff. Tato změna nenahrazuje jeho ACL/Unicode/profilové migrace.

## Co nyní připraví člověk (hodnoty neposílat do chatu/Gitu)

1. Ve stávajícím JHU Key Vaultu připravit **`ju-ai-search-jwt-signing-key-prod`**: nová náhodná hodnota alespoň 32 náhodných bytů, například výstup `secrets.token_urlsafe(32)`, uložená přímo bezpečnou cestou do portálu/secretu. Nepoužívat uživatelské heslo, starý výchozí klíč ani stejnou hodnotu jako legacy klíč. Zaznamenat pouze secret name a nově vrácené version ID.
2. Pro zachování starých hesel připravit **`ju-ai-search-legacy-password-key-prod`**, ale jeho hodnota musí být **skutečný dřívější klíč použitý pro heslové hashe příslušných účtů**, nikoli nově vygenerovaný klíč. Současný `.env` sám nedokazuje historii všech účtů. Původ a úspěšné ověření vhodného existujícího účtu musí potvrdit operátor, bez zveřejnění klíče nebo hesla. Pokud se původ nepodaří doložit nebo různé účty měly jiné klíče, zvolit výslovný postup resetu těchto účtů; automaticky žádný klíč nehádat.
3. Neprovádět role assignment. Existující role backendu platí na celý vault; běžné vytvoření secretu v něm nevyžaduje nový grant. Runtime čtení ale musí být ověřeno ještě před akceptací.

Vytvoření secrets samo běžící backend nezmění: stávající image nemá nové JWT načítání. Lokální `.env` zůstávají zachované a neupravené; image je nepřibaluje. Připravit secrets lze odděleně od aktivace, bez resetu uživatelských hesel.

## App configuration keys

| Runtime klíč | Hodnota / zdroj | Secret? |
|---|---|---:|
| `AZURE_KEY_VAULT_NAME` | zachovat `ju-ai-search-kv-prod` | ne |
| `AZURE_KEY_VAULT_SECRET_JWT_SIGNING_KEY` | `ju-ai-search-jwt-signing-key-prod` | ne, pouze název |
| `AZURE_KEY_VAULT_SECRET_JWT_SIGNING_KEY_VERSION` | člověkem vrácené version ID; připnout stejné všem replikám | ne |
| `AZURE_KEY_VAULT_SECRET_LEGACY_PASSWORD` | `ju-ai-search-legacy-password-key-prod`, jen při zvolené/doložené kompatibilitě | ne, pouze název |
| `JWT_SECRET` | v KV režimu bez starého privátního inline override/secretRef; resolver načte nový klíč | ano, nevypisovat |
| `LEGACY_PASSWORD_SECRET` | v KV režimu bez inline override; resolver načte původní klíč | ano, nevypisovat |

Explicitní privátní runtime JWT/legacy má přednost před KV; přidání názvu secretu vedle starého privátního inline klíče tedy rotaci neprovede. Opravu těchto runtime proměnných provést až ve schváleném údržbovém kroku. SDK načítá při vytváření Settings/startu, nikoli při každém loginu; změna verze vyžaduje koordinovanou novou revizi. Chybějící/default JWT nebo failed KV fetch znamená autentizační503, nikdy fallback k legacy klíči. Chybějící/nesprávný legacy klíč znamená odmítnutí starého hesla bez přepsání hashe; moderní Argon2 účty fungují dál.

## Validace před schváleným rollout

Lokální implementace skutečně prošla: finální celý pytest s `RUN_LOCAL_SQL_TESTS=1` — **281 passed,10 expected skips**,132,33s. Skip jsou dva opt-in real model tests, native Azure exact/ANN a šest MSSQL-only scénářů při SQLite variantě. Cílená první sada KV/password/auth/local-config —37passed; finální full suite navíc zahrnuje wrong legacy key a odmítnutí tokenu podepsaného starým klíčem. Žádné kritérium nebylo oslabeno a Azure testovací opt-ins byly vypnuté. ACR build, skutečné runtime KV načtení a JHU login nejsou tímto výsledkem potvrzené.

- Ověřit původ legacy klíče a určený Management účet, který bude schopen přihlášení. Žádné přidělení Management podle klientského requestu, reset všech účtů nebo merge tenantů není součástí tohoto souhlasu.
- Potvrdit zachované zálohy/UUID/počty, plánované změny korpusu/schema a rollback verzi. Předchozí image z 2026-10-08 nové Argon2 hashe neověří; samotný image rollback nevrací přihlášení po prvním modernizovaném loginu.
- Po nainstalování requirements spustit lokální testy:

```powershell
$env:RUN_LOCAL_SQL_TESTS = '1'
.venv\Scripts\python.exe -m pytest tests/test_password_migration.py tests/test_keyvault_config.py tests/test_multi_tenant_auth.py tests/test_local_development_config.py -q --tb=short
```

Tests používají fake KV, SQLite a unikátní loopback MSSQL test DB; nesměrují na JHU a nevytvářejí Azure secrets. Úspěšný test s odlišným novým signing klíčem a původním legacy klíčem prokáže zachování **stejného** uživatelského hesla a nový hash. Po odebrání legacy klíče a další JWT rotaci musí modernizovaný účet stále projít.

## Funkční validace po konkrétním schválení nasazení

1. V cílovém backendu bezpečně ověřit úspěšné načtení připnutého JWT a legacy secretu existující managed identity. Vrátit jen boolean/verzi, žádný výpis Settings/env/secretů.
2. Přihlásit vhodný stávající JHU účet původním heslem. Ověřit200 a prefix Argon2 u tohoto konkrétního uživatele bez výpisu hashe; zachovat UUID, skupiny, tenant, historii a ostatní účty. Nový podpisový klíč zneplatní staré session tokeny, uživatel se přihlásí znovu.
3. Chybné heslo vrací401 bez změny credentialu; nefunkční JWT nevydá token ani nepřepíše hash. Ověřit cizí tenant/legacy podpis jako401, správce/zobrazení PDF/chat podle hlavního handoffu.
4. Bez příslušného rollout souhlasu žádný z těchto skutečných loginů/DB update nedělat automaticky. Dosud žádné cloudové heslo/secret/hash nebyly změněny.

## Rollback a ukončení kompatibility

Před aktivací mít připravený rollback image, který rozumí Argon2 i legacy formátu. Starý image + modernizované hashe není funkční návrat. Hromadně nevracet staré hashe, protože by přepsaly nově změněná hesla. Bez připravené kompatibilní verze použít samostatně schválený obnovovací postup a omezený přístup; nikdy obnovu veřejně známého signing klíče.

Po ověřeném přechodu relevantních účtů odpojit legacy konfiguraci. Neaktivní účty mohou vyžadovat samostatný reset; žádná automatická expirace/reset API se nyní nepřidává. Podpora cloudového legacy verifieru je explicitní a dá se vypnout odstraněním reference/hodnoty. Moderní účty již původní klíč nepotřebují.

## Human-completed values (pouze ne-secret)

```yaml
jwt_secret_name:
jwt_secret_version:
legacy_secret_name:
legacy_key_provenance_verified: # ano/ne, nikoli hodnota klíče
manager_login_verified:
runtime_get_secret_verified:
rollback_argon2_compatible_image:
cloud_configuration_and_release_scope_approved:
```
