# =============================
# uninstall.ps1 - FIM Daemon Uninstaller
# =============================

$serviceName = "FIMDaemon"
$targetDir = "C:\Program Files\FIM-Daemon"
$nssmExe = Join-Path $targetDir "bin\nssm.exe"

Write-Host "Starting FIM Daemon uninstallation..."

# Stop and remove service
if (Get-Service -Name $serviceName -ErrorAction SilentlyContinue) {
    Write-Host "Stopping and removing service '$serviceName'..."
    
    # Stop the service if it's running
    $service = Get-Service -Name $serviceName
    if ($service.Status -eq 'Running') {
        Stop-Service $serviceName -Force
        Write-Host "Service stopped."
    }
    
    # Remove service using NSSM if available
    if (Test-Path $nssmExe) {
        & $nssmExe remove $serviceName confirm
        Write-Host "Service removed using NSSM."
    } else {
        # Fallback: Remove service using PowerShell
        Remove-Service -Name $serviceName
        Write-Host "Service removed using PowerShell."
    }
    
    # Wait a moment for service removal to complete
    Start-Sleep -Seconds 2
} else {
    Write-Host "Service '$serviceName' not found."
}

# Remove installation directory
if (Test-Path $targetDir) {
    Write-Host "Removing installation directory: $targetDir"
    try {
        Remove-Item $targetDir -Recurse -Force
        Write-Host "Installation directory removed successfully."
    } catch {
        Write-Warning "Failed to remove installation directory: $_"
        Write-Host "You may need to manually remove: $targetDir"
    }
} else {
    Write-Host "Installation directory not found: $targetDir"
}

# Clean up any remaining log files in temp or other locations
$tempLogs = @(
    "$env:TEMP\fim-daemon.log",
    "$env:TEMP\fim-daemon-error.log"
)

foreach ($logFile in $tempLogs) {
    if (Test-Path $logFile) {
        Remove-Item $logFile -Force -ErrorAction SilentlyContinue
        Write-Host "Removed log file: $logFile"
    }
}

Write-Host "Uninstallation complete!"
Write-Host "Note: Some files may require a system restart to be fully removed."
