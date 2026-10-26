# test_jhu_secrets.py

API-only reference backendu nemohou číst VPN pár; samostatná regrese prokazuje přesně dvě API čtení a odmítnutí VPN ještě před čtením.

Testy s fake SecretReader bez privátních souborů/sítě ověřují oddělené čtení dvou VPN a dvou API referencí, redakci CredentialPair, invalidní hodnoty a přesné řízené chyby pro 401/403/404, síť a další chyby. Nasazené env hodnoty se při chybě nepoužijí. Mockované AzureCliCredential/ManagedIdentityCredential ověřují výslovnou volbu identity, úklid klientů a žádné implicitní SDK retries.

```powershell
.venv\Scripts\python.exe -m pytest tests/test_jhu_secrets.py -q
```

Živý `jhu_connection.py check-secrets` je oddělený opt-in. Nevypisuje hodnoty; samotné úspěšné čtení neprokazuje validní VPN/API heslo.
