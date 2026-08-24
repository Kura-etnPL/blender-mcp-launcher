# Risk register

| Risk | Severity | Likelihood | Mitigation | Detection | Residual risk |
|---|---|---:|---|---|---|
| Upstream tools can execute local Blender Python | Critical | Medium | Trust only the MCP client/config; document the capability and require normal user review | upstream docs; security review | A trusted client still has powerful local control |
| Hidden Blender process is confusing | High | Medium | Hidden mode requires add-on preflight; visible/debug modes and PID-owned stop are available | `start --hidden`, `status`, PID checks | Blender may still show its own dialogs |
| Listener binds beyond loopback | High | Low | Companion never binds; doctor refuses non-loopback host and docs require loopback | `network_binding` doctor check | Upstream configuration can still be changed outside this project |
| Untrusted MCP client connects locally | High | Medium | Use only trusted clients/configs; no public listener | security docs; user review | Any local process with access may connect |
| PowerShell/path injection | High | Low | structured argument vectors, `shell=False`, literal paths, no `Invoke-Expression` | AST/static security test | External tools and Windows parsing remain platform dependencies |
| Codex config corruption | High | Low | parse before write, scoped section replacement, timestamped backup, same-directory atomic write, post-write validation | config unit/integration tests | A filesystem/host crash can still lose the latest change; backup remains |
| Upstream package/source breakage | High | Medium | prefer upstream `uvx`; wrapper validates and fails closed; show version/commit | doctor; upstream release/issue links | Upstream changes can require a new companion release |
| Blender API or add-on module change | High | Medium | derive module from `addon.py`, verify Blender API result, avoid claiming end-to-end support without testing | install script; doctor | Blender GUI/version matrix is partly expected rather than verified |
| Python 3.14 incompatibility reported upstream | Medium | Medium | prefer uv-managed Python 3.11; warn on 3.14; document issue #314 | doctor `python` check | Upstream may fix/change status after this release |
| Codex config format changes | High | Medium | official docs/source links, current `[mcp_servers.*]` shape, isolated merge tests | CI config tests; doctor syntax check | Future Codex versions may add fields or migration rules |
| Credential/path leakage in diagnostics | High | Low | redaction, no config values in JSON, secret scan of artifacts | doctor JSON tests; archive audit | Novel secret formats may evade a simple redactor |
