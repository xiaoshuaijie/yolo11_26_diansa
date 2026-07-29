---
name: maixpy
description: 在 MaixCAM/MaixCAM Pro/MaixCAM2 系列设备上开发、运行和调试 MaixPy/MaixCDK 应用时使用
---

# MaixPy

Use this skill to develop MaixPy/MaixCDK applications on MaixCAM-family hardware with a real-device loop: configure device -> generate code -> save locally -> run on device -> inspect logs/images -> iterate.

## Resources

- Use `scripts/maixpy_skill/cli.py` for environment checks, mDNS discovery, device config, development mode, running code, logs, and image artifact collection.
- Read `references/workflow.md` when configuring a device, handling SSH credentials, entering development mode, running code, or debugging helper failures. Chinese audit version: `references/workflow.zh.md`.
- Read `references/maixpy-app-rules.md` before generating or modifying MaixPy application code. Chinese audit version: `references/maixpy-app-rules.zh.md`.

## Non-Negotiables

- Store local config and intermediate files only under the user's current `.maixpy/` directory. Do not write user project state into the skill install directory.
- Save generated application code in the current working directory by default. Prefer `main.py`; if it exists, choose a clear non-destructive filename.
- Use the helper CLI instead of ad hoc SSH/SCP commands when the helper covers the operation.
- Support local Linux and Windows hosts. The MaixCAM-family device remains a Linux remote target.
- Support MaixCAM, MaixCAM Pro, and MaixCAM2. Treat `maixcam`, `maixcam-pro`, and `maixcam pro` as the same MaixCAM-Pro-compatible class unless hardware-specific behavior matters.
- Never expose SSH passwords in chat, command-line arguments, generated code, logs, summaries, or final replies.
- Generated apps must have an explicit exit path and must not rely on SSH or reboot to stop.
- Final generated apps must not display through `/dev/fb`, `/dev/fb0`, other `/dev/fb*` devices, fbdev/framebuffer writes, or framebuffer `mmap`. Do not pass framebuffer paths through display APIs, such as `display.Display(device="/dev/fb0")` or any `device="/dev/fb*"` variant. Use MaixPy display APIs such as `display.Display()` without framebuffer device paths.

## Default References

- MaixPy source: https://github.com/sipeed/MaixPy
- MaixCDK source: https://github.com/sipeed/MaixCDK
- MaixCAM software docs: https://wiki.sipeed.com/maixpy/doc/
- MaixCAM hardware docs: https://wiki.sipeed.com/hardware/zh/maixcam

## Helper Command

Resolve `<skill-dir>` to this skill folder. In this repository it is:

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

Run helper commands from the user's current project directory so `.maixpy/` state is project-local.

## Standard Workflow

1. On first use, read `references/workflow.md`, guide the user through device selection and credential handling, then run `doctor`, `device get`, `device scan` when needed, and `device check`.
2. If the conversation needs user input, use the required Chinese prompt forms:
   - Target device: first list scanned devices, mention `设置 -> 设备信息`, then say `请输入你的设备(IP/设备名)`.
   - Account name: say `请输入你的账户名(默认为:root)`.
   - Password: say `请输入你的密码(默认为:root)` or, for MaixCAM2, `请输入你的密码(默认为:sipeed)`. Do not ask the user to paste passwords into chat.
3. If `device check` succeeds, guide the user with `配置完成, 请描述你的功能`.
4. Generate or edit the application using `references/maixpy-app-rules.md`.
5. Run the application with `python <skill-dir>/scripts/maixpy_skill/cli.py run <local.py>`. Use `--debug-images` only for debug iterations that intentionally execute `save_debug_image()`.
6. Inspect `.maixpy/runs/<run_id>/summary.json`, stdout/stderr logs, pulled device logs, and pulled images before deciding the next edit.

## Credentials

Support exactly two SSH password paths:

- Local credential file: `.maixpy/device_credentials.local.json`, copied from `device_credentials.local.example.json` when needed.
- Terminal input: ask the user to run the helper in their own terminal and type the password into the SSH prompt.

Defaults:

- MaixCAM / MaixCAM Pro: username `root`, password `root`
- MaixCAM2: username `root`, password `sipeed`

Store host, user, name, and device class in normal device config. Store passwords only in `.maixpy/device_credentials.local.json`.

## Code Rules

Before generating MaixPy code, read `references/maixpy-app-rules.md`.

Hard requirements:

- Use `while not app.need_exit():` for normal long-running apps.
- Do not generate unbreakable `while True` loops.
- If the app uses the device key for its own feature, add an on-screen exit button or another explicit UI exit path.
- For camera, display, or vision apps, add or enable debug image saving only during debugging. Final user-facing code must not execute `save_debug_image()` unless the user explicitly asks to keep debug mode enabled.
- Use `display.Display()` for screen output; do not pass framebuffer paths such as `device="/dev/fb0"` to display APIs.

For MaixCDK applications, keep the same device selection, credential safety, launcher, run-log, and artifact collection rules, and follow MaixCDK source/docs for project build/run conventions.

## Run And Development Mode

Use the helper for all normal device operations:

```bash
python <skill-dir>/scripts/maixpy_skill/cli.py device check
python <skill-dir>/scripts/maixpy_skill/cli.py mode status
python <skill-dir>/scripts/maixpy_skill/cli.py mode enter
python <skill-dir>/scripts/maixpy_skill/cli.py mode exit
python <skill-dir>/scripts/maixpy_skill/cli.py run <local.py>
python <skill-dir>/scripts/maixpy_skill/cli.py run <local.py> --debug-images
```

The `run` command must enter and verify development mode on every invocation, then stop and re-check applications under `/maixapp/apps/` before executing user code.

Development mode means launcher daemon forms are stopped and app resources are free for direct code execution. Entering development mode must kill launcher daemon forms first, stop other `/maixapp/apps/` apps, and run a short `display.Display()` refresh program to verify the mode. Do this from the script before every code run because the user may have manually exited development mode between runs. Exiting development mode starts the launcher daemon in the background.

## Failure Handling

- If setup, credentials, run behavior, development mode, or logs are unclear, read `references/workflow.md`.
- If SSH fails, run `device check` and report the exact connection failure without exposing secrets.
- If `/maixapp/apps/` applications cannot be stopped, do not blindly run camera/display code.
- If output is unclear for a vision task, temporarily add or enable debug image saving, rerun with `--debug-images`, then remove or disable it before presenting final user-facing code.
