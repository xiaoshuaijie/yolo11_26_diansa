from __future__ import annotations

import re
import socket
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class DiscoveredDevice:
    host: str
    name: str
    device_class: str


def classify_name(name: str) -> str:
    text = name.lower().replace("_", "-").replace(" ", "-")
    if "maixcam2" in text or "maixcam-2" in text:
        return "maixcam2"
    if "maixcam" in text:
        return "maixcam-pro"
    return "unknown"


def scan_candidates(timeout: int = 4) -> list[DiscoveredDevice]:
    devices: dict[str, DiscoveredDevice] = {}
    for name in _common_mdns_names():
        try:
            host = socket.gethostbyname(name)
        except OSError:
            continue
        devices[name] = DiscoveredDevice(host=host, name=name, device_class=classify_name(name))
    for found in _scan_with_avahi(timeout):
        devices.setdefault(found.name, found)
    for found in _scan_with_dns_sd(timeout):
        devices.setdefault(found.name, found)
    return sorted(devices.values(), key=lambda item: item.name)


def _common_mdns_names() -> list[str]:
    return ["maixcam.local", "maixcam-pro.local", "maixcam2.local"]


def _scan_with_avahi(timeout: int) -> list[DiscoveredDevice]:
    checks = [
        (["avahi-browse", "-a", "-p", "-t"], _parse_avahi_parseable),
        (["avahi-browse", "-a", "-t"], _parse_avahi_text),
        (["avahi-browse", "-a", "-r", "-p", "-t"], _parse_avahi_parseable),
        (["avahi-browse", "-a", "-r", "-t"], _parse_avahi_text),
    ]
    for command, parser in checks:
        devices = parser(_run_avahi(command, timeout))
        if devices:
            return devices
    return []


def _run_avahi(command: list[str], timeout: int) -> str:
    try:
        proc = subprocess.run(
            command,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return proc.stdout
    except FileNotFoundError:
        return ""
    except subprocess.TimeoutExpired as exc:
        return _normalize_stdout(exc.stdout)


def _normalize_stdout(stdout: str | bytes | None) -> str:
    if stdout is None:
        return ""
    if isinstance(stdout, bytes):
        return stdout.decode(errors="ignore")
    return stdout


def _parse_avahi_parseable(stdout: str) -> list[DiscoveredDevice]:
    devices: dict[str, DiscoveredDevice] = {}
    for line in stdout.splitlines():
        lower = line.lower()
        if "maixcam" not in lower:
            continue
        parts = [_unescape_avahi(part.strip()) for part in line.split(";")]
        if len(parts) < 4:
            continue
        name = _clean_avahi_name(parts[3])
        if not name:
            continue
        host = ""
        if len(parts) > 7 and parts[7]:
            host = parts[7]
        elif len(parts) > 6 and parts[6]:
            host = parts[6]
        else:
            host = _name_to_mdns_host(name)
        devices[name] = DiscoveredDevice(host=host, name=name, device_class=classify_name(name))
    return sorted(devices.values(), key=lambda item: item.name)


def _parse_avahi_text(stdout: str) -> list[DiscoveredDevice]:
    devices: dict[str, DiscoveredDevice] = {}
    current_name = ""
    for line in stdout.splitlines():
        lower = line.lower()
        if lower.startswith(("=", "+")):
            current_name = _extract_maixcam_name(line)
            if current_name:
                devices.setdefault(
                    current_name,
                    DiscoveredDevice(
                        host=_name_to_mdns_host(current_name),
                        name=current_name,
                        device_class=classify_name(current_name),
                    ),
                )
            continue
        if not current_name:
            continue
        stripped = line.strip()
        if stripped.startswith("address = [") and stripped.endswith("]"):
            host = stripped.removeprefix("address = [").removesuffix("]")
        elif stripped.startswith("hostname = [") and stripped.endswith("]"):
            host = stripped.removeprefix("hostname = [").removesuffix("]")
        else:
            continue
        devices[current_name] = DiscoveredDevice(
            host=host,
            name=current_name,
            device_class=classify_name(current_name),
        )
    return sorted(devices.values(), key=lambda item: item.name)


def _extract_maixcam_name(text: str) -> str:
    match = re.search(r"\b(maixcam2-[A-Za-z0-9_-]+|maixcam-[A-Za-z0-9_-]+|maixcam2\b|maixcam\b)", text, re.I)
    if not match:
        return ""
    return _clean_avahi_name(match.group(1))


def _clean_avahi_name(name: str) -> str:
    name = re.sub(r"\s+\[[0-9A-Fa-f:.-]+\]$", "", name.strip())
    name = re.sub(r"\s+(SSH|SFTP)$", "", name, flags=re.I)
    return _extract_maixcam_name(name) if " " in name else name


def _name_to_mdns_host(name: str) -> str:
    if name.endswith(".local"):
        return name
    return f"{name}.local"


def _unescape_avahi(value: str) -> str:
    return re.sub(
        r"\\([0-9]{3})",
        lambda match: chr(int(match.group(1), 10)),
        value,
    )


def _scan_with_dns_sd(timeout: int) -> list[DiscoveredDevice]:
    try:
        proc = subprocess.run(
            ["dns-sd", "-B", "_ssh._tcp", "local"],
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        stdout = getattr(exc, "stdout", "") or ""
    else:
        stdout = proc.stdout
    if isinstance(stdout, bytes):
        stdout = stdout.decode(errors="ignore")
    devices: list[DiscoveredDevice] = []
    for line in stdout.splitlines():
        lower = line.lower()
        if "maixcam" not in lower:
            continue
        name = line.split()[-1].strip()
        if not name.endswith(".local"):
            host = f"{name}.local"
        else:
            host = name
        devices.append(DiscoveredDevice(host=host, name=name, device_class=classify_name(name)))
    return devices
