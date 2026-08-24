"""Build a deterministic, user-facing release archive and SHA256SUMS.txt."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import time
import zipfile


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_FILES = (
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "NOTICE.md",
    "README.md",
    "SECURITY.md",
    "VERSION",
    "auto_connect.py",
    "bmcpw.ps1",
    "bmcpw.py",
    "configs/claude_code_mcp.json.example",
    "configs/codex_mcp_config.toml.example",
    "docs/ARCHITECTURE.md",
    "docs/COMPATIBILITY.md",
    "docs/MIGRATION.md",
    "docs/RISK_REGISTER.md",
    "enable_addon.py",
    "enable_auto_start.py",
    "install_addon.py",
    "launch_blender_mcp.ps1",
    "launch_blender_mcp.vbs",
    "mcp_server_wrapper.py",
)
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"(?im)^\s*(?:api[_-]?key|token|password|secret)\s*=\s*['\"](?!<)[^'\"]+['\"]"),
)


def read_version() -> str:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise SystemExit(f"invalid VERSION: {version!r}")
    return version


def validate_files() -> list[Path]:
    paths: list[Path] = []
    for relative in ARTIFACT_FILES:
        path = ROOT / relative
        if not path.is_file():
            raise SystemExit(f"release input is missing: {relative}")
        paths.append(path)
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                raise SystemExit(f"possible secret found in release input: {path.relative_to(ROOT)}")
    return paths


def zip_datetime() -> tuple[int, int, int, int, int, int]:
    raw = os.environ.get("SOURCE_DATE_EPOCH", "")
    try:
        epoch = int(raw) if raw else 1767225600  # 2026-01-01 UTC, stable default
    except ValueError as exc:
        raise SystemExit("SOURCE_DATE_EPOCH must be an integer") from exc
    epoch = max(epoch, 315532800)  # ZIP timestamps cannot represent pre-1980.
    tm = time.gmtime(epoch)
    return tm.tm_year, tm.tm_mon, tm.tm_mday, tm.tm_hour, tm.tm_min, tm.tm_sec


def build(output_dir: Path) -> tuple[Path, Path]:
    version = read_version()
    files = validate_files()
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / f"blender-mcp-windows-compat-v{version}.zip"
    checksum_file = output_dir / "SHA256SUMS.txt"
    date_time = zip_datetime()
    names = [relative.replace("\\", "/") for relative in ARTIFACT_FILES]
    if names != sorted(names):
        # The manifest is intentionally checked in order to make accidental
        # archive churn visible in review.
        raise SystemExit("ARTIFACT_FILES must be sorted for reproducibility")
    # ZIP_STORED is intentional.  zlib's deflate output can change between
    # Python versions even when the input bytes and ZIP metadata are fixed.
    # Storing the archive avoids that runtime-dependent digest while retaining
    # fixed order, timestamps, and permissions.
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as handle:
        for path, relative in zip(files, ARTIFACT_FILES):
            info = zipfile.ZipInfo(relative, date_time=date_time)
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 0
            info.external_attr = 0o100644 << 16
            handle.writestr(info, path.read_bytes())
    with zipfile.ZipFile(archive, "r") as handle:
        actual = sorted(handle.namelist())
        expected = sorted(ARTIFACT_FILES)
        if actual != expected:
            raise SystemExit(f"archive contents mismatch: {actual!r}")
        bad = handle.testzip()
        if bad:
            raise SystemExit(f"archive CRC check failed: {bad}")
        for name in actual:
            text = handle.read(name).decode("utf-8")
            for pattern in SECRET_PATTERNS:
                if pattern.search(text):
                    raise SystemExit(f"possible secret found in archive: {name}")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    checksum_file.write_text(f"{digest} *{archive.name}\n", encoding="utf-8", newline="\n")
    return archive, checksum_file


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    archive, checksums = build(args.output_dir)
    print(f"artifact={archive}")
    print(f"checksums={checksums}")
    print(f"sha256={hashlib.sha256(archive.read_bytes()).hexdigest()}")
