# ============================================
# publish.ps1
# Publica PBIP no Power BI Service via REST API (workspace unico dinamico).
# O desvio dev/test/prod acontece so no commit, via sufixo por branch:
#   main -> Vendas | develop -> Vendas_Dev | test/release/* -> Vendas_Test
#   demais -> Vendas_preview_<slug>
# Uso: .\scripts\publish.ps1 -DatasetPath src\datasets\Vendas.Dataset -WorkspaceId $env:PBI_WORKSPACE_ID -Environment dev
# ============================================

param(
    [Parameter(Mandatory = $true)]
    [string]$DatasetPath,

    [string]$WorkspaceId = $env:PBI_WORKSPACE_ID,

    [Parameter(Mandatory = $true)]
    [ValidateSet("dev", "test", "prod")]
    [string]$Environment,

    [string]$TargetDataset = "",

    [string]$Conflict = "replace"  # replace | abort | ignore
)

function Get-TargetDataset {
    param([string]$Explicit, [string]$Base = "Vendas")
    if ($Explicit) { return $Explicit }
    try { $br = (git rev-parse --abbrev-ref HEAD 2>$null).Trim() } catch { $br = "" }
    if (-not $br) { $br = $env:GITHUB_REF_NAME }
    if ($br -eq "main") { return $Base }
    if ($br -eq "develop") { return "${Base}_Dev" }
    if ($br -eq "test" -or $br -like "release/*") { return "${Base}_Test" }
    if ($br) {
        $slug = ($br.ToLower() -replace "[^a-z0-9]+", "_").Trim("_")
        if ($slug.Length -gt 20) { $slug = $slug.Substring(0, 20).Trim("_") }
        if ($slug) { return "${Base}_preview_${slug}" }
    }
    return "${Base}_preview"
}

$ErrorActionPreference = "Stop"

if (-not $WorkspaceId) {
    Write-Error "WorkspaceId vazio. Configure PBI_WORKSPACE_ID (workspace unico dinamico por projeto conectado) ou passe -WorkspaceId."
    exit 1
}
$resolvedDataset = Get-TargetDataset -Explicit $TargetDataset
Write-Host "==> Publicando no ambiente '$Environment' (workspace unico)" -ForegroundColor Cyan
Write-Host "    Dataset:  $DatasetPath -> $resolvedDataset"
Write-Host "    Workspace: $WorkspaceId"
Write-Host "    Conflict:  $Conflict"
Write-Host "    Isolamento: RLS+Build por dataset (sem workspace por ambiente)"
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
