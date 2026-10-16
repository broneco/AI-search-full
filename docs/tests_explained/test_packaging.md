# Skutečný test Python balíčku

`tests/test_packaging.py` se zapíná `RUN_PACKAGE_TESTS=1` a potřebuje setuptools/wheel. Vytvoří čistý zdrojový staging, vloží syntetický zakázaný env soubor a sestaví skutečný wheel bez sítě/build isolation. Ověří přítomnost backendových modulů, JSON/PDF resources a nepřítomnost env/bytecode.

Syntetický secret leží pod JHU. Test kontroluje všechny skutečně přibalené JSON soubory a nevyžaduje `tenants/default` ani jiné klienty; podporuje tak i samostatný JHU export.

Poté wheel rozbalí mimo checkout a importuje aplikaci izolovaným Python procesem s vyčištěnými cloudovými proměnnými. Kontroluje i JHU alias prompty a cestu k ukázkovým PDF. Nejde pouze o kontrolu textu manifestu. Běžný unit běh tento integrační build přeskakuje; způsob zapnutí je v README.
