# JHU připojení: Key Vault a samostatná pomocná služba

Slice 1 navazuje na [VPN spike](jhu-vpn-spike.md). Aktuální slice 2 přidává opt-in aplikaci a VS Code podle [návodu managed připojení](jhu-managed-local.md); živá aplikační akceptace je samostatná. Níže je lifecycle a historické ověření slice 1. Standalone nástroj systémovou VPN nemění a neimportuje app Settings/SQL.

## Předpoklady

Docker Engine, projektová `.venv`, `az login` na účet s Get právy do vybraného vaultu, externí původní Client.ovpn. Ve stávajícím `ju-ai-search-kv-prod` jsou oddělené secrets:

| Reference | Obsah |
|---|---|
| `ju-ai-search-vpn-username-prod` | VPN login |
| `ju-ai-search-vpn-password-prod` | VPN heslo |
| `ju-ai-search-jhu-api-username-prod` | Basic uživatel modelového API |
| `ju-ai-search-jhu-api-password-prod` | Basic heslo modelového API |

Přístup ani hesla tento příkaz nemění. Nepřepínej APP_ENV na prod. Endpoint lze explicitně zadat přes `--endpoint`; jinak se čte pouze JHU_LLM_ENDPOINT z ignorovaného `.env.jhu-model`. Jeho staré username/password se pro helper nepoužijí. Pro ověření bez systémové VPN ji nejprve sám odpoj ve chvíli, kdy to neovlivní ostatní práci.

## Příkazy z VS Code terminálu

```powershell
$tenant = "jhu" # Konfigurační alias ju-prod je také povolen; DB identitu nástroj nemění.
$vault = "ju-ai-search-kv-prod"
$profile = "$env:USERPROFILE\OpenVPN\config\Client\Client.ovpn"

# Jednou / po aktualizaci veřejných zdrojů:
.venv\Scripts\python.exe probe_jhu_vpn.py build

# Ověří čtení všech čtyř secrets; vypíše jen configured/secret_count.
.venv\Scripts\python.exe jhu_connection.py check-secrets --tenant $tenant --vault $vault

.venv\Scripts\python.exe jhu_connection.py start --tenant $tenant --vault $vault --profile $profile --wait
.venv\Scripts\python.exe jhu_connection.py status --tenant $tenant
.venv\Scripts\python.exe jhu_connection.py reconnect --tenant $tenant --wait

# Po změně hesla/configu nebo vyčerpání pokusů: explicitně načte nový snapshot.
.venv\Scripts\python.exe jhu_connection.py restart --tenant $tenant --vault $vault --profile $profile --wait

.venv\Scripts\python.exe jhu_connection.py stop --tenant $tenant
```

Start/status/stop jsou idempotentní. Opakovaný start stejné konfigurace nečte znovu credentials a nezaloží druhý tunel. Změněná konfigurace vyžaduje restart. Druhý workspace s existujícím spravovaným helperem další relaci odmítne; nesdílí automaticky cizí spojení. Bez `--wait` start vrátí connecting; `--wait` má omezené čekání, nikoli garanci dokončení všech tří dlouhých handshake pokusů. Po timeoutu zkontroluj status a případně použij stop.

Po přestavení image použij explicitní restart: samotný start zachovává existující běžící kontejner a neaplikuje na něj nové vrstvy image. Následně použij [správní refresh](jhu-connection-resilience.md) nebo restart backendu kvůli novému klíči gateway. Po restartu počítače helper zajistí opt-in VS Code úloha ze slice 2, nikoli systémový autostart.

Aktuální protokol 2 publikuje úzkou capability gateway pouze na dynamický loopback port pro backend; síťové ovládání služby se nepublikuje. Původní slice 1 port neměl. `ready` potvrzuje tunel a odpověď 200/401 z neautentizovaného tags health checku. Správný API login ověří oddělený probe; samotné ready neprokazuje kvalitu modelu, oprávnění nebo RAG.

## Stav, chyby a bezpečné chování

- `connecting` / `ready`: navazování / ověřený forward s pravidelným heartbeat.
- `degraded`: spojení není použitelné; `code` je pevný diagnostický kód.
- `auth_failed`: VPN odmítla autentizaci; další pokus se automaticky neprovede.
- `disabled`: náš helper neběží.
- Tři pokusy za životnost kontejneru, mezi nimi 2 a 5 s; platí i po předchozím ready. Auth/certifikát/options failure jsou terminální. Nový rozpočet vzniká jen explicitním restartem.
- `jhu_secret_missing`, `jhu_vault_forbidden`, `jhu_vault_authentication_failed`, `jhu_vault_unreachable` rozlišují konfiguraci, práva, login a síť. Ve zvoleném KV režimu nenásleduje fallback na stará env hesla.
- `jhu_helper_restart_required`: změnil se profil/endpoint/reference, použij restart. `jhu_helper_foreign_owner` a `jhu_helper_other_workspace_active` odmítají zásah do cizího kontejneru.
- Terminální failure smaže auth/config z tmpfs. Stop odstraní jen vlastní immutable container ID, bez zásahu do systémové VPN, SQL kontejneru nebo dat. Zánik/stop Dockeru smaže tmpfs; další start vyžaduje nové načtení secrets.

KV resolver má explicitní variantu managed identity pro pozdější cloud, otestovanou pomocí mocku. Živý Azure helper ani cloudové identity se tímto slicem nenasazují. Uložení nových secrets řeší uživatel; širší úklid OpenAI/Storage/JWT/ACR je samostatný. Stávající `.env.jhu-model` credentials zachováváme pro explicitní legacy direct režim; managed cesta je nepoužívá.

## Ověření API credentials

Po zastavení helperu (kvůli jediné VPN relaci) lze spustit jednorázový probe:

```powershell
.venv\Scripts\python.exe jhu_connection.py stop --tenant $tenant
.venv\Scripts\python.exe probe_jhu_vpn.py live --profile $profile --api-credentials key_vault
```

Nový výchozí zdroj API credentials pro probe je Key Vault. Výslovné `--api-credentials env` zachovává starý testovací režim; nikdy se nezvolí automaticky při KV chybě. Jednorázový probe testuje API i VPN v jednom dočasném kontejneru; dlouho běžící helper dostává výhradně VPN credentials.

Rozhodnutí: [ADR-0038](../adr/ADR-0038-jhu-helper-secrets-lifecycle.md). Jednotkové testy: [resolver](../tests_explained/test_jhu_secrets.md), [lifecycle](../tests_explained/test_jhu_helper.md).

## Doložené výsledky 2026-10-22

Při systémové VPN odpojené (Wi-Fi default route) prošlo čtení všech čtyř skutečných KV secrets. Start a opakovaný start zachovaly attempts=1/generation=1, řízený reconnect přešel na 2/2. Testovací ukončení pouze procesu OpenVPN ve vlastním kontejneru vyvolalo automatickou obnovu na 3/3. Další ukončení přešlo do degraded bez čtvrtého pokusu; auth a client.conf v tmpfs byly prokazatelně odstraněny. Opakovaný stop, další start a explicitní restart prošly; konečný status byl disabled.

Samostatný jednorázový probe výhradně s KV API credentials ověřil 17 modelů, dvě skutečné generace Llama 3.2 3B (5 848 / 341 ms) a dva Nomic 768 embeddingy (712 ms). Jde o konektivitu, nikoli benchmark nebo aplikační RAG akceptaci. Secrets se nerotovaly a jejich hodnoty nebyly vypsány. Aplikační `.env`, SQL, korpus, Azure prostředky/identity a kapacita se neměnily; nové secrets vytvořil uživatel. Po testu byly vlastní testovací kontejnery odstraněny.

Ověření: **75 cílených testů prošlo** včetně skutečného wheelu a exportních regresí. Po poslední úpravě kódu chyby probe prošlo znovu všech **29 probe regresí**. Čistá projekce aktuálních zdrojů má 273 souborů a vylučuje interní helper; AST, nové dokumentační odkazy, navigace a whitespace prošly. Úplná aplikační sada, frontend buildy a cloudová akceptace se v tomto slicu neopakovaly. Starý slice 0 a nová lifecycle akceptace nejsou nasazením běžné aplikace.
