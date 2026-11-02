# ADR-0043: Explicitní cloudové indexy jako trvalé správní úlohy

Status: Accepted for source implementation; cloud rollout requires separate acceptance.

## Kontext

Lokální synchronní příprava indexu nesmí být pouhým odstraněním guardu zpřístupněna v cloudu. Výpočet může trvat déle než HTTP timeout, backend může být vyměněn a procesový semafor nechrání více pracovníků. JHU již podporuje nativní alternativní indexy nad stejnými chunky, chyběla jejich správní orchestrace.

## Rozhodnutí

Zavádíme poslední správní úlohu každého přesného tenantu v SQL `index_preparation_jobs`, včetně UUID úlohy/indexu, neměnného profilu, stavu, počtů, podmíněné rezervace a heartbeat. Nová explicitní operace Managera vrací HTTP 202 a běží mimo hlavní async smyčku v samostatném workeru s vlastním SQL session/event loopem. Nejde o novou placenou službu nebo obecnou frontu všech aplikačních úloh.

Cloud vyžaduje Azure SQL/MSSQL, aditivní migraci a `INDEX_PREPARATION_ENABLED=true`. Startup nic nemigruje. Vytvoření prázdné nativní tabulky je oddělené od backfillu. Platné dávky se zachovávají a po přerušení se opakují jen chybějící revize. Po ztrátě procesu se pokračování neprovádí automaticky. Vypršelá rezervace, změna identity úlohy, zrušení nebo ztráta oprávnění zabrání dalšímu potvrzení výsledků; při zápisu se rezervace v MSSQL zamyká ve stejné transakci jako dávka.

Oprávnění Managera a modelu se ověřuje při přijetí i před každou dávkou. Není povoleno přepočítávat ingestovaný výchozí index, mazat indexy, měnit sdílené chunky/revize ani aktivovat nový default. Alternativní profil zůstává digest-pinned; pravidla query/document instrukcí a ACL se nemění.

## Důsledky a hranice

SQL uchovává poslední operaci, nikoli úplnou historii. Krátký výpadek UI úlohu neukončí; výměna procesu může vyžadovat explicitní resume. Zrušené právě probíhající volání modelu může doběhnout, ale jeho neautorizovaná dávka se nesmí uložit. Počet tenantových úloh je omezený, sdílená JHU modelová propustnost se dál řídí existujícím slotem a může vracet busy; nedochází k automatickému opakování modelových volání.

Tento zdrojový krok neposkytuje obecnou garanci HA, automatické obnovení po restartu ani souhlas s cloudovou migrací. Native Azure a živá UI akceptace následují po samostatném schváleném nasazení. [Provozní postup](../development/cloud-embedding-management.md).
