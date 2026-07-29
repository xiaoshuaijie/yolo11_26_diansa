from __future__ import annotations

import shlex


LAUNCHER = "/maixapp/apps/launcher/launcher"
DAEMON_PATTERN = "/maixapp/apps/launcher/launcher daemon"
LAUNCHER_DAEMON = "/maixapp/apps/launcher/launcher_daemon"
DAEMON_MATCH_PATTERNS = (
    "/maixapp/apps/launcher/[l]auncher daemon",
    "/maixapp/apps/launcher/launcher[_]daemon",
)
MAIXAPP_APPS_ROOT = "/maixapp/apps/"


def daemon_running_test_command() -> str:
    return " || ".join(f"pgrep -f {pattern!r} >/dev/null" for pattern in DAEMON_MATCH_PATTERNS)


def status_command() -> str:
    return (
        f"if {daemon_running_test_command()}; then echo daemon=running; else echo daemon=stopped; fi; "
        f"if ps x | grep -F {LAUNCHER!r} | grep -v grep | grep -v launcher_daemon > /dev/null; then echo launcher=running; else echo launcher=stopped; fi; "
        "if [ -f /maixapp/auto_start.txt ]; then printf 'autostart='; cat /maixapp/auto_start.txt; else echo autostart=none; fi"
    )


def kill_launcher_daemon_command() -> str:
    return (
        f"pkill -f {DAEMON_MATCH_PATTERNS[1]!r} >/dev/null 2>&1 || true; "
        f"pkill -f {DAEMON_MATCH_PATTERNS[0]!r} >/dev/null 2>&1 || true; "
        "echo launcher_daemon=stopped"
    )


def start_launcher_daemon_command() -> str:
    return (
        f"if test -x {LAUNCHER_DAEMON!r}; then "
        f"nohup {LAUNCHER_DAEMON!r} >/tmp/launcher-daemon.log 2>&1 & "
        f"elif test -x {LAUNCHER!r}; then "
        f"nohup {LAUNCHER!r} daemon >/tmp/launcher-daemon.log 2>&1 & "
        "else echo launcher_daemon=missing >&2; exit 1; "
        "fi; "
        "sleep 0.5; "
        f"if {daemon_running_test_command()}; then echo daemon=running; else echo daemon=not_running >&2; exit 1; fi"
    )


def refresh_display_command() -> str:
    script = "\n".join(
        [
            "from maix import display, image",
            "disp = display.Display()",
            "img = image.Image(disp.width(), disp.height(), image.Format.FMT_RGB888, bg=image.COLOR_BLACK)",
            "disp.show(img)",
            "print('display_refreshed=ok')",
        ]
    )
    return (
        "$(if command -v python3 >/dev/null 2>&1; then echo python3; else echo python; fi) "
        f"-c {shlex.quote(script)}"
    )


def enter_command() -> str:
    refresh = refresh_display_command()
    return (
        f"{kill_launcher_daemon_command()}; "
        f"{ensure_maixapp_apps_stopped_command()}; "
        f"if {refresh}; then :; else echo display_refresh=failed >&2; exit 1; fi; "
        "echo development_mode=entered"
    )


def exit_command() -> str:
    return (
        f"{start_launcher_daemon_command()}; "
        "echo development_mode=exited"
    )


def stop_launcher_app_command() -> str:
    return (
        f"ps w | grep -F {LAUNCHER!r} | grep -v ' daemon' | grep -v grep | awk '{{print $1}}' | xargs -r kill >/dev/null 2>&1 || true; "
        "sleep 0.2; "
        "echo launcher_app=stopped"
    )


def maixapp_app_processes_command() -> str:
    return (
        "ps w | awk -v self=$$ "
        f"{_maixapp_process_filter()} || true"
    )


def maixapp_app_pids_command() -> str:
    return (
        "ps w | awk -v self=$$ "
        f"{_maixapp_pid_filter()} || true"
    )


def _maixapp_process_filter() -> str:
    return (
        "'index($0, \"/maixapp/apps/\") "
        "&& $1 != self "
        "&& $0 !~ /launcher daemon/ "
        "&& $0 !~ /launcher_daemon/ "
        "&& $0 !~ /awk -v self/ "
        "{print}'"
    )


def _maixapp_pid_filter() -> str:
    return (
        "'index($0, \"/maixapp/apps/\") "
        "&& $1 != self "
        "&& $0 !~ /launcher daemon/ "
        "&& $0 !~ /launcher_daemon/ "
        "&& $0 !~ /awk -v self/ "
        "{print $1}'"
    )


def ensure_maixapp_apps_stopped_command() -> str:
    pids = maixapp_app_pids_command()
    processes = maixapp_app_processes_command()
    return (
        f"pids=$({pids}); "
        "if [ -n \"$pids\" ]; then "
        "echo maixapp_apps=running; "
        f"{processes}; "
        "kill $pids >/dev/null 2>&1 || true; "
        "sleep 0.5; "
        f"pids=$({pids}); "
        "if [ -n \"$pids\" ]; then kill -9 $pids >/dev/null 2>&1 || true; sleep 0.2; fi; "
        "fi; "
        f"pids=$({pids}); "
        "if [ -n \"$pids\" ]; then "
        "echo maixapp_apps=still_running >&2; "
        f"{processes} >&2; "
        "exit 1; "
        "fi; "
        "echo maixapp_apps=stopped"
    )
