# Release procedure

The release gate is intentionally conservative.

1. Start from a clean checkout and verify the target commit/ref.
2. Run Python unit/security tests and the PowerShell parser/entry-point test.
3. Run `git diff --check` and the static source audit.
4. Build `dist/blender-mcp-windows-compat-v<VERSION>.zip` with
   `scripts/build_release.py`.
5. Inspect the sorted archive contents and run the artifact secret scan.
6. Build the same archive with Python 3.11, 3.12, and 3.13 and run
   `scripts/verify_reproducible_release.py`; all SHA256SUMS entries must match.
7. Run the tag-triggered release workflow; its matrix gate and cross-runtime
   verification must pass before a GitHub release is published.
8. Upload the zip and `SHA256SUMS.txt`, and record the exact commit SHA and
   checksum in the release notes.

The artifact contains scripts, examples, user-facing docs, `LICENSE`, and
`NOTICE.md`; it excludes `.git`, `.tmp`, logs, caches, tests, credentials, and
local Blender/Codex state. The build uses ZIP_STORED, deterministic ZIP
timestamps, sorted paths, and fixed permissions so zlib implementation changes
cannot alter the archive digest. A release is not called `RELEASED` if a
required gate or real Blender/Codex smoke test remains unverified.
