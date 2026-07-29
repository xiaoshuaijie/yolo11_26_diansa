# MaixPy App Code Rules

Read this file when generating or modifying MaixPy app code.

These rules apply regardless of whether the assistant is running on Linux or Windows. Generated MaixPy code runs on the MaixCAM-family device, so device paths such as `/tmp/maixpy_skill/...` are Linux-style paths.

## Required Exit Path

Every generated app must be able to exit.

Prefer:

```python
from maix import app

while not app.need_exit():
    ...
```

Do not generate:

```python
while True:
    ...
```

unless there is another explicit exit condition inside the loop.

If the device key is used for application features, add a visible on-screen exit button or another clear UI exit path. The user must not need SSH or a reboot to stop a generated app.

## Debug Images

For camera, display, and vision apps, save a current frame or annotated frame only during debugging.

Final user-facing code must not execute `save_debug_image()` unless the user explicitly asks to keep debug mode enabled. Prefer removing debug image calls before final output. If keeping the helper in code, keep it disabled by default and gate every call.

Use this pattern during debugging:

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

The runner pulls `.jpg`, `.jpeg`, `.png`, and `.bmp` files from the device run artifact directory.

## Display Output

Final generated applications must not display by directly opening or writing framebuffer devices such as `/dev/fb`, `/dev/fb0`, or other `/dev/fb*` paths.

Do not use fbdev/framebuffer access, `mmap` over framebuffer devices, shell commands that write to `/dev/fb*`, or Python file operations such as `open("/dev/fb0", ...)` for display output.

Do not pass framebuffer paths through MaixPy display APIs. These are forbidden:

```python
display.Display(device="/dev/fb0")
display.Display(device="/dev/fb")
display.Display(device="/dev/fb1")
```

Also reject any generated equivalent that sets the display `device` argument to a `/dev/fb*` path.

Use MaixPy display APIs instead, such as:

```python
from maix import display

disp = display.Display()
disp.show(img)
```

## MaixCAM Family

Support MaixCAM, MaixCAM Pro, and MaixCAM2.

Treat MaixCAM and MaixCAM Pro as the same device class for default app behavior. Only split behavior when the user asks for hardware-specific pins, peripherals, or performance assumptions.

## Common Minimal Camera Loop

```python
from maix import app, camera, display

cam = camera.Camera()
disp = display.Display()

while not app.need_exit():
    img = cam.read()
    disp.show(img)
```

Temporarily add or enable debug image saving when needed. Remove or disable it before final output.
