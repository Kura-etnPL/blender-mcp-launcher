# Security policy

## Scope

This project is a local Windows compatibility layer. It can launch Blender,
write a selected Codex `config.toml`, install a selected local Blender add-on,
and inspect a loopback TCP endpoint. The upstream BlenderMCP server can execute
arbitrary Blender Python; that capability is outside this project's control but
is part of the security boundary users must understand.

The companion itself has no telemetry, analytics, cloud backend, login system,
paid API dependency, remote command relay, or public network listener.

## Reporting a vulnerability

Use GitHub's **Security** tab and **Report a vulnerability** / private
vulnerability reporting for this repository when that control is available.
Do not put secrets, exploit details, personal paths, or `.blend` data in a
public issue.

If private reporting is not enabled, open a minimal public issue requesting a
private channel and omit the sensitive details. Do not invent or use an email
address that is not published by the maintainer.

## What is a security concern

Please report evidence of:

- command or PowerShell injection;
- arbitrary file overwrite or path traversal outside the selected target;
- exposure of Codex credentials or user paths in output/artifacts;
- unintended non-loopback binding or network traffic;
- unsafe import shadowing or execution of an unvalidated upstream path;
- destructive startup/configuration writes without explicit user intent.

## User safety

Only connect trusted MCP clients to Blender. Keep the BlenderMCP endpoint on
loopback, review generated Codex configuration, save work before mutating
operations, and do not paste unknown scripts into Blender or Codex.
