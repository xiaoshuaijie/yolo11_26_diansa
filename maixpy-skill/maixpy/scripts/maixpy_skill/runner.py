from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from . import launcher, logs
from .config import Device
from .ssh import CommandResult, command_env, scp_from_command, scp_to_command, shell_join, ssh_command


IMAGE_GLOBS = "*.jpg *.jpeg *.png *.bmp"


def remote_dir(run_id: str) -> str:
    return f"/tmp/maixpy_skill/{run_id}"


def python_detect_command() -> str:
    return "if command -v python3 >/dev/null 2>&1; then echo python3; else echo python; fi"


def remote_run_command(run_id: str, timeout: int, *, debug_images: bool = False) -> str:
    rdir = remote_dir(run_id)
    main = f"{rdir}/main.py"
    debug_flag = "1" if debug_images else "0"
    return (
        f"cd {rdir!r} && "
        f"export MAIXPY_SKILL_RUN_DIR={rdir!r}; "
        f"export MAIXPY_DEBUG_IMAGES={debug_flag!r}; "
        f"if command -v timeout >/dev/null 2>&1; then timeout {int(timeout)} "
        f"$(if command -v python3 >/dev/null 2>&1; then echo python3; else echo python; fi) {main!r}; "
        f"else $(if command -v python3 >/dev/null 2>&1; then echo python3; else echo python; fi) {main!r}; fi"
    )


def prepare_remote_command(run_id: str) -> str:
    rdir = remote_dir(run_id)
    return f"mkdir -p {rdir!r}/artifacts"


def collect_remote_log_command(run_id: str) -> str:
    rdir = remote_dir(run_id)
    return (
        f"mkdir -p {rdir!r}/collected; "
        "if [ -f /maixapp/tmp/last_run.log ]; then "
        f"cp /maixapp/tmp/last_run.log {rdir!r}/collected/device-last-run.log; "
        "fi; "
        f"find {rdir!r}/artifacts -maxdepth 1 -type f \\( -name '*.jpg' -o -name '*.jpeg' -o -name '*.png' -o -name '*.bmp' \\) -print"
    )


def run_file(
    device: Device,
    local_file: Path,
    *,
    timeout: int = 60,
    cwd: Path | None = None,
    debug_images: bool = False,
) -> Path:
    local_file = local_file.resolve()
    run_id = logs.new_run_id(local_file)
    out_dir = logs.create_run_dir(run_id, cwd)
    rdir = remote_dir(run_id)

    commands: dict[str, object] = {
        "run_id": run_id,
        "device": {"host": device.host, "user": device.user, "device_class": device.device_class},
        "remote_dir": rdir,
        "debug_images": debug_images,
        "enter_development_mode": True,
    }
    logs.write_json(out_dir / "command.json", commands)

    development = _run_local(ssh_command(device, launcher.enter_command()), check=False, env=command_env(device))
    logs.write_text(out_dir / "development-mode.log", development.stdout)
    if development.stderr:
        logs.write_text(out_dir / "development-mode.err.log", development.stderr)
    if development.returncode != 0:
        details = "\n".join(
            part
            for part in [
                development.stdout.strip(),
                development.stderr.strip(),
                f"run_dir={out_dir}",
            ]
            if part
        )
        raise RuntimeError(f"failed to enter development mode before run\n{details}")

    stop = _run_local(ssh_command(device, launcher.ensure_maixapp_apps_stopped_command()), check=False, env=command_env(device))
    logs.write_text(out_dir / "maixapp-stop.log", stop.stdout)
    if stop.stderr:
        logs.write_text(out_dir / "maixapp-stop.err.log", stop.stderr)
    if stop.returncode != 0:
        raise RuntimeError(f"failed to stop running maixapp applications before run\n{stop.stderr}")

    _run_local(ssh_command(device, prepare_remote_command(run_id)), env=command_env(device))
    _run_local(scp_to_command(device, str(local_file), f"{rdir}/main.py"), env=command_env(device))

    proc = _run_local(
        ssh_command(device, remote_run_command(run_id, timeout, debug_images=debug_images)),
        check=False,
        env=command_env(device),
    )
    logs.write_text(out_dir / "stdout.log", proc.stdout)
    logs.write_text(out_dir / "stderr.log", proc.stderr)

    collect = _run_local(ssh_command(device, collect_remote_log_command(run_id)), check=False, env=command_env(device))
    logs.write_text(out_dir / "artifact-list.txt", collect.stdout)
    _pull_optional(device, f"{rdir}/collected/device-last-run.log", out_dir / "device-last-run.log")
    _pull_artifacts(device, rdir, out_dir)

    summary = {
        "run_id": run_id,
        "exit_code": proc.returncode,
        "remote_dir": rdir,
        "image_markers": logs.parse_image_markers(proc.stdout),
        "local_run_dir": str(out_dir),
        "debug_images": debug_images,
    }
    logs.write_json(out_dir / "summary.json", summary)
    return out_dir


def _run_local(command: list[str], *, check: bool = True, env: dict[str, str] | None = None) -> CommandResult:
    proc = subprocess.run(command, text=True, capture_output=True, check=False, env=env)
    if check and proc.returncode != 0:
        raise RuntimeError(f"command failed: {shell_join(command)}\n{proc.stderr}")
    return CommandResult(proc.returncode, proc.stdout, proc.stderr)


def _pull_optional(device: Device, remote_path: str, local_path: Path) -> None:
    proc = subprocess.run(
        scp_from_command(device, remote_path, str(local_path)),
        text=True,
        capture_output=True,
        check=False,
        env=command_env(device),
    )
    if proc.returncode != 0 and local_path.exists():
        local_path.unlink()


def _pull_artifacts(device: Device, rdir: str, out_dir: Path) -> None:
    tmp = out_dir / "artifacts-remote"
    tmp.mkdir(parents=True, exist_ok=True)
    remote_spec = f"{rdir}/artifacts/*"
    proc = subprocess.run(
        scp_from_command(device, remote_spec, str(tmp)),
        text=True,
        capture_output=True,
        check=False,
        env=command_env(device),
    )
    if proc.returncode != 0:
        return
    artifacts = out_dir / "artifacts"
    artifacts.mkdir(exist_ok=True)
    for path in tmp.iterdir():
        if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}:
            shutil.move(str(path), artifacts / path.name)
