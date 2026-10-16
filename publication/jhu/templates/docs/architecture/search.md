# Současná architektura vyhledávání

FastAPI koordinuje ingestaci a RAG přes explicitní embedding/LLM rozhraní a factory. Implementované adaptéry používají Azure OpenAI. Lokální modelové adaptéry a automatické porovnávání modelů nejsou implementované. Oba Next.js frontendy jsou samostatné statické exporty. Datová cesta je Azure SQL + Blob Storage; podporované lokální prostředí je SQL Server 2022 Developer.

EmbeddingProfile identifikuje model, revizi, rozměry, normalizaci a verzované zpracování query/document vstupu. Endpoint a credentials jsou oddělené od profilu. Shodné rozměry neznamenají kompatibilní prostor. Katalog indexů odděluje profil a tenantí korpus; jeden index na tenant je explicitně aktivní. Vektorové tabulky neduplikují texty a ACL.

Výchozí hledání je přesné nad všemi způsobilými embeddingy. Nativní Azure SQL používá VECTOR_DISTANCE a parametrizované tenant/metadata/freshness i relační dokumentové/chunkové ACL před top K. Keyword větev používá SQL fulltext; lokální reference používá JSON cosine a LIKE. Kontekstové rozšíření, historie a PDF přístup znovu ověřují oprávnění a revize.

Volitelný DiskANN vyžaduje skutečný podporovaný cosine index verze alespoň 3 a explicitní režim ann. Vytvoření indexu jej nezapíná. Exact i ANN používají stejný profil a prefiltry. Chyba/timeout nespouští další nákladný scan. Aktivaci musí předcházet [kvalitativní a výkonové ověření](../development/testing.md).

Chunk, embedding, profil, revize vstupu a ACL se ukládají transakčně. Změna textu zneplatní embeddingy všech profilů, smazání chunku je kaskádově odstraní. Další model lze doplnit backfillem současných chunků bez nové extrakce. Neoznačeným historickým embeddingům se původ automaticky nepřisuzuje.

Autentizace používá vlastní podepsaný dvoudílný bearer token, Argon2id a aktuální serverové skupiny. Historické názvy JWT_* z něj nedělají standardní JWT. Entra ID a LangChain/LangGraph nejsou aktuální implementací. Přesná identita ju-prod zůstává v datech/tokenu/ACL; alias ju → jhu platí jen pro konfigurační adresář.

Údržba respektuje tenantí scope. Full refresh validuje zdroje před zápisy, nahrazuje dokumenty jednotlivě a stale řádky odstraní až po úplném úspěchu; pozdní chyba může zachovat hotové náhrady, ale nepromaže zbytek korpusu. Fast reindex nepoužívá basename fallback na jiný soubor. [Provozní postup](../deployment.md).

## Známé hranice

PostgreSQL retrieval zůstává experimentální. OCR, ukládání section_title v hlavní ingestaci, sjednocení Blob/lokální konfigurace, lokální modely a automatické experimenty nejsou hotové. Kapacita se nemění automaticky. Nativní SQL a skutečný provozní výkon vyžadují vlastní cílové ověření; funkční unit testy nejsou benchmark.
