# Testy konfigurace lokálního vývoje

## Jednoduše

Testy ověřují, že aplikace umí výslovně zvolit lokální SQL Server, používá pojmenovanou lokální databázi a odmítne spuštění bez přihlašovacích údajů nebo s cloudovou adresou databáze. Tím brání nechtěnému připojení do Azure při lokálním vývoji.

## Technicky

Testy vytvářejí samostatné instance `Settings` bez načítání `.env` souborů. Kontrolují profil `APP_ENV=local`, rozlišení `DATABASE_BACKEND=sqlserver`, kompatibilní příznak pro existující SQL Server větev, validační chybu při chybějícím hesle a odmítnutí hostitele mimo loopback. Nevyžadují SQL Server, Docker ani Azure.
