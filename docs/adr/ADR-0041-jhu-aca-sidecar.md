# JHU připojení přes userspace VPN sidecar v Azure Container Apps

- Status: accepted; JHU ACA functional connectivity verified 2026-10-29, broad Management exact SQL performance remains open
- Date: 2026-10-26
- Owners: AI Search
- Extends: ADR-0038, ADR-0039, ADR-0040

## Context

Lokální managed helper ověřil OpenVPN bez TUN/NET_ADMIN a společný transport pro chat, embeddingy a discovery. Azure nemůže použít VPN notebooku ani ověřovat helper přes Docker CLI. Je potřeba zachovat existující Container App, původní Azure modely a explicitní chyby bez přepnutí provideru.

## Decision

Explicitní `JHU_CONNECTION_MODE=sidecar` je určen pouze pro Linux ACA, `dev/prod` a JHU konfiguraci. Druhý kontejner sdílí síť repliky s backendem. VPN forward zůstává na loopbacku; chráněná HTTP gateway poslouchá pouze na `127.0.0.1:18081`. Kontext health odpovědi musí odpovídat přesné aplikaci, revizi, replice, datovému tenantu a pevnému upstreamu před každým modelovým voláním. Žádný request neurčuje endpoint. Lokální `managed` a výchozí `direct` zůstávají samostatné režimy.

Oba procesy používají přímo ManagedIdentityCredential. Backend čte jen API účet a gateway capability; helper jen VPN účet, profil a stejnou capability. Nejde o oddělené RBAC identity: systémová identita je sdílená a její existující vault-scoped role technicky dovoluje širší čtení. Oddělení je v implementovaných čtecích cestách. Nový náhodný 256bit klíč uložený v KV přežije restart helperu; jeho rotace vyžaduje koordinované obnovení obou procesů. Žádný credential není v image, env hodnotách, ARM souboru nebo CLI argumentech.

Helper načítá přesně čtyři secrets s omezenými SDK timeouty bez automatických opakování. Soukromé soubory mají 0600 v adresáři 0700 vlastněném UID 65532. Lokální varianta používá tmpfs; ACA varianta používá privátní efemérní filesystem kontejneru, netvrdíme, že je memory-only. Soubory se uklidí při ukončení a terminální VPN chybě. Přetrvávající bootstrap chyba ponechá proces živý, nevytváří nekonečný přihlašovací cyklus. Náprava je řízený restart helperu/revize; backendový refresh obnoví pouze jeho vlastní snapshot.

Platforma používá samostatný TCP process probe `18082` na replice. Neposkytuje data ani proxy; žádný helper port se nezveřejňuje přes ingress. Výpadek VPN nesmí restartovat zdravý backend. Supervisor, omezený reconnect budget, abort rozpracovaných socketů a zákaz replay zůstávají společné s lokální cestou.

`deploy_jhu_sidecar.py` standardně pouze čte. Apply zachová existující konfiguraci/secrets/identitu a v paměti PATCHne jen location a template. Kontroluje účet, přesný datový tenant/SQL/vault, image digesty, revizi, fingerprint a samostatná potvrzení modelů, migrací, VPN relace a kapacity. Před zápisem znovu čte fingerprint; If-Match používá, pokud služba vrací ETag. Bez ETag nejde o garantovaný atomický CAS: během schváleného okna nejsou povoleny jiné deploymenty.

## Options considered

- VM nebo veřejná HTTPS brána: možné později, nyní by vyžadovaly nové prostředky nebo spolupráci administrátora.
- Sdílený secret soubor/volume: přidává startovací a ownership závody; capability z KV podporuje restart helperu bez nového backendového snapshotu.
- Privilegovaný TUN: ACA ani ověřená lokální cesta jej nepotřebují.

## Consequences

První návrh zachová backend 0,5CPU/1Gi a přidá helper 0,25CPU/0,5Gi. Součet 0,75CPU/1,5Gi a změna maxReplicas 3→1 vyžadují schválení; nejde o příslib stejné ceny. Alternativní rozdělení původní kapacity explicitně zmenšuje backend a vyžaduje nové výkonové ověření. Ani režim Single nezaručuje absenci souběhu staré a nové revize; další rollout potřebuje posouzení souběžných VPN relací. Cloudová UDP trasa, živá managed identity a skutečné modelové volání nejsou prokázány lokálním testem.

## Implementation notes

[Runbook](../development/jhu-sidecar-azure.md). Oficiální podklady: [síť kontejnerů a kapacity](https://learn.microsoft.com/en-us/azure/container-apps/containers), [runtime proměnné](https://learn.microsoft.com/en-us/azure/container-apps/environment-variables), [probes](https://learn.microsoft.com/en-us/azure/container-apps/health-probes), [revize](https://learn.microsoft.com/en-us/azure/container-apps/revisions), [efemérní storage](https://learn.microsoft.com/en-us/azure/container-apps/storage-mounts), [template PATCH API](https://learn.microsoft.com/en-us/rest/api/resource-manager/containerapps/container-apps/update?view=rest-resource-manager-containerapps-2025-07-01).

## Follow-ups

- Řízená aktivace a funkční akceptace přímo v ACA podle schváleného handoffu.
