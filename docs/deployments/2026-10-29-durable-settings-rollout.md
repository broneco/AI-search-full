# JHU deployment 2026-10-29: trvalá nastavení a ověřený restart

- Status: completed — migrace, backend release a skutečná cloudová akceptace
- Autorizace: uživatel výslovně schválil nasazení připraveného převodu nastavení.
- Rozhodnutí: [ADR-0042](../adr/ADR-0042-durable-tenant-settings.md).
- Postup pro další prostředí: [aktualizace se zachováním dat](../development/non-destructive-updates.md).
- Zdrojová verze: v0.1.7 + pracovní změny; žádný nový Git commit/tag/push, GitHub ani Forgejo release.

## Skutečný výsledek

| Položka | Výsledek |
|---|---|
| Subscription / directory | `24e4a9a6-bab0-43f7-ba20-3b774704fade` / `c35f5da4-9a03-44e6-8bf9-92833634f6a7` |
| Resource group / region | `ju-ai-search-rg-prod` / swedencentral |
| Aktivní revize | `ju-ai-search-ca-prod--durable-1029-201612` |
| Předchozí revize | `ju-ai-search-ca-prod--jhu-v017-1029-173112`; během přepnutí zastavena před novou VPN relací |
| Nový backend image | `juaisearchcrprod.azurecr.io/ju-ai-search-ca-prod@sha256:9c87ef3a5a8fa557fc2f225fdbd67faf79ec88d70619f2e6b59dfc50499e9416`; ACR build run `dtn` |
| Helper | Původní digest `sha256:006c3070ecc2295cfd34d0c80e34c30d006d2bfe57d3e6aa7c58daa723275de3`, stejné env/probes |
| SQL / přesný tenant | `ju-ai-search-sql-prod.database.windows.net` / `ju-ai-search-sqldb-prod` / `ju-prod` |
| Jediná nová tabulka | `tenant_settings`, tři importované JSON dokumenty |
| SQL tier / kapacita | Standard10DTU; backend0,5CPU/1Gi + helper0,25CPU/0,5Gi, min1/max1; beze změny |
| Účty / konverzace / zprávy | **4 / 41 / 66** zachovaných původních záznamů |
| Dokumenty / chunky / vektory | **431 / 9372 / 9372**, stejné otisky obsahu |
| Aktivní index | `b1e81c70-686c-481a-bbff-e15f034288ef`, nadále exact |
| Veřejný backend | [JHU backend](https://ju-ai-search-ca-prod.mangosky-3e5a7049.swedencentral.azurecontainerapps.io) |
| Frontendy, MI, credentials, ingress | Obě SWA beze změny; původní identita/konfigurace/env/secret reference a veřejný ingress obnoveny a porovnány |

## Provedený převod

1. Ověřen skutečný Azure účet, běžící cílová revize, SQL a existující Management identita. Ověřena Online databáze a sedmidenní PITR historie; nejde o provedený restore drill. Původní ARM template a konfigurace uložené šifrovaně pomocí Windows DPAPI.
2. Z původního ACA kontejneru zachyceny CS/EN prompty, synchronní soubory, async efektivní search/classification a případné legacy Blob kopie. Všechny účinné hodnoty se shodovaly se soubory; obě legacy Blob konfigurace nebyly přítomné. Neimportovaly se nové checkout defaults místo živých hodnot.
3. Sestaven backend v existujícím ACR, ověřen neměnný digest, zdrojové hashe a plán bez blockerů. Žádná změna helper image, modelů, secrets/RBAC, SQL tieru, originálů ani frontendů.
4. Pro konzistentní závěrečný export dočasně nastaven ingress `external=false`. Platforma změnila FQDN na interní variantu; další konfigurace zůstala stejná. Závěrečný export měl stejné hashe jako první. Potom aplikace zastavena a skutečně ověřeno0replik před novým VPN přihlášením. Výpadek byl řízený, bez příslibu zero-downtime.
5. Při zastavených writerech zachyceny per-row SHA256 otisky existujících tenantových tabulek a nativních vektorů. Účty a historie mají navíc úplný šifrovaný logický checkpoint. Guarded `migrate_tenant_settings.py` po read-only plánu a kontrole přesného host/DB/tenant importoval pouze3chybějící řádky v nové tabulce. Žádný reset/backfill/reembedding/index activation ani opakování čtyř předchozích modelových migrací.
6. Guarded `apply_plan` s konkrétním fingerprintem/revizí aktualizoval jen backend image a revision suffix v zachovaném dvoukontejnerovém template. Start následoval až po ukončení původní relace.

## Skutečná cloudová akceptace

- Nová revize byla Ready. Při stále vypnutém veřejném ingressu prošel skutečný Management `PUT /api/prompts`200 s dočasným rozlišovacím promptem, SQL revision2. Celá aplikace byla zastavena na0replik a znovu spuštěna; nová replika načetla přesně uloženou změnu. Původní prompty pak obnoveny přesně, revision3. Žádný běžný uživatel nebyl během této zkoušky vystaven testovacímu promptu.
- Všechny3konfigurační API200. API, synchronní search/ingest load, async klasifikace a skutečné SQL řádky se shodují. Prompts/search/classification hashe odpovídají finálnímu předmigračnímu exportu; revize3/1/1.
- Per-row porovnání potvrdilo totožnost všech původních účtů včetně heslových hashů/skupin, vláken/zpráv, dokumentů/chunků, nativních vektorů, search/active indexů a modelových tabulek. Počty se nahradily kontrolou konkrétních ID a otisků, nikoli pouze součtů.
- Veřejný ingress a původní FQDN byly obnoveny. Celá původní `identity` a `configuration` se shodují; celý finální template odpovídá původnímu kromě backend image a revision suffix. Health200, existující účet `/auth/me`200, původní konverzace200 a skutečný PDF náhled200 s `%PDF` hlavičkou.
- Skutečný heslový login byl ověřen pouze přes vlastní dočasný User účet vytvořený správcem. Login a `/auth/me`200, Management discovery403. Účet odstraněn s přesným UUID+email+tenant guardem; původní hesla nebyla známa, zadávána ani resetována. Zachování původních účtů dokládá jejich identita a totožné heslové hashe, vedle existující serverové autentizace.
- JHU připojení skutečně `sidecar/ready`; testy nepoužily lokální VPN helper. Nový RAG/performance benchmark ani aktivace jiného indexu se neprováděly. Dříve otevřený Management exact/vector SQL timeout10s zůstává odděleným nevyřešeným problémem.

## Checkpointy, zdrojové testy a hranice

Soukromé receipts jsou v `.local/deployments/durable-settings-20261029-201612/`: DPAPI before/after ARM, initial/final nastavení, původní účty/historie, SQL before/after hashe, PITR policy, source manifest, ACR build/digest, migration plan/result, reviewed plány, skutečný API save/restart/restore proof, runtime shoda a veřejná akceptace. Credentials a citlivý obsah se nevypisovaly a nejsou součástí zdrojů/JHU exportu.

Před nasazením prošla úplná izolovaná sada včetně skutečného wheelu **572 passed /116 expected skips**, čistý JHU settings/resolver/API/wheel **34 passed**; předtím cílená87/11. Cloudové kroky výše jsou samostatné skutečné důkazy. Nenahrazují dlouhodobý soak, výkonovou akceptaci, klientské CAS/historii nastavení ani ověření obnovy zálohy.

## Návrat a další krok

Při pozdějším návratu nejprve zastavit novou VPN revizi a ověřit0replik, pak obnovit předchozí image/template se stejnou DB, přesným tenantem a klíči. Nedropovat tenant_settings, dokumenty ani indexy. Starý backend SQL overrides nečte: při zastavených správních editacích explicitně exportovat nejnovější SQL hodnoty a obnovit souborové/Blob konfigurace ze zkontrolovaného checkpointu. Pouhá aktivace původní image nezaručuje návrat souborových změn. Veřejný ingress obnovit podle původního template.

Jediný doporučený další slice: ověřit obnovu zálohy do izolovaného prostředí, se samostatným plánem potřebných zdrojů a bez zásahu do živé databáze.
