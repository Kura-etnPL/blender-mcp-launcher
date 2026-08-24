"""Small dependency-free release source audit."""

from __future__ import annotations

import ast
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
TEXT_FILES = tuple(ROOT.glob("*.py")) + tuple(ROOT.glob("*.ps1")) + tuple(ROOT.glob("*.vbs"))


def main() -> int:
    failures: list[str] = []
    for path in TEXT_FILES:
        text = path.read_text(encoding="utf-8")
        if re.search(r"(?i)(?:invoke-expression|\birm\b\s*\|\s*iex|shell\s*=\s*true)", text):
            failures.append(f"unsafe shell/network idiom in {path.name}")
        if "0.0.0.0" in text:
            failures.append(f"public bind literal in {path.name}")
        if path.suffix == ".py":
            try:
                tree = ast.parse(text, filename=str(path))
            except SyntaxError as exc:
                failures.append(f"syntax error in {path.name}: {exc}")
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name) and node.func.value.id == "os" and node.func.attr in {"system", "popen"}:
                        failures.append(f"shell-style os.{node.func.attr} in {path.name}")
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
                    failures.append(f"dynamic execution in {path.name}")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"security source audit passed ({len(TEXT_FILES)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
