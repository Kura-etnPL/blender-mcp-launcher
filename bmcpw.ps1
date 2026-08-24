[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $Arguments
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = 'Stop'

$scriptPath = Join-Path -Path $PSScriptRoot -ChildPath 'bmcpw.py'
if (-not (Test-Path -LiteralPath $scriptPath -PathType Leaf)) {
    throw "bmcpw.py was not found next to this launcher: $PSScriptRoot"
}

function Resolve-Python {
    if ($env:BMCPW_PYTHON) {
        $explicit = Get-Command -Name $env:BMCPW_PYTHON -ErrorAction SilentlyContinue
        if ($explicit) { return $explicit.Source }
        if (Test-Path -LiteralPath $env:BMCPW_PYTHON -PathType Leaf) { return $env:BMCPW_PYTHON }
        throw "BMCPW_PYTHON does not resolve to a Python executable."
    }

    $python = Get-Command -Name 'python.exe' -ErrorAction SilentlyContinue
    if (-not $python) { $python = Get-Command -Name 'python' -ErrorAction SilentlyContinue }
    if ($python) { return $python.Source }

    $py = Get-Command -Name 'py.exe' -ErrorAction SilentlyContinue
    if (-not $py) { $py = Get-Command -Name 'py' -ErrorAction SilentlyContinue }
    if ($py) { return $py.Source }
    throw 'Python was not found. Install Python 3.11+ or set BMCPW_PYTHON to python.exe.'
}

$pythonCommand = Resolve-Python
$pythonArguments = [System.Collections.Generic.List[string]]::new()
if ([System.IO.Path]::GetFileNameWithoutExtension($pythonCommand).ToLowerInvariant() -eq 'py') {
    [void] $pythonArguments.Add('-3.11')
}
[void] $pythonArguments.Add($scriptPath)
if ($Arguments) {
    foreach ($argument in $Arguments) { [void] $pythonArguments.Add([string]$argument) }
}

& $pythonCommand @pythonArguments
exit $LASTEXITCODE
