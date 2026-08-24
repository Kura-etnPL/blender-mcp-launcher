# Maintainer notes

- This repository is a Windows-first companion for `ahujasid/blender-mcp`; it
  is not the upstream server and must not copy or monkey-patch it.
- Keep the core offline, standard-library-only, loopback-only, and free of
  telemetry, analytics, cloud backends, and paid API dependencies.
- Prefer `bmcpw.py` and the unified PowerShell entry point. Keep legacy launch
  names as thin compatibility shims only.
- Run Python unit/security tests, PowerShell parser tests, and the release
  packaging check before publishing. Never commit credentials, logs, `.blend`
  files, or generated `dist/` output.
- Configuration writes must parse, back up, merge only the selected Codex MCP
  server, validate, and atomically replace. Preserve unrelated servers.
