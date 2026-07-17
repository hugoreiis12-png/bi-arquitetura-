# ============================================
# compile-pbip.ps1
# Compila todos os PBIPs do projeto (validação local)
# Uso: .\scripts\compile-pbip.ps1 [-DatasetPath src\datasets\MeuDataset.Dataset]
# ============================================

param(
    [string]$DatasetPath = "",
    [string]$OutputDir = ".\build"
)

$ErrorActionPreference = "Stop"

# Verifica pbi-tools
$pbicmd = Get-Command pbi-tools -ErrorAction SilentlyContinue
if (-not $pbicmd) {
    Write-Host "pbi-tools não encontrado. Instalando..." -ForegroundColor Yellow
    dotnet tool install --global Microsoft.PowerBI.Tools
    $env:PATH += ";$env:USERPROFILE\.dotnet\tools"
}

# Limpa build anterior
if (Test-Path $OutputDir) {
    Write-Host "Limpando $OutputDir..." -ForegroundColor DarkGray
    Remove-Item $OutputDir -Recurse -Force
}
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

if ($DatasetPath) {
    $targets = @( (Get-Item $DatasetPath) )
} else {
    $targets = Get-ChildItem -Path src/datasets -Filter *.pbip -Recurse
}

if ($targets.Count -eq 0) {
    Write-Host "Nenhum PBIP encontrado em src/datasets" -ForegroundColor Yellow
    exit 0
}

$ok = 0
$fail = @()

foreach ($pbip in $targets) {
    Write-Host ""
    Write-Host "==> Compilando $($pbip.Name)" -ForegroundColor Cyan
    pbi-tools compile $pbip.DirectoryName --out $OutputDir
    if ($LASTEXITCODE -eq 0) {
        $ok++
        Write-Host "  ✓ OK" -ForegroundColor Green
    } else {
        $fail += $pbip.Name
        Write-Host "  ✗ FAIL" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "=== Resumo ===" -ForegroundColor Cyan
Write-Host "  Compilados: $ok"
Write-Host "  Falhas:    $($fail.Count)"
if ($fail.Count -gt 0) {
    Write-Host "  - $($fail -join "`n  - ")" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Tudo compilado com sucesso" -ForegroundColor Green
