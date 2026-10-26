# ADR-0039: Lokální managed transport pro všechny JHU modelové operace

- Status: accepted for local opt-in; live slice-2 acceptance passed 2026-10-23
- Date: 2026-10-23
- Supersedes: aplikační nedostupnost helperu z ADR-0038; lifecycle zůstává
- Superseded in part by: ADR-0040 přidává explicitní Management refresh jako alternativu restartu backendu a rychlé ukončení přerušených operací.

## Kontext

Standalone userspace VPN z ADR-0038 funguje bez host TUN a bez systémové VPN. Backend nyní potřebuje bezpečný vstup do stejného forwardu pro generate, embed, tags a show. Oprávnění, digest, immutable profily a výběr jediného indexu musí zůstat společnými providerovými pravidly.

## Rozhodnutí

Opt-in `JHU_CONNECTION_MODE=managed` je omezen na local/test a JHU konfiguraci. `direct` zůstává výchozí, včetně HTTPS a původního Windows route guardu. dev.ps1/VS Code před backendem idempotentně zajistí vlastní helper; chybná JHU inicializace nevypne cloudové modely.

Helper protokolu 2 publikuje jen container port 18081 na dynamický host port 127.0.0.1. Gateway povoluje pouze GET tags, POST show/generate/embed a chráněný health. Každý request vyžaduje náhodný 256bit capability klíč v hlavičce. Klíč jde přes stdin bootstrap do tmpfs, nikdy do env/labels/args. Upstream je pevně 127.0.0.1:18080 přes VPN fd; žádná volitelná proxy URL, CONNECT, pull/delete nebo redirect. Brána má omezené request/response velikosti a nejvýše čtyři souběžné HTTP handlery.

Backend před inicializací ověří přes Docker workspace owner, roli, protokol, přesný upstream target a jediné loopback mapování. Z immutable container ID načte klíč; API credentials čte jen ze dvou explicitních KV referencí přes lokální Azure CLI identitu. Výsledek i inicializační chyba jsou procesový snapshot. VPN pár backend nečte a helper neuchovává API credentials. Jde o důvěru v lokální Docker daemon, nikoli ochranu před administrátorem hosta.

Jeden společný HTTP context zajišťuje Basic auth, capability, trust_env=false, zákaz redirectů a health s limitem 3 s a maximálně 30 s starým heartbeat. Používají jej inference, discovery i embedding provider; summary/classification/backfill přes ně přirozeně procházejí. Discovery sdílí s inference/embeddingy jeden procesový slot, uvnitř zachovává tři metadata requesty. Žádné automatické opakování modelového requestu ani fallback. Docker/KV nejsou na cestě každé otázky.

## Důsledky a ověření

Reindexace se nevyžaduje kvůli transportu. Model/index UUID, prefixy, digest a datová oprávnění se nemění. Explicitní restart helperu/rotace vyžaduje restart backendu kvůli novému capability/snapshotu; reconnect ve stejném kontejneru jej nevyžaduje. Automatický resnapshot a širší outage testy patří do následujícího slice 3.

Testy používají skutečný loopback HTTP parser, syntetický upstream, mock KV/Docker a skutečné PowerShell procesy. Původní Docker blocker byl shodný se známou chybou Rancher 1.24.0: neplatná healthcheck URL http://./_ping zastavovala Windows proxy. Doporučený provisioning workaround a uživatelův Quit/start obnovily http://localhost/_ping a dostupný daemon. Živý test nového managed transportu následně prošel při host trase Wi-Fi, bez systémové VPN: 17 modelů, skutečné Nomic embeddingy, druhý index, Llama 3.2 3B RAG s citací a uloženou model/index provenance. Aplikační korpus se neměnil. Azure managed režim zatím explicitně odmítáme; slice 4 vyžaduje samostatný schválený cloudový handoff.

Runbook: [lokální managed připojení](../development/jhu-managed-local.md).

Zdrojové ověření: úplná izolovaná sada 484/113 expected skips včetně skutečného wheelu; focused set po doplnění guardů 93/2 live skips. Čistý JHU snapshot 292 souborů, focused 79/9 expected skips včetně wheelu bez private env. Živý `tests/test_jhu_managed_live.py`: **1 passed / 1 SQLite skip**, 21 s celé testovací sady včetně SQL setup/teardown, nikoli retrieval benchmark. Prošly také veřejné managed generation/embedding probes. První modelový CLI probe měl obecnou chybu, kterou explicitní diagnostický běh nereprodukoval; nově rozlišuje HTTP status/timeout/empty/invalid/mismatch bez raw obsahu. Finální transport/CLI regrese: 21 passed. Frontendové UI se neměnilo. Širší outage/soak/rekey akceptace zůstává slice 3.
