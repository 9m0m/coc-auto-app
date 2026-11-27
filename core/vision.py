"""
Module Thị giác Máy tính (Computer Vision)
Hỗ trợ chụp màn hình tốc độ cao (MSS) và so khớp ảnh mẫu (OpenCV).
"""

import time
from typing import Optional, Tuple, Any, Callable
import cv2
import numpy as np
import mss

import config


class ADBCaptureSession:
    """Bộ đệm chụp màn hình qua ADB mô phỏng giao diện mss.grab() để dùng chung cho Rally và Phiêu Lưu."""

    def __init__(self, adb: Any, cache_ttl: Optional[float] = None):
        self.adb = adb
        ttl_default = float(getattr(config, "ADB_CAPTURE_CACHE_TTL", 0.35))
        self.cache_ttl = ttl_default if cache_ttl is None else float(cache_ttl)
        self._frame: Optional[np.ndarray] = None
        self._frame_time: float = 0.0
        self._frame_seq: int = -1

    def invalidate(self) -> None:
        """Xóa ảnh đệm hiện tại để lần đọc kế tiếp chụp khung hình mới từ Android."""
        self._frame = None
        self._frame_time = 0.0
        self._frame_seq = -1

    def _ensure_fresh_frame(self) -> Optional[np.ndarray]:
        now = time.time()
        last_input = float(getattr(self.adb, "last_input_time", 0.0))
        cur_seq = int(getattr(self.adb, "input_seq", 0))
        need_refresh = (
            self._frame is None
            or (now - self._frame_time) >= self.cache_ttl
            or last_input > self._frame_time
            or cur_seq != self._frame_seq
        )
        if need_refresh:
            timeout = float(getattr(config, "ADB_SCREENCAP_TIMEOUT", 4.0))
            captured = self.adb.capture_screen(timeout=timeout)
            if captured is not None and captured.size > 0:
                self._frame = captured
                self._frame_time = time.time()
                self._frame_seq = cur_seq
            else:
                self._frame = None
                self._frame_time = 0.0
                self._frame_seq = -1
        return self._frame

    def get_frame_size(self) -> Optional[Tuple[int, int]]:
        """Trả về (width, height) của khung hình Android hiện tại."""
        frame = self._ensure_fresh_frame()
        if frame is not None and frame.size > 0:
            fh, fw = frame.shape[:2]
            return int(fw), int(fh)
        sz = getattr(self.adb, "screen_size", None)
        if sz and sz[0] > 0 and sz[1] > 0:
            return int(sz[0]), int(sz[1])
        return None

    def grab(self, region: dict) -> Optional[np.ndarray]:
        """Cắt một vùng trên ảnh Android theo tọa độ từ region {'left', 'top', 'width', 'height'}."""
        frame = self._ensure_fresh_frame()
        if frame is None or frame.size == 0:
            return None
        fh, fw = frame.shape[:2]
        left = max(0, int(region.get("left", 0)))
        top = max(0, int(region.get("top", 0)))
        width = max(1, int(region.get("width", fw - left)))
        height = max(1, int(region.get("height", fh - top)))
        right = min(fw, left + width)
        bottom = min(fh, top + height)
        if right <= left or bottom <= top:
            return None
        return frame[top:bottom, left:right].copy()


def create_capture_session(adb: Any, capture_mode: str = "mss") -> Any:
    """Tạo session chụp màn hình tương ứng ('mss' siêu tốc hoặc 'adb' chạy ngầm)."""
    if capture_mode == "adb":
        return ADBCaptureSession(adb)
    return mss.mss()


def make_adb_viewport_getter(sct: ADBCaptureSession, adb: Any) -> Callable[[], Optional[Tuple[int, int, int, int]]]:
    """Tạo hàm lấy viewport (0, 0, w, h) khớp trực tiếp độ phân giải frame ADB."""
    def _get_vp() -> Optional[Tuple[int, int, int, int]]:
        sz = sct.get_frame_size()
        if sz and sz[0] > 0 and sz[1] > 0:
            return (0, 0, sz[0], sz[1])
        fallback_sz = getattr(adb, "screen_size", None)
        if fallback_sz and fallback_sz[0] > 0 and fallback_sz[1] > 0:
            return (0, 0, int(fallback_sz[0]), int(fallback_sz[1]))
        return None
    return _get_vp


def safe_grab(sct: Any, region: dict) -> Optional[np.ndarray]:
    """Chụp ảnh một vùng màn hình từ VRAM/ADB vào RAM dạng mảng BGR."""
    try:
        raw = sct.grab(region)
        if raw is None:
            return None
        img = np.array(raw)
        if img.size == 0:
            return None
        if img.ndim == 3 and img.shape[2] == 3:
            return img
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    except Exception:
        time.sleep(0.1)
        return None


def grab_roi(
    sct: Any,
    gw_box: dict,
    rel_x1: float,
    rel_y1: float,
    rel_x2: float,
    rel_y2: float,
) -> Tuple[Optional[np.ndarray], Tuple[int, int, int, int]]:
    """
    Chụp một vùng ảnh theo tỉ lệ tương đối (RelX, RelY) của Game Viewport.
    Trả về: (ảnh BGR hoặc None, (abs_x1, abs_y1, width, height)).
    """
    gw_left = gw_box["left"]
    gw_top = gw_box["top"]
    gw_w = gw_box["width"]
    gw_h = gw_box["height"]

    abs_x1 = int(gw_left + gw_w * rel_x1)
    abs_y1 = int(gw_top + gw_h * rel_y1)
    abs_x2 = int(gw_left + gw_w * rel_x2)
    abs_y2 = int(gw_top + gw_h * rel_y2)
    width = max(1, abs_x2 - abs_x1)
    height = max(1, abs_y2 - abs_y1)

    crop = safe_grab(sct, {"left": abs_x1, "top": abs_y1, "width": width, "height": height})
    return crop, (abs_x1, abs_y1, width, height)


def match_template_best(
    image: np.ndarray,
    template: np.ndarray,
    threshold: float = 0.8,
) -> Optional[Tuple[float, Tuple[int, int], Tuple[int, int]]]:
    """
    Tìm vị trí khớp nhất của template trong image.
    Trả về: (max_val, (max_loc_x, max_loc_y), (tpl_w, tpl_h)) nếu max_val >= threshold, ngược lại None.
    """
    if image is None or template is None:
        return None

    img_h, img_w = image.shape[:2]
    tpl_h, tpl_w = template.shape[:2]

    if img_h < tpl_h or img_w < tpl_w:
        return None

    res = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

    if max_val >= threshold:
        return float(max_val), max_loc, (tpl_w, tpl_h)
    return None
