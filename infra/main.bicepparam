using 'main.bicep'

param clientName = 'dolphin'
param environment = 'dev'
param location = 'northeurope'

// Set provisioning toggles: true = create new, false = reuse existing
param provisionPostgres = true
param existingPostgresHost = ''
param postgresAdminUser = 'Bronec'
param postgresAdminPassword = 'BULVER4v68rTzf4X'

param provisionOpenAI = true
param existingOpenAiEndpoint = ''
param existingOpenAiKey = ''

param provisionStorage = true
param existingStorageAccountName = ''
param existingStorageConnectionString = ''

param provisionACR = false
param existingACRName = 'dolphinds'

param provisionFrontends = true
