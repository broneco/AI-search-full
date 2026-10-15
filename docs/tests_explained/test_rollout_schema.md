# Testy schvalované schema migrace

`tests/test_rollout_schema.py` používá SQLite a izolovaný lokální SQL Server fixture. Ověřuje povinné zastavení writerů a skutečný převod VARCHAR→NVARCHAR spolu s přesným `ju`→`ju-prod`. Tenant `ju ` se nesmí změnit; počet řádků musí souhlasit, chybný expected count celou datovou transakci odmítne. Po převodu projde nový český text beze ztráty znaků.

Full-Text větev se provede, pokud ho lokální SQL Server má. Současný Docker SQL2022 ho nemá, proto lokální test neprokazuje FTS DDL. Před skutečným rolloutem bylo zvlášť ověřeno Azure CREATE/DROP/Unicode/restore na jediné malé dočasné tabulce v JHU se skutečným katalogem, jazykem1033 a SYSTEM stoplistem; tabulka byla odstraněna a původní index nebyl tímto testem změněn.

```powershell
$env:RUN_LOCAL_SQL_TESTS='1'
.venv\Scripts\python.exe -m pytest tests/test_rollout_schema.py -q --tb=short
```

Migrace odděluje autocommit FTS DDL a transakční Unicode/data část. FTS se obnovuje i při selhání datové transakce, pokud byl odebrán; změna neslučuje uživatele. Samotný guard neprokazuje zastavení aplikace: operátor musí ověřit nulové repliky a backup.
