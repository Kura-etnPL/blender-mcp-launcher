# Compatibility matrix

Status meanings:

- **Verified** — exercised by the release's automated or explicitly recorded
  test, with the command/result available in the release report;
- **Expected** — supported by upstream metadata or design but not an
  end-to-end verification in this release environment;
- **Unsupported / Known issue** — a documented limitation or an upstream issue
  that must not be presented as a pass.

| Dimension | Status | Evidence / limitation |
|---|---|---|
| Windows 10 | Expected | Windows-first code paths and PowerShell 5.1-compatible syntax; no clean Windows 10 GUI run was available for this release audit |
| Windows 11 | Expected | CI targets `windows-latest`; local release audit is not a Blender GUI smoke test |
| PowerShell 5.1 | Expected | Parser-compatible entry scripts; run `tests/test_powershell.ps1` on the target host for verification |
| PowerShell 7 | Verified | Parser and unified entry-point test in the release environment |
| Python 3.11 | Verified | Launcher unit/security tests run with Python 3.11 in the release audit |
| Python 3.12 | Expected | CI matrix target; no local interpreter was assumed |
| Python 3.13 | Expected | CI matrix target; no local interpreter was assumed |
| Python 3.14 | Unsupported / Known issue | Upstream issue [#314](https://github.com/ahujasid/blender-mcp/issues/314) reports compatibility risk; use managed 3.11 |
| Blender 3.0+ | Expected | Upstream `pyproject.toml` metadata; no general version-by-version GUI claim |
| Blender 4.x/5.x | Expected | Upstream add-on source and Scene-property behavior reviewed; end-to-end GUI verification remains environment-specific |
| Upstream BlenderMCP 1.8.3 | Expected | Current public `pyproject.toml` inspected; upstream source checkout can lack private `config.py` |
| Codex CLI/App/IDE | Expected | Current official MCP docs and `openai/codex` config/CLI implementation verified; local Codex executable is environment-specific |
| Codex MCP transport | Verified | Generated config uses official STDIO `mcp_servers` shape and unit tests parse/merge it |
| Upstream Windows transport | Unsupported / Known issue | See upstream [#314](https://github.com/ahujasid/blender-mcp/issues/314); doctor classifies the failure rather than claiming a fix |
