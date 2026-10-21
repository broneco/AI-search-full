# Testy bezpečné údržby

Synthetic provider fixture nyní deklaruje odpovídající embeddingový prostor také v testových settings, aby pipeline prošla skutečným ověřením tenantového katalogu; nepřeskakuje novou kontrolu profilu.

`tests/test_maintenance.py` běží nad vlastní paměťovou SQLite se dvěma tenanty a skutečnými repository/ingestion zápisy. Modely a Blob jsou nahrazené; soubory vznikají v pytest temp adresáři.

Ověřuje, že fast reindex čte/embeddí pouze přesný tenant včetně suffixu a chybějící zdroj nezamění za stejně pojmenovaný cizí soubor. Full refresh nevolá zápisy při chybějícím či prázdném zdroji, modelová chyba zachová původní data a stale cleanup nikdy nezasáhne cizí tenant. Pokrývá také výchozí read-only CLI plán, potvrzení cíle, pozdní selhání, nové souběžné uploady, změnu stale dokumentu a přesun vztahů na nová UUID. Model při detekci vztahu nedostane názvy cizích dokumentů.

Spuštění: `python -m pytest tests/test_maintenance.py -q`. SQLite zde neprokazuje výkon ani native Azure DDL.
