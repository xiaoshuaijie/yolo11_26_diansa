# MaixPy Device Workflow

Read this file when configuring a MaixCAM-family device, checking connectivity, entering development mode, running code, or diagnosing helper failures.

## Helper Command

Resolve `<skill-dir>` to the installed `maixpy` skill folder. In this repository it is:

```text
tools/skills/maixpy
```

Linux/macOS-style shells:

```bash
python <skill-dir>/scripts/maixpy_skill/cli.py <command>
python3 <skill-dir>/scripts/maixpy_skill/cli.py <command>
```

Windows PowerShell:

```powershell
py -3 <skill-dir>\scripts\maixpy_skill\cli.py <command>
python <skill-dir>\scripts\maixpy_skill\cli.py <command>
```

Run helper commands from the user's current project directory so all state is stored under that project's `.maixpy/` folder.

## First Use

Do not start first use by dumping commands only. First send a short guide that explains what input is needed, what should not be sent into chat, and what happens next. Use this text, adjusted to the current situation:

```text
Before we start, I need to confirm the local environment and target device so the MaixPy/MaixCDK code we generate can be run on real hardware.

Please reply with:

1. App requirement:
   Example: scan QR codes with the camera, capture and save images, show sensor data on screen, build a MaixCDK example app, etc.

2. Target device:
   If you know the IP/host, provide it, such as 192.168.1.23 or maixcam2-xxxx.local.
   If you do not know it, I will scan for MaixCAM/MaixCAM Pro/MaixCAM2 devices and show you the discovered list to choose from. Even if only one device is found, I will ask you to confirm it first.

3. SSH account name:
   The default username for MaixCAM, MaixCAM Pro, and MaixCAM2 is root. If you have not changed it, use root.

4. Password handling:
   A. Edit the local credential config file under the current .maixpy folder; the Python helper reads it by default.
   B. Type the password in the terminal.

You can start by answering only the app requirement and device info. We will handle the password later through one of the two supported paths.
```

Then run:

```bash
python <skill-dir>/scripts/maixpy_skill/cli.py doctor
python <skill-dir>/scripts/maixpy_skill/cli.py device get
```

If no device is configured, scan:

```bash
python <skill-dir>/scripts/maixpy_skill/cli.py device scan
```

If scan finds devices, list host/IP, discovered name, and device class. Even if only one device is found, ask the user to confirm before saving it. Tell the user they can open `设置 -> 设备信息` on the device to check the device name or IP, then say:

```text
请输入你的设备(IP/设备名)
```

If scan finds no device, still tell the user to check `设置 -> 设备信息`, then say:

```text
请输入你的设备(IP/设备名)
```

Ask for the account name with:

```text
请输入你的账户名(默认为:root)
```

Save host and username only:

```bash
python <skill-dir>/scripts/maixpy_skill/cli.py device set --host <ip-or-host> --user <user> --device-class <maixcam-pro|maixcam2>
```

Then check connectivity:

```bash
python <skill-dir>/scripts/maixpy_skill/cli.py device check
```

If the device, account, and password are configured and the connection check succeeds, guide the user into the app requirement with:

```text
配置完成, 请描述你的功能
```

## Password Handling

Support exactly two password handling paths.

### Path 1: Local credential config

The helper reads:

```text
.maixpy/device_credentials.local.json
```

If the file does not exist, copy the example:

```bash
mkdir -p .maixpy
cp <skill-dir>/device_credentials.local.example.json .maixpy/device_credentials.local.json
```

Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force .maixpy
Copy-Item <skill-dir>\device_credentials.local.example.json .maixpy\device_credentials.local.json
```

Shape:

```json
{
  "defaults": {
    "maixcam-pro": {"user": "root", "password": "root"},
    "maixcam2": {"user": "root", "password": "sipeed"}
  },
  "devices": {
    "default": {"password": "root"},
    "maixcam2-4ea6": {"password": "sipeed"},
    "192.168.1.23": {"password": "root"}
  }
}
```

When a password is loaded from config and `sshpass` is installed, the helper uses `sshpass -e` and passes the value through `SSHPASS`. Never put passwords in command-line arguments.

### Path 2: Terminal input

To use terminal input, leave the matching password absent or empty in `.maixpy/device_credentials.local.json`. If no password is configured, or `sshpass` is unavailable, ask the user to run the helper in their own terminal and type the password into the SSH prompt.

If the conversation needs to guide the user to prepare a password, use only these prompts and do not ask the user to paste the password into chat:

```text
请输入你的密码(默认为:root)
```

For MaixCAM2:

```text
请输入你的密码(默认为:sipeed)
```

Default credentials:

- MaixCAM / MaixCAM Pro: username `root`, password `root`
- MaixCAM2: username `root`, password `sipeed`

Security rules:

- Store passwords only in `.maixpy/device_credentials.local.json`.
- Never store passwords in `.maixpy/config.json`.
- Never put passwords in command-line arguments.
- Never write passwords to generated code, logs, summaries, or final replies.
- Store only non-secret device fields in normal config: host, user, name, and device class.
- Do not print environment variables that may contain secrets.

## Run Code

Run user code through:

```bash
python <skill-dir>/scripts/maixpy_skill/cli.py run <local.py>
```

For debug iterations that intentionally execute `save_debug_image()`, run:

```bash
python <skill-dir>/scripts/maixpy_skill/cli.py run <local.py> --debug-images
```

Do not use `--debug-images` for final validation unless the user explicitly asks to keep debug image saving enabled.

The helper will:

1. Verify the configured device.
2. Create `.maixpy/runs/<run_id>/`.
3. Enter and verify development mode, because the user may have manually exited development mode since the previous run.
4. Stop and re-check any running applications under `/maixapp/apps/` before running code.
5. Upload the script to `/tmp/maixpy_skill/<run_id>/main.py`.
6. Set `MAIXPY_SKILL_RUN_DIR` on the device.
7. Set `MAIXPY_DEBUG_IMAGES=1` only when `--debug-images` is passed; otherwise set it to `0`.
8. Run with detected `python3` or `python`.
9. Save stdout/stderr locally.
10. Pull `/maixapp/tmp/last_run.log` if available.
11. Pull image artifacts from the device run directory.

After each run, inspect:

```text
.maixpy/runs/<run_id>/summary.json
.maixpy/runs/<run_id>/development-mode.log
.maixpy/runs/<run_id>/stdout.log
.maixpy/runs/<run_id>/stderr.log
.maixpy/runs/<run_id>/artifacts/
```

Use logs and images to decide the next edit.

## Development Mode

Use:

```bash
python <skill-dir>/scripts/maixpy_skill/cli.py mode status
python <skill-dir>/scripts/maixpy_skill/cli.py mode enter
python <skill-dir>/scripts/maixpy_skill/cli.py mode exit
```

Development mode means `/maixapp/apps/launcher/launcher daemon` and `/maixapp/apps/launcher/launcher_daemon` are stopped so app resources are free for direct code execution.

The `run` helper executes the development-mode entry flow before every code run. Entering development mode must:

1. Try to kill `/maixapp/apps/launcher/launcher_daemon`.
2. Stop any other running application under `/maixapp/apps/`.
3. Run a short MaixPy `display.Display()` refresh program to refresh the screen and verify development mode is usable.

Exiting development mode starts the launcher daemon in the background.

## Failure Handling

- If SSH fails, run `device check` and report the exact connection failure without exposing secrets.
- If applications under `/maixapp/apps/` cannot be stopped, do not blindly run camera/display code.
- If `mode enter` reaches daemon startup but display refresh fails, treat it as failed and inspect stderr or `/tmp/launcher-daemon.log`.
- If the app hangs, inspect whether generated code has an exit path.
- If output is unclear for a vision task, temporarily add or enable debug image saving and rerun with `--debug-images`. Remove or disable it before presenting final user-facing code unless the user explicitly asks to keep debug mode enabled.
