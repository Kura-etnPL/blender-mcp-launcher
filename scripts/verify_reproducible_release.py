"""Verify that release artifacts built by multiple Python runtimes match."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re
import sys


CHECKSUM_LINE = re.compile(r"^(?P<digest>[0-9a-fA-F]{64}) \*(?P<name>[^\r\n]+)$")


def checksum_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root] if root.name == "SHA256SUMS.txt" else []
    return sorted(root.rglob("SHA256SUMS.txt"))


def read_manifest(path: Path) -> tuple[str, Path]:
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(lines) != 1:
        raise SystemExit(f"expected one checksum line in {path}")
    match = CHECKSUM_LINE.fullmatch(lines[0])
    if not match:
        raise SystemExit(f"invalid checksum line in {path}")
    artifact = path.parent / match.group("name")
    if not artifact.is_file():
        raise SystemExit(f"artifact named by {path} is missing: {artifact}")
    actual = hashlib.sha256(artifact.read_bytes()).hexdigest()
    expected = match.group("digest").lower()
    if actual != expected:
        raise SystemExit(f"checksum mismatch for {artifact}: {actual} != {expected}")
    return expected, artifact


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("roots", nargs="+", type=Path)
    args = parser.parse_args(argv)
    manifests = sorted({path for root in args.roots for path in checksum_files(root)})
    if not manifests:
        raise SystemExit("no SHA256SUMS.txt files found")
    results = [read_manifest(path) for path in manifests]
    digests = {digest for digest, _ in results}
    artifacts = {artifact.name for _, artifact in results}
    if len(digests) != 1 or len(artifacts) != 1:
        details = ", ".join(f"{artifact.name}={digest}" for digest, artifact in results)
        raise SystemExit(f"cross-runtime release digests differ: {details}")
    digest = next(iter(digests))
    print(f"cross-runtime release digest verified across {len(results)} builds: {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
