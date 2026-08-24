[CmdletBinding()]
param()

Set-StrictMode -Version 3.0
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$parseErrors = @()
$tokens = $null
foreach ($path in @(
    (Join-Path $root 'bmcpw.ps1'),
    (Join-Path $root 'launch_blender_mcp.ps1')
)) {
    [System.Management.Automation.Language.Parser]::ParseFile($path, [ref]$tokens, [ref]$parseErrors) | Out-Null
    if ($parseErrors.Count -gt 0) {
        throw "PowerShell parse errors in $path`: $($parseErrors | Out-String)"
    }
    $parseErrors = @()
}

$python = $env:BMCPW_PYTHON
if (-not $python) {
    $pythonCommand = Get-Command python.exe, python, py.exe, py -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($pythonCommand) { $python = $pythonCommand.Source }
}
if (-not $python) { throw 'Python is required for the PowerShell integration test.' }
$env:BMCPW_PYTHON = $python
$versionOutput = & (Join-Path $root 'bmcpw.ps1') version
if ($LASTEXITCODE -ne 0 -or $versionOutput -notmatch '^bmcpw 1\.0\.2$') {
    throw "Unified PowerShell entry point did not return the expected version: $versionOutput"
}
Write-Output 'PowerShell syntax and unified entry point checks passed.'
