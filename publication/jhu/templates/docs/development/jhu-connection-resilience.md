# Odolnost managed JHU připojení

Navazuje na [lokální přípravu](jhu-managed-local.md). Režim je určen pro local/test a používá jednu spravovanou relaci. Nová otázka nepřebírá nepovedený request; přerušené generování se automaticky neopakuje a nejde do jiného modelu.

## Co se stane při výpadku

Supervisor odvolá ready a ukončí čekající upstream sockety ještě před dokončením úklidu VPN. Dotaz dostane řízenou chybu. Obnova má stále nejvýše tři pokusy za životnost helperu a terminální auth/cert/options chyby nepokračují. Další otázku odešli až po ready. Úspěšný reconnect ve stejném kontejneru zachová klíč a backendový snapshot.

Při pouhém selhání kontroly API se ready odvolá hned, ale VPN proces se restartuje až po třech neúspěšných kontrolách za sebou. Každá čeká nejvýše 2 s; po chybě následuje další nejdříve za 0,5 s. Úspěch obnoví ready bez nové generation. Krátká nedostupnost při rekey tak nemusí vyčerpat reconnect pokus. Zánik procesu a terminální auth/cert chyby se řeší okamžitě.

Úplný restart helperu nebo Dockeru mění klíč/port. Backend záměrně nepřeposílá selhaný dotaz do nového spojení. Po novém startu helperu buď restartuj backend, nebo použij explicitní správní refresh níže. Při rotaci secrets se načtou jen nakonfigurované aktuální reference; nástroje samy hesla nemění.

## Diagnostika a refresh bez restartu backendu

API vyžaduje platný bearer token uživatele s aktuální serverovou skupinou `Management` v JHU tenantu. Použij běžné přihlášení aplikace; token nepatří do Gitu ani chatu. Příklad předpokládá token v neveřejné procesové proměnné `AI_SEARCH_TOKEN`:

```powershell
$headers = @{ Authorization = "Bearer $env:AI_SEARCH_TOKEN" }
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/models/connection" -Headers $headers
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/models/connection/refresh" -Method Post -Headers $headers
```

GET vrací stav JHU nezávisle na `/api/health`; healthy backend neznamená dostupný tunel. `health_ms` měří kontrolu helperu, nikoli samotnou latenci modelu, vyhledávání ani VPN overhead. Direct režim vrací managed disabled a nic nezakládá. POST ověří vlastní kontejner/mapování a znovu načte API pár z KV, potom atomicky vymění procesový snapshot. Pokud je JHU operace rozpracovaná, vrátí 429; chybný KV/owner/mapping snapshot nepřepíše. Při sticky chybě inicializace je právě refresh nebo restart backendu explicitní cestou obnovy.

Současné JHU volání zabere slot před jakýmkoli connection lookupem. Refresh drží slot i po odpojení volajícího, dokud jeho omezený worker nedokončí práci. HTTP klienti a event loopy zůstávají samostatné; cache obsahuje jen stejný ověřený SSLContext, takže se při každé otázce znovu nečte certifikační bundle. Ověření certifikátu a hostname zůstává aktivní. Po změně trust bundle restartuj backend.

API nepřijímá endpoint, credentials, cílový model ani index a oprávnění k dokumentům/modelům nemění. Nespouští VPN ani Docker. Po Docker restartu nejprve použij `dev.ps1 -Action start-jhu -Tenant jhu`, teprve potom refresh.

## Izolované testy

```powershell
.venv\Scripts\python.exe -m pytest tests/test_jhu_gateway.py tests/test_jhu_connection_status.py tests/test_jhu_transport.py tests/test_jhu_helper.py -q
```

Používají fiktivní KV/Docker a skutečné loopback sockety. Ověřují i zrušení mezi navázáním a odesláním, zákaz http.client reconnectu, ukončení během odpovědi a úspěch dalšího samostatného requestu. Backend health a cloudové modely zůstávají nezávislé.

## Skutečné přerušení, rekey a měření

Test vyžaduje Docker, veřejnou image z aktuálního zdroje, `az login`, čtyři připravené KV secrets a původní soukromý profil mimo repo. Systémovou VPN pro nezávislý důkaz ručně odpoj. Zastav vlastní aplikaci/helper; test odmítá další spravovanou relaci a nikdy nepřebírá existující helper.

```powershell
docker build --tag ai-search-vpn-spike:local scripts/vpn_spike
.\dev.ps1 -Action stop-jhu -Tenant jhu
$env:RUN_JHU_RESILIENCE_TESTS = "1"
$env:JHU_RESILIENCE_SOAK_SECONDS = "300"  # Povolený rozsah 120–3600 s.
.venv\Scripts\python.exe -m pytest tests/test_jhu_resilience_live.py -q -s --tb=short
Remove-Item Env:RUN_JHU_RESILIENCE_TESTS, Env:JHU_RESILIENCE_SOAK_SECONDS
```

Volitelně nastav `JHU_VPN_PROFILE` pro jinou externí cestu, `JHU_KEY_VAULT_NAME` pro jiný existující vault. Pro restart celého Rancheru nastav před testem ještě **`RUN_JHU_DOCKER_RESTART_TESTS=1`**, ale pouze když můžeš přerušit i ostatní kontejnery; po testu proměnnou odstraň. Bez tohoto dalšího opt-in se Rancher nerestartuje. Na Windows s nestandardní instalací lze zadat `RANCHER_DESKTOP_EXE`.

Test vytváří vlastní helper s náhodným workspace ownerem. Pouze v jeho odvozené tmpfs konfiguraci použije reneg-sec30; původní profil se nemění. Přes skutečné API odešle jeden delší syntetický prompt, ověří 429 souběžné varianty, ukončí pouze svůj OpenVPN proces, ověří rychlou řízenou chybu a právě jeden forwarded generate, pak obnovu a další dotaz. Dále vymění helper, explicitně obnoví snapshot a případně provede schválený Rancher restart. Následuje soak s čtením tags, stejnou generation a rostoucím počtem skutečných TLS kanálů. Měří helper cgroup paměť/CPU a health zvlášť od modelu; sampling má vlastní malou režii. Výstup je sanitizovaný JSON bez obsahu profilů a credentials.

Test nepotřebuje Azure model, SQL ani skutečné dokumenty, nevytváří KV verze a nemění RBAC/kapacitu. Nakonec odstraní jen svůj helper. Samostatný `test_jhu_managed_live.py` potom ověřuje RAG nad dočasnou lokální SQL. Živé výsledky a jejich limity se zapisují až po skutečném dokončení; samotný opt-in test není akceptace cloudu.

## Doložené lokální ověření

Aktuální helper byl ověřen bez systémové VPN dne 2026-10-23. Závěrečný test přešel od přerušené generace přes automatické obnovení a explicitní výměnu helperu k pětiminutovému rekey testu:

| Měření | Výsledek |
|---|---|
| Ukončení přerušené generace | 281 ms; právě jeden forwarded generate |
| Obnovení spojení pro další nový dotaz | 4 047 ms |
| Soak / TLS kanály | 302 s / 10; stejná generation, žádný samovolný reconnect |
| Kontrola dostupnosti helperu | medián 16 ms, maximum 16 ms v tomto běhu |
| Paměť helperu | špička 37,6 MiB, konec 29,4 MiB |
| Průměrný CPU helperu | 0,0027 jádra včetně měřicí režie |
| Samostatný schválený restart Rancheru | obnovení prostředí 92,2 s; ověřen dříve v témže slicu |

Krátký závěrečný opakovaný běh 121 s také prošel (medián health 7,5 ms). Kompletní testy s lokální SQL a skutečným wheelem: 606 prošlo / 23 očekávaných přeskočení. Tyto hodnoty měří lokální helper, nikoli celé RAG, součet kontejnerů ACA nebo dlouhodobé SLA. Dlouhodobá dostupnost API a chování sítě v Azure zůstávají samostatnou akceptací. Odeslaná operace se při žádném selhání sama neopakuje.

Následný skutečný test discovery → Nomic index → Llama chat s citací a uloženou provenance prošel v dočasné lokální SQL databázi (1 passed / 1 SQLite skip, 17,10 s). Aplikační dokumenty ani výchozí index se neměnily; vlastní pomocný VPN kontejner byl po testech vypnutý a SQL volume zachovaný.
