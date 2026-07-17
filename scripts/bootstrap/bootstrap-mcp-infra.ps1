# ============================================
# bootstrap-mcp-infra.ps1
# Provisiona toda a infra do MCP server no Azure
#
# Cria:
# - Resource Group
# - VNet + Subnet
# - Container Apps Environment
# - Container App (MCP Server)
# - Azure Cache for Redis
# - Azure AI Search
# - App Insights
# - Key Vault
# - Service Principal (MCP-only)
# - 5 Azure AD groups (RBAC)
# - 3 workspaces Power BI (Dev/Test/Prod)
# - 1 workspace AI-Playground
#
# Uso:
# .\bootstrap-mcp-infra.ps1 `
#   -SubscriptionId "xxx" `
#   -ResourceGroupName "rg-bi-mcp" `
#   -Location "eastus" `
#   -Environment "dev" `
#   -PowerBIWorkspaceDev "Dev Workspace Name" `
#   -PowerBIWorkspaceTest "Test Workspace Name" `
#   -PowerBIWorkspaceProd "Prod Workspace Name"
# ============================================

param(
    [Parameter(Mandatory = $true)]
    [string]$SubscriptionId,

    [Parameter(Mandatory = $true)]
    [string]$ResourceGroupName,

    [string]$Location = "eastus",

    [ValidateSet("dev", "test", "prod")]
    [string]$Environment = "dev",

    [string]$McpAppName = "powerbi-mcp",

    [string]$PowerBIWorkspaceDev = "[DEV] Vendas",
    [string]$PowerBIWorkspaceTest = "[TEST] Vendas",
    [string]$PowerBIWorkspaceProd = "Vendas",
    [string]$PowerBIWorkspacePlayground = "[AI-PLAYGROUND] Vendas",

    [string]$SpDisplayName = "bi-mcp-server",

    [switch]$SkipPowerBI
)

$ErrorActionPreference = "Stop"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Bootstrap MCP Server Infra" -ForegroundColor Cyan
Write-Host "  Environment: $Environment" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# ===========================
# 1. Set subscription
# ===========================
Write-Host "[1/9] Setting subscription..." -ForegroundColor Yellow
az account set --subscription $SubscriptionId | Out-Null
Write-Host "  ✓ Subscription: $SubscriptionId" -ForegroundColor Green

# ===========================
# 2. Create Resource Group
# ===========================
Write-Host "[2/9] Creating resource group $ResourceGroupName..." -ForegroundColor Yellow
$rgExists = az group exists --name $ResourceGroupName
if ($rgExists -eq "false") {
    az group create --name $ResourceGroupName --location $Location | Out-Null
    Write-Host "  ✓ Resource group created" -ForegroundColor Green
} else {
    Write-Host "  ✓ Resource group already exists" -ForegroundColor Green
}

# ===========================
# 3. VNet + Subnet for Container Apps
# ===========================
Write-Host "[3/9] Creating VNet + Subnet..." -ForegroundColor Yellow
$vnetName = "vnet-$McpAppName-$Environment"
$subnetName = "snet-container-apps"

$existingVnet = az network vnet show --name $vnetName --resource-group $ResourceGroupName 2>$null
if (-not $existingVnet) {
    az network vnet create `
        --resource-group $ResourceGroupName `
        --name $vnetName `
        --address-prefix "10.0.0.0/16" `
        --subnet-name $subnetName `
        --subnet-prefix "10.0.1.0/24" `
        --location $Location | Out-Null
    Write-Host "  ✓ VNet + Subnet created" -ForegroundColor Green
} else {
    Write-Host "  ✓ VNet already exists" -ForegroundColor Green
}

$subnetId = az network vnet subnet show `
    --resource-group $ResourceGroupName `
    --vnet-name $vnetName `
    --name $subnetName `
    --query "id" -o tsv

# ===========================
# 4. App Insights
# ===========================
Write-Host "[4/9] Creating Application Insights..." -ForegroundColor Yellow
$appInsightsName = "appi-$McpAppName-$Environment"
$existingAi = az monitor app-insights component show --app $appInsightsName --resource-group $ResourceGroupName 2>$null
if (-not $existingAi) {
    az monitor app-insights component create `
        --app $appInsightsName `
        --resource-group $ResourceGroupName `
        --location $Location `
        --application-type web | Out-Null
    Write-Host "  ✓ App Insights created" -ForegroundColor Green
} else {
    Write-Host "  ✓ App Insights already exists" -ForegroundColor Green
}
$appInsightsCs = az monitor app-insights component show `
    --app $appInsightsName `
    --resource-group $ResourceGroupName `
    --query "connectionString" -o tsv

# ===========================
# 5. Key Vault
# ===========================
Write-Host "[5/9] Creating Key Vault..." -ForegroundColor Yellow
$kvName = "kv-bi-$Environment".Replace("-", "").Substring(0, [Math]::Min(24, "kv-bi-$Environment".Replace("-", "").Length))
$existingKv = az keyvault show --name $kvName --resource-group $ResourceGroupName 2>$null
if (-not $existingKv) {
    az keyvault create `
        --name $kvName `
        --resource-group $ResourceGroupName `
        --location $Location `
        --enable-rbac-authorization false `
        --sku standard | Out-Null
    Write-Host "  ✓ Key Vault created: $kvName" -ForegroundColor Green
} else {
    Write-Host "  ✓ Key Vault already exists: $kvName" -ForegroundColor Green
}

# ===========================
# 6. Redis
# ===========================
Write-Host "[6/9] Creating Redis Cache..." -ForegroundColor Yellow
$redisName = "redis-$McpAppName-$Environment"
$existingRedis = az redis show --name $redisName --resource-group $ResourceGroupName 2>$null
if (-not $existingRedis) {
    az redis create `
        --resource-group $ResourceGroupName `
        --name $redisName `
        --location $Location `
        --sku Basic `
        --vm-size C0 | Out-Null
    Write-Host "  ✓ Redis created" -ForegroundColor Green
} else {
    Write-Host "  ✓ Redis already exists" -ForegroundColor Green
}
$redisKey = az redis list-keys --name $redisName --resource-group $ResourceGroupName --query "primaryKey" -o tsv
$redisHost = az redis show --name $redisName --resource-group $ResourceGroupName --query "hostName" -o tsv
$redisUrl = "redis://:$redisKey@$redisHost`:6380/0"

# ===========================
# 7. AI Search (RAG)
# ===========================
Write-Host "[7/9] Creating AI Search..." -ForegroundColor Yellow
$searchName = "srch-bi-$Environment"
$existingSearch = az search service show --name $searchName --resource-group $ResourceGroupName 2>$null
if (-not $existingSearch) {
    az search service create `
        --name $searchName `
        --resource-group $ResourceGroupName `
        --location $Location `
        --sku standard | Out-Null
    Write-Host "  ✓ AI Search created" -ForegroundColor Green
} else {
    Write-Host "  ✓ AI Search already exists" -ForegroundColor Green
}
$searchEndpoint = "https://$searchName.search.windows.net"

# ===========================
# 8. Container Apps Environment
# ===========================
Write-Host "[8/9] Creating Container Apps Environment + MCP Server..." -ForegroundColor Yellow
$envName = "env-bi-mcp-$Environment"
$existingEnv = az containerapp env show --name $envName --resource-group $ResourceGroupName 2>$null
if (-not $existingEnv) {
    az containerapp env create `
        --name $envName `
        --resource-group $ResourceGroupName `
        --location $Location `
        --infrastructure-subnet-resource-id $subnetId `
        --internal-only true | Out-Null
    Write-Host "  ✓ Container Apps Environment created" -ForegroundColor Green
} else {
    Write-Host "  ✓ Container Apps Environment already exists" -ForegroundColor Green
}

# ===========================
# 9. Service Principal (MCP-only)
# ===========================
Write-Host "[9/9] Creating Service Principal..." -ForegroundColor Yellow
$spList = az ad sp list --display-name $SpDisplayName --query "[].{appId:appId,objectId:id}" -o json | ConvertFrom-Json
if ($spList.Count -eq 0) {
    $spOutput = az ad sp create-for-rbac `
        --name $SpDisplayName `
        --role "Power BI Service Contributor" `
        --scopes "/subscriptions/$SubscriptionId" `
        --output json | ConvertFrom-Json

    $spClientId = $spOutput.appId
    $spObjectId = $spOutput.objectId
    $spSecret = $spOutput.password
    Write-Host "  ✓ SP created: $spClientId" -ForegroundColor Green

    # Store secret in Key Vault
    az keyvault secret set --vault-name $kvName --name "mcp-sp-client-id" --value $spClientId | Out-Null
    az keyvault secret set --vault-name $kvName --name "mcp-sp-client-secret" --value $spSecret | Out-Null
    Write-Host "  ✓ SP credentials stored in Key Vault" -ForegroundColor Green
} else {
    $spClientId = $spList[0].appId
    $spObjectId = $spList[0].objectId
    Write-Host "  ✓ SP already exists: $spClientId" -ForegroundColor Green
}

# ===========================
# 10. Azure AD Groups (RBAC)
# ===========================
Write-Host "" -ForegroundColor Yellow
Write-Host "[BONUS] Creating Azure AD groups for RBAC..." -ForegroundColor Yellow

$groups = @(
    @{ Name = "BI-AI-Reader";    Description = "Read-only access to Power BI via AI" },
    @{ Name = "BI-AI-Developer"; Description = "Can write measures and validate DAX" },
    @{ Name = "BI-AI-Lead";      Description = "Can deploy to Dev and Test" },
    @{ Name = "BI-AI-Steward";   Description = "Can deploy to Prod and modify RLS" },
    @{ Name = "BI-AI-Admin";     Description = "Full access including config" }
)

foreach ($g in $groups) {
    $existing = az ad group list --filter "displayName eq '$($g.Name)'" --query "[].id" -o tsv
    if (-not $existing) {
        $newGroup = az ad group create `
            --display-name $g.Name `
            --mail-nickname $g.Name `
            --description $g.Description `
            --output json | ConvertFrom-Json
        Write-Host "  ✓ Group created: $($g.Name) (oid: $($newGroup.id))" -ForegroundColor Green
    } else {
        Write-Host "  ✓ Group already exists: $($g.Name) (oid: $existing)" -ForegroundColor Green
    }
}

# ===========================
# 11. Power BI Workspaces
# ===========================
if (-not $SkipPowerBI) {
    Write-Host "" -ForegroundColor Yellow
    Write-Host "[BONUS] Power BI workspaces..." -ForegroundColor Yellow
    Write-Host "  ⚠  Power BI workspace creation is done via Power BI Service" -ForegroundColor Yellow
    Write-Host "  ⚠  Create these workspaces manually or via Power BI cmdlets:" -ForegroundColor Yellow
    Write-Host "     - $PowerBIWorkspaceDev" -ForegroundColor White
    Write-Host "     - $PowerBIWorkspaceTest" -ForegroundColor White
    Write-Host "     - $PowerBIWorkspaceProd" -ForegroundColor White
    Write-Host "     - $PowerBIWorkspacePlayground" -ForegroundColor White
    Write-Host ""
    Write-Host "  Then add the SP '$spClientId' as Contributor to each workspace." -ForegroundColor Yellow
}

# ===========================
# Summary
# ===========================
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Bootstrap Complete!" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Resources created:" -ForegroundColor Green
Write-Host "  Resource Group:      $ResourceGroupName"
Write-Host "  VNet:                $vnetName"
Write-Host "  App Insights:        $appInsightsName"
Write-Host "  Key Vault:           $kvName"
Write-Host "  Redis:               $redisName"
Write-Host "  AI Search:           $searchName"
Write-Host "  Container Apps Env:  $envName"
Write-Host "  Service Principal:   $spClientId"
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Create Power BI workspaces (Dev/Test/Prod/Playground)"
Write-Host "  2. Add SP '$spClientId' as Contributor to each workspace"
Write-Host "  3. Deploy MCP server:  cd mcp/powerbi-mcp-server && az containerapp create ..."
Write-Host "  4. Configure secrets in GitHub/Azure DevOps"
Write-Host "  5. Onboard first user"
Write-Host ""
Write-Host "Configuration saved to: .bootstrap-config.json" -ForegroundColor Cyan

# Save config for reference
@{
    subscription_id    = $SubscriptionId
    resource_group     = $ResourceGroupName
    location           = $Location
    environment        = $Environment
    mcp_app_name       = $McpAppName
    vnet_name          = $vnetName
    subnet_id          = $subnetId
    app_insights_cs    = $appInsightsCs
    key_vault          = $kvName
    redis_url          = $redisUrl
    search_endpoint    = $searchEndpoint
    container_env      = $envName
    sp_client_id       = $spClientId
    sp_object_id       = $spObjectId
    workspace_dev      = $PowerBIWorkspaceDev
    workspace_test     = $PowerBIWorkspaceTest
    workspace_prod     = $PowerBIWorkspaceProd
    workspace_playground = $PowerBIWorkspacePlayground
} | ConvertTo-Json -Depth 10 | Out-File ".bootstrap-config-$Environment.json" -Encoding utf8
