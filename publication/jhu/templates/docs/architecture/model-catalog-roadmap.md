# Modelové profily


`model_config.json` má file-level fallback; JHU soubor explicitně obsahuje všechny tři profily. Chybný existující soubor není důvod použít default. V JSON jsou veřejné identity a popisy; secrets, endpointy a deployment names jsou v prostředí. Lokální `.env.jhu-model` se čte pouze při APP_ENV=local a má nižší prioritu než `.env.local`/process environment. Testy jej automaticky nečtou.

`GET /api/models?purpose=chat|summary|classification` nevrací připojení. `available` znamená splněné konfigurační předpoklady, nikoli živý health check. Výběr je pro další dotaz; uložená konverzace může obsahovat více modelů. Stará zpráva bez provenance zůstává bez deklarovaného modelu.

SQL `model_access_policies` ukládá přesný tenant/model, `allowed_groups`, revizi, autora a čas. Chybějící pravidlo nebo null povoluje všem, [] nikomu. Role Management umožňuje editovat pravidla, neobchází zákaz samotného modelu. Aktualizace používají porovnání revize. Chybějící tabulka je řízená chyba, nikdy důvod ignorovat oprávnění. Azure inicializace tuto tabulku sama nevytváří; použije se explicitní migrace.

Nové modelové volání před odesláním ověří současné serverové skupiny a pravidla. Background práce dostává identitu původního správce, nikoli jeho zaslané skupiny. Operátorské CLI bez uživatelské identity používá explicitní důvěryhodný provozní přístup.

Ollama používá deterministický JSON přepis rolí uvnitř `prompt`; odpověď čte pouze z `response`, nikoli thinking. JHU má souběh 1 na backendový proces, okamžitou řízenou chybu při obsazení a žádné automatické opakování/fallback. Počet replik proto zvyšuje možný souběh. Vstupní znakový rozpočet je aplikační limit, nikoli tvrzení o ověřené maximální kontextové délce serveru.

VPN byla ověřena na vývojářově Windows počítači. Chrání úsek k VPN gateway; HTTP není end-to-end TLS. Lokální adaptér před HTTP voláním ověřuje trasu, ale nevytváří síťové spojení pro Azure. Cloudové zapojení JHU zůstává samostatným integračním krokem.

## Hranice

Lokální embeddingy přidává samostatná slice: viz [Nomic a více indexů](../development/local-embeddings.md). Streaming, automatický benchmark modelů a editor credentials zůstávají mimo rozsah. API službu JHU neměníme a nestahujeme modely. Změna shrnutí při explicitním přepracování dokumentu mění text a vyžaduje nové embeddingy. Změna chatového modelu korpus nepřepracovává. PostgreSQL, OCR, section_title a sjednocení stávajících Blob/lokálních konfigurací zůstávají samostatné práce.


## Rozšíření: všechny kompatibilní lokální modely

Tenantový SQL registr lokálních profilů, jejich explicitní přidání ze serverového inventáře, revize publikace a propojení obou konzolí jsou implementované. Embeddingové recepty zahrnují Nomic i MXBAI; uživatel vybírá jeden připravený a povolený index UUID. Všechny nové modelové volby jsou oddělené od výchozí ingestace. [Provozní postup](../development/local-model-registry.md). Dalším krokem je ruční relevance/latence vybraných modelů; plošný benchmark ani cloudové nasazení nejsou automatické.
