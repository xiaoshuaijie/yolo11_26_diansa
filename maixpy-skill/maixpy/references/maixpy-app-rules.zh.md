# MaixPy 应用代码规则

生成或修改 MaixPy 应用代码时阅读这个文件。

无论助手运行在 Linux 还是 Windows，这些规则都适用。生成的 MaixPy 代码运行在 MaixCAM 系列设备上，因此设备路径仍使用 Linux 风格，例如 `/tmp/maixpy_skill/...`。

## 必须有退出路径

每个生成的应用都必须能够退出。

优先使用：

```python
from maix import app

while not app.need_exit():
    ...
```

不要生成：

```python
while True:
    ...
```

除非循环内部有另一个明确退出条件。

如果设备按键被应用功能占用，必须添加可见的屏幕退出按钮或其他清楚的 UI 退出路径。用户不应该必须通过 SSH 或重启设备来停止生成的应用。

## 调试图片

对摄像头、屏幕和视觉应用，只在调试时保存当前帧或标注帧。

最终输出给用户的代码不应执行 `save_debug_image()`，除非用户明确要求保留调试模式。优先在最终输出前移除调试图片调用；如果保留 helper，则默认关闭，并且每次调用都必须有开关保护。

调试时使用这个模式：

```python
import os

DEBUG_IMAGES = os.environ.get("MAIXPY_DEBUG_IMAGES") == "1"


def save_debug_image(img, name="current.jpg"):
    if not DEBUG_IMAGES:
        return
    debug_run_dir = os.environ.get("MAIXPY_SKILL_RUN_DIR", "/tmp/maixpy_skill/manual")
    debug_artifact_dir = f"{debug_run_dir}/artifacts"
    debug_image = f"{debug_artifact_dir}/{name}"
    os.makedirs(debug_artifact_dir, exist_ok=True)
    img.save(debug_image)
    print(f"MAIXPY_SKILL_IMAGE {debug_image}")


if DEBUG_IMAGES:
    save_debug_image(img)
```

runner 会从设备 run artifact 目录拉取 `.jpg`、`.jpeg`、`.png` 和 `.bmp` 文件。

## 显示输出

最终生成的应用程序禁止通过直接打开或写入 framebuffer 设备来显示，例如 `/dev/fb`、`/dev/fb0` 或其他 `/dev/fb*` 路径。

不要使用 fbdev/framebuffer 访问、对 framebuffer 设备做 `mmap`、通过 shell 命令写入 `/dev/fb*`，也不要使用类似 `open("/dev/fb0", ...)` 的 Python 文件操作来显示。

不要把 framebuffer 路径传给 MaixPy 显示 API。下面写法都禁止：

```python
display.Display(device="/dev/fb0")
display.Display(device="/dev/fb")
display.Display(device="/dev/fb1")
```

凡是把 display 的 `device` 参数设置为 `/dev/fb*` 路径的等价生成代码，都要拒绝。

应使用 MaixPy 显示 API，例如：

```python
from maix import display

disp = display.Display()
disp.show(img)
```

## MaixCAM 系列

支持 MaixCAM、MaixCAM Pro 和 MaixCAM2。

默认应用行为中，把 MaixCAM 和 MaixCAM Pro 视为同一设备类别。只有当用户要求硬件特定的引脚、外设或性能假设时，才区分两者。

## 常见最小摄像头循环

```python
from maix import app, camera, display

cam = camera.Camera()
disp = display.Display()

while not app.need_exit():
    img = cam.read()
    disp.show(img)
```

需要时临时添加或启用调试图片保存。最终输出前需要移除或关闭。
