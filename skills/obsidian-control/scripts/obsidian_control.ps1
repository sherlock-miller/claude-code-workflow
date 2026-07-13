param(
  [string]$Action = "launch",
  [string]$VaultPath = "",
  [int]$DebugPort = 9223,
  [int]$TimeoutSeconds = 30,
  [switch]$ForceRestart
)

$script:DefaultVault = "E:\claude code\codex的obsidian经验\obsidian-vault"

if (-not $VaultPath) { $VaultPath = $DefaultVault }

function Find-ObsidianExe {
  $candidates = @(
    "$env:LOCALAPPDATA\Obsidian\Obsidian.exe",
    "$env:LOCALAPPDATA\obsidian\Obsidian.exe",
    "$env:LOCALAPPDATA\Programs\Obsidian\Obsidian.exe",
    "$env:APPDATA\Obsidian\Obsidian.exe",
    "${env:ProgramFiles}\Obsidian\Obsidian.exe",
    "${env:ProgramFiles(x86)}\Obsidian\Obsidian.exe",
    "$env:USERPROFILE\scoop\apps\obsidian\current\Obsidian.exe",
    (Get-Command obsidian -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source)
  )

  foreach ($c in $candidates) {
    if ($c -and (Test-Path $c -PathType Leaf)) { return $c }
  }

  # Search broader
  $searchPaths = @(
    "$env:LOCALAPPDATA",
    "$env:APPDATA",
    "$env:USERPROFILE\scoop"
  )
  foreach ($sp in $searchPaths) {
    if (-not (Test-Path $sp)) { continue }
    $found = Get-ChildItem -Path $sp -Filter "Obsidian.exe" -Recurse -Depth 4 -ErrorAction SilentlyContinue |
      Select-Object -First 1 -ExpandProperty FullName
    if ($found) { return $found }
  }

  throw "Obsidian.exe not found. Please install Obsidian or set OBSIDIAN_EXE environment variable."
}

function Stop-ObsidianProcesses {
  Get-Process -Name "Obsidian" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
  Start-Sleep -Seconds 2
}

function Test-CdpAvailable {
  param([int]$Port, [int]$Retries = 10)

  for ($i = 0; $i -lt $Retries; $i++) {
    try {
      $req = [System.Net.Http.HttpClient]::new()
      $req.Timeout = [TimeSpan]::FromSeconds(3)
      $resp = $req.GetAsync("http://127.0.0.1:${Port}/json/version").Result
      if ($resp.IsSuccessStatusCode) {
        $body = $resp.Content.ReadAsStringAsync().Result
        $json = $body | ConvertFrom-Json
        return @{ available = $true; url = "http://127.0.0.1:${Port}"; browser = $json.Browser }
      }
    } catch { }
    Start-Sleep -Seconds 1
  }
  return @{ available = $false; url = "http://127.0.0.1:${Port}" }
}

function Launch-Obsidian {
  $exe = Find-ObsidianExe
  $vaultPathResolved = (Resolve-Path $VaultPath -ErrorAction SilentlyContinue).Path
  if (-not $vaultPathResolved) { $vaultPathResolved = $VaultPath }

  if ($ForceRestart) { Stop-ObsidianProcesses }

  $cdpResult = Test-CdpAvailable -Port $DebugPort -Retries 2
  if ($cdpResult.available) {
    return @{
      action = "launch"
      vaultPath = $vaultPathResolved
      cdpUrl = "http://127.0.0.1:${DebugPort}"
      cdpAvailable = $true
      forceRestart = $ForceRestart
      message = "Obsidian CDP is already available on port ${DebugPort}."
    } | ConvertTo-Json -Compress
  }

  Write-Error "Starting Obsidian: $exe --remote-debugging-port=${DebugPort}"
  $proc = Start-Process -FilePath $exe `
    -ArgumentList "--remote-debugging-port=${DebugPort}" `
    -PassThru -WindowStyle Normal

  $cdpResult = Test-CdpAvailable -Port $DebugPort -Retries $TimeoutSeconds
  if (-not $cdpResult.available) {
    throw "Obsidian started but CDP not available on port ${DebugPort} after ${TimeoutSeconds}s"
  }

  return @{
    action = "launch"
    vaultPath = $vaultPathResolved
    cdpUrl = "http://127.0.0.1:${DebugPort}"
    cdpAvailable = $true
    forceRestart = $ForceRestart
    processId = $proc.Id
  } | ConvertTo-Json -Compress
}

switch ($Action) {
  "launch" {
    Launch-Obsidian
  }
  default {
    Write-Error "Unknown action: $Action. Valid: launch"
    exit 1
  }
}
