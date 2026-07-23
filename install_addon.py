import bpy
import os
import sys

# Path to your local clone of https://github.com/ahujasid/blender-mcp
REPO = os.environ.get("BLENDER_MCP_REPO", r"C:\tools\blender-mcp")
addon_path = os.path.join(REPO, "addon.py")

# Install from file
bpy.ops.preferences.addon_install(filepath=addon_path, overwrite=True)

# Enable the addon
bpy.ops.preferences.addon_enable(module="blender_mcp")

# Save preferences so it persists
bpy.ops.wm.save_userpref()

print("Blender MCP addon installed and enabled.", file=sys.stderr)
