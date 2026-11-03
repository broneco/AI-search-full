# Testy propojeného editoru indexů

`tests/test_index_editor.py` používá stejné izolované SQLite/lokální SQL fixtures a deterministické modely jako příprava indexů. Nevstupuje do provozní databáze ani JHU API.

- Jednorázové převzetí současné konfigurace funguje i pro dříve pojmenovaný index bez snapshotu. Další otevření se změněnými globálními hodnotami existující snapshot nepřepíše a nepřepočítá vektory.
- Nový index vzniká a plní se jednou úlohou. Úprava zachová logický UUID, schová fyzické verze z katalogu a přepne název/parametry až po dokončení; staré citační texty zůstávají dostupné.
- Selhání modelu nechá původní funkční verzi a její vektory dostupné. Opakování stejných parametrů pokračuje ve stejném nedokončeném korpusu.
- Úprava původního defaultu zachová ingestovaný pointer a baseline vektory. Dotaz běžného uživatele i čistě lexikální dotaz používají novou verzi; modelová publikace a ACL se neobcházejí. Default nelze smazat.
- Stará revize formuláře ani pokus o změnu embeddingového modelu nezaloží novou fyzickou verzi.

```powershell
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
$env:RUN_LOCAL_SQL_TESTS='1'
.venv/Scripts/python.exe -m pytest tests/test_index_editor.py tests/test_index_corpora.py tests/test_index_jobs.py tests/test_search_access.py -q
```

Lokální GUI se ověřuje zvlášť: existující index načte vlastní parametry bez volby modelu, nový zobrazí model a jiné spodní tlačítko; přepnutí indexu obnoví jeho hodnoty. Tyto testy ani loopback GUI nenahrazují Azure native VECTOR/Blob/JHU či produkční rollout.
