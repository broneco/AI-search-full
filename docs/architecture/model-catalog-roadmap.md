# Katalog modelů a jejich výběr

Implementované zdrojové slices 0–6; nasazení a cloudové integrační přijetí jsou samostatné.

Schválená implementace: tenantové LLM profily, Azure GPT-5.4-mini jako výchozí a GPT-5.4 jako pokročilý; JHU navíc Ollama `qwen3.8:latest`. Přepínání se týká chatu a dvou nezávislých úloh: shrnutí a klasifikace. Embeddingové profily ani indexy se výběrem LLM nemění.

## Slices a návaznosti

| Slice | Výstup | Ověření |
|---|---|---|
| 0 — kontrakt | Opakovatelný `probe_jhu_model.py`, VPN a skutečný požadovaný model | Dva syntetické dotazy; 2026-10-16 úspěch, první 92,2 s (load 86,7 s), další 4,4 s. Další start 41,9 s / 4,7 s. |
| 1 — katalog/API | Validované JSON, factory, konkrétní `model_id`, metadata odpovědí | Tenant/default/alias, neplatný soubor, žádný implicitní jiný model |
| 2 — JHU adaptér | Basic + `/api/generate`, přesně model/prompt/stream, omezený souběh | Mock chyby/timeout/limity; skutečný syntetický RAG s kódem a citací prošel |
| 3 — chatové UI | Obě konzole, popis a cloud/JHU, model u odpovědí | Oba produkční buildy; manuální scénáře v návodu |
| 4 — dokumenty | Oddělené modely klasifikace a shrnutí, skutečné shrnutí před embeddingem | Regrese providerů, žádný uložený placeholder při selhání |
| 5 — oprávnění | Management editor, SQL pravidla a revize | Autorizace, tenant, revize, odebrání skupin před voláním |
| 6 — integrace | Wheel/export, úplná sada, lokální návod a Azure handoff | 303 passed / 85 skipped v celé offline sadě; následné modelové hardening testy 27 passed / 1 skip; oba buildy, JHU kandidát a wheel prošly |

## Rozhodnutí

`model_config.json` má file-level fallback; JHU soubor explicitně obsahuje všechny tři profily. Chybný existující soubor není důvod použít default. V JSON jsou veřejné identity a popisy; secrets, endpointy a deployment names jsou v prostředí. Lokální `.env.jhu-model` se čte pouze při APP_ENV=local a má nižší prioritu než `.env.local`/process environment. Testy jej automaticky nečtou.

`GET /api/models?purpose=chat|summary|classification` nevrací připojení. `available` znamená splněné konfigurační předpoklady, nikoli živý health check. Výběr je pro další dotaz; uložená konverzace může obsahovat více modelů. Stará zpráva bez provenance zůstává bez deklarovaného modelu.

SQL `model_access_policies` ukládá přesný tenant/model, `allowed_groups`, revizi, autora a čas. Chybějící pravidlo nebo null povoluje všem, [] nikomu. Role Management umožňuje editovat pravidla, neobchází zákaz samotného modelu. Aktualizace používají porovnání revize. Chybějící tabulka je řízená chyba, nikdy důvod ignorovat oprávnění. Azure inicializace tuto tabulku sama nevytváří; použije se explicitní migrace.

Nové modelové volání před odesláním ověří současné serverové skupiny a pravidla. Background práce dostává identitu původního správce, nikoli jeho zaslané skupiny. Operátorské CLI bez uživatelské identity používá explicitní důvěryhodný provozní přístup.

Ollama používá deterministický JSON přepis rolí uvnitř `prompt`; odpověď čte pouze z `response`, nikoli thinking. JHU má souběh 1 na backendový proces, okamžitou řízenou chybu při obsazení a žádné automatické opakování/fallback. Počet replik proto zvyšuje možný souběh. Vstupní znakový rozpočet je aplikační limit, nikoli tvrzení o ověřené maximální kontextové délce serveru.

VPN byla ověřena na vývojářově Windows počítači. Chrání úsek k VPN gateway; HTTP není end-to-end TLS. Lokální adaptér před HTTP voláním ověřuje trasu, ale nevytváří síťové spojení pro Azure. Cloudové zapojení JHU zůstává samostatným integračním krokem.

## Hranice

Původní LLM slice nezahrnovala lokální embeddingy. Ty nově přidává samostatná [embeddingová slice](../development/local-embeddings.md), bez změny výběru LLM. Streaming, automatický benchmark modelů a editor credentials zůstávají mimo rozsah. API službu JHU neměníme a nestahujeme modely. Změna shrnutí při explicitním přepracování dokumentu mění text a vyžaduje nové embeddingy. Změna chatového modelu korpus nepřepracovává. PostgreSQL, OCR, section_title a sjednocení stávajících Blob/lokálních konfigurací zůstávají samostatné práce.

## Výsledek ověření

Živý syntetický test ověřil celé chatové API s Qwenem, citaci, uloženou historii, klasifikaci a skutečné shrnutí. Nový Azure adaptér odpověděl přes existující GPT-5.4-mini. Read-only Azure seznam potvrdil, že GPT-5.4 deployment na JHU dosud chybí; jeho vytvoření je oddělený schvalovaný krok. Lokální SQL port 1433 nebyl dostupný. SQLite/modelové výsledky nenahrazují skutečné SQL Server/Azure SQL ani produkční síťové přijetí. Žádné Azure prostředky ani Git repozitáře nebyly publikováním těchto zdrojových změn upraveny.


## Rozšíření: všechny kompatibilní lokální modely

Tenantový SQL registr lokálních profilů, jejich explicitní přidání ze serverového inventáře, revize publikace a propojení obou konzolí jsou implementované. Embeddingové recepty zahrnují Nomic i MXBAI; uživatel vybírá jeden připravený a povolený index UUID. Všechny nové modelové volby jsou oddělené od výchozí ingestace. [Provozní postup](../development/local-model-registry.md). Dalším krokem je ruční relevance/latence vybraných modelů; plošný benchmark ani cloudové nasazení nejsou automatické.
