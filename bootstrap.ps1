<#
.SYNOPSIS
Claude Code Workflow - One-Line Bootstrap
Usage: powershell -ExecutionPolicy Bypass -Command "iex (irm https://raw.githubusercontent.com/sherlock-miller/claude-code-workflow/main/bootstrap.ps1)"
#>
param(
    [switch] $Yes,     # Skip prompts
    [switch] $Full,    # Install all components
    [switch] $Quick,   # Minimal install
    [string] $Branch = "main"
)

$ErrorActionPreference = "Stop"
$RepoUrl = "https://github.com/sherlock-miller/claude-code-workflow.git"

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║     Claude Code Workflow - Bootstrap                        ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Check Git
try { git --version 2>$null | Out-Null } catch {
    Write-Host "ERROR: Git is not installed." -ForegroundColor Red
    Write-Host "Please install Git for Windows: https://git-scm.com/download/win"
    exit 1
}

# Check Node.js
try { node --version 2>$null | Out-Null } catch {
    Write-Host "ERROR: Node.js is not installed." -ForegroundColor Red
    Write-Host "Please install Node.js: https://nodejs.org/"
    exit 1
}

# Clone or update
$workDir = "$env:TEMP\claude-code-workflow"
if (Test-Path $workDir) {
    Write-Host "Updating installer..." -ForegroundColor Yellow
    Push-Location $workDir
    git pull origin $Branch 2>$null
    Pop-Location
} else {
    Write-Host "Downloading installer..." -ForegroundColor Yellow
    git clone -b $Branch $RepoUrl $workDir 2>&1 | Out-Null
    if (-not (Test-Path "$workDir\install.ps1")) {
        Write-Host "ERROR: Failed to clone repository." -ForegroundColor Red
        exit 1
    }
}

# Run installer
Write-Host "Starting installer..." -ForegroundColor Green
$installArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "$workDir\install.ps1")
if ($Yes) { $installArgs += "-Yes" }
if ($Full) { $installArgs += "-Full" }
if ($Quick) { $installArgs += "-Quick" }

powershell @installArgs

# Cleanup
Write-Host ""
Write-Host "Bootstrap complete. The installer files are at: $workDir" -ForegroundColor DarkGray
Write-Host "You can delete this directory if disk space is tight." -ForegroundColor DarkGray
