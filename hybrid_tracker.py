"""适用于 MaixCAM 系列的 NPU + CPU 混合钢珠跟踪器。

正常情况下只运行 YOLO26。YOLO 瞬时丢失时，依次使用小窗口模板跟踪、
自适应亮度增强后的 YOLO，以及低频全画面归一化模板重定位。这里没有全图
Hough 圆搜索，也没有 FFT，因此更适合 MaixCAM 的 CPU 和 NPU 结构。
"""

import math

import cv2
import numpy as np


def clamp(value, minimum=0.0, maximum=1.0):
    return max(minimum, min(maximum, value))


class HybridBallTracker:
    """融合 YOLO、亮度归一化、模板跟踪和快速经典候选。"""

    def __init__(self, detector, width, height):
        self.detector = detector
        self.width = width
        self.height = height
        self.scale = width / 640.0

        # YOLO 使用较低门限获取候选，再用时序位置和尺寸选择最佳目标。
        self.raw_confidence = 0.24
        self.enhanced_confidence = 0.24
        self.acquire_confidence = 0.40
        self.iou_threshold = 0.45

        # 低成本补救策略的运行频率。正常检测成功时不会执行它们。
        self.enhanced_retry_interval = 2
        self.global_template_interval = 3
        self.template_refresh_interval = 5
        # 黑色车架与钢珠都可能产生高相关纹理；模板只用于短暂补帧，
        # 且要求更高的匹配分数，不能持续替代检测器。
        self.template_threshold = 0.70
        self.global_template_threshold = 0.78
        self.template_grace_ms = 320
        self.reset_ms = 900

        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 4))
        self.template_clahe = cv2.createCLAHE(
            clipLimit=2.0, tileGridSize=(4, 4)
        )

        self.frame_index = 0
        self.missing_frames = 0
        self.last_result = None
        self.last_seen_ms = None
        self.last_detector_ms = None
        self.velocity_x = 0.0
        self.velocity_y = 0.0

        self.template = None
        self.template_ball_offset = None

    @staticmethod
    def _object_to_result(obj, source):
        return {
            "x": int(obj.x),
            "y": int(obj.y),
            "w": int(obj.w),
            "h": int(obj.h),
            "cx": float(obj.x + obj.w * 0.5),
            "cy": float(obj.y + obj.h * 0.5),
            "score": float(obj.score),
            "source": source,
            "class_id": int(obj.class_id),
        }

    def _select_yolo(self, objects, now_ms, source):
        if not objects:
            return None

        candidates = [self._object_to_result(obj, source) for obj in objects]
        if self.last_result is None or self.last_seen_ms is None:
            best = max(candidates, key=lambda item: item["score"])
            return best if best["score"] >= self.acquire_confidence else None

        dt = clamp((now_ms - self.last_seen_ms) * 0.001, 0.0, 0.12)
        predicted_x = self.last_result["cx"] + self.velocity_x * dt
        predicted_y = self.last_result["cy"] + self.velocity_y * dt
        previous_size = max(1.0, 0.5 * (self.last_result["w"] + self.last_result["h"]))
        position_gate = max(48.0 * self.scale, previous_size * 4.5)

        best = None
        best_value = -1.0
        for candidate in candidates:
            distance = math.hypot(
                candidate["cx"] - predicted_x,
                candidate["cy"] - predicted_y,
            )
            position_score = clamp(1.0 - distance / position_gate)
            candidate_size = max(1.0, 0.5 * (candidate["w"] + candidate["h"]))
            size_error = abs(candidate_size - previous_size) / previous_size
            size_score = clamp(1.0 - size_error / 0.75)
            value = candidate["score"] + 0.30 * position_score + 0.10 * size_score
            if value > best_value:
                best_value = value
                best = candidate

        if best is None:
            return None

        distance = math.hypot(best["cx"] - predicted_x, best["cy"] - predicted_y)
        # 低置信度框只有在上一位置附近才接受；高置信度框允许全画面重定位。
        if distance > position_gate and best["score"] < 0.38:
            return None
        return best

    @staticmethod
    def _frame_to_rgb_and_gray(frame):
        # 延迟导入使本模块可在电脑上单独测试经典候选部分。
        from maix import image as maix_image

        rgb = maix_image.image2cv(frame, ensure_bgr=False, copy=False)
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        return rgb, gray

    def _update_template(self, gray, result):
        box_width = max(8, int(result["w"]))
        box_height = max(8, int(result["h"]))
        pad_x = max(2, int(round(box_width * 0.12)))
        pad_y = max(2, int(round(box_height * 0.12)))

        x0 = max(0, int(result["x"]) - pad_x)
        y0 = max(0, int(result["y"]) - pad_y)
        x1 = min(self.width, int(result["x"] + result["w"]) + pad_x)
        y1 = min(self.height, int(result["y"] + result["h"]) + pad_y)
        if x1 - x0 < 8 or y1 - y0 < 8:
            return

        template = gray[y0:y1, x0:x1].copy()
        if float(np.std(template)) < 5.0:
            return

        self.template = template
        self.template_ball_offset = (
            int(result["x"] - x0),
            int(result["y"] - y0),
            int(result["w"]),
            int(result["h"]),
        )

    def _template_is_fresh(self, now_ms):
        """Allow OpenCV fallback only shortly after a detector-confirmed ball."""
        return (
            self.last_detector_ms is not None
            and now_ms - self.last_detector_ms <= self.template_grace_ms
        )

    def _track_template(self, gray, now_ms, full_frame=False):
        if (
            self.template is None
            or self.template_ball_offset is None
            or self.last_result is None
            or self.last_seen_ms is None
            or not self._template_is_fresh(now_ms)
        ):
            return None, 0.0

        dt = clamp((now_ms - self.last_seen_ms) * 0.001, 0.0, 0.15)
        predicted_x = self.last_result["cx"] + self.velocity_x * dt
        predicted_y = self.last_result["cy"] + self.velocity_y * dt
        speed_margin = math.hypot(self.velocity_x, self.velocity_y) * dt
        template_h, template_w = self.template.shape[:2]
        if full_frame:
            x0, y0, x1, y1 = 0, 0, self.width, self.height
            required_score = self.global_template_threshold
            result_source = "G"
        else:
            search_radius = int(
                min(
                    self.width * 0.22,
                    max(34.0 * self.scale, self.last_result["w"] * 2.5)
                    + speed_margin,
                )
            )
            x0 = max(
                0, int(round(predicted_x - search_radius - template_w * 0.5))
            )
            y0 = max(
                0, int(round(predicted_y - search_radius - template_h * 0.5))
            )
            x1 = min(
                self.width,
                int(round(predicted_x + search_radius + template_w * 0.5)),
            )
            y1 = min(
                self.height,
                int(round(predicted_y + search_radius + template_h * 0.5)),
            )
            required_score = self.template_threshold
            result_source = "T"
        search = gray[y0:y1, x0:x1]
        if search.shape[0] < template_h or search.shape[1] < template_w:
            return None, 0.0

        response = cv2.matchTemplate(search, self.template, cv2.TM_CCOEFF_NORMED)
        _, max_value, _, max_location = cv2.minMaxLoc(response)
        if max_value < required_score:
            return None, float(max_value)

        match_x = x0 + max_location[0]
        match_y = y0 + max_location[1]
        offset_x, offset_y, ball_w, ball_h = self.template_ball_offset
        ball_x = match_x + offset_x
        ball_y = match_y + offset_y
        result = {
            "x": int(ball_x),
            "y": int(ball_y),
            "w": int(ball_w),
            "h": int(ball_h),
            "cx": float(ball_x + ball_w * 0.5),
            "cy": float(ball_y + ball_h * 0.5),
            "score": float(clamp(0.30 + 0.65 * max_value)),
            "source": result_source,
            "class_id": 0,
        }
        if not self._verify_template_candidate(gray, result):
            return None, float(max_value)
        return result, float(max_value)

    def _verify_template_candidate(self, gray, result):
        """Use texture gates to reject dark chassis matches in all template paths."""
        x0 = max(0, int(result["x"]))
        y0 = max(0, int(result["y"]))
        x1 = min(self.width, x0 + int(result["w"]))
        y1 = min(self.height, y0 + int(result["h"]))
        patch = gray[y0:y1, x0:x1]
        if patch.shape[0] < 8 or patch.shape[1] < 8:
            return False

        enhanced = self.template_clahe.apply(patch)
        patch_h, patch_w = enhanced.shape[:2]
        yy, xx = np.ogrid[:patch_h, :patch_w]
        radius = min(patch_w, patch_h) * 0.5
        inner_mask = (
            (xx - patch_w * 0.5) ** 2 + (yy - patch_h * 0.5) ** 2
            <= (radius * 0.75) ** 2
        )
        if np.count_nonzero(inner_mask) < 20:
            return False
        inner = enhanced[inner_mask]
        texture = float(np.std(inner))
        dynamic_range = float(
            np.percentile(inner, 90) - np.percentile(inner, 10)
        )
        # 使用 CLAHE 后的相对纹理，不依赖原始画面的绝对亮度。
        return texture >= 51.0 and dynamic_range >= 138.0

    def _normalize_rgb(self, rgb, gray):
        """把过暗、过亮或局部不均匀画面拉回训练数据常见范围。"""
        mean_level = float(cv2.mean(gray)[0])
        if mean_level < 95.0 or mean_level > 170.0:
            safe_mean = max(8.0, min(247.0, mean_level)) / 255.0
            target = 125.0 / 255.0
            gamma = math.log(target) / math.log(safe_mean)
            gamma = clamp(gamma, 0.55, 1.75)
            lut = np.array(
                [
                    int(round(255.0 * ((index / 255.0) ** gamma)))
                    for index in range(256)
                ],
                dtype=np.uint8,
            )
            return cv2.LUT(rgb, lut), mean_level

        lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
        lab[:, :, 0] = self.clahe.apply(lab[:, :, 0])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB), mean_level

    def _detect_enhanced(self, rgb, gray, now_ms):
        from maix import image as maix_image

        corrected_rgb, mean_level = self._normalize_rgb(rgb, gray)
        corrected_image = maix_image.cv2image(
            corrected_rgb, bgr=False, copy=False
        )
        objects = self.detector.detect(
            corrected_image,
            conf_th=self.enhanced_confidence,
            iou_th=self.iou_threshold,
        )
        return self._select_yolo(objects, now_ms, "E"), len(objects), mean_level

    def _commit(self, result, now_ms, gray=None, refresh_template=False):
        if self.last_result is not None and self.last_seen_ms is not None:
            dt = clamp((now_ms - self.last_seen_ms) * 0.001, 0.005, 0.12)
            measured_vx = (result["cx"] - self.last_result["cx"]) / dt
            measured_vy = (result["cy"] - self.last_result["cy"]) / dt
            self.velocity_x = 0.65 * self.velocity_x + 0.35 * measured_vx
            self.velocity_y = 0.65 * self.velocity_y + 0.35 * measured_vy
        else:
            self.velocity_x = 0.0
            self.velocity_y = 0.0

        self.last_result = result
        self.last_seen_ms = now_ms
        self.missing_frames = 0
        if gray is not None and (refresh_template or self.template is None):
            self._update_template(gray, result)
        if result["source"] in ("Y", "E"):
            self.last_detector_ms = now_ms

    def process(self, frame, now_ms):
        """处理一帧，返回统一结果字典和调试统计。"""
        self.frame_index += 1
        debug = {
            "raw_objects": 0,
            "enhanced_objects": 0,
            "template_score": 0.0,
            "global_template_score": 0.0,
            "brightness": -1.0,
            "source": "-",
        }

        objects = self.detector.detect(
            frame,
            conf_th=self.raw_confidence,
            iou_th=self.iou_threshold,
        )
        debug["raw_objects"] = len(objects)
        result = self._select_yolo(objects, now_ms, "Y")
        if result is not None:
            refresh = (
                self.template is None
                or self.frame_index % self.template_refresh_interval == 0
            )
            gray = None
            if refresh:
                _, gray = self._frame_to_rgb_and_gray(frame)
            self._commit(result, now_ms, gray, refresh_template=refresh)
            debug["source"] = "Y"
            return result, debug

        self.missing_frames += 1
        rgb, gray = self._frame_to_rgb_and_gray(frame)

        result, template_score = self._track_template(gray, now_ms)
        debug["template_score"] = template_score
        if result is not None:
            self._commit(result, now_ms)
            debug["source"] = "T"
            return result, debug

        if self.missing_frames % self.enhanced_retry_interval == 1:
            result, object_count, brightness = self._detect_enhanced(
                rgb, gray, now_ms
            )
            debug["enhanced_objects"] = object_count
            debug["brightness"] = brightness
            if result is not None:
                self._commit(result, now_ms, gray, refresh_template=True)
                debug["source"] = "E"
                return result, debug

        if (
            self.template is not None
            and self.missing_frames % self.global_template_interval == 0
        ):
            result, global_score = self._track_template(
                gray, now_ms, full_frame=True
            )
            debug["global_template_score"] = global_score
            if result is not None:
                self._commit(result, now_ms)
                debug["source"] = "G"
                return result, debug

        if self.last_seen_ms is not None and now_ms - self.last_seen_ms >= self.reset_ms:
            self.last_result = None
            self.last_seen_ms = None
            self.last_detector_ms = None
            self.velocity_x = 0.0
            self.velocity_y = 0.0
            self.template = None
            self.template_ball_offset = None

        return None, debug
