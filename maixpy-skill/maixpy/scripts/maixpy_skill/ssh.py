from __future__ import annotations

import os
import shutil
import shlex
import subprocess
from dataclasses import dataclass

from .config import Device


DEFAULT_SSH_OPTIONS = [
    "-o",
    "ConnectTimeout=8",
    "-o",
    "StrictHostKeyChecking=accept-new",
]


@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


def quote_remote(command: str) -> str:
    return command


def ssh_command(device: Device, remote_command: str, *, tty: bool = False) -> list[str]:
    cmd = ["ssh", *DEFAULT_SSH_OPTIONS]
    if tty:
        cmd.append("-tt")
    cmd.extend([device.target, quote_remote(remote_command)])
    return with_password_helper(device, cmd)


def scp_to_command(device: Device, local_path: str, remote_path: str) -> list[str]:
    return with_password_helper(device, ["scp", *DEFAULT_SSH_OPTIONS, local_path, f"{device.target}:{remote_path}"])


def scp_from_command(device: Device, remote_path: str, local_path: str) -> list[str]:
    return with_password_helper(device, ["scp", *DEFAULT_SSH_OPTIONS, f"{device.target}:{remote_path}", local_path])


def with_password_helper(device: Device, command: list[str]) -> list[str]:
    if not device.password or not shutil.which("sshpass"):
        return command
    return ["sshpass", "-e", *command]


def command_env(device: Device, env: dict[str, str] | None = None) -> dict[str, str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    if device.password:
        merged_env["SSHPASS"] = device.password
    return merged_env


def run_ssh(device: Device, remote_command: str, *, timeout: int = 30, env: dict[str, str] | None = None) -> CommandResult:
    proc = subprocess.run(
        ssh_command(device, remote_command),
        text=True,
        capture_output=True,
        timeout=timeout,
        env=command_env(device, env),
        check=False,
    )
    return CommandResult(proc.returncode, proc.stdout, proc.stderr)


def shell_join(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)
