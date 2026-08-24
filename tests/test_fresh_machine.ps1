[CmdletBinding()]
param()

Set-StrictMode -Version 3.0
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$entry = Join-Path $root 'bmcpw.ps1'
$python = $env:BMCPW_PYTHON
if (-not $python) {
    $pythonCommand = Get-Command python.exe, python, py.exe, py -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($pythonCommand) { $python = $pythonCommand.Source }
}
if (-not $python) { throw 'Python is required for the fresh-machine test.' }

$temp = Join-Path ([System.IO.Path]::GetTempPath()) ('bmcpw-fresh-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $temp -Force | Out-Null
$oldPython = $env:BMCPW_PYTHON
$oldCodexHome = $env:CODEX_HOME
$oldLocalAppData = $env:LOCALAPPDATA
$oldBlender = $env:BLENDER_EXE
$oldRepo = $env:BLENDER_MCP_REPO
try {
    $env:BMCPW_PYTHON = $python
    $env:CODEX_HOME = Join-Path $temp 'codex'
    $env:LOCALAPPDATA = Join-Path $temp 'localappdata'
    Remove-Item Env:BLENDER_EXE -ErrorAction SilentlyContinue
    Remove-Item Env:BLENDER_MCP_REPO -ErrorAction SilentlyContinue

    $version = & $entry version
    if ($LASTEXITCODE -ne 0 -or $version -notmatch '^bmcpw 1\.0\.0$') {
        throw "Fresh-machine version check failed: $version"
    }
    $config = Join-Path $temp 'codex\config.toml'
    $jsonText = (& $entry doctor --json --config $config --timeout 0.05) -join "`n"
    if ($LASTEXITCODE -ne 1) { throw "Fresh-machine doctor expected exit 1, got $LASTEXITCODE" }
    $report = $jsonText | ConvertFrom-Json
    if ($report.schema_version -ne 1 -or $report.overall -ne 'NOT_READY') {
        throw 'Fresh-machine doctor schema/overall check failed.'
    }
    if (Test-Path -LiteralPath $config) { throw 'Fresh-machine doctor unexpectedly wrote Codex config.' }
    Write-Output 'Fresh-machine PowerShell smoke test passed.'
}
finally {
    if ($null -eq $oldPython) { Remove-Item Env:BMCPW_PYTHON -ErrorAction SilentlyContinue } else { $env:BMCPW_PYTHON = $oldPython }
    if ($null -eq $oldCodexHome) { Remove-Item Env:CODEX_HOME -ErrorAction SilentlyContinue } else { $env:CODEX_HOME = $oldCodexHome }
    if ($null -eq $oldLocalAppData) { Remove-Item Env:LOCALAPPDATA -ErrorAction SilentlyContinue } else { $env:LOCALAPPDATA = $oldLocalAppData }
    if ($null -eq $oldBlender) { Remove-Item Env:BLENDER_EXE -ErrorAction SilentlyContinue } else { $env:BLENDER_EXE = $oldBlender }
    if ($null -eq $oldRepo) { Remove-Item Env:BLENDER_MCP_REPO -ErrorAction SilentlyContinue } else { $env:BLENDER_MCP_REPO = $oldRepo }
    if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp -Recurse -Force }
}
