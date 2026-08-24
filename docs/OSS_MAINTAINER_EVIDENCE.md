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

## v1.0.3 security and CI hardening (2026-08-24)

Factual engineering record for the v1.0.3 hardening release:

- Release pipeline jobs run with least-privilege GitHub token permissions;
  the workflow default is `contents: read` and only the publish job declares
  `contents: write`.
- Every checkout in CI and release workflows sets
  `persist-credentials: false`; the secret-scan checkout uses
  `fetch-depth: 0` so history scanning covers all retrievable commits.
- Secret scanning runs the official Gitleaks binary (`v8.30.1`, pinned)
  against both the working tree and full Git history; the download is
  verified against Gitleaks' published checksum before use.
- All GitHub Actions are pinned to immutable commit SHAs with the release
  version recorded in a comment; majors used at this audit were
  `actions/checkout@v7.0.1`, `actions/setup-python@v7.0.0`,
  `actions/upload-artifact@v7.0.1`, `actions/download-artifact@v8.0.1`,
  and `softprops/action-gh-release@v3.0.2` (Node 24 runtimes).
- Windows PowerShell 5.1 (`powershell.exe`) and PowerShell 7 (`pwsh.exe`)
  each execute `tests/test_powershell.ps1` and
  `tests/test_fresh_machine.ps1` as separate visible CI jobs; the dual
  runtime matches the `.vbs` compatibility shim, which invokes PowerShell
  5.1 by design.
- A weekly `github-actions` Dependabot configuration tracks action updates.
- The static check is named "source safety audit" because that is its real
  scope: project-specific dangerous idiom and invariant checks. Secret
  detection is delegated to the Gitleaks gate rather than claimed by it.
