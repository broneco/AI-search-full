# ADR-0026: Kontrolované nasazení existující aplikace bez ingestace

- Status: accepted (lokální implementace; cloudový rollout neschválen)
- Date: 2026-10-15
- Owners: AI Search Core Team

## Context

Nasazení search sliců vyžaduje samostatné tenant/Unicode/ACL/profilové migrace. Původní backend skript přepisoval `ju-prod` na `jhu-prod`, mohl smazat existující Container App a vždy spouštěl full-refresh ingestaci. Image obsahoval tenant env soubory, zatímco modely/JWT nebyly runtime nastavené. JHU audit potvrdil navíc dokumenty `ju` vs aplikaci `ju-prod`.

## Decision

`deploy_backend.ps1` má výchozí čtecí plán. Umí pouze build jedinečného tagu a image update jedné existující aplikace. Pro apply musí operátor potvrdit subscription, Azure directory, předchozí image, dokončení databázové migrace a JWT/login migrace. Skutečné runtime tenant/SQL cíle musí přesně odpovídat explicitnímu tenant souboru. Adresářový alias ju→jhu se nesmí použít jako přepis datové identity.

Konfigurace a secrets pocházejí z runtime, nikoli image. Dockerfile kopíruje jen app, ne-secret tenant assets a provozní CLI; .dockerignore vyloučí env i v podadresářích, privátní klíče, data, frontendy a lokální artefakty. Release nic neprovisionuje, nečte KV/ACR credentials, nemění kapacitu/ingress/identity/secrets a nedělá reingest. Starý kombinovaný deploy je blokovaný, protože plán backendu nesmí pokračovat zápisem frontendů.

## Consequences

Existující provoz vyžaduje před prvním takovým deployem samostatnou přípravu runtime a všech migrací. SecretRef přítomnost neprokazuje jeho platnost ani sílu klíče; operátorské potvrzení nezastupuje funkční test. Plan obsahuje blokery a nikdy netvrdí cloudovou akceptaci podle samotného zdraví API. Během buildu se znovu porovná template/configuration; pro eliminaci zbývajícího souběhu je nutné údržbové okno. Žádné automatické rollbacky databáze či druhé nákladné operace po chybě.

## Validation and follow-up

### Schválený JHU rollout 2026-10-15

Uživatel následně povolil provést deployment kroky. Jednorázový `scratch/jhu_rollout.py` odděleně řídí snapshoty, existující KV secrets, stop/start, migrace, embeddingy, image/config patch a SWA release. Univerzální deploy_backend zůstává image-only/plan default. Citlivé snapshoty jsou v ignorovaném `.local/deployments/jhu-search-20261015/` šifrované Windows DPAPI; public checkpoint neobsahuje hodnoty secrets ani dokumentů. Migraci provádí samostatný testovaný `migrate_search_schema.py`; FTS definice se zachytí a obnoví, bez full-refresh/reextrakce. Docker base je připnutý na Bookworm podle ODBC repozitáře.

Runtime se přepne s image po úplné coverage. Nejprve bez legacy verifieru, se smoke na vlastním dočasném Argon2 účtu: existující legacy hashe se před ověřením nemění. Funkční ověření stanoví nový Argon2-compatible baseline, teprve potom se povolí KV legacy verifier a otestuje vlastním dočasným účtem. Původní účty se nemergují ani neresetují. Identity/RBAC a SKU/CPU/RAM se nemění. PostgreSQL/section_title/OCR a ANN/performance jsou mimo tento zásah.

Regrese spouští skutečný Windows PowerShell 5.1/7 s nativním falešným Azure CLI: bez Azure credentials a síťových volání. JHU postup, blokery a rollback jsou v `.agents/inbox/2026-10-15-jhu-search-rollout-handoff.md`. Další slice je konkrétní lokálně ověřená JHU datová/login migrace; Azure zápisy až po schválení.
