from __future__ import annotations

import importlib.util
import platform
import shutil
import sys


def check() -> dict[str, object]:
    tool_names = ["python3", "python", "py", "ssh", "scp", "sshpass", "avahi-browse", "dns-sd"]
    tools = {name: shutil.which(name) for name in tool_names}
    python_ok = bool(sys.executable or tools["python3"] or tools["python"] or tools["py"])
    mdns = {
        "zeroconf": importlib.util.find_spec("zeroconf") is not None,
        "avahi-browse": bool(tools["avahi-browse"]),
        "dns-sd": bool(tools["dns-sd"]),
    }
    hard_missing = []
    if not python_ok:
        hard_missing.append("python")
    for name in ["ssh", "scp"]:
        if not tools[name]:
            hard_missing.append(name)
    return {
        "ok": not hard_missing,
        "platform": {
            "system": platform.system(),
            "python": sys.executable,
            "python_version": platform.python_version(),
        },
        "tools": tools,
        "mdns": mdns,
        "hard_missing": hard_missing,
        "optional_missing": [name for name in ["sshpass"] if not tools[name]],
    }
