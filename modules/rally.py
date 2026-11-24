"""
Module Auto Rally (Tổng Tấn Công) - Sự kiện Sa Hải Mê Thành (Gold Rush)
Kế thừa 100% thuật toán nhận diện từ src code gốc (auto_rally.py)
Thay thế chuột vật lý bằng ADB Tap ngầm (Không chiếm chuột).
"""

import time
import threading
from typing import Optional, Tuple, Dict, List, Callable

import cv2
import numpy as np
import mss

import config
import assets
from core.viewport import get_game_viewport, screen_to_android
from core.vision import safe_grab
from core.adb_manager import ADBManager

# Quản lý trạng thái nội bộ của Rally
_rally_templates = assets.get_rally_templates()
_timer_template = assets.get_rally_timer_template()
_full_tiles_cooldown: Dict[Tuple[int, int], float] = {}
_recently_joined_tiles: Dict[Tuple[int, int], float] = {}
_last_clicked_tile: Optional[Tuple[int, int]] = None
_effective_vp: Optional[Tuple[int, int, int, int]] = None
_last_raw_vp: Optional[Tuple[int, int, int, int]] = None
_last_pillarbox_check: float = 0.0
_consecutive_reward_claims: int = 0


def reset_rally_state() -> None:
    """Xóa sạch bộ nhớ tạm và cooldown khi bắt đầu phiên chạy mới."""
    global _full_tiles_cooldown, _recently_joined_tiles, _last_clicked_tile, _consecutive_reward_claims
    _full_tiles_cooldown.clear()
    _recently_joined_tiles.clear()
    _last_clicked_tile = None
    _consecutive_reward_claims = 0


def _sleep(seconds: float, stop_event: threading.Event, jitter: bool = True) -> bool:
    """Nghỉ có thể ngắt ngay lập tức khi stop_event được set, kèm độ lệch ngẫu nhiên nhẹ chống game quét."""
    import random
    extra = random.uniform(0.01, 0.035) if jitter else 0.0
    deadline = time.time() + seconds + extra
    while time.time() < deadline:
        if stop_event.is_set():
            return True
        time.sleep(0.02)
    return False


def _adb_tap(adb: ADBManager, vp: Tuple[int, int, int, int], win_x: int, win_y: int, desc: str = "", log_cb: Optional[Callable[[str], None]] = None):
    """Chuyển đổi tọa độ Windows -> Android và chạm ngầm qua ADB."""
    if not adb or not adb.active_serial:
        return
    screen_sz = adb.screen_size or (720, 1280)
    ax, ay = screen_to_android(win_x, win_y, vp, screen_sz)
    if desc and log_cb:
        log_cb(f"-> {desc} (Android: {ax}, {ay})")
    adb.tap(ax, ay)


def _adb_swipe(
    adb: ADBManager,
    vp: Tuple[int, int, int, int],
    win_x1: int,
    win_y1: int,
    win_x2: int,
    win_y2: int,
    duration_ms: int = 280,
    desc: str = "",
    log_cb: Optional[Callable[[str], None]] = None,
):
    """Chuyển đổi tọa độ Windows -> Android và vuốt ngầm qua ADB."""
    if not adb or not adb.active_serial:
        return
    screen_sz = adb.screen_size or (720, 1280)
    ax1, ay1 = screen_to_android(win_x1, win_y1, vp, screen_sz)
    ax2, ay2 = screen_to_android(win_x2, win_y2, vp, screen_sz)
    if desc and log_cb:
        log_cb(f"-> {desc} (Android vuốt: ({ax1}, {ay1}) -> ({ax2}, {ay2}))")
    adb.swipe(ax1, ay1, ax2, ay2, duration_ms)


def _detect_pillarbox(sample_bgr: np.ndarray) -> Tuple[int, int]:
    """Phát hiện viền đen hai bên của màn hình mobile trên PC."""
    gray = cv2.cvtColor(sample_bgr, cv2.COLOR_BGR2GRAY)
    col_means = np.mean(gray, axis=0)
    non_black = np.where(col_means > 10.0)[0]
    if len(non_black) == 0:
        return 0, sample_bgr.shape[1]
    left_bound = int(non_black[0])
    right_bound = int(non_black[-1])
    real_w = max(10, right_bound - left_bound + 1)
    return left_bound, real_w


def _get_effective_vp(sct: mss.MSS, raw_vp: Tuple[int, int, int, int]) -> Tuple[int, int, int, int]:
    global _effective_vp, _last_raw_vp, _last_pillarbox_check
    now = time.time()
    if _effective_vp is not None and raw_vp == _last_raw_vp and (now - _last_pillarbox_check < 10.0):
        return _effective_vp

    gw_l, gw_t, gw_w, gw_h = raw_vp
    _last_raw_vp = raw_vp
    _last_pillarbox_check = now

    sample_y = int(gw_t + gw_h * 0.35)
    sample_h = max(10, int(gw_h * 0.30))
    sample = safe_grab(sct, {"left": gw_l, "top": sample_y, "width": gw_w, "height": sample_h})
    if sample is None:
        _effective_vp = raw_vp
        return raw_vp

    offset_x, real_w = _detect_pillarbox(sample)
    if offset_x > 0 or real_w < gw_w:
        _effective_vp = (gw_l + offset_x, gw_t, real_w, gw_h)
    else:
        _effective_vp = raw_vp
    return _effective_vp


def _is_tile_in_dict(tile: Tuple[int, int], target_dict: Dict[Tuple[int, int], float], threshold: Optional[int] = None) -> bool:
    if threshold is None:
        threshold = getattr(config, "RALLY_FULL_TILE_RADIUS", 30)
    tx, ty = tile
    now = time.time()
    return any(abs(tx - cx) < threshold and abs(ty - cy) < threshold for (cx, cy), exp in target_dict.items() if exp > now)


def _check_and_claim_reward(sct: mss.MSS, vp: Tuple[int, int, int, int], adb: ADBManager, stop_event: threading.Event, log_cb: Optional[Callable[[str], None]] = None) -> bool:
    global _consecutive_reward_claims
    if stop_event.is_set():
        return False

    # Cơ chế Failsafe: Tránh loop bấm nhận quà liên tiếp do nhận diện nhầm chi tiết màn hình
    if _consecutive_reward_claims >= 2:
        if log_cb:
            log_cb("Đã bấm nhận quà 2 lần liên tiếp -> Tự động chuyển tiếp để chống kẹt")
        _consecutive_reward_claims = 0
        return False

    gw_l, gw_t, gw_w, gw_h = vp
    x1 = int(gw_l + gw_w * config.RALLY_REWARD_BTN_REL_X_MIN)
    x2 = int(gw_l + gw_w * config.RALLY_REWARD_BTN_REL_X_MAX)
    y1 = int(gw_t + gw_h * config.RALLY_REWARD_BTN_REL_Y_MIN)
    y2 = int(gw_t + gw_h * config.RALLY_REWARD_BTN_REL_Y_MAX)

    crop = safe_grab(sct, {"left": x1, "top": y1, "width": x2 - x1, "height": y2 - y1})
    if crop is None:
        return False

    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    lower_green = np.array(getattr(config, "HSV_RALLY_REWARD_GREEN_LOWER", [40, 110, 110]), dtype=np.uint8)
    upper_green = np.array(getattr(config, "HSV_RALLY_REWARD_GREEN_UPPER", [80, 255, 255]), dtype=np.uint8)
    mask = cv2.inRange(hsv, lower_green, upper_green)

    px_count = int(np.count_nonzero(mask))
    threshold = getattr(config, "RALLY_REWARD_PX_THRESHOLD", 2000)
    if px_count >= threshold:
        cx = int(gw_l + gw_w * config.RALLY_CLAIM_REWARD_X)
        cy = int(gw_t + gw_h * config.RALLY_CLAIM_REWARD_Y)
        _adb_tap(adb, vp, cx, cy, "Nhận quà Rally", log_cb)
        _consecutive_reward_claims += 1
        _sleep(config.RALLY_DELAY_AFTER_CLAIM_REWARD, stop_event)
        return True

    _consecutive_reward_claims = 0
    return False


def _handle_rally_detail_popup(sct: mss.MSS, vp: Tuple[int, int, int, int], adb: ADBManager, stop_event: threading.Event, log_cb: Optional[Callable[[str], None]] = None) -> Tuple[bool, bool]:
    global _last_clicked_tile, _full_tiles_cooldown, _recently_joined_tiles
    if stop_event.is_set():
        return False, False

    gw_l, gw_t, gw_w, gw_h = vp
    screen_crop = safe_grab(sct, {"left": gw_l, "top": gw_t, "width": gw_w, "height": gw_h})
    if screen_crop is None:
        return False, False

    # 0. Type Alert: Hộp thoại thông báo hệ thống dạng Modal ("Xác Nhận")
    # Ví dụ: "Tổng Tấn Công chưa hoàn thành. Không thể tấn công ô mục tiêu."
    # Đặc điểm: Tiêu đề tím / nền hộp thoại sáng và Nút lớn màu xanh lá "Xác Nhận" ở giữa màn hình.
    btn_modal_crop = screen_crop[int(gw_h * 0.55):int(gw_h * 0.72), int(gw_w * 0.20):int(gw_w * 0.80)]
    hsv_modal = cv2.cvtColor(btn_modal_crop, cv2.COLOR_BGR2HSV)
    green_mask_m = cv2.inRange(hsv_modal, np.array([35, 100, 100]), np.array([85, 255, 255]))
    contours_m, _ = cv2.findContours(green_mask_m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    found_confirm_btn = None
    for c in contours_m:
        cx, cy, bw, bh = cv2.boundingRect(c)
        if bw >= int(gw_w * 0.20) and bh >= 35 and (1.5 <= bw / bh <= 6.0):
            confirm_x = int(gw_l + gw_w * 0.20 + cx + bw // 2)
            confirm_y = int(gw_t + gw_h * 0.55 + cy + bh // 2)
            found_confirm_btn = (confirm_x, confirm_y)
            break

    if found_confirm_btn is not None:
        header_crop = screen_crop[int(gw_h * 0.30):int(gw_h * 0.42), int(gw_w * 0.10):int(gw_w * 0.90)]
        hsv_h = cv2.cvtColor(header_crop, cv2.COLOR_BGR2HSV)
        purple_px = np.count_nonzero(cv2.inRange(hsv_h, np.array([115, 50, 50]), np.array([165, 255, 255])))
        body_crop = screen_crop[int(gw_h * 0.40):int(gw_h * 0.58), int(gw_w * 0.15):int(gw_w * 0.85)]

        if purple_px > 2000 or np.mean(body_crop) > 150:
            confirm_x, confirm_y = found_confirm_btn
            if log_cb:
                log_cb("Phát hiện thông báo 'Không thể tấn công ô mục tiêu' -> Bấm Xác Nhận")
            _adb_tap(adb, vp, confirm_x, confirm_y, "Bấm nút Xác Nhận", log_cb)
            _sleep(0.5, stop_event)

            if _last_clicked_tile is not None:
                cooldown = getattr(config, "RALLY_FULL_TILE_COOLDOWN", 30.0)
                _full_tiles_cooldown[_last_clicked_tile] = time.time() + cooldown
                if log_cb:
                    log_cb(f"Ô ({_last_clicked_tile[0]}, {_last_clicked_tile[1]}) không thể tấn công -> Khóa ô {int(cooldown)}s")
                _last_clicked_tile = None

            return True, False

    # 1. Type A: Popup danh sách Rally
    tab = screen_crop[int(gw_h * 0.15):int(gw_h * 0.22), int(gw_w * 0.03):int(gw_w * 0.40)]
    top_dim = screen_crop[int(gw_h * 0.09):int(gw_h * 0.14), int(gw_w * 0.20):int(gw_w * 0.80)]
    is_multi_sheet = (tab.size > 0 and top_dim.size > 0 and np.mean(tab) < 75.0 and np.mean(top_dim) < 70.0)

    if is_multi_sheet:
        def _get_green_btns(img_crop):
            bx1, bx2 = int(gw_w * 0.55), int(gw_w * 0.95)
            by1, by2 = int(gw_h * 0.22), int(gw_h * 0.85)
            card_crop = img_crop[by1:by2, bx1:bx2]
            hsv_cards = cv2.cvtColor(card_crop, cv2.COLOR_BGR2HSV)
            green_mask = cv2.inRange(hsv_cards, np.array([35, 100, 100]), np.array([85, 255, 255]))
            contours_g, _ = cv2.findContours(green_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            btns = []
            min_btn_w = int(gw_w * 0.16)
            for c in contours_g:
                cx, cy, bw, bh = cv2.boundingRect(c)
                if bw >= min_btn_w and 18 <= bh <= 55:
                    btns.append((bx1 + cx + bw // 2, by1 + cy + bh // 2))
            btns.sort(key=lambda b: b[1])
            return btns

        green_btns = _get_green_btns(screen_crop)

        # Xác thực xem có thực sự là danh sách Rally không (phải có nút xanh hoặc nút xám của các thẻ Rally)
        card_crop_chk = screen_crop[int(gw_h * 0.22):int(gw_h * 0.85), int(gw_w * 0.55):int(gw_w * 0.95)]
        hsv_chk = cv2.cvtColor(card_crop_chk, cv2.COLOR_BGR2HSV)
        grey_mask_chk = cv2.inRange(hsv_chk, np.array([0, 0, 70]), np.array([180, 50, 210]))
        contours_grey_chk, _ = cv2.findContours(grey_mask_chk, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        min_btn_w = int(gw_w * 0.16)
        max_btn_w = int(gw_w * 0.40)
        has_any_card = (len(green_btns) > 0 or any(min_btn_w <= cv2.boundingRect(c)[2] <= max_btn_w and 18 <= cv2.boundingRect(c)[3] <= 55 for c in contours_grey_chk))

        if not has_any_card:
            # Không phát hiện thẻ Rally nào ở cột bên phải -> Không phải bảng danh sách Rally
            pass
        else:
            joined_any = False
            cooldown_time = getattr(config, "RALLY_JOINED_COOLDOWN", 30.0)

            # Nhịp 1: Quét và tham gia các Rally ở trang đầu (Rally 1 -> 4)
            if green_btns:
                for idx, (btn_x, btn_y) in enumerate(green_btns):
                    if stop_event.is_set():
                        break
                    _adb_tap(adb, vp, gw_l + btn_x, gw_t + btn_y, f"Tham gia Rally {idx+1}/{len(green_btns)}", log_cb)
                    joined_any = True
                    _sleep(0.35, stop_event)

            # Vuốt cuộn trang lên để hiển thị các Rally thứ 5, 6... bị tràn bên dưới
            swipe_x = int(gw_l + gw_w * 0.50)
            swipe_y1 = int(gw_t + gw_h * 0.72)
            swipe_y2 = int(gw_t + gw_h * 0.28)
            _adb_swipe(adb, vp, swipe_x, swipe_y1, swipe_x, swipe_y2, 280, "Cuộn xem thêm Rally phía dưới", log_cb)
            _sleep(0.40, stop_event)

            # Nhịp 2: Quét lại sau khi cuộn để bấm các Rally mới lộ ra
            screen_crop2 = safe_grab(sct, {"left": gw_l, "top": gw_t, "width": gw_w, "height": gw_h})
            if screen_crop2 is not None:
                green_btns_p2 = _get_green_btns(screen_crop2)
                if green_btns_p2:
                    for idx, (btn_x, btn_y) in enumerate(green_btns_p2):
                        if stop_event.is_set():
                            break
                        _adb_tap(adb, vp, gw_l + btn_x, gw_t + btn_y, f"Tham gia Rally bổ sung {idx+1}/{len(green_btns_p2)}", log_cb)
                        joined_any = True
                        _sleep(0.35, stop_event)

            if joined_any:
                if _last_clicked_tile is not None:
                    _recently_joined_tiles[_last_clicked_tile] = time.time() + cooldown_time
            else:
                if _last_clicked_tile is not None:
                    _full_tiles_cooldown[_last_clicked_tile] = time.time() + getattr(config, "RALLY_FULL_TILE_COOLDOWN", 30.0)
                    if log_cb:
                        log_cb(f"Ô ({_last_clicked_tile[0]}, {_last_clicked_tile[1]}) đã đầy -> Bỏ qua {int(getattr(config, 'RALLY_FULL_TILE_COOLDOWN', 30.0))}s")

            safe_close_x = int(gw_l + gw_w * 0.50)
            safe_close_y = int(gw_t + gw_h * 0.12)
            _adb_tap(adb, vp, safe_close_x, safe_close_y, "Đóng Popup danh sách", log_cb)
            _sleep(0.35, stop_event)
            _last_clicked_tile = None
            return True, joined_any

    # 2. Type D: Bảng mỏ vàng phe ta / ô đất / cồn cát bị chọn (có nút [X] ở đáy khi xuất hiện thanh phòng thủ hoặc bảng chi tiết)
    crop_green_bar = screen_crop[int(gw_h * 0.66):int(gw_h * 0.74), int(gw_w * 0.15):int(gw_w * 0.85)]
    hsv_bar = cv2.cvtColor(crop_green_bar, cv2.COLOR_BGR2HSV)
    green_bar_px = int(np.count_nonzero(cv2.inRange(hsv_bar, (35, 100, 100), (85, 255, 255))))

    crop_close_x = screen_crop[int(gw_h * 0.925):int(gw_h * 0.980), int(gw_w * 0.44):int(gw_w * 0.56)]
    w_x_mask = (crop_close_x[:, :, 0] > 180) & (crop_close_x[:, :, 1] > 180) & (crop_close_x[:, :, 2] > 180)
    x_white_px = int(np.count_nonzero(w_x_mask))

    banner_crop = screen_crop[int(gw_h * 0.76):int(gw_h * 0.81), int(gw_w * 0.20):int(gw_w * 0.80)]
    banner_mean = float(np.mean(banner_crop)) if banner_crop.size > 0 else 0.0

    pill_crop = screen_crop[int(gw_h * 0.63):int(gw_h * 0.68), int(gw_w * 0.03):int(gw_w * 0.35)]
    pill_mean = float(np.mean(pill_crop)) if pill_crop.size > 0 else 255.0

    is_tile_sheet = (x_white_px > 300) and (green_bar_px > 1500 or banner_mean > 175.0 or pill_mean < 80.0)

    if is_tile_sheet:
        close_x = int(gw_l + gw_w * 0.50)
        close_y = int(gw_t + gw_h * 0.955)
        _adb_tap(adb, vp, close_x, close_y, "Đóng bảng ô đất / tài nguyên (Nút X)", log_cb)
        _sleep(config.RALLY_DELAY_AFTER_BACK_CLICK, stop_event)
        if _last_clicked_tile is not None:
            cooldown = getattr(config, "RALLY_FULL_TILE_COOLDOWN", 30.0)
            _full_tiles_cooldown[_last_clicked_tile] = time.time() + cooldown
            if log_cb:
                log_cb(f"Ô ({_last_clicked_tile[0]}, {_last_clicked_tile[1]}) là ô đất/tài nguyên -> Bỏ qua {int(cooldown)}s")
        _last_clicked_tile = None
        return True, False

    # 3. Type B & C & "Ảo Ảnh": Có nút Back thực sự ở góc trái
    back_x = int(gw_l + gw_w * config.RALLY_POPUP_BACK_X)
    back_y = int(gw_t + gw_h * config.RALLY_POPUP_BACK_Y)
    crop_back = screen_crop[max(0, int(gw_h * 0.90)):min(gw_h, int(gw_h * 0.97)), max(0, int(gw_w * 0.04)):min(gw_w, int(gw_w * 0.14))]
    w_mask = (crop_back[:, :, 0] > 180) & (crop_back[:, :, 1] > 180) & (crop_back[:, :, 2] > 180)
    white_px = int(np.count_nonzero(w_mask))
    mean_val = np.mean(crop_back) if crop_back.size > 0 else 255.0
    # Nút Back thật: Nút tròn màu tím/xám đậm (mean < 140) mang mũi tên trắng rõ nét (200 <= white_px <= 2500), loại trừ 100% Mapview
    has_back_btn = (200 <= white_px <= 2500 and mean_val < 140.0)

    if has_back_btn:
        bx1, bx2 = int(gw_w * 0.52), int(gw_w * 0.92)
        by1, by2 = int(gw_h * 0.88), int(gw_h * 0.97)
        btn_crop = screen_crop[by1:by2, bx1:bx2]
        hsv_btn = cv2.cvtColor(btn_crop, cv2.COLOR_BGR2HSV)

        yellow_px = int(np.count_nonzero(cv2.inRange(hsv_btn, (15, 100, 100), (35, 255, 255))))
        green_px = int(np.count_nonzero(cv2.inRange(hsv_btn, (35, 100, 100), (85, 255, 255))))
        grey_px = int(np.count_nonzero(cv2.inRange(hsv_btn, (0, 0, 100), (180, 40, 210))))

        if yellow_px > 2500:
            if _last_clicked_tile is not None:
                cooldown = getattr(config, "RALLY_FULL_TILE_COOLDOWN", 30.0)
                _full_tiles_cooldown[_last_clicked_tile] = time.time() + cooldown
                if log_cb:
                    log_cb(f"Ô ({_last_clicked_tile[0]}, {_last_clicked_tile[1]}) là ô đất thường -> Bỏ qua {int(cooldown)}s")
            _adb_tap(adb, vp, back_x, back_y, "Đóng bảng tấn công đất", log_cb)
            _sleep(config.RALLY_DELAY_AFTER_BACK_CLICK, stop_event)
            _last_clicked_tile = None
            return True, False

        if green_px > 1500:
            join_btn_x = int(gw_l + gw_w * 0.72)
            join_btn_y = int(gw_t + gw_h * 0.93)
            _adb_tap(adb, vp, join_btn_x, join_btn_y, "Tham gia Rally lẻ", log_cb)
            if _last_clicked_tile is not None:
                _recently_joined_tiles[_last_clicked_tile] = time.time() + getattr(config, "RALLY_JOINED_COOLDOWN", 30.0)
            _sleep(0.4, stop_event)
            _adb_tap(adb, vp, back_x, back_y, "Bấm Back về Map", log_cb)
            _sleep(config.RALLY_DELAY_AFTER_BACK_CLICK, stop_event)
            _last_clicked_tile = None
            return True, True

        if grey_px > 2000:
            if _last_clicked_tile is not None:
                _full_tiles_cooldown[_last_clicked_tile] = time.time() + config.RALLY_FULL_TILE_COOLDOWN
                if log_cb:
                    log_cb(f"Rally lẻ tại ({_last_clicked_tile[0]}, {_last_clicked_tile[1]}) đã đầy -> Bỏ qua {int(config.RALLY_FULL_TILE_COOLDOWN)}s")
            _adb_tap(adb, vp, back_x, back_y, "Back về Map", log_cb)
            _sleep(config.RALLY_DELAY_AFTER_BACK_CLICK, stop_event)
            _last_clicked_tile = None
            return True, False

        # Không có nút hành động nào khác -> Đây là bảng "Ảo Ảnh" / Bảng xếp hạng cứ điểm (có nút Back)
        if _last_clicked_tile is not None:
            cooldown = getattr(config, "RALLY_FULL_TILE_COOLDOWN", 30.0)
            _full_tiles_cooldown[_last_clicked_tile] = time.time() + cooldown
            if log_cb:
                log_cb(f"Ô ({_last_clicked_tile[0]}, {_last_clicked_tile[1]}) không có Rally -> Bỏ qua {int(cooldown)}s")
        _adb_tap(adb, vp, back_x, back_y, "Đóng bảng Ảo Ảnh/Cứ điểm về Map", log_cb)
        _sleep(config.RALLY_DELAY_AFTER_BACK_CLICK, stop_event)
        _last_clicked_tile = None
        return True, False

    return False, False


def scan_and_join_map_rallies(
    sct: mss.MSS,
    vp: Tuple[int, int, int, int],
    adb: ADBManager,
    stop_event: threading.Event,
    log_cb: Optional[Callable[[str], None]] = None,
) -> Optional[str]:
    global _last_clicked_tile, _full_tiles_cooldown, _recently_joined_tiles
    if stop_event.is_set():
        return None

    gw_l, gw_t, gw_w, gw_h = vp
    now = time.time()
    _full_tiles_cooldown = {p: exp for p, exp in _full_tiles_cooldown.items() if exp > now}
    _recently_joined_tiles = {p: exp for p, exp in _recently_joined_tiles.items() if exp > now}

    my1 = int(gw_t + gw_h * 0.12)
    my2 = int(gw_t + gw_h * 0.82)
    map_crop = safe_grab(sct, {"left": gw_l, "top": my1, "width": gw_w, "height": my2 - my1})
    if map_crop is None:
        return None

    map_gray = cv2.cvtColor(map_crop, cv2.COLOR_BGR2GRAY)
    candidates: List[Tuple[int, int, Tuple[int, int], str, float]] = []

    # Dynamic Adaptive Scaling: Tự động tính tỉ lệ scale tối ưu theo chiều cao cửa sổ game thật của người dùng
    ref_h = getattr(config, "RALLY_BASE_REFERENCE_HEIGHT", 1530.0)
    base_scale = gw_h / float(ref_h) if ref_h > 0 else 1.0
    configured_scales = getattr(config, "RALLY_SCALE_FACTORS", [1.00, 1.04, 0.96, 1.08, 0.92, 0.88, 0.84, 0.80])
    
    # Kết hợp dải scale thích ứng tự động và danh sách cấu hình tĩnh
    dynamic_scales = [base_scale * 1.00, base_scale * 1.04, base_scale * 0.96, base_scale * 1.08, base_scale * 0.92, base_scale * 0.85]
    scale_factors = sorted(list({round(s, 2) for s in (configured_scales + dynamic_scales) if 0.45 <= s <= 1.50}), reverse=True)

    # 1. ENGINE 1: Universal Timer Pill (Đa ngôn ngữ 100%: Bắt các số mm:ss trên nền đen viền vàng)
    timer_tpl = _timer_template if _timer_template is not None else assets.get_rally_timer_template()
    if timer_tpl is not None:
        t_th, t_tw = timer_tpl.shape[:2]
        timer_thresh = getattr(config, "RALLY_TIMER_MATCH_THRESHOLD", 0.52)
        avatar_offset_ratio = getattr(config, "RALLY_TIMER_AVATAR_OFFSET_Y", 0.85)

        for cur_sc in scale_factors:
            cur_tw = max(15, int(t_tw * cur_sc))
            cur_th = max(10, int(t_th * cur_sc))
            if cur_tw >= map_crop.shape[1] or cur_th >= map_crop.shape[0]:
                continue

            scaled_timer = cv2.resize(
                timer_tpl,
                (cur_tw, cur_th),
                interpolation=cv2.INTER_AREA if cur_sc < 1.0 else cv2.INTER_LINEAR,
            )
            res_timer = cv2.matchTemplate(map_crop, scaled_timer, cv2.TM_CCOEFF_NORMED)
            locs_timer = np.where(res_timer >= timer_thresh)
            for pt in zip(*locs_timer[::-1]):
                tx, ty = int(pt[0]), int(pt[1])
                score = float(res_timer[ty, tx])

                # Click rơi thẳng vào TÂM AVATAR (dịch ngược lên trên thanh timer)
                click_x = int(gw_l + tx + cur_tw // 2)
                click_y = int(my1 + ty - int(cur_th * avatar_offset_ratio))
                tile = (click_x, click_y)

                # Peak-Finding NMS: Luôn cập nhật điểm có score cực đại và tọa độ tâm chuẩn nhất trong bán kính 35px
                matched_idx = -1
                for idx, c in enumerate(candidates):
                    if abs(c[0] - click_x) < 35 and abs(c[1] - click_y) < 35:
                        matched_idx = idx
                        break
                if matched_idx == -1:
                    candidates.append((click_x, click_y, tile, f"TimerPill_{cur_sc:.2f}", score))
                elif score > candidates[matched_idx][4]:
                    candidates[matched_idx] = (click_x, click_y, tile, f"TimerPill_{cur_sc:.2f}", score)

    # 2. ENGINE 2: Banner Text Templates (Dự phòng bổ trợ cho Tiếng Việt)
    match_thresh = getattr(config, "RALLY_MATCH_THRESHOLD", 0.58)
    for tname, tpl in _rally_templates:
        is_clean = ("clean" in tname)
        tpl_th, tpl_tw = tpl.shape[:2]
        tpl_gray = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY) if is_clean else None

        for cur_sc in scale_factors:
            cur_tw = max(10, int(tpl_tw * cur_sc))
            cur_th = max(10, int(tpl_th * cur_sc))
            if cur_tw >= map_crop.shape[1] or cur_th >= map_crop.shape[0]:
                continue

            scaled_temp = cv2.resize(
                tpl_gray if is_clean else tpl,
                (cur_tw, cur_th),
                interpolation=cv2.INTER_AREA if cur_sc < 1.0 else cv2.INTER_LINEAR,
            )
            res = cv2.matchTemplate(map_gray if is_clean else map_crop, scaled_temp, cv2.TM_CCOEFF_NORMED)
            locs = np.where(res >= match_thresh)
            for pt in zip(*locs[::-1]):
                x, y = int(pt[0]), int(pt[1])
                score = float(res[y, x])
                click_x = int(gw_l + x + cur_tw // 2)
                click_y = int(my1 + y + int(cur_th * 1.85))
                tile = (click_x, click_y)

                # Peak-Finding NMS: Cập nhật nếu tìm thấy điểm khớp banner tốt hơn trong bán kính 35px
                matched_idx = -1
                for idx, c in enumerate(candidates):
                    if abs(c[0] - click_x) < 35 and abs(c[1] - click_y) < 35:
                        matched_idx = idx
                        break
                if matched_idx == -1:
                    candidates.append((click_x, click_y, tile, tname, score))
                elif score > candidates[matched_idx][4]:
                    candidates[matched_idx] = (click_x, click_y, tile, tname, score)

    # Sắp xếp ưu tiên độ tin cậy score giảm dần
    candidates.sort(key=lambda c: c[4], reverse=True)

    for click_x, click_y, tile, faction, score in candidates:
        if stop_event.is_set():
            return None

        if _is_tile_in_dict(tile, _recently_joined_tiles) or _is_tile_in_dict(tile, _full_tiles_cooldown):
            continue

        _last_clicked_tile = tile
        if log_cb:
            log_cb(f"Phát hiện Rally ({faction}) độ khớp {score:.2f} -> Bấm mở Avatar tại ({click_x}, {click_y})")

        _adb_tap(adb, vp, click_x, click_y, f"Mở Rally tại Avatar ({click_x}, {click_y})", log_cb)
        if _sleep(config.RALLY_DELAY_AFTER_MAP_CLICK, stop_event):
            return None

        is_pop, is_join = _handle_rally_detail_popup(sct, vp, adb, stop_event, log_cb)
        if not is_pop:
            # Thử kiểm tra lại lần 2 sau 0.35s phòng trường hợp giả lập lag mở popup chậm
            if not _sleep(0.35, stop_event):
                is_pop, is_join = _handle_rally_detail_popup(sct, vp, adb, stop_event, log_cb)

        if is_pop:
            return "JOINED" if is_join else "FULL"

        # Nếu đã bấm mở nhưng không có bất kỳ popup nào xuất hiện (ô không tương tác / lag / đã kết thúc / vô tình chọn ô đất):
        # BƯỚC TỰ GIẢI THOÁT: Chạm vùng bản đồ trống phía trên (50%, 20%) để chắc chắn hủy chọn ô đất và đóng mọi panel tồn đọng
        _adb_tap(adb, vp, int(gw_l + gw_w * 0.50), int(gw_t + gw_h * 0.20), "Bỏ chọn ô đất (Tự giải thoát)", log_cb)
        _sleep(0.3, stop_event)
        ensure_map_overview(sct, vp, adb, stop_event, None)

        cooldown = getattr(config, "RALLY_NON_INTERACTIVE_COOLDOWN", 20.0)
        _full_tiles_cooldown[tile] = time.time() + cooldown
        if log_cb:
            log_cb(f"Ô ({tile[0]}, {tile[1]}) không mở Popup -> Đã tự giải thoát & tạm bỏ qua {int(cooldown)}s")
        _last_clicked_tile = None
        return "CLICKED"

    return None


def ensure_map_overview(
    sct: mss.MSS,
    vp: Tuple[int, int, int, int],
    adb: ADBManager,
    stop_event: threading.Event,
    log_cb: Optional[Callable[[str], None]] = None,
) -> bool:
    """
    Đảm bảo bản đồ Sa Hải Mê Thành luôn ở chế độ toàn cảnh rộng nhất.
    Tự động chạm vào nút Kính Lúp dấu trừ ở góc dưới trái (Rel X: 0.084, Rel Y: 0.770)
    để mở toàn cảnh 4 phe nếu người dùng quên chưa bấm.
    """
    if stop_event.is_set():
        return False

    gw_l, gw_t, gw_w, gw_h = vp
    click_x = int(gw_l + gw_w * getattr(config, "RALLY_ZOOM_BTN_REL_X", 0.084))
    click_y = int(gw_t + gw_h * getattr(config, "RALLY_ZOOM_BTN_REL_Y", 0.770))

    zoom_tpl = assets.get_zoom_btn_template()
    has_zoom_minus = False
    if zoom_tpl is not None:
        roi_y1 = int(gw_t + gw_h * 0.68)
        roi_y2 = int(gw_t + gw_h * 0.85)
        roi_x1 = int(gw_l + gw_w * 0.01)
        roi_x2 = int(gw_l + gw_w * 0.25)
        roi_crop = safe_grab(sct, {"left": roi_x1, "top": roi_y1, "width": roi_x2 - roi_x1, "height": roi_y2 - roi_y1})
        if roi_crop is not None:
            best_val = 0.0
            best_pt = None
            for sc in [0.75, 0.85, 0.95, 1.0, 1.1, 1.25]:
                cur_w = int(zoom_tpl.shape[1] * sc)
                cur_h = int(zoom_tpl.shape[0] * sc)
                if cur_w >= roi_crop.shape[1] or cur_h >= roi_crop.shape[0]:
                    continue
                scaled = cv2.resize(zoom_tpl, (cur_w, cur_h))
                res = cv2.matchTemplate(roi_crop, scaled, cv2.TM_CCOEFF_NORMED)
                _, max_v, _, max_l = cv2.minMaxLoc(res)
                if max_v > best_val:
                    best_val = max_v
                    best_pt = (roi_x1 + max_l[0] + cur_w // 2, roi_y1 + max_l[1] + cur_h // 2)

            if best_val >= 0.55 and best_pt is not None:
                click_x, click_y = best_pt
                has_zoom_minus = True

    if has_zoom_minus:
        if log_cb:
            log_cb("Tự động kích hoạt toàn cảnh bản đồ (Kính lúp dấu trừ)...")
        _adb_tap(adb, vp, click_x, click_y, "Kính lúp toàn cảnh", log_cb)
        _sleep(0.5, stop_event)
        return True

    return False


def run_rally_loop(
    adb: ADBManager,
    get_vp_func: Callable[[], Optional[Tuple[int, int, int, int]]],
    stop_event: threading.Event,
    log_cb: Callable[[str], None],
):
    """Vòng lặp chạy chính của Auto Rally."""
    log_cb("Khởi động Auto Rally (Tổng Tấn Công)...")
    reset_rally_state()
    sct = mss.mss()

    is_first_cycle = True
    last_zoom_check = 0.0

    while not stop_event.is_set():
        raw_vp = get_vp_func()
        if not raw_vp:
            log_cb("Chờ phát hiện cửa sổ game...")
            _sleep(1.0, stop_event)
            continue

        vp = _get_effective_vp(sct, raw_vp)

        # Tự động kích hoạt toàn cảnh bản đồ 4 phe khi bắt đầu hoặc định kỳ 60s
        now = time.time()
        if is_first_cycle or (now - last_zoom_check > 60.0):
            ensure_map_overview(sct, vp, adb, stop_event, log_cb if is_first_cycle else None)
            is_first_cycle = False
            last_zoom_check = now

        # 1. Kiểm tra nhận quà nếu trận trước vừa xong
        if _check_and_claim_reward(sct, vp, adb, stop_event, log_cb):
            # Sau khi nhận quà quay lại map, đảm bảo góc nhìn vẫn là toàn cảnh
            ensure_map_overview(sct, vp, adb, stop_event, None)
            continue

        # 2. Quét và bấm Rally trên Mapview
        result = scan_and_join_map_rallies(sct, vp, adb, stop_event, log_cb)
        if result == "JOINED":
            log_cb("Đã tham gia Rally thành công! Đang chờ lượt quét tiếp theo...")
            _sleep(1.5, stop_event)
            continue

        # 3. Kiểm tra popup tồn đọng (tránh kẹt nếu popup bị mở sẵn)
        is_pop, is_join = _handle_rally_detail_popup(sct, vp, adb, stop_event, log_cb)
        if is_pop:
            if is_join:
                log_cb("Đã xử lý popup tồn đọng & tham gia Rally!")
            # Sau khi đóng popup ô đất / cứ điểm, lập tức khôi phục toàn cảnh bản đồ nếu bị zoom
            ensure_map_overview(sct, vp, adb, stop_event, None)
            _sleep(0.5, stop_event)
            continue

        _sleep(getattr(config, "RALLY_SCAN_INTERVAL", config.RALLY_DELAY_IDLE_SLEEP), stop_event)

    log_cb("Đã dừng Auto Rally.")
