# Azure handoff: JHU cloud stabilizace

- Status: completed; schválené S2, backend a oba SWA nasazeny, data/config a provozní QA ověřeny; relevance obecného R_583 zůstává otevřená.
- Datum: 2026-10-30
- Scope: cloud admin i user; lokální funkce ani nové embedding indexy nejsou aktuální priorita.

## Důkazy a navržená změna

Tři veřejné health sondy přes10s timeout. ACA původní revize durable-1029-201612, Running/Healthy,1replika,0restartů. Za poslední4h minutové CPU kontejneru nejvýše4%, paměť19,5%; odezvy až240s. SQL CPU/DTU maximum100% ve46minutách, poslední minutaavg98,75%; dataIO0/logIO0. CPU je prokazatelný kapacitní problém. Pozorované nadbytečné SQL dotazy a blokování event loopu jsou samostatný problém zdrojů.

Přesný cíl: `/subscriptions/24e4a9a6-bab0-43f7-ba20-3b774704fade/resourceGroups/ju-ai-search-rg-prod/providers/Microsoft.Sql/servers/ju-ai-search-sql-prod/databases/ju-ai-search-sqldb-prod`, tenant `ju-prod`, region `swedencentral`. Ověřený původní SKU: `{"name": "Standard", "tier": "Standard", "capacity": 10}`, objective `S0`, maxSizeBytes `268435456000`. Navrženo pouze service objective **S2 /50DTU**, ze současného S0/10DTU. Žádný nový server/DB, storage resize, schema migrace, reembedding, aktivace indexů, secrets/RBAC, model provisioning ani změna ACA/SWA kapacity. SKU navýšení může krátce přerušit SQL spojení.

Microsoft Retail Prices API pro Sweden Central/EUR/SQL Database Single Standard dne2026-10-30: S0=0,4258EUR/den, S1=0,8515EUR/den, S2=2,1295EUR/den. S2 přírůstek proti S0=1,7037EUR/den (~51,11EUR/30dní). Jsou to veřejné orientační ceny bez DPH a bez individuální Enterprise smlouvy; fakturace se může lišit. Zdroj: https://prices.azure.com/api/retail/prices , filtr serviceName SQL Database, armRegionName swedencentral, Consumption. Při testu preferujeme S2, menší S1 nelze považovat za výkonovou akceptaci bez měření.

## Aplikace a pořadí

1. Uchovat nový DPAPI app checkpoint, hashované baseline původních účtů/historie/korpusu/aktivního indexu a3konfigurace; ověřit aktuální live target proti očekávání. Zachovat přesnou identitu, DB a klíče.
2. Po konkrétním schválení SQL změny provést read-only plan a target/SKU guarded změnu pouze existující DB na S2; ověřit výsledek, žádné automatické zvyšování dalších resources.
3. Připravit a otestovat zdrojové opravy: dokumentový přehled jedním ACL-scoped agregovaným dotazem mimo event loop, bezpečné JSON/timeout chyby, neodhlašování při5xx, obnovitelné katalogy a vysvětlení blokovaného dotazu. Případný nový backend/SWA release má vlastní přehled diffu/buildy a aktuální fingerprint. Nový deployment musí být schválený pro tento slice; předchozí durable-settings deployment není univerzální souhlas.
4. Stejné dokumenty, původní index a otázky; oddělit login/katalogy/dokumenty/SQL retrieval/model generation/health souběh. Management i User bez obcházení ACL. Existující účet přihlásit bez předávání hesla do chatu; případné syntetické účty/konverzace odstranit jen přes vlastní UUID/tenant guards. Žádný upload privátních dokumentů nebo reset.
5. Ověřit zotavení po504/ne-JSON/401 a stav odeslání. Žádné překrývání health pollů. JHU VPN testy pouze přes stávající ACA sidecar, žádná souběžná lokální VPN relace se stejným účtem.

## Návrat

SQL zpět na původní S0/10DTU pouze po potvrzení ukončení testu a kapacity/velikosti, nikoli vynuceně během zatížení. Identita/databáze/obsah/tabulky zůstávají. Aplikaci případně vrátit na uložený image/template, respektovat0starých VPN replik před novou relací;3trvalé konfigurace ani nové tabulky nemazat. Původní source/runtime data checkpoint zachovat; žádné reset/mirror/force-push. Další SKU změna vyžaduje nové posouzení.

## Potřebné od uživatele

- S2 uživatel konkrétně schválil a bylo aplikováno; bez explicitního limitu, ale všechny další placené změny předem projednat. Na konci testu vyhodnotit ponechání/návrat.
- Uživatel dodal otázky k R_583 a organizačním útvarům i login přímo pro cloudový test. Přihlášení do obou SWA prošlo; heslo není v souborech/reportu. Potřebné je schválení následující konkrétní nové verze.


## Konkrétní nový release — ke schválení

- Subscription `24e4a9a6-bab0-43f7-ba20-3b774704fade`, directory `c35f5da4-9a03-44e6-8bf9-92833634f6a7`, RG `ju-ai-search-rg-prod`, přesný tenant `ju-prod`.
- Existující ACR `juaisearchcrprod`: sestavit právě ověřené zdroje do nové backend image, uložit digest a před aktualizací znovu porovnat source/target fingerprint.
- Existující ACA `ju-ai-search-ca-prod`: změnit pouze backend image a unikátní suffix revize. Původní active revision `durable-1029-201612`, backend digest `9c87ef3a5a8fa557fc2f225fdbd67faf79ec88d70619f2e6b59dfc50499e9416`; helper digest `006c3070ecc2295cfd34d0c80e34c30d006d2bfe57d3e6aa7c58daa723275de3` zachovat. Před novou relací zajistit nulu starých VPN replik; očekává se krátké okno nedostupnosti. Zachovat MI, secrets, env, veřejný ingress/FQDN, probes a měřené resources/scale.
- Existující SWA `ju-ai-search-swa-user-prod` a `ju-ai-search-swa-admin-prod`: nasadit nové statické buildy s tématem `jhu` a stejným backend URL `https://ju-ai-search-ca-prod.mangosky-3e5a7049.swedencentral.azurecontainerapps.io`; nevytvářet další SWA. Předem uložit dostupné staré assety pro rollback, token jen přes child env.
- Změny: dvě dávková katalogová SQL čtení, scoped hash joins v exact dotazu, synchronní retrieval/SQL mimo event loop, bezpečná a obnovitelná metadata UI a přihlašování. Přehled a úplné ověření v `docs/deployments/2026-10-30-cloud-stabilization.md`.
- Žádná další kapacita, změna SQL S2, DDL, backfill, ANN, přepnutí indexu, reset účtů/konfigurací, provisioning modelů, RBAC nebo VPN účtu. Jde pouze o obvyklý build a release do existujících resources. SQL corpus/účty/historie/konfigurace checkpointovat a po rollout porovnat; případné vlastní testovací konverzace rozlišit od původních dat.
- Rollback: uložený původní backend template/image a obě sady SWA assetů; nejprve ukončit novou VPN relaci, potom stará image. SQL tabulky ani trvalá nastavení nemazat. Návrat S2 na S0 je samostatné rozhodnutí po testu.
- Žádné nové lidské konfigurační hodnoty/secrets nejsou potřeba. Po schválení vyhodnotit oba UI a skutečné otázky, citace, role, obnovu po 504 a současnou dostupnost health. Dosavadní browser dotaz na staré revizi měl search_timeout; není to akceptace nové image.

## Dokončení

Aktivní stable-1030-093449, backend aa7f50e01141c2e5d0bb47344697d62324832421a68a63cd1bfba403bf63c54a, původní helper/ostatní kapacity/identity/keys/index zachovány. Původní datové a config otisky stejné; finální audit původní historie/účtů/corpusu/settings prošel. Vlastní User/thready odstraněné. Veřejné HTML+8/10assetů/CORS obou SWA ověřeny, skutečné Mini i Qwen RAG200/citace/historie, PDF200 a User HR404. Lokální projektový VPN helper vypnutý; po jediné nové cloudové relaci JHU ready1/TLS1. [Úplné důkazy a otevřený obsahový test](2026-10-30-cloud-stabilization.md). Předchozí návrhové body dokumentují schválený plán, ne čekající akce.
