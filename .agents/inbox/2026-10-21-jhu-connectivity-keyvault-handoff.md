# JHU: automatické připojení modelů a přesun secrets do Key Vaultu

- Status: slices 0–2 lokálně ověřeny; slice2 živá managed RAG akceptace prošla 2026-10-23. Cloudové změny čekají samostatně.
- Created: 2026-10-21
- Scope: pouze JHU, konfigurace `jhu`, skutečný cloudový tenant `ju-prod`.
- Related: [modelové připojení](2026-10-16-jhu-model-selection-handoff.md), [ověřený rollout](../../docs/deployments/2026-10-15-jhu-search-rollout.md).
- Rozhodnutí o infrastruktuře čeká na ověření níže; nejde o přijaté ADR ani schválení nasazení.

**Aktualizované pořadí po upřesnění uživatele:** další VM a čekání na správce JHU jsou nežádoucí. Nejprve prověřit variantu D (VPN-to-proxy bez TUN v existujícím kontejnerovém prostředí). Jde o omezený technický spike, nikoli potvrzenou kompatibilitu nebo produkční doporučení konkrétního komunitního klienta. Varianty B/C zůstávají alternativy; novou VM nyní neplánovat jako výchozí krok.

**Výsledek slice 0, 2026-10-22:** funguje izolovaný non-root Docker probe bez systémové VPN. Nově nalezená oficiální cesta OpenVPN 2.7.8 `dev-node unix:` nahrazuje níže zvažovaný starý Tuna fork; jediný userspace TCP forward poskytuje připnutý tunsocks. Proběhl skutečný cert-name negativní test, handshake, tags/show, dvě syntetické generace, dva Nomic embeddingy, rekey a SIGUSR1 reconnect s API kontrolou. Opraven timeout po reconnectu vynecháním persist-tun v odvozeném profilu. Uživatel vytvořil dvě VPN secrets a odpojil host VPN, agent pouze četl KV. GO pro pokračování prototypu, nikoli přijetí komunitní knihovny do produkce či cloudové akceptace. Podrobnosti a měření: [reprodukovatelný návod](../../docs/development/jhu-vpn-spike.md). Následuje slice 1. Níže uvedený původní audit a návrh slouží jako kontext; neznamená, že aplikace už používá nový tunel.

**Výsledek slice 1:** hotový explicitní secrets resolver a samostatná služba jhu_connection.py; uživatel vytvořil i dvě API secrets, všechny čtyři + skutečné API použití ověřeny bez výpisu hodnot. Živý start/idempotence/reconnect/automatická obnova/rozpočet pokusů/úklid/restart/stop prošly bez systémové VPN. Stav a návody: [helper](../../docs/development/jhu-connection-helper.md), [ADR-0038](../../docs/adr/ADR-0038-jhu-helper-secrets-lifecycle.md). Původní API env kopie zatím zůstávají kvůli běžným konzumentům. Následuje **slice 2**, který teprve napojí aplikaci a dev.ps1/VS Code. Cloudový handoff níže zůstává návrhem bez provedených cloudových zápisů.

## Požadovaný výsledek

Aktuální slice2 je přijatý: opt-in `-JhuManaged` a VS Code úloha **AI Search: start JHU local app**, common capability gateway/transport pro všechny JHU operace, API-only KV snapshot backendu. [Runbook](../../docs/development/jhu-managed-local.md), [ADR-0039](../../docs/adr/ADR-0039-jhu-managed-app-transport.md). Direct zůstává výchozí. Rancher healthcheck workaround odstranil Docker blocker po uživatelově Quit/start. Nová image, ready helper a skutečný managed discovery17/Nomic768/Llama RAG s citací a uloženou provenance prošly bez systémové VPN v izolované SQL (1 passed/1 SQLite skip); aktivní index/chunky zachovány. Nejde o cloudovou nebo širší provozní akceptaci. Po explicitním restartu helperu je nutný restart backendu. Následuje slice3 odolnost.

Uživatel zvolí JHU model a odešle otázku. Ruční zapínání VPN není součástí běžné práce. Uživatel výslovně připustil libovolné řešení připojení na pozadí. To neznamená povolení nešifrovaného veřejného API. Volání LLM, embeddingů i discovery provádí backend, nikdy prohlížeč s credentials. Azure nesmí záviset na běžícím notebooku.

## Ověřené skutečnosti, pouze čtení

| Oblast | Zjištění k 2026-10-21 |
|---|---|
| Dodaný soukromý `Client.ovpn` mimo repo | OpenVPN `dev tun`, UDP, `access.jcu.cz:1194`, `auth-user-pass` bez souboru, `auth-nocache`, inline CA; žádný inline klientský certifikát/privátní klíč ani direktiva pro jeho soubor. Heslo v profilu není. MFA, účtová omezení a obnovování autentizace z profilu nevyplývají. |
| Notebook | Aktivní cesta k `160.217.182.41` vede přes `OpenVPN TAP-Windows6`, odpovídající route je `128.0.0.0/1`. VPN nebyla odpojena ani změněna. Dosažitelnost mimo VPN nebyla ověřena. |
| API | Dosavadní kontrakt používá Basic auth a HTTP port 11434. VPN login a API login jsou dvě odlišné sady údajů. Poskytovatelé už podporují HTTPS endpoint; lokální HTTP vyžaduje Windows VPN guard. |
| Azure cíl | Subscription `24e4a9a6-bab0-43f7-ba20-3b774704fade`, directory `c35f5da4-9a03-44e6-8bf9-92833634f6a7`, RG `ju-ai-search-rg-prod`. |
| Backend | `ju-ai-search-ca-prod`, latest ready revision `ju-ai-search-ca-prod--0000008`; systémová identita `ccacbf26-dcd6-4f7b-af7b-e3e769137de8`. V runtime nejsou JHU modelové proměnné. |
| Síť ACA | Environment `ju-ai-search-cae2-prod`, Consumption workload profile, `vnetConfiguration=null`, veřejný přístup povolen. Jde o platformní síť, nikoli zákaznický VNet. |
| Key Vault | `ju-ai-search-kv-prod`, RBAC režim, veřejný endpoint, network ACL default Allow. Backend má existující **Key Vault Secrets User** na tomto vaultu; role nebyla změněna. |
| Cloudová konfigurace secrets | SQL, OpenAI, Storage, nový signing key a legacy verifier používají názvy KV secrets v env. Nejde o nativní ACA `keyVaultUrl` reference: secrets čte SDK aplikace při startu. Žádný z těchto privátních údajů není inline env aktuální ACA. |
| Container registry | Image pull používá heslový ACA secret `juaisearchcrprodazurecrio-juaisearchcrprod`, bez `keyVaultUrl`, nikoli managed identity. Hodnota se nečetla. |

## Varianty připojení

### A. Notebook: automaticky spravovaný OpenVPN klient

Pro první lokální slice ověřit možnost přihlášení a opětovného připojení stávajícím klientem, jeho službu/oprávnění a účtová omezení. Teprve potom doplnit samostatný Windows helper/startup workflow:

1. Explicitně načíst pouze JHU modelové/VPN secrets z KV pod přihlášeným Azure uživatelem. Backend nesmí kvůli tomu běžet jako administrátor.
2. Reuse již ověřeného JHU spojení; jinak helper založí vlastní tunel a vyčká na ověřenou trasu i připravenost API. Nespoléhat jen na název adaptéru jako na důkaz dostupnosti.
3. Pokud prostředí dovolí split tunnel, směrovat pouze nutný JHU cíl; server může pushovat jiné routy než profil obsahuje. Ověřit JHU policy, Azure/KV dostupnost a návrat rout. Automaticky nekopírovat současnou širokou `/1` trasu do cloudové gateway.
4. Bezpečně předat login klientovi, bez argumentů s heslem, historie konzole, logů nebo trvalého plaintext auth souboru. Pokud klient potřebuje dočasný soubor, musí mít omezené ACL, krátkou životnost a odstranění i při chybě. `auth-nocache` vyžaduje ošetřit další autentizační výzvy, ne jen první login.
5. Jeden vlastník tunelu, omezené opakování připojení, žádný nový VPN klient na každou otázku. Při chybě jasná nedostupnost JHU; žádné automatické opakování generace/přepnutí do Azure.
6. UI zůstane běžný modelový selector. Setup může jednorázově vyžadovat instalovanou Windows službu/ovladač; pozdější otázky už ruční zapnutí nepotřebují. Při ukončení odstranit jen vlastní spojení, ne VPN spuštěnou uživatelem.

Tento helper ani jeho config klíče zatím neexistují. Nestačí doplnit dvě env proměnné.

### B. Společný HTTPS vstup pro notebook a nynější ACA

Preferovaný cílový výsledek, pokud jej JHU může poskytnout: autentizovaná HTTPS reverse proxy u JHU před stávajícím API. Oba backendy používají stejný chráněný vstup bez klientské VPN. JHU nemusí zpřístupnit nezabezpečený port 11434. Je nutné potvrdit DNS, TLS, autentizaci a síťovou dostupnost z Azure i notebooku.

Pokud JHU HTTPS vstup neposkytne, technická alternativa je samostatná Azure Linux VM jako **HTTPS aplikační gateway + OpenVPN klient**:

```text
lokální backend / stávající ACA → HTTPS + autentizace → gateway VM
gateway VM → vlastní OpenVPN spojení → JHU modelové API
```

Tato alternativa funguje návrhově s aktuální veřejnou egress sítí ACA; nepotřebuje z notebooku sdílet tunel ani nutně stěhovat ACA. Není dosud realizována ani otestována a přidá náklady, správu VM a další bod selhání. Neobjednávat SKU bez domluvy. Gateway má pevný upstream, ověřuje volajícího a povoluje pouze potřebné `tags/show/generate/embed` operace, nikoli obecný forward proxy/CONNECT nebo libovolné URL. Oddělit její autentizaci od upstreamu, pokud smluvený provozní model neumožňuje zachovat end-to-end API Basic. TLS, omezení souběhu/velikosti, timeout podle studeného startu, redakce Authorization a zákaz logování textů jsou součástí implementace, nikoli doplněk. Odmítnout pull/delete modelů a ostatní řídicí API.

Pro gateway použít pokud možno dedikovaný služební VPN účet, který JHU povolí pro bezobslužný provoz. Osobní účet nejprve slouží k lokálnímu spike. Ověřit MFA, obnovování session a zda současné přihlášení notebooku a serveru nevytlačuje předchozí spojení.

Nová VM má **jinou identitu** než ACA. Existující role backendu se na ni nepřenáší; potřebný přístup její identity k vybraným secrets musí zajistit oprávněný administrátor. Uživatel má možnost secrets vytvářet/číst, nemá se po něm požadovat udělení RBAC, které nemůže provést.

### C. Privátní propojení sítí, samostatný pozdější projekt

Zákaznický VNet pro nové ACA environment + privátní gateway/OpenVPN VM, případně skutečné JHU–Azure site-to-site propojení. Stávající environment nelze pouhým updatem přepnout z platformní sítě na vlastní VNet. S2S Azure VPN Gateway používá IPsec/IKE; osobní OpenVPN `.ovpn` soubor není konfigurace pro přímý import do S2S gateway. Vyžaduje spolupráci správce JHU a oddělený migrační/kapacitní plán. Nejde o první doporučený krok.

Standardní tunelový OpenVPN klient nepatří jako běžný sidecar do nynější ACA: vyžaduje TUN a správu síťových rozhraní/rout, zatímco ACA nepodporuje privileged host-level kontejnery. Nestavět řešení na neověřeném předpokladu, že lze přidat `/dev/net/tun` a `NET_ADMIN`. Toto omezení samo o sobě nevylučuje čistě userspace VPN-to-proxy; ta je nyní předmětem navrhovaného spike D.

### D. VPN-to-proxy bez TUN, první kandidát k omezenému ověření

```text
JHU HTTP klient backendu → lokální proxy → OpenVPN v userspace → JHU API
```

Návrhově může proces běžet v non-root kontejneru bez síťových capabilities, změn rout nebo veřejně otevřené proxy. V ACA by šlo o sidecar ve stejné aplikaci, lokálně o Docker helper. ACA podporuje sidecary se společnou sítí. Kompatibilita tohoto konkrétního VPN klienta se službou JHU a ACA však ověřená není. Pro spike preferovat forward jediného cíle/portu; případná SOCKS proxy musí být omezena na JHU cíl a dostupná jen backendu.

Zjištěné kandidáty hodnotit podle jejich vlastních zdrojů:

- `n0madic/go-openvpn` / `openvpn2socks`: vlastní Go implementace OpenVPN + gVisor userspace stack, uvádí běh bez TUN/root. **Není drop-in pro dodaný profil:** parser výslovně odmítá `comp-lzo`, knihovna nepodporuje kompresi a legacy CBC kanál. `Client.ovpn` comp-lzo obsahuje; z toho nelze určit skutečně vyjednanou kompresi ani šifru. Neodstraňovat direktivy naslepo. Malý komunitní projekt, nikoli oficiální OpenVPN klient; před použitím posoudit aktualizace, implementaci ověřování serveru a licenci.
- `bendlas/openvpn-tuna` / `ValdikSS/openvpn-tunpipe` + `russdill/tunsocks`: upravený standardní OpenVPN předává IP pakety userspace stacku a ten poskytne TCP forward/proxy. Tuna dokumentuje rootless cestu, původní tunpipe se označuje za proof-of-concept. Pro legacy profil je to kandidát k ověření, ne důkaz funkčnosti. Zkontrolovat základní verzi OpenVPN, rozsah patchů a možnost přebírat bezpečnostní aktualizace; nenasazovat neprověřený starý fork jen proto, že se sestaví.

V aplikaci dnes nestačí nastavit globální HTTP_PROXY: embedding/discovery mají `trust_env=False` a lokální HTTP ověřuje Windows route. Po úspěšném spike bude nutný explicitní společný JHU transport pro generate/embed/tags/show, který rozliší chráněnou proxy cestu a současný Windows VPN režim. HTTPX proxy podporuje, SOCKS potřebuje volitelnou závislost. V žádném případě nevypínat ochranu transportu plošně ani neposílat Azure/SQL/KV provoz přes JHU. Při výpadku proxy žádný přímý HTTP fallback.

Akceptace spike:

1. Prověřit konkrétní zdroj/verzi/patch a kompatibilitu profilu; žádný vlastní vývoj VPN protokolu. Bez hesel lze zkontrolovat build a parser; skutečný handshake vyžaduje privátně připravené VPN secrets.
2. Lokálně spustit s běžným uživatelem, odebranými capabilities a bez `/dev/net/tun`. Platný server certifikát musí projít, chybná CA/jméno musí selhat. Neukládat credentials nebo payload do logů/image.
3. Přes tunel provést metadata a krátký syntetický generate/embed; ověřit chybu loginu, obnovu po výpadku i obnovení autentizace/klíčů. Pouhý start proxy nebo úspěšný socket nestačí.
4. Změřit CPU/RAM a latenci; původních 0,5 CPU / 1 GiB není záruka rezervy. Sidecar nemusí vyžadovat další placený prostředek, ale celková alokace a aktivita ovlivňují účet ACA. Keepalive může ovlivnit idle režim, cold start musí zahrnout VPN handshake. Pro MVP jedna VPN relace/replika; scaling/revision overlap může vytvořit více relací a vyžaduje ověření účtu.
5. Teprve po lokálním výsledku připravit schvalovaný ACA test ve stávajícím prostředí s vlastním přístupem ke KV; potvrdit odchozí UDP a fungování bez notebooku. Není nutné nové RBAC pro novou VM, pokud využijeme existující identitu ACA a její stávající přístup. Nasazení nové revize je samostatný cloudový zápis.

Stop podmínka: pokud kompatibilita vyžaduje rozsáhlou údržbu VPN forku, oslabení ověřování serveru nebo změny JHU policy, přerušit tuto cestu a vyhodnotit existující dosažitelný SSH vstup s povoleným forwardingem či HTTPS variantu. Samotné VPN/API přihlášení nedokazuje existenci SSH účtu. Relay přes notebook je možný jen jako dočasné demo s přiznanou závislostí na jeho běhu; nesplňuje nezávislý cloudový provoz.

## Co vytvořit v Key Vaultu

Ve **stávajícím `ju-ai-search-kv-prod` → Objects → Secrets → Generate/Import → Manual** vytvořit následující nové secrets. Nevkládat hodnoty do chatu, dokumentace ani CLI `--value` v historii. Jména jsou návrh této integrace; zkontrolováno, že při auditu ve vaultu nebyla. Nepřepisovat současných pět secrets.

| Secret name | Obsah | Konzument / stav |
|---|---|---|
| `ju-ai-search-vpn-username-prod` | Skutečný login do VPN JHU | Budoucí lokální helper; pro gateway později raději samostatný služební účet/oddělené secrets. |
| `ju-ai-search-vpn-password-prod` | Heslo k tomuto VPN účtu | Totéž; žádný automatický reset hesla. |
| `ju-ai-search-jhu-api-username-prod` | Dosavadní Basic login modelového API | LLM, embeddingy i discovery používají společné připojení. |
| `ju-ai-search-jhu-api-password-prod` | Dosavadní heslo modelového API | Nejde o heslo VPN. |

Content type volitelně `text/plain`, secret Enabled. Expiraci přizpůsobit účtové politice a plánované obnově. Soubor obsahuje CA a nesekretní síťové parametry; z aktuálního profilu nevyplývá potřeba dalšího secretu s klientským klíčem nebo passphrase. Originál ponechat mimo repo. Pro budoucí gateway lze jeho bezpečnou distribuci řešit samostatným config artefaktem nebo volitelným KV secretem `ju-ai-search-vpn-client-config-prod`; zatím není nutné jej vytvářet. Profil obsahuje legacy `comp-lzo`; ověřit kompatibilitu/verzi a doporučený profil u JHU, automaticky neměnit přiložený originál.

Pro **již implementovaný cloudový** loader patří do konfigurace pouze reference:

```dotenv
AZURE_KEY_VAULT_NAME=ju-ai-search-kv-prod
AZURE_KEY_VAULT_SECRET_JHU_LLM_USERNAME=ju-ai-search-jhu-api-username-prod
AZURE_KEY_VAULT_SECRET_JHU_LLM_PASSWORD=ju-ai-search-jhu-api-password-prod
```

Endpoint a ověřený model/digest zůstanou samostatnou nesekretní konfigurací; nastavit je až podle ověřené síťové varianty. VPN secret names aplikace zatím vůbec neumí číst. Nevymýšlet pro ně fungující env přepínač.

**Lokální profil dnes Key Vault úmyslně nečte.** `APP_ENV=local` čte `.env.jhu-model` a poté `.env.local`, test jen `.env.test`; process vars mají přednost. Budoucí opt-in se musí týkat pouze konkrétních JHU secrets, nikoli celého produkčního prostředí. Nikdy nepřepnout lokální backend na `APP_ENV=prod` kvůli získání VPN hesla. Lokální SQL cíle/guardy zůstanou beze změny. Přihlášený vývojář potřebuje existující právo Get pro příslušné secrets; další grant řeší administrátor jen při skutečném nedostatku oprávnění.

## Audit umístění a plán přesunu, pouze JHU

| Položka | Nález | Plán |
|---|---|---|
| `.env.jhu-model` | Přímý API login/heslo a veřejná konfigurace připojení. | Přesunout API credentials do dvou nových secrets; lokální KV opt-in a masked probe musí být nejprve implementovány a ověřeny. Pak odstranit jen staré hodnoty, soubor s endpointem/model metadata může zůstat. |
| `tenants/jhu/.env.prod` | Přímý OpenAI key a Storage connection string, SQL heslo prázdné. | Jejich odpovídající secrets již existují. Po ověření přesné shody a lokálního/operator workflow odstranit inline kopie; ponechat názvy KV referencí. Cloudovou běžící konfiguraci znovu nemigrovat. |
| `JWT_SECRET` v JHU dev/prod env | Obě lokální env obsahují známý výchozí klíč, nikoli současný produkční KV signing key. | Nekopírovat výchozí klíč do KV. Produkční konfiguraci opravit na již používaný signing secret a připnutou verzi z ověřeného rollout; současný runtime/klíč ani uživatelská hesla nerotovat. Dev vyžaduje vlastní klíč. |
| `LEGACY_PASSWORD_SECRET` | Cloud už používá samostatný `ju-ai-search-legacy-password-key-prod`. | Zachovat pro dosud nemigrované účty; neodvozovat z hodnoty starého lokálního JWT. Odstranění až po samostatné akceptaci migrace účtů. |
| `tenants/jhu/.env.dev` | Přímá pole pro OpenAI/SQL/Storage/Postgres, odlišné dev KV reference. V aktuální subscription se JHU dev vault při listu neobjevil. Platnost dev hodnot nebyla ověřována. | Nezaměňovat dev za prod. Rozhodnout, zda skutečné cloudové dev vůbec provozovat; pokud ano, vlastní dev secrets a izolované služby. Nepřenášet neověřené hodnoty automaticky do prod. |
| `POSTGRES_PASSWORD` | Přítomno v soukromých JHU env; cloud má referenci, ale odpovídající PostgreSQL secret ve vault listu není. | PostgreSQL není podporovaná aktuální JHU cesta. Nepřidávat nepotřebný produkční secret; odstranit mrtvou konfiguraci až po ověření závislostí. |
| Root `.env.local` | Heslo lokálního Docker SQL Serveru, ne produkční JHU SQL. | Ponechat lokální náhodné credentials, neukládat SA heslo do JHU prod KV. Azure připojení sem nepřidávat. |
| Frontend env | `NEXT_PUBLIC_*` obsahují pouze URL/tenant/vzhled; nalezeny také veřejné backend URL v development/production env. | Tyto hodnoty ponechat v konfiguraci. Do `NEXT_PUBLIC_*` nikdy nevkládat secret; vault žádný frontendový secret nemá zpřístupnit browseru. |
| ACR image-pull heslo | Jeden ACA secret bez KV reference. | Přednostně později přejít na managed identity + konkrétní image-pull oprávnění; RBAC samostatně administrátor. Pokud to nepůjde, přesunout heslo do KV a použít podporovanou ACA registry secret referenci po ověření této cesty. Nejde o Settings secret, bootstrap musí fungovat před startem Pythonu. |
| SWA deployment token | `deploy_frontend.ps1` jej získává pro nasazení a předává v paměti. | Dlouhodobě jej neukládat do env. Samostatný pipeline/CI secret teprve při zavedení CI, pokud nelze použít krátkodobý mechanismus. Nyní není důvod vytvořit další trvalý KV secret. |
| `.local/operations/` a `.local/deployments/` | Soukromé operátorské skripty a historické rollback snapshots `.dpapi`; ne-secret `state.json`. | Nové operace používají KV resolver, ne import všech prod env do procesu. DPAPI zálohy nejsou jednotlivé runtime secrets: neimportovat celé snapshoty do KV, nedešifrovat/neodstraňovat před retencí a ověřeným rollbackem. |
| `.local/publications/source-jhu-input.zip` | Zkontrolováno 282 entries: žádná soukromá env/key/pfx/ovpn jména ani přesná shoda delších současných privátních credentials z auditovaných env. | Výsledek je omezená kontrola konkrétního ZIPu, nikoli záruka celé historie/všech archivů. Export musí dál vylučovat secrets. |
| Privátní VPN soubor | Mimo workspace; nebyl kopírován. Git/Docker/export ochrany zatím explicitně neblokují všechny `.ovpn` varianty. | Před případným přidáním VPN helperu rozšířit packaging/exclusion regrese pro VPN/auth soubory; nepřidávat privátní profil do kořene repa. |
| App Insights / Azure login / ACL | App Insights connection string v JHU env prázdný. CLI tokeny jsou uživatelská přihlašovací cache; modelová ACL jsou SQL data. | Nevytvářet secret pro prázdnou telemetrii, nepřesouvat CLI cache nebo modelová oprávnění do KV. |

Přesné porovnání známých delších hodnot proti současným veřejným tracked/untracked souborům našlo jen známý veřejný výchozí JWT řetězec v implementaci/ochranách/testech, ne auditované privátní credentials. Audit nečetl `.git` historii, nedekódoval DPAPI, nečetl hodnoty cloudových secrets a neprocházel nesouvisející osobní credential stores.

### Načítání a rotace

Současný loader bere explicitní env hodnotu před KV, kromě chybějícího/výchozího JWT. Přidat referenci vedle existujícího hesla tedy neodstraní starou kopii a nemusí změnit použitý secret. Chyby SDK jsou dnes potlačeny; další slice musí rozlišit chybějící konfiguraci, zákaz čtení, síť a VPN bez vypsání hodnot. U volitelného JHU nesmí chyba odstranit dostupnost jiných modelů.

Nezaměňovat dvě možnosti: aplikační SDK resolution při startu vs nativní ACA `keyVaultUrl` + `secretRef`. Zachovat jednu jasnou cestu pro dané nastavení; nyní není nutné přepisovat fungující cloudový loader. Jeho rotace vyžaduje řízený restart/revizi; platformní versionless ACA reference má jiné obnovování. Podpisový klíč má připnutou verzi a nemá se automaticky měnit společně s heslem modelové služby.

## Navazující slices a akceptace

### Read-only cloud preflight 2026-10-26

Uživatel požádal o postup aktualizace Container App a celé aplikace. Proběhlo pouze čtení aktuálního Azure stavu; implementace cloudového adaptéru, build/push image, SQL DDL, secrets, škálování, nové revize a frontend release nebyly provedené. Tento plán není připravený Apply artefakt.

| Cíl | Ověřený aktuální stav |
|---|---|
| Subscription / directory | `24e4a9a6-bab0-43f7-ba20-3b774704fade` / `c35f5da4-9a03-44e6-8bf9-92833634f6a7` |
| RG / region | `ju-ai-search-rg-prod` / Sweden Central |
| Container App / environment | `ju-ai-search-ca-prod` / `ju-ai-search-cae2-prod` |
| Přesný aplikační tenant | `ju-prod`; JSON konfigurace používá alias jhu |
| Aktuální revize / image | `ju-ai-search-ca-prod--0000008` / `juaisearchcrprod.azurecr.io/ju-ai-search-ca-prod:prod-v014-20261015-145009` |
| Kontejnery / kapacita | jeden backend, 0,5 CPU / 1 GiB |
| Škálování / revize | min1 / max3; Single |
| Registry | `juaisearchcrprod` |
| SQL | `ju-ai-search-sql-prod.database.windows.net` / `ju-ai-search-sqldb-prod`; obsah/schéma v tomto preflightu neověřované |
| Frontendy | `ju-ai-search-swa-user-prod` a `ju-ai-search-swa-admin-prod` |
| Key Vault / identita | `ju-ai-search-kv-prod`; SystemAssigned principal `ccacbf26-dcd6-4f7b-af7b-e3e769137de8` má již vault-scoped `Key Vault Secrets User` |
| Existující secrets | VPN username/password a JHU API username/password: všechny4 enabled; čtena jen metadata, nikoli hodnoty |
| Privátní VPN profil | secret `ju-ai-search-vpn-client-config-prod` se při listování nenašel; navrhovaný nový secret obsahuje úplný externí Client.ovpn, ne hesla |
| Model deploymenty | `gpt-5.4-mini` a `text-embedding-3-large` Succeeded; GPT-5.4 chybí |

Konkrétní implementační mezery před rolloutem:

1. `app/providers/jhu_managed.py` správně odmítá cloud APP_ENV a ověřuje lokální Docker přes inspect/exec. Nahradit pouze cloudovou větev samostatným explicitním adaptérem pro pevný loopback sidecar; místní Docker verifikaci nezrušit. V cloudu nesmí vzniknout Docker socket/daemon ani AzureCliCredential.
2. Doplnit cloudový bootstrap helperu bez `docker exec`/stdin operátora: existující managed identity, oddělené VPN/API reference, chráněný runtime profil/capability a pevný JHU target. Image nesmí obsahovat profil/hesla, helper nemá public ingress. Zachovat bounded reconnect, fail-closed chování a zákaz replay/fallback.
3. `deploy_backend.ps1` nyní výslovně vyžaduje jeden kontejner a mění jen image. Připravit nový guarded plan/apply pro dva kontejnery s expected subscription/directory/tenant/current revision/template, se zachováním stávajících secrets, identity, URL a rollbacku. Nepoužít historický PostgreSQL Bicep jako aktuální SQL šablonu.
4. Předložit rozdělení prostředků: celkový počáteční cíl 0,5 CPU /1 GiB není zároveň garantované zachování současné kapacity samotného backendu po přidání helperu. Nezmenšit backend ani nezvýšit placený součet automaticky. Pro první cloud test předložit max1 repliku a ověřit VPN session policy; Single rollout může překrýt dvě revize i při max1. Lokální helper při skutečném cloud testu vypnout.
5. Ověřit pouze existenci/chybějící SQL tabulky a připravit cílové plány `migrate_model_access.py`, `migrate_model_registry.py`, `migrate_model_metadata.py`, `migrate_model_limits.py`. Spustit jen potřebné additive DDL po schválení s přesným host/DB/tenant, zajistit dostupnost migration runneru v navržené execution cestě (současný Dockerfile kopíruje jen starší search CLI). Neměnit corpus/default embedding index, nespouštět reindex ani ANN.
6. GPT-5.4 je volitelný chybějící deployment; jeho JSON profil ani neprázdné env jméno neprokazuje dostupnost. V plánu explicitně zajistit označení jako nedostupný, nebo samostatně schválit zřízení. Nevytvářet automaticky deployment/kvótu a neblokovat ostatní modely.
7. Připravit shodné zdrojové vydání/backend+helper image a oba frontend buildy. Privátní `.env.prod` obsahuje zastaralý APP_VERSION v0.1.3; před releasem odděleně ověřit a sjednotit veřejnou runtime verzi. GitHub a čistá Forgejo publikace zůstávají zvlášť autorizované operace.

Akceptace v pořadí: tags/show ze skutečné ACA → jeden syntetický generate/embed → token/login a GPT-mini RAG s citací → JHU RAG se stejným oprávněným korpusem → výpadek/rekey → oba frontendy/modelová práva. Notebook není relay. Nový cloudový embedding index se plní jako samostatný řízený backfill; současný admin `/prepare` je úmyslně pouze lokální. Přepnutí odpovědního modelu samo index nemění. Rollback vrací předchozí backend revision a oba frontend artefakty, nové additive tabulky ponechá. Secrets se nerotují ani nemažou; nedostupné JHU nesmí vyřadit cloudové odpovědi nebo způsobit jejich automatické použití místo zvoleného modelu.

Podklady: [ACA kontejnery a sdílená síť](https://learn.microsoft.com/en-us/azure/container-apps/containers), [secrets/Key Vault](https://learn.microsoft.com/en-us/azure/container-apps/manage-secrets), [dočasná storage](https://learn.microsoft.com/en-us/azure/container-apps/storage-mounts), [Single revision rollout a překryv](https://learn.microsoft.com/en-us/azure/container-apps/revisions).

Aktualizovaný implementační plán po vydání v0.1.6 (2026-10-21). Jde o návrh pořadí, nikoli provedenou implementaci či schválení cloudových zápisů. „Bez VPN“ znamená bez ručního ovládání systémové VPN: spojení zajistí vlastní pomocný proces. Vnější úsek z notebooku/ACA do JHU chrání VPN; nezměněné HTTP API uvnitř JHU tím nezískává end-to-end HTTPS.

### Slice 0 — Důkaz proveditelnosti (spike, doporučený další krok)

- Prověřit a připnout zdroj/verzi, licenci, bezpečnostní aktualizace a rozsah patchů klienta. První kandidát je Tuna/tunpipe + tunsocks; go-openvpn je kvůli comp-lzo zatím nevhodný. Žádný kandidát ještě není přijatou závislostí.
- Reprodukovatelný Docker build a test nejprve bez credentials. Pak skutečný handshake s externím read-only profilem a bezpečně předanými secrets. Non-root, cap-drop ALL, no-new-privileges, bez TUN/host network a bez změn hostitelských rout.
- Forward pouze k pevnému JHU API cíli/portu; žádný obecný proxy server. Při chybě tunelu nesmí existovat přímá síťová cesta z forwarderu na API. Profil nesmí v kontejneru spouštět libovolné hook skripty.
- Ověřit certifikát/jméno a negativní test, tags/show, krátký syntetický generate/embed, restart i autentizační chybu; změřit CPU/RAM a cold/warm připojení. Neopakovat chybné přihlášení ve smyčce.
- Finální lokální důkaz provést bez systémové VPN; její vypnutí domluvit s uživatelem, neodpojovat cizí relaci automaticky. Test při aktivní systémové VPN není důkaz nezávislosti. Změřit i přímou dosažitelnost VPN serveru z tohoto prostředí.
- Výstup: reprodukovatelný probe, připnutý kandidát a výsledek GO/NO-GO. Při neudržovatelném forku, nutném oslabení ověřování nebo nepodporované autentizaci tuto cestu zastavit; nevytvářet vlastní VPN protokol ani automaticky novou VM.

### Slice 1 — Secrets a životní cyklus pomocné služby

- Úzce omezený JHU resolver čte čtyři výše uvedené secrets. Lokálně použije přihlášeného Azure CLI uživatele; cloud později existující managed identity. APP_ENV zůstává local a lokální SQL izolované.
- Zdroj credentials je explicitní: KV režim nesmí při chybě tiše použít starou env kopii. Rozlišit chybějící secret, zamítnutý přístup, síťovou chybu a chybu VPN; logovat jen kód/stav.
- VPN klient dostává pouze VPN credentials, backend pouze API credentials. Žádné hodnoty v image, argumentech příkazů nebo Docker inspect env; použít vhodný paměťový kanál/runtime soubor s omezenými právy podle ověřeného klienta. Ošetřit další výzvu auth-nocache i úklid po pádu.
- Lokální profil mountovat z externí cesty. Pro cloud připravit privátní runtime distribuci, přednostně volitelný KV secret ju-ai-search-vpn-client-config-prod; rozhodnout přesný mechanismus v cloud handoffu. Profil se nesmí zabalit do wheelu, image ani JHU exportu.
- Jedna spravovaná relace, stavy disabled/connecting/ready/degraded/auth_failed, omezené reconnect pokusy s prodlevou. Ztráta VPN nesmí vyřadit cloudové modely ani způsobovat restart celé aplikace.
- Akceptace: chybové testy KV, redakce, restart a úklid bez zásahu do systémové VPN. Až ověřená cesta dovolí odstranit odpovídající inline API kopie; širší úklid ostatních secrets zůstává samostatný.

### Slice 2 — Jeden JHU transport a lokální aplikace

- Zavést společný JHU HTTP transport pro generate/embed/tags/show včetně kontrol digestu, summary/classification, CLI probe a backfillu. Výslovně rozlišit stávající Windows VPN režim, nový spravovaný forward a HTTPS. Globální HTTP_PROXY není řešení.
- Preferovat pevný TCP forward za úzkým HTTP vstupem povolujícím pouze potřebné API operace; žádné pull/delete/CONNECT, libovolný upstream nebo následování redirectů mimo cíl. Lokálně host publish pouze na loopback; v ACA loopback sdíleného síťového prostoru bez ingress portu pro helper. Implementace musí ověřit konkrétní mapování, ne jen důvěřovat libovolnému proxy URL.
- Zachovat autorizaci, Basic auth, timeouty, limity a společný JHU slot. Výpadek připojení vrátí řízenou chybu; neopakuje generování ani nepřepíná model/index/cestu.
- Přidat do dev.ps1 a VS Code tasks opt-in start/status/stop pro JHU připojení. Běžný start backendu při zapnutém režimu idempotentně zajistí helper; pro ostatní tenanty se nespouští. Konkrétní názvy přepínačů stanovit až v implementaci a uvést v README.
- Akceptace: po restartu počítače standardní start z VS Code, bez ručního OpenVPN; discovery, skutečná odpověď s citací a dotaz přes jeden připravený lokální embeddingový index. Model a profil/index identity se nemění, reindexace není nutná kvůli samotnému transportu.

### Slice 3 — Provozní odolnost a balení

- Ověřit ztrátu spojení během generace, automatické obnovení pro další dotaz, rekey/obnovení autentizace, restart Dockeru a rotaci secrets řízeným restartem. Žádné automatické opakování odeslaného modelového požadavku.
- Požadavky při navazování mají omezené čekání; stav JHU poskytovat odděleně od zdraví backendu. Nevytvářet další tunel na otázku ani nekonečné fronty. Rekey doložit skutečným testem, ne pouze jednotkovým mockem.
- Ověřit dlouhodobější paměť/CPU, latenci spojení oddělenou od generace a chování dvou administrátorských porovnání; VPN účet musí dovolit zamýšlený počet relací.
- Úplné relevantní lokální regrese, buildy při UI změně, čistý wheel/JHU export a Docker context bez profilů/auth souborů. Zapsat přijaté ADR až podle důkazu kompatibility, runbook, test explanations a paměť. Samotná návrhová dokumentace není runtime akceptace.

### Slice 4 — Samostatná Azure akceptace a aktivace

**Stav po 2026-10-23:** slices 0–3 jsou implementované a lokálně ověřené; Azure slice 4 není nasazený ani automaticky schválený předchozím souhlasem s restartem Rancheru. Aktuální ADR-0040 a [runbook odolnosti](../../docs/development/jhu-connection-resilience.md) doplňují Management GET stavu a explicitní atomický refresh jako alternativu restartu backendu. Kompletní lokální SQL/wheel sada606/23, čistá JHU99/7; skutečný aktuální fault/rekey/refresh test302s a následný cited RAG17,10s prošly. Schválený globální restart Rancheru byl proveden jednou dříve v témže slicu a obnovil prostředí za92,2s. Skutečná rotace KV hesel nebyla provedena; jen syntetická nová hodnota v resolver testu. Krátké lokální výsledky nedokazují ACA síť/kapacitu ani dlouhodobou dostupnost. Viz aktuální project-state pro limity a nevyjasněná dřívější selhání.

- Připravit konkrétní plan/apply handoff pro existující ju-ai-search-ca-prod: připnutý helper image, distribuce privátního profilu, secrets přes existující identitu, resource split, startup/health a rollback. Souhlas k publikaci Git v0.1.6 nezahrnuje tuto změnu.
- Začít jednou testovací replikou a řízeným přechodem revizí; i dvě souběžné revize mohou vytvořit dvě VPN relace. Prověřit účet/policy před takovým rolloutem. Test ze samotné ACA ověří UDP egress a dostupnost JHU; notebook není relay.
- Existujících 0,5 CPU / 1 GiB je první měřený rozpočet pro součet backendu a helperu, nikoli zaručená dostatečná kapacita. Změnu alokace/min replicas/ceny předložit samostatně podle výsledků. Cloudové modely musí fungovat i při nedostupném JHU; VPN health nesmí restartovat zdravý backend.
- Akceptace: tags/show, syntetický generate/embed a skutečný oprávněný RAG dotaz z ACA při vypnutém notebooku, rekey/reconnect a redigovaná diagnostika. Cloudové modelové SQL migrace nebo další v0.1.6 změny posoudit samostatně proti aktuálně nasazenému obrazu.
- Aktivovat až po funkčním testu, s návratem na předchozí kompatibilní revizi při neúspěchu. Pokud helper neprojde, cloudový JHU profil zůstane nedostupný, žádný veřejný HTTP fallback.

Širší migrace OpenAI/Storage env kopií, ACR managed identity a cloudové dev prostředí neblokují první důkaz spojení a patří do samostatných pozdějších slices. Jejich konkrétní plán zůstává v auditní tabulce výše.

## Hodnoty k doplnění člověkem, nikdy secrets

```yaml
vpn_username_secret_created:
vpn_password_secret_created:
jhu_api_username_secret_created:
jhu_api_password_secret_created:
unattended_vpn_allowed:
vpn_mfa_or_renewal_requirement:
concurrent_vpn_sessions_allowed:
jhu_https_gateway_available:
approved_cloud_network_option:
gateway_dns_and_tls_owner:
gateway_identity_and_kv_admin:
cloud_write_scope_approved:
```

## Rollback a hranice

Zatím nebylo nic nasazeno, není co vracet. Při implementaci helper vypnout bez ukončení cizí VPN, návrat jen vlastních rout. Při přesunu secrets zachovat předchozí ověřenou konfiguraci po omezenou dobu; nemazat staré KV verze ani všechny env najednou. Cloudovou bránu lze odpojit z JHU endpoint konfigurace a vrátit předchozí kompatibilní revizi; JHU bude nedostupné, cloudové profily zůstanou explicitně volitelné. Žádný tichý fallback, reindexace, SQL migrace, změna signing key/hesel nebo kapacity není součástí tohoto auditu.

## Oficiální podklady ověřené při návrhu

- [OpenVPN 2.6 manual](https://openvpn.net/community-docs/community-articles/openvpn-2-6-manual.html): TUN, auth-user-pass, auth-nocache, pushované route/redirect-gateway a legacy comp-lzo.
- [ACA containers / limitations](https://learn.microsoft.com/en-us/azure/container-apps/containers): chybí privileged host-level režim.
- [ACA networking](https://learn.microsoft.com/en-us/azure/container-apps/networking): platformní vs vlastní VNet, neměnnost typu sítě po vytvoření.
- [VPN Gateway topology](https://learn.microsoft.com/en-us/azure/vpn-gateway/design): S2S IPsec/IKE a rozdíl P2S klienta.
- [Key Vault portal secret creation](https://learn.microsoft.com/en-us/azure/key-vault/secrets/quick-create-portal).
- [ACA secret references](https://learn.microsoft.com/en-us/azure/container-apps/manage-secrets): managed identity, versioned/versionless URI a změny/restarty.
- [go-openvpn](https://github.com/n0madic/go-openvpn): userspace klient a výslovná omezení komprese/legacy šifer.
- [OpenVPN Tuna](https://github.com/bendlas/openvpn-tuna), [tunpipe](https://github.com/ValdikSS/openvpn-tunpipe), [tunsocks](https://github.com/russdill/tunsocks): komunitní VPN-to-proxy implementace, nikoli akceptace konkrétního deploymentu.
- [HTTPX proxies](https://www.python-httpx.org/advanced/proxies/): explicitní proxy transport a volitelná SOCKS podpora.
- [ACA billing](https://learn.microsoft.com/en-us/azure/container-apps/billing): náklady podle alokace a aktivních/idle replik.
