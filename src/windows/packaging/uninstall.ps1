# =============================
# uninstall.ps1 - FIM Daemon Uninstaller
# =============================

$targetDir = "C:\Program Files\FIM-Daemon"
$serviceName = "FIMDaemon"
$nssmExe = Join-Path $targetDir "bin\nssm.exe"

# Check if NSSM exists
if (-not (Test-Path $nssmExe)) {
    Write-Error "NSSM not found at: $nssmExe"
    exit 1
}

# Check if service exists
$existingService = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
if ($existingService) {
    Write-Host "Stopping service '$serviceName'..."
    Stop-Service $serviceName -Force
    Start-Sleep -Seconds 2

    Write-Host "Removing service '$serviceName'..."
    & $nssmExe remove $serviceName confirm
    Start-Sleep -Seconds 1

    Write-Host "Service '$serviceName' removed successfully."
} else {
    Write-Host "Service '$serviceName' does not exist. Nothing to remove."
}
Write-Host "Uninstallation complete."
