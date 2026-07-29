from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from maixpy_skill import discover, doctor, launcher, runner
    from maixpy_skill.config import ConfigError, clear_device, get_device, load_config, set_device
    from maixpy_skill.ssh import run_ssh
else:
    from . import discover, doctor, launcher, runner
    from .config import ConfigError, clear_device, get_device, load_config, set_device
    from .ssh import run_ssh


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ConfigError as exc:
        if _is_missing_device_config(exc):
            print_device_setup_prompt(str(exc), python_cmd=Path(sys.argv[0]).as_posix())
            return 2
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="maixpy-skill")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("doctor")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("device")
    dsub = p.add_subparsers(dest="device_command", required=True)
    g = dsub.add_parser("get")
    g.set_defaults(func=cmd_device_get)
    s = dsub.add_parser("set")
    s.add_argument("--host", required=True)
    s.add_argument("--user", required=True)
    s.add_argument("--name", default="default")
    s.add_argument("--device-class", default="unknown")
    s.set_defaults(func=cmd_device_set)
    c = dsub.add_parser("clear")
    c.set_defaults(func=cmd_device_clear)
    scan = dsub.add_parser("scan")
    scan.set_defaults(func=cmd_device_scan)
    check = dsub.add_parser("check")
    check.set_defaults(func=cmd_device_check)

    p = sub.add_parser("mode")
    msub = p.add_subparsers(dest="mode_command", required=True)
    for name in ["status", "enter", "exit"]:
        m = msub.add_parser(name)
        m.set_defaults(func=cmd_mode)

    p = sub.add_parser("run")
    p.add_argument("file")
    p.add_argument("--timeout", type=int, default=60)
    p.add_argument("--debug-images", action="store_true", help="enable debug image saving for this run")
    p.set_defaults(func=cmd_run)
    return parser


def cmd_doctor(args: argparse.Namespace) -> int:
    result = doctor.check()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


def cmd_device_get(args: argparse.Namespace) -> int:
    print(json.dumps(load_config(), indent=2, sort_keys=True))
    return 0


def cmd_device_set(args: argparse.Namespace) -> int:
    device = set_device(args.host, args.user, args.name, args.device_class)
    print(json.dumps({"ok": True, "device": device.public_dict()}, indent=2, sort_keys=True))
    return 0


def cmd_device_clear(args: argparse.Namespace) -> int:
    clear_device()
    print("device config cleared")
    return 0


def cmd_device_scan(args: argparse.Namespace) -> int:
    devices = [device.__dict__ for device in discover.scan_candidates()]
    print(json.dumps({"devices": devices}, indent=2, sort_keys=True))
    return 0 if devices else 1


def _is_missing_device_config(exc: ConfigError) -> bool:
    text = str(exc)
    return text == "no current device configured" or text.startswith("device not found:")


def print_device_setup_prompt(reason: str, *, python_cmd: str) -> None:
    print(f"ERROR: {reason}", file=sys.stderr)
    print("未配置当前设备。请先选择并保存 MaixCAM/MaixCAM Pro/MaixCAM2 设备。")
    devices = discover.scan_candidates()
    if devices:
        print("\n已扫描到以下设备：")
        for index, device in enumerate(devices, start=1):
            print(f"{index}. {device.name}  host={device.host}  type={device.device_class}")
    else:
        print("\n未扫描到设备。")
    print("\n请打开设备的 设置 -> 设备信息 查看设备名或者 IP。")
    print("请输入你的设备(IP/设备名)")
    print("请输入你的账户名(默认为:root)")
    print("\n保存配置示例：")
    print(f"python3 {python_cmd} device set --host <IP/设备名> --user <账户名> --device-class <maixcam-pro|maixcam2>")
    print("\n密码处理方式：")
    print("1. 修改当前目录 .maixpy/device_credentials.local.json，Python 脚本会默认读取。")
    print("2. 在终端中输入密码。")
    print("请输入你的密码(默认为:root)")
    print("MaixCAM2: 请输入你的密码(默认为:sipeed)")


def cmd_device_check(args: argparse.Namespace) -> int:
    device = get_device()
    result = run_ssh(device, "echo connected && uname -a", timeout=12)
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    if result.returncode == 0:
        print("配置完成, 请描述你的功能")
    return result.returncode


def cmd_mode(args: argparse.Namespace) -> int:
    device = get_device()
    commands = {
        "status": launcher.status_command(),
        "enter": launcher.enter_command(),
        "exit": launcher.exit_command(),
    }
    result = run_ssh(device, commands[args.mode_command], timeout=15)
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    return result.returncode


def cmd_run(args: argparse.Namespace) -> int:
    device = get_device()
    out_dir = runner.run_file(device, Path(args.file), timeout=args.timeout, debug_images=args.debug_images)
    print(f"RUN_DIR={out_dir}")
    summary = out_dir / "summary.json"
    if summary.exists():
        print(summary.read_text(encoding="utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
