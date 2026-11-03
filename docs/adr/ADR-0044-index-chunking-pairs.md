# ADR-0044: Index jako neměnná dvojice chunkování a embeddingového profilu

Status: Accepted for source implementation; Azure migration and runtime acceptance pending.

Následné zadání uživatele mění obsluhu na editaci logického indexu a výslovně schvaluje pracovní předpoklad současných parametrů u historických indexů. Tyto části nahrazuje [ADR-0045](ADR-0045-logical-index-editor.md); neměnnost jednotlivých fyzických snapshotů zůstává.

## Kontext

Dosavadní indexy oddělují embeddingové prostory, ale všechny používají stejné řádky chunků. To nestačí pro porovnání dvou velikostí nebo strategií dělení: přepis sdílených chunků znehodnocuje jiné vektory. Historické nastavení při jejich vzniku se neukládalo. Cloudový interaktivní náhled navíc chybně hledal originály v lokálním `data/` namísto uložené Blob URI.

## Rozhodnutí

Nové indexy vytvořené s nastavením dostanou vlastní `corpus_id=index-<UUID hex>`, neměnný embeddingový profil a snapshot validovaného nastavení v `index_settings`. Jméno je samostatná editovatelná hodnota s revizí pro optimistické zamykání. `index_documents` zaznamenává dokončenou přípravu každého originálu, jeho revizi a počet chunků včetně nulového počtu. Nový nullable `chunks.corpus_id` nechává historické řádky beze změny; NULL odpovídá `tenant-chunks-v1`.

Vlastní chunky vznikají z přesného evidovaného originálu, po dokumentech a s potvrzením rezervace/oprávnění před zápisem. Následuje stávající dávkový vektorový backfill. Pokračování neopakuje hotové nezměněné dokumenty ani platné vektory. Přidání nebo změna originálu znepřipraví index do explicitního doplnění. Sémantické/AI dělení v úplném výpočtu při chybě nezamění strategii za aproximaci. Slider náhled je výslovně aproximace; plný náhled používá zvolený model.

Výběr korpusu je serverový údaj z ověřeného indexu. SQL prefiltry pro exact/ANN/keyword/hybrid i rozšíření kontextu jej respektují současně s tenantem a ACL. Standardní ingestace zapisuje pouze historický výchozí korpus; izolovaný index nelze aktivovat jako ingestovaný default. Dokument se smí znovu segmentovat pouze při jednotných původních oprávněních pasáží odpovídajících dokumentu. Jinak nelze práva bezpečně přemapovat a operace skončí před čtením/modelovým zpracováním.

Mazání vyžaduje Management, aktuální revizi, neaktivní správní úlohu a index odlišný od ingestovaného defaultu. V transakci odstraní pouze jeho vektorovou tabulku, správní metadata a katalog. Textové chunky zůstávají pro existující historické citace, jejich korpus se nedostává do dalších dotazů. U již známých citací kontrolujeme aktuální tenant a ACL bez omezení na výchozí korpus.

Historické indexy nelze pravdivě doplnit dnešními hodnotami nastavení. UI je označuje jako nezaznamenané; lze je pojmenovat či odstranit při splnění ochranných podmínek. Kompatibilní staré API/CLI vytvoření bez snapshotu nadále znamená sdílený historický korpus. Nová administrace vždy posílá snapshot a bez načtené konfigurace vytvoření nepovolí.

## Nasazení a návrat

Migrace je explicitní a aditivní: dvě nové správní tabulky a nullable sloupec; žádný přepis původních chunků či vektorů. Startup Azure migraci neprovádí. Podrobnosti a hranice ověření: [provozní návod](../development/index-chunking-pairs.md).

**Starší binárka v0.1.10 není bezpečný rollback po vytvoření vlastních textových chunků:** nezná nový korpusový prefiltr a mohla by míchat texty ve keyword/expanzi. Po prvním vlastním korpusu se vrací pouze kompatibilní image s korpusovými filtry; nejprve se vypne správa indexů a zastaví úloha. Dřívější image lze použít jen před vznikem vlastních chunků nebo po samostatně schváleném a prokazatelném odstranění všech takových řádků včetně vyhodnocení historie. Schema se při návratu nesnižuje.

## Důsledky

Srovnání strategií je skutečné, ale každý index spotřebuje vlastní texty a vektory. Smazání ponechává citační text, takže není úplným uvolněním místa; garbage collection historie je samostatný budoucí krok. Nezaručujeme bitovou determinističnost AI chunkování ani reprodukovatelnost po změně externího generativního modelu. Není zde nový scheduler, automatické opakování inference, automatické přepínání defaultu ani řešení limitu vstupu MXBAI.
