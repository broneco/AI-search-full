# Regresní testy vývojového PowerShell skriptu

## Jednoduše

Docker může napsat varování, i když funguje. Testy ověřují, že vývojový skript takové varování nepovažuje za vypnutý Docker a pokračuje dál. Skutečné chyby připojení či spuštění/zastavení databáze musí pořád skončit chybou.

## Technicky

Managed startup regrese nahradí Python cestu skutečným testovacím interpretem a použijí syntetické `jhu_connection.py` a `uvicorn.py`. Ověřují předání přesného tenantu, managed režimu, workspace a KV referencí; chyba helperu nezabrání startu backendu. Pro jiného tenanta se helper ani backend nespustí. Žádný skutečný Docker, model, SQL nebo Azure se nevolá.

Spuštěný stub Uvicornu zaznamená skutečné argumenty. Regrese ověří právě jeden `--reload-dir` směřující na `app/` konkrétního workspace; testovací kopie v dočasných adresářích tak nepatří do sledovaného stromu. Testy samotné používají výchozí číslovaný workspace pod `.local/tmp/pytest/`.

`tests/test_dev_script.py` spouští skutečný `dev.ps1` v izolovaném dočasném adresáři přes Windows PowerShell 5.1 a PowerShell 7, pokud jsou dostupné na PATH. Místo Dockeru používá nativní `docker.cmd`, který zapisuje na stderr a vrací řízený exit code. Testy pokrývají úspěšné zastavení s varováním, neúspěšné zastavení, úspěšný daemon probe s varováním následovaný řízenou chybou Compose a neúspěšný daemon probe, který nesmí spustit Compose. Kontrolují i pořadí skutečně volaných příkazů. Testování používá pouze fiktivní lokální env a nikdy nevolá skutečný Docker ani Azure. Mimo Windows se tato sada přeskočí.

```powershell
.venv\Scripts\python.exe -m pytest tests/test_dev_script.py -q
```
