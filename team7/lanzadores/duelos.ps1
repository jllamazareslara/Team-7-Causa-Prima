# Lanza la Duelista (duelos.py) en esta ventana, independiente de Claude.
#   .\lanzadores\duelos.ps1               EN SECO, 3 ticks: solo mira, no manda ni acepta nada (prueba)
#   .\lanzadores\duelos.ps1 -Ticks 0      EN SECO sin fin
#   .\lanzadores\duelos.ps1 -Live         EN VIVO, sin fin (pide escribir SI antes de empezar)
# La clave se lee de bazaar-kit\.env (o de la variable BAZAAR_KEY) y no se escribe en ningún sitio.
# Parar: cerrar esta ventana, Ctrl + C, o crear el archivo runs\STOP (el Guardia deja de firmar duelos).
param(
    [switch]$Live,
    [int]$Ticks = -1
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
if ($Ticks -lt 0) { $Ticks = if ($Live) { 0 } else { 3 } }

$modo = if ($Live) { "EN VIVO" } else { "EN SECO" }
if (Test-Path "runs\STOP") { Write-Host "AVISO: existe runs\STOP, el Guardia no firmará ningún duelo." }
if ($Live) {
    Write-Host "Vas a jugar los duelos EN VIVO. Comprueba que nadie más juega duelos con esta clave (play.py duel, otro ordenador)."
    if ((Read-Host "Escribe SI para empezar") -ne "SI") { Write-Host "No se lanza."; exit 0 }
}
$host.UI.RawUI.WindowTitle = "Team 7 - Duelista $modo (cerrar = parar)"
New-Item -ItemType Directory -Force -Path "runs" | Out-Null
$log = "runs\duelos-$($modo -replace ' ', '-')-$(Get-Date -Format HHmm).log"   # un log por arranque
Add-Content -Path $log -Value "=== duelos $modo, ticks=$Ticks, $(Get-Date -Format HH:mm) ===" -Encoding utf8

$argumentos = @("-u", "programas\duelos.py", "--ticks", "$Ticks")
if ($Live) { $argumentos += "--live" }
$ErrorActionPreference = "Continue"
python @argumentos | ForEach-Object { $_; Add-Content -Path $log -Value $_ -Encoding utf8 }
Write-Host "La Duelista se ha parado. Log: $log. Pulsa Enter para cerrar."
Read-Host | Out-Null
