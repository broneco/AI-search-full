# JHU publikace: skutečné Git snapshoty a bezpečná synchronizace

Aktuální veřejný `jhu_connection.py` a `scripts/vpn_spike/` se od aplikační integrace předávají také. Test výslovně kontroluje runtime/manager/gateway/service/profile a Docker context, současně vyloučí jiné interní scripts. Manager nesmí záviset na neexportovaném experimentálním root probe. `.ovpn`/`.auth` se nikdy nepředávají.

`tests/test_jhu_publication.py` vytváří vlastní dočasné Git repozitáře a commity, bez sítě a cloudových credentials. Ověřuje export neměnného refu, ignorování pracovních změn a privátních souborů, materializaci samostatného JHU a odmítnutí driftu formátu. Fixture kopíruje veřejné zdroje, aby byly kontrolovatelné i skutečné dokumentační odkazy.

Regrese úplnosti zachovává všechny veřejné dokumenty mimo ADR, celé README, release historii a podrobné vysvětlení testů. Stručná template nesmí původní návod přepsat. Obsah porovnává po normalizaci Windows konců řádků. Odkazy na ADR jsou prostý text; ostatní odkazy musí zůstat platné v balíčku nebo mířit na odpovídající upstream vydání. ADR soubory ani jejich template se do předání nedostanou.

Celá izolovaná sada musí fungovat také z JHU-only balíčku. Session fixture v `tests/conftest.py` proto při chybějícím bundled `tenants/default/` vytvoří z veřejných JHU modelových a embeddingových JSON dočasný testovací fallback overlay pro syntetické tenanty. Tento obecný fallback obsahuje jen Azure baseline, stejně jako hlavní `tenants/default/`; JHU-only modely se testují explicitně. Ostatní JSON, prompty ani privátní env se nekopírují. Runtime ani předávaný tenantový strom se tím nemění.

Testy synchronizace procházejí read-only plán, explicitní Apply na EMPTY i další commit, plánované odstranění stale souboru a zachování Git historie i ignorovaného lokálního env. Odmítají nečistý checkout, jiný origin/větev, záměnu manifestu/ZIPu, nebezpečné cesty a symlinky. Test neprovádí skutečný push, nezjišťuje oprávnění Forgejo a nic nenasazuje do Azure.

Spuštění: `python -m pytest tests/test_jhu_publication.py -q`. Parent temp adresář musí existovat, pokud ručně zadáváš vnořený `--basetemp`.

Export musí obsahovat také úplný JHU embedding_config bez credentials a aktuální návod pro Nomic/backfill/aktivaci.

Fixture i čistý export zahrnují local_model_recipes.json a aktuální návod registrace lokálních modelů; runtime tenantová schválení a privátní připojení se do archivu nekopírují.

Současný čistý JHU export ověřuje i deploy_jhu_sidecar.py, scripts/deployment/jhu_sidecar.py, helper cloud.py a cloudový runbook. Vývojová historie a skutečné secrets/profily zůstávají vyloučené.

Export zahrnuje také veřejný verify_deployment.py a aktuální deployment-preservation-test.md. Dočasné fixture Git příkazy mají pouze pro konkrétní proces core.longpaths=true, aby vnořený Windows workspace nepřekročil limit cest; globální Git konfiguraci nemění.
