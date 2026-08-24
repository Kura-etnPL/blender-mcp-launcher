# Contributing

Thank you for improving this Windows-first companion project.

## Scope

Keep changes local, dependency-light, and auditable. This repository is not a
place to copy upstream BlenderMCP code or to add cloud services, telemetry,
analytics, paid API calls, public listeners, or hidden downloads.

For a change that belongs in the upstream server or add-on, open one focused
upstream contribution instead of adding a compatibility monkey patch here.
Link the reproducible upstream issue and keep this repository's docs explicit
about what is and is not fixed.

## Before opening a PR

Run the same checks used by CI:

```powershell
& python -m unittest discover -s tests -p 'test_*.py' -v
& (Get-Command pwsh).Source -NoProfile -File tests\test_powershell.ps1
& python scripts\build_release.py
```

For a local E:-scoped checkout, point temporary files at an E: directory before
running the gates. The fresh-machine harness accepts the same override and
otherwise uses the checkout's ignored `.tmp\test-temp` directory:

```powershell
$env:BMCPW_TEST_TEMP_ROOT = 'E:\path\to\blender-mcp-launcher\.tmp\test-temp'
$env:TEMP = $env:BMCPW_TEST_TEMP_ROOT
$env:TMP = $env:BMCPW_TEST_TEMP_ROOT
& (Get-Command pwsh).Source -NoProfile -File tests\test_fresh_machine.ps1
```

Do not commit `dist/`, `.tmp/`, logs, local Codex configs, Blender files, or
credentials. Run `git diff --check` and inspect the archive contents before a
release-related change.

## Bug and compatibility reports

Use the issue templates. Include the redacted output of `bmcpw doctor --json`
and the exact command/result. Remove usernames, full paths, tokens, API keys,
`.blend` contents, and private repository URLs before posting.

For Windows hangs, include (when safe):

- Windows version and PowerShell version;
- Blender version and whether the window was visible or background;
- upstream BlenderMCP version/commit;
- Python and uv/uvx versions;
- Codex client/version;
- whether the result was `CLOSED`, `ACCEPTS_BUT_NO_RESPONSE`, `RESET`, or
  `TIMEOUT`.

## Style

Use the standard library where practical, typed Python, explicit error
messages, structured subprocess arguments, bounded timeouts, and tests for
encoding/configuration/security edge cases. Do not broaden writes or add
network calls without a documented threat-model update.
