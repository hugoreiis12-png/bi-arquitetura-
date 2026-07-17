# ============================================
# refresh.ps1
# Dispara refresh do dataset no Power BI Service
# Uso: .\scripts\refresh.ps1 -WorkspaceId "xxx" -DatasetId "yyy" -Environment prod
# ============================================

param(
    [Parameter(Mandatory = $true)]
    [string]$WorkspaceId,

    [Parameter(Mandatory = $true)]
    [string]$DatasetId,

    [Parameter(Mandatory = $true)]
    [ValidateSet("dev", "test", "prod")]
    [string]$Environment,

    [string]$RefreshType = "full"  # full | automatic | dataOnly
)

$ErrorActionPreference = "Stop"

# Auth via service principal
$clientId     = $env:"PBI_SP_$($Environment.ToUpper())_CLIENT_ID"
$clientSecret = $env:"PBI_SP_$($Environment.ToUpper())_CLIENT_SECRET"
$tenantId     = $env:"PBI_TENANT_ID"

if (-not $clientId -or -not $clientSecret -or -not $tenantId) {
    Write-Error "Credenciais não configuradas no ambiente."
    exit 1
}

Write-Host "==> Adquirindo token..." -ForegroundColor DarkGray

$tokenBody = @{
    grant_type    = "client_credentials"
    client_id     = $clientId
    client_secret = $clientSecret
    scope         = "https://analysis.windows.net/powerbi/api/.default"
}

$tokenResponse = Invoke-RestMethod -Method Post `
    -Uri "https://login.microsoftonline.com/$tenantId/oauth2/v2.0/token" `
    -ContentType "application/x-www-form-urlencoded" `
    -Body $tokenBody

$token = $tokenResponse.access_token
$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type"  = "application/json"
}

Write-Host "==> Disparando refresh $RefreshType..." -ForegroundColor Cyan

$body = @{ notifyOption = "NoNotification" } | ConvertTo-Json
$body = $body -replace '"notifyOption"\s*:\s*"NoNotification"', '"type":"'$RefreshType'"'

$uri = "https://api.powerbi.com/v1.0/myorg/groups/$WorkspaceId/datasets/$DatasetId/refreshes"

try {
    $response = Invoke-RestMethod -Method Post -Uri $uri -Headers $headers -Body $body
    Write-Host "✅ Refresh disparado" -ForegroundColor Green
} catch {
    Write-Error "Falha: $_"
    exit 1
}

# Monitora
Write-Host "Monitorando..." -ForegroundColor DarkGray
$statusUri = "$uri"  # a response já retorna o id
Start-Sleep -Seconds 30
$status = Invoke-RestMethod -Method Get -Uri "$uri" -Headers $headers
$status.value | Format-Table -AutoSize
