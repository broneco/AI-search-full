# Testy keyword vyhledávání

Pro uživatele testy ověřují, že vyhledávání využije databázový textový index, respektuje oprávnění a při chybě nespouští další dlouhý scan. Lokální databáze bez FTS dál umožňuje vývojové testy.

Technicky `tests/test_keyword_search.py` kontroluje literal Unicode tokenizaci, limit NVARCHAR(4000) v UTF-16 jednotkách, parametrizovanou bounded SQL proměnnou, jediný TOP až po tenant/docACL/chunkACL/freshness/metadata a korelaci EXISTS. Žádná interpolace hledaných slov, top_n_by_rank ani čtení starých JSON embeddingů. Mock ODBC chyb ověřuje503/504 bez úniku SQL a bez fallbacku; prázdný dotaz nevolá DB.

Opt-in native test používá guarded `native_db` fixture. Ve vlastním schématu vytvoří český fulltext index/catalog a silnější nepovolené řádky obou ACL, jiného tenantu a metadata. Povolený slabší řádek musí vyhrát při K=1. Ověří diakritiku, whole-word versus substring, stopwords a prázdný filtr; čekání na population je ohraničené. Vlastní index/catalog se odstraní ve finally, fixture uklidí schéma a porovná původní dbo počty. Cizí objekty nemaže.

Běžný příkaz: `.venv/Scripts/python.exe -m pytest tests/test_keyword_search.py -q --basetemp .tmp-pytest-keyword`. Native běh vyžaduje explicitní cíl/RUN_NATIVE_SQL_TESTS a schválený izolovaný rozsah podle existujícího harnessu. Lokální LIKE není důkaz native FTS. Skutečné Azure výsledky jsou v deployment reportu.
