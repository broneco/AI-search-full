@description('Name of the Log Analytics Workspace')
param workspaceName string

@description('Name of Application Insights')
param appInsightsName string

@description('Azure Region')
param location string

resource logWorkspace 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: workspaceName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logWorkspace.id
  }
}

output workspaceId string = logWorkspace.id
output workspaceCustomerId string = logWorkspace.properties.customerId
output appInsightsConnectionString string = appInsights.properties.ConnectionString
