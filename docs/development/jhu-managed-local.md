# Automatické JHU připojení v lokální aplikaci

Opt-in režim `managed` používá samostatný Docker helper. Systémovou OpenVPN nemusíš ručně zapínat. Chat, shrnutí, klasifikace, discovery, embeddingy a backfill používají společný transport; každý dotaz stále hledá právě v jednom vybraném indexu. Připojení samo indexy ani modelové profily nemění.

## První příprava

Potřebuješ funkční **Server** část `docker info`, projektovou `.venv`, přihlášení `az login` s právem čtení vybraných secrets a původní soukromý `Client.ovpn` mimo repozitář. Systémovou VPN pro nezávislé ověření sám odpoj; helper ji nemění.

```powershell
# Z kořene repozitáře, jednou a po změně zdrojů helperu:
docker build --tag ai-search-vpn-spike:local scripts/vpn_spike
az login
```

Do existujícího ignorovaného `.env.local` přidej pouze nesekretní připojení, zachovej SQL hodnoty:

```dotenv
JHU_LLM_ENDPOINT=http://160.217.182.41:11434
JHU_LLM_ALLOW_HTTP=true
```

Endpoint musí odpovídat cíli dodaného profilu. Helper podporuje v této verzi pevný IPv4 HTTP cíl; veřejnou přímou HTTP cestu při selhání nepoužije. Původní `.env.jhu-model` se také podporuje, jeho hesla ale režim managed nepoužije. Nemusíš soubory mazat.

Ve vaultu `ju-ai-search-kv-prod` musí existovat čtyři oddělené secrets:

| Účel | Reference |
|---|---|
| VPN login | `ju-ai-search-vpn-username-prod` |
| VPN heslo | `ju-ai-search-vpn-password-prod` |
| Modelové API login | `ju-ai-search-jhu-api-username-prod` |
| Modelové API heslo | `ju-ai-search-jhu-api-password-prod` |

Helper čte jen VPN pár; backend čte jen API pár. Hodnoty nepatří do JSON katalogu, Git historie, argumentů ani Docker env.

## Každodenní start ve VS Code

Zvol **Terminal → Run Task… → AI Search: start JHU local app**. Spustí lokální SQL, JHU backend s managed připojením, user konzoli na 3000 a administraci na 3001. Po restartu počítače nejprve spusť Rancher/Docker, potom stejnou úlohu. Přihlášení Azure CLI musí být stále platné.

Ručně, backend v samostatném terminálu:

```powershell
$tenant = "jhu"
.\dev.ps1 -Action start-db
.\dev.ps1 -Action backend -Tenant $tenant -JhuManaged
```

Frontendové terminály jsou stejné jako v [README](../../README.md), s `$tenant = "jhu"`. Přepínač nepřepisuje soukromé env soubory. Jiný vault nebo cestu profilu zadáš pomocí `-JhuVault` a `-JhuVpnProfile`:

```powershell
.\dev.ps1 -Action backend -Tenant jhu -JhuManaged `
  -JhuVault "ju-ai-search-kv-prod" `
  -JhuVpnProfile "$env:USERPROFILE\OpenVPN\config\Client\Client.ovpn"
```

Nechceš-li přepínač opakovat, můžeš do `.env.local` přidat `JHU_CONNECTION_MODE=managed`; pak spouštěj backend s `-Tenant jhu`. Ostatní tenanty tento režim odmítnou. Výchozí režim `direct` zachovává původní HTTPS nebo ověřenou Windows VPN cestu.

## Stav, stop a diagnostika

```powershell
.\dev.ps1 -Action start-jhu -Tenant jhu
.\dev.ps1 -Action status-jhu -Tenant jhu
.\dev.ps1 -Action stop-jhu -Tenant jhu
```

Ve VS Code jsou také úlohy **AI Search: JHU connection status** a **AI Search: stop JHU connection**. Ctrl+C zastaví backend, samostatný helper zůstane do explicitního stopu nebo ukončení Dockeru. SQL volume se nemaže.

`ready` znamená funkční VPN forward; správný API login a model ověř samostatně:

```powershell
.venv\Scripts\python.exe probe_jhu_model.py --managed --tenant jhu --model llama3.2:3b
.venv\Scripts\python.exe probe_jhu_embeddings.py --managed --tenant jhu --embedding-profile jhu-nomic
```

Probes samy helper nezakládají. Používají stejný ověřený transport a Key Vault; modelový probe jen synteticky generuje, embeddingový kontroluje připnutý profil/digest. Nic nestahují a neaktivují index.

Reprodukovatelný RAG test přes skutečný helper a službu, při běžící lokální SQL a připraveném helperu:

```powershell
$env:RUN_LOCAL_SQL_TESTS = "1"
$env:RUN_JHU_MANAGED_TESTS = "1"
.venv\Scripts\python.exe -m pytest tests/test_jhu_managed_live.py -q -s --tb=short
Remove-Item Env:RUN_JHU_MANAGED_TESTS
Remove-Item Env:RUN_LOCAL_SQL_TESTS
```

Vytvoří vlastní náhodnou testovací SQL databázi, dva syntetické texty, druhý Nomic index a skutečnou odpověď malého Llama s citací a provenance. Po testu odstraní pouze svou databázi. Aplikační data/indexy se neaktivují ani nepřepisují, Azure model se nevolá. SQLite varianta se záměrně přeskočí. Test nepovažuj za úspěšný, pokud se přeskočila i SQL varianta.

V admin konzoli obnov modely z API. V chatu vyber jeden povolený JHU model a pro embeddingy jeden již připravený lokální index. Ověř odpověď, citaci a uložený model/index po obnovení konverzace. Příprava nového indexu je samostatná explicitní operace podle [návodu registru](local-model-registry.md).

Při chybě helperu backend pokračuje s ostatními nakonfigurovanými modely. Neprobíhá automatické opakování generace, přepnutí modelu/indexu ani náhradní přímé připojení. `jhu_vault_forbidden` znamená chybějící Get právo; `jhu_vault_authentication_failed` vyžaduje ověření `az login`; `jhu_helper_unavailable` nebo `jhu_docker_operation_failed` vyžaduje nejprve funkční Docker. Nesnaž se to řešit přepnutím `APP_ENV=prod`.

Helper je vázán na workspace a ověřený loopback port. Chyby `jhu_helper_mapping_invalid` / `jhu_helper_restart_required` znamenají neodpovídající runtime; po přestavení image nebo změně secrets proveď explicitní restart a potom správní refresh připojení, případně restart backendu:

```powershell
.venv\Scripts\python.exe jhu_connection.py restart --tenant jhu `
  --vault ju-ai-search-kv-prod --profile "$env:USERPROFILE\OpenVPN\config\Client\Client.ovpn" --wait
# Potom Management POST /api/models/connection/refresh, nebo restart backendu.
```

Backend drží jeden ověřený snapshot API credentials a runtime klíče. Řízený reconnect ve stejném kontejneru klíč zachová; explicitní restart kontejneru jej mění. Po chybě inicializace či rotaci použij explicitní Management refresh nebo restart backendu. [Stav a obnova připojení](jhu-connection-resilience.md) popisuje GET/POST API, oprávnění a živé fault/rekey testy. Docker a KV se nevolají při každé otázce. Krátká kontrola heartbeat před každou modelovou operací má limit 3 s; latence VPN/modelu se musí změřit zvlášť. TLS konfigurace klienta se sdílí s plným ověřováním certifikátů; HTTP klient ani cookies se mezi operacemi/event loopy nesdílejí.

## Rozsah ověření

Izolované testy transportu, HTTP brány, PowerShell startu a exportu používají syntetické služby. Samostatná živá akceptace 2026-10-23 prošla bez systémové VPN: host trasa Wi-Fi, helper ready na první pokus, 17 modelů, Nomic 768 a skutečný Llama 3.2 3B chat s citací a uloženým modelem/indexem. Test ve vlastní dočasné SQL databázi skončil **1 passed / 1 SQLite skip**, původní aktivní index/chunky zachoval a testovací DB odstranil. Veřejné managed CLI probes také prošly. Jde o funkční ověření, nikoli výkonový nebo dlouhodobý outage benchmark; jedna dřívější obecná chyba modelového CLI se při explicitním diagnostickém běhu nereprodukovala.

### Rancher 1.24.0: Hyper-V socket timeout po krátkém běhu

Pokud Docker krátce funguje a pak hlásí `timed out dialing Hyper-V socket`, ověř verzi přes `rdctl version` a healthcheck:

```powershell
wsl -d rancher-desktop -- grep _ping /etc/init.d/docker
```

Ve verzi 1.24.0 může být chybná URL `http://./_ping`. [Upstream popis a workaround](https://github.com/rancher-sandbox/rancher-desktop/issues/11130) doporučuje `%LOCALAPPDATA%\rancher-desktop\provisioning\fix-docker-healthcheck.start` s UTF-8 bez BOM a LF konci řádků:

```sh
#!/bin/sh
sed -i 's|http://\./_ping|http://localhost/_ping|g' /etc/init.d/docker
```

Po vědomém Quit/start Rancheru se má zobrazit `http://localhost/_ping`; ověř Docker i po několika minutách. Samotný `wsl` příkaz aplikaci Rancher ani její provisioning nespustí. Restart přeruší ostatní lokální kontejnery; factory reset a mazání volumes tento postup nevyžaduje. Workaround patří do lokálního nastavení Rancheru, nikoli do image aplikace či VPN profilu. Jeho potřebu po budoucí aktualizaci posuď proti konkrétní verzi.

Azure Container App tímto režimem nepřipojuj: managed v této verzi přijímá pouze local/test. Cloudová síť, distribuce profilu, identita a resource split čekají na samostatný handoff. Přerušení dotazů, rekey a správní refresh popisuje [provozní odolnost](jhu-connection-resilience.md).
