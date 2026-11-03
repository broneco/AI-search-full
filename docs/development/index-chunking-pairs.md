# Indexy s vlastním chunkováním

Stav: připravené zdroje, zatím nenasazeno do Azure. Existující v0.1.10 a provozní data se tímto zdrojovým krokem nemění.

## Použití v administraci

Aktualizovaný editor je popsán v [ADR-0045](../adr/ADR-0045-logical-index-editor.md). Závěrečné ověření této navazující úpravy: 107 passed / 2 skipped včetně lokálního SQL, wheelu a exportu; následné regrese modelových oprávnění/katalogu/editoru 46 passed / 2 skipped; čistý JHU balíček 20 passed / 14 očekávaných SQL skips. Admin Webpack/TypeScript a oba GUI režimy proti loopback testovacímu API prošly. Cloud tím nebyl změněn.

1. Otevřete **Chunkování** a zvolte **Upravuji existující** nebo **Tvořím nové**.
2. U existujícího vyberte index: formulář a náhled načtou jeho vlastní parametry, název a pevný embeddingový model. U nového zvolte také embeddingový model a případně název.
3. Upravte strategii, velikost, překryv a AI obohacení. Posuvníky a náhled pracují s pracovní kopií tohoto indexu, nepřepisují globální vyhledávací konfiguraci.
4. Spodní **Upravit index / Vytvořit index** uloží parametry a v jedné trvalé úloze připraví chunky i embeddingy. Průběhové okno ukazuje soubory a fáze. Zavření jej nezastaví; po chybě lze pokračovat.
5. Úprava zachová stejný výběrový UUID a model. Funkční verze se nahradí až po úplném dokončení nové. Během chyby/přerušení zůstává původní dostupná. Nový index se po vytvoření automaticky otevře v režimu úpravy.

Pozdější posun slideru se projeví až příslušným spodním tlačítkem. Změněné/přidané originály vyžadují explicitní doplnění. Nulový textový výsledek se zaznamená jako zpracovaný dokument bez chunků; prázdný index nelze použít pro dotaz. Úprava funguje i pro výchozí index: jeho ingestovaný korpus a model zůstávají zachované, dotazy používají novou dokončenou verzi. Nejde o automatický přepočet po uploadu.

**Přejmenování** nepočítá nové embeddingy. Kolize změn dvou správců vrátí konflikt a vyžaduje obnovení přehledu. **Smazat index…** ukáže potvrzení a odstraní vlastní vektory, katalog a nastavení. Výchozí ingestovaný index je chráněný a během běžící správní úlohy nelze indexy mazat. Originály, ostatní indexy, účty a historie se nemažou. Text pro historické citace zůstává uložený a nadále podléhá aktuálním ACL, takže smazání není úplné vyčištění úložiště.

U historických Azure/Nomic/MXBAI indexů se podle výslovného zadání uživatele při otevření editoru jednorázově převezmou aktuální serverové parametry chunkování. Označení `assumed` říká, že jde o pracovní předpoklad, nikoli důkaz původního výpočtu. Již uložené snapshoty se při dalších otevřeních nepřepisují. Tato inicializace nemění chunky ani vektory; přepočet začne až spodním tlačítkem. Staré API/CLI vytvoření bez `chunking` zůstává kompatibilním způsobem přípravy sdíleného historického korpusu.

## Interaktivní náhled

Náhled po ověření oprávnění načítá přesnou URI originálu: `azure://<originals-container>/<blob>` nebo přesnou cestu v `data/`. Blob se stáhne do dočasného souboru, ověří checksum, extrahuje a po použití odstraní. Nevyhledává podobné názvy ani nepřechází při výpadku Blobu na jiný lokální soubor.

Posuvníky mají debounce a starší odpovědi se při změně indexu, dokumentu, nastavení, relace či panelu zahazují. Základní náhled nevolá vzdálené embeddingy. Pro sémantické/AI dělení a shrnutí použijte **Znovu vygenerovat**; sémantika využije pevný model vybraného existujícího indexu nebo model zvolený u nového. Chyba úložiště/modelu je zobrazena jako chyba, nikoli jako úspěšný prázdný náhled.

Dokumenty s rozdílnými ACL jednotlivých pasáží nelze nově segmentovat bez explicitního mapování práv. Nový index se zastaví s `chunk_acl_mapping_required`; oprávnění se automaticky nerozšiřují. Samotný správce může číst úplný náhled podle stávající politiky Management.

## Databázová migrace

`migrate_index_corpora.py` je standardně pouze plán. Přidává `chunks.corpus_id VARCHAR(64) NULL`, `index_settings` a `index_documents`, včetně nullable polí `settings_origin`, `current_index_id`, `owner_index_id`, `base_revision` i u již existující tabulky nastavení. Historické hodnoty zůstávají NULL, migrace žádný původní řádek nepřepisuje. Jednorázové převzetí parametrů je samostatná explicitní operace editoru. Lokální inicializace SQL použije stejnou implementaci z wheelu; Azure startup tuto migraci nespouští.

Po samostatném schválení, s ověřeným cílem a před výměnou backendu:

```bash
python -u migrate_index_corpora.py
python -u migrate_index_corpora.py --apply \
  --expect-host ju-ai-search-sql-prod.database.windows.net \
  --expect-db ju-ai-search-sqldb-prod --expect-tenant ju-prod
```

Předchozí image ještě nemá nový skript. Nový zdroj umí vygenerovat samostatný payload se stejnými guards, který používá původní SQL připojení již přihlášeného kontejneru:

```bash
python migrate_index_corpora.py --console-script \
  --expect-host ju-ai-search-sql-prod.database.windows.net \
  --expect-db ju-ai-search-sqldb-prod --expect-tenant ju-prod
```

Výstup nejprve zkontrolujte, přeneste jako soubor a spusťte pouze při konkrétním souhlasu s migrací. Migrace není souhlasem k plnému přepočtu 431 dokumentů, publikaci ani aktivaci výchozího indexu. Nový backend před přidáním sloupce nenasazujte.

## Rollback a ověření

Před migrací a po nasazení pořiďte [read-only otisky dat](deployment-preservation-test.md). Nový nullable sloupec mění schéma/serializaci celých řádků: porovnejte explicitně původní sloupce, identické UUID/obsah/ACL/revize a původní vektory, ne pouze počty. Před jakýmkoli novým backfillem musí být původní data shodná.

**Po vytvoření vlastních textových chunků nelze bezpečně vrátit v0.1.10:** nezná korpusové filtry pro keyword/expanzi. Vypněte `INDEX_PREPARATION_ENABLED`, zastavte úlohu a použijte opravenou kompatibilní image se zachovanými filtry. Před prvním vlastním korpusem lze vrátit původní image/backend/SWA bez snižování schématu. Automatický rollback nevylučuje starou image podle obsahu databáze; tuto podmínku musí dodržet operátor.

SQLite/lokální SQL regrese ověřují oddělení korpusů, pokračování, názvy, mazání, ochranu defaultu, ACL, historii a Blob náhled se zastoupeným úložištěm. Nativní `VECTOR`/ANN a skutečný JHU/Blob/UI běh vyžadují samostatnou cloudovou akceptaci po nasazení. Testy ani zdrojový build nejsou důkazem nasazení.

Ověření zdrojů 3. 11. 2026: dosavadní celá sada 773 passed / 24 skipped včetně lokálního SQL; závěrečné regrese indexů, rezervací, správy a zachování dat 117 passed / 2 skipped; samostatný wheel/export průchod 39 passed; JS 10 passed. Obě konzole mají úspěšné produkční buildy a TypeScript. Lokální GUI proti syntetickému API ověřilo vytvoření, přejmenování, smazání, náhled a neměnné nastavení 800 po změně pracovního slideru na 1200. Skutečné veřejné testovací PDF prošlo načtením přes nahrazený Blob provider, reálnou extrakcí i dělením. Čistý JHU balíček se zkouší samostatně bez ADR a soukromých env souborů. Žádná nová verze, commit, publikace ani cloudový zápis nebyl proveden.

Před schvalováním rolloutu zbývá připravit původní-sloupcové porovnání otisků pro přidaný nullable sloupec a kompatibilní rollback image. Lokální administrační `out/` z GUI testu má loopback API a není distribuční cloudový artefakt; pro nasazení se musí znovu sestavit s ověřeným cloudovým backendem.
