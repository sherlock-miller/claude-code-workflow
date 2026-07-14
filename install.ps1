<#
.SYNOPSIS
Claude Code Workflow - One-Click Installer
Installs the complete Claude Code + DeepSeek workflow environment on Windows.

.DESCRIPTION
This script automates the entire setup:
- Environment detection
- Claude Code installation (if needed)
- Component selection (Edge CDP, Obsidian MCP, AutoCAD MCP, etc.)
- API key configuration (DeepSeek + Doubao/ARK)
- Template rendering (path adaptation)
- Dependency installation (npm + pip)
- Shell integration (.bashrc + .gitconfig)
- Verification

.EXAMPLE
powershell -ExecutionPolicy Bypass -File install.ps1
#>
param(
    [switch] $Yes,          # Skip all prompts, use defaults
    [switch] $Quick,        # Minimal install (core only)
    [switch] $Full,         # Install everything
    [switch] $TestMode,     # Install to temp dir for testing
    [switch] $Add,          # Incremental: add components to existing setup
    [string] $Component,    # Comma-separated components to install (with -Add)
    [string] $WorkspaceDir, # Pre-set workspace directory
    [string] $DeepSeekKey,  # Pre-set DeepSeek API key
    [string] $ArkKey        # Pre-set Doubao/ARK API key
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Load shared module
Import-Module "$ScriptDir\ClaudeWorkflow\ClaudeWorkflow.psm1" -Force

$VERSION = "1.0.0"

# ─── Test Mode: redirect everything to temp directory ───
if ($TestMode) {
    $TestRoot = Join-Path $env:TEMP "cwf-test-$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    $env:CWF_TEST_ROOT = $TestRoot
    $WorkspaceDir = Join-Path $TestRoot "workspace"
    New-Item -ItemType Directory -Force -Path $WorkspaceDir | Out-Null
    $DeepSeekKey = "sk-test-deepseek-key-for-validation"
    $ArkKey = "ark-test-key-for-validation"
    $Yes = $true
    $extraPaths = @()
    $obsidianVault = ""
    Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Magenta
    Write-Host "║     TEST MODE - Installing to temp directory                  ║" -ForegroundColor Magenta
    Write-Host "║     $TestRoot" -ForegroundColor DarkGray
    Write-Host "║     Your real ~/.claude/ will NOT be touched.                 ║" -ForegroundColor Magenta
    Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Magenta
}

# ════════════════════════════════════════════════════════════════
# 1. PREFLIGHT
# ════════════════════════════════════════════════════════════════

if (-not $TestMode) { Clear-Host }
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║     Claude Code Workflow Installer   v$VERSION                  ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

Write-Host "Step 1/5: Environment Detection" -ForegroundColor Yellow
Write-Host "─────────────────────────────────" -ForegroundColor Yellow

$envInfo = Get-EnvironmentInfo
Show-EnvironmentReport -Info $envInfo

if (-not $envInfo.IsWindows) {
    Write-Host "ERROR: This installer only supports Windows 10/11." -ForegroundColor Red
    exit 1
}

# Check for existing Claude Code installation
if (-not $envInfo.HasClaude) {
    if ($Add) {
        Write-Host "  [INFO] Claude Code not detected, but -Add mode only installs components." -ForegroundColor Yellow
        Write-Host "  Components will be copied; Claude Code is needed to use them." -ForegroundColor Yellow
    } elseif ($TestMode) {
        Write-Host "  [SKIP] Test mode: Claude Code install skipped" -ForegroundColor DarkGray
    } else {
        Write-Host "Claude Code is not installed. The installer can install it." -ForegroundColor Yellow
        if (-not $Yes) {
            $installCC = Read-Host "Install Claude Code globally? [Y/n]"
            if ($installCC -eq "n" -or $installCC -eq "N") {
                Write-Host "  [INFO] Skipping Claude Code install. Tools will be installed but need Claude Code to run." -ForegroundColor Yellow
            } else {
                Write-Host "  Installing Claude Code..." -ForegroundColor Cyan
                npm install -g @anthropic-ai/claude-code@2.1.153
                if ($LASTEXITCODE -ne 0) {
                    Write-Host "  [FAIL] Claude Code installation failed." -ForegroundColor Red
                } else {
                    Write-Host "  [OK] Claude Code installed"
                }
            }
        } else {
            Write-Host "  Installing Claude Code..." -ForegroundColor Cyan
            npm install -g @anthropic-ai/claude-code@2.1.153 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) { Write-Host "  [OK] Claude Code installed" }
        }
    }
}

# ════════════════════════════════════════════════════════════════
# 2. CONFIGURATION
# ════════════════════════════════════════════════════════════════

Write-Host ""
Write-Host "Step 2/5: Configuration" -ForegroundColor Yellow
Write-Host "─────────────────────────" -ForegroundColor Yellow

# ─── 2a. Component Selection ───

# Sub-component variables
$installVision = $installPythonTools  # initially follow python-tools
$installDoc = $installPythonTools
$installRag = $installPythonTools
$installWord = $installPythonTools
$installSession = $installPythonTools

# Parse -Component param (comma-separated)
$componentList = @()
if ($Component) {
    $componentList = $Component -split ',' | ForEach-Object { $_.Trim().ToLower() }
    Write-Host "  -Component specified: $($componentList -join ', ')" -ForegroundColor Cyan
}

if ($Quick) {
    $installEdgeCdp = $false
    $installObsidian = $false
    $installAutocad = $false
    $installMs365 = $false
    $installCliTools = $false
    $installPythonTools = $false
    $installVision = $false
    $installDoc = $false
    $installRag = $false
    $installWord = $false
    $installSession = $false
    $installSkills = $false
    $installNpmSkills = $false
} elseif ($componentList.Count -gt 0) {
    # -Component mode: only enable specified components (takes priority over TestMode)
    $installVision = ($componentList -contains "vision" -or $componentList -contains "python-tools")
    $installDoc = ($componentList -contains "doc" -or $componentList -contains "python-tools")
    $installRag = ($componentList -contains "rag" -or $componentList -contains "python-tools")
    $installWord = ($componentList -contains "word" -or $componentList -contains "python-tools")
    $installSession = ($componentList -contains "session" -or $componentList -contains "python-tools")
    $installEdgeCdp = ($componentList -contains "edge-cdp")
    $installObsidian = ($componentList -contains "obsidian")
    $installAutocad = ($componentList -contains "autocad")
    $installMs365 = ($componentList -contains "ms365")
    $installCliTools = ($componentList -contains "cli-tools")
    $installSkills = ($componentList -contains "skills")
    $installNpmSkills = ($componentList -contains "npm-skills")
    # If no python sub-components selected, don't treat python-tools as selected
    if (-not $installVision -and -not $installDoc -and -not $installRag -and -not $installWord -and -not $installSession) {
        $installPythonTools = $false
    } else {
        $installPythonTools = $true
    }
    Write-Host "  Selected:"
    Write-Host "    vision=$installVision doc=$installDoc rag=$installRag word=$installWord session=$installSession"
    Write-Host "    edge-cdp=$installEdgeCdp obsidian=$installObsidian autocad=$installAutocad ms365=$installMs365"
} elseif ($TestMode) {
    $installEdgeCdp = $false
    $installObsidian = $false
    $installAutocad = $false
    $installMs365 = $false
    $installCliTools = $false
    $installPythonTools = $true
    $installVision = $true
    $installDoc = $true
    $installRag = $true
    $installWord = $true
    $installSession = $true
    $installSkills = $true
    $installNpmSkills = $false
} elseif ($Full) {
    $installEdgeCdp = $true
    $installObsidian = $true
    $installAutocad = $true
    $installMs365 = $true
    $installCliTools = $true
    $installPythonTools = $true
    $installVision = $true
    $installDoc = $true
    $installRag = $true
    $installWord = $true
    $installSession = $true
    $installSkills = $true
    $installNpmSkills = $true
} elseif ($Add) {
    # Add mode: interactive selection of components to add
    Write-Host ""
    Write-Host "  Select components to ADD to your existing setup:" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Python Tools (sub-components):" -ForegroundColor Yellow
    $installVision = (Read-Host "    vision — Doubao image/PDF/PPTX recognition    [y/N]") -eq "y"
    $installDoc = (Read-Host "    doc — PDF/PPTX batch to Markdown               [y/N]") -eq "y"
    $installRag = (Read-Host "    rag — Chroma vector knowledge base              [y/N]") -eq "y"
    $installWord = (Read-Host "    word — Word document generation                 [y/N]") -eq "y"
    $installSession = (Read-Host "    session — session history management            [Y/n]") -ne "n"
    $installPythonTools = ($installVision -or $installDoc -or $installRag -or $installWord -or $installSession)
    Write-Host ""
    Write-Host "  MCP Servers:" -ForegroundColor Yellow
    $installEdgeCdp = (Read-Host "    edge-cdp — Edge browser automation              [y/N]") -eq "y"
    $installObsidian = (Read-Host "    obsidian — Obsidian note control                [y/N]") -eq "y"
    $installAutocad = (Read-Host "    autocad — AutoCAD COM control                   [y/N]") -eq "y"
    $installMs365 = (Read-Host "    ms365 — Microsoft 365 Graph API                 [y/N]") -eq "y"
    Write-Host ""
    Write-Host "  Other:" -ForegroundColor Yellow
    $installCliTools = (Read-Host "    cli-tools — starship/fzf/rg/eza/bat/delta       [y/N]") -eq "y"
    $installSkills = (Read-Host "    skills — batch/file/daily automation            [y/N]") -eq "y"
} else {
    Write-Host ""
    Write-Host "  Select components to install:" -ForegroundColor Cyan
    Write-Host ""
    $installEdgeCdp = (Read-Host "  Edge CDP MCP (browser automation)        [Y/n]") -ne "n"
    $installObsidian = (Read-Host "  Obsidian MCP (note-taking control)       [y/N]") -eq "y"
    $installAutocad = (Read-Host "  AutoCAD MCP (CAD automation)             [y/N]") -eq "y"
    $installMs365 = (Read-Host "  Microsoft 365 MCP (email/calendar/etc)   [Y/n]") -ne "n"
    $installCliTools = (Read-Host "  CLI Tools (starship/fzf/rg/eza/bat/...)  [Y/n]") -ne "n"
    $installPythonTools = (Read-Host "  Python Tools (vision/doc/word/RAG)       [Y/n]") -ne "n"
    $installSkills = (Read-Host "  Skills (batch/file/daily automation)     [Y/n]") -ne "n"
    $installNpmSkills = (Read-Host "  NPM Skills (huashu-nuwa/dot-skill)       [y/N]") -eq "y"
}

# ─── 2b. Paths ───
$defaultWorkspace = Join-Path $env:USERPROFILE "projects"
if (-not $WorkspaceDir) {
    $WorkspaceDir = if ($Yes) { $defaultWorkspace } else {
        $input = Read-Host "  Workspace directory [$defaultWorkspace]"
        if ($input) { $input } else { $defaultWorkspace }
    }
}
New-Item -ItemType Directory -Force -Path $WorkspaceDir | Out-Null

$installDir = Join-Path $env:USERPROFILE ".claude"

if ($TestMode) {
    $installDir = Join-Path $TestRoot ".claude"
}

if ($installObsidian -and -not $Yes) {
    $obsidianVault = Read-Host "  Obsidian vault path [skip if none]"
}

if (-not $Yes) {
    $extraPaths = @()
    $addMore = "y"
    while ($addMore -eq "y") {
        $p = Read-Host "  Add extra workspace path to whitelist? [enter to skip]"
        if ($p) { $extraPaths += $p } else { $addMore = "n" }
    }
}

# ─── 2c. API Keys ───
Write-Host ""
Write-Host "  ─── API Keys ───" -ForegroundColor Cyan

if (-not $DeepSeekKey) {
    Write-Host "  DeepSeek API Key (Required for Claude Code AI)" -ForegroundColor Yellow
    Write-Host "  Get your key at: https://platform.deepseek.com/api_keys"
    $DeepSeekKey = Read-Host "  API Key"
}
if (-not $DeepSeekKey) {
    Write-Host "  [WARN] No DeepSeek key provided. You can add it later in ~/.claude/.env" -ForegroundColor Yellow
}

if (-not $ArkKey -and $installVision) {
    Write-Host ""
    Write-Host "  Doubao/ARK API Key (Optional, for vision/image tools)" -ForegroundColor Yellow
    Write-Host "  Get your key at: https://console.volcengine.com/ark"
    Write-Host "  Press Enter to skip (vision tools won't work without it)"
    $ArkKey = Read-Host "  API Key"
}
if (-not $ArkKey) {
    Write-Host "  [INFO] No ARK key provided. Vision tools will need manual setup." -ForegroundColor DarkGray
}

# ─── 2d. Git Config ───
Write-Host ""
if (-not $Yes) {
    $gitName = Read-Host "  Git user name [enter to keep existing]"
    $gitEmail = Read-Host "  Git user email [enter to keep existing]"
}

# ════════════════════════════════════════════════════════════════
# 3. FILE LAYOUT
# ════════════════════════════════════════════════════════════════

Write-Host ""
Write-Host "Step 3/5: Installing Files" -ForegroundColor Yellow
Write-Host "────────────────────────────" -ForegroundColor Yellow

# Prepare install directory
if ((Test-Path $installDir) -and (-not $TestMode) -and (-not $Add)) {
    $existingVersion = "$installDir\.workflow-version"
    if (Test-Path $existingVersion) {
        Write-Host "  Existing claude-workflow installation detected. Upgrading..." -ForegroundColor Yellow
    } else {
        Write-Host "  ~/.claude/ exists but is not a claude-workflow installation." -ForegroundColor Yellow
        if (-not $Yes) {
            $choice = Read-Host "  Press Enter to continue (will back up existing files), or [A] to abort"
            if ($choice -eq "A") { Write-Host "Aborted."; exit 0 }
        }
    }
    $backupDir = "$installDir\backups\pre-upgrade"
    Backup-IfExists "$installDir\settings.json" $backupDir
    Backup-IfExists "$installDir\mcp.json" $backupDir
}

# ─── Config installation ───
if ($Add) {
    # Incremental mode: merge patches into existing config
    Write-Host "  Applying component patches to existing config..."
    New-Item -ItemType Directory -Force -Path $installDir | Out-Null
    $patchDir = "$ScriptDir\config\patches"

    if ($installEdgeCdp)   { Merge-SettingsJson -SettingsPath "$installDir\settings.json" -PatchPath "$patchDir\edge-cdp.json" }
    if ($installObsidian)  { Merge-SettingsJson -SettingsPath "$installDir\settings.json" -PatchPath "$patchDir\obsidian.json" }
    if ($installAutocad)   { Merge-SettingsJson -SettingsPath "$installDir\settings.json" -PatchPath "$patchDir\autocad.json" }
    if ($installMs365)     { Merge-SettingsJson -SettingsPath "$installDir\settings.json" -PatchPath "$patchDir\ms365.json" }
} else {
    # Fresh install: render templates from scratch
    Write-Host "  Rendering config templates..."
    $tokens = @{
        INSTALL_DIR        = $installDir
        WORKSPACE_DIR      = $WorkspaceDir
        USER_HOME          = $env:USERPROFILE
        PYTHON_PATH        = $envInfo.PythonPath
        OBSIDIAN_VAULT     = $(if ($obsidianVault) { $obsidianVault } else { "" })
        OBSIDIAN_ENABLED   = $installObsidian.ToString().ToLower()
        AUTOCAD_ENABLED    = $installAutocad.ToString().ToLower()
        MS365_ENABLED      = $installMs365.ToString().ToLower()
        EDGE_CDP_ENABLED   = $installEdgeCdp.ToString().ToLower()
        DEEPSEEK_API_KEY   = $(if ($DeepSeekKey) { $DeepSeekKey } else { "YOUR_DEEPSEEK_API_KEY_HERE" })
        ARK_API_KEY        = $(if ($ArkKey) { $ArkKey } else { "" })
        MS365_ACCOUNT      = "YOUR_M365_ACCOUNT_HERE"
        EXTRA_ALLOWED_PATHS = $extraPaths
    }
    Invoke-TemplateRendering -TemplateDir "$ScriptDir\config" -OutputDir $installDir -Tokens $tokens
}

# ─── Python tools (sub-component granularity) ───
if ($installPythonTools) {
    Write-Host "  Installing Python tools..."
    $pyToolsDest = "$installDir\tools"
    New-Item -ItemType Directory -Force -Path $pyToolsDest | Out-Null

    if ($installVision) {
        Copy-Item "$ScriptDir\tools\python\multimodal_vision.py" $pyToolsDest -Force
        Copy-Item "$ScriptDir\tools\python\clipboard_vision.py" $pyToolsDest -Force -ErrorAction SilentlyContinue
        Write-Host "    vision tools installed"
    }
    if ($installDoc) {
        Copy-Item "$ScriptDir\tools\python\doc_preprocessor.py" $pyToolsDest -Force
        Write-Host "    doc tools installed"
    }
    if ($installRag) {
        Copy-Item "$ScriptDir\tools\python\knowledge_base.py" $pyToolsDest -Force
        Write-Host "    rag tools installed"
    }
    if ($installWord) {
        Copy-Item "$ScriptDir\tools\python\word_builder.py" $pyToolsDest -Force
        Copy-Item "$ScriptDir\tools\python\word_omml.py" $pyToolsDest -Force -ErrorAction SilentlyContinue
        Write-Host "    word tools installed"
    }
    if ($installSession) {
        Copy-Item "$ScriptDir\tools\python\session_manager.py" $pyToolsDest -Force
        Copy-Item "$ScriptDir\tools\python\session_questions.py" $pyToolsDest -Force
        Write-Host "    session tools installed"
    }
}

# Copy Node.js tools (always useful)
Copy-Item "$ScriptDir\tools\node\*" "$installDir\tools\" -Force -ErrorAction SilentlyContinue

# Copy hooks
Write-Host "  Installing hooks..."
$hooksDest = "$installDir\hooks"
New-Item -ItemType Directory -Force -Path $hooksDest | Out-Null
Copy-Item "$ScriptDir\hooks\notify.ps1" $hooksDest -Force
# validate-path.ps1 is rendered from template, rename from template output
if (Test-Path "$installDir\validate-path.ps1") {
    Move-Item "$installDir\validate-path.ps1" "$hooksDest\validate-path.ps1" -Force
}

# Copy MCP servers
if ($installEdgeCdp) {
    Write-Host "  Installing Edge CDP MCP..."
    $edgeDest = "$installDir\edge-mcp"
    New-Item -ItemType Directory -Force -Path $edgeDest | Out-Null
    Copy-Item "$ScriptDir\mcp\edge-cdp\*" $edgeDest -Force -Exclude "node_modules"
    Push-Location $edgeDest
    Write-Host "    npm install..."
    npm install --silent 2>&1 | Out-Null
    Pop-Location
    Write-Host "    [OK] Edge CDP MCP ready"
}

if ($installObsidian) {
    Write-Host "  Installing Obsidian MCP..."
    $obsDest = "$installDir\obsidian-mcp"
    New-Item -ItemType Directory -Force -Path $obsDest | Out-Null
    Copy-Item "$ScriptDir\mcp\obsidian-mcp\*" $obsDest -Force -Exclude "node_modules"
    Push-Location $obsDest
    Write-Host "    npm install..."
    npm install --silent 2>&1 | Out-Null
    Pop-Location
    Write-Host "    [OK] Obsidian MCP ready"
}

if ($installAutocad) {
    Write-Host "  Installing AutoCAD MCP..."
    $acadDest = "$installDir\autocad-mcp"
    New-Item -ItemType Directory -Force -Path $acadDest | Out-Null
    Copy-Item "$ScriptDir\mcp\autocad-mcp\*" $acadDest -Force
    Write-Host "    [OK] AutoCAD MCP ready"
}

# Copy skills
if ($installSkills) {
    Write-Host "  Installing skills..."
    $skillsDest = "$installDir\skills"
    New-Item -ItemType Directory -Force -Path $skillsDest | Out-Null
    Copy-Item "$ScriptDir\skills\*" $skillsDest -Recurse -Force
    Write-Host "    [OK] Skills installed"
}

# Copy scripts (for update/verify)
Write-Host "  Installing maintenance scripts..."
$scriptsDest = "$installDir\scripts"
New-Item -ItemType Directory -Force -Path $scriptsDest | Out-Null
Copy-Item "$ScriptDir\scripts\*" $scriptsDest -Force -ErrorAction SilentlyContinue

# ════════════════════════════════════════════════════════════════
# 4. PYTHON DEPENDENCIES
# ════════════════════════════════════════════════════════════════

if ($installPythonTools) {
    Write-Host ""
    Write-Host "  Installing Python dependencies..." -ForegroundColor Cyan
    if ($envInfo.HasPython) {
        $reqPath = "$ScriptDir\tools\python\requirements.txt"
        if (Test-Path $reqPath) {
            $prevEAP = $ErrorActionPreference
            $ErrorActionPreference = "Continue"
            pip install -r $reqPath --quiet 2>&1 | ForEach-Object {
                if ($_ -match "ERROR|error:") { Write-Host "    $_" -ForegroundColor Red }
            }
            $ErrorActionPreference = $prevEAP
            if ($LASTEXITCODE -ne 0) {
                Write-Host "    [WARN] Some pip packages may have failed" -ForegroundColor Yellow
            } else {
                Write-Host "    [OK] Python dependencies installed"
            }
        }
    } else {
        Write-Host "    [WARN] Python not found, skipping pip install" -ForegroundColor Yellow
        Write-Host "    Install Python and run: pip install -r tools/python/requirements.txt"
    }
}

# ════════════════════════════════════════════════════════════════
# 5. SHELL INTEGRATION
# ════════════════════════════════════════════════════════════════

Write-Host ""
Write-Host "Step 4/5: Shell Integration" -ForegroundColor Yellow
Write-Host "─────────────────────────────" -ForegroundColor Yellow

if ($TestMode -or $Add) {
    Write-Host "  [SKIP] Shell integration skipped ($(if ($TestMode) { 'test mode' } else { 'add mode' }))" -ForegroundColor DarkGray
} else {
    # .bashrc
    $bashrcSnippet = Get-Content "$ScriptDir\config\bashrc-snippet.template" -Raw -Encoding UTF8
    Merge-Bashrc -SnippetContent $bashrcSnippet

    # .gitconfig
    if ($gitName -or $gitEmail) {
        Merge-Gitconfig -UserName $gitName -UserEmail $gitEmail
    } else {
        Write-Host "  [SKIP] Git config (keep existing)"
    }

    # Starship
    $starshipSrc = "$ScriptDir\config\starship.toml"
    $starshipDest = "$env:USERPROFILE\.config\starship.toml"
    if (Test-Path $starshipSrc) {
        New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.config" | Out-Null
        if (-not (Test-Path $starshipDest)) {
            Copy-Item $starshipSrc $starshipDest -Force
            Write-Host "  [OK] Starship config installed"
        }
    }
}

# ════════════════════════════════════════════════════════════════
# 6. SECRETS
# ════════════════════════════════════════════════════════════════

Write-Host ""
Write-Host "Step 5/5: Writing Secrets & Finalizing" -ForegroundColor Yellow
Write-Host "───────────────────────────────────────" -ForegroundColor Yellow

# Write .env
$envPath = "$installDir\.env"
$envContent = @"
# Claude Code Workflow Environment Variables
# Generated by install.ps1 v$VERSION on $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

ANTHROPIC_API_KEY=$DeepSeekKey
ARK_API_KEY=$ArkKey
EDGE_CDP_URL=http://127.0.0.1:9224
"@
Set-Content -Path $envPath -Value $envContent -Encoding UTF8
Protect-SecretFile $envPath
Write-Host "  [OK] API keys saved to $envPath"

# Write .workflow-version
$verInfo = @{
    package_version = $VERSION
    installed_at    = (Get-Date -Format "yyyy-MM-ddTHH:mm:ssK")
    components      = @{
        edge_cdp    = $installEdgeCdp
        obsidian    = $installObsidian
        autocad     = $installAutocad
        ms365       = $installMs365
        cli_tools   = $installCliTools
        python_tools = $installPythonTools
        skills      = $installSkills
        npm_skills  = $installNpmSkills
    }
}
$verInfo | ConvertTo-Json | Set-Content -Path "$installDir\.workflow-version" -Encoding UTF8

# Write path registry
Write-PathRegistry -RegistryPath "$installDir\installed_paths.json" -Data @{
    Version         = $VERSION
    InstallDir      = $installDir
    WorkspaceDir    = $WorkspaceDir
    PythonPath      = $envInfo.PythonPath
    ObsidianVault   = $(if ($obsidianVault) { $obsidianVault } else { "" })
    EdgeCdpEnabled  = $installEdgeCdp
    ObsidianEnabled = $installObsidian
    AutocadEnabled  = $installAutocad
    Ms365Enabled    = $installMs365
    CliToolsEnabled = $installCliTools
    PythonToolsEnabled = $installPythonTools
    SkillsEnabled   = $installSkills
}

# Install npm skills (npx skills add ...)
if ($installNpmSkills) {
    Write-Host "  Installing npm skills (huashu-nuwa, dot-skill)..."
    # Note: npx skills install requires Git Bash context, skip if in pure PowerShell
    Write-Host "  [INFO] Run these commands in Git Bash:"
    Write-Host "    npx skills add alchaincyf/nuwa-skill --all -g -y"
    Write-Host "    npx skills add titanwings/colleague-skill --all -g -y"
}

# ════════════════════════════════════════════════════════════════
# DONE
# ════════════════════════════════════════════════════════════════

if ($TestMode) {
    Write-Host ""
    Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Magenta
    Write-Host "║     TEST MODE - Installation Complete!                       ║" -ForegroundColor Magenta
    Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Magenta
    Write-Host ""
    Write-Host "  Test install directory: $installDir" -ForegroundColor Yellow
    Write-Host "  Test workspace:         $WorkspaceDir" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Files created:" -ForegroundColor Cyan
    Get-ChildItem $installDir -Recurse -File | ForEach-Object {
        $relPath = $_.FullName.Substring($installDir.Length + 1)
        Write-Host "    $relPath" -ForegroundColor DarkGray
    }
    $fileCount = (Get-ChildItem $installDir -Recurse -File).Count
    Write-Host ""
    Write-Host "  Total: $fileCount files installed to test directory" -ForegroundColor Green
    Write-Host ""
    Write-Host "  To clean up: Remove-Item -Recurse -Force '$TestRoot'" -ForegroundColor DarkGray
    Write-Host ""
    exit 0
}

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║              Installation Complete!                          ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "  Quick Start:" -ForegroundColor Cyan
Write-Host "  ───────────"
Write-Host "    1. Restart Git Bash (or run: source ~/.bashrc)"
Write-Host "    2. Type 'cc' to launch Claude Code"
Write-Host "    3. Type 'ccc' to resume last session"
Write-Host ""
Write-Host "  Verification:" -ForegroundColor Cyan
Write-Host "  ─────────────"
Write-Host "    claude-workflow verify"
Write-Host ""
Write-Host "  Management:" -ForegroundColor Cyan
Write-Host "  ───────────"
Write-Host "    claude-workflow status   - Quick health check"
Write-Host "    claude-workflow update   - Update to latest version"
Write-Host "    claude-workflow help     - Show all commands"
Write-Host ""

if ($installMs365) {
    Write-Host "  ⚠ Microsoft 365 Setup:" -ForegroundColor Yellow
    Write-Host "    Run: npx -y @softeria/ms-365-mcp-server --login"
    Write-Host "    Follow the browser login prompt to connect your M365 account."
    Write-Host ""
}

if ($installEdgeCdp) {
    Write-Host "  ⚠ Edge CDP Setup:" -ForegroundColor Yellow
    Write-Host "    First launch: run 'cc' and test the edge MCP tools."
    Write-Host "    The dedicated Edge instance will auto-start on port 9224."
    Write-Host ""
}

if (-not $installPythonTools) {
    Write-Host "  ℹ Python tools were not installed." -ForegroundColor DarkGray
    Write-Host "    You can re-run the installer with --Full to add them."
    Write-Host ""
}

Write-Host "  Install directory: $installDir" -ForegroundColor DarkGray
Write-Host "  Workspace:         $WorkspaceDir" -ForegroundColor DarkGray
Write-Host ""
