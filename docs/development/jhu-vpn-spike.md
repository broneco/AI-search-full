# JHU připojení: experiment bez systémové VPN

Toto je izolovaný slice 0, nikoli běžný start aplikace nebo hotové Azure řešení. `probe_jhu_vpn.py` sestaví pomocný Docker image, ověří userspace forward a explicitně spustí krátký test JHU. Nemění aplikační databázi, indexy, modely, systémové routy ani Azure prostředky. Současné providery aplikace zatím používají dosavadní připojení. Navazující slice 1 přidává [samostatný lifecycle a Key Vault resolver](jhu-connection-helper.md).

## Výběr kandidáta

- Oficiální OpenVPN **2.7.8**, commit `dc1f569087135894ac2703aeabd7a960ee9452d4`, GPL-2.0. Vestavěný `dev-node unix:` vytváří AF_UNIX/SOCK_DGRAM kanál a předá descriptor pomocnému programu přes `TUNTAP_SOCKET_FD`. VPN ani kryptografický protokol nepatchujeme.
- `russdill/tunsocks`, commit `4e4ff8682053412145930b8daf2c55d357cf1e44` z 2023-06-22, BSD podle jeho README/lwIP licence. Používáme jediný `-L` forward, žádný SOCKS/HTTP proxy server, NAT ani hostový `-S` stack. Připnuté submoduly jsou určeny stromem tohoto commitu; lwIP `832490eec8ca35bad435fec104512cfbdaf994bf` stahujeme z HTTPS mirroru projektu místo starého git:// endpointu.
- `bridge.py` pouze validuje a mapuje prostředí OpenVPN na `VPNFD` a adresu userspace stacku; před spuštěním forwarderu odstraňuje ostatní env.
- Základ Docker image je připnut digestem; Debian balíčky se načítají z repozitářů při sestavení. Nejde o bitově reprodukovatelný build všech závislostí.
- Starý OpenVPN Tuna 2.6.5 nepoužíváme. `go-openvpn` odmítá comp-lzo dodaného profilu. Oficiální `lwipovpn` je emulátor pro testy, nikoli hotový forward pro náš backend.

Stáří komunitního forwarderu a jeho síťových knihoven zůstává provozním rizikem. Úspěšný funkční probe není bezpečnostní audit ani automatické přijetí této závislosti do produkce. Před cloudem je nutné rozhodnout o udržitelnosti/aktualizacích.

## Spuštění ve VS Code / PowerShellu

Docker Engine musí běžet. Použij existující projektové `.venv` s Azure SDK; probe neimportuje Settings, nepřepíná APP_ENV a nepřipojuje SQL.

```powershell
.venv\Scripts\python.exe probe_jhu_vpn.py build
.venv\Scripts\python.exe probe_jhu_vpn.py offline
```

Offline test běží s Docker `--network none`. Ověří skutečný TCP SYN na předaném unixovém packet descriptoru, nulové capabilities, non-root a nepřítomnost `/dev/net/tun`. Neprokazuje handshake ani odpověď ze skutečného API.

Pro živý test se nejprve přihlas do správného Azure účtu. Do `ju-ai-search-kv-prod` musíš mít právo Get. Od slice 1 jsou potřeba všechny čtyři secrets z [návodu helperu](jhu-connection-helper.md), také pro API. Původní slice 0 četl API credentials z ignorovaného `.env.jhu-model`; nyní je tato starší cesta dostupná jen explicitně přes `--api-credentials env`. Z env se standardně čte pouze endpoint. Žádné heslo nepatří do příkazů ani chatu.

```powershell
$profile = "$env:USERPROFILE\OpenVPN\config\Client\Client.ovpn"
# Nejdříve ručně odpoj systémovou VPN, pokud test neohrozí jinou práci.
.venv\Scripts\python.exe probe_jhu_vpn.py live --profile $profile --negative-name
.venv\Scripts\python.exe probe_jhu_vpn.py live --profile $profile
# Rozšířený test: klientská renegociace klíčů a jeden řízený reconnect.
.venv\Scripts\python.exe probe_jhu_vpn.py live --profile $profile --rekey --reconnect
```

Negativní test používá v paměti odvozený profil s jiným očekávaným jménem certifikátu a musí skončit `negative_certificate_name: passed`. Originál nemění. Běžný test ověřuje tags/show, dvě krátké syntetické generace a dva embeddingy. Výchozí modely jsou `llama3.2:3b` a `nomic-embed-text:latest`; lze explicitně zvolit `--model` a `--embedding-model`. Modely se automaticky nestahují ani nezaměňují. `--handshake-only` ukončí test po navázání tunelu.

## Omezení a ochrany

- Kontejner: UID/GID 65532, cap-drop ALL, no-new-privileges, read-only filesystem, 512 MiB / 0,5 CPU, nejvýše 64 procesů, žádný publikovaný port/TUN/host network. Je to limit samostatného testu, ne návrh rozdělení kapacity ACA.
- Secrets a profil jdou přes stdin, nikoli Docker env/argumenty. Auth a odvozený config existují pouze v omezeném tmpfs a po testu se odstraní spolu s kontejnerem. Log driver je vypnutý. Stdout obsahuje jen metadata; raw OpenVPN log ani odpovědi/text/vektory se neukládají.
- Profil má úzký allowlist; hooky, pluginy, include, alternativní auth soubory a libovolné `setenv` se odmítnou. CA, jméno serveru a comp-lzo se zachovávají. Pouze interní kontrolovaný bridge může být spuštěn přes script-security 2.
- Odvozená konfigurace vynechá `persist-tun`, aby se userspace stack při reconnectu obnovil; ponechání způsobilo timeout API po úspěšném znovupřipojení. Originál souboru se nemění. `--rekey` pouze pro test nastaví klientský reneg-sec na 15 s; čeká na další ustavený TLS control channel a ověřuje API, nikoli jen začátek renegociace.
- API test běží uvnitř stejného kontejneru přes `127.0.0.1:18080`. Forward má jediný pevný IPv4 cíl z privátní konfigurace. Žádná přímá cesta při výpadku, redirect ani automatický modelový retry.
- API Basic a VPN login jsou oddělené. Tento probe neprovádí opakované pokusy se záměrně chybným heslem skutečného účtu, aby nedošlo k jeho zamčení.
- Funkčnost z notebooku při odpojené systémové VPN neprokazuje odchozí UDP, kapacitu ani síťové policy v ACA. Obnova/rekey a delší provoz vyžadují vlastní doložené testy.

## Podklady a ověření

- [Oficiální OpenVPN 2.7.8 – dev-node unix](https://github.com/OpenVPN/openvpn/blob/v2.7.8/doc/man-sections/vpn-network-options.rst)
- [Implementace AF_UNIX 2.7.8](https://github.com/OpenVPN/openvpn/blob/v2.7.8/src/openvpn/tun_afunix.c)
- [Připnutý tunsocks, jeho licence a forward](https://github.com/russdill/tunsocks/tree/4e4ff8682053412145930b8daf2c55d357cf1e44)
- [Testy probe](../tests_explained/test_vpn_spike.md)

Ověřeno 2026-10-22 na notebooku s uživatelem odpojenou systémovou VPN (trasa k API přes Wi-Fi, nikoli OpenVPN):

| Kontrola | Výsledek |
|---|---|
| Docker build / offline packet test | PASS; OpenVPN 2.7.8, non-root, capabilities 0, žádný TUN, SYN pro jediný cílový port přes unixový descriptor při vypnuté síti kontejneru |
| Nesprávné jméno serverového certifikátu | Správně odmítnuto před API voláními |
| Skutečný VPN handshake | 1 146 ms v závěrečném běhu |
| API tags/show | 17 modelů, oba požadované modely přítomné |
| Llama 3.2 3B, dvě krátké generace | 318 / 255 ms v zahřátém závěrečném běhu; první dřívější volání 5 818 ms zahrnovalo načtení modelu |
| Nomic, 2 vstupy | Dva konečné číselné vektory, 768 rozměrů, 60 ms v závěrečném běhu |
| Rekey | Druhý ustavený TLS control channel a úspěšné API volání |
| Řízený SIGUSR1 reconnect | Úspěšný nový handshake i API, 3 439 ms |
| Prostředky testovacího kontejneru | cgroup memory.peak 25 047 040 B (23,9 MiB); souhrnný CPU čas 401 709 µs |

Jde o **GO pro pokračování lokálního prototypu**, ne o produkční akceptaci knihoven, celý RAG test nebo kapacitní benchmark. Nekontrolovali jsme chybu skutečného hesla (riziko zamčení účtu); její diagnostika má unit test. Negativní jméno certifikátu není samostatný test jiné CA. SIGUSR1 dokládá klientský reconnect, nikoli všechny typy výpadků sítě nebo dlouhodobý provoz. Paměť/CPU jsou pouze pro tento krátký pomocný kontejner, nikoli součet s backendem v ACA. Všechny probe kontejnery se po testu odstraňují; vývojový image zůstává pro opakování. Runtime aplikace, Azure a korpus se neměnily.

Finální cílené regrese: **47 passed**, včetně skutečného wheelu a JHU exportních testů. Po posledním přesunu klasifikace chyb znovu prošel offline Docker test i negativní TLS test. AST, navigace nových souborů a whitespace kontrola prošly. Úplná aplikační sada/frontend buildy se neopakovaly: aplikace/UI se neměnily. Finální lokální image ID: `sha256:1d6ab2bf050399bebf569f52589ec880af687ea56703cba65f048514f20853b5`. Nejde o image publikovaný v registru.
