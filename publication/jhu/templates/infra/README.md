# Provisioning šablony

Tato složka obsahuje Bicep a PowerShell zdroje pro provisioning. Nejde o ověřený aktuální release postup existujícího JHU prostředí. main.bicepparam má nesoulad se současnou šablonou; PostgreSQL moduly a legacy Compose nejsou podporovaným lokálním vývojem.

Pro existující aplikaci používej [oddělený backend/frontend deployment](../docs/deployment.md) a pro lokální vývoj kořenový docker-compose.local.yml přes dev.ps1. Provisioning nejdřív vyžaduje vlastní revizi cílových parametrů, šablon, bezpečných secret vstupů a oprávnění; nespouští se při publikaci zdrojů.
