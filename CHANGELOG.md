# Changelog

All notable changes to this companion project are documented here.

## [Unreleased]


## [1.0.2] - 2026-08-24

### Fixed

- Release archives now normalize UTF-8 text inputs to LF before packaging, so
  Windows CRLF and CI LF checkouts produce identical bytes.
- Added a Windows-vs-CI checkout normalization reproducibility gate.

## [1.0.1] - 2026-08-24

### Fixed

- Windows discovery now validates executable paths from running Blender
  processes, so portable/custom installations on drives such as `E:` are
  found without scanning arbitrary directories or executing process metadata.
- The fresh-machine PowerShell harness supports the configurable
  `BMCPW_TEST_TEMP_ROOT` and defaults to the checkout's ignored `.tmp` area.

## [1.0.0] - 2026-08-24

### Added

- Windows-first `bmcpw` CLI with `doctor`, `status`, `install`, `start`, `stop`,
  `version`, and safe Codex configuration commands.
- Bounded localhost health diagnostics that distinguish closed, listening but
  unresponsive, responding, reset, and timeout states.
- Idempotent Codex TOML migration from legacy `[agents.blender]` sections to
  the current `[mcp_servers.blender]` shape, with backup, dry-run, UTF-8/BOM,
  atomic-write, and unrelated-server preservation support.
- Real Blender add-on module detection (`addon` for upstream `addon.py`),
  explicit backup before add-on replacement, and honest Scene-property
  auto-start persistence behavior.
- Unit, integration, PowerShell parser, security, CI, and reproducible release
  packaging checks.
- Threat model, risk register, compatibility matrix, migration guide, and OSS
  maintainer evidence record.

### Security

- The launcher has no telemetry, analytics, cloud backend, public listener, or
  paid API dependency.
- Upstream launch configuration sets `DISABLE_TELEMETRY=true` by default.
- Hidden starts run a local add-on preflight and all process invocations use
  structured argument vectors without shell evaluation.

### Release integrity

- Release archives use fixed ZIP metadata and `ZIP_STORED` entries so the same
  source produces one SHA256 digest on Python 3.11, 3.12, and 3.13; CI and the
  release workflow compare all runtime manifests before publication.
