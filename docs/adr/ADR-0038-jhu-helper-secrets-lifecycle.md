# ADR-0038: JHU secrets a lokální životní cyklus připojení

- Status: accepted (lokální helper; produkční/cloudová aktivace čeká)
- Date: 2026-10-22
- Owners: AI Search

## Context

Slice 0 prokázal spojení bez systémové VPN přes nepatchovaný OpenVPN 2.7.8 AF_UNIX a pevný userspace TCP forward. Dosavadní app Settings při local/test Key Vault záměrně nenačítá; změnit APP_ENV kvůli VPN by ohrozilo izolaci SQL. Modelové API a VPN mají jiné účty. Uživatel schválil samostatný slice správy secrets a služby před zapojením modelových volání.

## Decision

`app/providers/jhu_secrets.py` poskytuje explicitní resolver se čtyřmi dodanými referencemi, rozdělený na VPN a API CredentialPair. Nevypisuje hodnoty, nečte env fallback, nelistuje vault a nemá I/O při importu. Lokální operátor používá AzureCliCredential, připravená cloudová větev výslovně ManagedIdentityCredential. Obecný Settings ani současný cloudový loader se tím nemění. Chyby rozlišují chybějící/invalidní secret, autentizaci, zákaz, síť a nedostupnost. Nový snapshot credentials vyžaduje explicitní restart konzumenta; idempotentní start není rotace.

Root `jhu_connection.py` spravuje jediný vlastní lokální kontejner. Docker atomické jméno chrání paralelní starty stejného workspace; druhý workspace s už existujícím spravovaným helperem odmítne další relaci. Vlastnictví se ověřuje před mutací a stop/reconnect používají immutable ID. Konfigurace je otisk neveřejného profilu a veřejných endpoint/reference metadat; změna vyžaduje restart. Žádné secrets v labels, Docker env nebo argumentech.

Kontejner zůstává non-root, read-only, cap-drop ALL, bez TUN/host network/publikovaných portů. Payload s VPN údaji jde přes Docker exec stdin do omezeného tmpfs, supervisor jej přečte a bootstrap soubor smaže. API údaje helper nedostává. Auth soubor v tmpfs umožňuje auth-nocache obnovu; odstraní se při terminal failure, stopu a zániku kontejneru. Stav se publikuje jako atomický sanitizovaný JSON v tmpfs, ne jako síťové administrační API.

Stavy jsou disabled/connecting/ready/degraded/auth_failed. Ready znamená VPN a odpověď přes forward (200/401 pro tags bez autentizace), nikoli povolení účtu/modelu. Supervisor zajišťuje nejvýše tři pokusy za životnost kontejneru s prodlevami 2/5 s; auth/certificate/options failure další přihlášení nevyvolá. Interní soft restart OpenVPN se mapuje na SIGTERM, aby neobešel rozpočet supervisora. Rekey zůstává podporován. Žádná modelová generace se neopakuje. Ztráta spojení se zjistí také periodickým omezeným read-only upstream checkem; starý heartbeat se nesmí hlásit jako ready.

## Options considered

- Plošně zapnout produkční Key Vault loader lokálně: odmítnuto kvůli přenosu nesouvisejících cloudových secrets a izolaci DB.
- Docker env s VPN heslem: odmítnuto kvůli inspect. Privátní profil v image nebo workspace: odmítnuto.
- Nový tunel na každý dotaz: odmítnuto kvůli latenci, účtovým limitům a obnově spojení.
- Systémový OpenVPN klient: dosavadní režim zůstává pro aplikaci do slice 2; helper neovládá jeho službu ani route.

## Consequences

Po restartu počítače Docker/session bez secrets nelze bez přihlášení do Azure CLI obnovit; explicitní start je znovu načte. Změna/rotace v KV se promítne restartem, ne implicitně během dotazu. Start nepřepisuje funkční relaci, restart nejprve ověří nové credentials a teprve potom ukončí starou. Terminální selhání vyžaduje explicitní restart. Oprávnění Dockeru nejsou tenantová bezpečnostní hranice, jde o lokální operátorský nástroj.

Starší komunitní userspace stack vyžaduje další posouzení údržby před produkcí. Omezení replik, MFA/policy, UDP egress a prostředky ACA zůstávají cloudovou akceptací. V tomto slicu nevzniká veřejný forward, backend transport, automatický VS Code start, SQL migrace ani změna indexů.

## Follow-ups

- Slice 2: společný omezený transport generate/embed/tags/show a opt-in dev.ps1/VS Code start; API credentials dodá resolver přímo backendu. Až poté odstranit prokazatelně nahrazené inline API kopie.
