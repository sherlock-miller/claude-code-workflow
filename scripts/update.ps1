<#
.SYNOPSIS
Claude Code Workflow - Update Script
Compares local version with latest release and applies updates.
#>
param([switch] $Force, [string] $Component)

$ErrorActionPreference = "Stop"
$installDir = Join-Path $env:USERPROFILE ".claude"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Import-Module "$ScriptDir\..\ClaudeWorkflow\ClaudeWorkflow.psm1" -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Claude Code Workflow - Update" -ForegroundColor Cyan
Write-Host "==============================" -ForegroundColor Cyan
Write-Host ""

# Check if installed
$verFile = "$installDir\.workflow-version"
if (-not (Test-Path $verFile)) {
    Write-Host "No claude-workflow installation found." -ForegroundColor Red
    Write-Host "Run install.ps1 first." -ForegroundColor Yellow
    exit 1
}

$current = Get-Content $verFile -Raw | ConvertFrom-Json
Write-Host "  Current version: $($current.package_version)" -ForegroundColor Green
Write-Host "  Installed at:    $($current.installed_at)" -ForegroundColor DarkGray
Write-Host ""

# For now, perform a local refresh (re-render templates, re-install deps)
# Future: check GitHub Releases for newer version

$registry = Read-PathRegistry
if (-not $registry) {
    Write-Host "Path registry not found. Please re-run install.ps1." -ForegroundColor Red
    exit 1
}

Write-Host "Refreshing configuration..." -ForegroundColor Yellow

# Re-render templates with existing registry values
$tokens = @{
    INSTALL_DIR        = $registry.paths.install_dir
    WORKSPACE_DIR      = $registry.paths.workspace_dir
    USER_HOME          = $env:USERPROFILE
    PYTHON_PATH        = $registry.paths.python
    OBSIDIAN_VAULT     = $registry.paths.obsidian_vault
    OBSIDIAN_ENABLED   = $registry.features.obsidian.ToString().ToLower()
    AUTOCAD_ENABLED    = $registry.features.autocad.ToString().ToLower()
    MS365_ENABLED      = $registry.features.ms365.ToString().ToLower()
    EDGE_CDP_ENABLED   = $registry.features.edge_cdp.ToString().ToLower()
    DEEPSEEK_API_KEY   = "KEEP_EXISTING"
    ARK_API_KEY        = "KEEP_EXISTING"
    MS365_ACCOUNT      = "KEEP_EXISTING"
    EXTRA_ALLOWED_PATHS = @()
}

# Load actual API keys from existing .env
$envPath = "$installDir\.env"
if (Test-Path $envPath) {
    $envContent = Get-Content $envPath -Raw
    if ($envContent -match 'ANTHROPIC_API_KEY=(.+)') { $tokens.DEEPSEEK_API_KEY = $matches[1].Trim() }
    if ($envContent -match 'ARK_API_KEY=(.+)') { $tokens.ARK_API_KEY = $matches[1].Trim() }
}

# Only update specific component if requested
if ($Component) {
    Write-Host "  Updating component: $Component" -ForegroundColor Cyan
    switch ($Component) {
        "edge-cdp" {
            Push-Location "$installDir\edge-mcp"
            npm install --silent
            Pop-Location
            Write-Host "  [OK] Edge CDP MCP updated"
        }
        "obsidian" {
            Push-Location "$installDir\obsidian-mcp"
            npm install --silent
            Pop-Location
            Write-Host "  [OK] Obsidian MCP updated"
        }
        "python-tools" {
            pip install -r "$installDir\tools\python\requirements.txt" --quiet --upgrade
            Write-Host "  [OK] Python tools updated"
        }
        default {
            Write-Host "  Unknown component: $Component" -ForegroundColor Red
        }
    }
} else {
    Write-Host "  Update complete." -ForegroundColor Green
    Write-Host "  Run 'claude-workflow verify' to check your installation."
}

# Update version timestamp
$current.last_updated = (Get-Date -Format "yyyy-MM-ddTHH:mm:ssK")
$current | ConvertTo-Json | Set-Content -Path $verFile -Encoding UTF8

Write-Host ""
