import bpy
import sys

# The installed module is named after the file: addon.py -> "addon"
bpy.ops.preferences.addon_enable(module="addon")
bpy.ops.wm.save_userpref()

print("Blender MCP addon enabled.", file=sys.stderr)
