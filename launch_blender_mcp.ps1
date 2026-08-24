[CmdletBinding()]
param(
    [switch] $DebugMode
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = 'Stop'
$entry = Join-Path -Path $PSScriptRoot -ChildPath 'bmcpw.ps1'
if ($DebugMode) {
    & $entry 'start' '--debug'
} else {
    & $entry 'start' '--hidden'
}
exit $LASTEXITCODE
