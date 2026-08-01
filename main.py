"""MaixCAM / MaixCAM2 钢珠混合识别与图传。

正常帧使用 NPU YOLO26；丢失时才启用轻量模板跟踪、亮度归一化复检和
低频全画面模板重定位。程序只识别和发送位置，不参与运动控制。
"""

import struct

from maix import app, camera, display, err, image, nn, pinmap, sys, time, uart

from ball_position import (
    AdaptiveAlphaBetaFilter,
    axis_point,
    position_from_pixel,
    validate_calibration,
)
from hybrid_tracker import HybridBallTracker


# ============================== 功能开关 ==============================

DEBUG_LOG = False
DRAW_DEBUG = True
SHOW_FPS = True
USE_WEBRTC = True
PRINT_PROTOCOL = False
LENS_CORR_ENABLE = False
LENS_CORR_STRENGTH = 0.6

# dual_buff=False：检测结果对应当前输入帧，降低位置反馈延迟。
LOW_LATENCY_MODE = True

# ============================== text ==============================
def draw_calibration_grid(frame):
    color = image.Color.from_rgb(80, 80, 80)

    for x in range(0, FRAME_WIDTH, 20):
        frame.draw_line(x, 0, x, FRAME_HEIGHT - 1, color, 1)
        frame.draw_string(x + 1, 1, str(x), color=color, scale=0.6)

    for y in range(0, FRAME_HEIGHT, 20):
        frame.draw_line(0, y, FRAME_WIDTH - 1, y, color, 1)
        frame.draw_string(1, y + 1, str(y), color=color, scale=0.6)

# ============================== STM32 UART ==============================

UART_DEVICE = "/dev/ttyS0"
UART_BAUDRATE = 115200
UART_FRAME_HEAD = b"\xAA\x55"
UART_FRAME_SIZE = 13

for pin, function in {
    "A16": "UART0_TX",
    "A17": "UART0_RX",
}.items():
    err.check_raise(
        pinmap.set_pin_function(pin, function),
        "Failed to set {} to {}".format(pin, function),
    )

serial = uart.UART(UART_DEVICE, UART_BAUDRATE)


# ============================== 模型与标定 ==============================

MAIXCAM_MODEL_PATH = (
    "/root/text/best.mud"
)
MAIXCAM2_MODEL_PATH = (
    "models/yolo26_all_maixcam2_yolo26_640_160/yolo26_all.mud"
)


def model_path_for_device(device_name):
    normalized = device_name.strip().lower()
    if normalized == "maixcam2":
        return MAIXCAM2_MODEL_PATH
    if normalized in ("maixcam", "maixcam-pro", "maixcam_pro"):
        return MAIXCAM_MODEL_PATH
    raise ValueError("unsupported device: {}".format(device_name))


detector = nn.YOLO26(
    model=model_path_for_device(sys.device_name()),
    dual_buff=not LOW_LATENCY_MODE,
)

FRAME_WIDTH = detector.input_width()
FRAME_HEIGHT = detector.input_height()

# 青色线只帮助安装和完成厘米换算，不限制识别必须在线上。
# AXIS_START_PX = (5, FRAME_HEIGHT // 2)
# AXIS_END_PX = (FRAME_WIDTH - 5, FRAME_HEIGHT // 2)

# 白色导轨的两个内侧端点；青色十字与实物红色标记对齐。
AXIS_START_PX = (21, 80)     # 左端，-12.5 cm
AXIS_END_PX = (460, 80)      # 右端，+12.5 cm
AXIS_START_CM = -12.5
AXIS_END_CM = 12.5


def debug_print(message):
    if DEBUG_LOG:
        print(message)


def clamp_int(value, lower, upper):
    return max(lower, min(upper, int(round(value))))


def build_ball_uart_frame(
    valid, position_cm, velocity_pixel_s, quality, frame_time_ms
):
    """Build the STM32 fixed-length, little-endian 13-byte frame."""
    if not valid:
        position_cm = 0.0
        velocity_pixel_s = 0.0
        quality = 0.0

    payload = struct.pack(
        "<BhhBI",
        1 if valid else 0,
        clamp_int(position_cm * 100.0, -32768, 32767),
        clamp_int(velocity_pixel_s * 10.0, -32768, 32767),
        clamp_int(quality * 100.0, 0, 100),
        int(frame_time_ms) & 0xFFFFFFFF,
    )
    frame = bytearray(UART_FRAME_HEAD + payload)
    checksum = 0
    for byte in frame:
        checksum ^= byte
    frame.append(checksum)

    if len(frame) != UART_FRAME_SIZE:
        raise RuntimeError("unexpected UART frame size")
    return bytes(frame)


def send_ball_result(valid, position_cm, velocity_pixel_s, quality, now_ms):
    """Send one STM32 fixed-length binary frame over UART0."""
    frame = build_ball_uart_frame(
        valid, position_cm, velocity_pixel_s, quality, now_ms
    )
    serial.write(frame)

    if PRINT_PROTOCOL:
        print("BALL TX:", " ".join("{:02X}".format(byte) for byte in frame))


def draw_installation_axis(frame):
    axis_color = image.Color.from_rgb(0, 220, 255)
    frame.draw_line(
        AXIS_START_PX[0],
        AXIS_START_PX[1],
        AXIS_END_PX[0],
        AXIS_END_PX[1],
        axis_color,
        2,
    )
    frame.draw_cross(AXIS_START_PX[0], AXIS_START_PX[1], axis_color, 7, 2)
    frame.draw_cross(AXIS_END_PX[0], AXIS_END_PX[1], axis_color, 7, 2)


validate_calibration(
    AXIS_START_PX,
    AXIS_END_PX,
    AXIS_START_CM,
    AXIS_END_CM,
    FRAME_WIDTH,
    FRAME_HEIGHT,
)

cam = camera.Camera(FRAME_WIDTH, FRAME_HEIGHT, detector.input_format())
disp = display.Display()
tracker = HybridBallTracker(detector, FRAME_WIDTH, FRAME_HEIGHT)
position_filter = AdaptiveAlphaBetaFilter()

webrtc_server = None
if USE_WEBRTC:
    from maix import webrtc

    stream_channel = cam.add_channel(320, 180, image.Format.FMT_YVU420SP)
    webrtc_server = webrtc.WebRTC()
    webrtc_server.bind_camera(stream_channel)
    webrtc_server.start()
    print("WebRTC:", webrtc_server.get_url())

print(
    "Hybrid detector v1.0: {}x{}, model={}".format(
        FRAME_WIDTH, FRAME_HEIGHT, model_path_for_device(sys.device_name())
    )
)

panel_color = image.Color.from_rgb(0, 0, 0)
projection_color = image.Color.from_rgb(255, 220, 0)
source_colors = {
    "Y": image.COLOR_GREEN,                    # 原图 YOLO
    "T": image.Color.from_rgb(255, 220, 0),   # 模板跟踪
    "E": image.Color.from_rgb(0, 220, 255),   # 增强图 YOLO
    "G": image.Color.from_rgb(255, 140, 0),   # 全画面模板重定位
}
last_loop_ms = time.ticks_ms()


while not app.need_exit():
    loop_start_ms = time.ticks_ms()
    loop_cost_ms = loop_start_ms - last_loop_ms
    last_loop_ms = loop_start_ms

    frame = cam.read()
    if LENS_CORR_ENABLE:
        frame = frame.lens_corr(strength=LENS_CORR_STRENGTH)

    detect_start_ms = time.ticks_ms()
    now_ms = time.ticks_ms()
    ball, debug = tracker.process(frame, now_ms)
    detect_cost_ms = time.ticks_ms() - detect_start_ms

    # draw_calibration_grid(frame)
    draw_installation_axis(frame)
    frame.draw_rect(0, 0, FRAME_WIDTH, 34, panel_color, -1)

    if ball is not None:
        filtered_x, filtered_y = position_filter.update(
            ball["cx"], ball["cy"], now_ms
        )
        position_cm, axis_ratio, _ = position_from_pixel(
            (filtered_x, filtered_y),
            AXIS_START_PX,
            AXIS_END_PX,
            AXIS_START_CM,
            AXIS_END_CM,
        )
        projected_x, projected_y = axis_point(
            axis_ratio, AXIS_START_PX, AXIS_END_PX
        )

        source = ball["source"]
        box_color = source_colors.get(source, image.COLOR_GREEN)
        draw_x = max(0, int(ball["x"]))
        draw_y = max(0, int(ball["y"]))
        draw_w = max(1, min(FRAME_WIDTH - draw_x, int(ball["w"])))
        draw_h = max(1, min(FRAME_HEIGHT - draw_y, int(ball["h"])))
        frame.draw_rect(draw_x, draw_y, draw_w, draw_h, box_color, 2)
        frame.draw_cross(
            int(round(filtered_x)), int(round(filtered_y)), box_color, 9, 2
        )
        frame.draw_cross(
            int(round(projected_x)),
            int(round(projected_y)),
            projection_color,
            6,
            2,
        )

        frame.draw_string(
            8,
            5,
            "BALL {:+.2f}cm {}".format(position_cm, source),
            color=image.COLOR_WHITE,
            scale=1.25,
            thickness=2,
        )

        if DRAW_DEBUG:
            debug_text = "{} Q{:.2f} Y{} T{:.2f} {}ms".format(
                source,
                ball["score"],
                debug["raw_objects"],
                debug["template_score"],
                detect_cost_ms,
            )
            text_y = min(FRAME_HEIGHT - 18, draw_y + draw_h + 2)
            frame.draw_string(
                max(0, min(draw_x, FRAME_WIDTH - 205)),
                text_y,
                debug_text,
                color=box_color,
                scale=0.8,
                thickness=1,
            )

        send_ball_result(
            True,
            position_cm,
            position_filter.vx,
            ball["score"],
            now_ms,
        )
    else:
        position_filter.mark_missing(now_ms)
        frame.draw_string(
            8,
            5,
            "BALL LOST",
            color=image.COLOR_RED,
            scale=1.25,
            thickness=2,
        )
        if DRAW_DEBUG:
            # Y=原图框数，E=增强图框数，T=局部模板，G=全画面模板。
            debug_text = "Y{} E{} T{:.2f} G{:.2f} {}ms".format(
                debug["raw_objects"],
                debug["enhanced_objects"],
                debug["template_score"],
                debug["global_template_score"],
                detect_cost_ms,
            )
            frame.draw_string(
                8,
                38,
                debug_text,
                color=image.Color.from_rgb(255, 170, 0),
                scale=0.8,
                thickness=1,
            )
        send_ball_result(False, 0.0, 0.0, 0.0, now_ms)

    if SHOW_FPS:
        fps = 0 if loop_cost_ms <= 0 else int(1000 / loop_cost_ms)
        fps_text = "FPS:{}".format(fps)
        text_width = image.string_size(
            fps_text, scale=1.0, thickness=1
        ).width()
        frame.draw_string(
            FRAME_WIDTH - text_width - 5,
            6,
            fps_text,
            color=image.COLOR_GREEN,
            scale=1.0,
            thickness=1,
        )

    debug_print(
        "source={} detect={}ms loop={}ms".format(
            debug["source"], detect_cost_ms, loop_cost_ms
        )
    )
    disp.show(frame)
