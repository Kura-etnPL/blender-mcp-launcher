# Architecture

```text
User
  |
  v
bmcpw.py / bmcpw.ps1
  |-- discovery (Blender, Python, uv, upstream, Codex)
  |-- doctor/status (local checks + bounded loopback ping)
  |-- install (Blender's local user add-on directory)
  |-- configure codex (parse -> merge -> validate -> atomic replace)
  |-- start/stop (structured local process control)
  v
Codex STDIO launcher (usually uvx blender-mcp)
  v
BlenderMCP upstream server
  v
Blender add-on TCP endpoint on loopback
```

The project has no server of its own, public listener, cloud backend,
telemetry, analytics, login system, remote command relay, or paid API. The
health probe is a client-side diagnostic only; it does not start or expose a
network service.

The only intentional import-path manipulation is in
`mcp_server_wrapper.py`, after validating the explicitly selected upstream
checkout contains `src/blender_mcp/server.py`. It is a documented offline
fallback and fails closed when the checkout is incomplete.
