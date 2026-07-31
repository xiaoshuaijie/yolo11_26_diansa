"""钢珠像素位置换算和低延时 alpha-beta 滤波。"""

import math


def project_onto_axis(point, axis_start, axis_end):
    px, py = point
    x0, y0 = axis_start
    x1, y1 = axis_end
    dx = x1 - x0
    dy = y1 - y0
    length_squared = dx * dx + dy * dy
    if length_squared <= 0:
        raise ValueError("calibration endpoints must be different")
    ratio = ((px - x0) * dx + (py - y0) * dy) / float(length_squared)
    projected_x = x0 + ratio * dx
    projected_y = y0 + ratio * dy
    return ratio, math.hypot(px - projected_x, py - projected_y)


def axis_point(ratio, axis_start, axis_end):
    x0, y0 = axis_start
    x1, y1 = axis_end
    return x0 + ratio * (x1 - x0), y0 + ratio * (y1 - y0)


def position_from_pixel(point, axis_start, axis_end, start_cm, end_cm):
    if start_cm == end_cm:
        raise ValueError("physical calibration positions must be different")
    ratio, distance = project_onto_axis(point, axis_start, axis_end)
    return start_cm + ratio * (end_cm - start_cm), ratio, distance


class AdaptiveAlphaBetaFilter:
    def __init__(self, reset_ms=250):
        self.reset_ms = reset_ms
        self.reset()

    def reset(self):
        self.x = None
        self.y = None
        self.vx = 0.0
        self.vy = 0.0
        self.last_ms = None

    def update(self, measured_x, measured_y, now_ms):
        if self.x is None:
            self.x = float(measured_x)
            self.y = float(measured_y)
            self.last_ms = now_ms
            return self.x, self.y

        dt = max(0.005, min(0.100, (now_ms - self.last_ms) * 0.001))
        predicted_x = self.x + self.vx * dt
        predicted_y = self.y + self.vy * dt
        error_x = measured_x - predicted_x
        error_y = measured_y - predicted_y
        error = math.hypot(error_x, error_y)
        motion = min(1.0, error / 10.0) ** 2
        alpha = 0.20 + (0.95 - 0.20) * motion
        beta = 0.01 + (0.12 - 0.01) * motion
        self.x = predicted_x + alpha * error_x
        self.y = predicted_y + alpha * error_y
        self.vx += beta * error_x / dt
        self.vy += beta * error_y / dt
        self.last_ms = now_ms
        return self.x, self.y

    def mark_missing(self, now_ms):
        if self.last_ms is not None and now_ms - self.last_ms >= self.reset_ms:
            self.reset()


def validate_calibration(axis_start, axis_end, start_cm, end_cm, width, height):
    if width <= 0 or height <= 0:
        raise ValueError("image dimensions must be positive")
    for point in (axis_start, axis_end):
        if not (0 <= point[0] < width and 0 <= point[1] < height):
            raise ValueError("calibration point is outside the image")
    position_from_pixel(axis_start, axis_start, axis_end, start_cm, end_cm)
