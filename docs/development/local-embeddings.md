# JHU embeddingy a více indexů

Embedding je samostatná volba od modelu odpovědi v obou konzolích. `embedding_config.json` obsahuje výchozí Azure profil a v JHU také `jhu-nomic`: `nomic-embed-text:latest`, 768 rozměrů, L2 normalizace a povinné prefixy `search_query: ` / `search_document: `. JSON se nahrazuje celý; chyba existujícího tenantového souboru se neskrývá fallbackem. `ju-prod` používá JHU konfiguraci, jeho datová identita zůstává přesná.

Připojení používá stejné `JHU_LLM_ENDPOINT`, `JHU_LLM_USERNAME`, `JHU_LLM_PASSWORD`, `JHU_LLM_ALLOW_HTTP` a `JHU_LLM_VPN_INTERFACE` jako inference. Existující `.env.jhu-model` ani `.env.local` nemaž. Endpoint a secrets nepatří do katalogu. `JHU_LLM_VERIFIED_MODEL` ověřuje inferenční model; embedding má vlastní kontrolu digestu a nezávisí na názvu Qwenu.

## Porovnání přímo v administraci — Azure a Nomic nad dvěma PDF

1. Spusť běžný lokální backend pro JHU, administraci a JHU VPN. Přihlas se účtem se serverovou skupinou `Management`.
2. Přejdi do záložky **Modely a vyhledávání**, sekce **Embeddingové modely a indexy**, a otevři **Embeddingové indexy — příprava a porovnání**. Zkontroluj počet dokumentů a existující Azure index; u dvou jednochunkových PDF bude pokrytí `2/2`. Pokrytí počítá chunky, nikoli dokumenty.
3. V profilu k přípravě vyber **nomic-embed-text:latest** a klikni **Připravit / doplnit index**. Backend zpracuje stávající chunky celého tohoto tenantu, bez nové extrakce, shrnutí či kopírování dokumentů. Opakovaný požadavek doplní existující index; úplný index znovu nevolá model. Pokud existuje více indexů stejného profilu, zvol **Doplnit embeddingy** přímo u konkrétního řádku.
4. Vyčkej na nový Nomic řádek se stavem **připravený** a úplným pokrytím. Azure řádek zůstane zachovaný. V lokální SQL databázi jsou dvě fyzické vektorové tabulky odkazující na stejné chunk UUID, texty, PDF a ACL.
5. Ve stejné záložce zvol v **Embeddingový index pro tento dotaz** Azure index a klikni **Přejít k vyhledávání**. Polož otázku, přes **Změnit model / index** se vrať a vyber Nomic; potom polož stejnou otázku. Zachovej stejný odpovědní LLM, filtry a strategii; pro izolaci embeddingové větve použij `vector`. Keyword režim embeddingový selector nepoužívá. Pro čisté porovnání lze vyprázdnit konverzaci.
6. Pod každou odpovědí je skutečný embeddingový model a krátké UUID použitého indexu. API a uložená provenance obsahují úplné `search_index_id`, `embedding_profile_id` a `embedding_model`.

Výběr v chatu platí jen pro konkrétní požadavek, nemění výchozí ingestaci a nevyžaduje restart backendu. Jeden požadavek vytvoří jeden query embedding a čte jedinou vybranou vektorovou tabulku; žádné sloučení indexů nebo fallback. Stejný profil může mít více indexů, proto se posílá UUID konkrétního indexu. Neúplný, chybějící, cizí nebo neznámý profil je chyba před embeddingem/thread zápisem. Obnovení přehledu nenahradí neplatnou volbu jiným indexem.

Příprava v UI je povolená pouze pro lokální SQL Server na loopback / `ai_search_local`; celý cloudový backfill/DDL nadále vyžaduje zvláštní řízený postup. Pro lokální UI operaci backend zůstává běžet. Během porovnávání dokumenty neměň: ingestace dál zapisuje svůj výchozí profil a jiné experimenty pak mohou potřebovat doplnění. Server kontroluje skutečné pokrytí před každou explicitní volbou, nikoli jen stav starého dropdownu. Změna či odebrání správce během backfillu zabrání dalšímu dávkovému zápisu/volání. Přerušená příprava zachová původní data a lze ji obnovit.

Příprava je pouze v administraci pro Management. Uživatelská konzole má vlastní výběr kompletních indexů: aktivní tenantový default a publikované, skupinově povolené experimenty. Další modely včetně MXBAI se přidávají přes [tenantový registr](local-model-registry.md). Publikace neobchází dokumentová ani chunková ACL. Živý test nové cesty ověřil Nomic embeddingy obou skutečných ukázkových PDF, lokální SQL a chatové API s mockovaným odpovědním LLM; nejde o cloudovou ani relevanční evaluaci.

## Ověření připojení

Z kořene repozitáře ve VS Code připoj JHU OpenVPN a spusť:

```powershell
.venv\Scripts\python.exe probe_jhu_embeddings.py
```

Probe použije pouze syntetické české texty. Vrací profil, rozměry, časy a podobnosti, nevypisuje vektory ani credentials a nemění databázi. První volání může zahrnovat načtení modelu. Na stejné službě se embeddingy a generování dělí o jeden slot na backendový proces; více replik není globální distribuovaný limit.

Adaptér používá Basic autentizaci a `POST /api/embed` s dávkovým `input` a `truncate:false`. Znakový rozpočet 12 000 není počet tokenů ani záruka délky kontextu. Server příliš dlouhý vstup odmítne; nic se potichu nezkrátí. Profil má timeout 180 s a sekvenční dávky po 8; při timeoutu/obsazení se volání automaticky neopakuje ani nepřepne do Azure.

Modelový digest se kontroluje přes `/api/tags` před i po operaci. Aktualizace mutable tagu znamená nový profil a index, nikoli míchání starých a nových vektorů. Během backfillu neměň serverový model; kontrola před/po nemůže uzamknout vzdálenou administraci. Žádný model se automaticky nestahuje.

## Naplnění druhého indexu lokálně

Nejdřív nech běžným startem vytvořit lokální JHU data a demo. Pro backfill/aktivaci backend zastav; databázi nech běžet. Nepoužívej terminál s exportovanými cloudovými `AZURE_SQL_*` proměnnými.

```powershell
.\dev.ps1 -Action start-db
.\dev.ps1 -Action backend -Tenant jhu
# Po dokončeném startu backend ukonči Ctrl+C.
$env:APP_ENV = "local"
$env:TENANT_ID = "jhu"
.venv\Scripts\python.exe migrate_search_vectors.py
```

Audit vypíše přesný host, DB, tenant, UUID indexů, model, rozměry, coverage a aktivní index. Poznamenej si UUID původního Azure indexu. Následující očekávané hodnoty platí pro výchozí lokální setup; pokud audit ukazuje jiný cíl, neobcházej ochrany změnou očekávání bez jeho ověření.

```powershell
.venv\Scripts\python.exe migrate_search_vectors.py --create --embedding-profile jhu-nomic --reembed --expect-host 127.0.0.1 --expect-db ai_search_local --expect-tenant jhu
```

Tím vznikne **neaktivní** druhá tabulka vektorů. Znovu se použijí stejné chunky, UUID, texty, ACL a revize; původní Azure vektory a legacy JSON zůstanou. Neprobíhá extrakce, chunkování ani generování shrnutí. Jeden dokument se nekopíruje pro každý model. Dávky se commitují samostatně a přerušený backfill lze dokončit přes vrácené UUID:

```powershell
$nomicIndex = "<UUID vytvořeného indexu>"
.venv\Scripts\python.exe migrate_search_vectors.py --index $nomicIndex --reembed --expect-host 127.0.0.1 --expect-db ai_search_local --expect-tenant jhu
```

Opakované `--create` vytváří další index; pro pokračování použij `--index`. U existujícího indexu se provider vybírá z uložené identity profilu. Samotná shoda rozměrů nestačí.

## Přepnutí a návrat

Aktivace je samostatný explicitní krok a vyžaduje úplné pokrytí aktuálního korpusu:

```powershell
.venv\Scripts\python.exe migrate_search_vectors.py --index $nomicIndex --activate --expect-host 127.0.0.1 --expect-db ai_search_local --expect-tenant jhu
.\dev.ps1 -Action backend -Tenant jhu
```

Chat, preview a ingestace nyní používají prostor aktivního indexu; dropdown chatového LLM funguje nezávisle. API odpovědi uvádí `metadata.embedding_profile_id` a `metadata.embedding_model`. Runtime nevolá všechny embeddingové modely. Lokální demo při restartu zachová již připravené indexy/chunky. ANN se tím nezapíná; lokální SQL 2022 používá přesnou JSON referenci. Pro tento první experiment ponech `vector_search_mode=exact`; nový index automaticky nepřebírá DiskANN ze starého indexu.

Nová ingestace doplňuje aktivní profil. Ostatní experimenty mohou mít neúplné pokrytí; změna textu zneplatní jeho vektory ve všech indexech a smazání chunku je odstraní kaskádově. Před návratem na starý Azure index zastav backend, ověř audit a případně jej doplň `--index <Azure UUID> --reembed` se stejnými target guards. Pak jej aktivuj přes `--index <Azure UUID> --activate`. Starý profil ponech v katalogu i prostředí, dokud na něj potřebuješ návrat. Volba nového LLM sama nevyžaduje nový embedding.

## Regrese a limity ověření

```powershell
.venv\Scripts\python.exe -m pytest tests/test_local_embeddings.py tests/test_embedding_profiles.py -q
$env:RUN_LOCAL_SQL_TESTS = "1"
.venv\Scripts\python.exe -m pytest tests/test_local_embeddings.py tests/test_vector_store.py -q
# Navíc skutečný JHU model a samostatná dočasná lokální SQL DB:
$env:RUN_JHU_EMBEDDING_TESTS = "1"
.venv\Scripts\python.exe -m pytest tests/test_local_embeddings.py -k live_nomic_local_sql_roundtrip -q
Remove-Item Env:RUN_LOCAL_SQL_TESTS
Remove-Item Env:RUN_JHU_EMBEDDING_TESTS
```

Základní testy nečtou private env ani nevolají modely. Živý test používá syntetické texty a izolovanou SQL databázi; nepřepíná aplikační `ai_search_local`. Výsledek lokální JSON reference neprokazuje Azure VECTOR/DiskANN ani dostupnost JHU z Container App. VPN na notebooku neposkytuje trasu Azure. Pro cloud je potřeba samostatně schválit síť, image, vytvoření profilové tabulky, backfill a aktivaci; existující nativní storage podporuje 768 rozměrů bez změny starých tabulek.

Krátká syntetická zkouška není evaluace češtiny. Před změnou výchozího modelu porovnej Azure/Nomic na stejných označených českých otázkách, chunkách a filtrech pomocí Recall@K/nDCG@K, citací a latence. Cosine skóre různých modelů mezi sebou neporovnávej.

Kontrakt: [Ollama embed](https://docs.ollama.com/api/embed), [Nomic task prefixes](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5).
