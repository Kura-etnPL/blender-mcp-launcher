# Blender MCP Launcher (Windows)

Windows launcher, auto-connect scripts and MCP config templates for [ahujasid/blender-mcp](https://github.com/ahujasid/blender-mcp).

This is **not** the Blender MCP server itself. It is a small glue layer that makes the upstream project easier to run on Windows with:

- a **hidden-window Blender launcher** (`.vbs` / `.ps1`)
- a **server wrapper** that fixes PYTHONPATH issues when running `blender_mcp.server` directly
- **command-line addon install / enable / auto-start scripts**
- an **auto-connect handler** that starts the Blender MCP server on scene load
- ready-to-copy MCP config snippets for **Claude Code** and **Codex CLI**

## What this repo contains

| File | Purpose |
|------|---------|
| `launch_blender_mcp.vbs` | Launch Blender with no visible window (double-click friendly) |
| `launch_blender_mcp.ps1` | PowerShell version of the hidden-window launcher |
| `mcp_server_wrapper.py` | Adds the upstream `blender-mcp/src` folder to `sys.path` and starts the MCP server |
| `install_addon.py` | Install/enable the upstream `addon.py` from the command line |
| `enable_addon.py` | Enable an already-installed addon and save preferences |
| `enable_auto_start.py` | Turn on the addon's "auto start server" flag |
| `auto_connect.py` | Blender handler that auto-starts the MCP server on scene load |
| `configs/` | Example MCP configurations for Claude Code / Codex CLI |

## Prerequisites

1. **Blender** installed on Windows.
2. A local clone of [`ahujasid/blender-mcp`](https://github.com/ahujasid/blender-mcp).
3. (Optional) The [uv](https://docs.astral.sh/uv/) package manager if you run the upstream server through uvx.

## Configuration

All scripts read paths from environment variables. Set them once and the scripts work without editing source files.

Recommended way on Windows:

```powershell
[Environment]::SetEnvironmentVariable("BLENDER_EXE", "C:\Program Files\Blender Foundation\Blender 4.2\blender.exe", "User")
[Environment]::SetEnvironmentVariable("BLENDER_MCP_REPO", "C:\tools\blender-mcp", "User")
```

Or edit the default values at the top of each script.

| Environment variable | Default | Meaning |
|----------------------|---------|---------|
| `BLENDER_EXE` | `C:\Program Files\Blender Foundation\Blender 4.2\blender.exe` | Path to `blender.exe` |
| `BLENDER_MCP_REPO` | `C:\tools\blender-mcp` | Path to your clone of `ahujasid/blender-mcp` |

Other paths are derived from `BLENDER_MCP_REPO`:

- addon: `%BLENDER_MCP_REPO%\addon.py`
- server source: `%BLENDER_MCP_REPO%\src`

## Usage

### 1. Install the Blender addon once

```powershell
# From PowerShell, or run via Blender's Python console
& "$env:BLENDER_EXE" --background --python "install_addon.py"
```

### 2. Enable auto-start

```powershell
& "$env:BLENDER_EXE" --background --python "enable_auto_start.py"
```

### 3. Launch Blender hidden

Double-click `launch_blender_mcp.vbs`, or run:

```powershell
.\launch_blender_mcp.ps1
```

Blender will start in the background and the addon will connect automatically.

### 4. Connect Claude Code / Codex

Copy the relevant example from `configs/` into your MCP config and adjust paths.

For **Claude Code** (`.claude.json` / `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "blender": {
      "command": "python",
      "args": [
        "C:\\tools\\blender-mcp-launcher\\mcp_server_wrapper.py"
      ],
      "env": {
        "BLENDER_MCP_REPO": "C:\\tools\\blender-mcp"
      }
    }
  }
}
```

For **Codex CLI** (`~/.codex/config.toml` or project `codex.config.toml`):

```toml
[agents.blender]
command = ["python", "C:\\tools\\blender-mcp-launcher\\mcp_server_wrapper.py"]
```

See [`configs/`](configs/) for full examples.

## Why this wrapper?

The upstream MCP server is usually started with `uvx blender-mcp`. On some Windows setups, running the server directly from Claude Code fails because the `blender_mcp` package cannot be found. `mcp_server_wrapper.py` simply inserts the upstream `src` directory into `sys.path` before importing the server, sidestepping the import error.

## License

MIT — see [LICENSE](LICENSE). This wrapper is independent of `ahujasid/blender-mcp`; the upstream project remains under its own MIT license and copyright.
