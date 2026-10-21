# JHU publikace: skutečné Git snapshoty a bezpečná synchronizace

`tests/test_jhu_publication.py` vytváří vlastní dočasné Git repozitáře a commity, bez sítě a cloudových credentials. Ověřuje export neměnného refu, ignorování pracovních změn a privátních/historických souborů, materializaci samostatného JHU, dokumentační templates a odmítnutí driftu formátu.

Testy synchronizace procházejí read-only plán, explicitní Apply na EMPTY i další commit, plánované odstranění stale souboru a zachování Git historie i ignorovaného lokálního env. Odmítají nečistý checkout, jiný origin/větev, záměnu manifestu/ZIPu, nebezpečné cesty a symlinky. Test neprovádí skutečný push, nezjišťuje oprávnění Forgejo a nic nenasazuje do Azure.

Spuštění: `python -m pytest tests/test_jhu_publication.py -q`. Parent temp adresář musí existovat, pokud ručně zadáváš vnořený `--basetemp`.

Export musí obsahovat také úplný JHU embedding_config bez credentials a aktuální návod pro Nomic/backfill/aktivaci.

Fixture i čistý export zahrnují local_model_recipes.json a aktuální návod registrace lokálních modelů; runtime tenantová schválení a privátní připojení se do archivu nekopírují.
