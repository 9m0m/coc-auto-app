"""
Module Auto Câu Cá (COC Auto Fishing)
Kế thừa 100% thuật toán nhận diện màu HSV, bộ lọc nhiễu, máy trạng thái 4 bước và
cơ chế 2 pha Continuous Sweep từ auto_cauca.py gốc.
Thay thế toàn bộ click chuột Win32 bằng ADB Tap ngầm (Không chiếm chuột).
"""

import time
import threading
import ctypes
import random
from typing import Optional, Tuple, Callable

import cv2
import numpy as np
import mss

import config
from core.viewport import screen_to_android
from core.vision import safe_grab
from core.adb_manager import ADBManager

user32 = ctypes.windll.user32 if hasattr(ctypes, "windll") else None


def _sleep_check(seconds: float, stop_event: threading.Event) -> bool:
    """Nghỉ có thể ngắt ngay lập tức khi stop_event được bật."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        if stop_event.is_set():
            return True
        time.sleep(0.015)
    return False


def _mouse_fast_tap(x: int, y: int, jitter: bool = True) -> None:
    """Bấm siêu tốc phản xạ mili-giây qua Win32 mouse_event mô phỏng tay người (±2px, 16-26ms)."""
    if not user32:
        return
    click_x = int(x)
    click_y = int(y)
    hold_time = 0.020
    if jitter:
        click_x += random.randint(-2, 2)
        click_y += random.randint(-2, 2)
        hold_time = random.uniform(0.016, 0.026)
    user32.SetCursorPos(click_x, click_y)
    user32.mouse_event(0x0002, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTDOWN
    time.sleep(hold_time)
    user32.mouse_event(0x0004, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTUP


def _mouse_touch_tap(
    x: int,
    y: int,
    desc: str = "",
    log_cb: Optional[Callable[[str], None]] = None,
    jitter: bool = True,
) -> None:
    """Chạm cảm ứng Win32 mô phỏng tay người giữ 55-75ms, độ lệch ±2px."""
    if not user32:
        return
    if desc and log_cb:
        log_cb(f"-> [Chuột] {desc} ({x}, {y})")
    click_x = int(x)
    click_y = int(y)
    hold_time = 0.065
    if jitter:
        click_x += random.randint(-2, 2)
        click_y += random.randint(-2, 2)
        hold_time = random.uniform(0.055, 0.075)
    user32.SetCursorPos(click_x, click_y)
    user32.mouse_event(0x0002, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTDOWN
    time.sleep(hold_time)
    user32.mouse_event(0x0004, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTUP


def _adb_tap(
    adb: ADBManager,
    vp: Tuple[int, int, int, int],
    win_x: int,
    win_y: int,
    desc: str = "",
    log_cb: Optional[Callable[[str], None]] = None,
):
    """Chuyển đổi tọa độ Windows sang Android và chạm ngầm qua ADB."""
    if not adb or not adb.active_serial:
        return
    screen_sz = adb.screen_size or (720, 1280)
    ax, ay = screen_to_android(win_x, win_y, vp, screen_sz)
    if desc and log_cb:
        log_cb(f"-> [ADB] {desc} (Android: {ax}, {ay})")
    adb.tap(ax, ay)


def _perform_tap(
    click_mode: str,
    adb: ADBManager,
    vp: Tuple[int, int, int, int],
    screen_x: int,
    screen_y: int,
    desc: str = "",
    log_cb: Optional[Callable[[str], None]] = None,
    is_fast: bool = False,
) -> None:
    """Điều phối tap dựa theo click_mode: 'mouse' (Chuột siêu tốc) hoặc 'adb' (ADB ngầm)."""
    if click_mode == "mouse":
        if is_fast:
            _mouse_fast_tap(screen_x, screen_y, jitter=True)
        else:
            _mouse_touch_tap(screen_x, screen_y, desc=desc, log_cb=log_cb, jitter=True)
    else:
        _adb_tap(adb, vp, screen_x, screen_y, desc=desc, log_cb=log_cb)


def analyze_button_colors(btn_bgr: np.ndarray) -> Tuple[int, int, int]:
    """Phân tích số lượng pixel tương ứng với trạng thái nút câu."""
    hsv = cv2.cvtColor(btn_bgr, cv2.COLOR_BGR2HSV)

    green_mask = cv2.inRange(
        hsv,
        np.array(config.HSV_READY_GREEN_LOWER, dtype=np.uint8),
        np.array(config.HSV_READY_GREEN_UPPER, dtype=np.uint8),
    )
    green_px = int(np.count_nonzero(green_mask))

    s_channel = hsv[:, :, 1]
    v_channel = hsv[:, :, 2]
    grey_mask = (s_channel < config.GREY_SATURATION_MAX) & (
        v_channel >= config.GREY_VALUE_MIN
    ) & (v_channel <= config.GREY_VALUE_MAX)
    grey_px = int(np.count_nonzero(grey_mask))

    purple_mask = cv2.inRange(
        hsv,
        np.array(config.HSV_BITE_PURPLE_LOWER, dtype=np.uint8),
        np.array(config.HSV_BITE_PURPLE_UPPER, dtype=np.uint8),
    )
    purple_px = int(np.count_nonzero(purple_mask))

    return green_px, grey_px, purple_px


def detect_fishing_button(
    scan_bgr: np.ndarray,
    scan_left: int,
    scan_top: int,
    ref_rel: Optional[Tuple[Optional[float], Optional[float]]] = None,
    gw_vp: Optional[Tuple[int, int, int, int]] = None,
) -> Optional[Tuple[int, int, str, int]]:
    """
    Quét dải đáy màn hình để tìm nút câu cá hình tròn thích ứng (Smart Adaptive Button).
    Tự động nhận diện tâm nút câu qua 3 trạng thái màu:
    - Tím (Cá cắn / Giật cần)
    - Xanh lá (Sẵn sàng quăng cần)
    - Xám (Cần dưới nước đang chờ cá)

    Hỗ trợ cả BlueStacks, LDPlayer, Nox, MuMu mà không cần fix cứng toạ độ.
    Trả về: (screen_x, screen_y, color_type, contour_area) nếu tìm thấy, ngược lại None.
    """
    if scan_bgr is None or scan_bgr.size == 0:
        return None

    try:
        hsv = cv2.cvtColor(scan_bgr, cv2.COLOR_BGR2HSV)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        sh, sw = scan_bgr.shape[:2]

        ref_x, ref_y = None, None
        if ref_rel and ref_rel[0] is not None and ref_rel[1] is not None and gw_vp:
            gw_l, gw_t, gw_w, gw_h = gw_vp
            ref_x = int(gw_l + gw_w * ref_rel[0])
            ref_y = int(gw_t + gw_h * ref_rel[1])
        elif gw_vp:
            gw_l, gw_t, gw_w, gw_h = gw_vp
            ref_x = int(gw_l + gw_w * config.BUTTON_REL_X)
            ref_y = int(gw_t + gw_h * config.BUTTON_REL_Y)

        # 1. Quét màu Tím (Ưu tiên cao nhất khi cá cắn câu)
        purple_mask = cv2.inRange(
            hsv,
            np.array(config.HSV_BITE_PURPLE_LOWER, dtype=np.uint8),
            np.array(config.HSV_BITE_PURPLE_UPPER, dtype=np.uint8),
        )
        if np.count_nonzero(purple_mask) > 150:
            clean_p = cv2.morphologyEx(purple_mask, cv2.MORPH_CLOSE, kernel)
            contours, _ = cv2.findContours(clean_p, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            p_candidates = []
            for c in contours:
                area = cv2.contourArea(c)
                if area >= 150:
                    x, y, bw, bh = cv2.boundingRect(c)
                    aspect_ratio = float(bw) / float(bh) if bh > 0 else 0
                    if 0.65 <= aspect_ratio <= 1.50 and bw >= 22 and bh >= 22 and bw <= sw * 0.9 and bh <= sh * 0.9:
                        M = cv2.moments(c)
                        cx = int(M["m10"] / M["m00"]) if M["m00"] > 0 else x + bw // 2
                        cy = int(M["m01"] / M["m00"]) if M["m00"] > 0 else y + bh // 2
                        p_candidates.append((area, cx, cy))
            if p_candidates:
                if ref_x is not None and ref_y is not None:
                    p_candidates.sort(key=lambda item: ((scan_left + item[1] - ref_x) ** 2 + (scan_top + item[2] - ref_y) ** 2))
                else:
                    p_candidates.sort(key=lambda item: item[0], reverse=True)
                area, cx, cy = p_candidates[0]
                return scan_left + cx, scan_top + cy, "purple", int(area)

        # 2. Quét màu Xanh lá (Nút sẵn sàng quăng cần trên bờ)
        green_mask = cv2.inRange(
            hsv,
            np.array(config.HSV_READY_GREEN_LOWER, dtype=np.uint8),
            np.array(config.HSV_READY_GREEN_UPPER, dtype=np.uint8),
        )
        if np.count_nonzero(green_mask) > 150:
            clean_g = cv2.morphologyEx(green_mask, cv2.MORPH_CLOSE, kernel)
            contours, _ = cv2.findContours(clean_g, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            g_candidates = []
            for c in contours:
                area = cv2.contourArea(c)
                if area >= 150:
                    x, y, bw, bh = cv2.boundingRect(c)
                    aspect_ratio = float(bw) / float(bh) if bh > 0 else 0
                    if 0.65 <= aspect_ratio <= 1.50 and bw >= 22 and bh >= 22 and bw <= sw * 0.9 and bh <= sh * 0.9:
                        M = cv2.moments(c)
                        cx = int(M["m10"] / M["m00"]) if M["m00"] > 0 else x + bw // 2
                        cy = int(M["m01"] / M["m00"]) if M["m00"] > 0 else y + bh // 2
                        g_candidates.append((area, cx, cy))
            if g_candidates:
                if ref_x is not None and ref_y is not None:
                    g_candidates.sort(key=lambda item: ((scan_left + item[1] - ref_x) ** 2 + (scan_top + item[2] - ref_y) ** 2))
                else:
                    g_candidates.sort(key=lambda item: item[0], reverse=True)
                area, cx, cy = g_candidates[0]
                return scan_left + cx, scan_top + cy, "green", int(area)

        # 3. Quét màu Xám (Cần đã thả xuống nước, đang chờ cá cắn)
        s_channel = hsv[:, :, 1]
        v_channel = hsv[:, :, 2]
        grey_mask = (
            (s_channel < config.GREY_SATURATION_MAX)
            & (v_channel >= config.GREY_VALUE_MIN)
            & (v_channel <= config.GREY_VALUE_MAX)
        ).astype(np.uint8) * 255

        if np.count_nonzero(grey_mask) > 250:
            clean_grey = cv2.morphologyEx(grey_mask, cv2.MORPH_CLOSE, kernel)
            contours, _ = cv2.findContours(clean_grey, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            grey_candidates = []
            for c in contours:
                area = cv2.contourArea(c)
                if area >= 250:
                    x, y, bw, bh = cv2.boundingRect(c)
                    aspect_ratio = float(bw) / float(bh) if bh > 0 else 0
                    fill_ratio = area / float(bw * bh) if (bw * bh) > 0 else 0
                    if 0.65 <= aspect_ratio <= 1.50 and bw >= 24 and bh >= 24 and bw <= sw * 0.9 and bh <= sh * 0.9 and fill_ratio >= 0.35:
                        M = cv2.moments(c)
                        cx = int(M["m10"] / M["m00"]) if M["m00"] > 0 else x + bw // 2
                        cy = int(M["m01"] / M["m00"]) if M["m00"] > 0 else y + bh // 2
                        grey_candidates.append((area, cx, cy))
            if grey_candidates:
                if ref_x is not None and ref_y is not None:
                    grey_candidates.sort(key=lambda item: ((scan_left + item[1] - ref_x) ** 2 + (scan_top + item[2] - ref_y) ** 2))
                else:
                    grey_candidates.sort(key=lambda item: item[0], reverse=True)
                area, cx, cy = grey_candidates[0]
                return scan_left + cx, scan_top + cy, "grey", int(area)

    except Exception:
        pass

    return None


def detect_yellow_and_bobber(roi_img: np.ndarray) -> Tuple[Optional[Tuple[int, int]], Optional[int]]:
    """
    Quét ô vàng mục tiêu và phao đỏ trên thanh trượt mini-game bằng contour & morphology.
    Kế thừa 100% thuật toán gốc từ auto_cauca.py:
    - Hỗ trợ cả ô vàng siêu hẹp của cá hiếm / cá kỷ lục (area >= 8).
    - Tự động ghép nối nếu phao đỏ che đôi ô vàng ở giữa (gap <= 26px).
    - Cô lập rãnh trượt 0.25 <= Y <= 0.78, loại bỏ 100% chữ 'Hoàn hảo!' và hoa giấy confetti.
    """
    hsv = cv2.cvtColor(roi_img, cv2.COLOR_BGR2HSV)
    kernel_yellow = np.ones((3, 1), np.uint8)
    kernel_red = np.ones((3, 3), np.uint8)
    rh, rw = roi_img.shape[:2]

    # 1. Quét ô vàng mục tiêu (Dùng kernel dọc 3x1 để giữ trọn vẹn ô vàng hẹp)
    lower_yellow = np.array(config.HSV_YELLOW_LOWER, dtype=np.uint8)
    upper_yellow = np.array(config.HSV_YELLOW_UPPER, dtype=np.uint8)
    yellow_mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
    clean_yellow = cv2.morphologyEx(yellow_mask, cv2.MORPH_OPEN, kernel_yellow)

    yellow_range = None
    contours, _ = cv2.findContours(clean_yellow, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    valid_yellows = []
    for c in contours:
        area = cv2.contourArea(c)
        if area >= 8:
            x, y, w, h = cv2.boundingRect(c)
            # Cô lập không gian rãnh trượt:
            if y < int(0.25 * rh) or (y + h) > int(0.78 * rh):
                continue
            if x < 12 or (x + w) > rw - 8:
                continue
            if h >= 10 and w <= config.YELLOW_MAX_WIDTH:
                valid_yellows.append((x, x + w, area))

    if valid_yellows:
        if len(valid_yellows) == 1:
            yellow_range = (valid_yellows[0][0], valid_yellows[0][1])
        else:
            valid_yellows.sort(key=lambda item: item[2], reverse=True)
            main_box = valid_yellows[0]
            second_box = valid_yellows[1]
            left_box = min(main_box, second_box, key=lambda b: b[0])
            right_box = max(main_box, second_box, key=lambda b: b[0])
            gap = right_box[0] - left_box[1]
            merged_width = right_box[1] - left_box[0]
            if gap <= 26 and merged_width <= config.YELLOW_MAX_WIDTH:
                yellow_range = (left_box[0], right_box[1])
            else:
                yellow_range = (main_box[0], main_box[1])

    # 2. Quét phao đỏ (bobber)
    lower_red1 = np.array(config.HSV_RED_LOWER1, dtype=np.uint8)
    upper_red1 = np.array(config.HSV_RED_UPPER1, dtype=np.uint8)
    lower_red2 = np.array(config.HSV_RED_LOWER2, dtype=np.uint8)
    upper_red2 = np.array(config.HSV_RED_UPPER2, dtype=np.uint8)

    red_mask = cv2.inRange(hsv, lower_red1, upper_red1) | cv2.inRange(hsv, lower_red2, upper_red2)
    clean_red = cv2.morphologyEx(red_mask, cv2.MORPH_OPEN, kernel_red)

    bobber_x = None
    r_contours, _ = cv2.findContours(clean_red, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    valid_reds = []
    for c in r_contours:
        area = cv2.contourArea(c)
        if area >= 50:
            x, y, w, h = cv2.boundingRect(c)
            if w < 10 or h < 10:
                continue
            if y < int(0.15 * rh) or (y + h) > int(0.85 * rh):
                continue
            if x < 12 or (x + w) > rw - 8:
                continue
            M = cv2.moments(c)
            if M["m00"] > 0:
                cx = int(M["m10"] / M["m00"])
            else:
                cx = x + w // 2
            valid_reds.append((cx, area))

    if valid_reds:
        valid_reds.sort(key=lambda item: item[1], reverse=True)
        bobber_x = valid_reds[0][0]

    return yellow_range, bobber_x


def run_fishing_loop(
    adb: ADBManager,
    get_vp_func: Callable[[], Optional[Tuple[int, int, int, int]]],
    stop_event: threading.Event,
    log_cb: Callable[[str], None],
    click_mode: str = "mouse",
):
    """
    Vòng lặp chạy chính của Auto Câu Cá (FSM 4 bước + 2 Pha Minigame chuẩn 100%).
    Hỗ trợ 2 cơ chế click độc lập:
    - click_mode == 'mouse': Win32 mouse_event siêu tốc 0.02s mô phỏng tay người (Khuyên dùng, nhạy 100%).
    - click_mode == 'adb': ADB Tap ngầm (Không chiếm chuột).
    """
    mode_name = "Chiếm chuột (0.02s)" if click_mode == "mouse" else "Click ảo (ADB ngầm)"
    log_cb(f"Khởi động Auto Câu Cá (Cơ chế: {mode_name})...")
    sct = mss.mss()

    state = "READY_TO_CAST"
    wait_ready_start = time.time()
    last_heartbeat = time.time()
    bite_wait_start = time.time()
    no_rod_start = 0.0
    last_claim_check_waiting = 0.0
    fish_count = 0
    adaptive_btn_rel_x: Optional[float] = None
    adaptive_btn_rel_y: Optional[float] = None

    while not stop_event.is_set():
        vp = get_vp_func()
        if not vp:
            log_cb("Chờ phát hiện cửa sổ game...")
            _sleep_check(1.0, stop_event)
            continue

        gw_l, gw_t, gw_w, gw_h = vp

        # Tọa độ nút câu thích ứng (Tự động thích nghi giữa BlueStacks, LDPlayer, Nox, MuMu)
        cur_btn_rel_x = adaptive_btn_rel_x if adaptive_btn_rel_x is not None else config.BUTTON_REL_X
        cur_btn_rel_y = adaptive_btn_rel_y if adaptive_btn_rel_y is not None else config.BUTTON_REL_Y

        btn_screen_x = int(gw_l + gw_w * cur_btn_rel_x)
        btn_screen_y = int(gw_t + gw_h * cur_btn_rel_y)
        claim_screen_x = int(gw_l + gw_w * config.CLAIM_REL_X)
        claim_screen_y = int(gw_t + gw_h * config.CLAIM_REL_Y)
        card_screen_x = int(gw_l + gw_w * config.CARD_REL_X)
        card_screen_y = int(gw_t + gw_h * config.CARD_REL_Y)
        card_confirm_y = int(gw_t + gw_h * config.CARD_CONFIRM_REL_Y)

        btn_radius = 55
        btn_box = {
            "top": btn_screen_y - btn_radius,
            "left": btn_screen_x - btn_radius,
            "width": btn_radius * 2,
            "height": btn_radius * 2,
        }

        scan_box = {
            "left": int(gw_l + gw_w * config.BUTTON_SCAN_REL_X_MIN),
            "top": int(gw_t + gw_h * config.BUTTON_SCAN_REL_Y_MIN),
            "width": max(1, int(gw_w * (config.BUTTON_SCAN_REL_X_MAX - config.BUTTON_SCAN_REL_X_MIN))),
            "height": max(1, int(gw_h * (config.BUTTON_SCAN_REL_Y_MAX - config.BUTTON_SCAN_REL_Y_MIN))),
        }

        slider_box = {
            "left": int(gw_l + gw_w * config.SLIDER_REL_X_MIN),
            "top": int(gw_t + gw_h * config.SLIDER_REL_Y_MIN),
            "width": max(1, int(gw_w * (config.SLIDER_REL_X_MAX - config.SLIDER_REL_X_MIN))),
            "height": max(1, int(gw_h * (config.SLIDER_REL_Y_MAX - config.SLIDER_REL_Y_MIN))),
        }

        claim_box = {
            "top": claim_screen_y - 15,
            "left": claim_screen_x - 30,
            "width": 60,
            "height": 30,
        }

        now = time.time()

        # =========================================================
        # BƯỚC 1: CHUẨN BỊ QUĂNG CẦN (READY_TO_CAST)
        # =========================================================
        if state == "READY_TO_CAST":
            # 1. Ưu tiên kiểm tra và giải phóng nút "Nhận Ngay" trước
            claim_bgr = safe_grab(sct, claim_box)
            if claim_bgr is not None:
                c_hsv = cv2.cvtColor(claim_bgr, cv2.COLOR_BGR2HSV)
                c_green = cv2.inRange(
                    c_hsv,
                    np.array(config.HSV_READY_GREEN_LOWER, dtype=np.uint8),
                    np.array(config.HSV_READY_GREEN_UPPER, dtype=np.uint8),
                )
                if np.count_nonzero(c_green) > 300:
                    log_cb("[Phục hồi] Phát hiện nút Nhận Ngay -> Nhận thưởng!")
                    state = "CLAIM_REWARD"
                    continue

            # 2. Tự động thích ứng vị trí nút câu cá qua dải quét đáy màn hình
            scan_bgr = safe_grab(sct, scan_box)
            bgr = None
            det_col = None
            det_area = 0
            if scan_bgr is not None:
                det = detect_fishing_button(
                    scan_bgr,
                    scan_box["left"],
                    scan_box["top"],
                    ref_rel=(adaptive_btn_rel_x, adaptive_btn_rel_y),
                    gw_vp=vp,
                )
                if det is not None:
                    det_x, det_y, det_col, det_area = det
                    det_rel_x = (det_x - gw_l) / float(gw_w)
                    det_rel_y = (det_y - gw_t) / float(gw_h)
                    if (
                        adaptive_btn_rel_x is None
                        or abs(det_rel_x - adaptive_btn_rel_x) > 0.015
                        or abs(det_rel_y - adaptive_btn_rel_y) > 0.015
                    ):
                        adaptive_btn_rel_x = det_rel_x
                        adaptive_btn_rel_y = det_rel_y
                        log_cb(f"[Thích ứng] Khóa tâm nút câu: Rel X = {adaptive_btn_rel_x:.3f}, Rel Y = {adaptive_btn_rel_y:.3f} ({det_col})")
                    btn_screen_x = det_x
                    btn_screen_y = det_y
                    btn_box["left"] = btn_screen_x - btn_radius
                    btn_box["top"] = btn_screen_y - btn_radius

                    # Cắt nhanh btn_bgr từ scan_bgr đã có trong RAM (tiết kiệm thời gian chụp màn hình)
                    rel_l = btn_screen_x - btn_radius - scan_box["left"]
                    rel_t = btn_screen_y - btn_radius - scan_box["top"]
                    box_sz = btn_radius * 2
                    if (
                        0 <= rel_l
                        and 0 <= rel_t
                        and (rel_l + box_sz) <= scan_box["width"]
                        and (rel_t + box_sz) <= scan_box["height"]
                    ):
                        bgr = scan_bgr[rel_t : rel_t + box_sz, rel_l : rel_l + box_sz]

            if bgr is None:
                bgr = safe_grab(sct, btn_box)

            if bgr is None:
                if _sleep_check(0.5, stop_event):
                    break
                continue

            green_px, grey_px, purple_px = analyze_button_colors(bgr)

            is_bite = (det_col == "purple") or (purple_px > config.PURPLE_PX_THRESHOLD)
            if is_bite:
                log_cb(f"[Phục hồi] Cá đang cắn ({det_area or purple_px}px tím) -> GIẬT CẦN!")
                _perform_tap(click_mode, adb, vp, btn_screen_x, btn_screen_y, "Giật cần", log_cb, is_fast=True)
                if _sleep_check(0.35, stop_event):
                    break
                state = "MINIGAME_SLIDER"
                log_cb("[3/4] Quét thanh trượt...")
                continue

            is_grey = (det_col == "grey") or (grey_px > config.GREY_PX_THRESHOLD)
            if is_grey and not is_bite:
                log_cb(f"[Phục hồi] Cần dưới nước ({grey_px}px xám) -> Chờ cá cắn...")
                state = "WAITING_BITE"
                bite_wait_start = time.time()
                no_rod_start = 0.0
                last_claim_check_waiting = 0.0
                last_heartbeat = now
                continue

            is_green = (det_col == "green") or (green_px > config.GREEN_PX_THRESHOLD)
            if is_green:
                log_cb(f"[1/4] Thả cần ({green_px}px xanh)...")
                _perform_tap(click_mode, adb, vp, btn_screen_x, btn_screen_y, "Nút quăng cần", log_cb)
                if _sleep_check(1.5, stop_event):
                    break
                state = "WAITING_BITE"
                bite_wait_start = time.time()
                no_rod_start = 0.0
                last_claim_check_waiting = 0.0
                last_heartbeat = time.time()
                continue

            if now - last_heartbeat > 2.0:
                log_cb(f"[Chờ] Xanh: {green_px} | Xám: {grey_px} | Tím: {purple_px}")
                last_heartbeat = now

            if now - wait_ready_start > 1.5:
                log_cb("[Giải phóng] Chạm giải phóng thẻ bài / popup tồn dư...")
                _perform_tap(click_mode, adb, vp, card_screen_x, card_screen_y, "Giải phóng thẻ bài", log_cb)
                time.sleep(0.2)
                _perform_tap(click_mode, adb, vp, card_screen_x, card_confirm_y, "Giải phóng xác nhận giữa", log_cb)
                time.sleep(0.2)
                _perform_tap(click_mode, adb, vp, claim_screen_x, claim_screen_y, "Giải phóng Nhận Ngay", log_cb)
                if _sleep_check(0.5, stop_event):
                    break
                wait_ready_start = time.time()
            else:
                if _sleep_check(0.15, stop_event):
                    break

        # =========================================================
        # BƯỚC 2: CHỜ CÁ CẮN CÂU (WAITING_BITE)
        # =========================================================
        elif state == "WAITING_BITE":
            if now - last_claim_check_waiting > 0.35:
                last_claim_check_waiting = now
                claim_bgr = safe_grab(sct, claim_box)
                if claim_bgr is not None:
                    c_hsv = cv2.cvtColor(claim_bgr, cv2.COLOR_BGR2HSV)
                    c_green = cv2.inRange(
                        c_hsv,
                        np.array(config.HSV_READY_GREEN_LOWER, dtype=np.uint8),
                        np.array(config.HSV_READY_GREEN_UPPER, dtype=np.uint8),
                    )
                    if np.count_nonzero(c_green) > 300:
                        log_cb(f"[Phục hồi] Nút Nhận Ngay xuất hiện khi đang chờ -> Nhận thưởng!")
                        state = "CLAIM_REWARD"
                        continue

            # 2. Tự động thích ứng vị trí nút câu cá trong dải đáy màn hình
            scan_bgr = safe_grab(sct, scan_box)
            bgr = None
            det_col = None
            det_area = 0
            if scan_bgr is not None:
                det = detect_fishing_button(
                    scan_bgr,
                    scan_box["left"],
                    scan_box["top"],
                    ref_rel=(adaptive_btn_rel_x, adaptive_btn_rel_y),
                    gw_vp=vp,
                )
                if det is not None:
                    det_x, det_y, det_col, det_area = det
                    det_rel_x = (det_x - gw_l) / float(gw_w)
                    det_rel_y = (det_y - gw_t) / float(gw_h)
                    if (
                        adaptive_btn_rel_x is None
                        or abs(det_rel_x - adaptive_btn_rel_x) > 0.015
                        or abs(det_rel_y - adaptive_btn_rel_y) > 0.015
                    ):
                        adaptive_btn_rel_x = det_rel_x
                        adaptive_btn_rel_y = det_rel_y
                        log_cb(f"[Thích ứng] Khóa tâm nút câu khi chờ: Rel X = {adaptive_btn_rel_x:.3f}, Rel Y = {adaptive_btn_rel_y:.3f} ({det_col})")
                    btn_screen_x = det_x
                    btn_screen_y = det_y
                    btn_box["left"] = btn_screen_x - btn_radius
                    btn_box["top"] = btn_screen_y - btn_radius

                    rel_l = btn_screen_x - btn_radius - scan_box["left"]
                    rel_t = btn_screen_y - btn_radius - scan_box["top"]
                    box_sz = btn_radius * 2
                    if (
                        0 <= rel_l
                        and 0 <= rel_t
                        and (rel_l + box_sz) <= scan_box["width"]
                        and (rel_t + box_sz) <= scan_box["height"]
                    ):
                        bgr = scan_bgr[rel_t : rel_t + box_sz, rel_l : rel_l + box_sz]

            if bgr is None:
                bgr = safe_grab(sct, btn_box)

            if bgr is None:
                if _sleep_check(0.5, stop_event):
                    break
                continue

            green_px, grey_px, purple_px = analyze_button_colors(bgr)

            # Phát hiện cá cắn (Ưu tiên trực tiếp từ nhận diện thích ứng det_col hoặc qua ngưỡng pixel tím)
            is_bite = (det_col == "purple") or (purple_px > config.PURPLE_PX_THRESHOLD)
            if is_bite:
                log_cb(f"[2/4] CÁ CẮN! ({det_area or purple_px}px tím) -> GIẬT CẦN!")
                _perform_tap(click_mode, adb, vp, btn_screen_x, btn_screen_y, "Giật cần", log_cb, is_fast=True)
                if _sleep_check(0.35, stop_event):
                    break
                state = "MINIGAME_SLIDER"
                log_cb("[3/4] Quét thanh trượt minigame...")
                continue

            is_green = (det_col == "green") or (green_px > config.GREEN_PX_THRESHOLD and grey_px < 300)
            if is_green and not is_bite:
                log_cb(f"[Phục hồi] Cần trên bờ ({green_px}px xanh) -> Thả cần lại!")
                state = "READY_TO_CAST"
                wait_ready_start = time.time()
                continue

            if now - last_heartbeat > 2.0:
                log_cb(f"[2/4] Đang chờ cá cắn... Xám: {grey_px} | Tím: {purple_px}")
                last_heartbeat = now

            # Bất thường: Không có cần dưới nước > 2.5s (chỉ kích hoạt khi chắc chắn không có cá cắn)
            if not is_bite and grey_px < 100 and purple_px < 100 and det_col != "grey":
                if no_rod_start == 0.0:
                    no_rod_start = now
                elif now - no_rod_start > 2.5:
                    log_cb("[Giải phóng] Mất cần > 2.5s -> Tự giải thoát popup...")
                    _perform_tap(click_mode, adb, vp, card_screen_x, card_screen_y, "Giải phóng thẻ", log_cb)
                    time.sleep(0.2)
                    _perform_tap(click_mode, adb, vp, card_screen_x, card_confirm_y, "Giải phóng xác nhận giữa", log_cb)
                    time.sleep(0.2)
                    _perform_tap(click_mode, adb, vp, claim_screen_x, claim_screen_y, "Giải phóng Nhận Ngay", log_cb)
                    state = "READY_TO_CAST"
                    wait_ready_start = time.time()
                    no_rod_start = 0.0
                    if _sleep_check(0.5, stop_event):
                        break
                    continue
            else:
                no_rod_start = 0.0

            # Timeout an toàn > 18s
            if now - bite_wait_start > 18.0:
                log_cb("[Timeout] Chờ cá cắn > 18s -> Tự giải phóng và thả lại...")
                _perform_tap(click_mode, adb, vp, card_screen_x, card_screen_y, "Đóng thẻ tồn dư", log_cb)
                time.sleep(0.2)
                _perform_tap(click_mode, adb, vp, card_screen_x, card_confirm_y, "Xác nhận giữa tồn dư", log_cb)
                time.sleep(0.2)
                _perform_tap(click_mode, adb, vp, claim_screen_x, claim_screen_y, "Nhận Ngay tồn dư", log_cb)
                state = "READY_TO_CAST"
                wait_ready_start = time.time()
                no_rod_start = 0.0
                if _sleep_check(0.5, stop_event):
                    break
                continue

            if _sleep_check(0.015, stop_event):
                break

        # =========================================================
        # BƯỚC 3: MINI-GAME THANH TRƯỢT (2 PHA CHUẨN 100%)
        # =========================================================
        elif state == "MINIGAME_SLIDER":
            no_slider_since = 0.0
            last_hit_time = 0.0
            hit_count = 0
            minigame_start = time.time()
            last_bobber_seen = time.time()
            last_claim_check = 0.0
            prev_bobber_x = None

            slider_phase = "SEARCH_BOX"
            locked_yellow = None

            while not stop_event.is_set():
                cur_t = time.time()

                if cur_t - minigame_start > config.MINIGAME_MAX_DURATION:
                    log_cb(f"[Timeout] Minigame > {config.MINIGAME_MAX_DURATION}s -> Thu cần và nhận thưởng...")
                    state = "CLAIM_REWARD"
                    break

                s_bgr = safe_grab(sct, slider_box)
                if s_bgr is None:
                    time.sleep(0.01)
                    continue

                yellow_range, bobber_x = detect_yellow_and_bobber(s_bgr)

                # Cập nhật thời gian nhìn thấy phao đỏ
                if bobber_x is not None:
                    last_bobber_seen = cur_t

                # Kiểm tra định kỳ nút Nhận Ngay mỗi 0.15s (kể cả khi phao chưa mất, đề phòng popup hiện đè)
                if cur_t - last_claim_check > 0.15:
                    last_claim_check = cur_t
                    claim_bgr = safe_grab(sct, claim_box)
                    if claim_bgr is not None:
                        c_hsv = cv2.cvtColor(claim_bgr, cv2.COLOR_BGR2HSV)
                        c_green = cv2.inRange(
                            c_hsv,
                            np.array(config.HSV_READY_GREEN_LOWER, dtype=np.uint8),
                            np.array(config.HSV_READY_GREEN_UPPER, dtype=np.uint8),
                        )
                        if np.count_nonzero(c_green) > 250:
                            log_cb("[3/4] Phát hiện nút Nhận Ngay -> Kết thúc minigame!")
                            state = "CLAIM_REWARD"
                            break

                # Nếu minigame > 0.4s mà không thấy phao đỏ > 0.65s -> Trận đã kết thúc!
                if (cur_t - minigame_start > 0.4) and (cur_t - last_bobber_seen > 0.65):
                    log_cb(f"[3/4] Kéo cá hoàn tất ({hit_count} Hoàn Hảo, phao biến mất). Nhận thưởng...")
                    state = "CLAIM_REWARD"
                    break

                # Kiểm tra mất thanh trượt (chỉ cần không thấy ô vàng trên màn hình là tính timeout kết thúc)
                if yellow_range is None:
                    if no_slider_since == 0.0:
                        no_slider_since = cur_t
                    slider_timeout = 0.35 if hit_count >= 2 else 0.70
                    if cur_t - no_slider_since > slider_timeout:
                        log_cb(f"[3/4] Kéo cá hoàn tất ({hit_count} Hoàn Hảo, thanh trượt kết thúc). Nhận thưởng...")
                        state = "CLAIM_REWARD"
                        break
                else:
                    no_slider_since = 0.0

                # ---------------------------------------------------------
                # PHA 1: SEARCH_BOX - Chờ game sinh ô vàng mới & khóa tọa độ
                # ---------------------------------------------------------
                if slider_phase == "SEARCH_BOX":
                    if cur_t - last_hit_time < 0.20:
                        prev_bobber_x = bobber_x
                        continue

                    if yellow_range is not None:
                        ystart, yend = yellow_range
                        y_width = yend - ystart
                        if y_width >= 8:
                            locked_yellow = (ystart, yend)
                            slider_phase = "WAIT_HIT"
                            prev_bobber_x = bobber_x

                # ---------------------------------------------------------
                # PHA 2: WAIT_HIT - Ô vàng đã khóa, theo dõi phao đỏ để bấm Hoàn Hảo
                # ---------------------------------------------------------
                elif slider_phase == "WAIT_HIT":
                    if locked_yellow is None:
                        slider_phase = "SEARCH_BOX"
                        continue

                    l_start, l_end = locked_yellow

                    if yellow_range is not None:
                        c_start, c_end = yellow_range
                        c_center = (c_start + c_end) / 2
                        l_center = (l_start + l_end) / 2
                        if abs(c_center - l_center) < 30:
                            locked_yellow = (min(l_start, c_start), max(l_end, c_end))
                            l_start, l_end = locked_yellow

                    y_width = l_end - l_start

                    if bobber_x is not None:
                        inside = (l_start <= bobber_x <= l_end)

                        if prev_bobber_x is not None and abs(bobber_x - prev_bobber_x) <= 35:
                            move_min = min(prev_bobber_x, bobber_x)
                            move_max = max(prev_bobber_x, bobber_x)
                            crossed = max(move_min, l_start) <= min(move_max, l_end)
                        else:
                            crossed = False

                        if inside or crossed:
                            _perform_tap(click_mode, adb, vp, btn_screen_x, btn_screen_y, is_fast=True)
                            hit_count += 1
                            last_hit_time = cur_t
                            log_cb(f"  -> [Hoàn Hảo #{hit_count}] Phao ({bobber_x}) trúng ô vàng [{l_start}, {l_end}] (Rộng: {y_width}px)")
                            locked_yellow = None
                            prev_bobber_x = None
                            slider_phase = "SEARCH_BOX"
                            continue

                        prev_bobber_x = bobber_x

            if stop_event.is_set():
                break

        # =========================================================
        # BƯỚC 4: NHẬN QUÀ / ĐÓNG POPUP (CLAIM_REWARD - ĐA TẦNG AN TOÀN)
        # =========================================================
        elif state == "CLAIM_REWARD":
            log_cb("[4/4] Chờ hoạt ảnh cá (1.0s)...")
            if _sleep_check(1.0, stop_event):
                break

            # Chuỗi chạm 3 điểm an toàn đa tầng (Tâm thẻ -> Nút giữa -> Nút đáy)
            # Giúp đóng triệt để mọi popup: Cá Lam, Kỷ Lục Mới, Cá Mới, Chia Sẻ kể cả trên máy giật lag 2GB RAM
            for attempt in range(4):
                # Nhịp 1: Chạm tâm thẻ bài kỷ lục / cá mới (Rel Y = 0.480)
                _perform_tap(click_mode, adb, vp, card_screen_x, card_screen_y, f"Đóng thẻ bài (Lần {attempt + 1})", log_cb)
                if _sleep_check(0.25, stop_event):
                    break

                # Nhịp 2: Chạm nút xác nhận / tiếp tục giữa màn hình (Rel Y = 0.720)
                _perform_tap(click_mode, adb, vp, card_screen_x, card_confirm_y, f"Chạm xác nhận giữa (Lần {attempt + 1})", log_cb)
                if _sleep_check(0.25, stop_event):
                    break

                # Nhịp 3: Chạm nút Nhận Ngay ở đáy (Rel Y = 0.870)
                _perform_tap(click_mode, adb, vp, claim_screen_x, claim_screen_y, f"Nhận Ngay (Lần {attempt + 1})", log_cb)
                if _sleep_check(0.35, stop_event):
                    break

                # Kiểm tra nút Nhận Ngay xem đã biến mất chưa
                claim_bgr = safe_grab(sct, claim_box)
                has_green = False
                if claim_bgr is not None:
                    c_hsv = cv2.cvtColor(claim_bgr, cv2.COLOR_BGR2HSV)
                    c_green = cv2.inRange(
                        c_hsv,
                        np.array(config.HSV_READY_GREEN_LOWER, dtype=np.uint8),
                        np.array(config.HSV_READY_GREEN_UPPER, dtype=np.uint8),
                    )
                    has_green = np.count_nonzero(c_green) > 250

                # Nếu sau ít nhất 1 lần chạm mà không còn nút Nhận Ngay: kiểm tra xem nút cần câu trên bờ đã xuất hiện chưa
                if not has_green and attempt >= 1:
                    btn_bgr_chk = safe_grab(sct, btn_box)
                    if btn_bgr_chk is not None:
                        chk_g, chk_gr, chk_p = analyze_button_colors(btn_bgr_chk)
                        if chk_g > config.GREEN_PX_THRESHOLD or chk_gr > config.GREY_PX_THRESHOLD:
                            break  # Game đã quay về hồ câu thành công!

            fish_count += 1
            log_cb(f"[4/4] Nhận thưởng thành công! Tổng số cá: {fish_count}")

            if _sleep_check(0.3, stop_event):
                break

            state = "READY_TO_CAST"
            wait_ready_start = time.time()
            log_cb("=" * 35)
            log_cb("[Vòng mới] Chuẩn bị thả mồi...")
            last_heartbeat = time.time()

    log_cb("Đã dừng Auto Câu Cá.")
