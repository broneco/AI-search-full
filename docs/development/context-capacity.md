# Shrnutí sousedních chunků a odhad kapacity

V administraci v **Konfigurace vyhledávání → Rozšiřování kontextu a tokenové limity** je volba **AI shrnutí pouze u nalezeného chunku**. Výchozí hodnota je zapnuto. Při rozšíření o sousedy, stránku nebo sekci ponechá shrnutí nalezeného chunku, ze sousedů odstraní pouze generovaný úvod `[AI Shrnutí: …]`. Samotný text sousedů zůstává. Vypnutí vrátí původní chování. Volba se ukládá běžným tlačítkem konfigurace pod klíčem `summaries_only_for_matched_chunk`.

Jde o sestavení kontextu při dotazu: uložené chunky, vektory, jejich hashe a historie se nepřepisují a přepočet indexu není potřebný. Generování shrnutí při přípravě indexu se nemění. Odstranění proběhne až po autorizovaném SQL načtení a před rozpočtem/mergem kontextu.

Pod tokenovým limitem je **Odhad využití vstupní kapacity**. Při otevření této části nebo změně vybraného indexu/modelu se načte jeden deterministický platný chunk z dokončené fyzické verze indexu a jeho délka se v backendu lokálně spočítá v tokenech. Vzorek respektuje tenant, dokumentová i chunková oprávnění a platnost vektoru podle hashe. Nečte vektorový payload a do prohlížeče posílá pouze délky a identifikátory, nikoli text. Prázdný nebo zastaralý index nemá vzorek. Endpoint je Management-only `GET /api/search-indexes/{id}/context-sample?model_id=…`.

Vzorec je **finální počet výsledků × počet tokenů vzorku**. Změna počtu výsledků okamžitě přepočítá panel bez dalšího čtení dokumentu. Při Union se použije součet obou finálních limitů; lexikální strategie používá výchozí index stejně jako skutečný dotaz. Tlačítko **Obnovit vzorek** zopakuje načtení; nejde o náhodné losování při každém kliknutí. Staré odpovědi a požadavky předchozí relace nesmějí přepsat novější výběr.

Metadata modelu se čtou z efektivního katalogu včetně aktuálních provozních limitů. Pokud je znám `context_tokens`, vstupní rozpočet odečte `max_output_tokens` a aplikační rezervu 256. Vedle modelové kapacity se může zobrazit přísnější aplikační pojistka: stávající provider omezuje také znaky a u profilů s tokenovým kontextem konzervativně i UTF-8 bajty. Tyto limity se převádějí poměrem délek vzorku. Pokud model deklaruje jen `max_input_chars`, panel výslovně ukazuje přepočtený **limit aplikace**, nikoli domyšlenou kapacitu modelu. Překročení kteréhokoli vstupního limitu má upozornění; nic se automaticky neořezává ani nenavyšuje.

Používá se lokální referenční [tiktoken](https://github.com/openai/tiktoken) s `o200k_base`. Pro jiný model nemusí odpovídat jeho skutečnému tokenizeru. Je to odhad z jednoho chunku, který nezahrnuje systémový prompt, otázku, historii ani dodatečné sousedy. Není měřením celého požadavku ani zárukou průchodu providerovým limitem.

Závislost je součástí runtime balíčku. Docker image obsahuje veřejná data tokenizeru připravená při buildu v `/opt/tiktoken-cache`, takže při běhu není potřeba síť ani modelové API. Lokálně lze nastavit `TIKTOKEN_CACHE_DIR`; při prvním použití bez existující cache knihovna potřebuje stáhnout veřejný slovník, neposílá přitom text chunku. Chyba tokenizeru se zobrazuje jako bezpečná 503 a neblokuje běžné vyhledávání.

Obě funkce jsou zatím zdrojové změny. Lokální GUI používá izolované syntetické API a není dokladem cloudového nasazení.
