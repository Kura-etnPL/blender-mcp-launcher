# OSS maintainer evidence

This is a factual record for maintainers and reviewers, not an adoption or
marketing claim.

- Repository: [Kura-etnPL/blender-mcp-launcher](https://github.com/Kura-etnPL/blender-mcp-launcher)
- Purpose: Windows compatibility, diagnostics, installation, launch, and Codex
  integration for the independent upstream [ahujasid/blender-mcp](https://github.com/ahujasid/blender-mcp)
- License: MIT, with upstream attribution in `NOTICE.md`
- Maintainer account: `Kura-etnPL` (repository owner at the release audit)
- Core implementation: standard-library Python CLI plus PowerShell wrappers
- Privacy posture: no companion telemetry, analytics, cloud backend, account
  system, public listener, or paid API requirement
- Tests: Python unit/integration/security tests, PowerShell parser/entry-point
  checks, CI, release archive and checksum validation
- Codex support: current official `[mcp_servers.<name>]` STDIO format, CLI
  command reference, safe legacy migration, dry-run, backup, atomic write
- Upstream evidence reviewed: issues #328 and #314; open PRs #329 and #327 at
  the 2026-08-24 audit. No upstream PR was created by this companion because
  the relevant focused fixes already existed as open proposals and no second
  duplicate was justified.
- Community activity: no invented users, stars, downloads, endorsements,
  issues, or adoption statistics are claimed here.
