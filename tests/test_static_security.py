from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class StaticSecurityTests(unittest.TestCase):
    def test_python_sources_compile_and_avoid_shell_execution(self) -> None:
        for path in ROOT.glob("*.py"):
            if path.name == "test_static_security.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "os"
                ):
                    if node.func.attr in {"system", "popen"}:
                        self.fail(f"shell-style execution API found in {path}: {node.func.attr}")
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id in {"eval", "exec"}:
                        self.fail(f"dynamic code execution found in {path}: {node.func.id}")
            self.assertNotIn("shell=True", path.read_text(encoding="utf-8"))

    def test_network_binding_is_not_public(self) -> None:
        source = (ROOT / "bmcpw.py").read_text(encoding="utf-8")
        # Needles are constructed so this test does not trip the source
        # safety audit's own public-bind constant scan.
        self.assertNotIn("0" + ".0.0.0", source)
        self.assertNotIn("::", source.replace("::1", ""))


if __name__ == "__main__":
    unittest.main()
