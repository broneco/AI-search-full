# Ověření aplikace

## Izolované testy

V kořeni po instalaci requirements.txt spusť `./dev.ps1 -Action test` nebo `python -m pytest -q`. Testy používají SQLite, deterministické modelové mocky a dočasný konfigurační overlay. Nevyžadují privátní tenantí env ani Azure. Strukturální kontrola skutečných env přijme alespoň jeden vyplněný tenant; bez soukromé konfigurace přeskočí jen tuto kontrolu. Syntetická regrese běží vždy.

Výchozí dočasné adresáře jsou pod `.local/tmp/pytest/`; pytest je čísluje a zamyká pro oddělení souběžných relací. Uchovává tři poslední běhy s ochranou aktivních relací; cache je odděleně v `.local/pytest-cache/`. Nepřidávej pracovní adresáře do kořene repozitáře. Explicitní `PYTEST_DEBUG_TEMPROOT` a `--basetemp` se respektují; pevný `--basetemp` se před použitím maže a nesmí se sdílet nebo obsahovat uživatelská data. Lokální backend sleduje pro autoreload jen `app/`.

## Lokální SQL

Spusť `./dev.ps1 -Action start-db`. V samostatném terminálu nastav `$env:RUN_LOCAL_SQL_TESTS = "1"` a spusť testy; po dokončení použij `Remove-Item Env:RUN_LOCAL_SQL_TESTS`. Tyto testy vytvářejí izolované dočasné testovací databáze na localhostu, které uklidí. Nesměřují na aplikační korpus. Lokální SQL 2022 ověřuje dialect, transakce, ACL a JSON přesné hledání, nikoli native VECTOR/DiskANN/fulltext.

## Wheel a frontendy

Nainstaluj `python -m pip install setuptools wheel`, nastav `$env:RUN_PACKAGE_TESTS = "1"` a spusť `python -m pytest tests/test_packaging.py -q`. Test sestaví skutečný wheel a importuje ho mimo checkout, včetně veřejných resources a kontroly vyloučení env. Poté proměnnou odeber.

Frontendy ověřuj samostatně přes `npm --prefix frontend-user run build` a obdobně frontend-admin. TypeScript kontrola nenahrazuje kompletní produkční build ani živé ověření po nasazení.

## Azure native integrace

Native integrace jsou explicitní opt-in. Než zapneš RUN_NATIVE_SQL_TESTS nebo RUN_NATIVE_ANN_TESTS, přečti cílové guardy v tests/test_vector_store.py, tests/test_ann_search.py a tests/native_sql_harness.py. Použij schválený izolovaný testovací cíl; potvrzení hostu/databáze/tenantu a schema guardy neobcházej. Lokální výsledky nejsou důkazem Azure výkonu. Modelové integrace jsou také opt-in přes RUN_AZURE_MODEL_TESTS.

## Retrieval a benchmark

`benchmark_search.py --help` popisuje oddělenou přípravu query embedding cache a read-only run. Cache musí odpovídat indexu/profilu; porovnávej stejný korpus, otázky a filtry. Pro ANN požaduj průměrný recall@30 alespoň 95 % na nejméně 100 reprezentativních dotazech proti přesné referenci; report rozděl podle selektivity filtrů. Latenci měř alespoň 200 requesty pro souběh 1 i 3, studený start zvlášť. Cíl p95 retrievalu je nejvýše 1 s bez query embeddingu a generování odpovědi. Jde o podmínky přijetí, nikoli již potvrzený výkon.

Jednotlivé moduly a jejich testovací funkce jsou v [mapě repozitáře](../navigation_guide.md) a docs/tests_explained/. Cross-tenant scénáře používají syntetické identity; nejsou další přibalené skutečné tenanty.
