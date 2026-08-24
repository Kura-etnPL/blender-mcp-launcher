# Migration guide

## From the original scripts

Existing environment variables remain valid:

- `BLENDER_EXE` selects Blender;
- `BLENDER_MCP_REPO` selects the local upstream checkout.

Use `bmcpw.ps1` as the main entry point. The old
`launch_blender_mcp.ps1` and `launch_blender_mcp.vbs` names delegate to it and
can be removed later after local verification.

## From legacy Codex configuration

The old project example used `[agents.blender]`. Current Codex uses
`[mcp_servers.blender]` for a local STDIO server. Preview and migrate only the
known Blender sections:

```powershell
.\bmcpw.ps1 configure codex --dry-run
.\bmcpw.ps1 configure codex
```

The command validates the entire existing TOML first, preserves unrelated MCP
servers, backs up an existing file, and is idempotent. If the file uses an
inline `mcp_servers = { ... }` map or is malformed, it refuses to rewrite it;
convert/fix that file manually after taking your own copy.

## Auto-start behavior

The upstream `blendermcp_auto_start_server` value is a Scene property, not a
user-preference value. The new installer does not silently replace Blender's
startup file. Use `--save-startup-file` only as an explicit, understood action.

## Source checkout wrapper

The old wrapper inserted any supplied directory into `sys.path`. The new
wrapper validates `src/blender_mcp/server.py` first and reports an incomplete
upstream source checkout. It does not create a fake private telemetry config or
claim to fix upstream #328.
