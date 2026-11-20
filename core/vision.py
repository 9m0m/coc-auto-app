"""
Module Thị giác Máy tính (Computer Vision)
Hỗ trợ chụp màn hình tốc độ cao (MSS) và so khớp ảnh mẫu (OpenCV).
"""

import time
from typing import Optional, Tuple, Any
import cv2
import numpy as np
import mss


def safe_grab(sct: Any, region: dict) -> Optional[np.ndarray]:
    """Chụp ảnh một vùng màn hình từ VRAM vào RAM dạng mảng BGR."""
    try:
        raw = sct.grab(region)
        if raw is None:
            return None
        img = np.array(raw)
        if img.size == 0:
            return None
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
