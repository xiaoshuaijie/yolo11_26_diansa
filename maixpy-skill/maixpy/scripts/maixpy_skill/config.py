from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


SECRET_KEYS = {"password", "passwd", "token", "secret", "key"}
DEFAULT_CREDENTIALS = {
    "maixcam-pro": {"user": "root", "password": "root"},
    "maixcam2": {"user": "root", "password": "sipeed"},
    "unknown": {"user": "root", "password": ""},
}


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Device:
    host: str
    user: str
    name: str = "default"
    device_class: str = "unknown"
    password: str | None = field(default=None, repr=False)

    @property
    def target(self) -> str:
        return f"{self.user}@{self.host}"

    def public_dict(self) -> dict[str, str]:
        return {
            "host": self.host,
            "user": self.user,
            "name": self.name,
            "device_class": self.device_class,
        }


def state_dir(cwd: Path | None = None) -> Path:
    return (cwd or Path.cwd()) / ".maixpy"


def config_path(cwd: Path | None = None) -> Path:
    return state_dir(cwd) / "config.json"


def skill_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def credentials_path(cwd: Path | None = None) -> Path:
    return state_dir(cwd) / "device_credentials.local.json"


def normalize_device_class(value: str | None) -> str:
    text = (value or "unknown").strip().lower().replace("_", "-").replace(" ", "-")
    if text in {"maixcam", "maixcam-pro", "maixcampro"}:
        return "maixcam-pro"
    if text in {"maixcam2", "maixcam-2"}:
        return "maixcam2"
    return text or "unknown"


def _reject_secrets(value: Any, path: str = "") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            key_path = f"{path}.{key}" if path else str(key)
            if str(key).lower() in SECRET_KEYS:
                raise ConfigError(f"refusing to store secret field: {key_path}")
            _reject_secrets(nested, key_path)
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_secrets(nested, f"{path}[{index}]")


def load_config(cwd: Path | None = None) -> dict[str, Any]:
    path = config_path(cwd)
    if not path.exists():
        return {"current_device": None, "devices": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    _reject_secrets(data)
    data.setdefault("current_device", None)
    data.setdefault("devices", {})
    return data


def save_config(data: dict[str, Any], cwd: Path | None = None) -> Path:
    _reject_secrets(data)
    path = config_path(cwd)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def set_device(host: str, user: str, name: str = "default", device_class: str = "unknown", cwd: Path | None = None) -> Device:
    if not host or not user:
        raise ConfigError("host and user are required")
    device = Device(host=host, user=user, name=name, device_class=normalize_device_class(device_class))
    data = load_config(cwd)
    data["current_device"] = name
    data.setdefault("devices", {})[name] = {
        "host": device.host,
        "user": device.user,
        "device_class": device.device_class,
    }
    save_config(data, cwd)
    return device


def load_credentials(cwd: Path | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {
        "defaults": {key: value.copy() for key, value in DEFAULT_CREDENTIALS.items()},
        "devices": {},
    }
    path = credentials_path(cwd)
    if path.exists():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            if isinstance(loaded.get("defaults"), dict):
                for key, value in loaded["defaults"].items():
                    if isinstance(value, dict):
                        normalized = normalize_device_class(key)
                        data["defaults"][normalized] = {**data["defaults"].get(normalized, {}), **value}
            if isinstance(loaded.get("devices"), dict):
                data["devices"] = loaded["devices"]
    return data


def default_user(device_class: str | None, cwd: Path | None = None) -> str:
    credentials = load_credentials(cwd)
    normalized = normalize_device_class(device_class)
    raw = credentials.get("defaults", {}).get(normalized) or credentials.get("defaults", {}).get("unknown", {})
    return str(raw.get("user") or "root")


def default_password(device_class: str | None, cwd: Path | None = None) -> str:
    credentials = load_credentials(cwd)
    normalized = normalize_device_class(device_class)
    raw = credentials.get("defaults", {}).get(normalized) or credentials.get("defaults", {}).get("unknown", {})
    return str(raw.get("password") or "")


def device_password(name: str, host: str, device_class: str, cwd: Path | None = None) -> str | None:
    credentials = load_credentials(cwd)
    devices = credentials.get("devices", {})
    for key in [name, host, device_class]:
        raw = devices.get(key) if isinstance(devices, dict) else None
        if isinstance(raw, dict) and raw.get("password"):
            return str(raw["password"])
    return default_password(device_class, cwd) or None


def get_device(name: str | None = None, cwd: Path | None = None) -> Device:
    data = load_config(cwd)
    selected = name or data.get("current_device")
    if not selected:
        raise ConfigError("no current device configured")
    raw = data.get("devices", {}).get(selected)
    if not raw:
        raise ConfigError(f"device not found: {selected}")
    return Device(
        name=selected,
        host=raw["host"],
        user=raw["user"],
        device_class=normalize_device_class(raw.get("device_class")),
        password=device_password(selected, raw["host"], normalize_device_class(raw.get("device_class")), cwd),
    )


def clear_device(cwd: Path | None = None) -> None:
    save_config({"current_device": None, "devices": {}}, cwd)
