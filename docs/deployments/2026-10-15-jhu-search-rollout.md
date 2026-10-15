# JHU search rollout — 2026-10-15

## Aktuální v0.1.4 — keyword nasazen, ANN připravené a vypnuté

Backend **revize0000008**, image **`prod-v014-20261015-145009`**, i oba existující frontendy byly nasazeny a ověřeny ve verzi v0.1.4. Live HTML obou SWA odpovídá novým buildům. Stav indexů: skutečný DiskANN v3 nad původním profilem, Czech1029 FTS9372řádků/population0, coverage9372/9372. **Runtime stále exact, Blob search config nebyl aktivací vytvořen/upraven.** User požádal o vysvětlení zhoršení ANN místo výběru adaptivní varianty; rozhodnutí o další strategii je otevřené, žádné adaptivní přepínání se neimplementovalo.

Skutečný image digest `sha256:8704a1ec3fd3dcec3206c405a23caafa26cff47aa53e4248b91b8ebeb05bfba0`; pull/run s network=none ověřil0env souborů, žádný corpus/data a žádný frontend. Privátní checkpoint má keyword_deployment_completed=true, deployment_completed=false a image_exclusions_verified=true: nezaměňovat dokončený keyword release s nedokončenou ANN aktivací.

Aktuální skutečné HTTP smoke flash/thinking: oba200+5citací, User72dokumentů, autentizované PDF200, vlastní dočasný účet/konverzace odstraněné. Diagnostika retrievalu **3927/2117ms**, vector1196/588ms, keyword1123/365ms, fusion1/1ms, expansion1608/1163ms. Původní obdobné runtime smoke28553/29381ms: výrazný pokles bez ANN. Dvě měření nejsou p95 ani akceptace≤1s. Local FINAL **298passed/13expectedskips**, native keyword **10passed** s cleanup; žádné potřebné regrese nezůstaly červené.

ANN runtime překvapení: původní přímý ACL join timeoutoval5/10s. Nová úplná SQL materializace ID/revizí (bez capu), vynucené ANN a scoped NOCOUNT odstranily tento problém u60User dotazů (mean recall@30 **0,991111**), ale100dotazový běh se zastavil u první Management otázky (v tehdejším runneru nebyl zaznamenán mode selhání). Samostatné bounded probe potvrzuje **Management+languagecs vynucené ANN>5s**, bez metadata325ms; RECOMPILE nepomohl. Nativní optimizer bez FORCE byl u jednodušších dotazů~1s, materializovaný Management+cs8768ms. Nelze tvrdit, že je problém vyřešen univerzálně nebo že100dotazová ANN recall brána prošla. Kvalitativní/performance akceptace slice5 zůstává otevřená.

Finální agregované počty **431docs/9372chunks/7users/31threads/58messages**; původní dokumentová/chunková UUID a texty zachované. Počty31/58 již existovaly při izolovaných testech před keyword rollout; vlastní smoke je nezměnil. Oproti starému prvnímu DPAPI snapshotu se liší1hash původního uživatele, což je slučitelné s dříve nasazeným login→Argon2 upgradem; tento operátorský postup nepřepisoval hashe původních uživatelů. CORS, identity/CPU/RAM/scale, Unicode a odstranění inline secrets znovu ověřeny. Žádná změna SKU/RBAC/credentials, reembedding či rechunking. ANN fyzický index je ponechaný připravený; nic nesnižuje běžné oprávnění.

**Návrat:** do dalšího výkonového rozhodnutí ponechat exact. Aktuální v014/rev8 je funkčně ověřený baseline pro keyword; předchozí kompatibilní v013/rev7 je uchovaný. Nespouštět znovu původní tenant/full-refresh migrace. Jestli se později aktivuje ANN, návrat nastavení je explicitní exact nad stejnou tabulkou/profilem; timeout sám nezahájí druhý scan. Vyhodnotit skutečný dotazový plán, selektivitu a náklad expansion, nikoli automaticky navyšovat kapacitu.

### Historie přípravy v0.1.4

Výslovné zadání uživatele: zapnout ANN, opravit keyword a zvýšit verzi v jednom slicu. ADR0028 mění dřívější zákaz aktivace na řízené provozní ověření; formální reprezentativní výkonové brány zůstávají otevřené. Připraven image `prod-v014-20261015-140148`, oba produkční frontend buildy/TypeScript prošly. Konečné lokální regrese297passed/12expectedskips; skutečný izolovaný Azure keyword test10passed včetně Czech/English slov, ACL/tenant/metadata před K a cleanup. Byly opraveny skutečné ODBC typy a CONTAINSTABLE grammar, testy respektují skutečný SYSTEM stoplist (české „a“ na tomto serveru není stopword). Snapshoty `v014-before-app`, `v014-before-fulltext`, `v014-before-search-config` jsou DPAPI v původním privátním rollout adresáři. Další checkpoint v `.local/deployments/jhu-ann-20261015/`; zatím netvrdit runtime aktivaci. Níže je zachován původní exact rollout jako historie/baseline.

## Výsledek a rozsah

Uživatel výslovně povolil agentovi provést připravené deployment kroky. Funkční rollout na existujícím JHU `prod` je dokončený: backend a oba frontendy, přesný tenant korpusu, Unicode, ACL projekce, nativní profilové VECTOR úložiště a Key Vault JWT/credentials. **ANN není aktivní a výkonová akceptace slice5 není splněná.** Žádné nové RBAC role/identity, nové databáze, změna SQL tieru nebo CPU/RAM/scale.

| Cíl | Hodnota |
|---|---|
| Azure directory / subscription | `c35f5da4-9a03-44e6-8bf9-92833634f6a7` / `24e4a9a6-bab0-43f7-ba20-3b774704fade` |
| Resource group | `ju-ai-search-rg-prod` |
| Backend | `ju-ai-search-ca-prod`, ready revision `ju-ai-search-ca-prod--0000007` |
| Image | `juaisearchcrprod.azurecr.io/ju-ai-search-ca-prod:prod-search-20261015-124847` |
| Image digest | `sha256:1ceb6e0c2e5f1d31de9aef4f19fcee8d503ab56efe7c8fb23cdb63265458bfd6` |
| SQL | `ju-ai-search-sql-prod.database.windows.net` / `ju-ai-search-sqldb-prod`, Standard10DTU, compatibility170 |
| Runtime | 0,5CPU /1GiB, min1/max3, Single revision |
| User frontend | https://nice-forest-03f01f203.6.azurestaticapps.net |
| Admin frontend | https://kind-tree-0c95d5203.2.azurestaticapps.net |
| Index / profile | `b1e81c70-686c-481a-bbff-e15f034288ef` / `364c43c779759bbbc82f466102315cc3928fa22599a7dee323e019b4c6e7cb09` |
| Vector mode | native1536/float32, **exact**, coverage9372/9372 |

Working tree nebyl commitnutý ani pushnutý; ACR build použil připravené lokální zdroje. První build `prod-search-20261015-121816` zůstal zachovaný, po otestované optimalizaci backfillu vznikl nový jednoznačný tag výše. Docker základ je Bookworm podle Microsoft ODBC repozitáře. Provozní skript `scratch/jhu_rollout.py` zůstává v tomto pracovním adresáři ignorovaný Gitem; nejde o veřejný API endpoint nebo obecný one-click deploy.

## Provedené změny a ochrana dat

- Backend byl během datové migrace zastavený přes existující Container Apps stop/start, ověřeno nula replik. Definice kapacity zůstala stejná. Dostupný SQL restore interval byl ověřen (earliestRestoreDate 2026-10-08), před migrací zaznamenán čas 2026-10-15 12:31:34 UTC.
- Původní konfigurace a dotčená data byly lokálně uloženy šifrovaně Windows DPAPI a roundtrip ověřen. Artifacts `.local/deployments/jhu-search-20261015/`: `before-app.dpapi`, `before-data.dpapi`, `old-runtime.dpapi` a ne-secret `state.json`. Nelze je bezpečně vypsat, commitovat ani automaticky přenášet na jiný účet/stroj; DPAPI je svázané s aktuálním Windows uživatelem. Nejde o provedený test obnovy celé SQL DB.
- Přesně `ju`→`ju-prod` pro431documents/9372chunks, se zachováním UUID/textů. `users` zůstali3×ju +4×ju-prod, bez sloučení (audit nalezl3 duplicitní identity mezi aliasy).
- Čtyři textové sloupce převedeny na NVARCHAR. Původní FTS zachycen a obnoven: `ftCatalog`, původní PK, language1033, changeTrackingAUTO, SYSTEM stoplist. Malá vlastní Azure FTS test tabulka byla odstraněna, žádný testovací objekt nezůstal. Finální populationStatus0.
- Vytvořeny/backfill relační granty:761document /16677chunk. Vytvořen profilový katalog a native VECTOR tabulka, z textů vytvořeny nové embeddingy přes explicitní JHU model text-embedding-3-large/version1/dim1536, poté úplná coverage a aktivace exact. Bez reextrakce, rechunkingu nebo full-refresh mazání; staré JSON vektory zůstaly.
- Během backfillu odstraněno N+1 ověřování po jednom chunku: dávkové čtení s MSSQL UPDLOCK/HOLDLOCK po modelovém volání, bez přenášení starého JSON v prvních čteních. Regrese zachovávají detekci změněného vstupu a transakční záruky. Vlastní pomalý worker byl ohraničeně ukončen, jeho nepotvrzená transakce rollbackla; navazující worker přeskočil platné uložené dávky a doplnil7292chunků. Celkem9372platných, žádné směšování modelových profilů.

## Key Vault, modely a přihlášení

Backend již měl Key Vault Secrets User na `ju-ai-search-kv-prod`; role ani identity se neměnily. Vytvořeny tři secrets (hodnoty nejsou v tomto dokumentu):

- `ju-ai-search-jwt-signing-key-prod`, version `122282707eab47e48c5ba089313c259c` — nový náhodný signing klíč, verze připnutá v runtime.
- `ju-ai-search-legacy-password-key-prod`, version `623b3434582641aaa8bb193827f10b65` — původní klíč soukromě ověřený přímo z dosud nasazeného image, pouze verifier starých hesel.
- `ju-ai-search-openai-api-key-prod`, version `8092aa84e0bb42d1ac6abe649d3a9956` — existující funkční JHU credential, bez rotace modelového klíče.

SQL/Storage values byly porovnány s existujícími KV secrets a shodovaly se. Inline SQL/Storage/OpenAI/JWT/legacy hodnoty v Container App odstraněny, nové runtime používá KV názvy. Skutečný login, chat a PDF prokázaly přístup běžící identity k potřebným secrets. Žádné `.env` soubory nebyly smazány nebo upraveny. Původní image skutečně používal Dolphin model endpoint; nová verze má výslovně JHU endpoint a `gpt-5.4-mini` pro flash i thinking. Samostatně ověřen skutečný embedding i chat call.

Přepnutí bylo nejdříve bez legacy verifieru, ověřeno vlastním dočasným Argon2 účtem, teprve poté zapnut oddělený KV legacy verifier v revizi0000007. Druhý vlastní dočasný účet prokázal skutečný SHA256 legacy login → Argon2 upgrade. Oba účty i jejich konverzace byly odstraněné. Původní heslové hashe se při nasazení nezměnily (finální porovnání:0); skutečný uživatel zachová heslo a při úspěšném přihlášení se jeho hash modernizuje. Staré session tokeny po novém podpisovém klíči neplatí, je nutné nové přihlášení.

## Skutečně provedená validace

- Celá lokální sada po všech kódových změnách: **288passed /11expectedskips**,135,57s. Skips: dva volitelné model calls, dva native Azure test opt-ins a sedm SQLite variant vyžadujících MSSQL. Předchozí native Showcase exact/ANN výsledky zůstávají samostatnou historií, nejsou nahrazené lokálním testem.
- Oba Next.js produkční buildy včetně TypeScript prošly. Obě existující SWA publikovány přes CLI2.0.10, deployment token jen v paměti; živé HTML obou aplikací přesně shodné s lokálními artifacty.
- Skutečný nasazený image byl stažen a spuštěn lokálně s vypnutou sítí pouze pro kontrolu souborového systému: **0 env souborů**, žádný lokální korpus ani frontend adresář. Digest ověřen přímo z ACR. Není to pouze statická kontrola `.dockerignore`.
- Běžící JHU: autentizovaný `/api/auth/me`200; přihlášení nového/legacy vlastního účtu200; nepřihlášené dokumenty401; User reindex403; dokumentů viditelných pro testovací User72; flash i thinking hybrid chat200 s5citacemi; autentizované PDF200 se skutečnými PDF bytes.
- CORS OPTIONS200 pro uživatelskou SWA: konkrétní origin, povolené authorization/content-type a GET/POST/OPTIONS. Původní CORS/ingress konfigurace nemusela být změněná.
- Finální počty **431docs /9372chunks /7users /29threads /54messages**; původní dokumentové/chunkové UUID a texty identické se snapshotem, původní uživatelé a hashe zachované. Unicode a FTS ověřeny. Identita/CPU/RAM/scale zachované, inline secrets odstraněné.

## Výkon — otevřený konkrétní problém

Dva funkční hybrid smoke requesty v Azure hlásily vektorovou část **805ms /435ms**, ale diagnostiku retrievalu **28553ms /29381ms**. To není reprezentativní p95 benchmark ani úspěch výkonové brány; jsou to dva konkrétní pomalé requesty. Příčinu zbývajícího času je třeba odděleně profilovat mezi keyword, fusion/filtry a expansion. Nelze ji bez měření připsat jen jedné větvi ani očekávat, že ji odstraní ANN, když native exact vektorová část už byla pod sekundou.

Blob `config/search_config.json` v JHU originals při kontrole chyběl; backend používá existující file fallback (default JSON, exact). Žádný tichý přechod na ANN, snížení context expansion nebo navýšení kapacity se neprovedlo. Recall100queries, souběhy1/3, p95≤1s, cold start a aktivace DiskANN zůstávají mimo akceptaci tohoto rollout.

### Read-only diagnostika po nasazení (2026-10-15)

Jeden diagnostický běh z pracovního počítače proti stejné JHU SQL DB, bez zápisů, bez modelových volání a s kontextem `ju-prod` / skupina User: osmislovný dotaz ve tvaru shrnutí názvu dostupného dokumentu. Původní `_get_fts_candidates` trval **26473ms** pro10výsledků, `_apply_filters` po zaokrouhlení **0ms**, page expansion prvních5výsledků **1220ms**. Nejde o stejný HTTP smoke ani reprezentativní benchmark; síťová latence počítač→Azure je zahrnutá. Název ani obsah dokumentu nebyl vypsán.

Azure/MSSQL keyword implementace v `app/retrieval/vector.py` používá `LIKE '%slovo%'` a výpočet četnosti přes `LOWER/LEN/REPLACE`, nikoli `CONTAINSTABLE`. Existující enabled fulltext index nad chunks.content má language1033 (angličtina). Jeho pouhá existence tuto SQL větev nezrychlí. Keyword SELECT navíc hydratuje celé DBChunk včetně starého JSON embeddingu, který keyword skóre nepotřebuje. To je další odstranitelný náklad, jeho samostatný podíl zatím není změřen.

Index inventory potvrdilo chunks pouze PK(chunk_id) a tenant_id index; chybí přístupová cesta přes document_id/page_number/chunk_index pro page expansion. ACL mají PK i relační skupinové indexy. DMV za posledních5minut:19vzorků, průměr CPU14,02%, maximum97,92%, data IO0%; maximum nelze přiřadit výhradně tomuto dotazu a průměr není důkazem trvalého vytížení.

Další doporučený slice: nativní parametrizovaná FTS větev se stejnými tenant/docACL/chunkACL/metadata filtry před finálním TOP K (ne globální `top_n_by_rank` před ACL), testy změněné sémantiky slov/rankingu a češtiny; vynechat JSON embedding z keyword SELECT. Samostatně změřit a optimalizovat page expansion podle plánu. ANN lze připravit nad stávajícími9372nativními vektory bez reembeddingu, ale vybudování indexu samo nepřepíná režim. Před běžnou aktivací zůstávají platné schválené recall/performance brány; návrat pouze `vector_search_mode=exact` nad stejným profilem. V tomto šetření nebyl vytvořen ANN index ani změněna runtime konfigurace/kapacita.

## Návrat a další krok

Aktuální nový image/revize je funkčně ověřený Argon2-compatible baseline pro příští release. Původní image20261008 nepoužívat jako prostý rollback po modernizaci hesel; neumí Argon2 a má staré auth/ACL vlastnosti. Před prvním ověřením nebyl legacy přechod povolen, takže případný návrat v této fázi nemusel měnit původní credentials. Po aktivaci používat kompatibilní baseline, zachovat profil/tabulky/Unicode a vracet jen přesně prověřené změny. Nepřevádět text zpět na VARCHAR ani plošně nepřepisovat password_hash starou zálohou.

**Jeden další slice:** změřit rozpad pomalého celého retrievalu na JHU a opravit hlavní nákladnou větev se stejnými filtry/ACL. ANN teprve po samostatných recall/performance branách. Dříve odložené PostgreSQL, section_title, sjednocení Blob/file konfigurace a OCR zůstávají odložené.
