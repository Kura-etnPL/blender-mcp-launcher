from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile


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
        return output / "blender-mcp-windows-compat-v1.0.0.zip"

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
