"""Enable an already installed BlenderMCP add-on and persist preferences."""

from __future__ import annotations

import os
import re
import sys

import bpy


module = os.environ.get("BLENDER_MCP_ADDON_MODULE", "addon").strip()
if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", module):
    print(f"BlenderMCP: invalid add-on module identifier: {module!r}", file=sys.stderr)
    raise SystemExit(2)

try:
    result = bpy.ops.preferences.addon_enable(module=module)
    if "FINISHED" not in result or bpy.context.preferences.addons.get(module) is None:
        raise RuntimeError(f"Blender did not enable module {module!r}; operator result={result}")
    bpy.ops.wm.save_userpref()
except Exception as exc:
    print(f"BlenderMCP: could not enable {module!r}: {exc}", file=sys.stderr)
    raise SystemExit(2)

print(f"BlenderMCP add-on enabled (module={module}).")
