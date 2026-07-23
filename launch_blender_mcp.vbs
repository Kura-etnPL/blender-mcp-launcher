Set WshShell = CreateObject("WScript.Shell")

' Read Blender path from environment variable, fallback to a common default.
blenderExe = WshShell.ExpandEnvironmentStrings("%BLENDER_EXE%")
If blenderExe = "%BLENDER_EXE%" Then
    blenderExe = "C:\Program Files\Blender Foundation\Blender 4.2\blender.exe"
End If

' Launch Blender with a hidden window (0 = hidden, false = don't wait).
WshShell.Run " """ & blenderExe & """" , 0, False
