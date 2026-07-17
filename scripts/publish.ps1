# ============================================
# publish.ps1
# Publica PBIP no Power BI Service via REST API
# Uso: .\scripts\publish.ps1 -DatasetPath src\datasets\Vendas.Dataset -WorkspaceId "xxxx-xxxx" -Environment dev
# ============================================

param(
    [Parameter(Mandatory = $true)]
    [string]$DatasetPath,

    [Parameter(Mandatory = $true)]
    [string]$WorkspaceId,

    [Parameter(Mandatory = $true)]
    [ValidateSet("dev", "test", "prod")]
    [string]$Environment,

    [string]$Conflict = "replace"  # replace | abort | ignore
)

$ErrorActionPreference = "Stop"

Write-Host "==> Publicando no ambiente '$Environment'" -ForegroundColor Cyan
Write-Host "    Dataset:  $DatasetPath"
Write-Host "    Workspace: $WorkspaceId"
Write-Host "    Conflict:  $Conflict"
Write-Host ""

# Variáveis de ambiente por ambiente
$clientId = $env:"PBI_SP_$($Environment.ToUpper())_CLIENT_ID"
$clientSecret = $env:"PBI_SP_$($Environment.ToUpper())_CLIENT_SECRET"
$tenantId = $env:"PBI_TENANT_ID"

if (-not $clientId -or -not $clientSecret -or -not $tenantId) {
    Write-Error "Variáveis de ambiente faltando. Configure PBI_SP_${Environment.ToUpper()}_CLIENT_ID, _CLIENT_SECRET e PBI_TENANT_ID"
    exit 1
}

# Compila primeiro
Write-Host "Compilando PBIP..." -ForegroundColor DarkGray
& "$PSScriptRoot\compile-pbip.ps1" -DatasetPath $DatasetPath -OutputDir ".\build\$Environment"
if ($LASTEXITCODE -ne 0) { exit 1 }

# Verifica pbi-tools
$pbicmd = Get-Command pbi-tools -ErrorAction SilentlyContinue
if (-not $pbicmd) {
    dotnet tool install --global Microsoft.PowerBI.Tools
    $env:PATH += ";$env:USERPROFILE\.dotnet\tools"
}

# Publica
Write-Host "Publicando..." -ForegroundColor Cyan
pbi-tools publish $DatasetPath `
    --workspace $WorkspaceId `
    --auth sp `
    --tenant $tenantId `
    --clientId $clientId `
    --clientSecret $clientSecret `
    --conflict $Conflict

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ Publicado com sucesso" -ForegroundColor Green
    Write-Host "https://app.powerbi.com/groups/$WorkspaceId" -ForegroundColor Blue
} else {
    Write-Error "Falha na publicação"
    exit 1
}
