# Azure handoff: popisy modelů a porovnání v administraci

- Status: draft — cloudové zápisy nejsou v tomto úkolu schválené.
- Created: 2026-10-21
- Related ADR: [ADR-0036](../../docs/adr/ADR-0036-admin-model-comparison-and-descriptions.md)

## Cíl a konkrétní změna

Ve stávající ověřené testovací/JHU Azure SQL vytvořit pouze tabulku `model_descriptions` pro veřejné popisy CS/EN, hash přesného tenantu + model_id, přesný tenant_id, vlastní revizi, autora a UTC čas. Primární klíč `(tenant_key, model_id)`. Žádné nové služby, SKU, kapacita, RBAC, secrets, vektory, backfill ani aktivace indexu.

Kód je připravený pro lokální testy bez cloudu. Lokální startup tabulku vytvoří. Cloud startup ji explicitně vynechává. Bez migrace katalog používá původní popisy a úpravu odmítne řízenou chybou. Chyba přístupu existující tabulky se neignoruje.

## Ověřené hodnoty doplní operátor před Apply

Použij existující soukromé tenantové prostředí; nepřenášej credentials do tohoto souboru. Z read-only plánu a Azure contextu ověř subscription/directory, SQL host, databázi, přesný tenant (v DB/token scope žádná konfigurační alias normalizace), aktuální backend image a administrační SWA. K nasazení nepoužívej lokální `.env.local`.

```powershell
# V novém terminálu s vědomě zvoleným existujícím cloudovým prostředím:
.venv\Scripts\python.exe migrate_model_metadata.py
# Teprve po schválení konkrétního výše vypsaného cíle:
.venv\Scripts\python.exe migrate_model_metadata.py --apply --expect-host '<ověřený-host>' --expect-db '<ověřená-DB>' --expect-tenant '<přesný-tenant>'
```

CLI nevypisuje hesla a odmítne neshodný cíl. Operátor potřebuje právo CREATE TABLE; běžící backend SELECT/INSERT/UPDATE na nové tabulce podle existujícího SQL nastavení. Pokud práva nemá, předá krok oprávněnému správci; nemění Key Vault RBAC.

## Release a validace

Po lokálních regresích a výslovném schválení proveď běžný backend image-only release a admin frontend release do ověřených existujících prostředků podle README. User frontend není v tomto slice změněn. Současné připojení/modely a exact/ANN režim zachovat.

Management `GET /api/models/management` musí vrátit přehled bez secrets. Ulož syntetický CS/EN popis, načti jej znovu i veřejným oprávněným `/api/models`, zopakuj starou revizi a ověř 409. Ordinary user PUT/management GET musí vrátit 403. Ověř tenantovou izolaci, nezměněné počty profilů/chunků/index UUID a dvě samostatná vlákna při porovnání. Úpravu shrnutí/klasifikace ověř na budoucím syntetickém zpracování, bez automatického přepracování korpusu.

## Návrat

Vrať předchozí backend image a admin build. Přidaná tabulka je kompatibilní navíc; nemaž ji ani její popisy. Předchozí runtime používá dosavadní JSON popisy. Žádný rollback vektorů/aktivace není potřeba. Skutečná cloudová validace a naměřené chování patří do dokončeného deployment záznamu, ne do lokálního tvrzení.
