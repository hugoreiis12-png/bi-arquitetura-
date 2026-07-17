# ============================================
# extract-pbip.ps1
# Converte um .pbix legado em PBIP (.Dataset + .Report)
# Uso: .\scripts\extract-pbip.ps1 -InputPath .\legacy\dashboard.pbix -OutputDir .\src
# ============================================

param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath,

    [Parameter(Mandatory = $true)]
    [string]$OutputDir
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $InputPath)) {
    Write-Error "Arquivo não encontrado: $InputPath"
    exit 1
}

Write-Host "==> Extraindo PBIP de $InputPath" -ForegroundColor Cyan

# 1. Garante pbi-tools instalado
$pbicmd = Get-Command pbi-tools -ErrorAction SilentlyContinue
if (-not $pbicmd) {
    Write-Host "Instalando pbi-tools..." -ForegroundColor Yellow
    dotnet tool install --global Microsoft.PowerBI.Tools
    $env:PATH += ";$env:USERPROFILE\.dotnet\tools"
}

# 2. Extrai
$baseName = [System.IO.Path]::GetFileNameWithoutExtension($InputPath)
$destPath = Join-Path $OutputDir "datasets\$baseName.Dataset"

New-Item -ItemType Directory -Path $destPath -Force | Out-Null

pbi-tools extract "$InputPath" --out "$destPath" --format PBIP

if ($LASTEXITCODE -ne 0) {
    Write-Error "Falha na extração"
    exit 1
}

# 3. Reporta
Write-Host ""
Write-Host "✅ PBIP extraído em: $destPath" -ForegroundColor Green
Write-Host ""
Write-Host "Próximos passos:" -ForegroundColor Yellow
Write-Host "  1. Abra o arquivo $baseName.pbip no Power BI Desktop"
Write-Host "  2. Confirme que dataset e report estão visíveis"
Write-Host "  3. git add . && git commit -m 'feat: migra $baseName para PBIP'"
