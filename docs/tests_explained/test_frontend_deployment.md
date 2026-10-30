# Testy frontend deploymentu

`tests/test_frontend_deployment.py` spouští skutečný PowerShell skript s vlastními nativními fake az/npm/npx. Každý běh má syntetické prostředky a log příkazů; síťové operace se neprovádějí.

Kontroluje, že výchozí plán pouze čte, Apply cílí na existující SWA, chyby Azure/build/token/deploy vracejí nenulový kód, žádná větev nevolá create a chybná subscription zastaví práci před buildem. Syntetický deployment token se nesmí objevit ve stdout/stderr. Stejná sada běží pro dostupný Windows PowerShell a PowerShell7; na ostatních systémech je explicitně přeskočená.

Spuštění: `python -m pytest tests/test_frontend_deployment.py -q`.

SWA deployment token musí být dostupný v child prostředí `SWA_CLI_DEPLOYMENT_TOKEN` a chybět v argv/logu nativních příkazů. Fake npx ověřuje i dočasné `SWA_CLI_DEBUG=error`; skript po dokončení obnovuje původní hodnoty prostředí. Cílená Windows sada po této změně prošla14testy.

Použitá proměnná je dokumentovaná v [oficiální SWA CLI dokumentaci](https://azure.github.io/static-web-apps-cli/docs/cli/env-vars/).
