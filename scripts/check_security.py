"""Dependency-free source safety audit.

This is a narrow audit of this project's own security invariants (dangerous
shell/execution idioms, public network bindings, unpinned Actions, and
destructive delete patterns). It is a source safety audit, not a full SAST
and not a secret scanner; secret detection lives in the CI Gitleaks gate.
"""

from __future__ import annotations

import ast
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]

PYTHON_FILES = sorted(
    path
    for pattern in ("*.py", "scripts/*.py", "tests/*.py")
    for path in ROOT.glob(pattern)
)
SCRIPT_FILES = sorted([*ROOT.glob("*.ps1"), *ROOT.glob("*.vbs")])
WORKFLOW_FILES = sorted(ROOT.glob(".github/workflows/*.yml"))

TEXT_IDIOM_RULES = (
    (re.compile(r"(?i)\binvoke-expression\b"), "Invoke-Expression"),
    (re.compile(r"(?i)\birm\b\s*\|\s*iex\b"), "irm | iex"),
    (re.compile(r"(?i)\bcurl\b[^\n|]*\|\s*(?:ba)?sh\b"), "curl | sh"),
    (re.compile(r"\b0\.0\.0\.0\b"), "public bind literal"),
    (re.compile(r"\[::\]"), "public IPv6 bind literal"),
)

DYNAMIC_START_PROCESS = re.compile(
    r"""(?ix)\bStart-Process\b(?=[^\n]*(?:\$\(|'\s*\+|\+\s*'))"""
)

DESTRUCTIVE_DELETE = re.compile(r"(?i)\bRemove-Item\b")

USES_LINE = re.compile(r"(?m)^\s*-?\s*uses:\s*(\S+)")
PINNED_USES = re.compile(r"@[0-9a-f]{40}\b")


def audit_python(path: Path, failures: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        failures.append(f"syntax error in {path.name}: {exc}")
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "os" and node.func.attr in {"system", "popen"}:
                failures.append(f"shell-style os.{node.func.attr} in {path.name}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
            failures.append(f"dynamic execution in {path.name}")
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                    failures.append(f"shell=True subprocess in {path.name}")
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            # Needles are constructed so this file does not trip its own scan.
            public_bind_needles = ("0" + ".0.0.0", "[" + "::]")
            if any(needle in node.value for needle in public_bind_needles):
                failures.append(f"public bind literal in {path.name}")


def audit_text_file(path: Path, failures: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    for pattern, label in TEXT_IDIOM_RULES:
        if pattern.search(text):
            failures.append(f"{label} in {path.relative_to(ROOT)}")
    if DYNAMIC_START_PROCESS.search(text):
        failures.append(f"dynamically constructed Start-Process target in {path.relative_to(ROOT)}")


def audit_destructive_delete(path: Path, failures: list[str]) -> None:
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if DESTRUCTIVE_DELETE.search(line) and "-recurse" in line.lower() and "*" in line:
            failures.append(f"recursive wildcard Remove-Item at {path.relative_to(ROOT)}:{number}")


def audit_workflows(failures: list[str]) -> None:
    for path in WORKFLOW_FILES:
        text = path.read_text(encoding="utf-8")
        for match in USES_LINE.finditer(text):
            reference = match.group(1)
            if not PINNED_USES.search(reference):
                failures.append(f"unpinned action reference {reference!r} in {path.relative_to(ROOT)}")
        if "pull_request_target" in text:
            failures.append(f"pull_request_target trigger in {path.relative_to(ROOT)}")
        if re.search(r"(?m)^\s*(?:permissions:\s*)?write-all\s*$", text):
            failures.append(f"write-all permissions in {path.relative_to(ROOT)}")


def main() -> int:
    failures: list[str] = []
    for path in PYTHON_FILES:
        audit_python(path, failures)
    for path in SCRIPT_FILES + WORKFLOW_FILES:
        audit_text_file(path, failures)
    for path in SCRIPT_FILES:
        audit_destructive_delete(path, failures)
    audit_workflows(failures)
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(
        "source safety audit passed "
        f"({len(PYTHON_FILES)} python, {len(SCRIPT_FILES)} script, {len(WORKFLOW_FILES)} workflow files)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
