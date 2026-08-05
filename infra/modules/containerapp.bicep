@description('Name of Container Apps Environment')
param containerEnvName string

@description('Name of Backend Container App')
param containerAppName string

@description('Log Analytics Workspace Customer ID')
param logWorkspaceCustomerId string

@description('Log Analytics Workspace Shared Key')
@secure()
param logWorkspaceSharedKey string

@description('Docker Image Name')
param imageName string

@description('PostgreSQL Host FQDN')
param postgresHost string

@description('PostgreSQL DB Name')
param postgresDb string

@description('PostgreSQL User')
param postgresUser string

@description('PostgreSQL Password')
@secure()
param postgresPassword string

@description('Azure OpenAI Endpoint')
param openAiEndpoint string

@description('Azure OpenAI Key')
@secure()
param openAiKey string

@description('Storage Connection String')
@secure()
param storageConnectionString string

@description('Originals Container Name')
param originalsContainer string

@description('Tenant ID')
param tenantId string

@description('App Environment (dev or prod)')
param appEnv string

@description('Azure Region')
param location string

resource containerEnv 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: containerEnvName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logWorkspaceCustomerId
        sharedKey: logWorkspaceSharedKey
      }
    }
  }
}

resource containerApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: containerAppName
  location: location
  properties: {
    managedEnvironmentId: containerEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        allowInsecure: false
        corsPolicy: {
          allowedOrigins: ['*']
          allowedMethods: ['GET', 'POST', 'OPTIONS']
          allowedHeaders: ['*']
          allowCredentials: true
        }
      }
      secrets: [
        {
          name: 'pg-password'
          value: postgresPassword
        }
        {
          name: 'openai-key'
          value: openAiKey
        }
        {
          name: 'storage-conn'
          value: storageConnectionString
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'backend'
          image: imageName
          env: [
            { name: 'APP_ENV', value: appEnv }
            { name: 'POSTGRES_HOST', value: postgresHost }
            { name: 'POSTGRES_PORT', value: '5432' }
            { name: 'POSTGRES_DB', value: postgresDb }
            { name: 'POSTGRES_USER', value: postgresUser }
            { name: 'POSTGRES_PASSWORD', secretRef: 'pg-password' }
            { name: 'POSTGRES_SSLMODE', value: 'require' }
            { name: 'AZURE_OPENAI_ENDPOINT', value: openAiEndpoint }
            { name: 'AZURE_OPENAI_API_KEY', secretRef: 'openai-key' }
            { name: 'AZURE_STORAGE_CONNECTION_STRING', secretRef: 'storage-conn' }
            { name: 'AZURE_BLOB_CONTAINER_ORIGINALS', value: originalsContainer }
            { name: 'TENANT_ID', value: tenantId }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1.0Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 3
      }
    }
  }
}

output fqdn string = containerApp.properties.configuration.ingress.fqdn
output appName string = containerApp.name
