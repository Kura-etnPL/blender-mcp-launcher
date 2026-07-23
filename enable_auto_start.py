import bpy
import sys

# Enable BlenderMCP auto-start on Blender launch
for scene in bpy.data.scenes:
    scene.blendermcp_auto_start_server = True

bpy.ops.wm.save_userpref()

print("BlenderMCP auto-start enabled.", file=sys.stderr)
