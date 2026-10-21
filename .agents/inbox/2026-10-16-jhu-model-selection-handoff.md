# JHU model selection — integrační handoff

Stav: připraveno; Azure zápisy tímto handoffem nejsou provedené ani automaticky schválené. Read-only ověření 2026-10-16 potvrdilo pouze deploymenty text-embedding-3-large a gpt-5.4-mini. **GPT-5.4 deployment chybí**, ačkoli na něj env odkazuje. Nový adaptér byl ověřen jednou skutečnou syntetickou odpovědí GPT-5.4-mini (asi 4,6 s); GPT-5.4 nelze živě přijmout před jeho samostatně schváleným zřízením.

## Cíl a stávající prostředky

Tenant musí zůstat přesně `ju-prod`; konfigurace se načítá z jhu. Poslední ověřený backend je `ju-ai-search-ca-prod`, revize `ju-ai-search-ca-prod--0000008`, image `prod-v014-20261015-145009`. Před nasazením ověř současnou subscription/directory, resource group, SQL host/DB, ACR a SWA podle aktuálního Azure účtu. Neodvozuj cloudový stav z lokálního backendu.

Read-only account show: subscription `24e4a9a6-bab0-43f7-ba20-3b774704fade`, directory `c35f5da4-9a03-44e6-8bf9-92833634f6a7`. Stávající privátní cílová konfigurace uvádí RG `ju-ai-search-rg-prod`, model resource `ju-ai-search-aif-prod`, SQL host `ju-ai-search-sql-prod.database.windows.net`, DB `ju-ai-search-sqldb-prod`, ACR `juaisearchcrprod`, SWA `ju-ai-search-swa-user-prod` a `ju-ai-search-swa-admin-prod`. Tyto hodnoty nejsou povolením k zápisům; při releasu je ověř znovu proti živým prostředkům.

## Oddělené operace

1. V ověřené SQL DB spusť `migrate_model_access.py` bez Apply. Po schválení použij Apply s přesným očekávaným host/DB/tenant. Vzniká pouze `model_access_policies`; žádné korpusové/vector/ANN migrace.
2. Ověř existující Azure deploymenty GPT-5.4-mini a GPT-5.4. Zkontroluj `AZURE_OPENAI_FLASH_DEPLOYMENT`, `AZURE_OPENAI_THINKING_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION=2024-10-21` a případný APP_VERSION override. Modelový profil není důkaz existence deploymentu.
3. Pro JHU doplň chráněnou síťovou cestu z Container App. Lokální OpenVPN byla ověřena pouze na notebooku. Bez prokázané cloudové cesty nech JHU nenakonfigurované/nedostupné; cloudové profily lze vydat samostatně.
4. Runtime potřebuje `JHU_LLM_ENDPOINT`, `JHU_LLM_USERNAME`, `JHU_LLM_PASSWORD`, `JHU_LLM_VERIFIED_MODEL=qwen3.8:latest`. Username/password lze dodat existujícími Container App secretRefs nebo Key Vault referencemi. Jména KV secrets se nastavují přes `AZURE_KEY_VAULT_SECRET_JHU_LLM_USERNAME` a `AZURE_KEY_VAULT_SECRET_JHU_LLM_PASSWORD`; skutečná jména doplní operátor bez hodnot secrets.
5. Preferuj HTTPS/chránený transport. HTTP vyžaduje výslovné `JHU_LLM_ALLOW_HTTP=true` až po ověření síťové ochrany. Nevypínej TLS verifikaci a nevytvářej veřejný proxy endpoint.
6. Backend image a oba frontendové release plány připrav standardními deploy skripty. Apply backendu nemění runtime secrets, SQL ani networking. Žádné automatické zvýšení kapacity, model deployment create, RBAC granty, ANN nebo reembedding.

## Hodnoty k doplnění před Apply

- Azure subscription/directory, resource group, přesný SQL host/DB, ACR/image a obě existující SWA.
- Ověřené názvy obou GPT deploymentů a funkční API verze.
- Cloudová cesta k JHU endpointu, použitá ochrana transportu a jména secrets/referencí (bez jejich hodnot).
- Rozsah schválených operací: SQL tabulka / runtime nastavení / image / frontend samostatně.

## Validace a rollback

Ověř login, katalog bez secrets, obě cloudové odpovědi s citacemi, přepnutí modelu v historii, správu přístupů a přímé odmítnutí zakázaného modelu. JHU testuj nejprve synteticky, po připojení z cloudového backendu. Model má výrazný studený start; neopakuj automaticky timeoutnuté generace.

Rollback: obnov předchozí backend revision a frontend artefakty; SQL tabulku ponech. Pro deaktivaci JHU odeber jeho ověřené runtime připojení, výchozí GPT mini ponech. Bez explicitní potřeby nemaž data, nereindexuj korpus ani nerotuj existující klíče. Do záznamu výsledků odděl skutečné cloudové ověření od SQLite/mocků a lokálního VPN smoke.
