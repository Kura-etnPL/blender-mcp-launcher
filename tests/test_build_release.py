from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from scripts import build_release


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "scripts" / "build_release.py"


class ReleaseArchiveTests(unittest.TestCase):
    def build(self, output: Path) -> Path:
        result = subprocess.run(
            [sys.executable, str(BUILD), "--output-dir", str(output)],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        return output / f"blender-mcp-windows-compat-v{version}.zip"

    def make_checkout(self, destination: Path, newline: bytes) -> None:
        for relative in build_release.ARTIFACT_FILES:
            source = ROOT / relative
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            data = build_release.canonical_file_bytes(source)
            target.write_bytes(data.replace(b"\n", newline))

    def test_archive_matches_between_lf_and_windows_crlf_checkouts(self) -> None:
        """Gate the bytes that differ between a CI and Windows checkout."""

        temp_root = Path(os.environ.get("BMCPW_TEST_TEMP_ROOT", tempfile.gettempdir()))
        temp_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="bmcpw-checkouts-", dir=temp_root) as temp:
            root = Path(temp)
            lf_checkout = root / "lf"
            crlf_checkout = root / "crlf"
            self.make_checkout(lf_checkout, b"\n")
            self.make_checkout(crlf_checkout, b"\r\n")
            lf_archive, _ = build_release.build(root / "lf-dist", lf_checkout)
            crlf_archive, _ = build_release.build(root / "crlf-dist", crlf_checkout)
            self.assertEqual(lf_archive.read_bytes(), crlf_archive.read_bytes())

    def test_archive_is_stored_and_reproducible_in_one_runtime(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bmcpw-release-") as temp:
            root = Path(temp)
            first = self.build(root / "first")
            second = self.build(root / "second")
            self.assertEqual(hashlib.sha256(first.read_bytes()).digest(), hashlib.sha256(second.read_bytes()).digest())
            with zipfile.ZipFile(first) as archive:
                self.assertTrue(archive.infolist())
                for info in archive.infolist():
                    self.assertEqual(info.compress_type, zipfile.ZIP_STORED)
                    self.assertEqual(info.date_time, (2026, 1, 1, 0, 0, 0))
                    self.assertEqual(info.external_attr, 0o100644 << 16)


if __name__ == "__main__":
    unittest.main()
