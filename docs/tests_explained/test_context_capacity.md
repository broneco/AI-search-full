# Testy shrnutí a odhadu kontextu

`tests/test_context_capacity.py` ověřuje nové nastavení přes skutečný retrieval, SQL/API a lokální tokenizer. Parametrizované databázové fixtures běží nad SQLite a volitelně skutečným lokálním Microsoft SQL Serverem (`RUN_LOCAL_SQL_TESTS=1` podle návodu v `test_search_access.md`). Nevolají JHU ani jiné modelové API.

- Zapnutá volba odstraní shrnutí obou sousedů, zachová jejich tělo i shrnutí nalezeného chunku. Vypnutá zachová všechna shrnutí. Obsah a hashe uložených chunků se nezmění.
- Parser odstraní pouze generovaný prefix na začátku včetně víceřádkového shrnutí; citovaný řetězec uvnitř dokumentu zůstane. Konfigurace zachová explicitní `false` při uložení/načtení a implicitně používá `true`.
- API vrací přesný počet referenčních tokenů uloženého vzorku a délky, žádný obsah; databázi nemění ani nepoužije embedding provider.
- Po úpravě logického indexu vzorek pochází z dokončené nové fyzické verze, nikoli ze starého korpusu.
- Cizí tenant, uživatel bez Management a nepovolený model jsou odmítnuti ještě před tokenizací. Stará hash revize vektorů nedá vzorek.

```powershell
$env:OPENBLAS_NUM_THREADS = '1'
$env:OMP_NUM_THREADS = '1'
$env:TIKTOKEN_CACHE_DIR = "$PWD/.local/tiktoken-cache"
& ./.venv/Scripts/python.exe -m pytest tests/test_context_capacity.py
node --test tests/frontend_resilience.cjs
```

Tokenizer potřebuje veřejná data v cache (při prvním lokálním použití je stáhne); Docker je připravuje při buildu. Frontendové testy ověřují násobek a dynamickou změnu počtu výsledků, tokenový/znakový rozpočet, přísnější aplikační limit, nulový rozpočet a chybějící vzorek. Instalovaný wheel test importuje nový modul a skutečně tokenizuje syntetický text mimo checkout.

Lokální GUI akceptace proti disposable API ověřila checkbox zapnuto/vypnuto, save/reload a změnu 5×240=1200 na 10×240=2400 tokenů včetně upozornění na přísnější limit. Backend testy používají skutečnou SQL vrstvu; GUI metadata jsou syntetická. Offline Docker kontrola `--network none` importovala modul a spočítala český syntetický text. Tato evidence nenahrazuje Azure/JHU akceptaci.
