"""YOLO11 detection with MaixCAM display and wireless MJPEG streaming."""

import socket

from maix import app, camera, display, http, image, nn, time


MODEL_PATH = "/root/text/yolo11n.mud"
CONF_THRESHOLD = 0.5
IOU_THRESHOLD = 0.45
DUAL_BUFFER = True


HTML_PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CyberCAM YOLO11 无线图传</title>
  <style>
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: #111315;
      color: #e8eaed;
      font-family: "Segoe UI", system-ui, sans-serif;
    }
    header, main, footer { width: min(100% - 24px, 880px); margin-inline: auto; }
    header {
      min-height: 64px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }
    h1 { margin: 0; font-size: 20px; font-weight: 650; }
    #status {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: #aeb4bb;
      font-size: 14px;
    }
    #status::before {
      content: "";
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #d05a55;
    }
    #status.online::before { background: #43a66b; }
    .stage {
      width: 100%;
      aspect-ratio: __STREAM_WIDTH__ / __STREAM_HEIGHT__;
      display: grid;
      place-items: center;
      overflow: hidden;
      border: 1px solid #34383d;
      border-radius: 6px;
      background: #050607;
    }
    #stream { width: 100%; height: 100%; object-fit: contain; }
    .toolbar {
      min-height: 64px;
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    button {
      min-height: 38px;
      padding: 0 14px;
      border: 1px solid #454b52;
      border-radius: 6px;
      background: #1c2024;
      color: #f1f3f4;
      font: inherit;
      cursor: pointer;
    }
    button:hover { border-color: #8b949e; background: #262b30; }
    button.active { border-color: #c84b47; color: #ffb3af; }
    .meta { margin-left: auto; color: #8e969f; font-size: 13px; }
    footer { padding: 0 0 20px; color: #777f87; font-size: 12px; }
    canvas { display: none; }
    @media (max-width: 560px) {
      header { min-height: 56px; }
      h1 { font-size: 18px; }
      .toolbar { padding-block: 10px; }
      .meta { width: 100%; margin-left: 0; }
    }
  </style>
</head>
<body>
  <header>
    <h1>CyberCAM YOLO11 无线图传</h1>
    <span id="status">正在连接</span>
  </header>
  <main>
    <section class="stage" id="stage">
      <img id="stream" src="/stream" alt="YOLO11 实时识别画面">
      <canvas id="canvas"></canvas>
    </section>
    <div class="toolbar">
      <button id="record" type="button">开始录制</button>
      <button id="snapshot" type="button">截图</button>
      <button id="fullscreen" type="button">全屏</button>
      <span class="meta">__STREAM_WIDTH__ x __STREAM_HEIGHT__ | MJPEG | YOLO11</span>
    </div>
  </main>
  <footer>视频和截图保存在当前浏览器的下载目录。</footer>
  <script>
    const streamWidth = __STREAM_WIDTH__;
    const streamHeight = __STREAM_HEIGHT__;
    const image = document.getElementById("stream");
    const canvas = document.getElementById("canvas");
    const ctx = canvas.getContext("2d");
    const status = document.getElementById("status");
    const recordButton = document.getElementById("record");
    let recorder = null;
    let chunks = [];
    let drawTimer = null;

    image.addEventListener("load", () => {
      status.textContent = "在线";
      status.classList.add("online");
    });
    image.addEventListener("error", () => {
      status.textContent = "连接中断";
      status.classList.remove("online");
    });

    function prepareCanvas() {
      canvas.width = image.naturalWidth || streamWidth;
      canvas.height = image.naturalHeight || streamHeight;
      ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
    }

    document.getElementById("snapshot").addEventListener("click", () => {
      prepareCanvas();
      const link = document.createElement("a");
      link.download = `cybercam-yolo11-${Date.now()}.jpg`;
      link.href = canvas.toDataURL("image/jpeg", 0.92);
      link.click();
    });

    document.getElementById("fullscreen").addEventListener("click", () => {
      document.getElementById("stage").requestFullscreen().catch(() => {});
    });

    recordButton.addEventListener("click", () => {
      if (recorder && recorder.state === "recording") {
        recorder.stop();
        return;
      }
      if (!window.MediaRecorder || !canvas.captureStream) {
        alert("当前浏览器不支持网页录制，请使用截图功能。");
        return;
      }
      prepareCanvas();
      chunks = [];
      const canvasStream = canvas.captureStream(20);
      recorder = new MediaRecorder(canvasStream, { mimeType: "video/webm" });
      recorder.addEventListener("dataavailable", (event) => {
        if (event.data.size) chunks.push(event.data);
      });
      recorder.addEventListener("stop", () => {
        clearInterval(drawTimer);
        drawTimer = null;
        canvasStream.getTracks().forEach((track) => track.stop());
        const link = document.createElement("a");
        link.download = `cybercam-yolo11-${Date.now()}.webm`;
        link.href = URL.createObjectURL(new Blob(chunks, { type: "video/webm" }));
        link.click();
        setTimeout(() => URL.revokeObjectURL(link.href), 1000);
        recordButton.textContent = "开始录制";
        recordButton.classList.remove("active");
      });
      drawTimer = setInterval(() => {
        ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
      }, 50);
      recorder.start(250);
      recordButton.textContent = "停止录制";
      recordButton.classList.add("active");
    });
  </script>
</body>
</html>
"""


def build_html(stream_width, stream_height):
    return (
        HTML_PAGE.replace("__STREAM_WIDTH__", str(stream_width))
        .replace("__STREAM_HEIGHT__", str(stream_height))
    )


def get_access_host(bind_host):
    if bind_host not in ("0.0.0.0", "::", ""):
        return bind_host

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # UDP connect selects the active interface without sending a packet.
        sock.connect(("8.8.8.8", 80))
        local_ip = sock.getsockname()[0]
        if local_ip and local_ip != "0.0.0.0":
            return local_ip
    except OSError:
        pass
    finally:
        sock.close()

    try:
        local_ip = socket.gethostbyname(socket.gethostname())
        if local_ip and not local_ip.startswith("127."):
            return local_ip
    except OSError:
        pass
    return bind_host


def draw_detections(img, detector, objects):
    for obj in objects:
        img.draw_rect(obj.x, obj.y, obj.w, obj.h, color=image.COLOR_RED)
        label = "{}: {:.2f}".format(detector.labels[obj.class_id], obj.score)
        img.draw_string(obj.x, obj.y, label, color=image.COLOR_RED)


def main():
    detector = nn.YOLO11(model=MODEL_PATH, dual_buff=DUAL_BUFFER)
    stream_width = detector.input_width()
    stream_height = detector.input_height()

    cam = camera.Camera(
        stream_width,
        stream_height,
        detector.input_format(),
    )
    disp = display.Display()
    stream = http.JpegStreamer()
    stream.set_html(build_html(stream_width, stream_height))
    stream.start()

    bind_host = stream.host()
    access_host = get_access_host(bind_host)
    url = "http://{}:{}".format(access_host, stream.port())
    print("YOLO11_MODEL {}".format(MODEL_PATH))
    print("YOLO11_INPUT {}x{}".format(stream_width, stream_height))
    print("CYBERCAM_LISTEN {}:{}".format(bind_host, stream.port()))
    print("CYBERCAM_READY {}".format(url))
    print("Open the URL above from a device on the same hotspot.")

    frame_count = 0
    detection_count = 0
    started_at = time.ticks_ms()
    while not app.need_exit():
        img = cam.read()
        objects = detector.detect(
            img,
            conf_th=CONF_THRESHOLD,
            iou_th=IOU_THRESHOLD,
        )
        draw_detections(img, detector, objects)

        # Both destinations receive the same annotated inference frame.
        stream.write(img)
        disp.show(img)

        frame_count += 1
        detection_count += len(objects)
        now = time.ticks_ms()
        elapsed = now - started_at
        if elapsed >= 5000:
            fps = frame_count * 1000.0 / elapsed
            print(
                "YOLO11_STREAM_FPS {:.1f} DETECTIONS {}".format(
                    fps,
                    detection_count,
                )
            )
            frame_count = 0
            detection_count = 0
            started_at = now


if __name__ == "__main__":
    main()
