<#
.SYNOPSIS
Claude Code Workflow - Verification & Diagnostics
#>
param([switch] $Quick)

$installDir = Join-Path $env:USERPROFILE ".claude"
Import-Module "$PSScriptRoot\..\ClaudeWorkflow\ClaudeWorkflow.psm1" -Force -ErrorAction SilentlyContinue

Clear-Host
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║     Claude Code Workflow - Verification Report               ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Date: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor DarkGray
Write-Host ""

# Load registry
$registry = Read-PathRegistry
if ($registry) {
    Write-Host "  Installed Version: $($registry.version)" -ForegroundColor DarkGray
    Write-Host "  Install Directory: $($registry.paths.install_dir)" -ForegroundColor DarkGray
    Write-Host ""
}

# ══════════════════════════════════════
# TIER 1: Environment Integrity
# ══════════════════════════════════════

Write-Host "  ── Tier 1: Environment ──" -ForegroundColor Cyan
Write-Host ""

$envInfo = Get-EnvironmentInfo
Write-CheckResult "Windows" $envInfo.IsWindows $envInfo.OS
Write-CheckResult "Git" $envInfo.HasGit
Write-CheckResult "Node.js" $envInfo.HasNode "v$($envInfo.NodeVersion)"
Write-CheckResult "Python" $envInfo.HasPython $envInfo.PythonVersion
Write-CheckResult "Claude Code" $envInfo.HasClaude $envInfo.ClaudeVersion

$hasRegistry = Test-Path "$installDir\installed_paths.json"
Write-CheckResult "Path Registry" $hasRegistry

$hasEnv = Test-Path "$installDir\.env"
Write-CheckResult ".env file" $hasEnv "(API keys)"

# ══════════════════════════════════════
# TIER 2: Component Availability
# ══════════════════════════════════════

Write-Host ""
Write-Host "  ── Tier 2: Components ──" -ForegroundColor Cyan
Write-Host ""

$configFiles = @(
    @{Path="$installDir\settings.json"; Name="settings.json"},
    @{Path="$installDir\mcp.json"; Name="mcp.json"},
    @{Path="$installDir\CLAUDE.md"; Name="CLAUDE.md"},
    @{Path="$installDir\hooks\notify.ps1"; Name="Hooks: notify.ps1"},
    @{Path="$installDir\hooks\validate-path.ps1"; Name="Hooks: validate-path.ps1"}
)

foreach ($f in $configFiles) {
    $exists = Test-Path $f.Path
    Write-CheckResult $f.Name $exists
}

# Check for template leftovers (unrendered {{TOKEN}})
if (Test-Path "$installDir\settings.json") {
    $content = Get-Content "$installDir\settings.json" -Raw
    $hasTemplates = $content -match '\{\{[A-Z_]+\}\}'
    Write-CheckResult "settings.json (no template leftovers)" (-not $hasTemplates)
}

Write-Host ""

# Edge CDP MCP
$edgeNodeModules = Test-Path "$installDir\edge-mcp\node_modules"
Write-CheckResult "Edge CDP MCP (deps)" $edgeNodeModules

# Obsidian MCP
$obsInstalled = Test-Path "$installDir\obsidian-mcp\server.cjs"
if ($obsInstalled) {
    $obsDeps = Test-Path "$installDir\obsidian-mcp\node_modules"
    Write-CheckResult "Obsidian MCP (deps)" $obsDeps
} else {
    Write-CheckResult "Obsidian MCP (not installed)" $true "(skip)"
}

# AutoCAD MCP
$acadInstalled = Test-Path "$installDir\autocad-mcp\autocad_mcp_server.py"
if ($acadInstalled) {
    Write-CheckResult "AutoCAD MCP" $true
} else {
    Write-CheckResult "AutoCAD MCP (not installed)" $true "(skip)"
}

# Python tools
$pyTools = Test-Path "$installDir\tools\multimodal_vision.py"
if ($pyTools) {
    Write-CheckResult "Python Tools" $true
    if ($envInfo.HasPython) {
        try {
            $null = python -c "import requests, PIL, fitz, pptx, docx, lxml" 2>&1
            Write-CheckResult "Python Dependencies (import)" ($LASTEXITCODE -eq 0)
        } catch {
            Write-CheckResult "Python Dependencies (import)" $false "some missing"
        }
    }
} else {
    Write-CheckResult "Python Tools (not installed)" $true "(skip)"
}

# Skills
$skillsDir = "$installDir\skills"
if (Test-Path $skillsDir) {
    $skillCount = (Get-ChildItem $skillsDir -Directory).Count
    Write-CheckResult "Skills" $true "$skillCount installed"
}

# ══════════════════════════════════════
# TIER 3: API Connectivity
# ══════════════════════════════════════

Write-Host ""
Write-Host "  ── Tier 3: Connectivity ──" -ForegroundColor Cyan
Write-Host ""

if (-not $Quick) {
    # DeepSeek API
    try {
        $dsResult = Invoke-RestMethod -Uri "https://api.deepseek.com/v1/models" `
            -Headers @{"Authorization"="Bearer $((Get-Content "$installDir\.env" -Raw | Select-String 'ANTHROPIC_API_KEY=(.+)').Matches.Groups[1].Value)"} `
            -TimeoutSec 10 -ErrorAction Stop
        Write-CheckResult "DeepSeek API" $true "reachable"
    } catch {
        Write-CheckResult "DeepSeek API" $false "unreachable or no key"
    }

    # Edge CDP
    try {
        $edgeResult = Invoke-RestMethod -Uri "http://127.0.0.1:9224/json/version" -TimeoutSec 5 -ErrorAction Stop
        Write-CheckResult "Edge CDP (:9224)" $true $edgeResult.Browser
    } catch {
        Write-CheckResult "Edge CDP (:9224)" $false "not running (ok if not started)"
    }

    # Obsidian CDP
    if ($obsInstalled) {
        try {
            $obsResult = Invoke-RestMethod -Uri "http://127.0.0.1:9225/json/version" -TimeoutSec 5 -ErrorAction Stop
            Write-CheckResult "Obsidian CDP (:9225)" $true
        } catch {
            Write-CheckResult "Obsidian CDP (:9225)" $false "not running"
        }
    }
} else {
    Write-Host "  [Quick mode: Connectivity checks skipped]" -ForegroundColor DarkGray
}

# ══════════════════════════════════════
# TIER 4: Shell Integration
# ══════════════════════════════════════

Write-Host ""
Write-Host "  ── Tier 4: Shell Integration ──" -ForegroundColor Cyan
Write-Host ""

$bashrcPath = "$env:USERPROFILE\.bashrc"
if (Test-Path $bashrcPath) {
    $bashrcContent = Get-Content $bashrcPath -Raw
    $hasWorkflow = $bashrcContent -match "# >>> claude-workflow begin"
    Write-CheckResult ".bashrc integration" $hasWorkflow
}

$localBin = "$env:USERPROFILE\.local\bin"
$hasLocalBin = Test-Path $localBin
Write-CheckResult "~/.local/bin/" $hasLocalBin "PATH extension"

# Check specific CLI tools if installed
if ($hasLocalBin) {
    $cliTools = @("starship.exe", "fzf.exe", "zoxide.exe", "rg.exe", "eza.exe", "bat.exe", "delta.exe")
    foreach ($t in $cliTools) {
        $exists = Test-Path (Join-Path $localBin $t)
        if ($exists) { Write-CheckResult "  $t" $true } else { Write-CheckResult "  $t" $false "not installed" }
    }
}

# ══════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║              Verification Complete                           ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "  Quick start:" -ForegroundColor Cyan
Write-Host "    cc          → Launch Claude Code"
Write-Host "    ccc         → Resume last session"
Write-Host "    claude-workflow verify  → Re-run this check"
Write-Host ""
