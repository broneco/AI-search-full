# test_jhu_helper.py

Fake Docker CLI ověřuje idempotentní start/stop, předání bootstrapu jen přes stdin, oddělení API credentials, vlastnické labely a immutable ID při mutacích. Změna konfigurace i cizí workspace jsou odmítnuté; KV chyba nic nespustí. Stará metadata se nehlásí jako ready. Pure lifecycle testy ověřují terminální auth/cert chyby a omezení tří pokusů i přes předchozí úspěšná spojení.

```powershell
.venv\Scripts\python.exe -m pytest tests/test_jhu_helper.py tests/test_jhu_secrets.py tests/test_vpn_spike.py -q
```

Tyto testy nepřistupují na Docker ani JHU. Živý start/status/reconnect/restart/stop je samostatná akceptace podle [návodu](../development/jhu-connection-helper.md), která nemění systémovou VPN. Helper se od slice2 předává v čistém JHU exportu; tento testovací modul zůstává interní kvůli společnému fixture profilu z neexportovaného experimentálního probe. Exportované transport/gateway testy a veřejný managed runbook zachovávají samostatné ověření.

Protokol2 ověřuje výhradně `127.0.0.1::18081` publish; capability vzniká pouze v bootstrap stdin, nikoli Docker args/env/labels. Runtime používá explicitní lokální image bez automatického pullu.

ForwardHealth regrese ověřují okamžité odvolání ready při neúspěšném health probe, toleranci dvou přechodných chyb, reset čítače po úspěchu a restart až při třetí souvislé chybě. Návrat upstreamu ve stejném VPN procesu nezvyšuje generation ani attempts; neúspěšná počáteční kontrola nikdy nepublikuje ready.
