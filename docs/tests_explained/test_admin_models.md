# test_admin_models

Nastavení maximální délky výstupu navíc ověřuje Management autorizaci, SQL persistenci a přesný tenant, přísnou validaci integer/range, vlastní CAS revize a reset bez opakovaného použití revize 0. Cloud/registrovaný lokální model respektuje limit pro chat/shrnutí/klasifikaci; embeddingový profil se odmítne. Zvýšení lokálního výstupu zmenší vstupní rozpočet a příliš dlouhý prompt selže před HTTP. Payload má `num_predict`/`max_completion_tokens`; vyšší interní požadavek limit neobejde. Registry snapshot zůstane stejný. Implicitní klasifikátor s DB session používá override. SQL repository regrese zahrnuje chybějící tabulku bez porušení transakce a guarded migraci.

Regrese společné správy modelů a promptů v `tests/test_admin_models.py`:

- Přehled spojuje LLM/embeddingy a jejich parametry, je pouze pro Management a nevrací endpointy/credentials.
- Popis CS/EN přežije reload, projeví se ve veřejném autorizovaném katalogu, má CAS revizi a přesnou tenantovou izolaci. Neplatné ID/pole/jazyky se odmítnou.
- Úprava embeddingového popisu nezmění profil, fingerprint ani registry snapshot a nevyvolá reindexaci.
- Chybějící tabulka ponechá původní čtení katalogu, ale zápis požaduje migraci. SQL permission error nesmí vyvolat tichý fallback.
- Zápis promptu shrnutí/klasifikace mění skutečně používané pole a zachová ostatní parametry i kategorie a ACL. Nepovolená skupina, neznámý účel a příliš dlouhý vstup selžou.
- Migrační CLI je read-only bez Apply a vyžaduje přesný host/databázi/tenant.
- Parametrizovaný repository test ověřuje Unicode, case-sensitive tenantovou izolaci a nepokaženou SQL transakci po zjištění skutečně chybějící tabulky; MSSQL varianta vyžaduje `RUN_LOCAL_SQL_TESTS=1` a izolovanou Docker DB.
- API porovnání dvou modelů a Azure/Nomic indexů prokazuje samostatná vlákna, stejné otázky, skutečné profile/index metadata a historii bez předchozí odpovědi druhé varianty, pro SQLite i opt-in SQL Server. Modely a embeddingové volání jsou deterministické testovací adaptéry.

Prohlížečový průchod navíc ověřuje dvě samostatné historie/modely/indexy při společné otázce, nezávislé chyby, vyhledání profilu podle popisu, modal discovery a sjednocené prompty. Používá syntetické API; není to benchmark JHU ani důkaz dostupnosti cloudových deploymentů.
