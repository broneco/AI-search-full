# JHU: ověření aktualizace se zachováním dat

**2026-10-30: skutečný test nové backendové image prošel.** Před/po výměně kontejneru se shodovaly všechny chráněné SQL řádky včetně obou profilových vektorových tabulek, runtime otisky identity/připojení/klíčů, uložené konfigurace a byte obsah všech431odkazovaných PDF. Po funkčních testech a úklidu vlastních QA konverzací byl znovu potvrzen přesně stejný SQL stav. Nejde pouze o srovnání počtů ani o restart téže revize.

## Skutečné nasazení

- Uživatel po přípravě testu výslovně požádal „Ok spusť jej prosím.“ [Dokončený plán a rollback](2026-10-30-preservation-test-handoff.md).
- Původní revize `ju-ai-search-ca-prod--stable-1030-093449`, backend digest `aa7f50e01141c2e5d0bb47344697d62324832421a68a63cd1bfba403bf63c54a`.
- Nová revize **`ju-ai-search-ca-prod--preserve-1030-151331`**, backend `juaisearchcrprod.azurecr.io/ju-ai-search-ca-prod@sha256:5d5b6f6b45af7f1df5d863fcd08402028a669367f4c034d72dc78bdf12c6000f`, ACR run `dtq`; nová replika `preserve-1030-151331-558c879568-pdjr6`.
- Aplikační/tenantové/fixture zdroje a pyproject odpovídaly dokončenému stabilizačnímu rollout receipt. Image přidala veřejný read-only `verify_deployment.py`; jeho skutečný SHA256 uvnitř nové image `981eeb00c308adaa4cd767c8666b626523024677f05d2557dd9a8f7af4d84eac` odpovídá kontrolovaným zdrojům.
- Source/runtime nadále v0.1.7 s pracovními změnami. Žádný Git commit/tag/push/Forgejo ani release frontendů.
- Stejný přesný `ju-prod`, SQL host/DB, Storage, MI, credentials/references, helper image, ingress po obnovení, probes a registry. SQL zůstává **S2/50DTU**, ACA backend0,5CPU/1Gi +helper0,25CPU/0,5Gi, min1/max1. Žádné nové resources, schéma, reembedding, ANN, publikace modelů, přepnutí ingestace ani další navýšení kapacit.

## Zachovaný stav

| Oblast | Před | Po / po úklidu |
|---|---:|---:|
| Účty včetně heslových hashů/skupin | 4 | 4 |
| Konverzace / zprávy | 45 / 72 | 45 / 72 |
| Dokumenty / chunky | 431 / 9372 | 431 / 9372 |
| Document ACL / chunk ACL grants | 761 / 16677 | 761 / 16677 |
| Embedding profily / indexy / aktivní pointer | 2 / 2 / 1 | 2 / 2 / 1 |
| Azure vektory | 9372 | 9372 |
| Nomic vektory | 9372 | 9372 |
| Uložené SQL konfigurace | 3 | 3 |
| Odkazované Blob originály | 431 | 431 |

Všechny celé řádky mají stejné agregované SHA256 otisky, nejen počty. Modelové registry/access/descriptions/runtime tabulky zůstávají prázdné a stejné. Původní vlastní prompty, chunkování, vyhledávání, shrnutí a klasifikace mají stejný SQL payload/revizi; běžící správní API a synchronní loadery vracejí odpovídající hodnoty.

Azure index `b1e81c70-686c-481a-bbff-e15f034288ef` zůstává ingestion default; Nomic `c536b88c-8df6-4280-8063-ff8d2bb273a9` zůstává samostatný experiment. Oba mají úplné pokrytí9372/9372. Nomic vznikl a byl uživatelem naplněn před tímto testem; nebyl zde znovu přepočítáván.

Přímo z Blob Storage byly před/po streamovány všechny přesně odkazované soubory: **141119258 bytes**, stejný agregovaný digest `8442ebb9f35b4d6b49c044930858609245f3af7dff932973afec9a2ab8c251cd`. Cache a podobné názvy nebyly použity. Po následném QA se opakovala SQL kontrola; další plné Blob čtení již nebylo potřeba, QA provádělo pouze GET originálu.

## Funkční akceptace

- Management auth/me200 se správným tenantem; existující historie200/4zprávy; původní PDF200/platná%PDFhlavička.
- Existující obyčejný User auth200 a Management endpoint403. Žádný účet, heslo ani skupina se nevytvářely/neměnily.
- Seznam431dokumentů200 za0,080s, oba připravené indexy200 za0,235s, summary/classification katalogy200. Prompty, search/chunking/summary a classification API odpovídají zachovanému SQL; synchronní loader také.
- JHU sidecarready, attempts2/generation1/TLS1. Po změně image nevznikly souběžné VPN relace: nula starých replik byla potvrzena ještě před apply/start. Lokální helper nebyl spouštěn.
- Stejná explicitní otázka k R_583, `vector`, GPT-5.4-mini: Azure **200/3,316s**, Nomic **200/6,297s**. Obě odpovědi mají5zdrojů, správný skutečný model/index a2uložené zprávy v samostatném vlastním QA vláknu. Obě nová vlákna byla přes jejich přesné vrácené UUID odstraněna; finální SQL otisky všech původních řádků včetně historie jsou stejné jako před testem.
- Původní veřejný ingress a úplná ARM konfigurace/identity/helper/kapacity byly porovnány, veřejný health200 potvrzen.
- Obě veřejné SWA vracejí HTML200 a CORS200; veřejné autentizované auth/me, indexy a JHU connection také200. Poslední JHU stavready/attempts2/generation1/TLS1.

**Relevance je samostatně otevřená:** Azure u explicitní otázky citovalo R_583, Nomic mezi vrácenými zdroji R_583 nemělo. Technická funkčnost nového indexu ani tento preservation test neznamenají, že je Nomic pro dané otázky kvalitnější. Jediný doporučený další slice: vyhodnotit relevanci a ranking Azure/Nomic na uživatelem dodaných otázkách a referenčních dokumentech, beze změny ACL a neměnných embeddingových profilů.

## Průběh a hranice důkazu

Servisní okno bylo přibližně15minut: požadavek na interní ingress **16:23:33**, požadavek na obnovení veřejného ingressu **16:38:13 CET (Europe/Prague)**, dostupnost následně potvrzena HTTP200. Toto byl test se zachováním dat, nikoli nasazení bez výpadku. Před vlastní výměnou proběhlo sestavení image za běhu aplikace.

Azure konzole několikrát vrátila handshake401, včetně standardního CLI po vzniku nové repliky. Následné připojení standardním CLI uspělo. Dlouhé výstupy byly přeneseny v číslovaných blocích a jejich přenos ověřen SHA256; žádná poškozená/neúplná kopie nebyla přijata jako úspěšný checkpoint. Vložený browser při závěrečném GUI reloadu timeoutoval; nové GUI/password-login ověření se proto nepovažuje za provedené. Autentizace existujících účtů přes API, zachování heslových hashů a ostatní uvedené kontroly jsou skutečné.

Na notebooku test nejprve blokovala vyčerpaná virtuální paměť: uživatel schválil ukončení ověřeného lokálního Next.js admin serveru na3001 (launcher39164/worker27416, přibližně92GBprivate memory). Oba tyto procesy byly ukončeny; lokální SQL/backend a cloudové resources tím nebyly zastaveny. Lokální administrace zůstala vypnutá, automaticky se nerestartovala.

## Opakovatelnost a ověření zdrojů

[Veřejný nástroj a runbook](../development/deployment-preservation-test.md) umožňuje zachytit/porovnat další release bez privátních scratch operátorů. Izolované SQLite+skutečný lokální SQL Server/config testy: **60passed**. Čistý JHU export: **18passed**; fixture podporuje dlouhé Windows cesty jen procesovým Git nastavením. Nový plný běh celé aplikační sady nebyl pro tento read-only nástroj prováděn; žádné aplikační/tenantové runtime zdroje se proti již ověřené verzi nezměnily. Azure nativeVECTOR a skutečné Blob bytes mají navíc tento živý důkaz. Nejde o obnovu zálohy ani o schválení bezpečnosti budoucích destruktivních migrací.

Privátní DPAPI rollback ARM, image/build/plány, všechny před/po/final manifesty, porovnání, funkční a veřejné kontroly jsou v ignorovaném `.local/deployments/preservation-20261030-151331/`. Manifesty obsahují otisky a metadata, ne texty dokumentů/promptů/zpráv, heslové hashe, vektory nebo credentials. Jsou důkazem zachování, nikoli zálohou pro obnovu.
