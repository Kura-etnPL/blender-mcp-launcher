"""Enable the upstream scene property without pretending user preferences save it.

``blendermcp_auto_start_server`` is a Scene property.  ``save_userpref`` does
not persist a Scene value, so replacing Blender's startup file is explicit and
opt-in via ``BLENDER_MCP_SAVE_HOMEFILE=1``.
"""

from __future__ import annotations

import os
import sys

import bpy


scenes = list(bpy.data.scenes)
if not scenes:
    print("BlenderMCP: no scene is loaded; nothing to configure.", file=sys.stderr)
    raise SystemExit(2)

try:
    for scene in scenes:
        if not hasattr(scene, "blendermcp_auto_start_server"):
            raise RuntimeError("BlenderMCP add-on is not enabled or exposes no auto-start property")
        scene.blendermcp_auto_start_server = True
except Exception as exc:
    print(f"BlenderMCP: could not enable auto-start: {exc}", file=sys.stderr)
    raise SystemExit(2)

if os.environ.get("BLENDER_MCP_SAVE_HOMEFILE", "").lower() in {"1", "true", "yes", "on"}:
    try:
        bpy.ops.wm.save_homefile()
    except Exception as exc:
        print(f"BlenderMCP: startup file save failed: {exc}", file=sys.stderr)
        raise SystemExit(2)
    print("BlenderMCP: auto-start enabled and Blender startup file saved.")
else:
    print(
        "BlenderMCP: auto-start property enabled for the current scene. "
        "The upstream default is true; startup-file replacement was skipped. "
        "Pass --save-startup-file only when that global write is intentional."
    )
