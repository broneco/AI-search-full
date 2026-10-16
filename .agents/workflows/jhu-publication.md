# Workflow: předání JHU a nasazení do Azure

Toto je kanonický postup pro AI v hlavním vývojovém repozitáři. Nepoužívej staré privátní skripty z `.local/hardening-*` ani `.local/publications/prepare_jhu.py`; nejsou potřebné po novém klonu. Aktuální nástroje jsou verzované `export_jhu.py`, `prepare_jhu_publication.py`, `scripts/publication/` a `publication/jhu/templates/`.

## 1. Urči schválený cíl

| Požadavek | Povolený výstup | Samostatná operace |
|---|---|---|
| Vydat změny do normálního repa | GitHub `broneco/AI-search-full`, současná větev `microsoft-sql`, schválený release tag | Forgejo předání a Azure release |
| Aktualizovat JHU repo | Forgejo `dconsulting/jhu-ai-search`, větev `main`, nový souhrnný commit | Nasazení aplikace, SQL, indexů a secrets |
| Nasadit aplikaci JHU do Azure | Explicitně schválený backend/frontend cíl | Změny schématu, reembedding, ANN aktivace, RBAC a kapacity |

Pokud „JHU deployment“ neurčuje, zda jde o předání zdrojů nebo Azure, vyjasni cíl před zápisy. Mezitím lze číst stav a připravit plán. Neopakuj již udělené schválení v jeho rozsahu. Nikdy nedoplň chybějící resource/tenant hodnoty odhadem.

## 2. Zachovej oddělení repozitářů

- Zdroj: `https://github.com/broneco/AI-search-full.git`.
- Předání: `https://forgejo.jcu.cz/dconsulting/jhu-ai-search.git`, samostatný clone, nikoli worktree zdrojového Gitu.
- Doporučený lokální cíl: `.local/publications/jhu-ai-search` uvnitř zdrojového workspace; složka je ignorovaná a přežije restart.
- První publikace vytvořila samostatný kořenový commit `e4b116efc51ff41bae65a338155b94caee7b1a2c`. Při dalších publikacích zachovej její návaznost. Nový kořen nevytvářej opakovaně.
- Nepřidávej Forgejo remote do zdrojového Gitu. Nekopíruj `.git`, nepoužívej mirror, merge/cherry-pick vývojových commitů, push všech větví/tagů, force-push ani přepis historie.
- Uživatel chce v JHU pouze současný stav. Nepředávej staré changelogy, release/deployment reporty, handoffy, archiv AI paměti, provozní deníky, interní zdrojové SHA nebo cestu na soukromé operátory. Aktuální návody/architektura a budoucí souhrnné předávací commity zůstávají.

## 3. Připrav zdrojové vydání

Přečti kontrakt, project-state, tento workflow a deployment handshake. Ověř větev, origin, pracovní změny a vzdálený stav. Zachovej práci uživatele. Verzi sjednoť v pyproject.toml, backendu, obou package.json/package-lock.json, UI badge a README. Zaznamenej release notes, changelog a skutečné výsledky testů.

Export čte pouze commitnutý Git ref přes `git archive`. Necommitované změny ani pracovní secrets automaticky nečte. Pro předání používej schválený neměnný tag/commit; nepředpokládej, že HEAD obsahuje právě editovaný kód. Commit/tag/push hlavního repozitáře musí být autorizovaný pro konkrétní vydání.

Privátní env nejsou součástí vydání. Před skutečným Azure releasem prověř `APP_VERSION`, protože existující env ji může přepsat. Úpravu pouze veřejné verze odděl od credentials; nikdy nevypisuj obsah env/secrets. Verze zdroje není důkazem verze běžící služby.

## 4. Zkontroluj cílový checkout

Příkazy spouštěj z kořene hlavního workspace. Při prvním použití:

```powershell
git clone https://forgejo.jcu.cz/dconsulting/jhu-ai-search.git .local/publications/jhu-ai-search
```

Při dalším předání:

```powershell
git -C .local/publications/jhu-ai-search remote -v
git -C .local/publications/jhu-ai-search status --short
git -C .local/publications/jhu-ai-search switch main
git -C .local/publications/jhu-ai-search fetch origin main
git -C .local/publications/jhu-ai-search pull --ff-only origin main
git -C .local/publications/jhu-ai-search log -3 --oneline
git -C .local/publications/jhu-ai-search rev-parse HEAD
```

Pracovní strom musí být čistý. Pokud cílový tým přidal vlastní commity, zkontroluj jejich diff a slaď změny před projekcí; čistý Git sám neprokazuje, že je lze přepsat. Divergenci nebo necommitované změny neřeš resetem/cleanem. U čerstvého skutečně prázdného cíle použij očekávané HEAD `EMPTY`, jinak přesné SHA.

## 5. Vygeneruj kandidáta

Nahraď ukázkový tag skutečným schváleným vydáním a zvol nový výstupní název:

```powershell
.venv\Scripts\python.exe export_jhu.py --ref v0.1.5 --output .local/publications/jhu-v0.1.5.zip
```

Nástroj nic nepushuje. Vytvoří ZIP a sousední `.manifest.json`; existující artefakt nepřepisuje. Manifest uchovává interní provenienci mimo zákaznický ZIP. Oba soubory zachovej jako pár.

Povinné vlastnosti exportu:

- Pouze `tenants/jhu`, bez privátních env; chybějící search/classification se zmaterializují z aktuálních default souborů.
- Jediný JHU motiv a logo obou frontendů. Lokální identita jhu a demo login JHU; cloudová přesná identita ju-prod se nikdy nezkracuje.
- Ostatní runtime změny smí být jen explicitní projekce definovaná v nástroji. Změna očekávaného formátu způsobí chybu a vyžaduje revizi, nikoli tiché hádání.
- Žádný Git graf, jiné klientské konfigurace, interní exportéry/templates, pracovní dokumenty, dependency/cache, klíče, data a historické poznámky.
- Aktuální dokumentace je z verzovaných templates. Při změně chování reviduj také templates; automatická projekce není záruka jejich aktuálnosti.

## 6. Zobraz plán, potom aplikuj soubory

```powershell
.venv\Scripts\python.exe prepare_jhu_publication.py --archive .local/publications/jhu-v0.1.5.zip --destination .local/publications/jhu-ai-search
```

Zkontroluj `head`, `write` i `remove` proti zamýšlenému předání. Výchozí režim je read-only. Apply vyžaduje přesné SHA právě zkontrolovaného cíle:

```powershell
.venv\Scripts\python.exe prepare_jhu_publication.py --archive .local/publications/jhu-v0.1.5.zip --destination .local/publications/jhu-ai-search --expect-head "<ověřené cílové HEAD>" --apply
git -C .local/publications/jhu-ai-search diff --stat
git -C .local/publications/jhu-ai-search diff
```

Nástroj odmítá jiný origin, větev, nečistý checkout, nevhodné cesty, symlinky/junctions a kolize s lokálními soubory. Maže pouze plánované sledované soubory, které už nejsou v předání; ignorované secrets/data a `.git` zachová. Neprovádí commit/push. Neobejdi odmítnutí pomocí resetu nebo ručního kopírování přes ochrany; zjisti příčinu.

Přerušené zapisování může zanechat pracovní diff. Zkontroluj jej vůči předchozímu HEAD a manifestu; nespouštěj apply znovu proti nečistému stromu. Případný návrat omez na konkrétní generované soubory po ověření, že neobsahují cizí práci. Žádný plošný git clean.

## 7. Ověř přesný kandidát

Rozbal ZIP do nové ignorované testovací složky. Nepoužívej `pip install .` z jiného cwd, protože requirements.txt odkazuje na relativní `.[dev]`. Ověř package/resources bez privátních env, izolované testy a oba frontend buildy/TypeScript. Lokální SQL regrese spusť při zásahu do DB. Native Azure a výkon jsou oddělené explicitní brány.

Ověř tenantí scope, dokumentační odkazy a hashe ZIP/manifestu; proveď kontrolu secrets bez jejich výpisu. Do zákaznického changelogu přidej pouze aktuální souhrn předávané verze, ne interní auditní průběh. Pokud po generování měníš zákaznické soubory, vrať změnu do verzovaných templates/projekce a znovu vytvoř kandidáta z nového commitu; nepoužívej neodpovídající manifest.

## 8. Commit a push pouze do Forgejo

```powershell
git -C .local/publications/jhu-ai-search add --all
git -C .local/publications/jhu-ai-search diff --cached --stat
git -C .local/publications/jhu-ai-search commit -m "Předání JHU AI Search v0.1.5"
git -C .local/publications/jhu-ai-search push origin main
git -C .local/publications/jhu-ai-search rev-parse HEAD
git ls-remote https://forgejo.jcu.cz/dconsulting/jhu-ai-search.git refs/heads/main
```

Před commitem zkontroluj přesný staged file set a runtime/brand rozdíly vůči ZIPu; nativní Git může normalizovat EOL. Po pushi musí vzdálené main SHA odpovídat lokálnímu. Ověř čistý checkout a návaznost na předchozí publikované HEAD. Neopakuj úvodní jednorootový commit při aktualizaci. Git Credential Manager obstará přihlášení; heslo/token nepatří do chatu ani URL.

Ulož neveřejný release záznam pod `.local/publications/`: zdrojové SHA/tag/verze, cílové SHA před/po, manifest a hash ZIPu, výsledky testů, schválení a rozsah. Do aktuální projektové paměti zapiš odkaz a skutečně dokončený stav, bez secrets. Pokud push selže, rozliš lokální commit od vzdáleného výsledku a nehlaš vydání jako dokončené.

## 9. Samostatný Azure release

Pro Azure pokračuj jen s odpovídajícím schválením. Použij [deployment handshake](../rules/azure-deployment-handshake.md) a [aktuální README](../../README.md#deployment-do-azure). Ověř Azure subscription/directory, přesný tenant, resource group, Container App/ACR/SWA a stávající image/modelový profil. Připrav read-only plány, změny a rollback před zápisy.

Backend `deploy_backend.ps1` má image-only Apply s očekávaným subscription/directory/image a explicitním potvrzením dokončených migrací. Frontendy `deploy_frontend.ps1` publikuj odděleně do existujících SWA s JHU motivem a ověřeným HTTPS backendem. Prověř APP_VERSION a runtime nastavení; lokální env nevydávej do image. SQL migraci, reembedding, indexovou aktivaci, RBAC, klíče a kapacitu nikdy nepřidávej k běžnému image releasu implicitně.

Předání zdrojů do Forgejo nemění Azure. Po skutečném nasazení ověř ready revizi/verzi, login, chat/citace/PDF/CORS a oprávnění. ANN zůstává explicitní možností; exact se nemění bez zvláštní validace a schválení.
