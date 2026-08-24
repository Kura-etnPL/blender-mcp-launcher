# BlenderMCP Windows Compatibility

Windows compatibility, diagnostics, setup, and Codex MCP configuration for
[ahujasid/blender-mcp](https://github.com/ahujasid/blender-mcp).

This is an independent companion project. It is not BlenderMCP itself, a
Blender Foundation project, an OpenAI project, or an official Windows edition.

## What this solves

The launcher gives a Windows user one local entry point for:

- finding Blender, Python, uv/uvx, the upstream checkout, and Codex;
- installing and enabling the upstream single-file add-on with the real module
  identifier (`addon` for `addon.py`);
- checking the BlenderMCP TCP transport with a bounded MCP `ping`;
- classifying `CLOSED`, `LISTENING`, `ACCEPTS_BUT_NO_RESPONSE`, `RESPONDS`,
  `RESET`, `MALFORMED_RESPONSE`, `BLOCKED_NON_LOOPBACK`, and `TIMEOUT` states;
- safely registering BlenderMCP in the current Codex configuration shape;
- keeping diagnostics and configuration local and redacted.

It does not copy the upstream server, patch its imports invisibly, start a
cloud service, collect telemetry, or require a paid API.

## Quick start

Open a normal PowerShell window in this repository:

```powershell
$env:BLENDER_MCP_REPO = 'C:\tools\blender-mcp'
.\bmcpw.ps1 doctor
.\bmcpw.ps1 install
.\bmcpw.ps1 configure codex
.\bmcpw.ps1 start --hidden
.\bmcpw.ps1 status
```

`BLENDER_MCP_REPO` must point to a local clone of the upstream repository.
The launcher does not download or execute an unreviewed remote script. If
Python is not on `PATH`, set `BMCPW_PYTHON` to a Python 3.11+ executable.

The old `launch_blender_mcp.ps1` and `.vbs` files remain compatibility shims;
they delegate to `bmcpw.ps1`. The PowerShell wrapper uses a per-process
execution-policy bypass only for that invocation and never changes Windows
execution policy.

## Requirements

- Windows 10 or 11 for the supported launcher path;
- Blender 3.0 or newer, according to the upstream package metadata;
- Python 3.11+ for the complete CLI and TOML validation path;
- a local upstream BlenderMCP checkout for add-on installation;
- uv/uvx for the upstream-recommended MCP server command, or an already
  prepared local Python environment for the explicit wrapper fallback.

The launcher itself uses only the Python standard library. The core commands
`doctor`, `status`, `configure`, and `start` do not contact the network.

## Commands

```text
bmcpw doctor [--json]       local preflight and actionable diagnostics
bmcpw status                bounded localhost MCP ping
bmcpw install               backup, install, enable the upstream add-on
bmcpw start [--hidden]      launch Blender with structured arguments
bmcpw stop                  stop only the launcher-owned Blender PID
bmcpw configure codex       safe Codex config merge and legacy migration
bmcpw configure codex --dry-run
bmcpw version
```

PowerShell users can call the same commands with `.\bmcpw.ps1`. `diagnose` is
an alias for `doctor`, and `codex` is an alias for `configure codex`.

### Doctor

Use the human-readable form when fixing a setup and the JSON form when
attaching a sanitized report to an issue:

```powershell
.\bmcpw.ps1 doctor
.\bmcpw.ps1 doctor --json | ConvertFrom-Json
```

The JSON schema contains check codes, statuses, safe messages, and redacted
paths. It does not include usernames, full home paths, credentials, tokens,
API keys, or file contents. Exit code `1` means `NOT_READY`; `0` means no
blocking failure was found (warnings can still require review).

A health result is deliberately more specific than “failed”:

| State | Meaning | Next action |
|---|---|---|
| `CLOSED` | no TCP listener accepted the connection | enable the add-on and start BlenderMCP |
| `LISTENING` | TCP connect succeeded | inspect the following request classification |
| `ACCEPTS_BUT_NO_RESPONSE` | connection accepted, MCP ping timed out | inspect Blender's main loop and system console |
| `RESPONDS` | a bounded JSON ping response arrived | transport is healthy for this check |
| `RESET` | the peer reset/closed the exchange | restart the add-on and inspect stale clients |
| `MALFORMED_RESPONSE` | bytes arrived but were not one complete JSON response | inspect the client/server protocol |
| `BLOCKED_NON_LOOPBACK` | the requested host was not loopback | use `127.0.0.1`, `localhost`, or `::1` |
| `TIMEOUT` | TCP connection itself did not complete in time | check local process/firewall state |

The diagnostic timeout defaults to three seconds and is always bounded. The
CLI rejects probe timeouts above 30 seconds and refuses non-loopback hosts
before opening a socket.

On Windows, automatic Blender discovery first honors `--blender`/
`BLENDER_EXE`, then validates paths of running `blender.exe` processes before
checking `PATH`, standard install roots, and read-only registry hints. It does
not recursively scan arbitrary drives, and process metadata is never executed
as a command.

## Install and auto-start

The installer validates `BLENDER_MCP_REPO\addon.py`, uses Blender's own user
resource directory, makes a timestamped backup of an existing same-name add-on,
then enables the module derived from the file (`addon`). It does not write the
registry, system `PATH`, Defender, UAC, or execution policy.

The upstream auto-start flag is a Blender **Scene** property. Calling
`save_userpref` does not persist a scene value. Therefore `bmcpw install` does
not silently replace Blender's global startup file. If that global write is
intended, use:

```powershell
.\bmcpw.ps1 install --save-startup-file
```

The explicit flag is destructive to the user's startup-file choice and should
be used only after saving/understanding the current Blender startup file.

## Codex MCP setup

Current official Codex documentation uses `~/.codex/config.toml` and
`[mcp_servers.<name>]` for local STDIO servers. The official CLI form is:

```powershell
codex mcp add blender --env DISABLE_TELEMETRY=true -- uvx --python 3.11 blender-mcp
codex mcp list
```

The companion's safer merge path is:

```powershell
.\bmcpw.ps1 configure codex --dry-run
.\bmcpw.ps1 configure codex
```

It validates the existing TOML before changing it, removes only known
`[agents.blender]` and nested sections, creates a timestamped backup, preserves
other MCP entries, writes through a same-directory temporary file, validates
again, and replaces atomically. Repeating the command is a no-op.

The generated server entry prefers the upstream-recommended `uvx` command and
pins its managed interpreter to Python 3.11. If uv/uvx is not found, it falls
back to the validated local wrapper only when `BLENDER_MCP_REPO` is available.
The wrapper fails closed when a source checkout is incomplete; it does not
invent the upstream private configuration or monkey-patch the package.

Codex's MCP configuration is shared by the Codex CLI, desktop app, and IDE
extension on the same host. A GUI-launched client may need the full path from
`where.exe uvx` because its `PATH` can differ from a terminal's `PATH`.

References:

- [OpenAI Codex MCP documentation](https://developers.openai.com/codex/mcp/)
- [Codex TOML implementation](https://github.com/openai/codex/blob/main/codex-rs/config/src/config_toml.rs)
- [Codex `mcp add` implementation](https://github.com/openai/codex/blob/main/codex-rs/cli/src/mcp_cmd.rs)
- [generated TOML example](configs/codex_mcp_config.toml.example)

## Claude Code

The example in `configs/claude_code_mcp.json.example` uses upstream's current
`uvx` STDIO path and disables upstream telemetry. Claude Code's own CLI/config
format is separate from Codex's TOML format; do not copy the JSON shape into
Codex.

## Upstream relationship and known issues

The upstream server and add-on remain the source of truth for Blender behavior.
At the 2026-08-24 release audit:

- upstream issue [#328](https://github.com/ahujasid/blender-mcp/issues/328)
  tracks Codex metadata, zero-argument `get_scene_info`, instructions, and
  annotations;
- upstream issue [#314](https://github.com/ahujasid/blender-mcp/issues/314)
  reports Windows accepted-connection hangs, resets, and a Python 3.14 risk;
- upstream PR [#329](https://github.com/ahujasid/blender-mcp/pull/329) and
  PR [#327](https://github.com/ahujasid/blender-mcp/pull/327) were open and
  unmerged during this audit.

This project detects and explains those classes of failure. It does not claim
to have fixed upstream internals and does not copy or monkey-patch upstream
code. Use a released upstream package or a reviewed upstream change when a
source checkout is missing its private telemetry config.

## Security

Connecting a trusted AI agent to Blender grants that client powerful local
control, including arbitrary Blender Python through upstream tools. Only
connect clients and configs you trust, keep the listener on loopback, save
important `.blend` files, and review scripts before running them.

The companion layer:

- opens no network listener and performs only bounded loopback health probes;
- has no cloud backend, analytics, telemetry, account system, or paid API;
- invokes Blender and process tools with argument arrays and `shell=False`;
- validates an explicitly selected upstream source before importing it;
- writes only the selected Codex config, same-directory backup/temp files, the
  selected Blender user add-on, and its bounded local log directory.

See [SECURITY.md](SECURITY.md), [docs/RISK_REGISTER.md](docs/RISK_REGISTER.md),
and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Compatibility

The project distinguishes `Verified`, `Expected`, and `Unsupported / Known
issue`; it does not turn upstream metadata into an end-to-end compatibility
claim. See [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md).

## Troubleshooting

1. Run `.\bmcpw.ps1 doctor --json` and remove personal paths before posting.
2. If `CLOSED`, confirm the add-on is enabled and the Blender sidebar reports a
   running server on the same port.
3. If `ACCEPTS_BUT_NO_RESPONSE`, keep Blender visible, inspect the system
   console, and attach the redacted report. Do not increase a timeout to hide a
   hang.
4. If Codex is missing the server, run `codex mcp list`, then rerun the dry-run
   and merge commands. Fully restart the desktop/IDE client after config/PATH
   changes.
5. If the local wrapper reports a missing upstream config, use `uvx` or an
   upstream release/PR; this companion intentionally does not fabricate config.

## Migration

Existing users can keep `BLENDER_EXE` and `BLENDER_MCP_REPO`. Old launcher names
remain as shims. Replace old Codex `[agents.blender]` blocks with:

```powershell
.\bmcpw.ps1 configure codex --dry-run
.\bmcpw.ps1 configure codex
```

Read [docs/MIGRATION.md](docs/MIGRATION.md) before deleting old files or
changing a Blender startup file.

## Development and release

```powershell
& 'E:\CSoftware\PythonEnvs\auto_empire\Scripts\python.exe' -m unittest discover -s tests -p 'test_*.py' -v
& (Get-Command pwsh).Source -NoProfile -File tests\test_powershell.ps1
& 'E:\CSoftware\PythonEnvs\auto_empire\Scripts\python.exe' scripts\build_release.py
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [docs/RELEASE.md](docs/RELEASE.md),
and the pull-request CI workflow. A release is not represented by a tag alone;
the zip and `SHA256SUMS.txt` are generated from a clean, tested tree.
The archive contract uses fixed ordering, timestamps, permissions, and
`ZIP_STORED` entries; CI and the release workflow verify one SHA256 digest
across Python 3.11, 3.12, and 3.13 before publication.

## License

This companion project is MIT licensed; see [LICENSE](LICENSE). Upstream
BlenderMCP is separate and retains its own license and terms; see
[NOTICE.md](NOTICE.md).
