from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ConfigMigrationIntegrationTests(unittest.TestCase):
    def make_upstream(self, root: Path) -> Path:
        upstream = root / "上游 Blender & MCP;"
        package = upstream / "src" / "blender_mcp"
        package.mkdir(parents=True)
        (upstream / "addon.py").write_text("bl_info = {'name': 'Blender MCP'}\n", encoding="utf-8")
        (package / "server.py").write_text("def main(): pass\n", encoding="utf-8")
        (package / "config.py").write_text("# complete local fixture\n", encoding="utf-8")
        return upstream

    def run_cli(self, *args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ROOT / "bmcpw.py"), *args],
            cwd=ROOT,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=15,
            check=False,
        )

    def test_cli_migrates_legacy_config_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bmcpw-integration-") as temp:
            root = Path(temp)
            upstream = self.make_upstream(root)
            config = root / "配置 &;" / "config.toml"
            config.parent.mkdir()
            config.write_text(
                "# preserve this\n"
                "[mcp_servers.other]\ncommand = \"other\"\n\n"
                "[agents.blender]\ncommand = [\"legacy\"]\n",
                encoding="utf-8",
            )
            before_dry_run = config.read_bytes()
            env = os.environ.copy()
            env.update({"CODEX_HOME": str(root / "codex"), "PATH": ""})
            env.pop("BLENDER_EXE", None)
            env.pop("BMCPW_PYTHON", None)

            dry = self.run_cli(
                "configure", "codex", "--config", str(config), "--repo", str(upstream),
                "--python", sys.executable, "--dry-run", env=env,
            )
            self.assertEqual(dry.returncode, 0, dry.stderr)
            self.assertEqual(before_dry_run, config.read_bytes())
            self.assertIn("Dry run; no file was written", dry.stdout)

            merged = self.run_cli(
                "configure", "codex", "--config", str(config), "--repo", str(upstream),
                "--python", sys.executable, env=env,
            )
            self.assertEqual(merged.returncode, 0, merged.stderr)
            parsed = __import__("tomllib").loads(config.read_text(encoding="utf-8"))
            self.assertEqual(parsed["mcp_servers"]["other"]["command"], "other")
            self.assertEqual(parsed["mcp_servers"]["blender"]["command"], sys.executable)
            self.assertNotIn("agents", parsed)
            self.assertTrue(list(config.parent.glob("config.toml.bak-*")))

            repeated = self.run_cli(
                "configure", "codex", "--config", str(config), "--repo", str(upstream),
                "--python", sys.executable, env=env,
            )
            self.assertEqual(repeated.returncode, 0, repeated.stderr)
            self.assertIn("already configured; no file write", repeated.stdout)

    def test_doctor_json_is_machine_readable_in_a_clean_env(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bmcpw-integration-") as temp:
            root = Path(temp)
            env = os.environ.copy()
            env.update({"CODEX_HOME": str(root / "codex"), "PATH": ""})
            env.pop("BLENDER_EXE", None)
            env.pop("BLENDER_MCP_REPO", None)
            result = self.run_cli("doctor", "--json", "--config", str(root / "config.toml"), "--timeout", "0.05", env=env)
            self.assertEqual(result.returncode, 1)
            report = json.loads(result.stdout)
            self.assertEqual(report["schema_version"], 1)
            self.assertEqual(report["overall"], "NOT_READY")
            self.assertNotIn(str(root), result.stdout)


if __name__ == "__main__":
    unittest.main()
