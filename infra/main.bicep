targetScope = 'resourceGroup'

@description('Client Name (e.g. dolphin, university)')
param clientName string = 'dolphin'

@description('Environment (dev or prod)')
@allowed(['dev', 'prod'])
param environment string = 'dev'

@description('Azure Region')
param location string = 'northeurope'

// Conditional Resource Provisioning Toggles
@description('Set true to create a new Azure Database for PostgreSQL Flexible Server.')
param provisionPostgres bool = true
param existingPostgresHost string = ''
param postgresAdminUser string = 'pgadmin'
@secure()
param postgresAdminPassword string = ''

@description('Set true to create a new Azure OpenAI resource.')
param provisionOpenAI bool = true
param existingOpenAiEndpoint string = ''
@secure()
param existingOpenAiKey string = ''

@description('Set true to create a new Azure Storage Account.')
param provisionStorage bool = true
param existingStorageAccountName string = ''
@secure()
param existingStorageConnectionString string = ''

@description('Set true to create a new Azure Container Registry.')
param provisionACR bool = true
param existingACRName string = 'dolphinds'

@description('Set true to create Azure Static Web Apps for frontends.')
param provisionFrontends bool = true

// Computed resource names
var cleanClient = toLower(clientName)
var cleanEnv = toLower(environment)
var baseName = '${cleanClient}-${cleanEnv}'

var workspaceName = 'log-${baseName}'
var appInsightsName = 'appins-${baseName}'
var storageName = provisionStorage ? 'st${cleanClient}${cleanEnv}${uniqueString(resourceGroup().id)}' : existingStorageAccountName
var originalsContainerName = '${cleanClient}-originals-${cleanEnv}'
var artifactsContainerName = '${cleanClient}-artifacts-${cleanEnv}'

var postgresServerName = 'psql-${baseName}-${uniqueString(resourceGroup().id)}'
var dbName = '${cleanClient}_ai_search_${cleanEnv}'

var openAiName = 'oai-${baseName}-${uniqueString(resourceGroup().id)}'
var acrName = provisionACR ? 'acr${cleanClient}${cleanEnv}${uniqueString(resourceGroup().id)}' : existingACRName

var containerEnvName = 'env-${baseName}'
var containerAppName = '${cleanClient}-ai-search-backend-${cleanEnv}'

// 1. Observability Module
module logAnalytics 'modules/log_analytics.bicep' = {
  name: 'logAnalyticsDeployment'
  params: {
    workspaceName: workspaceName
    appInsightsName: appInsightsName
    location: location
  }
}

// 2. Storage Module (Conditional)
module storageModule 'modules/storage.bicep' = if (provisionStorage) {
  name: 'storageModuleDeployment'
  params: {
    storageAccountName: storageName
    originalsContainerName: originalsContainerName
    artifactsContainerName: artifactsContainerName
    location: location
  }
}

// 3. PostgreSQL Module (Conditional)
module postgresModule 'modules/postgres.bicep' = if (provisionPostgres) {
  name: 'postgresModuleDeployment'
  params: {
    serverName: postgresServerName
    databaseName: dbName
    adminUser: postgresAdminUser
    adminPassword: postgresAdminPassword
    location: location
  }
}

// 4. Azure OpenAI Module (Conditional)
module openAiModule 'modules/openai.bicep' = if (provisionOpenAI) {
  name: 'openAiModuleDeployment'
  params: {
    openAiName: openAiName
    location: location
  }
}

// 5. Azure Container Registry Module (Conditional)
module acrModule 'modules/acr.bicep' = if (provisionACR) {
  name: 'acrModuleDeployment'
  params: {
    acrName: acrName
    location: location
  }
}

// Resolved connection values
var resolvedPostgresHost = provisionPostgres ? postgresModule.outputs.fqdn : existingPostgresHost
var resolvedOpenAiEndpoint = provisionOpenAI ? openAiModule.outputs.endpoint : existingOpenAiEndpoint
var resolvedOpenAiKey = provisionOpenAI ? openAiModule.outputs.apiKey : existingOpenAiKey
var resolvedStorageConnStr = provisionStorage ? storageModule.outputs.connectionString : existingStorageConnectionString
var resolvedAcrServer = provisionACR ? acrModule.outputs.loginServer : '${existingACRName}.azurecr.io'
var imageName = '${resolvedAcrServer}/${containerAppName}:latest'

// 6. Azure Container Apps Backend Module
module containerAppModule 'modules/containerapp.bicep' = {
  name: 'containerAppDeployment'
  params: {
    containerEnvName: containerEnvName
    containerAppName: containerAppName
    logWorkspaceCustomerId: logAnalytics.outputs.workspaceCustomerId
    logWorkspaceSharedKey: ''
    imageName: imageName
    postgresHost: resolvedPostgresHost
    postgresDb: dbName
    postgresUser: postgresAdminUser
    postgresPassword: postgresAdminPassword
    openAiEndpoint: resolvedOpenAiEndpoint
    openAiKey: resolvedOpenAiKey
    storageConnectionString: resolvedStorageConnStr
    originalsContainer: originalsContainerName
    tenantId: '${cleanClient}-${cleanEnv}'
    appEnv: cleanEnv
    location: location
  }
}

// 7. Frontend Static Web Apps Modules (Conditional)
module userFrontend 'modules/staticwebapp.bicep' = if (provisionFrontends) {
  name: 'userFrontendDeployment'
  params: {
    appName: 'swa-${cleanClient}-user-${cleanEnv}'
    location: location
  }
}

module adminFrontend 'modules/staticwebapp.bicep' = if (provisionFrontends) {
  name: 'adminFrontendDeployment'
  params: {
    appName: 'swa-${cleanClient}-admin-${cleanEnv}'
    location: location
  }
}

// Outputs
output backendFqdn string = containerAppModule.outputs.fqdn
output userFrontendUrl string = provisionFrontends ? userFrontend.outputs.defaultHostname : ''
output adminFrontendUrl string = provisionFrontends ? adminFrontend.outputs.defaultHostname : ''
output databaseHost string = resolvedPostgresHost
output storageAccountName string = storageName
