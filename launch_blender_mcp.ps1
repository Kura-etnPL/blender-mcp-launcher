# Launch Blender with hidden window; BlenderMCP addon will auto-connect on startup.
$blender = if ($env:BLENDER_EXE) { $env:BLENDER_EXE } else { "C:\Program Files\Blender Foundation\Blender 4.2\blender.exe" }
$workDir = Split-Path -Parent $blender

Start-Process -FilePath $blender `
    -WorkingDirectory $workDir `
    -WindowStyle Hidden
