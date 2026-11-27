"""
Module Auto Phiêu Lưu Cổ Vật (Relic Adventure)
Kế thừa 100% thuật toán FLEX đa tỉ lệ, nhận diện ải, quái vật, rương và kết toán từ auto_phieuluu.py.
Thay thế thao tác chiếm chuột bằng ADB Tap ngầm.
"""

import time
import threading
from typing import Optional, Tuple, Dict, Callable

import cv2
import numpy as np
import mss

import config
import assets
from core.viewport import screen_to_android
from core.vision import safe_grab, create_capture_session, make_adb_viewport_getter
from core.adb_manager import ADBManager

_templates: Optional[Dict[str, np.ndarray]] = None


def load_templates() -> Dict[str, np.ndarray]:
    global _templates
    if _templates is None:
        _templates = assets.get_phieuluu_templates()
    return _templates


def _sleep(seconds: float, stop_event: threading.Event) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if stop_event.is_set():
            return True
        time.sleep(0.02)
    return False


def _adb_tap(adb: ADBManager, vp: Tuple[int, int, int, int], win_x: int, win_y: int, desc: str = "", log_cb: Optional[Callable[[str], None]] = None):
    if not adb or not adb.active_serial:
        return
    screen_sz = adb.screen_size or (720, 1280)
    ax, ay = screen_to_android(win_x, win_y, vp, screen_sz)
    if desc and log_cb:
        log_cb(f"-> {desc} (Android: {ax}, {ay})")
    adb.tap(ax, ay)


def find_template_flex(
    gray_vp: np.ndarray,
    tpl: np.ndarray,
    roi_rel: Tuple[float, float, float, float],
    thresh: float = 0.68,
) -> Optional[Tuple[float, Tuple[int, int, int, int]]]:
    if gray_vp is None or tpl is None:
        return None

    if len(tpl.shape) == 3:
        tpl_gray = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY)
    else:
        tpl_gray = tpl

    vh, vw = gray_vp.shape[:2]
    rx1 = int(vw * roi_rel[0])
    ry1 = int(vh * roi_rel[1])
    rx2 = int(vw * roi_rel[2])
    ry2 = int(vh * roi_rel[3])

    sub = gray_vp[ry1:ry2, rx1:rx2]
    if sub.shape[0] < 15 or sub.shape[1] < 15:
        return None

    est_scale = vw / 405.0
    fine_factors = [1.0, 0.96, 1.04, 0.92, 1.08, 0.88, 1.12, 0.84, 1.16, 0.80, 1.22, 1.30, 0.70, 1.40]
    scales = []
    seen = set()
    for sc in [1.0] + [est_scale * f for f in fine_factors]:
        sc_r = round(sc, 3)
        if 0.35 <= sc_r <= 2.5 and sc_r not in seen:
            seen.add(sc_r)
            scales.append(sc_r)

    best_score = 0.0
    best_match: Optional[Tuple[int, int, int, int]] = None

    for cur_sc in scales:
        tw = int(tpl_gray.shape[1] * cur_sc)
        th = int(tpl_gray.shape[0] * cur_sc)
        if tw >= sub.shape[1] or th >= sub.shape[0] or tw < 10 or th < 10:
            continue

        interp = cv2.INTER_AREA if cur_sc < 1.0 else cv2.INTER_LINEAR
        cur_tpl = cv2.resize(tpl_gray, (tw, th), interpolation=interp)

        res = cv2.matchTemplate(sub, cur_tpl, cv2.TM_CCOEFF_NORMED)
        _, max_v, _, max_l = cv2.minMaxLoc(res)

        if max_v > best_score:
            best_score = float(max_v)
            cx = rx1 + max_l[0] + tw // 2
            cy = ry1 + max_l[1] + th // 2
            best_match = (cx, cy, tw, th)

        if max_v >= 0.88:
            break

    if best_score >= thresh and best_match is not None:
        return best_score, best_match

    return None


def classify_screen_flex(vp_img: np.ndarray) -> Tuple[str, float, Optional[Tuple[int, int]]]:
    if vp_img is None or vp_img.size == 0:
        return "UNKNOWN", 0.0, None

    vh, vw = vp_img.shape[:2]
    gray = cv2.cvtColor(vp_img, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(vp_img, cv2.COLOR_BGR2HSV)
    tpls = load_templates()

    # 0. Menu Thoát / Tạm Dừng
    if "tiep_tuc" in tpls:
        m = find_template_flex(gray, tpls["tiep_tuc"], (0.35, 0.70, 0.65, 0.95), thresh=0.70)
        if m:
            score, (cx, cy, tw, th) = m
            return "PAUSE_MENU", score, (cx, cy)

    # 1. Màn Kết Toán / Thất Bại
    if "chap_nhan" in tpls:
        m = find_template_flex(gray, tpls["chap_nhan"], (0.10, 0.70, 0.90, 0.98), thresh=0.68)
        if m:
            score, (cx, cy, tw, th) = m
            return "SETTLEMENT", score, (cx, cy)

    # 2. Màn Mở Nhộng / Quà Mốc
    if "mo_tat_ca" in tpls:
        m = find_template_flex(gray, tpls["mo_tat_ca"], (0.45, 0.80, 0.98, 0.96), thresh=0.75)
        if m:
            score, (cx, cy, tw, th) = m
            return "REWARD_EGG", score, (cx, cy)

    # Fallback màu sắc cặp nút xanh + vàng
    y1_btn, y2_btn = int(vh * 0.80), int(vh * 0.96)
    roi_l = hsv[y1_btn:y2_btn, int(vw * 0.04):int(vw * 0.50)]
    mask_g = cv2.inRange(roi_l, np.array([35, 120, 140]), np.array([85, 255, 255]))
    cnts_g, _ = cv2.findContours(mask_g, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    roi_r = hsv[y1_btn:y2_btn, int(vw * 0.50):int(vw * 0.96)]
    mask_y = cv2.inRange(roi_r, np.array([12, 120, 150]), np.array([35, 255, 255]))
    cnts_y, _ = cv2.findContours(mask_y, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for cg in cnts_g:
        _, _, g_bw, g_bh = cv2.boundingRect(cg)
        if g_bw < 0.25 * vw or g_bh < 0.03 * vh or not (2.5 <= g_bw / g_bh <= 4.5):
            continue
        for cy in cnts_y:
            y_bx, y_by, y_bw, y_bh = cv2.boundingRect(cy)
            if y_bw < 0.25 * vw or y_bh < 0.03 * vh or not (2.5 <= y_bw / y_bh <= 4.5):
                continue
            cx = int(vw * 0.50) + y_bx + y_bw // 2
            cy = y1_btn + y_by + y_bh // 2
            return "REWARD_EGG", 0.95, (cx, cy)

    # 3. Bảng Phần Thưởng / Nút OK
    if "btn_ok" in tpls:
        m = find_template_flex(gray, tpls["btn_ok"], (0.20, 0.82, 0.80, 0.96), thresh=0.88)
        if m:
            score, (cx, cy, tw, th) = m
            if 0.35 <= cx / vw <= 0.65:
                return "REWARD_OK", score, (cx, cy)

    # 4. Quái Vật Chặn Đường
    if "chien_dau" in tpls:
        m = find_template_flex(gray, tpls["chien_dau"], (0.45, 0.55, 0.98, 0.98), thresh=0.68)
        if m:
            score, (cx, cy, tw, th) = m
            return "MONSTER", score, (cx, cy)

    # 5. Popup Cổ Vật / Bảo Vật
    if "cham_tiep_tuc" in tpls:
        m = find_template_flex(gray, tpls["cham_tiep_tuc"], (0.05, 0.75, 0.95, 1.00), thresh=0.72)
        if m:
            score, (cx, cy, tw, th) = m
            return "POPUP_RELIC", score, (cx, cy)

    # 6. Sảnh Chính
    if "bat_dau" in tpls:
        m = find_template_flex(gray, tpls["bat_dau"], (0.15, 0.70, 0.85, 0.98), thresh=0.68)
        if m:
            score, (cx, cy, tw, th) = m
            return "LOBBY", score, (cx, cy)
    if "bat_dau_cn" in tpls:
        m = find_template_flex(gray, tpls["bat_dau_cn"], (0.15, 0.70, 0.85, 0.98), thresh=0.68)
        if m:
            score, (cx, cy, tw, th) = m
            return "LOBBY", score, (cx, cy)

    # 7. Trong Mê Cung - Nút Tiến Lên
    if "tien_len" in tpls:
        m = find_template_flex(gray, tpls["tien_len"], (0.15, 0.50, 0.85, 1.00), thresh=0.65)
        if m:
            score, (cx, cy, tw, th) = m
            return "IN_DUNGEON", score, (cx, cy)
        else:
            roi_y1 = int(vh * 0.65)
            roi_y2 = int(vh * 0.98)
            roi_x1 = int(vw * 0.20)
            roi_x2 = int(vw * 0.80)
            roi_hsv = hsv[roi_y1:roi_y2, roi_x1:roi_x2]
            mask_cyan = cv2.inRange(roi_hsv, np.array([65, 75, 95]), np.array([100, 255, 255]))
            cnts, _ = cv2.findContours(mask_cyan, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            min_dim = int(35 * (vw / 405.0))
            for c in cnts:
                bx, by, bw, bh = cv2.boundingRect(c)
                if bw >= min_dim and bh >= min_dim and abs(bw - bh) < int(25 * (vw / 405.0)):
                    cx = roi_x1 + bx + bw // 2
                    cy = roi_y1 + by + bh // 2
                    return "IN_DUNGEON", 0.90, (cx, cy)

    return "UNKNOWN", 0.0, None


def run_adventure_loop(
    adb: ADBManager,
    get_vp_func: Callable[[], Optional[Tuple[int, int, int, int]]],
    stop_event: threading.Event,
    log_cb: Callable[[str], None],
    capture_mode: str = "mss",
):
    """Vòng lặp chính của Auto Phiêu Lưu (hỗ trợ 'mss' và 'adb' chạy ngầm)."""
    cap_desc = "Chạy ngầm ADB" if capture_mode == "adb" else "Hiển thị MSS"
    log_cb(f"Khởi động Auto Phiêu Lưu Cổ Vật ({cap_desc})...")
    sct = create_capture_session(adb, capture_mode)
    active_get_vp = make_adb_viewport_getter(sct, adb) if capture_mode == "adb" else get_vp_func

    runs_count = 0
    advances_count = 0
    relics_count = 0
    last_known_state = "UNKNOWN"
    last_known_state_time = time.time()
    same_state_count = 0

    while not stop_event.is_set():
        vp = active_get_vp()
        if not vp:
            log_cb("Chờ phát hiện cửa sổ game...")
            _sleep(1.0, stop_event)
            continue

        gw_l, gw_t, gw_w, gw_h = vp
        vp_img = safe_grab(sct, {"left": gw_l, "top": gw_t, "width": gw_w, "height": gw_h})
        if vp_img is None:
            _sleep(0.3, stop_event)
            continue

        state, score, center_pt = classify_screen_flex(vp_img)
        now = time.time()

        if state != "UNKNOWN":
            last_known_state_time = now
            if state == last_known_state:
                same_state_count += 1
            else:
                same_state_count = 1
                last_known_state = state
        else:
            same_state_count = 0

        if state == "LOBBY":
            cx = gw_l + (center_pt[0] if center_pt else int(gw_w * config.PHIEULUU_START_REL_X))
            cy = gw_t + (center_pt[1] if center_pt else int(gw_h * config.PHIEULUU_START_REL_Y))
            log_cb("Sảnh chính: Bấm 'Bắt Đầu Phiêu Lưu!'")
            _adb_tap(adb, vp, cx, cy, "Bắt Đầu", log_cb)
            runs_count += 1
            _sleep(config.PHIEULUU_DELAY_AFTER_START, stop_event)
            continue

        elif state == "IN_DUNGEON":
            max_retries = getattr(config, "PHIEULUU_SAME_STATE_MAX_RETRIES", 6)
            if same_state_count > max_retries:
                log_cb(f"[Cảnh báo] Bấm 'Tiến Lên' {same_state_count} lần liên tiếp mà chưa đổi cảnh.")
                log_cb("[Chống kẹt] Có thể ĐÃ HẾT ĐUỐC hoặc lag -> Chạm nhẹ điểm an toàn...")
                cx = int(gw_l + gw_w * config.PHIEULUU_DISMISS_REL_X)
                cy = int(gw_t + gw_h * config.PHIEULUU_DISMISS_REL_Y)
                _adb_tap(adb, vp, cx, cy, "Chạm an toàn", log_cb)
                same_state_count = 0
                _sleep(1.0, stop_event)
                continue

            cx = gw_l + (center_pt[0] if center_pt else int(gw_w * config.PHIEULUU_ADVANCE_REL_X))
            cy = gw_t + (center_pt[1] if center_pt else int(gw_h * config.PHIEULUU_ADVANCE_REL_Y))
            advances_count += 1
            log_cb(f"Mê cung: Bấm 'Tiến Lên' (Bước {advances_count})")
            _adb_tap(adb, vp, cx, cy, "Tiến Lên", log_cb)
            _sleep(config.PHIEULUU_DELAY_AFTER_ADVANCE, stop_event)
            continue

        elif state == "POPUP_RELIC":
            log_cb("Nhận Bảo Vật -> Chờ 1.0s timing hoạt ảnh...")
            if _sleep(config.PHIEULUU_DELAY_POPUP_TIMING, stop_event):
                break
            cx = int(gw_l + gw_w * config.PHIEULUU_DISMISS_REL_X)
            cy = int(gw_t + gw_h * config.PHIEULUU_DISMISS_REL_Y)
            _adb_tap(adb, vp, cx, cy, "Đóng Popup bảo vật", log_cb)
            relics_count += 1
            log_cb(f"Đã nhận cổ vật thứ {relics_count}!")
            _sleep(config.PHIEULUU_DELAY_AFTER_DISMISS, stop_event)
            continue

        elif state == "MONSTER":
            cx = gw_l + (center_pt[0] if center_pt else int(gw_w * config.PHIEULUU_FIGHT_REL_X))
            cy = gw_t + (center_pt[1] if center_pt else int(gw_h * config.PHIEULUU_FIGHT_REL_Y))
            log_cb("Gặp quái vật -> Luôn chọn 'Chiến Đấu'!")
            _adb_tap(adb, vp, cx, cy, "Chiến Đấu", log_cb)
            _sleep(config.PHIEULUU_DELAY_AFTER_FIGHT, stop_event)
            continue

        elif state == "SETTLEMENT":
            cx = gw_l + (center_pt[0] if center_pt else int(gw_w * config.PHIEULUU_SETTLE_REL_X))
            cy = gw_t + (center_pt[1] if center_pt else int(gw_h * config.PHIEULUU_SETTLE_REL_Y))
            log_cb("Kết toán lượt chơi -> Bấm 'Chấp Nhận' và reset về Sảnh...")
            _adb_tap(adb, vp, cx, cy, "Chấp Nhận", log_cb)
            _sleep(config.PHIEULUU_DELAY_AFTER_RESET, stop_event)
            continue

        elif state == "REWARD_EGG":
            cx = gw_l + (center_pt[0] if center_pt else int(gw_w * config.PHIEULUU_UNBOX_REL_X))
            cy = gw_t + (center_pt[1] if center_pt else int(gw_h * config.PHIEULUU_UNBOX_REL_Y))
            log_cb("Quà mốc -> Bấm 'Mở Tất Cả'...")
            _adb_tap(adb, vp, cx, cy, "Mở Tất Cả", log_cb)
            _sleep(config.PHIEULUU_DELAY_AFTER_UNBOX, stop_event)
            continue

        elif state == "REWARD_OK":
            cx = gw_l + (center_pt[0] if center_pt else int(gw_w * config.PHIEULUU_OK_REL_X))
            cy = gw_t + (center_pt[1] if center_pt else int(gw_h * config.PHIEULUU_OK_REL_Y))
            log_cb("Bảng thưởng -> Bấm 'OK'")
            _adb_tap(adb, vp, cx, cy, "Bấm OK", log_cb)
            _sleep(config.PHIEULUU_DELAY_AFTER_OK, stop_event)
            continue

        elif state == "PAUSE_MENU":
            cx = gw_l + (center_pt[0] if center_pt else int(gw_w * 0.47))
            cy = gw_t + (center_pt[1] if center_pt else int(gw_h * 0.83))
            log_cb("Bảng tạm dừng -> Bấm 'Tiếp Tục'")
            _adb_tap(adb, vp, cx, cy, "Tiếp Tục", log_cb)
            _sleep(1.0, stop_event)
            continue

        else:
            now = time.time()
            if state != last_known_state:
                last_known_state = state
                last_known_state_time = now

            unknown_duration = now - last_known_state_time
            if unknown_duration >= getattr(config, "PHIEULUU_WATCHDOG_UNKNOWN_TIMEOUT", 3.5):
                log_cb(f"[Chống treo] Đợi hoạt ảnh quá {unknown_duration:.1f}s -> Chạm an toàn...")
                cx = int(gw_l + gw_w * config.PHIEULUU_DISMISS_REL_X)
                cy = int(gw_t + gw_h * config.PHIEULUU_DISMISS_REL_Y)
                _adb_tap(adb, vp, cx, cy, "Chạm an toàn", log_cb)
                last_known_state_time = now - 1.5

        _sleep(0.35, stop_event)

    log_cb("Đã dừng Auto Phiêu Lưu.")
