from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import struct
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import bmcpw  # noqa: E402


class ConfigTests(unittest.TestCase):
    def make_upstream(self, root: Path) -> Path:
        upstream = root / "上游 Blender & MCP;"
        (upstream / "src" / "blender_mcp").mkdir(parents=True)
        (upstream / "addon.py").write_text("bl_info = {'name': 'Blender MCP'}\n", encoding="utf-8")
        (upstream / "src" / "blender_mcp" / "server.py").write_text("def main(): pass\n", encoding="utf-8")
        (upstream / "src" / "blender_mcp" / "config.py").write_text("# complete local fixture\n", encoding="utf-8")
        (upstream / "pyproject.toml").write_text(
            '[project]\nname = "blender-mcp"\nversion = "9.9.9"\nrequires-python = ">=3.10"\n',
            encoding="utf-8",
        )
        return upstream

    def test_merge_migrates_legacy_and_preserves_other_servers(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bmcpw-") as temp:
            root = Path(temp)
            upstream = self.make_upstream(root)
            config = root / "config.toml"
            config.write_text(
                "# keep this comment\n"
                "[mcp_servers.other]\ncommand = \"other\"\n\n"
                "[agents.blender]\ncommand = [\"legacy\"]\n"
                "[agents.blender.env]\nOLD = \"value\"\n",
                encoding="utf-8",
            )
            changed, _, notes, backup, _ = bmcpw.configure_codex(
                config=str(config), upstream_path=str(upstream), python_path=sys.executable
            )
            self.assertTrue(changed)
            self.assertIsNotNone(backup)
            self.assertTrue(Path(backup).is_file())
            text = config.read_text(encoding="utf-8")
            self.assertIn("[mcp_servers.other]", text)
            self.assertIn("[mcp_servers.blender]", text)
            self.assertNotIn("[agents.blender]", text)
            self.assertIn("migrated [agents.blender]", " ".join(notes))
            parsed = bmcpw._parse_toml(text)
            self.assertEqual(parsed["mcp_servers"]["other"]["command"], "other")
            self.assertEqual(parsed["mcp_servers"]["blender"]["default_tools_approval_mode"], "writes")

            changed_again, _, notes_again, backup_again, _ = bmcpw.configure_codex(
                config=str(config), upstream_path=str(upstream), python_path=sys.executable
            )
            self.assertFalse(changed_again)
            self.assertIsNone(backup_again)
            self.assertIn("no file write", " ".join(notes_again))

    def test_utf8_bom_and_special_path_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bmcpw-") as temp:
            root = Path(temp) / "中文 &; path"
            root.mkdir()
            upstream = self.make_upstream(root)
            config = root / "配置.toml"
            original = "[mcp_servers.other]\ncommand = \"保留\"\n"
            config.write_bytes(b"\xef\xbb\xbf" + original.encode("utf-8"))
            bmcpw.configure_codex(config=str(config), upstream_path=str(upstream), python_path=sys.executable)
            raw = config.read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
            parsed = bmcpw._parse_toml(raw.decode("utf-8-sig"))
            self.assertEqual(parsed["mcp_servers"]["other"]["command"], "保留")
            self.assertIn("BLENDER_MCP_REPO", raw.decode("utf-8-sig"))

    def test_malformed_config_is_not_written(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bmcpw-") as temp:
            root = Path(temp)
            upstream = self.make_upstream(root)
            config = root / "config.toml"
            config.write_text("[mcp_servers.blender\ncommand = 'broken'\n", encoding="utf-8")
            before = config.read_bytes()
            with self.assertRaises(bmcpw.BMCPWError):
                bmcpw.configure_codex(config=str(config), upstream_path=str(upstream), python_path=sys.executable)
            self.assertEqual(before, config.read_bytes())

    def test_inline_server_map_is_rejected_without_touching_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bmcpw-") as temp:
            root = Path(temp)
            upstream = self.make_upstream(root)
            config = root / "config.toml"
            config.write_text('mcp_servers = { other = { command = "other" } }\n', encoding="utf-8")
            before = config.read_bytes()
            with self.assertRaises(bmcpw.BMCPWError):
                bmcpw.configure_codex(config=str(config), upstream_path=str(upstream), python_path=sys.executable)
            self.assertEqual(before, config.read_bytes())

    def test_incomplete_local_checkout_is_not_written_into_a_dead_wrapper(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bmcpw-") as temp:
            root = Path(temp)
            upstream = self.make_upstream(root)
            (upstream / "src" / "blender_mcp" / "config.py").unlink()
            config = root / "config.toml"
            with mock.patch.object(bmcpw, "_find_uv", return_value=(None, None)):
                with self.assertRaisesRegex(bmcpw.BMCPWError, "source checkout is incomplete"):
                    bmcpw.configure_codex(
                        config=str(config), upstream_path=str(upstream), python_path=sys.executable
                    )
            self.assertFalse(config.exists())


class BlenderDiscoveryTests(unittest.TestCase):
    def make_blender(self, root: Path, name: str = "blender.exe") -> Path:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"MZ\x90\x00 test fixture")
        return path

    def discover_with_running(self, running: tuple[Path, ...], **env: str) -> bmcpw.Discovery:
        with mock.patch.object(bmcpw, "_running_blender_paths", return_value=running), \
             mock.patch.object(bmcpw.shutil, "which", return_value=None), \
             mock.patch.object(bmcpw.sys, "platform", "win32"), \
             mock.patch.dict(os.environ, env, clear=True):
            return bmcpw._discover_blender()

    def test_running_custom_drive_path_with_spaces_and_cjk_is_discovered(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bmcpw-") as temp:
            root = Path(temp) / "E CSoftware 中文 & safe" / "Blender 5.2"
            blender = self.make_blender(root)
            result = self.discover_with_running((blender,))
        self.assertEqual(result.selected, blender.resolve())
        self.assertEqual(result.candidates, (blender.resolve(),))

    def test_explicit_path_has_precedence_over_running_process(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bmcpw-") as temp:
            root = Path(temp)
            explicit = self.make_blender(root / "explicit")
            with mock.patch.object(bmcpw, "_running_blender_paths") as running_discovery:
                result = bmcpw._discover_blender(str(explicit))
        running_discovery.assert_not_called()
        self.assertTrue(result.explicit)
        self.assertEqual(result.selected, explicit.resolve())

    def test_environment_override_has_precedence_over_running_process(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bmcpw-") as temp:
            root = Path(temp)
            explicit = self.make_blender(root / "environment")
            with mock.patch.object(bmcpw, "_running_blender_paths") as running_discovery, \
                 mock.patch.dict(os.environ, {"BLENDER_EXE": str(explicit)}, clear=True):
                result = bmcpw._discover_blender()
        running_discovery.assert_not_called()
        self.assertTrue(result.explicit)
        self.assertEqual(result.selected, explicit.resolve())

    def test_invalid_explicit_path_fails_closed_without_running_fallback(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bmcpw-") as temp:
            with mock.patch.object(bmcpw, "_running_blender_paths") as running_discovery:
                result = bmcpw._discover_blender(str(Path(temp) / "missing & unsafe.exe"))
        running_discovery.assert_not_called()
        self.assertTrue(result.explicit)
        self.assertIsNone(result.selected)
        self.assertEqual(result.error, "BLENDER_EXE does not point to a file")

    def test_running_process_precedes_passive_path_candidate(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bmcpw-") as temp:
            root = Path(temp)
            passive = self.make_blender(root / "passive")
            running = self.make_blender(root / "running")
            with mock.patch.object(bmcpw, "_running_blender_paths", return_value=(running,)), \
                 mock.patch.object(bmcpw.shutil, "which", return_value=str(passive)), \
                 mock.patch.dict(os.environ, {}, clear=True):
                result = bmcpw._discover_blender()
        self.assertEqual(result.selected, running.resolve())
        self.assertEqual(result.candidates[0], running.resolve())

    def test_untrusted_process_metadata_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bmcpw-") as temp:
            root = Path(temp)
            valid = self.make_blender(root / "中文 & safe")
            directory_named_blender = root / "directory" / "blender.exe"
            directory_named_blender.mkdir(parents=True)
            untrusted = root / "blender.exe; Remove-Item"
            untrusted.write_bytes(b"not a trusted executable name")
            with mock.patch.object(bmcpw, "_running_blender_paths", return_value=(
                untrusted, directory_named_blender, valid,
            )), \
                 mock.patch.object(bmcpw.shutil, "which", return_value=None), \
                 mock.patch.dict(os.environ, {}, clear=True):
                result = bmcpw._discover_blender()
        self.assertEqual(result.selected, valid.resolve())
        self.assertNotIn(untrusted.resolve(), result.candidates)
        self.assertNotIn(directory_named_blender.resolve(), result.candidates)


class HealthTests(unittest.TestCase):
    def serve_once(self, handler):
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        ready = threading.Event()

        def run():
            ready.set()
            try:
                conn, _ = listener.accept()
                with conn:
                    handler(conn)
            finally:
                listener.close()

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        ready.wait(1)
        return port, thread

    def test_responds(self) -> None:
        def handler(conn):
            conn.recv(4096)
            conn.sendall(b'{"status":"success","result":{"pong":true}}')

        port, thread = self.serve_once(handler)
        result = bmcpw.probe_health(port=port, timeout=1)
        thread.join(1)
        self.assertEqual(result.state, "RESPONDS")
        self.assertEqual(result.tcp_state, "LISTENING")
        self.assertEqual(result.response["result"]["pong"], True)

    def test_accepts_but_does_not_respond(self) -> None:
        def handler(conn):
            conn.recv(4096)
            time.sleep(0.35)

        port, thread = self.serve_once(handler)
        result = bmcpw.probe_health(port=port, timeout=0.05)
        thread.join(1)
        self.assertEqual(result.state, "ACCEPTS_BUT_NO_RESPONSE")
        self.assertEqual(result.tcp_state, "LISTENING")

    def test_reset_is_classified(self) -> None:
        def handler(conn):
            conn.recv(4096)
            conn.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))

        port, thread = self.serve_once(handler)
        result = bmcpw.probe_health(port=port, timeout=1)
        thread.join(1)
        self.assertEqual(result.state, "RESET")

    def test_malformed_response_is_not_reported_healthy(self) -> None:
        def handler(conn):
            conn.recv(4096)
            conn.sendall(b"not-json")

        port, thread = self.serve_once(handler)
        result = bmcpw.probe_health(port=port, timeout=1)
        thread.join(1)
        self.assertEqual(result.state, "MALFORMED_RESPONSE")

    def test_non_loopback_probe_is_blocked_before_connect(self) -> None:
        with mock.patch.object(bmcpw.socket, "create_connection") as connect:
            result = bmcpw.probe_health(host="203.0.113.7", port=9876, timeout=1)
        self.assertEqual(result.state, "BLOCKED_NON_LOOPBACK")
        connect.assert_not_called()

    def test_probe_limits_are_validated(self) -> None:
        with self.assertRaises(bmcpw.BMCPWError):
            bmcpw.probe_health(port=0, timeout=1)
        with self.assertRaises(bmcpw.BMCPWError):
            bmcpw.probe_health(port=9876, timeout=bmcpw.MAX_TIMEOUT + 1)


class DoctorAndSecurityTests(unittest.TestCase):
    def test_json_report_is_serializable_and_redacted(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bmcpw-") as temp:
            config = Path(temp) / "config.toml"
            config.write_text(
                '[mcp_servers.other]\ncommand = "other"\n'
                '[secrets]\napi_key = "do-not-print"\n',
                encoding="utf-8",
            )
            with mock.patch.dict(os.environ, {"USERPROFILE": r"C:\Users\Alice"}, clear=False):
                report = bmcpw.run_doctor(config=str(config), blender_path=str(Path(temp) / "missing.exe"), timeout=0.05)
                encoded = json.dumps(report.to_dict(), ensure_ascii=False)
            self.assertNotIn("do-not-print", encoded)
            self.assertIn('"schema_version": 1', encoded)
            self.assertIn('"overall": "NOT_READY"', encoded)

    def test_redaction_masks_home_and_token_values(self) -> None:
        with mock.patch.dict(os.environ, {"USERPROFILE": r"C:\Users\Alice"}, clear=False):
            value = bmcpw._redact_text(r"C:\Users\Alice\x token=secret-value")
        self.assertNotIn("Alice", value)
        self.assertNotIn("secret-value", value)
        self.assertIn("<HOME>", value)


if __name__ == "__main__":
    unittest.main()
