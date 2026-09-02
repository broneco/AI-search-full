targetScope = 'resourceGroup'

@description('Client / Tenant Name (e.g. dolphin, alzbeta, showcase)')
param clientName string = 'dolphin'

@description('Environment (dev, prod, showcase)')
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
param existingACRName string = 'craisearchdev'

// Frontend Provisioning Parameters
@description('Set true to create Azure Static Web Apps for frontends.')
param provisionFrontends bool = true

// Computed resource names according to Naming Convention Standard
var cleanClient = toLower(clientName)
var cleanEnv = toLower(environment)
var baseName = '${cleanClient}-${cleanEnv}'

var workspaceName = 'log-aisearch-${cleanEnv}'
var appInsightsName = 'appi-aisearch-${cleanEnv}'
var storageName = provisionStorage ? 'staisearch${cleanEnv}' : existingStorageAccountName
var originalsContainerName = '${cleanClient}-originals-${cleanEnv}'
var artifactsContainerName = '${cleanClient}-artifacts-${cleanEnv}'

var sqlServerName = 'sql-aisearch-${cleanEnv}'
var dbName = 'sqldb-${cleanClient}-${cleanEnv}'

var openAiName = 'oai-aisearch-${cleanEnv}'
var acrName = provisionACR ? 'craisearch${cleanEnv}' : existingACRName

var containerEnvName = 'cae-aisearch-${cleanEnv}'
var containerAppName = 'ca-aisearch-${cleanClient}-${cleanEnv}'

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
    appName: 'swa-aisearch-${cleanClient}-user-${cleanEnv}'
    location: location
  }
}

module adminFrontend 'modules/staticwebapp.bicep' = if (provisionFrontends) {
  name: 'adminFrontendDeployment'
  params: {
    appName: 'swa-aisearch-${cleanClient}-admin-${cleanEnv}'
    location: location
  }
}

// Outputs
output backendFqdn string = containerAppModule.outputs.fqdn
output userFrontendUrl string = provisionFrontends ? userFrontend.outputs.defaultHostname : ''
output adminFrontendUrl string = provisionFrontends ? adminFrontend.outputs.defaultHostname : ''
output databaseHost string = resolvedSqlHost
output storageAccountName string = storageName
