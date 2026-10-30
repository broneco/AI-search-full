# Obnova frontendů po výpadku

[frontend_resilience.cjs](../../tests/frontend_resilience.cjs) spouští Node test runner proti skutečným TypeScript utilitám obou konzolí. Potřebuje Node a nainstalované vývojové závislosti `frontend-admin`; nevyžaduje běžící backend ani přístup k Azure.

```powershell
node --test tests/frontend_resilience.cjs
```

Osm scénářů ověřuje bezpečnou chybu při textovém/HTML 502/504, odmítnutí neplatného úspěšného JSON, timeout také při čtení těla a zrušení volajícím. Pouze 401 patřící stále aktuálnímu tokenu označí relaci za expirovanou; 403/422/5xx ani stará odpověď nesmějí odhlásit novější relaci.

Po selhání prvního načtení lze znovu zvolit deklarovaný dostupný výchozí model/index. Explicitní volba se při ztrátě dostupnosti tiše nenahrazuje. Health poll nemá současně více aktivních požadavků a cleanup zruší probíhající čtení bez pozdější aktualizace UI.

Testy nepředstavují skutečnou browser/produkční akceptaci. Tu je nutné provést zvlášť s oběma konzolemi a skutečnými rolemi.
