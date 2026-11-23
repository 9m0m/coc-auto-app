"""
Module Auto Câu Cá (COC Auto Fishing)
Kế thừa 100% thuật toán nhận diện màu HSV, bộ lọc nhiễu, máy trạng thái 4 bước và
cơ chế 2 pha Continuous Sweep từ auto_cauca.py gốc.
Thay thế toàn bộ click chuột Win32 bằng ADB Tap ngầm (Không chiếm chuột).
"""

import time
import threading
from typing import Optional, Tuple, Callable

import cv2
import numpy as np
import mss

import config
from core.viewport import screen_to_android
from core.vision import safe_grab
from core.adb_manager import ADBManager


def _sleep_check(seconds: float, stop_event: threading.Event) -> bool:
    """Nghỉ có thể ngắt ngay lập tức khi stop_event được bật."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        if stop_event.is_set():
            return True
        time.sleep(0.015)
    return False


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
        log_cb(f"-> {desc} (Android: {ax}, {ay})")
    adb.tap(ax, ay)


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
):
    """
    Vòng lặp chạy chính của Auto Câu Cá (FSM 4 bước + 2 Pha Minigame chuẩn 100%).
    """
    log_cb("Khởi động Auto Câu Cá (Hybrid ADB)...")
    sct = mss.mss()

    state = "READY_TO_CAST"
    wait_ready_start = time.time()
    last_heartbeat = time.time()
    bite_wait_start = time.time()
    no_rod_start = 0.0
    last_claim_check_waiting = 0.0
    fish_count = 0

    while not stop_event.is_set():
        vp = get_vp_func()
        if not vp:
            log_cb("Chờ phát hiện cửa sổ game...")
            _sleep_check(1.0, stop_event)
            continue

        gw_l, gw_t, gw_w, gw_h = vp

        # Tính toán tọa độ và vùng quét theo tỉ lệ chuẩn config
        btn_screen_x = int(gw_l + gw_w * config.BUTTON_REL_X)
        btn_screen_y = int(gw_t + gw_h * config.BUTTON_REL_Y)
        claim_screen_x = int(gw_l + gw_w * config.CLAIM_REL_X)
        claim_screen_y = int(gw_t + gw_h * config.CLAIM_REL_Y)
        card_screen_x = int(gw_l + gw_w * config.CARD_REL_X)
        card_screen_y = int(gw_t + gw_h * config.CARD_REL_Y)

        btn_box = {
            "top": btn_screen_y - 30,
            "left": btn_screen_x - 30,
            "width": 60,
            "height": 60,
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

            bgr = safe_grab(sct, btn_box)
            if bgr is None:
                if _sleep_check(0.5, stop_event):
                    break
                continue

            green_px, grey_px, purple_px = analyze_button_colors(bgr)

            if purple_px > config.PURPLE_PX_THRESHOLD:
                log_cb(f"[Phục hồi] Cá đang cắn ({purple_px}px tím) -> GIẬT CẦN!")
                _adb_tap(adb, vp, btn_screen_x, btn_screen_y, "Giật cần", log_cb)
                if _sleep_check(0.35, stop_event):
                    break
                state = "MINIGAME_SLIDER"
                log_cb("[3/4] Quét thanh trượt...")
                continue

            if grey_px > config.GREY_PX_THRESHOLD:
                log_cb(f"[Phục hồi] Cần dưới nước ({grey_px}px xám) -> Chờ cá cắn...")
                state = "WAITING_BITE"
                bite_wait_start = time.time()
                no_rod_start = 0.0
                last_claim_check_waiting = 0.0
                last_heartbeat = now
                continue

            if green_px > config.GREEN_PX_THRESHOLD:
                log_cb(f"[1/4] Thả cần ({green_px}px xanh)...")
                _adb_tap(adb, vp, btn_screen_x, btn_screen_y, "Nút quăng cần", log_cb)
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

            if now - wait_ready_start > 2.5:
                log_cb("[Giải phóng] Chạm giải phóng thẻ bài / popup tồn dư...")
                _adb_tap(adb, vp, card_screen_x, card_screen_y, "Giải phóng thẻ bài")
                time.sleep(0.3)
                _adb_tap(adb, vp, claim_screen_x, claim_screen_y, "Giải phóng Nhận Ngay")
                if _sleep_check(0.8, stop_event):
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

            bgr = safe_grab(sct, btn_box)
            if bgr is None:
                if _sleep_check(0.5, stop_event):
                    break
                continue

            green_px, grey_px, purple_px = analyze_button_colors(bgr)

            if green_px > config.GREEN_PX_THRESHOLD and grey_px < 300:
                log_cb(f"[Phục hồi] Cần trên bờ ({green_px}px xanh) -> Thả cần lại!")
                state = "READY_TO_CAST"
                wait_ready_start = time.time()
                continue

            if now - last_heartbeat > 2.0:
                log_cb(f"[2/4] Đang chờ cá cắn... Xám: {grey_px} | Tím: {purple_px}")
                last_heartbeat = now

            # Phát hiện cá cắn
            if purple_px > config.PURPLE_PX_THRESHOLD:
                log_cb(f"[2/4] CÁ CẮN! ({purple_px}px tím) -> GIẬT CẦN!")
                _adb_tap(adb, vp, btn_screen_x, btn_screen_y, "Giật cần", log_cb)
                if _sleep_check(0.35, stop_event):
                    break
                state = "MINIGAME_SLIDER"
                log_cb("[3/4] Quét thanh trượt minigame...")
                continue

            # Bất thường: Không có cần dưới nước > 3s
            if grey_px < 100 and purple_px < 100:
                if no_rod_start == 0.0:
                    no_rod_start = now
                elif now - no_rod_start > 3.0:
                    log_cb("[Giải phóng] Mất cần > 3s -> Tự giải thoát popup...")
                    _adb_tap(adb, vp, card_screen_x, card_screen_y, "Giải phóng thẻ")
                    time.sleep(0.3)
                    _adb_tap(adb, vp, claim_screen_x, claim_screen_y, "Giải phóng Nhận Ngay")
                    state = "READY_TO_CAST"
                    wait_ready_start = time.time()
                    no_rod_start = 0.0
                    if _sleep_check(0.8, stop_event):
                        break
                    continue
            else:
                no_rod_start = 0.0

            # Timeout an toàn > 18s
            if now - bite_wait_start > 18.0:
                log_cb("[Timeout] Chờ cá cắn > 18s -> Tự giải phóng và thả lại...")
                _adb_tap(adb, vp, card_screen_x, card_screen_y, "Đóng thẻ tồn dư")
                time.sleep(0.3)
                _adb_tap(adb, vp, claim_screen_x, claim_screen_y, "Nhận Ngay tồn dư")
                state = "READY_TO_CAST"
                wait_ready_start = time.time()
                no_rod_start = 0.0
                if _sleep_check(0.8, stop_event):
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
                    log_cb(f"[Timeout] Minigame > {config.MINIGAME_MAX_DURATION}s -> Reset...")
                    state = "READY_TO_CAST"
                    wait_ready_start = time.time()
                    break

                s_bgr = safe_grab(sct, slider_box)
                if s_bgr is None:
                    time.sleep(0.01)
                    continue

                yellow_range, bobber_x = detect_yellow_and_bobber(s_bgr)

                # Cập nhật thời gian nhìn thấy phao đỏ & kiểm tra nút Nhận Ngay nếu mất phao
                if bobber_x is not None:
                    last_bobber_seen = cur_t
                else:
                    if cur_t - last_claim_check > 0.12:
                        last_claim_check = cur_t
                        claim_bgr = safe_grab(sct, claim_box)
                        if claim_bgr is not None:
                            c_hsv = cv2.cvtColor(claim_bgr, cv2.COLOR_BGR2HSV)
                            c_green = cv2.inRange(
                                c_hsv,
                                np.array(config.HSV_READY_GREEN_LOWER, dtype=np.uint8),
                                np.array(config.HSV_READY_GREEN_UPPER, dtype=np.uint8),
                            )
                            if np.count_nonzero(c_green) > 300:
                                log_cb(f"[3/4] Phát hiện nút Nhận Ngay -> Kết thúc minigame!")
                                state = "CLAIM_REWARD"
                                break

                # Nếu minigame > 0.4s mà không thấy phao đỏ > 0.65s -> Trận đã kết thúc!
                if (cur_t - minigame_start > 0.4) and (cur_t - last_bobber_seen > 0.65):
                    log_cb(f"[3/4] Kéo cá hoàn tất ({hit_count} Hoàn Hảo, phao biến mất). Nhận thưởng...")
                    state = "CLAIM_REWARD"
                    break

                # Kiểm tra mất thanh trượt
                if yellow_range is None and locked_yellow is None:
                    if no_slider_since == 0.0:
                        no_slider_since = cur_t
                    slider_timeout = 0.35 if hit_count >= 2 else 0.85
                    if cur_t - no_slider_since > slider_timeout:
                        log_cb(f"[3/4] Kéo cá hoàn tất ({hit_count} Hoàn Hảo). Nhận thưởng...")
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
                            _adb_tap(adb, vp, btn_screen_x, btn_screen_y)
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
        # BƯỚC 4: NHẬN QUÀ / ĐÓNG POPUP (CLAIM_REWARD - 3 NHỊP CHUẨN)
        # =========================================================
        elif state == "CLAIM_REWARD":
            log_cb("[4/4] Chờ hoạt ảnh cá (0.6s)...")
            if _sleep_check(0.6, stop_event):
                break

            # Nhịp 1: Chạm trực tiếp tâm thẻ (Rel Y = 0.480) để đóng thẻ Kỷ Lục Mới / Cá Mới
            _adb_tap(adb, vp, card_screen_x, card_screen_y, "Đóng thẻ kỷ lục (Nhịp 1)", log_cb)
            if _sleep_check(0.35, stop_event):
                break

            # Nhịp 2: Chạm nút "Nhận Ngay" (Rel Y = 0.870) của màn hình cá thường
            _adb_tap(adb, vp, claim_screen_x, claim_screen_y, "Nhận Ngay (Nhịp 2)", log_cb)
            if _sleep_check(0.35, stop_event):
                break

            # Nhịp 3: Xác nhận đóng - nếu nút Nhận Ngay vẫn còn thì bấm tiếp tối đa 3 lần
            for retry in range(3):
                claim_bgr = safe_grab(sct, claim_box)
                if claim_bgr is not None:
                    c_hsv = cv2.cvtColor(claim_bgr, cv2.COLOR_BGR2HSV)
                    c_green = cv2.inRange(
                        c_hsv,
                        np.array(config.HSV_READY_GREEN_LOWER, dtype=np.uint8),
                        np.array(config.HSV_READY_GREEN_UPPER, dtype=np.uint8),
                    )
                    if np.count_nonzero(c_green) > 300:
                        log_cb(f"  -> Popup vẫn còn ({np.count_nonzero(c_green)}px xanh), bấm tiếp lần {retry + 1}...")
                        _adb_tap(adb, vp, claim_screen_x, claim_screen_y, "Nhận Ngay bổ sung", log_cb)
                        if _sleep_check(0.35, stop_event):
                            break
                    else:
                        break

            fish_count += 1
            log_cb(f"[4/4] Nhận thưởng thành công! Tổng số cá: {fish_count}")

            if _sleep_check(0.4, stop_event):
                break

            state = "READY_TO_CAST"
            wait_ready_start = time.time()
            log_cb("=" * 35)
            log_cb("[Vòng mới] Chuẩn bị thả mồi...")
            last_heartbeat = time.time()

    log_cb("Đã dừng Auto Câu Cá.")
