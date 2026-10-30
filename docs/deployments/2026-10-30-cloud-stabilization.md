# JHU cloud: nasazená provozní stabilizace a otevřená relevance

Stav 2026-10-30: schválené SQL S2, stabilizační backend a obě cloudové konzole jsou **nasazené a provozně ověřené**. Původní účty, historie, dokumenty, vektory a všechna uložená nastavení zůstaly zachované. Obsahová akceptace obecné otázky k dovolené proti uživatelem dodanému R_583 **neprošla**; konkrétní problém řazení zdrojů je popsaný níže.

## Dokončený rollout

- Aktivní revize `ju-ai-search-ca-prod--stable-1030-093449`, backend `juaisearchcrprod.azurecr.io/ju-ai-search-ca-prod@sha256:aa7f50e01141c2e5d0bb47344697d62324832421a68a63cd1bfba403bf63c54a`, ACR run `dtp`.
- Helper image `sha256:006c3070ecc2295cfd34d0c80e34c30d006d2bfe57d3e6aa7c58daa723275de3`, MI, secrets/reference hodnoty, veřejný ingress/FQDN, obě SWA, CPU/paměť a min1/max1 zůstaly stejné. Původní backend `durable-1029-201612` je neaktivní s nulou replik. Před novou VPN relací byla nula starých replik skutečně potvrzena.
- Existující SWA [user](https://nice-forest-03f01f203.6.azurestaticapps.net/) a [admin](https://kind-tree-0c95d5203.2.azurestaticapps.net/): živé HTML a všech 8/10 odkazovaných JS/CSS assetů odpovídá aktuálním buildům; oba CORS preflighty 200. Obě přihlášené UI byly zkontrolovány v browseru, admin ukazuje summary/classification modely a index 9372/9372. Původní přihlášení přežilo reload nové verze. Admin tlačítko Vyhledat se po vyplnění skutečné testovací otázky aktivuje; user UI skutečný dotaz odeslalo a zobrazilo odpověď/citace.
- Před/po výměně byly všechny tenantované datové/config otisky stejné. Finální kontrola po testech znovu potvrdila původní účty a původní historii i corpus/index/settings. Zůstává 4 účtů, 431 dokumentů, 9372 chunků/vektorů, 1 stejný index a 3 nastavení. Stav konverzací se změnil 42/66 → 43/68 pouze o jednu skutečnou GUI testovací konverzaci se dvěma zprávami; původních 42 vláken a 66 zpráv má stejné otisky. Syntetický User a všechny vyhrazené API testovací thready byly odstraněny jen přes vlastní identity.
- Zdroj/runtime nadále `v0.1.7` s pracovními změnami; nevznikl nový Git commit/tag/push ani Forgejo publikace. [Dokončený schválený handoff](2026-10-30-cloud-stabilization-handoff.md).

## Skutečné odezvy nové verze

Veřejné GETy se stejným existujícím účtem a cílem jako předchozí sondy:

| Operace | Stará revize po S2 | Nová revize |
|---|---:|---:|
| Seznam dokumentů | 22,000 s | 0,281 s |
| Přehled indexů | 14,156 s | 0,172 s |
| Kategorie | 0,406 s | 0,047 s |
| Search config | 0,204 s | 0,031 s |
| Auth/me | 0,343 s | 0,141 s |
| Health | po S2 0,031–0,219 s | 0,047 s |

Standardní chat API přes loopback v ACA, s původním exact indexem a uloženou konfigurací:

| Model / role | Dovolená | Organizační útvary |
|---|---:|---:|
| Management + GPT-5.4-mini | 3,238 s | 4,558 s |
| Management + JHU Qwen | 52,502 s | 53,406 s |

Všechny čtyři odpovědi HTTP200, 5 zdrojů, správná provenance model/index a 2 uložené zprávy před odstraněním vlastního testovacího threadu. Retrieval 0,56–0,79 s; Qwen generation 51,2–52,3 s včetně 10,4–15,0 s načítání modelu. Samotná větší část zbylé Qwen latence je tedy v externí modelové službě, ne ve zablokovaném API. Souběžné loopback health sondy všechny 200 za 2–55 ms.

Skutečný vlastní User login200/auth-me200/Management403, 72 povolených dokumentů a citovaný chat200 za 3,965 s. Skutečné PDF200 s `%PDF` hlavičkou; HR R_583 je pro tohoto Usera404. Jde o několik cílených smoke měření, nikoli p95 nebo dlouhý/mnohauživatelský benchmark.

## JHU relace a obsahový nález

Po nové replice byl JHU helper `degraded/vpn_upstream_unavailable`, attempts3/generation3/TLS3. Na notebooku zároveň běžel projektový helper `ai-search-jhu-03a6a9d96ab9d868` se stejným cílem a vlastnictvím workspace. Byl ukončen kanonickým `jhu_connection.py stop`; ostatní lokální aplikace/SQL/Rancher se nezastavovaly. Po stop0/start téže cloudové revize je JHU **ready/attempts1/generation1/TLS1**, potvrzeno i po skutečných generacích. Souvislost s kolizí relací je silná, přesná serverová VPN session politika nebyla nezávisle potvrzena. Lokální helper musí při cloudových testech zůstat vypnutý.

R_583 je v korpusu v CS/EN, oba dokumenty current, po 3 chunkech, ACL Management/HR. Obecná otázka na převedenou dovolenou přes oba modely neodpovídá dodané referenci: vybrané podklady jsou jiné předpisy. Čtecí diagnostika stejného profilu najde CS R_583 na vektorové pozici5; uložené `score_addition`, freshness_boost0,2 a váhy0,6/0,4 jej vyřadí z finálních5. Diagnostické RRF nad stejnými kandidáty ho zahrne. Všechny tyto produkční hodnoty byly záměrně zachovány.

Výslovný dotaz „Podle opatření rektora R_583…“ odpověděl za2,863s a obsahuje uživatelem očekávané31.3. s citací R_583. Organizační otázka cituje skutečný R_634 a jeho definice. Celková provozní akceptace tím není totéž co akceptace relevance. **Jediný doporučený další slice:** eval a náprava řazení/čerstvosti zdrojů na obecné otázce k R_583 a dalších reprezentativních otázkách, bez zásahu do ACL a embeddingových identit.

## Rozsah a náklady

Existující `ju-ai-search-sqldb-prod` na `ju-ai-search-sql-prod` v `ju-ai-search-rg-prod`, Sweden Central, přesný tenant `ju-prod`. Uživatel schválil S0/10 DTU → S2/50 DTU pro dnešní testy. Ověřeno Online/S2; maximální velikost 268435456000 B se nezměnila. Další placená změna vyžaduje domluvu; žádné automatické navyšování.

Veřejné orientační ceny Microsoft Retail Prices API v EUR/den: S0 0,4258; S2 2,1295; rozdíl 1,7037. Enterprise smlouva a daň mohou výslednou cenu změnit. [Cenové API](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices). Na konci testování vyhodnotit S2 proti naměřenému vytížení; návrat na S0 neprovádět naslepo při zatížení.

## Zjištění a oddělené důkazy

- Před S2 tři veřejné health sondy překročily 10 s. ACA měla jednu zdravou repliku, žádné restarty, minutové CPU maximum 4 % a paměť 19,5 %. SQL mělo CPU/DTU maximum 100 % ve 46 minutových intervalech za předchozí čtyři hodiny; poslední průměr 98,75 %. Samotné škálování ACA proto nemělo oporu v měření.
- Po S2 **stejná stará verze** vrátila health za 31–219 ms. Samostatná autorizovaná čtení profilu, konfigurací a modelových katalogů vrátila 200 přibližně za 63–406 ms. Přehled indexů ale trval 14,156 s a dokumenty 22 s. Nejde o p95 ani zátěžovou akceptaci.
- Starý dokumentový endpoint prováděl metadata SELECT a samostatný COUNT pro každý dokument: 432 dotazů pro 431 dokumentů. Navíc synchronní ORM pracovalo přímo v async handleru. Stejný problém blokování se týkal SQL konfigurací a retrievalu.
- Nový dokumentový repository používá dvě dávková čtení a stejné sdílené tenant/docACL/chunkACL predikáty. Metadata a agregace zůstávají oddělené; měřený SQL Server ACL plán agregace používá hash joins. Čtecí ověření konečných zdrojů na S2: Management 431 dokumentů/9372 chunků za 0,390/0,234 s; User 72/1663 za 0,204/0,172 s. Navázání spojení/Key Vault režie byla měřena odděleně. Nula chunků se zachovává jako nula.
- Skutečný browser login do obou cloudových konzolí prošel. V administraci se načetly chat/summary/classification modely i původní index 9372/9372. Žádný model/index nebyl přidán, publikován nebo přepnut. GPT-5.4 je nadále nenakonfigurovaný.
- Dotaz k dovolené ve staré cloudové verzi skončil `search_timeout` ještě před generací. Přímé čtecí měření stejného nativního exact SQL nad původním indexem a syntetickým 1536dim vektorem: Management původní plán HYT00 po 11,359 s; hash joins 50 výsledků za 1,485 s. User 50 výsledků za 0,765/0,625 s se shodným otiskem pořadí UUID. To je důkaz změny SQL plánu, nikoli úspěšné odpovědi na skutečnou otázku ani benchmark relevance.
- Konečná varianta omezuje hint výhradně na hlavní joiny tabulek; globální hint byl odmítnut, protože JSON metadata filtr vyvolal 8622. Z existující ACA byl v samostatném čtecím Python procesu ověřen skutečný konečný compiler/dotaz: Management all 0,625 s; User all 0,305 s; Management document_type filtr 0,757 s; User latest 0,285 s. Vždy 50 výsledků, stejné původní tabulky/index a desetisekundový limit. API worker ani soubory/image tím nebyly změněny. Přímý notebookový přístup mezitím odmítl firewall 40615; žádné jeho pravidlo nebylo rozšířeno.

## Nasazené opravy

Retrieval a přehled dokumentů používají synchronní SQL v pracovním vlákně; cloudové async konfigurace také odkládají blokující SQL mimo event loop. Čtení kategorií vůbec nepotřebuje inicializovat klasifikační model. Nativní exact dotaz zachovává všechny předfiltry, revizi vstupu, vzdálenost, pořadí i finální TOP K a používá měřený hash-join plán. Desetisekundový limit, původní index a exact režim zůstávají.

Obě UI bezpečně zpracují textové/HTML gateway chyby, mají omezené načítání a ruční obnovu katalogů. Po selhání prvního načtení lze obnovit deklarované výchozí volby; explicitní model/index se tiše nenahrazují. Dočasné 5xx neodhlašuje uživatele a stará odpověď 401 nesmaže novější relaci. Profil nově obsahuje přesný tenant. Odeslání se řídí skutečnou dostupností modelu/indexu a vysvětluje blokovaný stav. Health polling se nepřekrývá a cleanup ruší probíhající požadavek.

## Ověření a další akceptace

Úplná izolovaná sada s wheelem po async retrieval změně: **582 passed / 120 expected skips**. Konečné frontend utility: **8 passed**. Dokumentové/config/auth regrese s izolovaným lokálním SQL: 36 passed. Širší retrieval/ACL/benchmark sada: 162 passed / 7 expected skips; model/config/auth sada 80 passed / 8 expected skips. Po omezení hintu pouze na hlavní joiny proběhla nová SQLite/MSSQL katalog/vector/ANN sada: **65 passed / 6 expected skips**; tato konečná SQL varianta má navíc živé ACA ověření uvedené výše. Oba konečné Next produkční buildy včetně TypeScriptu prošly s JHU tématem a skutečným cloudovým backend URL. Syntaxe, aktuální JHU projekce319souborů a navigace476veřejných zdrojů prošly. Žádný z těchto zdrojových výsledků nepředstavuje nasazení nové image nebo dokončený test skutečných odpovědí.

Konečný čistý JHU balíček bez privátních env souborů navíc prošel katalog/config/model/wheel testy: **57 passed / 5 expected skips**. Dvě finální native SQL kompilační regrese prošly po doplnění kontrol korelace ACL.

Release zachoval existující MI, Key Vault reference, credentials, SQL identity/data, tři uložené konfigurace, helper image, ACA 0,75 CPU/1,5 Gi/min1/max1 a oba existující SWA cíle. Žádné nové DDL, reembedding, aktivace ANN či změna modelových limitů. Dokončený [handoff](2026-10-30-cloud-stabilization-handoff.md) rozlišuje schválené S2 a samostatně schválený release. Chráněné template a datové/config checkpointy jsou uložené; překryv VPN replik byl vyloučen.

Po nasazení byly ověřeny oba UI, přihlášení, reprezentativní otázky, citace/provenance, uložená historie, PDF a role. Obnova po textové504/5xx/stale401 je pokrytá izolovanými JS regresemi; nebyla provedena nová umělá produkční porucha gateway. Uživatel dodal testovací otázky a přihlašovací údaje přímo pro toto ověření; heslo se neukládá do zdrojů, reportu ani privátních operačních skriptů.

Privátní diagnostika je v ignorovaném `.local/stabilization-20261030/`, dokončené release/DPAPI/baseline/build/preservation/QA/cleanup/live asset receipts v `.local/deployments/stabilization-20261030-093449/`. Standardní postup na těchto scratch skriptech nezávisí. Žádný commit, push ani Forgejo release nebyl proveden.
