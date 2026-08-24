"""Validated local-source fallback for BlenderMCP's official server module.

The preferred Codex command is the upstream ``uvx blender-mcp`` entry point.
This wrapper exists for offline/local checkout scenarios only.  It validates
the source root before the intentional import-path insertion and fails clearly
when a source checkout is incomplete; it never creates a fake upstream module.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import sys


def _fail(message: str) -> "NoReturn":
    print(f"BlenderMCP local wrapper: ERROR: {message}", file=sys.stderr)
    raise SystemExit(2)


raw_repo = os.environ.get("BLENDER_MCP_REPO", "").strip()
if not raw_repo:
    _fail("BLENDER_MCP_REPO is required for the local-source fallback")
repo = Path(raw_repo).expanduser().resolve()
source = repo / "src"
package = source / "blender_mcp"
server = package / "server.py"
if not repo.is_dir():
    _fail(f"repository does not exist: {repo}")
if not source.is_dir() or not package.is_dir() or not server.is_file():
    _fail(f"repository is not a validated BlenderMCP source checkout: {repo}")
if not re.fullmatch(r"blender_mcp", package.name):
    _fail("unexpected upstream package directory")

# The source checkout is now validated and the project intentionally takes
# precedence over an unrelated installed blender_mcp package.
sys.path.insert(0, str(source))
os.environ.setdefault("DISABLE_TELEMETRY", "true")

try:
    from blender_mcp.server import main
except ModuleNotFoundError as exc:
    if exc.name == "blender_mcp.config":
        _fail(
            "the upstream source checkout lacks its private telemetry config; "
            "use `uvx blender-mcp` or an upstream release/PR with the fallback. "
            "No compatibility monkey patch was applied."
        )
    _fail(f"upstream server dependency is unavailable: {exc}")
except Exception as exc:
    _fail(f"upstream server import failed: {exc}")


if __name__ == "__main__":
    main()
