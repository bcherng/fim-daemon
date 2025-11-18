# =============================
# uninstall.ps1 - FIM Daemon Uninstaller
# =============================

$serviceName = "FIMDaemon"
$targetDir = "C:\Program Files\FIM-Daemon"
$nssmExe = Join-Path $targetDir "bin\nssm.exe"

# Stop and remove service
if (Get-Service -Name $serviceName -ErrorAction SilentlyContinue) {
    Write-Host "Stopping and removing service '$serviceName'..."
    Stop-Service $serviceName -Force
    if (Test-Path $nssmExe) {
        & $nssmExe remove $serviceName confirm
    } else {
        Remove-Service -Name $serviceName
    }
}

# Remove installation directory
if (Test-Path $targetDir) {
    Write-Host "Removing installation directory: $targetDir"
    Remove-Item $targetDir -Recurse -Force
}

Write-Host "Uninstallation complete!"