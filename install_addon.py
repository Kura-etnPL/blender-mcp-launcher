"""Install the upstream single-file BlenderMCP add-on from inside Blender.

This script runs under Blender's Python, not the launcher interpreter.  It
never downloads code and only reads the explicitly supplied local repository.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import sys
from datetime import datetime

import bpy


def fail(message: str) -> "NoReturn":
    print(f"BlenderMCP installer: ERROR: {message}", file=sys.stderr)
    raise SystemExit(2)


repo_value = os.environ.get("BLENDER_MCP_REPO", "").strip()
if not repo_value:
    fail("BLENDER_MCP_REPO is not set; point it to a local ahujasid/blender-mcp checkout.")
repo = Path(repo_value).expanduser().resolve()
addon_path = repo / "addon.py"
if not repo.is_dir() or not addon_path.is_file():
    fail(f"upstream add-on file was not found at {addon_path}")

module = os.environ.get("BLENDER_MCP_ADDON_MODULE", addon_path.stem).strip()
if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", module):
    fail(f"invalid Blender add-on module identifier: {module!r}")

try:
    addons_dir = Path(bpy.utils.user_resource("SCRIPTS", path="addons", create=True)).resolve()
except TypeError:
    # Older Blender versions do not accept create=.
    addons_dir = Path(bpy.utils.user_resource("SCRIPTS", path="addons")).resolve()
except Exception as exc:
    fail(f"could not resolve Blender's user add-on directory: {exc}")

if not addons_dir.is_dir():
    fail(f"Blender's add-on directory does not exist: {addons_dir}")

# Make a recoverable, timestamped backup of a same-name installed file before
# asking Blender to overwrite it.  The target is derived from Blender's own
# user-resource directory; no recursive or broad cleanup is performed.
for existing in (addons_dir / f"{module}.py", addons_dir / addon_path.name):
    if not existing.is_file():
        continue
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = existing.with_name(f"{existing.name}.bak-{stamp}")
    try:
        shutil.copy2(existing, backup)
        print(f"Backed up existing add-on to {backup}")
    except OSError as exc:
        fail(f"could not back up {existing}: {exc}")

try:
    result = bpy.ops.preferences.addon_install(filepath=str(addon_path), overwrite=True)
    if "FINISHED" not in result:
        fail(f"Blender rejected add-on installation: {result}")
    result = bpy.ops.preferences.addon_enable(module=module)
    if "FINISHED" not in result:
        fail(f"Blender rejected add-on enable for module {module!r}: {result}")
    if bpy.context.preferences.addons.get(module) is None:
        fail(f"Blender did not report module {module!r} as enabled after installation")
    bpy.ops.wm.save_userpref()
except SystemExit:
    raise
except Exception as exc:
    fail(f"Blender API operation failed: {exc}")

print(f"BlenderMCP add-on installed and enabled (module={module}, source={addon_path}).")
