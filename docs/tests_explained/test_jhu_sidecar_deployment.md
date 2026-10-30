# test_jhu_sidecar_deployment.py

Testy staví plán nad syntetickým Container App dokumentem a ověřují přesný cloud/data tenant, SQL, vault, topologii, immutable image, veřejné porty a kapacitu. Veřejný plán nesmí obsahovat soukromé env ani scale metadata; původní konfigurace se zachová jen uvnitř patch template v paměti.

Apply se nepovolí bez stejného fingerprintu/revize a potvrzení migrací, modelů, VPN relace, kapacitní změny a případného souběhu revizí. Změna stavu těsně před zápisem přeruší rollout. Mock HTTP ověřuje jediný ARM PATCH s location/template, zachovaným If-Match, bez CLI argumentů nesoucích tělo či token. Timeout se neopakuje a chyba je sanitizovaná. CLI testuje Windows launcher/UTF8, odmítnutí shell syntaxe, standardní read-only režim a kontrolu účtu před čtením aplikace.

Spuštění: `python -m pytest tests/test_jhu_sidecar_deployment.py -q`. Tyto testy neprokazují akceptaci skutečného ARM template ani dostupnost image/modelu v Azure.
