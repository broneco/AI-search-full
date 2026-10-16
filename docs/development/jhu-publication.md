# Předávání zdrojů JHU

Hlavní vývojový repozitář a zákaznický Forgejo repozitář mají oddělené historie. Hlavní repo uchovává kompletní vývoj; `dconsulting/jhu-ai-search` obsahuje pouze JHU snapshoty a jejich souhrnné aktualizace. Samotné nahrání zdrojů nenasazuje Azure.

Verzované nástroje:

- `export_jhu.py --ref <tag-nebo-commit> --output <nový.zip>` vytvoří JHU-only balíček z commitnutého zdroje.
- `prepare_jhu_publication.py --archive <zip> --destination <samostatný-clone>` zobrazí read-only plán.
- Tentýž příkaz s `--apply --expect-head <ověřené-SHA>` změní jen plánované zdrojové soubory, nikoli Git index/refy nebo cloud.

ZIP neobsahuje původní `.git`, interní historii dokumentace, jiné klienty, secrets ani dependency/cache. Současné návody a JHU konfigurace vznikají z verzovaných `publication/jhu/templates/`; změny formátu zdroje export bezpečně odmítne k revizi. Provenience je v sousedním neveřejném manifestu, nikoli v zákaznickém Git grafu.

Úplné příkazy, validační brány, práce s cizími změnami, navazující souhrnné commity, obnovení po přerušení a oddělený Azure release jsou v [kanonickém AI workflow](../../.agents/workflows/jhu-publication.md). Postup je obnovitelný po novém klonu a nevyžaduje původní `.local` skripty. `.local` obsahuje pouze lokální checkout a odvozené artefakty.
