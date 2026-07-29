---
name: maixpy
description: 在 MaixCAM/MaixCAM Pro/MaixCAM2 系列设备上开发、运行和调试 MaixPy/MaixCDK 应用时使用
---

# MaixPy 应用开发

使用这个 skill 在 MaixCAM 系列硬件上开发 MaixPy/MaixCDK 应用，并形成真实设备闭环：配置设备 -> 生成代码 -> 保存到本地 -> 在设备上运行 -> 检查日志/图片 -> 继续迭代。

## 资源

- 使用 `scripts/maixpy_skill/cli.py` 完成环境检查、mDNS 发现、设备配置、开发模式、运行代码、日志和图片产物收集。
- 配置设备、处理 SSH 凭据、进入开发模式、运行代码或诊断 helper 失败时，阅读 `references/workflow.md`。中文审核版：`references/workflow.zh.md`。
- 生成或修改 MaixPy 应用代码前，阅读 `references/maixpy-app-rules.md`。中文审核版：`references/maixpy-app-rules.zh.md`。

## 硬约束

- 本地配置文件和中间文件只能保存到用户当前目录的 `.maixpy/` 文件夹下。不要把用户项目状态写入 skill 安装目录。
- 默认把生成的应用代码保存到当前工作目录。优先使用 `main.py`；如果已存在，选择清楚且不会覆盖现有文件的名称。
- helper CLI 已覆盖的操作，不要临时拼 raw SSH/SCP 命令。
- 支持本地 Linux 和 Windows 主机。MaixCAM 系列设备仍按 Linux 远端目标处理。
- 支持 MaixCAM、MaixCAM Pro 和 MaixCAM2。除非硬件特定行为有影响，否则把 `maixcam`、`maixcam-pro` 和 `maixcam pro` 视为兼容 MaixCAM-Pro 的同一类别。
- 永远不要在对话、命令行参数、生成代码、日志、总结或最终回复中泄漏 SSH 密码。
- 生成的应用必须有明确退出路径，不能依赖 SSH 或重启才能停止。
- 最终生成的应用禁止通过 `/dev/fb`、`/dev/fb0`、其他 `/dev/fb*` 设备、fbdev/framebuffer 写入或 framebuffer `mmap` 显示；也禁止把 framebuffer 路径传给显示 API，例如 `display.Display(device="/dev/fb0")` 或任何 `device="/dev/fb*"` 变体。应使用不带 framebuffer 设备路径的 MaixPy `display.Display()` 等显示 API。

## 默认参考

- MaixPy 源码：https://github.com/sipeed/MaixPy
- MaixCDK 源码：https://github.com/sipeed/MaixCDK
- MaixCAM 软件文档：https://wiki.sipeed.com/maixpy/doc/
- MaixCAM 硬件文档：https://wiki.sipeed.com/hardware/zh/maixcam

## Helper 命令

将 `<skill-dir>` 解析为这个 skill 文件夹。在本仓库中它是：

```text
tools/skills/maixpy
```

Linux/macOS 风格 shell：

```bash
python <skill-dir>/scripts/maixpy_skill/cli.py <command>
python3 <skill-dir>/scripts/maixpy_skill/cli.py <command>
```

Windows PowerShell：

```powershell
py -3 <skill-dir>\scripts\maixpy_skill\cli.py <command>
python <skill-dir>\scripts\maixpy_skill\cli.py <command>
```

从用户当前项目目录运行 helper，保证 `.maixpy/` 状态属于当前项目。

## 标准流程

1. 首次使用时，阅读 `references/workflow.md`，引导用户完成设备选择和凭据处理，然后按需运行 `doctor`、`device get`、`device scan` 和 `device check`。
2. 对话过程如果需要用户输入信息，使用指定中文引导：
   - 目标设备：先列出扫描到的设备，提示 `设置 -> 设备信息`，然后说 `请输入你的设备(IP/设备名)`。
   - 账户名：说 `请输入你的账户名(默认为:root)`。
   - 密码：说 `请输入你的密码(默认为:root)`；MaixCAM2 说 `请输入你的密码(默认为:sipeed)`。不要要求用户把密码发到对话中。
3. 如果 `device check` 成功，用 `配置完成, 请描述你的功能` 引导用户描述功能。
4. 按 `references/maixpy-app-rules.md` 生成或修改应用。
5. 用 `python <skill-dir>/scripts/maixpy_skill/cli.py run <local.py>` 运行应用。只有在调试迭代中需要执行 `save_debug_image()` 时，才使用 `--debug-images`。
6. 检查 `.maixpy/runs/<run_id>/summary.json`、stdout/stderr 日志、拉取的设备日志和图片后，再决定下一次修改。

## 凭据

只支持两种 SSH 密码处理方式：

- 本地凭据文件：`.maixpy/device_credentials.local.json`，需要时从 `device_credentials.local.example.json` 复制。
- 终端输入：请用户在自己的终端运行 helper，并在 SSH 密码提示中输入。

默认账号：

- MaixCAM / MaixCAM Pro：用户名 `root`，密码 `root`
- MaixCAM2：用户名 `root`，密码 `sipeed`

普通设备配置只保存 host、user、name 和 device class。密码只保存到 `.maixpy/device_credentials.local.json`。

## 代码规则

生成 MaixPy 代码前，阅读 `references/maixpy-app-rules.md`。

硬要求：

- 普通长运行应用使用 `while not app.need_exit():`。
- 不要生成无法退出的 `while True` 死循环。
- 如果应用把设备按键用于自身功能，必须添加屏幕退出按钮或其他明确 UI 退出路径。
- 对摄像头、屏幕或视觉应用，只在调试时添加或启用调试图片保存。最终输出给用户的代码不应执行 `save_debug_image()`，除非用户明确要求保留调试模式。
- 屏幕输出使用 `display.Display()`；不要直接使用 framebuffer 设备，也不要向显示 API 传入 `device="/dev/fb0"` 等 framebuffer 路径。

对 MaixCDK 应用，沿用同样的设备选择、凭据安全、launcher、运行日志和产物收集规则，并根据 MaixCDK 源码/文档里的项目约定进行构建和运行。

## 运行和开发模式

常规设备操作都使用 helper：

```bash
python <skill-dir>/scripts/maixpy_skill/cli.py device check
python <skill-dir>/scripts/maixpy_skill/cli.py mode status
python <skill-dir>/scripts/maixpy_skill/cli.py mode enter
python <skill-dir>/scripts/maixpy_skill/cli.py mode exit
python <skill-dir>/scripts/maixpy_skill/cli.py run <local.py>
python <skill-dir>/scripts/maixpy_skill/cli.py run <local.py> --debug-images
```

`run` 命令每次执行时都必须先进入并验证开发模式，然后在运行用户代码前停止并复查 `/maixapp/apps/` 下正在运行的应用。

开发模式表示 launcher daemon 形式已停止，应用资源已释放，可直接运行代码。进入开发模式时必须先杀死 launcher daemon 形式，停止其他 `/maixapp/apps/` 应用，并运行一个简短的 `display.Display()` 刷新显示程序来验证模式可用。脚本每次运行代码前都要执行这一步，因为用户可能在两次运行之间手动退出开发模式。退出开发模式会在后台启动 launcher daemon。

## 失败处理

- 如果设置、凭据、运行行为、开发模式或日志不清楚，阅读 `references/workflow.md`。
- 如果 SSH 失败，运行 `device check`，报告准确连接错误，但不要暴露 secret。
- 如果无法停止 `/maixapp/apps/` 下正在运行的应用，不要盲目运行摄像头/屏幕代码。
- 如果视觉任务输出不清楚，临时添加或启用调试图片保存，并用 `--debug-images` 重新运行；最终输出给用户前需要移除或关闭。
