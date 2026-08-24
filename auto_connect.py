"""Optional Blender-side auto-connect helper for the upstream ``addon`` module.

The helper is deliberately idempotent: it checks the real server object before
calling the operator, registers one timer, and never registers timers from a
client thread.  It complements upstream auto-start; it does not patch the
upstream server implementation.
"""

from __future__ import annotations

import os

import bpy
from bpy.app.handlers import persistent


ADDON_MODULE = os.environ.get("BLENDER_MCP_ADDON_MODULE", "addon")


def _server():
    return getattr(bpy.types, "blendermcp_server", None)


def _is_running() -> bool:
    server = _server()
    return bool(server is not None and getattr(server, "running", False))


def auto_connect_handler():
    """Start the upstream server once, on Blender's main thread."""
    try:
        if bpy.context.preferences.addons.get(ADDON_MODULE) is None:
            print(f"BlenderMCP: add-on module {ADDON_MODULE!r} is not enabled; skipping auto-connect")
            return None
        if _is_running():
            print("BlenderMCP: server already running; auto-connect is idempotent")
            return None
        result = bpy.ops.blendermcp.start_server()
        if not _is_running():
            print(f"BlenderMCP: start operator returned {result}, but the server is not running")
        else:
            print("BlenderMCP: auto-connect started the server")
    except Exception as exc:
        print(f"BlenderMCP: auto-connect failed: {exc}")
    return None


def _register_timer():
    try:
        registered = bpy.app.timers.is_registered(auto_connect_handler)
    except AttributeError:
        registered = False
    if not registered:
        bpy.app.timers.register(auto_connect_handler, first_interval=1.0, persistent=True)


@persistent
def _on_load_post(_scene):
    _register_timer()


def register():
    if _on_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load_post)
    _register_timer()


def unregister():
    try:
        bpy.app.handlers.load_post.remove(_on_load_post)
    except ValueError:
        pass
    try:
        if bpy.app.timers.is_registered(auto_connect_handler):
            bpy.app.timers.unregister(auto_connect_handler)
    except (AttributeError, ValueError):
        pass


register()
