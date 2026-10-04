# Lanza los Ojos (ojos.py) en esta ventana, independiente de Claude.
#   .\lanzadores\ojos.ps1                 sin fin: cada 12 segundos ven todo, lo validan con la Contable y proponen
#   .\lanzadores\ojos.ps1 -Ticks 1        una sola mirada
#   .\lanzadores\ojos.ps1 -Segundos 30    una mirada cada 30 segundos
# Solo leen (GET): no mandan ni aceptan nada, así que no hay modo en vivo ni hace falta escribir SI.
# La clave se lee de bazaar-kit\.env (o de la variable BAZAAR_KEY) y no se escribe en ningún sitio.
# Parar: cerrar esta ventana, Ctrl + C, o crear el archivo runs\STOP (ojo: STOP es de todo el equipo).
# La última vista queda en runs\ojos.json: la lee la skill /ojos. (El Regateador y el Cambista usan los Ojos dentro de su tick.)
param(
    [int]$Ticks = 0,
    [double]$Segundos = 12
)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")   # team7: aquí están runs, menus.json y programas
$kit = Join-Path $PSScriptRoot "..\..\..\bazaar-kit\.env"
if (Test-Path $kit) {
    foreach ($l in Get-Content $kit) {
        if ($l -match '^\s*(BAZAAR_KEY|BAZAAR_URL)\s*=\s*(.+?)\s*$') { Set-Item -Path ("env:" + $Matches[1]) -Value $Matches[2] }
    }
}
if (-not $env:BAZAAR_KEY) { $env:BAZAAR_KEY = [Environment]::GetEnvironmentVariable("BAZAAR_KEY", "User") }
if (-not $env:BAZAAR_KEY) { Write-Host "Falta BAZAAR_KEY (ni en bazaar-kit\.env ni en las variables de usuario)."; Read-Host | Out-Null; exit 1 }
$env:PYTHONPATH = (Resolve-Path "..").Path
$env:PYTHONIOENCODING = "utf-8"

if (Test-Path "runs\STOP") { Write-Host "AVISO: existe runs\STOP, los Ojos se cierran al empezar. Bórralo para que miren." }
$host.UI.RawUI.WindowTitle = "Team 7 - Ojos (solo proponen; cerrar = parar)"
New-Item -ItemType Directory -Force -Path "runs" | Out-Null
$log = "runs\ojos-$(Get-Date -Format HHmm).log"   # un log por arranque
Add-Content -Path $log -Value "=== ojos, ticks=$Ticks, cada $Segundos s, $(Get-Date -Format HH:mm) ===" -Encoding utf8

$ErrorActionPreference = "Continue"
python -u programas\ojos.py --ticks $Ticks --segundos $Segundos | ForEach-Object { $_; Add-Content -Path $log -Value $_ -Encoding utf8 }
Write-Host "Los Ojos se han parado. Log: $log. Pulsa Enter para cerrar."
Read-Host | Out-Null
