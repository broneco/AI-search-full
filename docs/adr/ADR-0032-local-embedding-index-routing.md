# ADR-0032: Lokální embeddingy nad sdíleným korpusem

Status: přijato; 2026-10-19.

## Rozhodnutí

Tenantový `embedding_config.json` drží oddělené embeddingové připojení/profilové aliasy od inferenčního katalogu. Výchozí Azure profil dále vzniká z existujících settings se shodným fingerprintem; JHU přidává Nomic 768 s digestem serverového modelu, L2 a verzovanými query/document prefixy. Endpoint ani credentials nejsou součástí identity prostoru.

Používáme existující per-profile fyzické tabulky a jeden aktivní index na přesný tenant. Query i ingest provider se vybírají podle identity aktivního indexu; neznámý prostor je chyba, žádná náhrada stejně dlouhým vektorem. Explicitní backfill přidá embeddingy stávajících chunků bez kopírování textu, extrakce a změny UUID. Aktivace vyžaduje úplné aktuální pokrytí a zastavené zápisy. Runtime nevypočítává všechny experimentální modely; neaktivní indexy je nutné před opětovnou aktivací doplnit.

JHU adaptér používá stejnou Basic službu jako inference, ale `/api/embed` a `truncate:false`. Digest se ověřuje před i po operaci, batch count/dimenze/číselnost/konečnost/L2 před zápisem. Měnící se tag vyžaduje nový profil. Nevytváříme lokální modelový server ani nestahujeme modely. Embedding a generation sdílí procesový slot; neposkytujeme distribuované řízení kapacity.

## Důsledky a ověření

Azure zůstává výchozí, přepnutí je operátorské CLI; UI embedding picker a automatické porovnání nejsou součástí této vertikální slice. Reindexace měnící text správně zneplatní staré experimenty. Lokální demo nesmí při změně profilu přepsat neměnné chunky ani legacy provenance.

Mock testy pokrývají kontrakt/chyby a API routing; izolovaný SQL test pokrývá dvě dimenze, backfill/resume, aktivní ingest a kaskády. Opt-in živý test kombinuje skutečné JHU vektory s dočasnou lokální SQL DB. Toto ověření nenahrazuje Azure native storage a produkční síťovou/relevanční evaluaci. [Provozní návod](../development/local-embeddings.md).
