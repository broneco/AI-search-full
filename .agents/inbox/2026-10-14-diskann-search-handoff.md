# Azure Deployment Handoff: DiskANN v3+ — cloudová brána ve slice 5

- Status: waiting-for-human (odloženo na slice 5 na přání uživatele)
- Created: 2026-10-14
- Related task: search slice 4, combined native exact/ANN validation in slice 5
- Related ADR: docs/adr/ADR-0024-explicit-diskann-search-and-failure-policy.md
- Related branch/PR: uncommitted local implementation; no cloud deployment

## Why this handoff exists

**Aktualizace 2026-10-14:** skutečný native ANN lifecycle na Showcase v izolovaném schématu nyní prošel: v3 COSINE enabled1536, selective/empty/fullK, oba ACL/tenant, revize/reembedding/update/rollback/cascade. Native exact také prošel. Vlastní objekty jsou uklizeny a dbo counts stejné. Opravené DDL/autocommit, bind typy a korelované EXISTS jsou lokálně v kódu; nejsou nasazené do běžící Container App. Runtime identity/API/migrace, representative recall/performance a ANN activation dále čekají; výkon uživatel odložil na JHU. Aktuální výsledky a rozsah souhlasu viz slice5 handoff.

Lokální SQL Server 2022 ověřuje reference/ACL/kontrakty, nikoli nativní Azure DiskANN. Člověk musí před cloudovou aktivací potvrdit actual index verzi, SQL syntax/permissions/query plans a výkon Basic 5 DTU. Do té doby pokračují lokální testy, běžný runtime exact a vývoj slice 5. Tento handoff nepožaduje okamžité vytvoření placeného Azure zdroje.

## Goal

V oddělené prázdné Azure SQL test DB projít exact i ANN integrační test a následnou slice 5 evaluaci. ANN zapnout v cílovém provozu až při splnění recall/performance bran; dosavadní indexy ponechat pro návrat.

## Resources to create or modify

| Resource | Action | Suggested name | Required settings | Notes |
|---|---|---|---|---|
| Azure SQL test DB | samostatně vytvořit/použít | `<empty-vector-test-db>` | potvrzený host/name; `test` v názvu; nejprve bez tabulek | Stejná izolace jako handoff slice 3; nepoužívat aplikační DB. |
| Native vector tables | vytvoří test/explicitní CLI | `dbo.chunk_vectors_<UUIDhex>` | VECTOR float32, int clustered PK, chunk FK cascade | Katalog/profil a ACL schema podle předchozích handoffů. |
| DiskANN index | vytvoří test/CLI | `diskann_<UUIDhex>` | cosine, enabled, Version ≥3, MAXDOP 1 | ≥100 aktuálních vektorů a úplné pokrytí; create samo režim nepřepíná. |
| Runtime configuration | změnit až po evaluaci | stávající tenant config | vector_search_mode exact/ann, vector_query_timeout_seconds 10 | Použít Management API / Blob konfiguraci; neměnit kapacitu bez schválení. |

Azure vector index ≥3 nemá zvláštní version flag: CREATE použije aktuální formát a verze se následně ověří. Skutečné Azure ověření 2026-10-14 odmítlo CREATE uvnitř transakce chybou574. DDL proto běží na odděleném AUTOCOMMIT připojení, s ukončenou caller transakcí a uzavřeným read-only preflightem. Verzi kontrolujeme po DDL; rollback vytvoření nelze slíbit. Starší/neznámá verze znamená odmítnutí ANN a zachování exact; stav se ručně prověří před případným explicitním DROP/recreate. Automaticky nemažeme existující index ani nezapínáme ALLOW_STALE_VECTOR_INDEX. Pokud cílový tier/engine nepodporuje tuto cestu, vrátit omezení člověku; nenasazovat post-filter pseudořešení.

## Required app configuration keys

Pro native test: ignorovaný `.env.native-test` s AZURE_SQL_HOST/DB/USER/PASSWORD/DRIVER a případným portem podle handoffu slice 3. Šifrování yes, TrustServerCertificate no, samostatný potvrzený testovací cíl. Nové env ani modelové secrets tento slice nepřidává. Runtime search JSON má `vector_search_mode` default exact a `vector_query_timeout_seconds` default 10 (int 1..120).

## Human-completed values

Vrátit pouze ne-tajné údaje: resource group, region, SQL host, prázdná test DB, engine/service version, DB tier, auth mode/driver, potvrzení SQL oprávnění, vytvořený index ID/name/version/metric/enabled a stručný výsledek testů. Do repozitáře nepsat hesla ani tokeny. Account pro DDL potřebuje ALTER tabulky; runtime potřebuje SELECT tabulek/katalogové viditelnosti a běžná ingestující DML oprávnění, nemusí mít DDL.

## Secrets that must exist but must not be pasted here

Stávající SQL přihlašovací údaje v Key Vaultu nebo ignorovaném env; žádný nový Azure model deployment nebo API key pro syntetické testy není potřeba.

## Validation steps for human

1. Dokončit slice 2 schema/ACL/Unicode handoff a slice 3 native přípravu pro potvrzené testovací prostředí; nepředpokládat cloudové nasazení podle lokálního testu.
2. Spustit oba nativní testy přes [návod slice 4](../../docs/development/search-slice-4-testing.md). Oba opt-in musí být výslovně zapnuté; pytest vytvoří/smaže své tabulky ve zcela prázdné test DB a nevytváří/neruší celou Azure DB.
3. Ověřit query plans pro oba ACL EXISTS a metadata JSON predikáty. ANN používá WITH APPROXIMATE + FORCE_ANN_ONLY; error/timeout vede k řízené chybě bez dalšího scanu. Ověřit aplikaci i s runtime oprávněními, ne jen SQL adminem.
4. Při nativní CLI přípravě již potvrzeného cíle nejprve audit a vybrat existující UUID. Mutace `--index <UUID> --create-ann --expect-host <HOST> --expect-db <DB> --expect-tenant <TENANT>` vyžaduje shodu se skutečným nastavením procesu. Nepoužívat lokální `.env.local` pro Azure. `--ann-status` je read-only; starý index se nepřebudovává automaticky.
5. Slice 5: ≥100 označených dotazů, average recall@30 ≥95 % vůči exact; rozdělit podle selektivity. Zátěž ≥200 dotazů pro concurrency 1 i 3, p95 celého retrievalu ≤1 s bez embedding/LLM; preflight/catalog čas měřit a přičíst k retrieval nákladům v reportu, cold start zvlášť. Basic 5 DTU / 0,5 CPU / 1 GiB automaticky nezvyšovat.
6. Teprve po výsledcích uložit celou současnou search konfiguraci přes Management API s mode ann; běžný dotaz má jeden aktivní profil. Změny DDL/aktivace dělat s pozastavenými ingestujícími úlohami a maintenance oknem. API metadata musí uvést ann a správný profil/index.

## Validation steps for agent after completion

Zaznamenat skutečné výsledky a omezení, ověřit verzi ≥3, profile coverage, SQL plány, query aliases/parameters, oba ACL, rollback/cascade a error policy. Bez cloudového výsledku zůstává status neověřeno, žádné claims o recall/p95.

## Rollback

Management načte celou aktuální konfiguraci, změní pouze vector_search_mode na exact a uloží ji zpět přes config API, které zapisuje i cloudovou Blob konfiguraci. Native tabulka, profil a embeddingy zůstávají stejné. ANN index není potřeba mazat; exact používá VECTOR_DISTANCE. Při potřebě návratu na jiný logický index použít explicitní coverage-checked aktivaci se zastavenými writery. Nepřepínat do legacy JSON ani jiného modelu podle pouhé shody rozměru.

## Open issues

- [x] Native exact i ANN lifecycle skutečně prošly na izolovaném Showcase schématu; v3/COSINE/enabled1536, cleanup a dbo counts potvrzeny.
- [ ] Runtime-account permissions, komplexní prefilter query plans a reálná latence neověřeny.
- [ ] Recall/performance benchmark a bezpečná provozní aktivace patří do slice 5.
- [ ] SQL Server 2025 Docker jako lokální native test prostředí je stále návrh; v tomto slice se instalace ani stávající volume neměnily.
