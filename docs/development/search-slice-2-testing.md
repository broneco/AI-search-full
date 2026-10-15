# Ověření slice 2: identita, prefiltry a ACL

Slice 2 chrání vyhledávání, rozšíření kontextu, náhledy, změny ACL a historii. Vektorový cap zatím zůstává; úplné přesné hledání patří do slice 3. Níže uvedené lokální SQL testy neprokazují výkon ani Azure provisioning.

## Automatické testy

V novém terminálu v kořeni projektu lze bez modelových credentials spustit rychlou část:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_search_access.py -q --tb=short
```

SQL Server scénáře jsou v této variantě záměrně skipped. Pro skutečný SQL Server spusť Rancher Desktop a lokální SQL kontejner, potom:

```powershell
.\dev.ps1 -Action start-db
$env:RUN_LOCAL_SQL_TESTS = "1"
.venv\Scripts\python.exe -m pytest tests/test_search_access.py -q --tb=short
Remove-Item Env:RUN_LOCAL_SQL_TESTS
```

Fixture povoluje pouze localhost a vytvoří vlastní databázi `ai_search_acl_test_<náhodné UUID>`, kterou v závěru odstraní. Nepoužívá ani nemaže data `ai_search_local` a není určena pro Azure host. Testuje skutečné T-SQL predikáty, OPENJSON, indexované granty, cascade, rollback i ORM/Core zápisy. LLM volání jsou nahrazena fakes.

Celou běžnou sadu spouští `.\dev.ps1 -Action test`. Pytest JSON overlay se pro každý běh vytváří v jeho dočasném adresáři; nevychází z předchozích `.local/test` změn. Real-model integrační testy ingestace/RAG vyžadují navíc explicitní `RUN_AZURE_MODEL_TESTS=1` a platné Azure OpenAI credentials; běžná sada je záměrně přeskočí. Lokální SQL a Azure modely jsou dvě nezávislé opt-in volby.

## Ruční API a UI kontrola

1. Spusť backend a frontend obvyklým způsobem. Local startup automaticky vytvoří ACL grant tabulky a obnoví jejich obsah ze source JSON. Na `/api/health` ověř environment `local`.
2. Přihlas se existujícím lokálním administrátorským účtem, jehož DB groups obsahují Management. Ve Swaggeru `/docs` použij `/api/auth/login` a vlož vrácený access_token do tlačítka **Authorize**. Pouhé X-User-Id/X-User-Groups už neopravňuje k žádné akci a automatický výběr prvního uživatele je odstraněn.
3. Přes `/api/documents/ingest` vlož dva vlastní krátké testovací texty s různými kódy: jeden s `security_acl={"allowed_groups":["User"]}`, druhý s `{"allowed_groups":["HR"]}`. Metadata nastav např. `{"department":"test-public"}` a `{"department":"test-hr"}`. Uchovej jejich ID pro kontrolu.
4. S Management tokenem lze v rámci aktuálního tenantu oba vyhledat. Odhlas se a přihlas běžného User uživatele. Ve vector i keyword režimu nesmí dostat HR zdroj, ani po přidání hlavičky `X-User-Groups: Management`. Filtr department=test-public má vrátit veřejný text; neexistující hodnota má prázdné sources. Odpověď bez evidence nemá tvrdit, že čerpá ze skrytého dokumentu.
5. Bez tokenu chat/list/chunks/PDF/preview vracejí 401. S User tokenem skrytý dokument/chunky/PDF/preview vracejí 404 a administrátorský zápis (např. reindex-all) 403. Registrace s role=Admin/groups=Management stále vytvoří pouze User. V UI se oprávnění zobrazují z účtu, nepřepínají klientským role selector.
6. Mixed document/chunk ACL, selective top K, siblings/page/section a přesnou tenant izolaci včetně case/trailing spaces ověřuje automatická sada. Raw PDF a re-chunk preview se otevřou jen při oprávnění ke všem chunkům dokumentu. Při povolených chunky zkontroluj PDF drawer, modal, zvýraznění a otevření v nové záložce; URL nesmí obsahovat token.
7. Změna DB skupin platí i se starým stále platným tokenem. Nové odpovědi evidují všechny přispívající chunky a jejich transitivní použití v navazujících tazích. Po odebrání skupiny nesmí být stará chráněná odpověď dostupná v historii ani znovu vložená do LLM. Historické assistant zprávy bez této provenance zobrazí placeholder; začni nový chat pro nové citace.

HTTP souborové cesty musí zůstat v data/; náhled či potvrzená ingestace souboru mimo tento adresář se odmítne. Cloudový Blob náhled musí odpovídat originals containeru nastavenému pro tento tenant. V dev/prod se veřejná registrace zavírá a demo účty se automaticky nevytvářejí; jejich audit a bootstrap správce patří do handoffu.

## Azure hranice

Před cloudovým nasazením vyžaduje slice 2 [ruční handoff](../../.agents/inbox/2026-10-14-search-acl-migration-handoff.md): audit přesných tenantů, compatibility level ≥130, grant tabulky/backfill, aplikační práva a soukromý JWT_SECRET. Žádné tenant env soubory ani Azure zdroje v tomto slice agent neupravil. Cloudový rollout čeká na lidské ověření; lokální testy samy jej neschvalují.
