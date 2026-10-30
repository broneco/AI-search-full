# Azure Deployment Handoff: JHU test zachování dat

- Status: completed, 2026-10-30
- Created: 2026-10-30
- Authorization: uživatel po návrhu skutečné výměny image s před/po kontrolami napsal „Ok spusť jej prosím.“ Schválené ukončení pouze lokální administrace port3001 kvůli92GB virtuální paměti je dokončené; SQL/backend/cloud tím nebyly zastaveny.
- Source publication: žádný commit/tag/push/Forgejo ani frontend release.

## Cíl a hranice

Prokázat zachování původních účtů/heslových hashů/skupin/historie/dokumentů/chunků/ACL/vektorů a uložených konfigurací při nasazení nové image. Zahrnout nově uživatelem naplněný Nomic index. Připravený veřejný verify_deployment.py pořizuje pouze read-only checkpointy; izolované regrese musí před produkčním zápisem projít.

## Přesné cíle

- Subscription24e4a9a6-bab0-43f7-ba20-3b774704fade, directoryc35f5da4-9a03-44e6-8bf9-92833634f6a7.
- RGju-ai-search-rg-prod, Sweden Central, ACAju-ai-search-ca-prod.
- SQLju-ai-search-sql-prod.database.windows.net / ju-ai-search-sqldb-prod, přesný tenantju-prod. Zachovat S2/50DTU/maxsize.
- ACRjuaisearchcrprod: sestavení nové image ze zkontrolovaných veřejných zdrojů, bez nové placené resource. Backend image se liší přidáním read-only testovacího nástroje; runtime app/tenant/fixture zdroje porovnat s dokončeným rolloutem.
- Původní revizestable-1030-093449, backenddigestaa7f50e01141c2e5d0bb47344697d62324832421a68a63cd1bfba403bf63c54a; helperdigest006c3070ecc2295cfd34d0c80e34c30d006d2bfe57d3e6aa7c58daa723275de3 zůstává.
- ACA zachovat backend0.5CPU/1Gi +helper0.25CPU/0.5Gi, min1max1, identity/env/secrets/references/probes/registry/ingress; pouze nová backend image a suffixrevize. Veřejný ingress dočasně internal pro klid zápisů, po testu obnovit přesně.
- Zachovat indexAzureb1e81c70-686c-481a-bbff-e15f034288ef jakoingestiondefault a Nomicc536b88c-8df6-4280-8063-ff8d2bb273a9 jakoexperiment; oba předem požadovat úplné/neprázdné. Aktuální počty zjistit capture, neodvozovat pouze z posledního výpisu9372.
- Storage a originály pouze číst/hashovat; nová data/záložní resource, RBAC, secrets, kvóty a kapacity se nemění. Obě SWA se nenasazují.

## Operace

1. Lokální izolované SQLite/MSSQL a public export regrese, syntaxe/navigace/projekce. Před buildem ověřit app/tenant/fixture soubory vůči stabilizačnímu source receipt.
2. Read-only account/app/SQL/resource/imageguard a ověření konzolového přístupu. Pokud přístup či test selže, žádný deploy.
3. Soukromý nový rollback checkpoint ARM (DPAPI), zachovat původní immutable image, nová image v existujícím ACR, canonical read-only plan bez změn env/capacity.
4. Freeze ingress, počkat na doběhnutí zápisů; veřejným nástrojem zachytit beforemanifest + skutečné Blobbytes. Originální config přečíst i přes API/loader; hesla/obsah nezapisovat do veřejných logů.
5. Stop app, potvrdit0starých replik, guardedimage-onlytemplatepatch, start a readiness. Neukládat runtimeenv do argumentů/plaintextu. Nevytvářet souběžné VPN relace; lokálníhelperzůstáváOFF.
6. Stejný veřejný nástroj: aftermanifest, offlinecompare --require-new-revision. Požadovat state_preservedtrue/blobs_checkedtrue, stejnésettings/model/active/obaindexyvektory; ověřit template/identity/config bezezměny.
7. Obnovit veřejný ingress a funkčně zkontrolovat původní účet/session, staroukonverzaci/PDF, správní nastavení, JHUready a citovaný dotaz přeskaždýindex. Nové vlastníQA zprávy evidovat odděleně od baseline. Výsledek není relevanční benchmark.

## Rollback

Při problému image/startupu vrátit přesně původní backend image ve zkontrolovaném template, helper/env/identity/data zachovat; nejprve0VPNreplik, potomstart a znovuotevřítingress. Nikdy automaticky neimportovat defaults, nespouštět reembedding ani neobnovovat produkčníDB přes stávající data. Při datovém rozdílu zachovat manifesty a zjistit příčinu, obnovu řešit samostatně.

## Akceptace a receipts

Dokončení doložit konkrétní novou immutable image/revizí, stejnými všemi datovými a Blob otisky a funkčními výsledky. Privátní artefakty pod .local/deployments/preservation-<UTCstamp>/, veřejný dokončený report v docs/deployments/. Dokud tato evidence nevznikne, nehlásit cloudový test jako hotový.

## Dokončený výsledek

Schválený test byl proveden; skutečná image/revize, všechny shodné otisky, funkční akceptace a otevřená relevance jsou v [dokončeném reportu](2026-10-30-preservation-test.md). Obnovený veřejný ingress/obě SWA/API200, JHUready. Privátní receipts .local/deployments/preservation-20261030-151331/. Neopakovat již dokončený rollout.
