# Testy bezpečného backend deploymentu

## Jednoduše

Testy spustí opravdový PowerShell skript, ale Azure nahradí malým lokálním programem. Ověřují, že běžné spuštění jen ukáže plán, neplatný účet nebo nepřipravená konfigurace zastaví nasazení a schválená cesta pouze sestaví image a aktualizuje kontejner. Nikdy se nepřipojují do Azure a nepoužívají skutečná hesla.

## Technicky

`tests/test_backend_deployment.py` parametrizuje dostupné Windows PowerShell 5.1 a PowerShell 7. Do tmp_path kopíruje skript, syntetický tenant `.env.prod`, ARM fixture a nativní `az.cmd` přesměrovaný na Python fake. Volání CLI zaznamená do JSONL; tajná testovací hodnota se nesmí objevit ve stdout/stderr. Fixture používá alias adresáře `ju` a skutečný runtime tenant `ju-prod`, privátní inline credentials a JWT secretRef.

Scénáře pokrývají výchozí read-only plán, nesprávnou subscription/directory/image, chybějící potvrzení JWT migrace, rozdílný tenant, známý default/chybějící JWT, selhání CLI, úspěšný image-only update i kontejner historicky pojmenovaný simple-hello-world-container a souběžnou změnu konfigurace po buildu. Native stderr warning s exit0 nesmí porušit JSON ani zastavit běh; exit9 nesmí odhalit výstup s citlivou hodnotou. Legacy `deploy_all.ps1` musí skončit před jakýmkoli nástrojem.

```powershell
.venv\Scripts\python.exe -m pytest tests/test_backend_deployment.py -q --tb=short
```

Další regrese odmítají neúplnou identitu embeddingového profilu, neexistující JWT secretRef a zastaví update při selhání ACR buildu.

Při přípravě JWT migrace přibyla platná konfigurace existujícího Key Vaultu + názvu JWT secretu, bez inline JWT nebo s výchozím klíčem čekajícím na KV resolution. Plan tento zdroj přijme bez čtení secretu nebo role assignmentu; funkční ověření načtení zůstává samostatnou podmínkou.

Nejde o test skutečného ACR buildu, platnosti secretRefs, SQL migrací ani cloudového rollout/rollbacku. Tyto části vyžadují konkrétní schválený Azure handoff a vlastní akceptaci.
