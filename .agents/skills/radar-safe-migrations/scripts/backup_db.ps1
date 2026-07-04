$ErrorActionPreference = "Stop"
$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..\..")
Set-Location $projectRoot
$candidates = @("data\radar_laboral.db", "radar_laboral.db")
$dbPath = $null
foreach ($candidate in $candidates) {
    if (Test-Path $candidate) { $dbPath = Resolve-Path $candidate; break }
}
if (-not $dbPath) { throw "No se encontró la base SQLite en las rutas conocidas." }
$backupDir = Join-Path $projectRoot "backups"
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupPath = Join-Path $backupDir "radar_laboral_$timestamp.db"
Copy-Item $dbPath $backupPath -Force
Write-Host "Respaldo creado: $backupPath"
