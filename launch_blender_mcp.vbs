Option Explicit

Dim shell, fso, powershell, entry, command
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' This is a compatibility shim. It delegates to the single, validated
' PowerShell entry point and passes no user-controlled command string.
powershell = shell.ExpandEnvironmentStrings("%SystemRoot%") & "\System32\WindowsPowerShell\v1.0\powershell.exe"
entry = fso.BuildPath(fso.GetParentFolderName(WScript.ScriptFullName), "bmcpw.ps1")
command = Quote(powershell) & " -NoLogo -NoProfile -ExecutionPolicy Bypass -File " & Quote(entry) & " start --hidden"
shell.Run command, 0, False

Function Quote(value)
    ' Windows file paths cannot contain a double quote; surrounding the path
    ' is sufficient to protect spaces, &, semicolons, and parentheses.
    Quote = """" & value & """"
End Function
