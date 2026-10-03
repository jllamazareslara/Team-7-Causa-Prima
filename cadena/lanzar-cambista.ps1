# Lanza el Cambista EN VIVO en esta ventana, independiente de Claude.
# La clave se lee de bazaar-kit\.env y no se escribe en ningún sitio.
# Parar: cerrar esta ventana, o crear el archivo runs\STOP.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$kit = Join-Path $PSScriptRoot "..\..\bazaar-kit\.env"
foreach ($l in Get-Content $kit) {
    if ($l -match '^\s*(BAZAAR_KEY|BAZAAR_URL)\s*=\s*(.+?)\s*$') { Set-Item -Path ("env:" + $Matches[1]) -Value $Matches[2] }
}
$env:PYTHONPATH = (Resolve-Path "..").Path
$env:PYTHONIOENCODING = "utf-8"
$host.UI.RawUI.WindowTitle = "Team 7 - Cambista EN VIVO (cerrar = parar)"
$log = "runs\en-vivo-$(Get-Date -Format HHmm).log"   # un log por arranque: el anterior puede seguir bloqueado
Add-Content -Path $log -Value "=== relanzado en ventana propia $(Get-Date -Format HH:mm) ===" -Encoding utf8
$ErrorActionPreference = "Continue"
python -u jugar.py --live | ForEach-Object { $_; Add-Content -Path $log -Value $_ -Encoding utf8 }
Write-Host "El Cambista se ha parado. Pulsa Enter para cerrar."
Read-Host | Out-Null
