$ServerUrl = "http://localhost:3000"
$Endpoint = "$ServerUrl/api/clients/verify"

Write-Host "=== FIM Security Demo: Server Rate Limiting ===" -ForegroundColor Cyan
Write-Host "This script will send 120 requests to the server to trigger the 100-request limit."

$SuccessCount = 0
$BlockedCount = 0

for ($i = 1; $i -le 120; $i++) {
    try {
        $response = Invoke-WebRequest -Uri $Endpoint -Method Post -TimeoutSec 2 -ErrorAction Stop
        $SuccessCount++
        if ($i % 20 -eq 0) { Write-Host "Sent $i requests..." }
    }
    catch {
        $StatusCode = $_.Exception.Response.StatusCode.value__
        if ($StatusCode -eq 429) {
            Write-Host "`n[!] RATE LIMITED at request $i (Status 429)" -ForegroundColor Yellow
            $BlockedCount = 120 - $i + 1
            break
        }
        else {
            Write-Host "Error at request $i: $_" -ForegroundColor Red
            break
        }
    }
}

Write-Host "`n--- Demo Results ---"
Write-Host "Successful Requests: $SuccessCount"
Write-Host "Blocked Requests (Rate Limited): $BlockedCount"

if ($BlockedCount -gt 0) {
    Write-Host "`nSUCCESS: Server rate limiting is active." -ForegroundColor Green
} else {
    Write-Host "`nFAILURE: Server did not rate limit requests." -ForegroundColor Red
}
