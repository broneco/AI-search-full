# ADR-0040: Přerušení JHU operací a explicitní obnova připojení

- Status: accepted for local opt-in; live fault/rekey/refresh acceptance passed 2026-10-23
- Date: 2026-10-23
- Supersedes: nutnost restartu backendu po změně helperu v ADR-0039

## Kontext

Funkční managed cesta je ověřená. Při ztrátě tunelu ale nelze nechat otázku čekat na celý modelový timeout. Po úplném restartu helperu se mění capability a host port; backend potřebuje řízené načtení nového snapshotu, aniž by znovu odeslal již zpracovávaný prompt.

## Rozhodnutí

Supervisor před čekáním na ukončení VPN potomka odvolá ready a přeruší aktivní upstream sockety. Gateway drží nejvýše čtyři handlery, třísekundové lokální TCP připojení a 300sekundový celkový watchdog. Nepřidává frontu ani automatické reconnect modelového requestu. Explicitní connect má následně `auto_open=0`, aby http.client po zrušení socketu znovu nenavázal spojení. Uzavírání je serializované pro každý upstream; shutdown a převzetí/uzavření descriptoru uvolní i makefile čtení, které jinak drží I/O reference. Dokončení a watchdog nezavírají tentýž descriptor souběžně.

Transport převádí označené chyby gateway a síťové přerušení do `jhu_connection_unavailable`/503. Modelový timeout zůstává řízený 504; žádná chyba sama nevyvolá nové generate/embed, změnu profilu, indexu nebo náhradní připojení. Další samostatný dotaz může po obnově ve stejném kontejneru použít původní snapshot.

`GET /api/models/connection` vrací whitelist stavu, pevný kód, attempts/generation, počet navázaných TLS kanálů a dobu health kontroly. Má Management autorizaci, přesnou tokenovou identitu a pouze JHU konfigurační capability. Není součástí obecného backend health. Nevrací URL, port, key, username, modelový text ani metrics requestů.

`POST /api/models/connection/refresh` vyžaduje stejné serverové oprávnění a volný společný JHU slot; jinak 429. Znovu ověří Docker owner/protokol/target/loopback mapování a explicitní API KV reference. Snapshot se vymění atomicky teprve po úspěšném načtení, chyba zachová poslední snapshot. Stavový GET neobchází sticky inicializační chybu. Žádná tato cesta nestartuje helper, nemění env, data, secrets ani oprávnění modelů. Managed režim zůstává local/test; v budoucím víceprocesovém cloudu nelze tento lokální refresh vydávat za distribuovanou rotaci.

Modelové operace zabírají slot ještě před connection/Docker/KV lookupem, takže souběžné odmítnuté otázky nečekají ve frontě thread poolu. Pokud refresh klient odejde, shieldovaný bounded KV worker drží slot do svého skutečného konce; zrušení HTTP requestu nepovolí souběžnou mutaci snapshotu s modelem.

Měření odhalilo 215–359 ms pro každé vytvoření HTTPX klienta kvůli opakovanému načítání trust bundle. Sdílíme pouze immutable SSLContext vytvořený přes stejný `httpx.create_ssl_context(verify=True, trust_env=False)`. Certifikát i hostname se nadále ověřují; HTTP klient, cookies a event-loop stav se nesdílejí. Samotné konstrukce s tímto kontextem byly 0,0–0,2 ms po prvním vytvoření. Změnu trust bundle aplikuje restart backendu.

Supervisor ukládá pouze počet skutečných `Control Channel: TLS` log událostí a součty obnovy podle pevných chybových kódů, nikoli raw logy. Gateway přidává chráněné součty forwarded operací a aktivních socketů; slouží k důkazu, že fault nevyvolal replay. Čítače příčin obnovy a operací zůstávají v chráněné diagnostice helperu, mimo whitelist správního API. Credentials, prompt ani API odpověď se do metrik neukládají.

Neúspěšná kontrola upstreamu okamžitě odvolá ready a přeruší aktivní požadavky. Samotný VPN proces však ukončí až tři po sobě neúspěšné kontroly (každá má timeout 2 s, následující začíná nejdříve po 0,5 s). Úspěšná kontrola čítač nuluje a obnoví ready ve stejné generation. Jednorázová nedostupnost při rekey tak nemusí spotřebovat celý reconnect pokus. Ukončení procesu a terminální autentizační chyby tuto toleranci nepoužívají.

## Ověření a hranice

Unit/API testy pokrývají auth, current groups, přesný tenant, atomický refresh při KV chybě/změně credentials, slot, oddělený backend health, staré/terminální heartbeat a skutečné socket přerušení před odesláním i během čtení. Samostatný živý test má explicitní opt-in; restart celého Rancheru má další nezávislý opt-in a souhlas kvůli ostatním kontejnerům. Pětiminutový soak není důkaz dnů provozu nebo cloudové kapacity. Skutečné přepsání KV hesla není testem automaticky povoleno; novou hodnotu ověřujeme v izolovaném resolveru a živě obnovu nové identity helperu.

Návod: [odolnost připojení](../development/jhu-connection-resilience.md). Azure aktivace zůstává samostatný slice 4.

Závěrečný skutečný test aktuální image prošel: přerušení generace 281 ms, obnovení 4 047 ms, soak 302 s ve stejné generation, 10 TLS kanálů a žádná příčina samovolného reconnectu. Oddělený dřívější schválený restart celého Rancheru v tomto slicu obnovil prostředí za 92,2 s; po následných změnách lokálního transportu se globální restart zbytečně neopakoval. Závěrečný 121sekundový běh také prošel. Kompletní regrese s lokální SQL a wheelem: 606 passed / 23 očekávaných skipů.

Před závěrečným ověřením jeden běh selhal na obecné model_request_failed a dva další na nečekané nové generation během soak. Příčina těchto dřívějších jevů nebyla prokázána; nezaměňovat pozdější úspěch za vysvětlení jejich příčiny. Doplněny tolerance health probe a pevné recovery_causes. Nejde o záruku dostupnosti modelového serveru, soak na dny nebo Azure acceptance.
