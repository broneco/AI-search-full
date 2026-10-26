# Úzká lokální HTTP brána

Odolnost přidává skutečný zablokovaný upstream: supervisor zruší socket během čekání a klient musí dostat 503 do dvou sekund bez replay. Samostatný případ ruší spojení mezi track a odesláním; `auto_open=0` brání implicitnímu opětovnému připojení. Následující nový request po ready projde. Ready se starým heartbeat neforwarduje. Watchdog a supervisor serializují uzavření descriptoru, který může držet HTTP makefile.

`tests/test_jhu_gateway.py` spouští skutečný HTTP server na náhodném loopback portu a syntetický pevný upstream. Ověřuje capability před forwardem, povolené metody/cesty, zákaz CONNECT/pull/delete/redirect, request limit a odmítnutí chunked framingu. Upstream dostane jen API Basic auth a content type; capability ani klientský Host neprochází dál.

Nepřipravené stavy vracejí 503 bez upstream volání, request body se před řízeným odmítnutím spotřebuje v omezené velikosti, aby uzavření TCP nezpůsobilo reset. Timeout má jediný pokus a pevnou chybu bez obsahu exception. Testy nepoužívají VPN, skutečné credentials ani Docker.

```powershell
.venv\Scripts\python.exe -m pytest tests/test_jhu_gateway.py -q
```
