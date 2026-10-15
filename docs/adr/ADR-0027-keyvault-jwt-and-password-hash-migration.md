# ADR-0027: JWT z Key Vaultu a nezávislé ukládání hesel

- Status: accepted (lokální implementace; cloudové nastavení/nasazení čeká na schválení)
- Date: 2026-10-15
- Owners: AI Search Core Team

## Context

JHU backend už má Key Vault Secrets User na svém vaultu. Uživatel nemůže udělovat nové role, ale může vytvářet secrets. Dosavadní heslový hash SHA256(password:JWT_SECRET) svazoval hesla s podpisovým klíčem tokenů. Nový soukromý JWT by bez přechodové cesty zablokoval přihlášení. Historický původ konkrétního heslového hashe nelze určit z dnešního env. SDK pro Key Vault navíc nebylo v requirements, přestože je kód importoval.

## Decision

- Nové registrace a lokální demo účty ukládají Argon2id s náhodnou solí: 19 MiB, 2 iterace, 1 lane, 16B salt/32B digest. Používáme `argon2-cffi`, nikoli vlastní kryptografický algoritmus. Formát obsahuje parametry a vejde se do stávajícího VARCHAR(255), bez DDL. Hodnoty odpovídají [OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html); paměť a CPU na skutečném JHU při souběhu se ještě neměřily. Native verifier má omezení načtených parametrů (max64MiB,4iterace,4lanes), aby poškozený hash nemohl vyžádat neomezenou práci. Slabší podporovaný Argon2 lze po úspěchu posílit; silnější se automaticky nesnižuje.
- Cloud přijímá starý 64hex SHA256 pouze přes explicitní `LEGACY_PASSWORD_SECRET` se skutečným původním klíčem. Není to JWT fallback: starým klíčem nelze podepsat platný nový token. Žádné automatické hádání veřejného defaultu v cloudu. Local/test dočasně umožňuje svůj dosavadní JWT pro staré demo účty. Nové hashe na žádném z těchto klíčů nezávisí.
- Po úspěšném legacy přihlášení se skutečné heslo zahashuje Argon2id a provede tenant-scoped compare-and-set UPDATE podle user UUID a přesného předchozího hashe. Výsledný token se vrátí až po commit. Chybné heslo, chybějící/nesprávný legacy klíč nebo nefunkční signing key nic nepřepíší. Současná změna credentialu znamená odmítnutí přihlášení; DB chyba rollback+503 bez provider detailů. Úspěšný moderní login hash nemění.
- Hashování/ověřování v async routách běží v threadpoolu. Neznámý uživatel a zamítnuté legacy heslo provedou dummy Argon2 verifikaci. Nejde o náhradu budoucích limitů počtu přihlášení ani o prokázání konstantního času celé API cesty.
- `AZURE_KEY_VAULT_SECRET_JWT_SIGNING_KEY` určí secret name; volitelný `..._VERSION` umožní připnout jednotnou verzi pro všechny repliky. `AZURE_KEY_VAULT_SECRET_LEGACY_PASSWORD` určí oddělený starý klíč pro migraci. Fetch probíhá přes existující DefaultAzureCredential/SecretClient jen v cloud prostředí, nikdy local/test. Soukromý explicitní runtime JWT/legacy klíč má přednost. Prázdný nebo známý default JWT může být nahrazen z KV; při selhání zůstane autentizace odmítnutá, bez převzetí legacy klíče. JWT a legacy hodnoty jsou v Settings skryté pro repr/model_dump.
- Doplněny `azure-keyvault-secrets`, `azure-identity` a `argon2-cffi` do instalačních manifestů podle skutečných importů. Žádné nové Azure role ani změny identity. Release plan přijímá explicitní KV JWT zdroj, ale nevydává přítomnost názvu za funkční čtení nebo cloudovou akceptaci.

## Consequences and migration

Uživatelé se správným doloženým původním klíčem mohou zachovat stejné heslo. Tokeny podepsané starým JWT po rotaci přestanou platit a je nutné se znovu přihlásit. Po migraci všech relevantních účtů lze odstranit legacy konfiguraci; neaktivní/neprokázané účty vyžadují vlastní postup, nikoli automatický reset nebo sloučení. Známé demo/nevhodně přidělené účty potřebují samostatný audit; kompatibilita neopravňuje jejich použití v produkci.

Rollback na původní image neumí ověřit nové Argon2 hashe. Před cloudovou aktivací proto vyžadujeme rollback verzi s tímto verifierem nebo výslovně připravenou obnovu credentialů; vrácení image samo nestačí. Nesmí se plošně obnovit staré hashe a přepsat tím nová hesla. Žádný hash, secret, token nebo plaintext není součástí dokumentace. `.env` nebyly měněny a key parity zůstává zachovaná; nové runtime klíče jsou volitelné, vypsané v handoffu.

## Verification and follow-up

Mocked Key Vault testy pokrývají precedence/version/failure/local isolation a neunikání citlivých údajů. SQLite i lokální MSSQL ověřují úspěšnou tenant-scoped migraci, zamítnutí chybného hesla/klíče, commit rollback, změněný credential, registraci a nezávislost na dalším JWT. Skutečné secrets a runtime smoke musí navázat podle `.agents/inbox/2026-10-15-jhu-jwt-password-migration-handoff.md`; žádný cloudový zápis tento ADR neschvaluje.
