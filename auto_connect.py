import bpy


def auto_connect_handler(dummy):
    try:
        # Only run if the addon is registered and server not already running
        prefs = bpy.context.preferences.addons.get("addon")
        if prefs is None:
            print("BlenderMCP: addon not found, skipping auto-connect")
            return
        bpy.ops.blendermcp.start_server()
        print("BlenderMCP: auto-connect triggered")
    except Exception as e:
        print(f"BlenderMCP: auto-connect failed: {e}")


# Register on scene load; delay one tick so the UI is ready
bpy.app.timers.register(lambda: auto_connect_handler(None), first_interval=1.0)
