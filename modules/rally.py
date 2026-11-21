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


def _is_tile_in_dict(tile: Tuple[int, int], target_dict: Dict[Tuple[int, int], float], threshold: int = 35) -> bool:
    tx, ty = tile
    return any(abs(tx - cx) < threshold and abs(ty - cy) < threshold for cx, cy in target_dict.keys())


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

    # 1. Type A: Popup danh sách Rally
    tab = screen_crop[int(gw_h * 0.15):int(gw_h * 0.22), int(gw_w * 0.03):int(gw_w * 0.40)]
    top_dim = screen_crop[int(gw_h * 0.09):int(gw_h * 0.14), int(gw_w * 0.20):int(gw_w * 0.80)]
    is_multi_sheet = (tab.size > 0 and top_dim.size > 0 and np.mean(tab) < 75.0 and np.mean(top_dim) < 70.0)

    if is_multi_sheet:
        bx1, bx2 = int(gw_w * 0.55), int(gw_w * 0.95)
        by1, by2 = int(gw_h * 0.22), int(gw_h * 0.85)
        card_crop = screen_crop[by1:by2, bx1:bx2]
        hsv_cards = cv2.cvtColor(card_crop, cv2.COLOR_BGR2HSV)

        green_mask = cv2.inRange(hsv_cards, np.array([35, 100, 100]), np.array([85, 255, 255]))
        contours_g, _ = cv2.findContours(green_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        green_btns = []
        min_btn_w = int(gw_w * 0.16)
        for c in contours_g:
            cx, cy, bw, bh = cv2.boundingRect(c)
            if bw >= min_btn_w and 18 <= bh <= 55:
                green_btns.append((bx1 + cx + bw // 2, by1 + cy + bh // 2))
        green_btns.sort(key=lambda b: b[1])

        joined_any = False
        cooldown_time = getattr(config, "RALLY_JOINED_COOLDOWN", 30.0)
        if green_btns:
            # Lần lượt tham gia tất cả các Rally còn slot xanh trong danh sách (xử lý chồng Rally)
            for idx, (btn_x, btn_y) in enumerate(green_btns):
                if stop_event.is_set():
                    break
                _adb_tap(adb, vp, gw_l + btn_x, gw_t + btn_y, f"Tham gia Rally {idx+1}/{len(green_btns)}", log_cb)
                joined_any = True
                _sleep(0.35, stop_event)

            if _last_clicked_tile is not None:
                _recently_joined_tiles[_last_clicked_tile] = time.time() + cooldown_time
            if _sleep(0.3, stop_event):
                return True, True
        else:
            if _last_clicked_tile is not None:
                _full_tiles_cooldown[_last_clicked_tile] = time.time() + config.RALLY_FULL_TILE_COOLDOWN
                if log_cb:
                    log_cb(f"Ô ({_last_clicked_tile[0]}, {_last_clicked_tile[1]}) đã đầy -> Bỏ qua {int(config.RALLY_FULL_TILE_COOLDOWN)}s")

        safe_close_x = int(gw_l + gw_w * 0.50)
        safe_close_y = int(gw_t + gw_h * 0.12)
        _adb_tap(adb, vp, safe_close_x, safe_close_y, "Đóng Popup danh sách", log_cb)
        _sleep(0.35, stop_event)
        _last_clicked_tile = None
        return True, joined_any

    # 2. Type D: Bảng mỏ vàng phe ta (chỉ bấm nút [X] ở đáy khi xác nhận có thanh quân phòng thủ xanh > 1500px)
    crop_green_bar = screen_crop[int(gw_h * 0.66):int(gw_h * 0.72), int(gw_w * 0.15):int(gw_w * 0.85)]
    hsv_bar = cv2.cvtColor(crop_green_bar, cv2.COLOR_BGR2HSV)
    green_bar_px = int(np.count_nonzero(cv2.inRange(hsv_bar, (35, 100, 100), (85, 255, 255))))

    crop_close_x = screen_crop[int(gw_h * 0.925):int(gw_h * 0.980), int(gw_w * 0.44):int(gw_w * 0.56)]
    w_x_mask = (crop_close_x[:, :, 0] > 180) & (crop_close_x[:, :, 1] > 180) & (crop_close_x[:, :, 2] > 180)
    x_white_px = int(np.count_nonzero(w_x_mask))

    if green_bar_px > 1500 and x_white_px > 100:
        close_x = int(gw_l + gw_w * 0.50)
        close_y = int(gw_t + gw_h * 0.955)
        _adb_tap(adb, vp, close_x, close_y, "Đóng bảng ô đất đồng minh (Nút X)", log_cb)
        _sleep(config.RALLY_DELAY_AFTER_BACK_CLICK, stop_event)
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
    matches = []
    scale_factors = getattr(config, "RALLY_SCALE_FACTORS", [1.00, 1.04, 0.96, 1.08, 0.92, 1.12, 0.88, 0.80, 0.72, 0.67, 1.20, 1.28])
    match_thresh = getattr(config, "RALLY_MATCH_THRESHOLD", 0.62)

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
                if not any(abs(m[0] - x) < cur_tw * 0.6 and abs(m[1] - y) < cur_th * 0.6 for m in matches):
                    matches.append((x, y, cur_tw, cur_th, tname, float(res[y, x])))

    for x, y, cur_tw, cur_th, faction, score in matches:
        if stop_event.is_set():
            return None

        click_x = int(gw_l + x + cur_tw // 2)
        click_y = int(my1 + y + int(cur_th * 1.85))
        tile = (click_x, click_y)

        if _is_tile_in_dict(tile, _recently_joined_tiles) or _is_tile_in_dict(tile, _full_tiles_cooldown):
            continue

        ay1 = y + cur_th
        ay2 = min(map_crop.shape[0], y + cur_th + int(gw_h * 0.08))
        ax1 = max(0, x - 10)
        ax2 = min(map_crop.shape[1], x + cur_tw + 10)
        avatar_crop = map_crop[ay1:ay2, ax1:ax2]

        if avatar_crop.size > 0:
            a_hsv = cv2.cvtColor(avatar_crop, cv2.COLOR_BGR2HSV)
            joined_mask = cv2.inRange(
                a_hsv,
                np.array(config.HSV_RALLY_JOINED_GREEN_LOWER, dtype=np.uint8),
                np.array(config.HSV_RALLY_JOINED_GREEN_UPPER, dtype=np.uint8),
            )
            joined_px = int(np.count_nonzero(joined_mask))
            if joined_px >= config.RALLY_JOINED_PX_THRESHOLD:
                if log_cb:
                    log_cb(f"Ô ({click_x}, {click_y}) đã có huy hiệu 'Đã tham gia' ({joined_px}px) -> Bỏ qua")
                _recently_joined_tiles[tile] = time.time() + getattr(config, "RALLY_JOINED_COOLDOWN", 30.0)
                continue

        _last_clicked_tile = tile
        if log_cb:
            log_cb(f"Phát hiện Rally ({faction}) độ khớp {score:.2f} -> Bấm mở Popup")

        _adb_tap(adb, vp, click_x, click_y, f"Mở Rally tại ({click_x}, {click_y})", log_cb)
        if _sleep(config.RALLY_DELAY_AFTER_MAP_CLICK, stop_event):
            return None

        is_pop, is_join = _handle_rally_detail_popup(sct, vp, adb, stop_event, log_cb)
        if is_pop:
            return "JOINED" if is_join else "FULL"
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
            _sleep(0.5, stop_event)
            continue

        _sleep(getattr(config, "RALLY_SCAN_INTERVAL", config.RALLY_DELAY_IDLE_SLEEP), stop_event)

    log_cb("Đã dừng Auto Rally.")
