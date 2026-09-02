@description('Azure SQL Server Name')
param serverName string

@description('Azure SQL Database Name')
param databaseName string

@description('Administrator Login Username')
param adminUser string

@description('Administrator Login Password')
@secure()
param adminPassword string

@description('Azure Region')
param location string

@description('DTU SKU Name (Basic, Standard)')
param dtuSkuName string = 'Basic'

@description('DTU Tier (Basic, Standard)')
param dtuTier string = 'Basic'

@description('DTU Capacity (5 for Basic, 10 for Standard S0, 20 for Standard S1)')
param dtus int = 5

@description('Maximum database size in bytes (e.g. 2147483648 for 2GB Basic, 268435456000 for 250GB Standard)')
param maxSizeBytes int = 2147483648

// 1. Azure SQL Server
resource sqlServer 'Microsoft.Sql/servers@2022-05-01-preview' = {
  name: serverName
  location: location
  properties: {
    administratorLogin: adminUser
    administratorLoginPassword: adminPassword
    version: '12.0'
    publicNetworkAccess: 'Enabled'
  }
}

// 2. Allow Azure Internal Services Firewall Rule (0.0.0.0)
resource allowAzureIps 'Microsoft.Sql/servers/firewallRules@2022-05-01-preview' = {
  parent: sqlServer
  name: 'AllowAllWindowsAzureIps'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

// 3. Azure SQL Database (DTU Model)
resource sqlDatabase 'Microsoft.Sql/servers/databases@2022-05-01-preview' = {
  parent: sqlServer
  name: databaseName
  location: location
  sku: {
    name: dtuSkuName
    tier: dtuTier
    capacity: dtus
  }
  properties: {
    collation: 'SQL_Latin1_General_CP1_CI_AS'
    maxSizeBytes: maxSizeBytes
  }
}

output fqdn string = sqlServer.properties.fullyQualifiedDomainName
output dbName string = sqlDatabase.name
