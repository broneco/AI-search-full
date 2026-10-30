# Skutečný test Python balíčku

`tests/test_packaging.py` se zapíná `RUN_PACKAGE_TESTS=1` a potřebuje setuptools/wheel. Vytvoří čistý zdrojový staging, vloží syntetický zakázaný env soubor a sestaví skutečný wheel bez sítě/build isolation. Ověří přítomnost backendových modulů, JSON/PDF resources a nepřítomnost env/bytecode.

Syntetický secret leží pod JHU. Test kontroluje všechny skutečně přibalené JSON soubory a nevyžaduje `tenants/default` ani jiné klienty; podporuje tak i samostatný JHU export.

VPN spike přidává syntetické `Client.ovpn` a `vpn.auth` pod tenantem; skutečný wheel musí oba vyloučit.

Poté wheel rozbalí mimo checkout a importuje aplikaci izolovaným Python procesem s vyčištěnými cloudovými proměnnými. Kontroluje i JHU alias prompty a cestu k ukázkovým PDF. Nejde pouze o kontrolu textu manifestu. Běžný unit běh tento integrační build přeskakuje; způsob zapnutí je v README.

Embeddingová slice navíc ověřuje načtení JHU Nomic katalogu z nainstalovaného wheelu mimo checkout; profil 768 musí být dostupný bez soukromého prostředí.

Managed integrace kontroluje přibalení a import `jhu_managed.py` a `jhu_secrets.py` bez závislosti na hostitelském `scripts/` či root probe. Izolovaný import odstraňuje také JHU process variables; nesmí potřebovat Docker ani Key Vault.

Cloudový runtime musí být také v instalovaném wheelu: kontrola vyžaduje app/providers/jhu_sidecar.py. Žádné .ovpn/.auth/env hodnoty se nebalí.

Trvalá nastavení přidávají povinný modul `app/storage/tenant_settings.py`; izolovaný import aplikace musí fungovat i s jeho lazy vazbou na resolver, bez připojení k produkční databázi.
