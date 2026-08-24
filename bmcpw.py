"""Windows-first diagnostics and setup CLI for the BlenderMCP companion project.

This module deliberately uses only the Python standard library.  It does not
download code, phone home, modify the registry, or expose a listener.  The
upstream BlenderMCP project remains the server and add-on implementation.
"""

from __future__ import annotations

import argparse
import codecs
import dataclasses
import datetime as _dt
import hashlib
import ipaddress
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import platform
import re
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any, Iterable, Sequence


def _configure_stdio() -> None:
    """Keep Windows CLI output safe for UTF-8 paths and machine-readable JSON."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="backslashreplace")
        except (OSError, ValueError):
            pass


_configure_stdio()


VERSION = "1.0.0"
PROJECT_NAME = "blender-mcp-windows-compat"
PROJECT_URL = "https://github.com/Kura-etnPL/blender-mcp-launcher"
UPSTREAM_URL = "https://github.com/ahujasid/blender-mcp"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9876
DEFAULT_TIMEOUT = 3.0
MAX_TIMEOUT = 30.0
MAX_HEALTH_RESPONSE = 1024 * 1024
REQUIRED_FILES = (
    "bmcpw.py",
    "bmcpw.ps1",
    "install_addon.py",
    "enable_addon.py",
    "enable_auto_start.py",
    "mcp_server_wrapper.py",
)

LOGGER = logging.getLogger("bmcpw")


class BMCPWError(RuntimeError):
    """Expected, actionable command failure."""


@dataclasses.dataclass(frozen=True)
class Discovery:
    selected: Path | None
    candidates: tuple[Path, ...] = ()
    explicit: bool = False
    error: str | None = None


@dataclasses.dataclass(frozen=True)
class UpstreamInfo:
    root: Path | None
    addon_path: Path | None
    module: str | None
    version: str | None
    commit: str | None
    requires_python: str | None
    source_root: Path | None
    source_checkout_incomplete: bool
    error: str | None = None


@dataclasses.dataclass(frozen=True)
class HealthResult:
    host: str
    port: int
    state: str
    tcp_state: str
    message: str
    response: dict[str, Any] | None = None
    elapsed_ms: int | None = None


@dataclasses.dataclass(frozen=True)
class CheckResult:
    code: str
    status: str
    message: str
    details: dict[str, Any] = dataclasses.field(default_factory=dict)
    blocking: bool = False


@dataclasses.dataclass(frozen=True)
class DoctorReport:
    version: str
    checks: tuple[CheckResult, ...]
    overall: str
    recommended_action: str

    @property
    def exit_code(self) -> int:
        return 0 if self.overall != "NOT_READY" else 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "tool": PROJECT_NAME,
            "version": self.version,
            "overall": self.overall,
            "recommended_action": self.recommended_action,
            "checks": [
                {
                    "code": check.code,
                    "status": check.status,
                    "message": check.message,
                    "details": _redact_value(check.details),
                    "blocking": check.blocking,
                }
                for check in self.checks
            ],
        }


def _project_root() -> Path:
    return Path(__file__).resolve().parent


def _env_path(name: str) -> Path | None:
    value = os.environ.get(name, "").strip()
    return Path(value).expanduser() if value else None


def _resolve(path: Path) -> Path:
    try:
        return path.expanduser().resolve(strict=False)
    except OSError:
        return Path(os.path.abspath(os.fspath(path)))


def _path_is_file(path: Path | None) -> bool:
    try:
        return bool(path and path.is_file())
    except OSError:
        return False


def _path_is_dir(path: Path | None) -> bool:
    try:
        return bool(path and path.is_dir())
    except OSError:
        return False


def _unique_paths(paths: Iterable[Path]) -> tuple[Path, ...]:
    result: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        resolved = _resolve(path)
        key = os.path.normcase(os.fspath(resolved))
        if key not in seen:
            seen.add(key)
            result.append(resolved)
    return tuple(result)


def _which(*names: str) -> Path | None:
    for name in names:
        found = shutil.which(name)
        if found:
            return _resolve(Path(found))
    return None


def _safe_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _redact_text(value: str) -> str:
    """Redact home/user paths and obvious credential-shaped values."""

    result = value
    homes: list[Path] = []
    for key in ("USERPROFILE", "HOME", "HOMEDRIVE", "HOMEPATH", "CODEX_HOME"):
        raw = os.environ.get(key, "").strip()
        if raw and ("\\" in raw or "/" in raw):
            homes.append(_resolve(Path(raw)))
    try:
        homes.append(_resolve(Path.home()))
    except OSError:
        pass
    for home in sorted(_unique_paths(homes), key=lambda p: len(os.fspath(p)), reverse=True):
        for candidate in (os.fspath(home), os.fspath(home).replace("\\", "/")):
            if candidate:
                result = result.replace(candidate, "<HOME>")

    username = os.environ.get("USERNAME") or os.environ.get("USER")
    if username:
        result = re.sub(re.escape(username), "<USER>", result, flags=re.IGNORECASE)

    result = re.sub(
        r"(?i)(api[_-]?key|token|secret|password|credential)\s*[=:]\s*[^\s,;]+",
        r"\1=<REDACTED>",
        result,
    )
    return result


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, dict):
        return {str(key): _redact_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact_value(item) for item in value]
    return value


def _toml_string(value: str) -> str:
    # JSON basic strings have the same escaping rules needed by TOML basic
    # strings for the path and environment values used here.
    return json.dumps(str(value), ensure_ascii=False)


def _toml_array(values: Sequence[str]) -> str:
    return "[" + ", ".join(_toml_string(value) for value in values) + "]"


def _parse_toml(text: str) -> dict[str, Any]:
    try:
        import tomllib  # Python 3.11+

        return tomllib.loads(text)
    except ModuleNotFoundError:
        try:
            import tomli  # type: ignore[import-not-found]

            return tomli.loads(text)
        except ModuleNotFoundError as exc:
            raise BMCPWError(
                "TOML validation requires Python 3.11+ or the optional tomli package. "
                "Install Python 3.11 and retry."
            ) from exc
    except Exception as exc:
        raise BMCPWError(f"Codex config TOML is invalid: {exc}") from exc


def _read_utf8(path: Path) -> tuple[str, bool]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise BMCPWError(f"Cannot read {path_label(path)}: {exc}") from exc
    bom = raw.startswith(codecs.BOM_UTF8)
    try:
        return raw.decode("utf-8-sig"), bom
    except UnicodeDecodeError as exc:
        raise BMCPWError(f"File is not valid UTF-8: {path_label(path)}") from exc


def path_label(path: Path | str) -> str:
    return _redact_text(os.fspath(path))


def _run(
    argv: Sequence[str],
    *,
    timeout: float,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a fixed executable/argument vector without a shell."""

    if not argv:
        raise BMCPWError("Cannot run an empty command")
    LOGGER.debug("running executable=%s arg_count=%d", path_label(argv[0]), len(argv) - 1)
    try:
        return subprocess.run(
            [os.fspath(item) for item in argv],
            cwd=os.fspath(cwd) if cwd else None,
            env=env,
            shell=False,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.PIPE if capture else None,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise BMCPWError(f"Executable not found: {path_label(argv[0])}") from exc
    except subprocess.TimeoutExpired as exc:
        raise BMCPWError(
            f"Command timed out after {timeout:g}s: {path_label(argv[0])}"
        ) from exc
    except OSError as exc:
        raise BMCPWError(f"Cannot start {path_label(argv[0])}: {exc}") from exc


def _parse_version(text: str) -> str | None:
    match = re.search(r"(?<!\d)(\d+\.\d+(?:\.\d+)?(?:[-+][0-9A-Za-z.-]+)?)", text)
    return match.group(1) if match else None


def _discover_blender(explicit: str | None = None) -> Discovery:
    requested = explicit if explicit is not None else os.environ.get("BLENDER_EXE", "")
    if requested.strip():
        path = _resolve(Path(requested.strip()))
        return Discovery(path if _path_is_file(path) else None, (path,), True,
                         None if _path_is_file(path) else "BLENDER_EXE does not point to a file")

    candidates: list[Path] = []
    for name in ("blender.exe", "blender"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))

    if sys.platform == "win32":
        roots = [
            _env_path("ProgramFiles"),
            _env_path("ProgramW6432"),
            _env_path("ProgramFiles(x86)"),
            _env_path("LOCALAPPDATA"),
        ]
        for root in [item for item in roots if item]:
            candidates.extend(root.glob("Blender Foundation/Blender */blender.exe"))
            candidates.extend(root.glob("Programs/Blender Foundation/Blender */blender.exe"))
            candidates.extend(root.glob("Steam/steamapps/common/Blender/blender.exe"))
            candidates.extend(root.glob("Programs/Steam/steamapps/common/Blender/blender.exe"))
        user_profile = _env_path("USERPROFILE")
        if user_profile:
            candidates.extend(user_profile.glob("scoop/apps/blender/current/blender.exe"))
            candidates.extend(user_profile.glob("AppData/Local/Programs/Blender Foundation/Blender */blender.exe"))

        # Registry reads are intentionally optional and read-only.  They are a
        # convenience for installed Blender builds, never a requirement.
        try:
            import winreg  # type: ignore[import-not-found]

            for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                for key_name in (
                    r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\blender.exe",
                    r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\blender.exe",
                ):
                    try:
                        with winreg.OpenKey(hive, key_name) as key:
                            value, _ = winreg.QueryValueEx(key, None)
                            if value:
                                candidates.append(Path(value))
                    except OSError:
                        continue
        except ImportError:
            pass

    existing = _unique_paths(path for path in candidates if _path_is_file(_resolve(path)))
    return Discovery(existing[0] if existing else None, existing)


def _looks_like_upstream(root: Path) -> bool:
    return _path_is_file(root / "addon.py") or _path_is_dir(root / "src" / "blender_mcp")


def _discover_upstream(explicit: str | None = None) -> Discovery:
    requested = explicit if explicit is not None else os.environ.get("BLENDER_MCP_REPO", "")
    if requested.strip():
        path = _resolve(Path(requested.strip()))
        return Discovery(path if _looks_like_upstream(path) else None, (path,), True,
                         None if _looks_like_upstream(path) else
                         "BLENDER_MCP_REPO does not contain addon.py or src/blender_mcp")

    candidates = [
        Path.cwd(),
        _project_root().parent / "blender-mcp",
        Path.home() / "blender-mcp",
        Path.home() / "src" / "blender-mcp",
        Path.home() / "projects" / "blender-mcp",
        Path(r"C:\tools\blender-mcp"),
    ]
    existing = _unique_paths(path for path in candidates if _looks_like_upstream(_resolve(path)))
    return Discovery(existing[0] if existing else None, existing)


def _read_pyproject(root: Path) -> tuple[str | None, str | None]:
    path = root / "pyproject.toml"
    if not _path_is_file(path):
        return None, None
    try:
        text, _ = _read_utf8(path)
    except BMCPWError:
        return None, None
    version = None
    requires = None
    try:
        data = _parse_toml(text)
        project = data.get("project", {}) if isinstance(data, dict) else {}
        version = project.get("version") if isinstance(project, dict) else None
        requires = project.get("requires-python") if isinstance(project, dict) else None
    except BMCPWError:
        version_match = re.search(r"(?m)^version\s*=\s*[\"']([^\"']+)", text)
        requires_match = re.search(r"(?m)^requires-python\s*=\s*[\"']([^\"']+)", text)
        version = version_match.group(1) if version_match else None
        requires = requires_match.group(1) if requires_match else None
    return str(version) if version else None, str(requires) if requires else None


def _git_commit(root: Path) -> str | None:
    git = _which("git", "git.exe")
    if not git:
        return None
    try:
        result = _run([git, "-C", str(root), "rev-parse", "--short", "HEAD"], timeout=2)
    except BMCPWError:
        return None
    return result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else None


def _upstream_info(discovery: Discovery) -> UpstreamInfo:
    root = discovery.selected
    if not root:
        return UpstreamInfo(None, None, None, None, None, None, None, False, discovery.error)
    addon = root / "addon.py"
    if not _path_is_file(addon):
        addon = root / "src" / "blender_mcp" / "bundled" / "addon.py"
    source_root = root / "src" if _path_is_dir(root / "src" / "blender_mcp") else None
    version, requires = _read_pyproject(root)
    incomplete = bool(source_root and _path_is_file(source_root / "blender_mcp" / "server.py")
                      and not _path_is_file(source_root / "blender_mcp" / "config.py"))
    return UpstreamInfo(
        root=root,
        addon_path=addon if _path_is_file(addon) else None,
        module=addon.stem if _path_is_file(addon) else None,
        version=version,
        commit=_git_commit(root),
        requires_python=requires,
        source_root=source_root,
        source_checkout_incomplete=incomplete,
        error=discovery.error,
    )


def _python_info(explicit: str | None = None) -> tuple[Path, str | None]:
    requested = explicit if explicit is not None else os.environ.get("BMCPW_PYTHON", "")
    if requested.strip():
        path = _resolve(Path(requested.strip()))
    else:
        path = _resolve(Path(sys.executable))
    if not _path_is_file(path):
        raise BMCPWError(f"Python executable not found: {path_label(path)}")
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if path != _resolve(Path(sys.executable)):
        try:
            result = _run([path, "--version"], timeout=2)
            version = _parse_version(result.stdout + result.stderr) or "unknown"
        except BMCPWError:
            version = None
    return path, version


def _find_uv() -> tuple[Path | None, Path | None]:
    return _which("uvx", "uvx.exe"), _which("uv", "uv.exe")


def _powershell_version() -> tuple[str | None, str | None]:
    for executable in ("pwsh", "pwsh.exe", "powershell", "powershell.exe"):
        path = _which(executable)
        if not path:
            continue
        try:
            result = _run(
                [path, "-NoProfile", "-NonInteractive", "-Command", "$PSVersionTable.PSVersion.ToString()"],
                timeout=2,
            )
        except BMCPWError:
            continue
        if result.returncode == 0:
            return _parse_version(result.stdout), str(path)
    return None, None


def codex_config_path(explicit: str | None = None) -> Path:
    if explicit:
        return _resolve(Path(explicit))
    codex_home = _env_path("CODEX_HOME")
    if codex_home:
        return _resolve(codex_home / "config.toml")
    return _resolve(Path.home() / ".codex" / "config.toml")


def _section_heading(line: str) -> str | None:
    match = re.match(r"^\s*(\[\[?)([^\]]+)(\]\]?)\s*(?:#.*)?$", line.rstrip("\r\n"))
    if not match:
        return None
    opener, name, closer = match.groups()
    if opener == "[[" or closer != "]":
        return "ARRAY:" + name.strip()
    return name.strip()


def _remove_named_sections(text: str, prefixes: Sequence[str]) -> tuple[str, list[str]]:
    """Remove known table sections, including nested tables, only."""

    lines = text.splitlines(keepends=True)
    output: list[str] = []
    removed: list[str] = []
    skip = False
    for line in lines:
        heading = _section_heading(line)
        if heading is not None:
            is_target = any(heading == prefix or heading.startswith(prefix + ".") for prefix in prefixes)
            if heading.startswith("ARRAY:") and any(
                heading[6:] == prefix or heading[6:].startswith(prefix + ".") for prefix in prefixes
            ):
                raise BMCPWError(f"Cannot safely migrate array table [{heading[6:]}]")
            if is_target:
                skip = True
                removed.append(heading)
                continue
            skip = False
        if not skip:
            output.append(line)
    return "".join(output), removed


def _has_inline_mcp_servers(text: str) -> bool:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("["):
            continue
        if re.match(r"^mcp_servers\s*=", stripped):
            return True
    return False


def _server_block(
    *,
    command: Path,
    args: Sequence[str],
    env: dict[str, str],
    cwd: Path | None,
    startup_timeout: int = 20,
    tool_timeout: int = 60,
) -> str:
    lines = [
        "[mcp_servers.blender]",
        f"command = {_toml_string(str(command))}",
        f"args = {_toml_array(list(args))}",
        f"startup_timeout_sec = {int(startup_timeout)}",
        f"tool_timeout_sec = {int(tool_timeout)}",
        'default_tools_approval_mode = "writes"',
    ]
    if cwd:
        lines.append(f"cwd = {_toml_string(str(cwd))}")
    lines.extend(["", "[mcp_servers.blender.env]"])
    for key in sorted(env):
        lines.append(f"{key} = {_toml_string(env[key])}")
    return "\n".join(lines) + "\n"


def _choose_server_command(
    *,
    upstream: UpstreamInfo,
    python: Path,
    uvx: Path | None,
    uv: Path | None,
) -> tuple[Path, list[str], dict[str, str], Path | None, str]:
    """Prefer upstream's official uvx path; use the validated wrapper offline."""

    env = {"DISABLE_TELEMETRY": "true"}
    if uvx:
        return uvx, ["--python", "3.11", "blender-mcp"], env, None, "uvx"
    if uv:
        return uv, ["tool", "run", "--python", "3.11", "blender-mcp"], env, None, "uv"
    if upstream.root and _path_is_file(_project_root() / "mcp_server_wrapper.py"):
        if upstream.source_checkout_incomplete:
            raise BMCPWError(
                "The local BlenderMCP source checkout is incomplete (its telemetry config is missing). "
                "Use the upstream uvx package or a complete reviewed checkout; the companion will not monkey-patch it."
            )
        env["BLENDER_MCP_REPO"] = str(upstream.root)
        return (
            python,
            [str(_project_root() / "mcp_server_wrapper.py")],
            env,
            upstream.root,
            "validated local wrapper",
        )
    raise BMCPWError(
        "No uvx/uv was found and no valid BLENDER_MCP_REPO is available. "
        "Install uv from https://docs.astral.sh/uv/ or set BLENDER_MCP_REPO."
    )


def _config_plan(
    *,
    config_path: Path,
    upstream: UpstreamInfo,
    python: Path,
    uvx: Path | None,
    uv: Path | None,
) -> tuple[str, str, list[str], bool]:
    """Return (old_text, new_text, migration notes, had_bom)."""

    if _path_is_file(config_path):
        old_text, had_bom = _read_utf8(config_path)
        _parse_toml(old_text)
    else:
        old_text, had_bom = "", False
        if config_path.exists() and not config_path.is_file():
            raise BMCPWError(f"Codex config path is not a file: {path_label(config_path)}")

    if _has_inline_mcp_servers(old_text):
        raise BMCPWError(
            "The config uses an inline `mcp_servers = ...` value. "
            "Refusing to rewrite it automatically; convert it to table form first."
        )

    command, args, env, cwd, mode = _choose_server_command(
        upstream=upstream, python=python, uvx=uvx, uv=uv
    )
    block = _server_block(command=command, args=args, env=env, cwd=cwd)
    remainder, removed = _remove_named_sections(old_text, ("mcp_servers.blender", "agents.blender"))
    remainder = remainder.rstrip()
    new_text = (remainder + ("\n\n" if remainder else "") + block).replace("\r\n", "\n")
    # Keep validation strict and verify the generated server shape, while not
    # printing the parsed values (which could include unrelated secrets).
    parsed = _parse_toml(new_text)
    servers = parsed.get("mcp_servers")
    if not isinstance(servers, dict) or not isinstance(servers.get("blender"), dict):
        raise BMCPWError("Generated Codex config did not contain mcp_servers.blender")
    if not servers["blender"].get("command") or not isinstance(servers["blender"].get("args"), list):
        raise BMCPWError("Generated Codex config has an invalid Blender MCP command")
    notes = [f"selected launch mode: {mode}"]
    notes.extend(f"migrated [{heading}]" for heading in removed)
    return old_text, new_text, notes, had_bom


def _backup_path(path: Path) -> Path:
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    return path.with_name(f"{path.name}.bak-{stamp}")


def _atomic_write(path: Path, text: str, *, had_bom: bool) -> None:
    parent = path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise BMCPWError(f"Cannot create config directory {path_label(parent)}: {exc}") from exc
    encoded = (codecs.BOM_UTF8 if had_bom else b"") + text.encode("utf-8")
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=f".{path.name}.", suffix=".tmp", dir=parent, delete=False
        ) as handle:
            temp_name = handle.name
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        check_text = Path(temp_name).read_bytes().decode("utf-8-sig")
        _parse_toml(check_text)
        os.replace(temp_name, path)
        temp_name = None
    except OSError as exc:
        raise BMCPWError(f"Atomic config write failed for {path_label(path)}: {exc}") from exc
    finally:
        if temp_name:
            try:
                Path(temp_name).unlink(missing_ok=True)
            except OSError:
                pass


def configure_codex(
    *,
    config: str | None = None,
    upstream_path: str | None = None,
    python_path: str | None = None,
    dry_run: bool = False,
    server_name: str = "blender",
) -> tuple[bool, Path, list[str], Path | None, str]:
    if server_name != "blender":
        raise BMCPWError("Only the reserved Blender server name is supported by this release")
    config_path = codex_config_path(config)
    upstream = _upstream_info(_discover_upstream(upstream_path))
    python, _ = _python_info(python_path)
    uvx, uv = _find_uv()
    old_text, new_text, notes, had_bom = _config_plan(
        config_path=config_path, upstream=upstream, python=python, uvx=uvx, uv=uv
    )
    changed = old_text != new_text
    backup: Path | None = None
    if dry_run:
        return changed, config_path, notes, None, _redact_text(new_text)
    if not changed:
        return False, config_path, notes + ["already configured; no file write"], None, ""

    if _path_is_file(config_path):
        backup = _backup_path(config_path)
        try:
            shutil.copy2(config_path, backup)
        except OSError as exc:
            raise BMCPWError(f"Cannot create config backup {path_label(backup)}: {exc}") from exc
    _atomic_write(config_path, new_text, had_bom=had_bom)
    try:
        verify_text, _ = _read_utf8(config_path)
        parsed = _parse_toml(verify_text)
        if not isinstance(parsed.get("mcp_servers", {}).get("blender"), dict):
            raise BMCPWError("Post-write validation did not find mcp_servers.blender")
    except Exception as exc:
        if backup and _path_is_file(backup):
            try:
                os.replace(backup, config_path)
            except OSError:
                pass
        if isinstance(exc, BMCPWError):
            raise
        raise BMCPWError(f"Post-write config validation failed: {exc}") from exc
    return True, config_path, notes, backup, ""


def probe_health(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, timeout: float = DEFAULT_TIMEOUT) -> HealthResult:
    try:
        port = int(port)
    except (TypeError, ValueError) as exc:
        raise BMCPWError("Port must be an integer between 1 and 65535") from exc
    if not 1 <= port <= 65535:
        raise BMCPWError("Port must be an integer between 1 and 65535")
    try:
        timeout = float(timeout)
    except (TypeError, ValueError) as exc:
        raise BMCPWError(f"Timeout must be a positive number no greater than {MAX_TIMEOUT:g}s") from exc
    if not 0 < timeout <= MAX_TIMEOUT:
        raise BMCPWError(f"Timeout must be a positive number no greater than {MAX_TIMEOUT:g}s")
    if not _is_loopback(host):
        return HealthResult(
            host, port, "BLOCKED_NON_LOOPBACK", "NOT_ATTEMPTED",
            "Refused a non-loopback health probe; this companion is local-only.",
            None, 0,
        )
    started = time.monotonic()
    tcp_state = "CLOSED"
    try:
        with socket.create_connection((host, int(port)), timeout=timeout) as client:
            tcp_state = "LISTENING"
            client.settimeout(timeout)
            request = json.dumps({"type": "ping", "params": {}}, separators=(",", ":")).encode("utf-8")
            client.sendall(request)
            chunks: list[bytes] = []
            while sum(len(chunk) for chunk in chunks) < MAX_HEALTH_RESPONSE:
                data = client.recv(8192)
                if not data:
                    break
                chunks.append(data)
                try:
                    response = json.loads(b"".join(chunks).decode("utf-8"))
                    elapsed = int((time.monotonic() - started) * 1000)
                    return HealthResult(
                        host, port, "RESPONDS", tcp_state,
                        "MCP ping returned a JSON response", response, elapsed,
                    )
                except json.JSONDecodeError:
                    continue
            if not chunks:
                return HealthResult(host, port, "RESET", tcp_state,
                                    "Listener closed the connection before returning data",
                                    None, int((time.monotonic() - started) * 1000))
            return HealthResult(host, port, "MALFORMED_RESPONSE", tcp_state,
                                "Listener returned data that was not a complete JSON response",
                                None, int((time.monotonic() - started) * 1000))
    except ConnectionRefusedError:
        state = "CLOSED"
        message = f"No listener accepted TCP on {host}:{port}"
    except socket.timeout:
        state = "ACCEPTS_BUT_NO_RESPONSE" if tcp_state == "LISTENING" else "TIMEOUT"
        message = (f"TCP connected but no MCP response within {timeout:g}s"
                   if tcp_state == "LISTENING" else
                   f"TCP connection timed out after {timeout:g}s")
    except ConnectionResetError:
        state = "RESET"
        message = "Listener reset the connection while handling the MCP ping"
    except OSError as exc:
        state = "RESET" if tcp_state == "LISTENING" else "CLOSED"
        message = f"Socket diagnostic failed: {exc}"
    return HealthResult(host, port, state, tcp_state, message, None,
                        int((time.monotonic() - started) * 1000))


def _health_action(result: HealthResult) -> str:
    actions = {
        "CLOSED": "Start Blender with the BlenderMCP add-on enabled, then check the configured port.",
        "TIMEOUT": "Check local firewall/process health and retry with a shorter diagnostic timeout.",
        "ACCEPTS_BUT_NO_RESPONSE": "The listener accepts TCP but did not service ping; inspect Blender's UI/system console and the upstream Windows issue.",
        "RESET": "Restart the Blender add-on and inspect for a stale server/client thread or WinError 10054.",
        "MALFORMED_RESPONSE": "The listener returned bytes that were not one complete JSON response; inspect the server/client protocol and restart the add-on.",
        "BLOCKED_NON_LOOPBACK": "Use 127.0.0.1, localhost, or ::1; this companion does not probe remote hosts.",
        "RESPONDS": "No transport failure detected by the bounded MCP ping.",
    }
    return actions.get(result.state, "Inspect the local BlenderMCP process and configuration.")


def _is_loopback(host: str) -> bool:
    lowered = host.strip().lower()
    if lowered == "localhost":
        return True
    try:
        normalized = lowered.strip("[]")
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _installed_addon_candidates(blender_version: str | None = None) -> tuple[Path, ...]:
    candidates: list[Path] = []
    explicit = _env_path("BLENDER_MCP_ADDONS_DIR")
    if explicit:
        candidates.extend([explicit / "addon.py", explicit / "blender_mcp.py"])
    resources = _env_path("BLENDER_USER_RESOURCES")
    if resources:
        candidates.extend([
            resources / "scripts" / "addons" / "addon.py",
            resources / "scripts" / "addons" / "blender_mcp.py",
        ])
    if sys.platform == "win32":
        appdata = _env_path("APPDATA")
        if appdata:
            base = appdata / "Blender Foundation" / "Blender"
            candidates.extend(base.glob("*/scripts/addons/addon.py"))
            candidates.extend(base.glob("*/scripts/addons/blender_mcp.py"))
            candidates.extend(base.glob("*/scripts/addons/*/addon.py"))
    return _unique_paths(path for path in candidates if _path_is_file(_resolve(path)))


def _check(code: str, status: str, message: str, *, details: dict[str, Any] | None = None, blocking: bool = False) -> CheckResult:
    return CheckResult(code, status, message, details or {}, blocking)


def run_doctor(
    *,
    config: str | None = None,
    upstream_path: str | None = None,
    blender_path: str | None = None,
    port: int = DEFAULT_PORT,
    host: str = DEFAULT_HOST,
    timeout: float = DEFAULT_TIMEOUT,
) -> DoctorReport:
    checks: list[CheckResult] = []
    checks.append(_check(
        "os", "PASS" if sys.platform == "win32" else "WARN",
        f"{platform.system()} {platform.release()} detected" if sys.platform == "win32"
        else "This CLI is Windows-first; running outside Windows is not a release verification.",
        details={"platform": sys.platform, "release": platform.release()},
    ))

    ps_version, ps_exe = _powershell_version()
    checks.append(_check(
        "powershell", "PASS" if ps_version else "WARN",
        f"PowerShell {ps_version} detected" if ps_version else "PowerShell was not detected; the .ps1 entry point cannot run.",
        details={"version": ps_version, "executable": ps_exe},
    ))

    blender = _discover_blender(blender_path)
    if blender.selected:
        result = None
        try:
            result = _run([blender.selected, "--version"], timeout=timeout)
            blender_version = _parse_version(result.stdout + result.stderr)
        except BMCPWError:
            blender_version = None
        checks.append(_check(
            "blender", "PASS" if blender_version else "WARN",
            f"Blender {blender_version} detected" if blender_version else
            f"Blender executable found but --version did not return a version: {path_label(blender.selected)}",
            details={"path": str(blender.selected), "version": blender_version,
                     "candidates": [str(item) for item in blender.candidates]},
            blocking=not bool(blender_version),
        ))
        if len(blender.candidates) > 1:
            checks.append(_check(
                "blender_multiple", "WARN",
                f"Multiple Blender installations detected; selected {path_label(blender.selected)}.",
                details={"count": len(blender.candidates)},
            ))
    else:
        checks.append(_check(
            "blender", "FAIL",
            blender.error or "Blender executable was not found. Set BLENDER_EXE or install Blender.",
            details={"candidates": [str(item) for item in blender.candidates]}, blocking=True,
        ))
        blender_version = None

    upstream = _upstream_info(_discover_upstream(upstream_path))
    if upstream.root:
        checks.append(_check(
            "upstream_repo", "PASS",
            f"BlenderMCP repository detected at {path_label(upstream.root)}",
            details={"path": str(upstream.root), "version": upstream.version, "commit": upstream.commit},
        ))
        if upstream.addon_path:
            checks.append(_check(
                "addon_source", "PASS",
                f"Upstream add-on source found; Blender module identifier is {upstream.module!r}.",
                details={"path": str(upstream.addon_path), "module": upstream.module},
            ))
        else:
            checks.append(_check("addon_source", "FAIL", "Upstream add-on source was not found.", blocking=True))
        if upstream.source_checkout_incomplete:
            checks.append(_check(
                "upstream_source_checkout", "WARN",
                "This source checkout imports a private telemetry config that is absent; use upstream uvx or an upstream release/PR with the fallback instead of monkey-patching it.",
                details={"issue": "upstream #328 / PR #329", "path": str(upstream.source_root)},
            ))
        if upstream.version:
            checks.append(_check(
                "upstream_version", "PASS",
                f"Upstream package version {upstream.version} detected" +
                (f" at commit {upstream.commit}" if upstream.commit else "."),
                details={"version": upstream.version, "commit": upstream.commit,
                         "requires_python": upstream.requires_python},
            ))
        else:
            checks.append(_check("upstream_version", "WARN", "Upstream package version is unknown; verify the checkout before reporting compatibility."))
    else:
        checks.append(_check(
            "upstream_repo", "WARN",
            upstream.error or "BlenderMCP repository was not found. Set BLENDER_MCP_REPO for local source operations.",
        ))

    try:
        python, python_version = _python_info()
    except BMCPWError as exc:
        python, python_version = Path(sys.executable), None
        checks.append(_check("python", "FAIL", str(exc), blocking=True))
    else:
        python_status = "PASS"
        python_message = f"Python {python_version or 'unknown'} detected at {path_label(python)}"
        if sys.version_info >= (3, 14):
            python_status = "WARN"
            python_message += "; upstream issue #314 reports a Python 3.14 compatibility risk—prefer managed Python 3.11"
        checks.append(_check("python", python_status, python_message,
                             details={"path": str(python), "version": python_version,
                                      "upstream_requires": upstream.requires_python if upstream else None}))

    uvx, uv = _find_uv()
    checks.append(_check(
        "uv", "PASS" if uvx or uv else "WARN",
        f"uv tooling detected ({path_label(uvx or uv)})" if uvx or uv else
        "uv/uvx was not found; Codex configuration can fall back to the validated local wrapper when dependencies are installed.",
        details={"uvx": str(uvx) if uvx else None, "uv": str(uv) if uv else None},
    ))

    codex = _which("codex", "codex.exe")
    codex_version = None
    if codex:
        try:
            result = _run([codex, "--version"], timeout=timeout)
            codex_version = _parse_version(result.stdout + result.stderr) or _safe_text(result.stdout).strip()[:80]
        except BMCPWError:
            pass
    checks.append(_check(
        "codex", "PASS" if codex and codex_version else "WARN",
        f"Codex CLI detected ({codex_version or 'version unavailable'})" if codex else
        "Codex CLI was not found on PATH; the desktop/app may still share the config, but CLI registration cannot be verified.",
        details={"path": str(codex) if codex else None, "version": codex_version},
    ))

    config_path = codex_config_path(config)
    if _path_is_file(config_path):
        try:
            text, _ = _read_utf8(config_path)
            parsed = _parse_toml(text)
        except BMCPWError as exc:
            checks.append(_check("codex_config_syntax", "FAIL", str(exc),
                                 details={"path": str(config_path)}, blocking=True))
            parsed = {}
        else:
            servers = parsed.get("mcp_servers", {}) if isinstance(parsed, dict) else {}
            has_blender = isinstance(servers, dict) and isinstance(servers.get("blender"), dict)
            legacy = isinstance(parsed.get("agents"), dict) and isinstance(parsed.get("agents", {}).get("blender"), dict)
            checks.append(_check(
                "codex_config", "PASS" if has_blender else "FAIL",
                "Codex config is valid and contains [mcp_servers.blender]." if has_blender else
                "Codex config is valid but BlenderMCP is not registered; run `bmcpw configure codex`.",
                details={"path": str(config_path), "has_blender": has_blender, "legacy_agents_blender": legacy},
                blocking=not has_blender,
            ))
            if legacy:
                checks.append(_check("codex_legacy_config", "WARN",
                                     "Legacy [agents.blender] configuration is present; migrate it with `bmcpw configure codex`.",
                                     details={"legacy_section": "agents.blender"}))
    else:
        checks.append(_check(
            "codex_config", "FAIL",
            f"Codex config was not found at {path_label(config_path)}; run `bmcpw configure codex`.",
            details={"path": str(config_path)}, blocking=True,
        ))

    installed = _installed_addon_candidates(blender_version)
    checks.append(_check(
        "addon_install", "PASS" if installed else "WARN",
        f"Installed Blender add-on candidate found ({path_label(installed[0])})." if installed else
        "No installed BlenderMCP add-on file was detected in known user resource folders; run `bmcpw install`.",
        details={"candidates": [str(item) for item in installed]},
    ))

    if not _is_loopback(host):
        checks.append(_check(
            "network_binding", "FAIL",
            f"Configured diagnostic host {host!r} is not loopback; refusing to bless LAN/public exposure.",
            details={"host": host}, blocking=True,
        ))
    else:
        checks.append(_check(
            "network_binding", "PASS",
            f"Diagnostics target loopback only ({host}:{port}); this project does not open a listener.",
            details={"host": host, "port": port},
        ))

    health = probe_health(host, port, timeout)
    health_status = "PASS" if health.state == "RESPONDS" else "FAIL"
    checks.append(_check(
        "server_health", health_status,
        f"{health.state}: {health.message} {_health_action(health)}",
        details={"state": health.state, "tcp_state": health.tcp_state, "host": host,
                 "port": port, "elapsed_ms": health.elapsed_ms},
        blocking=health.state != "RESPONDS",
    ))

    missing = [name for name in REQUIRED_FILES if not _path_is_file(_project_root() / name)]
    checks.append(_check(
        "launcher_integrity", "PASS" if not missing else "FAIL",
        "Required launcher files are present." if not missing else
        f"Required launcher files are missing: {', '.join(missing)}",
        details={"missing": missing}, blocking=bool(missing),
    ))

    if any(check.status == "FAIL" for check in checks):
        overall = "NOT_READY"
        action = "Resolve FAIL checks, then rerun `bmcpw doctor --json`."
    elif any(check.status == "WARN" for check in checks):
        overall = "READY_WITH_WARNINGS"
        action = "Review WARN checks before connecting an AI client; rerun `bmcpw doctor --json` after setup."
    else:
        overall = "READY"
        action = "Local preflight passed; still connect only a trusted MCP client and keep Blender on loopback."
    return DoctorReport(VERSION, tuple(checks), overall, action)


def _state_dir() -> Path:
    if sys.platform == "win32":
        root = _env_path("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")
    else:
        root = _env_path("XDG_STATE_HOME") or (Path.home() / ".local" / "state")
    return _resolve(root / "blender-mcp-launcher")


def _pid_file() -> Path:
    return _state_dir() / "blender.pid.json"


def _write_pid(pid: int, executable: Path) -> None:
    _atomic_write(_pid_file(), json.dumps({"pid": int(pid), "executable": str(executable), "version": VERSION}) + "\n", had_bom=False)


def _read_pid() -> tuple[int, Path] | None:
    path = _pid_file()
    if not _path_is_file(path):
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        pid = int(data.get("pid"))
        executable = _resolve(Path(str(data.get("executable", ""))))
        if pid <= 0 or not executable.name.lower().startswith("blender"):
            return None
        return pid, executable
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def _remove_pid() -> None:
    try:
        _pid_file().unlink(missing_ok=True)
    except OSError:
        pass


def _pid_process_name(pid: int) -> str | None:
    if sys.platform != "win32":
        try:
            os.kill(pid, 0)
            return "process"
        except OSError:
            return None
    try:
        result = _run(["tasklist.exe", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"], timeout=2)
    except BMCPWError:
        return None
    for line in result.stdout.splitlines():
        if line.startswith('"'):
            return line.split('"', 2)[1]
    return None


def start_blender(*, blender_path: str | None = None, hidden: bool = False, debug: bool = False) -> int:
    blender = _discover_blender(blender_path)
    if not blender.selected:
        raise BMCPWError(blender.error or "Blender was not found; set BLENDER_EXE")
    existing = _read_pid()
    if existing:
        existing_pid, existing_executable = existing
        existing_name = _pid_process_name(existing_pid)
        if existing_name and existing_name.lower().startswith("blender"):
            LOGGER.info("launcher-owned Blender is already running: pid=%d executable=%s", existing_pid, path_label(existing_executable))
            return existing_pid
        _remove_pid()
    installed = _installed_addon_candidates()
    if hidden and not installed:
        raise BMCPWError(
            "Hidden start refused because no installed BlenderMCP add-on was detected. "
            "Run `bmcpw install` first so a failed hidden launch is not silent."
        )
    kwargs: dict[str, Any] = {
        "args": [str(blender.selected)],
        "cwd": str(blender.selected.parent),
        "shell": False,
        "stdin": subprocess.DEVNULL,
    }
    if hidden:
        kwargs.update({"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL})
        if sys.platform == "win32":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
            kwargs["startupinfo"] = startupinfo
    elif debug:
        kwargs.update({"stdout": None, "stderr": None})
        if sys.platform == "win32":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    else:
        kwargs.update({"stdout": None, "stderr": None})
    try:
        process = subprocess.Popen(**kwargs)
    except OSError as exc:
        raise BMCPWError(f"Could not start Blender without a shell: {exc}") from exc
    _write_pid(process.pid, blender.selected)
    return process.pid


def stop_blender() -> str:
    record = _read_pid()
    if not record:
        return "No launcher-owned Blender PID record was found."
    pid, executable = record
    name = _pid_process_name(pid)
    if not name:
        _remove_pid()
        return "Blender process was not running; removed the stale PID record."
    if not name.lower().startswith("blender"):
        raise BMCPWError(f"Refusing to stop PID {pid}: process name is {name!r}, not Blender")
    if sys.platform == "win32":
        result = _run(["taskkill.exe", "/PID", str(pid), "/T"], timeout=10)
        if result.returncode not in (0, 128):
            raise BMCPWError(f"taskkill failed for Blender PID {pid}: {_redact_text(result.stderr.strip())}")
    else:
        try:
            os.kill(pid, 15)
        except OSError as exc:
            raise BMCPWError(f"Could not stop Blender PID {pid}: {exc}") from exc
    _remove_pid()
    return f"Stopped launcher-owned Blender PID {pid} ({path_label(executable)})."


def _run_blender_script(blender: Path, script_name: str, env_overrides: dict[str, str], timeout: float = 60) -> subprocess.CompletedProcess[str]:
    script = _resolve(_project_root() / script_name)
    if not _path_is_file(script):
        raise BMCPWError(f"Launcher script is missing: {path_label(script)}")
    env = os.environ.copy()
    env.update(env_overrides)
    return _run([blender, "--background", "--python", str(script)], timeout=timeout, env=env, cwd=blender.parent)


def install_addon(*, blender_path: str | None = None, upstream_path: str | None = None, save_startup_file: bool = False) -> str:
    blender = _discover_blender(blender_path)
    if not blender.selected:
        raise BMCPWError(blender.error or "Blender was not found; set BLENDER_EXE")
    upstream = _upstream_info(_discover_upstream(upstream_path))
    if not upstream.root or not upstream.addon_path:
        raise BMCPWError("Upstream addon.py was not found; set BLENDER_MCP_REPO to a real BlenderMCP checkout")
    env = {
        "BLENDER_MCP_REPO": str(upstream.root),
        "BLENDER_MCP_ADDON_MODULE": upstream.module or "addon",
        "DISABLE_TELEMETRY": "true",
    }
    result = _run_blender_script(blender.selected, "install_addon.py", env)
    if result.returncode != 0:
        raise BMCPWError(_redact_text((result.stderr or result.stdout).strip())[-2000:])
    messages = [_redact_text((result.stdout or result.stderr).strip()) or "Blender add-on installed and enabled."]
    if save_startup_file:
        env["BLENDER_MCP_SAVE_HOMEFILE"] = "1"
        auto = _run_blender_script(blender.selected, "enable_auto_start.py", env)
        if auto.returncode != 0:
            raise BMCPWError(_redact_text((auto.stderr or auto.stdout).strip())[-2000:])
        messages.append(_redact_text((auto.stdout or auto.stderr).strip()) or "Blender startup file saved.")
    else:
        messages.append("Auto-start remains the upstream scene default; use --save-startup-file only if replacing Blender's startup file is intentional.")
    return "\n".join(messages)


def _configure_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", help="Codex config.toml path (default: ~/.codex/config.toml)")
    parser.add_argument("--repo", dest="upstream_path", help="BlenderMCP checkout (or BLENDER_MCP_REPO)")
    parser.add_argument("--python", dest="python_path", help="Python executable for local wrapper fallback")
    parser.add_argument("--dry-run", action="store_true", help="Show the redacted merge without writing")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bmcpw",
        description="Windows compatibility, diagnostics, setup, and Codex integration for BlenderMCP.",
    )
    parser.add_argument("--version", action="version", version=f"bmcpw {VERSION}")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("version", help="Print the launcher version")
    sub.add_parser("help", help="Show this help")

    doctor = sub.add_parser("doctor", aliases=["diagnose"], help="Run bounded local diagnostics")
    doctor.add_argument("--json", action="store_true", help="Emit redacted machine-readable JSON")
    doctor.add_argument("--config", help="Codex config.toml path")
    doctor.add_argument("--repo", dest="upstream_path", help="BlenderMCP checkout")
    doctor.add_argument("--blender", dest="blender_path", help="Blender executable")
    doctor.add_argument("--host", default=os.environ.get("BLENDER_HOST", DEFAULT_HOST))
    doctor.add_argument("--port", type=int, default=int(os.environ.get("BLENDER_MCP_PORT", DEFAULT_PORT)))
    doctor.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)

    status = sub.add_parser("status", help="Show local MCP transport state")
    status.add_argument("--json", action="store_true")
    status.add_argument("--host", default=os.environ.get("BLENDER_HOST", DEFAULT_HOST))
    status.add_argument("--port", type=int, default=int(os.environ.get("BLENDER_MCP_PORT", DEFAULT_PORT)))
    status.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)

    start = sub.add_parser("start", help="Start Blender with safe argument handling")
    start.add_argument("--blender", dest="blender_path")
    start.add_argument("--hidden", action="store_true", help="Start hidden after add-on preflight")
    start.add_argument("--debug", action="store_true", help="Start with a visible debug console")

    stop = sub.add_parser("stop", help="Stop the launcher-owned Blender process")
    stop.set_defaults()

    install = sub.add_parser("install", help="Install and enable the upstream Blender add-on")
    install.add_argument("--blender", dest="blender_path")
    install.add_argument("--repo", dest="upstream_path")
    install.add_argument("--save-startup-file", action="store_true", help="Explicitly replace Blender's startup file")

    configure = sub.add_parser("configure", help="Safely update Codex MCP configuration")
    configure_sub = configure.add_subparsers(dest="configure_command")
    codex = configure_sub.add_parser("codex", help="Register BlenderMCP in Codex config.toml")
    _configure_args(codex)
    top_codex = sub.add_parser("codex", help="Alias for configure codex")
    _configure_args(top_codex)
    return parser


def _print_report(report: DoctorReport) -> None:
    for check in report.checks:
        print(f"[{check.status}] {check.code}: {check.message}")
    print(f"Overall: {report.overall}")
    print(f"Recommended action: {report.recommended_action}")


def main(argv: Sequence[str] | None = None) -> int:
    _configure_logging()
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command
    try:
        if command in (None, "help"):
            parser.print_help()
            return 0
        if command == "version":
            print(f"bmcpw {VERSION}")
            return 0
        if command in ("doctor", "diagnose"):
            report = run_doctor(
                config=args.config,
                upstream_path=args.upstream_path,
                blender_path=args.blender_path,
                port=args.port,
                host=args.host,
                timeout=args.timeout,
            )
            if args.json:
                print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
            else:
                _print_report(report)
            return report.exit_code
        if command == "status":
            result = probe_health(args.host, args.port, args.timeout)
            payload = {
                "host": args.host, "port": args.port, "state": result.state,
                "tcp_state": result.tcp_state, "message": result.message,
                "elapsed_ms": result.elapsed_ms,
            }
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print(f"{result.state}: {result.message}")
                print(f"TCP: {result.tcp_state}; action: {_health_action(result)}")
            return 0 if result.state == "RESPONDS" else 1
        if command == "start":
            pid = start_blender(blender_path=args.blender_path, hidden=args.hidden, debug=args.debug)
            print(f"Started Blender PID {pid}; health check: bmcpw status")
            return 0
        if command == "stop":
            print(stop_blender())
            return 0
        if command == "install":
            print(install_addon(blender_path=args.blender_path, upstream_path=args.upstream_path,
                                save_startup_file=args.save_startup_file))
            return 0
        if command == "configure" and args.configure_command != "codex":
            parser.error("configure requires the `codex` subcommand")
        if command in ("codex", "configure"):
            changed, config_path, notes, backup, preview = configure_codex(
                config=args.config, upstream_path=args.upstream_path,
                python_path=args.python_path, dry_run=args.dry_run,
            )
            print(f"Codex config: {path_label(config_path)}")
            for note in notes:
                print(note)
            if args.dry_run:
                print("Dry run; no file was written. Proposed redacted config:")
                print(preview, end="" if preview.endswith("\n") else "\n")
            elif changed:
                print(f"Updated [mcp_servers.blender] atomically; backup: {path_label(backup) if backup else 'not needed'}")
            return 0
        parser.error(f"Unknown command: {command}")
    except BMCPWError as exc:
        print(f"ERROR: {_redact_text(str(exc))}", file=sys.stderr)
        return 2


def _configure_logging() -> None:
    if LOGGER.handlers:
        return
    LOGGER.setLevel(logging.INFO)
    try:
        log_dir = _state_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            log_dir / "bmcpw.log", maxBytes=512 * 1024, backupCount=2, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        LOGGER.addHandler(handler)
    except OSError:
        # Diagnostics remain usable if a locked-down machine rejects the local
        # log directory.  No fallback writes to a broad or system directory.
        LOGGER.addHandler(logging.NullHandler())


if __name__ == "__main__":
    raise SystemExit(main())
