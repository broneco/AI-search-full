# Testy katalogu modelů

JHU kontrakt nyní ověřuje i `options.num_predict` pro legacy profil bez explicitního `num_ctx`, aby zobrazovaný/správcovský limit platil také v této cestě. Připnuté profily nadále nastavují oba parametry; vyšší interní max_tokens nesmí obejít efektivní strop.

`tests/test_model_catalog.py` testuje striktní tenantové katalogy, alias JHU, veřejný autentizovaný seznam bez připojení/secrets, legacy směrování a izolaci modelů. SQLite testy vytvářejí vlastní databázi a syntetické účty. HTTP/SDK mocky nikdy nevolají skutečné služby.

Regrese ověřují Management-only editor, null/[] pravidla, tenantovou izolaci, konflikty revizí, podvržené skupiny a odebrání skupiny po výběru před generací. Dále testují správný Azure deployment a parametry, přesný JHU request, historii v promptu, nezveřejnění thinking, chyby/timeout bez retry/fallback a odmítnutí příliš velkého vstupu.

Chatové testy mění model uvnitř konverzace a čtou skutečně uloženou provenance. Neznámý model nesmí spustit embedding ani uložit zprávu. Shrnutí má samostatného providera a jeho selhání nesmí být převedeno na placeholder.

`RUN_JHU_MODEL_TESTS=1` zpřístupní jeden syntetický RAG smoke s konkrétním kódem a citací. Jen tento explicitní test čte ignorovaný `.env.jhu-model`; běžná sada funguje bez něho. Živý test není akceptací produkčního retrievalu ani výkonovým benchmarkem.

Doplňující regrese ověřují target guard skutečného migračního CLI v SQLite, bezpečné Key Vault reference a jejich prioritu vůči explicitním hodnotám, a odmítnutí HTTP trasy mimo OpenVPN. Živý test nyní prochází celé chatové API včetně uložené historie a dále skutečnou klasifikací a shrnutím; retrieval/embeddingy jsou syntetické a žádné soukromé dokumenty neopouštějí test.

Po zavedení lokálních embeddingů fixture deklaruje také nezávislý embeddingový katalog. Regrese selhání shrnutí tak nadále prochází reálným výběrem embeddingového profilu a selže až u zamýšleného modelového volání, bez závislosti na soukromém prostředí.
