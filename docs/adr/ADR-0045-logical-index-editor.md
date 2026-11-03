# ADR-0045: Editor logického indexu a dokončené verze

Status: Accepted for source implementation; cloud migration/runtime acceptance remains pending.

## Kontext

Uživatel výslovně změnil obsluhu připravené ADR-0044: existující index se má otevřít, upravit a přepočítat, nový má navíc volbu modelu. Současné globální ukládání chunkování/přestavba DB s tímto modelem nesouvisí. U historických indexů je nově schváleno jednorázové převzetí současných parametrů i bez záruky, že odpovídají původnímu výpočtu.

## Rozhodnutí

Administrace má dva režimy, vlastní pracovní formulář a jedno spodní tlačítko **Upravit index / Vytvořit index**. Náhled používá tento formulář a model zvoleného indexu, nepřepisuje globální konfiguraci. Nové vytvoření v jedné trvalé úloze připraví texty i embeddingy. Existující model určuje server podle uloženého profilu; změnu modelu odmítne.

UUID indexu pro uživatelský výběr zůstává stabilní. `index_settings.current_index_id` odkazuje na dokončenou fyzickou verzi se stejným přesným tenantem a profilem. Její `owner_index_id` ukazuje na původní logický index a `base_revision` chrání souběžnou změnu. Každá fyzická verze má vlastní neměnný snapshot, chunky a vektorovou tabulku. Do přehledů patří pouze logické indexy, připravované verze jsou skryté a průběh používá jejich fyzický UUID.

Přepočet získá stejnou tenantovou rezervaci jako dosavadní úlohy, ověří revizi a postaví novou verzi vedle funkční původní. Po ověření všech dokumentů, ACL a pokrytí worker v jedné transakci přepne ukazatel/název/revizi i konečný stav úlohy. Selhání či zrušení ponechá původní verzi dostupnou; shodný opakovaný požadavek pokračuje v téže nedokončené verzi. Staré texty a citace se nemažou.

Takto lze upravit i výchozí index. `active_search_indexes` dál odkazuje na původní ingestovaný korpus a jeho model; standardní ingestace stále zapisuje do baseline. Dotazy explicitním i výchozím indexem používají dokončenou aktuální verzi. Čistě lexikální hledání následuje aktuální textový korpus výchozího indexu bez volání embeddingového modelu. Nové či změněné originály mohou vlastní verzi znepřipravit do explicitního doplnění; nedochází k automatickému přepočtu po uploadu.

Běžnému uživateli se zachovávají původní publikace/modelová oprávnění a ACL. Dokončená verze původního defaultu dědí pouze jeho indexovou dostupnost při stejném profilu; připravované sourozence tím nepublikujeme. Smazání nevýchozího logického indexu odstraní všechny jeho fyzické vektorové tabulky/katalogy, uchová text pro historii. Ingestovaný default zůstává chráněný před smazáním.

`POST /api/search-indexes/initialize-settings` výslovně při otevření editoru doplní pouze dosud neznámé snapshoty ze současné serverové konfigurace; označí je `settings_origin=assumed`. Záznamy s konfigurací nepřepisuje. Toto je uživatelem schválený předpoklad, nikoli důkaz původních parametrů. Náhled a přepočet začnou vycházet z parametrů uložených u vybraného indexu.

## Migrace a omezení

Připravená aditivní migrace ADR-0044 přidává také čtyři nullable pole do `index_settings`, včetně upgradu již vytvořené tabulky. Azure migrace zůstává explicitní, startup nové cloudové DDL neprovádí. Starší nepodporované image nejsou bezpečný rollback po vzniku vlastních korpusů; ponechat kompatibilní filtry a rozlišení aktuální verze. Jde o zdrojovou implementaci bez nové publikace nebo cloudové změny.

[Použití](../development/index-chunking-pairs.md), [regrese](../tests_explained/test_index_editor.md).
