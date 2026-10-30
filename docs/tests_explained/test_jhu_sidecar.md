# test_jhu_sidecar.py

Izolované testy používají syntetické ACA metadata, mock KV a skutečné providerové cesty chatu, embeddingu a discovery. Prokazují společný MI snapshot bez Dockeru, přesnou shodu health kontextu aplikace/revize/repliky/tenantu/targetu a fail-closed před odesláním modelového dotazu. Lokální managed guard zůstává platný.

Helper testuje čtyři vyjmenované MI reads bez API credentials a redakci chybných secrets. Test bootstrap řízení simuluje službu a ověřuje jediné načtení, terminální sanitizovanou chybu, samostatný liveness a cleanup bez přihlašovacího retry cyklu. Windows test nahrazuje Linux signal konstantu a souborový report; skutečný filesystem/process start se ověřuje zvlášť v Linux Docker smoke. Neprovádí žádný Azure ani VPN login.

Spuštění: `python -m pytest tests/test_jhu_sidecar.py -q`. Živá managed identity a Azure síť jsou samostatná akceptace podle [runbooku](../development/jhu-sidecar-azure.md).
