# Claude Code Workflow - Shared PowerShell Module
# Functions used by install.ps1, update.ps1, and verify.ps1

# ─── Template Rendering ───

function Invoke-TemplateRendering {
    <#
    .SYNOPSIS
    Render .template files by replacing {{TOKEN}} placeholders with actual values.
    .PARAMETER TemplateDir
    Directory containing .template files
    .PARAMETER OutputDir
    Directory to write rendered files to
    .PARAMETER Tokens
    Hashtable of token names to values
    #>
    param(
        [Parameter(Mandatory)] [string] $TemplateDir,
        [Parameter(Mandatory)] [string] $OutputDir,
        [Parameter(Mandatory)] [hashtable] $Tokens
    )

    New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

    Get-ChildItem -Path $TemplateDir -Recurse -File | ForEach-Object {
        $content = Get-Content $_.FullName -Raw -Encoding UTF8
        $relativePath = $_.FullName.Substring($TemplateDir.Length).TrimStart("\", "/")

        # Simple token replacement ({{TOKEN}} → value)
        foreach ($key in $Tokens.Keys) {
            $placeholder = "{{$key}}"
            $value = if ($null -ne $Tokens[$key]) { $Tokens[$key] } else { "" }
            $content = $content.Replace($placeholder, $value)
        }

        # Handle conditional blocks: {{#if TOKEN}}content{{/if}}
        $content = [regex]::Replace($content,
            '\{\{#if\s+(\w+)\}\}(.*?)\{\{/if\}\}',
            {
                param($m)
                $varName = $m.Groups[1].Value
                $val = $Tokens[$varName]
                if ($Tokens.ContainsKey($varName) -and $val -and $val -ne "false") {
                    return $m.Groups[2].Value
                }
                return ""
            },
            [System.Text.RegularExpressions.RegexOptions]::Singleline
        )

        # Handle each blocks: {{#each TOKEN}}...{{/each}}
        # (simplified - does text substitution per iteration)
        $content = [regex]::Replace($content,
            '\{\{#each\s+(\w+)\}\}(.*?)\{\{/each\}\}',
            {
                param($m)
                $varName = $m.Groups[1].Value
                $template = $m.Groups[2].Value
                if ($Tokens.ContainsKey($varName) -and $Tokens[$varName] -is [array]) {
                    $result = ""
                    foreach ($item in $Tokens[$varName]) {
                        $result += $template.Replace("{{this}}", $item)
                    }
                    return $result
                }
                return ""
            },
            [System.Text.RegularExpressions.RegexOptions]::Singleline
        )

        # Remove .template suffix from output filename
        $outPath = $relativePath -replace '\.template$', ''
        $outFull = Join-Path $OutputDir $outPath
        $outParent = Split-Path $outFull -Parent
        if ($outParent) { New-Item -ItemType Directory -Force -Path $outParent | Out-Null }
        Set-Content -Path $outFull -Value $content -Encoding UTF8 -NoNewline
    }
    Write-Host "  [OK] Rendered templates from $TemplateDir to $OutputDir"
}

# ─── Environment Detection ───

function Get-EnvironmentInfo {
    <#
    .SYNOPSIS
    Detect the user's environment: OS, tools, paths.
    .DESCRIPTION
    Returns a hashtable with all detected info.
    #>
    $info = @{
        OS         = [System.Environment]::OSVersion.VersionString
        IsWindows  = $true  # always true for this workflow
        UserHome   = $env:USERPROFILE
        UserName   = $env:USERNAME
        ComputerName = $env:COMPUTERNAME
        HasGit     = $false
        HasNode    = $false
        NodeVersion = ""
        HasPython  = $false
        PythonPath = ""
        PythonVersion = ""
        HasClaude  = $false
        ClaudeVersion = ""
    }

    # Git
    try { $null = git --version 2>$null; $info.HasGit = $true } catch {}

    # Node.js
    try {
        $nodeVer = node --version 2>$null
        if ($nodeVer) { $info.HasNode = $true; $info.NodeVersion = $nodeVer.TrimStart('v') }
    } catch {}

    # Python
    try {
        $pyPath = (Get-Command python -ErrorAction Stop).Source
        $pyVer = python --version 2>&1
        $info.HasPython = $true
        $info.PythonPath = $pyPath
        if ($pyVer -match '(\d+\.\d+\.\d+)') { $info.PythonVersion = $matches[1] }
    } catch {}

    # Claude Code
    try {
        $ccVer = npx @anthropic-ai/claude-code --version 2>$null
        if ($LASTEXITCODE -eq 0 -and $ccVer) {
            $info.HasClaude = $true
            $info.ClaudeVersion = $ccVer.Trim()
        }
    } catch {
        try {
            $ccVer = claude --version 2>$null
            if ($LASTEXITCODE -eq 0) { $info.HasClaude = $true; $info.ClaudeVersion = $ccVer.Trim() }
        } catch {}
    }

    return $info
}

function Show-EnvironmentReport {
    param([hashtable] $Info)
    Write-Host ""
    Write-Host "  Environment Detection:" -ForegroundColor Cyan
    Write-Host "  ─────────────────────"
    $status = if ($info.IsWindows) { "PASS" } else { "FAIL" }
    Write-Host "  OS:       Windows ($($info.OS))" -ForegroundColor $(if ($info.IsWindows) { "Green" } else { "Red" })
    Write-Host "  Git:      $(if ($info.HasGit) { 'Found' } else { 'NOT FOUND' })" -ForegroundColor $(if ($info.HasGit) { "Green" } else { "Red" })
    Write-Host "  Node.js:  $(if ($info.HasNode) { "v$($info.NodeVersion)" } else { 'NOT FOUND' })" -ForegroundColor $(if ($info.HasNode) { "Green" } else { "Yellow" })
    Write-Host "  Python:   $(if ($info.HasPython) { "$($info.PythonVersion) ($($info.PythonPath))" } else { 'NOT FOUND' })" -ForegroundColor $(if ($info.HasPython) { "Green" } else { "Yellow" })
    Write-Host "  Claude:   $(if ($info.HasClaude) { "v$($info.ClaudeVersion)" } else { 'NOT INSTALLED' })" -ForegroundColor $(if ($info.HasClaude) { "Green" } else { "Yellow" })
    Write-Host ""
}

# ─── Shell Integration ───

function Merge-Bashrc {
    param(
        [string] $BashrcPath = "$env:USERPROFILE\.bashrc",
        [string] $SnippetContent
    )
    $marker_begin = "# >>> claude-workflow begin"
    $marker_end = "# <<< claude-workflow end"

    $existing = ""
    if (Test-Path $BashrcPath) {
        $existing = Get-Content $BashrcPath -Raw -Encoding UTF8
    }

    # Remove old block if exists
    if ($existing -match [regex]::Escape($marker_begin)) {
        $existing = $existing -replace "(?ms)$([regex]::Escape($marker_begin)).*$([regex]::Escape($marker_end))\r?\n?", ""
    }

    # Append new block
    $newContent = $existing.TrimEnd() + "`n`n$marker_begin`n$SnippetContent`n$marker_end`n"
    Set-Content -Path $BashrcPath -Value $newContent -Encoding UTF8 -NoNewline
    Write-Host "  [OK] .bashrc updated"
}

function Merge-Gitconfig {
    param(
        [string] $GitconfigPath = "$env:USERPROFILE\.gitconfig",
        [string] $UserName,
        [string] $UserEmail
    )
    git config --global user.name $UserName 2>$null
    git config --global user.email $UserEmail 2>$null
    git config --global core.autocrlf false
    git config --global http.postBuffer 524288000
    git config --global safe.directory "*"
    Write-Host "  [OK] .gitconfig updated"
}

# ─── Path Registry ───

function Write-PathRegistry {
    param(
        [string] $RegistryPath = "$env:USERPROFILE\.claude\installed_paths.json",
        [hashtable] $Data
    )
    $ov = if ($Data.ObsidianVault) { $Data.ObsidianVault } else { "" }
    $registry = @{
        version    = $Data.Version
        created_at = (Get-Date -Format "yyyy-MM-ddTHH:mm:ssK")
        paths      = @{
            install_dir     = $Data.InstallDir
            workspace_dir   = $Data.WorkspaceDir
            python          = $Data.PythonPath
            obsidian_vault  = $ov
        }
        features   = @{
            edge_cdp    = $Data.EdgeCdpEnabled
            obsidian    = $Data.ObsidianEnabled
            autocad     = $Data.AutocadEnabled
            ms365       = $Data.Ms365Enabled
            cli_tools   = $Data.CliToolsEnabled
            python_tools = $Data.PythonToolsEnabled
            skills      = $Data.SkillsEnabled
        }
    }
    $parent = Split-Path $RegistryPath -Parent
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $registry | ConvertTo-Json -Depth 4 | Set-Content -Path $RegistryPath -Encoding UTF8
    Write-Host "  [OK] Path registry saved"
}

function Read-PathRegistry {
    param([string] $RegistryPath = "$env:USERPROFILE\.claude\installed_paths.json")
    if (-not (Test-Path $RegistryPath)) { return $null }
    return Get-Content $RegistryPath -Raw -Encoding UTF8 | ConvertFrom-Json
}

# ─── Verification Helpers ───

function Test-Command {
    param([string] $Command, [string] $Args = "--version")
    try {
        $result = & $Command $Args 2>&1
        return ($LASTEXITCODE -eq 0)
    } catch { return $false }
}

function Write-CheckResult {
    param([string] $Label, [bool] $Passed, [string] $Detail = "")
    $icon = if ($Passed) { "[PASS]" } else { "[FAIL]" }
    $color = if ($Passed) { "Green" } else { "Red" }
    $line = "  $icon $Label"
    if ($Detail) { $line += "  ($Detail)" }
    Write-Host $line -ForegroundColor $color
}

# ─── Utility ───

function Protect-SecretFile {
    param([string] $Path)
    if (Test-Path $Path) {
        icacls $Path /inheritance:r /grant "${env:USERNAME}:R" 2>$null | Out-Null
    }
}

function Backup-IfExists {
    param([string] $Path, [string] $BackupDir)
    if (Test-Path $Path) {
        $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $backupPath = Join-Path $BackupDir "$(Split-Path $Path -Leaf).backup.$timestamp"
        New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
        Copy-Item $Path $backupPath -Force
        Write-Host "  [BACKUP] $Path → $backupPath"
    }
}

# ─── Config Merging (v1.1) ───

function Merge-Hashtable {
    <#
    .SYNOPSIS
    Deep merge two hashtables. Override values from $Override are added or replace.
    Arrays are merged with dedup.
    #>
    param(
        [hashtable] $Base,
        [hashtable] $Override
    )
    $result = @{}
    # Copy base
    foreach ($key in $Base.Keys) { $result[$key] = $Base[$key] }
    # Merge override
    foreach ($key in $Override.Keys) {
        if (-not $result.ContainsKey($key)) {
            $result[$key] = $Override[$key]
        } elseif ($result[$key] -is [hashtable] -and $Override[$key] -is [hashtable]) {
            $result[$key] = Merge-Hashtable -Base $result[$key] -Override $Override[$key]
        } elseif ($result[$key] -is [array] -and $Override[$key] -is [array]) {
            $merged = [System.Collections.ArrayList]::new()
            foreach ($item in $result[$key]) { if ($item -notin $merged) { $null = $merged.Add($item) } }
            foreach ($item in $Override[$key]) { if ($item -notin $merged) { $null = $merged.Add($item) } }
            $result[$key] = $merged.ToArray()
        } else {
            $result[$key] = $Override[$key]
        }
    }
    return $result
}

function Merge-SettingsJson {
    <#
    .SYNOPSIS
    Merge a component patch into existing settings.json.
    Adds permissions and MCP servers without overwriting existing config.
    #>
    param(
        [string] $SettingsPath = "$env:USERPROFILE\.claude\settings.json",
        [string] $PatchPath
    )
    if (-not (Test-Path $SettingsPath)) {
        Write-Host "    [SKIP] No existing settings.json to merge into" -ForegroundColor Yellow
        return
    }
    if (-not (Test-Path $PatchPath)) {
        Write-Host "    [SKIP] Patch not found: $PatchPath" -ForegroundColor Yellow
        return
    }
    try {
        $existing = Get-Content $SettingsPath -Raw -Encoding UTF8 | ConvertFrom-Json -AsHashtable -Depth 10
        $patch = Get-Content $PatchPath -Raw -Encoding UTF8 | ConvertFrom-Json -AsHashtable -Depth 10
        $merged = Merge-Hashtable -Base $existing -Override $patch
        $json = $merged | ConvertTo-Json -Depth 10
        Set-Content $SettingsPath -Value $json -Encoding UTF8
        Write-Host "    [OK] Merged $(Split-Path $PatchPath -Leaf) into settings.json"
    } catch {
        Write-Host "    [WARN] Failed to merge patch: $_" -ForegroundColor Yellow
    }
}

function Merge-McpJson {
    <#
    .SYNOPSIS
    Add MCP server entry to existing mcp.json without removing existing entries.
    #>
    param(
        [string] $McpPath = "$env:USERPROFILE\.claude\mcp.json",
        [string] $ServerId,
        [hashtable] $ServerConfig
    )
    if (-not (Test-Path $McpPath)) { return }
    try {
        $existing = Get-Content $McpPath -Raw -Encoding UTF8 | ConvertFrom-Json -AsHashtable -Depth 5
        if (-not $existing.ContainsKey("mcpServers")) { $existing["mcpServers"] = @{} }
        $servers = $existing["mcpServers"]
        if ($servers -is [hashtable] -and -not $servers.ContainsKey($ServerId)) {
            $servers[$ServerId] = $ServerConfig
            $existing | ConvertTo-Json -Depth 5 | Set-Content $McpPath -Encoding UTF8
            Write-Host "    [OK] Added '$ServerId' to mcp.json"
        } else {
            Write-Host "    [SKIP] '$ServerId' already in mcp.json"
        }
    } catch {
        Write-Host "    [WARN] Failed to update mcp.json: $_" -ForegroundColor Yellow
    }
}

Export-ModuleMember -Function @(
    "Invoke-TemplateRendering",
    "Get-EnvironmentInfo",
    "Show-EnvironmentReport",
    "Merge-Bashrc",
    "Merge-Gitconfig",
    "Write-PathRegistry",
    "Read-PathRegistry",
    "Test-Command",
    "Write-CheckResult",
    "Protect-SecretFile",
    "Backup-IfExists",
    "Merge-Hashtable",
    "Merge-SettingsJson",
    "Merge-McpJson"
)
