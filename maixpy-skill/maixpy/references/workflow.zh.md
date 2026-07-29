# MaixPy 设备工作流

配置 MaixCAM 系列设备、检查连接、进入开发模式、运行代码或诊断 helper 失败时阅读这个文件。

## Helper 命令

将 `<skill-dir>` 解析为已安装的 `maixpy` skill 文件夹。在本仓库中它是：

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

从用户当前项目目录运行 helper，这样所有状态都会写入该项目的 `.maixpy/` 文件夹。

## 首次使用

首次使用时，不要直接丢命令清单。先用一段简短说明告诉用户需要哪些输入、哪些信息不要发到对话里，以及下一步会做什么。可使用下面这段文案并按实际情况微调：

```text
开始前我需要先确认开发环境和目标设备，这样后面生成的 MaixPy/MaixCDK 代码可以直接跑到板子上验证。

请按下面格式提供信息：

1. 你要做的应用需求：
   例如：摄像头识别二维码、拍照保存图片、屏幕显示传感器数据、MaixCDK 示例工程等。

2. 目标设备：
   如果你知道 IP/主机名，请填写，例如 192.168.1.23 或 maixcam2-xxxx.local。
   如果不知道，我会先扫描 MaixCAM/MaixCAM Pro/MaixCAM2 设备，然后把发现的设备列出来让你选择。即使只发现一台，也会先让你确认。

3. SSH 账户名：
   MaixCAM、MaixCAM Pro、MaixCAM2 默认都是 root。如果你没有改过，可以写 root。

4. 密码处理方式：
   A. 修改当前目录 .maixpy 下的本地凭据配置文件，Python 脚本会默认读取。
   B. 在终端中输入密码。

你可以先只回答应用需求和设备信息；密码等到连接检查时再按上面两种方式处理。
```

然后运行：

```bash
python <skill-dir>/scripts/maixpy_skill/cli.py doctor
python <skill-dir>/scripts/maixpy_skill/cli.py device get
```

如果没有配置设备，先扫描：

```bash
python <skill-dir>/scripts/maixpy_skill/cli.py device scan
```

如果扫描到设备，列出 host/IP、发现名称和设备类别。即使只扫描到一台，也先让用户确认再保存。提示用户可以打开设备的 `设置 -> 设备信息` 查看设备名或 IP，然后说：

```text
请输入你的设备(IP/设备名)
```

如果没有扫描到设备，也提示用户查看 `设置 -> 设备信息`，然后说：

```text
请输入你的设备(IP/设备名)
```

询问账户名：

```text
请输入你的账户名(默认为:root)
```

只保存 host 和用户名：

```bash
python <skill-dir>/scripts/maixpy_skill/cli.py device set --host <ip-or-host> --user <user> --device-class <maixcam-pro|maixcam2>
```

然后检查连接：

```bash
python <skill-dir>/scripts/maixpy_skill/cli.py device check
```

如果设备、账户和密码都配置完成，并且连接检查成功，用这句引导用户描述功能：

```text
配置完成, 请描述你的功能
```

## 密码处理

只支持两种密码处理方式。

### 方式一：本地凭据配置

helper 读取：

```text
.maixpy/device_credentials.local.json
```

如果文件不存在，从模板复制：

```bash
mkdir -p .maixpy
cp <skill-dir>/device_credentials.local.example.json .maixpy/device_credentials.local.json
```

Windows PowerShell：

```powershell
New-Item -ItemType Directory -Force .maixpy
Copy-Item <skill-dir>\device_credentials.local.example.json .maixpy\device_credentials.local.json
```

结构：

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

脚本读取密码后，如果本机安装了 `sshpass`，会通过环境变量 `SSHPASS` 传给 `sshpass -e`。不要把密码放进命令行参数。

### 方式二：终端输入

如果希望使用终端输入，让 `.maixpy/device_credentials.local.json` 中对应密码不存在或为空字符串。如果没有配置密码，或者本机没有 `sshpass`，请用户在自己的终端运行 helper 命令，并在 SSH 密码提示中输入密码。

如果对话过程需要引导用户准备密码，只使用下面的提示，不要求用户把密码发到对话中：

```text
请输入你的密码(默认为:root)
```

MaixCAM2 使用：

```text
请输入你的密码(默认为:sipeed)
```

默认账号：

- MaixCAM / MaixCAM Pro：用户名 `root`，密码 `root`
- MaixCAM2：用户名 `root`，密码 `sipeed`

安全规则：

- 密码只写入 `.maixpy/device_credentials.local.json`。
- 永远不要把密码写入 `.maixpy/config.json`。
- 永远不要把密码放进命令行参数。
- 永远不要把密码写入生成代码、日志、总结或最终回复。
- 普通设备配置只保存非敏感字段：host、user、name、device class。
- 不要打印可能包含 secret 的环境变量。

## 运行代码

通过 helper 运行用户代码：

```bash
python <skill-dir>/scripts/maixpy_skill/cli.py run <local.py>
```

如果是调试迭代，并且需要有意执行 `save_debug_image()`，运行：

```bash
python <skill-dir>/scripts/maixpy_skill/cli.py run <local.py> --debug-images
```

除非用户明确要求保留调试图片保存，否则最终验证不要使用 `--debug-images`。

helper 会：

1. 验证已配置设备。
2. 创建 `.maixpy/runs/<run_id>/`。
3. 进入并验证开发模式，因为用户可能在上一次运行后手动退出开发模式。
4. 运行代码前停止并复查 `/maixapp/apps/` 下正在运行的应用。
5. 上传脚本到 `/tmp/maixpy_skill/<run_id>/main.py`。
6. 在设备上设置 `MAIXPY_SKILL_RUN_DIR`。
7. 只有传入 `--debug-images` 时设置 `MAIXPY_DEBUG_IMAGES=1`；否则设置为 `0`。
8. 用检测到的 `python3` 或 `python` 运行。
9. 本地保存 stdout/stderr。
10. 如果可用，拉取 `/maixapp/tmp/last_run.log`。
11. 从设备 run 目录拉取图片产物。

每次运行后检查：

```text
.maixpy/runs/<run_id>/summary.json
.maixpy/runs/<run_id>/development-mode.log
.maixpy/runs/<run_id>/stdout.log
.maixpy/runs/<run_id>/stderr.log
.maixpy/runs/<run_id>/artifacts/
```

根据日志和图片决定下一次修改。

## 开发模式

使用：

```bash
python <skill-dir>/scripts/maixpy_skill/cli.py mode status
python <skill-dir>/scripts/maixpy_skill/cli.py mode enter
python <skill-dir>/scripts/maixpy_skill/cli.py mode exit
```

开发模式表示 `/maixapp/apps/launcher/launcher daemon` 和 `/maixapp/apps/launcher/launcher_daemon` 已停止，应用资源已释放，可直接运行代码。

`run` helper 每次运行代码前都会执行开发模式进入流程。进入开发模式必须：

1. 尝试杀死 `/maixapp/apps/launcher/launcher_daemon`。
2. 停止 `/maixapp/apps/` 下其他正在运行的应用。
3. 运行一个简短的 MaixPy `display.Display()` 刷新显示程序，以刷新屏幕并验证开发模式可用。

退出开发模式会在后台启动 launcher daemon。

## 失败处理

- 如果 SSH 失败，运行 `device check`，报告准确连接错误，但不要暴露 secret。
- 如果无法停止 `/maixapp/apps/` 下正在运行的应用，不要盲目运行摄像头/屏幕代码。
- 如果 `mode enter` 已启动 daemon 但刷新显示失败，将其视为失败，并检查 stderr 或 `/tmp/launcher-daemon.log`。
- 如果应用卡住，检查生成代码是否有退出路径。
- 如果视觉任务输出不清楚，临时添加或启用调试图片保存，并用 `--debug-images` 重新运行。最终输出给用户前需要移除或关闭，除非用户明确要求保留调试模式。
