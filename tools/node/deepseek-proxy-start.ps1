# DeepSeek Proxy — Start script
# Auto-starts the message format proxy for DeepSeek Anthropic Gateway
#
# The proxy transforms Claude Code 2.1.154+ requests:
#   system role in messages[] → top-level system parameter
#
# Usage: .\deepseek-proxy-start.ps1

param(
    [int]$Port = 8787
)

$env:DEEPSEEK_PROXY_PORT = $Port

# Check if already running
$existing = Get-Process -Name "node" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -match "deepseek-proxy"
}
if ($existing) {
    Write-Host "[deepseek-proxy] Already running (PID: $($existing.Id))"
    exit 0
}

# Also check port
$portCheck = netstat -ano 2>$null | Select-String "127.0.0.1:$Port.*LISTENING"
if ($portCheck) {
    Write-Host "[deepseek-proxy] Port $Port already in use — assuming proxy is running"
    exit 0
}

$proxyScript = "$env:USERPROFILE\.claude\tools\deepseek-proxy.mjs"

Write-Host "[deepseek-proxy] Starting on port $Port..."
$process = Start-Process -FilePath "node" -ArgumentList "`"$proxyScript`"" -WindowStyle Hidden -PassThru

Start-Sleep -Seconds 1

if ($process.HasExited) {
    Write-Host "[deepseek-proxy] ERROR: Failed to start (exit code: $($process.ExitCode))"
    exit 1
}

Write-Host "[deepseek-proxy] Started (PID: $($process.Id))"
Write-Host "[deepseek-proxy] ANTHROPIC_BASE_URL should be: http://127.0.0.1:$Port"
