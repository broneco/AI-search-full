# Předávání zdrojů JHU

Hlavní vývojový repozitář a zákaznický Forgejo repozitář mají oddělené historie. Hlavní repo uchovává kompletní vývoj; `dconsulting/jhu-ai-search` obsahuje pouze JHU snapshoty a jejich souhrnné aktualizace. Samotné nahrání zdrojů nenasazuje Azure.

Verzované nástroje:

- `export_jhu.py --ref <tag-nebo-commit> --output <nový.zip>` vytvoří JHU-only balíček z commitnutého zdroje.
- `prepare_jhu_publication.py --archive <zip> --destination <samostatný-clone>` zobrazí read-only plán.
- Tentýž příkaz s `--apply --expect-head <ověřené-SHA>` změní jen plánované zdrojové soubory, nikoli Git index/refy nebo cloud.

ZIP zachovává úplnou veřejnou dokumentaci hlavního projektu včetně README, changelogu, release notes, deployment reportů a podrobných vysvětlení testů. Vynechává pouze ADR soubory; odkazy na ně převede na prostý text. Odkazy na známé zdrojové soubory vynechané z JHU balíčku směřují na odpovídající vydání hlavního repozitáře. Neznámé nefunkční odkazy export odmítne.

Runtime konfigurace a branding obsahují pouze JHU. Obecné příklady jiných tenantů v dokumentaci jsou zachované jako kontext. Původní `.git`, privátní env, dokumentová data, secrets, dependency/cache a archiv agentní paměti se nepředávají. Plné zdrojové návody mají přednost před stručnými templates; templates doplňují chybějící návody a samostatné agentní instrukce. Provenience zůstává v sousedním neveřejném manifestu, nikoli v zákaznickém Git grafu.

Úplné příkazy, validační brány, práce s cizími změnami, navazující souhrnné commity, obnovení po přerušení a oddělený Azure release jsou v [kanonickém AI workflow](../../.agents/workflows/jhu-publication.md). Postup je obnovitelný po novém klonu a nevyžaduje původní `.local` skripty. `.local` obsahuje pouze lokální checkout a odvozené artefakty.
