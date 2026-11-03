# Obnova frontendů po výpadku

Snapshot nového indexu navíc přenáší jen parametry chunkování a skutečně zvolené pomocné modely. Regrese vylučuje rankingové hodnoty, ověřuje chybějící konfiguraci a nepřidává neaktivní modely shrnutí/AI dělení.

Odhad kontextu testuje násobek počtu výsledků a tokenové délky vzorku, změnu počtu bez dalšího načtení, tokenová metadata modelu, přepočet ze znaků při neznámém kontextu a přísnější aplikační pojistku. Chybějící vzorek a nulový rozpočet nesmějí vrátit zavádějící procento. Soubor nyní obsahuje 11 scénářů.

[frontend_resilience.cjs](../../tests/frontend_resilience.cjs) spouští Node test runner proti skutečným TypeScript utilitám obou konzolí. Potřebuje Node a nainstalované vývojové závislosti `frontend-admin`; nevyžaduje běžící backend ani přístup k Azure.

```powershell
node --test tests/frontend_resilience.cjs
```

Osm scénářů ověřuje bezpečnou chybu při textovém/HTML 502/504, odmítnutí neplatného úspěšného JSON, timeout také při čtení těla a zrušení volajícím. Pouze 401 patřící stále aktuálnímu tokenu označí relaci za expirovanou; 403/422/5xx ani stará odpověď nesmějí odhlásit novější relaci.

Po selhání prvního načtení lze znovu zvolit deklarovaný dostupný výchozí model/index. Explicitní volba se při ztrátě dostupnosti tiše nenahrazuje. Health poll nemá současně více aktivních požadavků a cleanup zruší probíhající čtení bez pozdější aktualizace UI.

Testy nepředstavují skutečnou browser/produkční akceptaci. Tu je nutné provést zvlášť s oběma konzolemi a skutečnými rolemi.

Výběr nově registrovaného embeddingu se testuje nad neuspořádaným registrem: první položkou může být chatový model nebo jiná embeddingová recipe. Zvolit lze pouze konkrétní candidate ID se stejným modelem/digestem a druhem embedding; nejednoznačnost nebo změněný digest se nesmí tiše nahradit.

Administrace používá sdílený nativní dialog ProcessingProgress pro indexy i rechunking. Průběh lze zavřít a znovu otevřít bez zastavení úlohy; pollování je sériové a stará identita ruší rozpracované požadavky. Seznam indexových souborů se načítá pouze při otevřeném okně.
