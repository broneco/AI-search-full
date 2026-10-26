# test_vpn_spike.py

Izolované testy bez privátní konfigurace, Key Vaultu, VPN a Dockeru. Ověřují zachování CA/jména/comp-lzo, odmítnutí hooků, include, alternativních auth souborů, duplicitních remote a chybějících kontrol identity. Kontrolují, že bridge předává jen minimální prostředí, jediný pevný forward a žádnou cestu přes hostový stack nebo obecnou proxy. Exportní pravidla odmítnou `.ovpn` a `.auth` včetně velikosti písmen.

Další regrese ověřují vynechání persist-tun pouze z odvozeného configu, odmítnutí prázdné identity a mapování AUTH_FAILED/TLS/certifikátových chyb na pevné kódy bez textu peer logu.

```powershell
.venv\Scripts\python.exe -m pytest tests/test_vpn_spike.py tests/test_jhu_publication.py -q
```

Samostatný `probe_jhu_vpn.py offline` skutečně spouští non-root Docker bez sítě a pozoruje TCP SYN na unixovém descriptoru. `live` je explicitní externí test s KV a JHU; není součástí běžných unit testů. Podmínky, příkazy a omezení jsou v [návodu](../development/jhu-vpn-spike.md).
