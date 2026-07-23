import os
import sys

# Path to your local clone of https://github.com/ahujasid/blender-mcp
REPO = os.environ.get("BLENDER_MCP_REPO", r"C:\tools\blender-mcp")

sys.path.insert(0, os.path.join(REPO, "src"))

from blender_mcp.server import main

if __name__ == "__main__":
    main()
