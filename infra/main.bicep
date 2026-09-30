targetScope = 'resourceGroup'

@description('Client / Tenant Name (e.g. showcase, dolphin, alzbeta)')
param clientName string = 'showcase'

@description('Environment (dev, prod)')
param environment string = 'dev'

@description('Azure Region')
param location string = 'northeurope'

// Database Provisioning Parameters (Azure SQL DTU Model)
@description('Set true to create a new Azure SQL Server and Database in DTU mode.')
param provisionAzureSql bool = true
param existingSqlHost string = ''
param sqlAdminUser string = 'sqladmin'
@secure()
param sqlAdminPassword string = ''
param dtuSkuName string = 'Basic'
param dtuTier string = 'Basic'
param dtus int = 5

// OpenAI Provisioning Parameters
@description('Set true to create a new Azure OpenAI resource.')
param provisionOpenAI bool = true
param existingOpenAiEndpoint string = ''
@secure()
param existingOpenAiKey string = ''

// Storage Account Provisioning Parameters
@description('Set true to create a new Azure Storage Account.')
param provisionStorage bool = true
param existingStorageAccountName string = ''
@secure()
param existingStorageConnectionString string = ''

// Container Registry Parameters
@description('Set true to create a new Azure Container Registry.')
param provisionACR bool = true
param existingACRName string = 'aisearchshowcasecrdev'

// Frontend Provisioning Parameters
@description('Set true to create Azure Static Web Apps for frontends.')
param provisionFrontends bool = true

// Computed resource names according to Naming Convention Standard: ai-search-{tenant}-{prefix}-{env}
var cleanClient = toLower(clientName)
var cleanEnv = toLower(environment)

var workspaceName = 'ai-search-${cleanClient}-log-${cleanEnv}'
var appInsightsName = 'ai-search-${cleanClient}-appi-${cleanEnv}'
var storageName = provisionStorage ? 'aisearch${cleanClient}st${cleanEnv}' : existingStorageAccountName
var originalsContainerName = '${cleanClient}-originals-${cleanEnv}'
var artifactsContainerName = '${cleanClient}-artifacts-${cleanEnv}'

var sqlServerName = 'ai-search-${cleanClient}-sql-${cleanEnv}'
var dbName = 'ai-search-${cleanClient}-sqldb-${cleanEnv}'

var openAiName = 'ai-search-${cleanClient}-aif-${cleanEnv}'
var acrName = provisionACR ? 'aisearch${cleanClient}cr${cleanEnv}' : existingACRName

var containerEnvName = 'ai-search-${cleanClient}-cae-${cleanEnv}'
var containerAppName = 'ai-search-${cleanClient}-ca-${cleanEnv}'

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

// 3. Azure SQL Database Module (DTU Model) (Conditional)
module azureSqlModule 'modules/azuresql.bicep' = if (provisionAzureSql) {
  name: 'azureSqlModuleDeployment'
  params: {
    serverName: sqlServerName
    databaseName: dbName
    adminUser: sqlAdminUser
    adminPassword: sqlAdminPassword
    dtuSkuName: dtuSkuName
    dtuTier: dtuTier
    dtus: dtus
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
var resolvedSqlHost = provisionAzureSql ? azureSqlModule.outputs.fqdn : existingSqlHost
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
    postgresHost: resolvedSqlHost
    postgresDb: dbName
    postgresUser: sqlAdminUser
    postgresPassword: sqlAdminPassword
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
    appName: 'ai-search-${cleanClient}-swa-user-${cleanEnv}'
    location: location
  }
}

module adminFrontend 'modules/staticwebapp.bicep' = if (provisionFrontends) {
  name: 'adminFrontendDeployment'
  params: {
    appName: 'ai-search-${cleanClient}-swa-admin-${cleanEnv}'
    location: location
  }
}

// Outputs
output backendFqdn string = containerAppModule.outputs.fqdn
output userFrontendUrl string = provisionFrontends ? userFrontend.outputs.defaultHostname : ''
output adminFrontendUrl string = provisionFrontends ? adminFrontend.outputs.defaultHostname : ''
output databaseHost string = resolvedSqlHost
output storageAccountName string = storageName
