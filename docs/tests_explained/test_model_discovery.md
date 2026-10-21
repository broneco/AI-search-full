# Testy discovery modelů

`tests/test_model_discovery.py` mockuje pouze vnější metadata HTTP. Ověřuje skutečnou klasifikaci chat/embedding/reranker, zákaz odvozování embeddingové podpory z LLM hidden dimensions, whitelist bez systémových promptů/templates/cest, neplatné názvy/digesty/duplicity, omezený inventář a částečné selhání jednoho modelu.

Timeout a chyby služby nevyvolají retry ani leak private řetězců; procesový scan slot odmítne souběžnou práci ještě před HTTP. Požadavky směřují jen na tags/show, nikdy generate/embed/pull. VPN/URL guard je sdílen se stávajícím připojením a jeho vlastní regrese zůstávají v embeddingových testech.

Asynchronní transport s deseti modely měří skutečný souběh metadata requestů a ověřuje maximum tři současná volání.

API případy používají skutečné serverové účty/skupiny/tokeny: anonymní a běžný uživatel nemají přístup, jiný tenant bez JHU konfigurace nevolá službu. JHU/ju-prod manager vidí vazby na existující profily; discovery nezmění katalog ani nepovolí nový model a změněný embeddingový digest se nespojí se starým profilem.

Příkaz: `.venv\Scripts\python.exe -m pytest tests/test_model_discovery.py tests/test_model_catalog.py tests/test_local_embeddings.py -q`. Bez skutečného API či privátního prostředí. Živý metadata inventář a frontend build se ověřují odděleně; nejde o generování/quality/performance test všech modelů ani cloudový rollout.
