# Opt-in živá managed akceptace

`tests/test_jhu_managed_live.py` vyžaduje explicitní `RUN_JHU_MANAGED_TESTS=1` i `RUN_LOCAL_SQL_TESTS=1`, běžící vlastní helper a přístup ke KV. SQLite případ se přeskočí. Fixture vytváří náhodnou `ai_search_acl_test_*` databázi a odstraní pouze ji, nikoli aplikační korpus. Helper se tímto testem nezakládá ani nerestartuje.

Test používá skutečný discovery, registraci malého Llama, Nomic document/query embedding, přípravu druhého indexu a chat s citací. Ověří jediný zvolený UUID, skutečný model v odpovědi/uložené provenance, nezměněné chunky a původní aktivní index. Azure referenční vektory jsou syntetické, Azure model se nevolá. API hesla jsou záměrně vyprázdněná ve Settings, transport je získá pouze scoped KV cestou. Modelový prompt obsahuje jen dva syntetické české texty.

Postup a omezení: [managed runbook](../development/jhu-managed-local.md). Bez skutečného spuštění testu nelze jeho existenci pokládat za živou akceptaci.
