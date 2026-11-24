"""
Comprehensive Test Suite for All Known Rally & Popup Cases in COC AutoMaster.
Tests:
1. Modal Alert ("Không thể tấn công ô mục tiêu" -> Bấm nút Xác Nhận -> Cooldown 30s).
2. Type A Popup (Danh sách nhiều Rally -> Nhịp 1 bấm tham gia -> Vuốt cuộn trang -> Nhịp 2 bấm tham gia -> Đóng popup ở đỉnh).
3. Type B Single Rally - Nút xanh ("Tham gia" -> Bấm tham gia -> Bấm Back tím về map -> Cooldown joined).
4. Type B Single Rally - Nút xám ("Chờ chấp thuận" / "Đã đầy" -> Bấm Back tím -> KHÔNG bấm nút xám -> Cooldown 30s).
5. Type B Single Rally - Nút vàng (Bảng tấn công ô đất thường -> Bấm Back tím -> Cooldown 30s).
6. Type B "Ảo Ảnh" / Bảng xếp hạng không có nút hành động -> Bấm Back tím -> Cooldown 30s.
7. Type D Popup (Ô đất / Cồn cát / Mỏ tài nguyên có thanh máu & nút [X] ở đáy giữa -> Bấm nút [X] -> Cooldown 30s).
8. Miss-click Self-Escape (Bấm mở avatar nhưng không hiện popup -> Tap vùng trống 50%, 20% -> Bấm kính lúp -> Cooldown 20s).
9. Peak-Finding NMS (Nhiều điểm match lân cận -> Gom nhóm bán kính 35px, lấy điểm score cao nhất).
10. Claim Reward & Failsafe (Nhận diện nút xanh lá -> Tap nhận quà; Failsafe ngắt nhận quà khi bấm liên tiếp 2 lần).
11. Pillarbox Detection (Viền đen 2 bên màn hình mobile -> Tính đúng left_bound và real_w).
12. Ensure Map Overview (Icon kính lúp dấu trừ -> Kích hoạt toàn cảnh).
13. User 6 Screens Verification (Xác minh 100% chính xác trên 6 ảnh thực tế: Viewmap KHÔNG bấm X, các popup đóng đúng nút).
"""

import os
import sys
import glob
import threading
import unittest
from unittest.mock import patch
import cv2
import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import config
import assets
from modules import rally


class MockADB:
    """Mock ADBManager để ghi nhận toàn bộ tap và swipe trong quá trình kiểm thử."""
    def __init__(self, screen_size=(720, 1280)):
        self.active_serial = "emulator-5554"
        self.screen_size = screen_size
        self.taps = []
        self.swipes = []

    def tap(self, x: int, y: int):
        self.taps.append((x, y))

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 280):
        self.swipes.append((x1, y1, x2, y2, duration_ms))

    def clear(self):
        self.taps.clear()
        self.swipes.clear()


def make_mock_grab(full_frame: np.ndarray):
    """Mô phỏng chính xác hành vi của mss.grab / safe_grab khi cắt theo ROI monitor."""
    def _grab(sct, mon):
        if mon is None:
            return full_frame.copy()
        l = max(0, mon.get("left", 0))
        t = max(0, mon.get("top", 0))
        w = mon.get("width", full_frame.shape[1] - l)
        h = mon.get("height", full_frame.shape[0] - t)
        crop = full_frame[t:t+h, l:l+w]
        return crop.copy() if crop.size > 0 else None
    return _grab


class TestRallyCases(unittest.TestCase):

    def setUp(self):
        rally.reset_rally_state()
        self.gw_w = 720
        self.gw_h = 1280
        self.vp = (0, 0, self.gw_w, self.gw_h)
        self.mock_adb = MockADB(screen_size=(self.gw_w, self.gw_h))
        self.stop_event = threading.Event()
        self.sleep_patcher = patch("modules.rally._sleep", return_value=False)
        self.sleep_patcher.start()

    def tearDown(self):
        self.sleep_patcher.stop()

    def _create_blank_frame(self, bg_bgr=(50, 150, 200)):
        """Mặc định nền vàng cát sa mạc (Mapview)."""
        frame = np.zeros((self.gw_h, self.gw_w, 3), dtype=np.uint8)
        frame[:] = bg_bgr
        return frame

    def _draw_popup_card(self, frame):
        """Vẽ thẻ popup màu tím nhạt/lavender che nửa dưới màn hình (Y: 0.52 -> 0.98)."""
        py1, py2 = int(self.gw_h * 0.52), int(self.gw_h * 0.98)
        frame[py1:py2, :] = (225, 215, 230)
        # Tiêu đề slate đen ở Y: 0.52 -> 0.58
        ty1, ty2 = int(self.gw_h * 0.53), int(self.gw_h * 0.57)
        tx1, tx2 = int(self.gw_w * 0.05), int(self.gw_w * 0.40)
        frame[ty1:ty2, tx1:tx2] = (50, 40, 45)

    def _draw_purple_back_btn(self, frame):
        """Vẽ nút Back tím ở góc dưới trái (Rel X: ~0.08, Rel Y: ~0.935)."""
        y1, y2 = int(self.gw_h * 0.90), int(self.gw_h * 0.96)
        x1, x2 = int(self.gw_w * 0.05), int(self.gw_w * 0.15)
        # Nền tím (HSV: H=135, S=200, V=140)
        frame[y1:y2, x1:x2] = (140, 20, 140)
        # Mũi tên trắng bên trong
        frame[y1+8:y2-8, x1+10:x2-10] = (255, 255, 255)

    # -------------------------------------------------------------
    # CASE 1: Modal Alert ("Không thể tấn công ô mục tiêu")
    # -------------------------------------------------------------
    def test_case_01_modal_alert_confirm(self):
        """Hộp thoại Alert: Header tím/sáng + Nút Xác Nhận xanh ở giữa -> Bấm nút & set cooldown 30s."""
        frame = self._create_blank_frame(bg_bgr=(30, 30, 30))
        hy1, hy2 = int(self.gw_h * 0.30), int(self.gw_h * 0.42)
        hx1, hx2 = int(self.gw_w * 0.10), int(self.gw_w * 0.90)
        frame[hy1:hy2, hx1:hx2] = (160, 40, 140)

        by1, by2 = int(self.gw_h * 0.40), int(self.gw_h * 0.58)
        bx1, bx2 = int(self.gw_w * 0.15), int(self.gw_w * 0.85)
        frame[by1:by2, bx1:bx2] = (220, 220, 220)

        ny1, ny2 = int(self.gw_h * 0.60), int(self.gw_h * 0.67)
        nx1, nx2 = int(self.gw_w * 0.35), int(self.gw_w * 0.65)
        frame[ny1:ny2, nx1:nx2] = (30, 200, 30)

        rally._last_clicked_tile = (250, 400)
        with patch("modules.rally.safe_grab", side_effect=make_mock_grab(frame)):
            is_pop, is_join = rally._handle_rally_detail_popup(
                None, self.vp, self.mock_adb, self.stop_event
            )

        self.assertTrue(is_pop)
        self.assertFalse(is_join)
        self.assertGreaterEqual(len(self.mock_adb.taps), 1)

        tap_x, tap_y = self.mock_adb.taps[0]
        self.assertTrue(nx1 <= tap_x <= nx2)
        self.assertTrue(ny1 <= tap_y <= ny2)
        self.assertTrue(rally._is_tile_in_dict((250, 400), rally._full_tiles_cooldown))

    # -------------------------------------------------------------
    # CASE 2: Type A Popup (Danh sách nhiều Rally)
    # -------------------------------------------------------------
    def test_case_02_type_a_multi_rally_list_with_swipe(self):
        """Danh sách nhiều Rally: bấm nút xanh nhịp 1, vuốt cuộn trang, bấm nhịp 2, bấm đóng trên đỉnh."""
        frame1 = self._create_blank_frame(bg_bgr=(20, 20, 20))
        frame1[int(self.gw_h * 0.15):int(self.gw_h * 0.22), int(self.gw_w * 0.03):int(self.gw_w * 0.40)] = (50, 50, 50)
        frame1[int(self.gw_h * 0.09):int(self.gw_h * 0.14), int(self.gw_w * 0.20):int(self.gw_w * 0.80)] = (40, 40, 40)

        btn_w, btn_h = 130, 35
        frame1[400:400+btn_h, 450:450+btn_w] = (30, 200, 30)
        frame1[550:550+btn_h, 450:450+btn_w] = (30, 200, 30)

        frame2 = frame1.copy()
        frame2[700:700+btn_h, 450:450+btn_w] = (30, 200, 30)

        frames = [frame1, frame2]
        rally._last_clicked_tile = (100, 200)

        def mock_grab_sequence(sct, mon):
            curr_frame = frames[0] if len(self.mock_adb.swipes) == 0 else frames[1]
            return make_mock_grab(curr_frame)(sct, mon)

        with patch("modules.rally.safe_grab", side_effect=mock_grab_sequence):
            is_pop, is_join = rally._handle_rally_detail_popup(
                None, self.vp, self.mock_adb, self.stop_event
            )

        self.assertTrue(is_pop)
        self.assertTrue(is_join)
        self.assertGreaterEqual(len(self.mock_adb.swipes), 1)
        self.assertGreaterEqual(len(self.mock_adb.taps), 4)

        last_tap = self.mock_adb.taps[-1]
        self.assertAlmostEqual(last_tap[0] / self.gw_w, 0.50, delta=0.05)
        self.assertAlmostEqual(last_tap[1] / self.gw_h, 0.12, delta=0.05)
        self.assertTrue(rally._is_tile_in_dict((100, 200), rally._recently_joined_tiles))

    # -------------------------------------------------------------
    # CASE 3: Type B Single Rally - Nút xanh (Tham gia)
    # -------------------------------------------------------------
    def test_case_03_type_b_single_rally_green(self):
        """Single Rally nút xanh: Bấm tham gia lẻ -> Sau đó bấm nút Back tím về Map."""
        frame = self._create_blank_frame()
        self._draw_popup_card(frame)
        self._draw_purple_back_btn(frame)

        frame[int(self.gw_h * 0.90):int(self.gw_h * 0.96), int(self.gw_w * 0.60):int(self.gw_w * 0.85)] = (30, 200, 30)

        rally._last_clicked_tile = (300, 500)
        with patch("modules.rally.safe_grab", side_effect=make_mock_grab(frame)):
            is_pop, is_join = rally._handle_rally_detail_popup(
                None, self.vp, self.mock_adb, self.stop_event
            )

        self.assertTrue(is_pop)
        self.assertTrue(is_join)
        self.assertEqual(len(self.mock_adb.taps), 2)

        tap1 = self.mock_adb.taps[0]
        self.assertAlmostEqual(tap1[0] / self.gw_w, 0.72, delta=0.08)
        self.assertAlmostEqual(tap1[1] / self.gw_h, 0.93, delta=0.08)

        tap2 = self.mock_adb.taps[1]
        self.assertAlmostEqual(tap2[0] / self.gw_w, config.RALLY_POPUP_BACK_X, delta=0.05)
        self.assertAlmostEqual(tap2[1] / self.gw_h, config.RALLY_POPUP_BACK_Y, delta=0.05)

        self.assertTrue(rally._is_tile_in_dict((300, 500), rally._recently_joined_tiles))

    # -------------------------------------------------------------
    # CASE 4: Type B Single Rally - Nút xám "Chờ chấp thuận" / "Đã đầy"
    # -------------------------------------------------------------
    def test_case_04_type_b_single_rally_grey_waiting_approval(self):
        """CRITICAL: Nút xám 'Chờ chấp thuận' / 'Đã đầy' -> Bấm Back tím về Map, KHÔNG bấm nút xám, cooldown 30s."""
        frame = self._create_blank_frame()
        self._draw_popup_card(frame)
        self._draw_purple_back_btn(frame)

        frame[int(self.gw_h * 0.90):int(self.gw_h * 0.96), int(self.gw_w * 0.60):int(self.gw_w * 0.85)] = (130, 130, 130)

        rally._last_clicked_tile = (400, 600)
        with patch("modules.rally.safe_grab", side_effect=make_mock_grab(frame)):
            is_pop, is_join = rally._handle_rally_detail_popup(
                None, self.vp, self.mock_adb, self.stop_event
            )

        self.assertTrue(is_pop)
        self.assertFalse(is_join)
        self.assertEqual(len(self.mock_adb.taps), 1)

        tap = self.mock_adb.taps[0]
        self.assertAlmostEqual(tap[0] / self.gw_w, config.RALLY_POPUP_BACK_X, delta=0.05)
        self.assertAlmostEqual(tap[1] / self.gw_h, config.RALLY_POPUP_BACK_Y, delta=0.05)
        self.assertTrue(rally._is_tile_in_dict((400, 600), rally._full_tiles_cooldown))

    # -------------------------------------------------------------
    # CASE 5: Type B Single Rally - Nút vàng (Tấn công ô đất thường)
    # -------------------------------------------------------------
    def test_case_05_type_b_yellow_button_attack_tile(self):
        """Nút vàng tấn công đất -> Bấm Back tím, cooldown 30s."""
        frame = self._create_blank_frame()
        self._draw_popup_card(frame)
        self._draw_purple_back_btn(frame)

        frame[int(self.gw_h * 0.90):int(self.gw_h * 0.96), int(self.gw_w * 0.60):int(self.gw_w * 0.85)] = (0, 200, 220)

        rally._last_clicked_tile = (123, 456)
        with patch("modules.rally.safe_grab", side_effect=make_mock_grab(frame)):
            is_pop, is_join = rally._handle_rally_detail_popup(
                None, self.vp, self.mock_adb, self.stop_event
            )

        self.assertTrue(is_pop)
        self.assertFalse(is_join)
        self.assertEqual(len(self.mock_adb.taps), 1)
        self.assertAlmostEqual(self.mock_adb.taps[0][0] / self.gw_w, config.RALLY_POPUP_BACK_X, delta=0.05)
        self.assertTrue(rally._is_tile_in_dict((123, 456), rally._full_tiles_cooldown))

    # -------------------------------------------------------------
    # CASE 6: Type B "Ảo Ảnh" / Bảng xếp hạng cứ điểm (Không có nút hành động)
    # -------------------------------------------------------------
    def test_case_06_type_b_ao_anh_ranking_board(self):
        """Bảng xếp hạng / Ảo ảnh cứ điểm: có nút Back nhưng không có nút hành động -> Bấm Back về Map."""
        frame = self._create_blank_frame()
        self._draw_popup_card(frame)
        self._draw_purple_back_btn(frame)

        rally._last_clicked_tile = (555, 666)
        with patch("modules.rally.safe_grab", side_effect=make_mock_grab(frame)):
            is_pop, is_join = rally._handle_rally_detail_popup(
                None, self.vp, self.mock_adb, self.stop_event
            )

        self.assertTrue(is_pop)
        self.assertFalse(is_join)
        self.assertEqual(len(self.mock_adb.taps), 1)
        self.assertAlmostEqual(self.mock_adb.taps[0][0] / self.gw_w, config.RALLY_POPUP_BACK_X, delta=0.05)
        self.assertTrue(rally._is_tile_in_dict((555, 666), rally._full_tiles_cooldown))

    # -------------------------------------------------------------
    # CASE 7: Type D Popup (Bảng ô đất / mỏ tài nguyên có nút [X] ở đáy giữa)
    # -------------------------------------------------------------
    def test_case_07_type_d_territory_sheet(self):
        """Bảng ô đất / mỏ tài nguyên: Có thẻ popup mở + nút [X] ở đáy giữa -> Bấm nút [X], cooldown 30s."""
        frame = self._create_blank_frame()
        self._draw_popup_card(frame)
        # KHÔNG vẽ nút Back tím để phân biệt với Type B

        # Nút [X] màu trắng ở đáy giữa (Y: 0.925 -> 0.980, X: 0.44 -> 0.56)
        frame[int(self.gw_h * 0.94):int(self.gw_h * 0.97), int(self.gw_w * 0.48):int(self.gw_w * 0.52)] = (255, 255, 255)

        rally._last_clicked_tile = (777, 888)
        with patch("modules.rally.safe_grab", side_effect=make_mock_grab(frame)):
            is_pop, is_join = rally._handle_rally_detail_popup(
                None, self.vp, self.mock_adb, self.stop_event
            )

        self.assertTrue(is_pop)
        self.assertFalse(is_join)
        self.assertEqual(len(self.mock_adb.taps), 1)
        tap = self.mock_adb.taps[0]
        self.assertAlmostEqual(tap[0] / self.gw_w, 0.50, delta=0.05)
        self.assertAlmostEqual(tap[1] / self.gw_h, 0.955, delta=0.05)
        self.assertTrue(rally._is_tile_in_dict((777, 888), rally._full_tiles_cooldown))

    # -------------------------------------------------------------
    # CASE 8: Miss-Click Self-Escape (Bấm ô không mở popup)
    # -------------------------------------------------------------
    def test_case_08_miss_click_self_escape_and_overview(self):
        """Khi bấm vào avatar mà không có popup nào mở: Tự bấm vùng trống (50%, 20%) & gọi kính lúp & cooldown 20s."""
        timer_tpl = assets.get_rally_timer_template()
        th, tw = timer_tpl.shape[:2]

        map_frame = self._create_blank_frame(bg_bgr=(50, 50, 50))
        target_y = int(self.gw_h * 0.35)
        target_x = int(self.gw_w * 0.45)
        map_frame[target_y:target_y+th, target_x:target_x+tw] = timer_tpl

        blank_popup = self._create_blank_frame(bg_bgr=(100, 100, 100))

        call_count = [0]
        def mock_grab_for_scan(sct, mon):
            call_count[0] += 1
            if call_count[0] == 1:
                return make_mock_grab(map_frame)(sct, mon)
            return make_mock_grab(blank_popup)(sct, mon)

        with patch("modules.rally.safe_grab", side_effect=mock_grab_for_scan):
            with patch("modules.rally.ensure_map_overview") as mock_ensure_overview:
                result = rally.scan_and_join_map_rallies(
                    None, self.vp, self.mock_adb, self.stop_event
                )

        self.assertEqual(result, "CLICKED")
        self.assertGreaterEqual(len(self.mock_adb.taps), 2)

        tap_avatar = self.mock_adb.taps[0]
        self.assertTrue(tap_avatar[1] < target_y + th // 2)

        tap_escape = self.mock_adb.taps[1]
        self.assertAlmostEqual(tap_escape[0] / self.gw_w, 0.50, delta=0.05)
        self.assertAlmostEqual(tap_escape[1] / self.gw_h, 0.20, delta=0.05)

        mock_ensure_overview.assert_called_once()

    # -------------------------------------------------------------
    # CASE 9: Peak-Finding NMS (Chống trùng lặp điểm match)
    # -------------------------------------------------------------
    def test_case_09_peak_finding_nms(self):
        """Khi có nhiều điểm match lân cận trong bán kính 35px, NMS chỉ giữ lại 1 điểm có score cao nhất."""
        timer_tpl = assets.get_rally_timer_template()
        th, tw = timer_tpl.shape[:2]

        map_frame = self._create_blank_frame(bg_bgr=(40, 40, 40))
        map_frame[400:400+th, 300:300+tw] = timer_tpl
        map_frame[415:415+th, 315:315+tw] = cv2.addWeighted(timer_tpl, 0.5, np.zeros_like(timer_tpl), 0.5, 0)

        with patch("modules.rally.safe_grab", side_effect=make_mock_grab(map_frame)):
            with patch("modules.rally._handle_rally_detail_popup", return_value=(True, True)):
                result = rally.scan_and_join_map_rallies(
                    None, self.vp, self.mock_adb, self.stop_event
                )

        self.assertEqual(result, "JOINED")
        self.assertEqual(len(self.mock_adb.taps), 1)

    # -------------------------------------------------------------
    # CASE 10: Claim Reward & Anti-loop Failsafe
    # -------------------------------------------------------------
    def test_case_10_claim_reward_and_failsafe(self):
        """Nhận thưởng: bấm nút xanh lá nhận quà; ngắt Failsafe sau 2 lần liên tiếp."""
        frame = self._create_blank_frame()
        ry1 = int(self.gw_h * config.RALLY_REWARD_BTN_REL_Y_MIN)
        ry2 = int(self.gw_h * config.RALLY_REWARD_BTN_REL_Y_MAX)
        rx1 = int(self.gw_w * config.RALLY_REWARD_BTN_REL_X_MIN)
        rx2 = int(self.gw_w * config.RALLY_REWARD_BTN_REL_X_MAX)
        frame[ry1:ry2, rx1:rx2] = (30, 200, 30)

        with patch("modules.rally.safe_grab", side_effect=make_mock_grab(frame)):
            claimed_1 = rally._check_and_claim_reward(None, self.vp, self.mock_adb, self.stop_event)
            self.assertTrue(claimed_1)
            self.assertEqual(rally._consecutive_reward_claims, 1)

            claimed_2 = rally._check_and_claim_reward(None, self.vp, self.mock_adb, self.stop_event)
            self.assertTrue(claimed_2)
            self.assertEqual(rally._consecutive_reward_claims, 2)

            claimed_3 = rally._check_and_claim_reward(None, self.vp, self.mock_adb, self.stop_event)
            self.assertFalse(claimed_3)
            self.assertEqual(rally._consecutive_reward_claims, 0)

    # -------------------------------------------------------------
    # CASE 11: Pillarbox Detection (Viền đen 2 bên màn hình)
    # -------------------------------------------------------------
    def test_case_11_pillarbox_detection(self):
        """Tự động phát hiện viền đen trái và phải của giả lập mobile trên PC."""
        sample = np.zeros((400, 1000, 3), dtype=np.uint8)
        sample[:, 151:851] = (150, 150, 150)

        left_bound, real_w = rally._detect_pillarbox(sample)
        self.assertAlmostEqual(left_bound, 151, delta=2)
        self.assertAlmostEqual(real_w, 700, delta=4)

    # -------------------------------------------------------------
    # CASE 12: Ensure Map Overview (Kính lúp dấu trừ)
    # -------------------------------------------------------------
    def test_case_12_ensure_map_overview(self):
        """Khôi phục toàn cảnh bản đồ bằng template icon kính lúp."""
        zoom_tpl = assets.get_zoom_btn_template()
        if zoom_tpl is not None:
            zh, zw = zoom_tpl.shape[:2]
            frame = self._create_blank_frame()
            zy = int(self.gw_h * 0.75)
            zx = int(self.gw_w * 0.08)
            frame[zy:zy+zh, zx:zx+zw] = zoom_tpl

            with patch("modules.rally.safe_grab", side_effect=make_mock_grab(frame)):
                restored = rally.ensure_map_overview(None, self.vp, self.mock_adb, self.stop_event)

            self.assertTrue(restored)
            self.assertGreaterEqual(len(self.mock_adb.taps), 1)
            tap = self.mock_adb.taps[0]
            self.assertAlmostEqual(tap[0] / self.gw_w, 0.08, delta=0.08)
            self.assertAlmostEqual(tap[1] / self.gw_h, 0.77, delta=0.08)

    # -------------------------------------------------------------
    # CASE 13: User Uploaded 6 Real Screens Verification
    # -------------------------------------------------------------
    def test_case_13_user_real_screens_classification(self):
        """Kiểm thử trực tiếp trên 6 ảnh chụp thực tế do người dùng cung cấp."""
        user_files = sorted(glob.glob(r"C:\Users\ADMIN\.gemini\antigravity\brain\93b2c7c8-abdd-44b8-bc5f-e53ca99e9bbe\.user_uploaded\*.jpg"))
        if len(user_files) < 6:
            self.skipTest("Chưa có đủ 6 ảnh user upload để test")

        # Hình 1: Mapview -> Tuyệt đối không nhận diện là popup, KHÔNG bấm nút [X] ở đáy!
        img1 = cv2.imread(user_files[0])
        h1, w1 = img1.shape[:2]
        self.mock_adb.clear()
        with patch("modules.rally.safe_grab", return_value=img1):
            is_pop, is_join = rally._handle_rally_detail_popup(None, (0, 0, w1, h1), self.mock_adb, self.stop_event)
        self.assertFalse(is_pop, "Hình 1 (Mapview) tuyệt đối KHÔNG được nhận là popup")
        self.assertEqual(len(self.mock_adb.taps), 0, "Hình 1 (Mapview) tuyệt đối KHÔNG được bấm nút [X] ở đáy!")

        # Hình 2: Lane có thể tấn công (có nút Back tím + Tổng Tấn Công + Tấn Công) -> Bấm Back
        img2 = cv2.imread(user_files[1])
        h2, w2 = img2.shape[:2]
        self.mock_adb.clear()
        with patch("modules.rally.safe_grab", return_value=img2):
            is_pop, is_join = rally._handle_rally_detail_popup(None, (0, 0, w2, h2), self.mock_adb, self.stop_event)
        self.assertTrue(is_pop)
        self.assertFalse(is_join)
        self.assertEqual(len(self.mock_adb.taps), 1)
        self.assertAlmostEqual(self.mock_adb.taps[0][0] / self.mock_adb.screen_size[0], config.RALLY_POPUP_BACK_X, delta=0.08)

        # Hình 3: Đất đồng minh (có nút [X] ở đáy giữa, KHÔNG có nút Back) -> Bấm nút [X]
        img3 = cv2.imread(user_files[2])
        h3, w3 = img3.shape[:2]
        self.mock_adb.clear()
        with patch("modules.rally.safe_grab", return_value=img3):
            is_pop, is_join = rally._handle_rally_detail_popup(None, (0, 0, w3, h3), self.mock_adb, self.stop_event)
        self.assertTrue(is_pop)
        self.assertFalse(is_join)
        self.assertEqual(len(self.mock_adb.taps), 1)
        self.assertAlmostEqual(self.mock_adb.taps[0][0] / self.mock_adb.screen_size[0], 0.50, delta=0.08)
        self.assertAlmostEqual(self.mock_adb.taps[0][1] / self.mock_adb.screen_size[1], 0.955, delta=0.08)

        # Hình 4: Ảo ảnh không có đường đánh (có nút Back tím) -> Bấm Back
        img4 = cv2.imread(user_files[3])
        h4, w4 = img4.shape[:2]
        self.mock_adb.clear()
        with patch("modules.rally.safe_grab", return_value=img4):
            is_pop, is_join = rally._handle_rally_detail_popup(None, (0, 0, w4, h4), self.mock_adb, self.stop_event)
        self.assertTrue(is_pop)
        self.assertFalse(is_join)
        self.assertEqual(len(self.mock_adb.taps), 1)
        self.assertAlmostEqual(self.mock_adb.taps[0][0] / self.mock_adb.screen_size[0], config.RALLY_POPUP_BACK_X, delta=0.08)

        # Hình 5: Lane địch không có đường đánh (có nút [X] ở đáy giữa, KHÔNG có nút Back) -> Bấm nút [X]
        img5 = cv2.imread(user_files[4])
        h5, w5 = img5.shape[:2]
        self.mock_adb.clear()
        with patch("modules.rally.safe_grab", return_value=img5):
            is_pop, is_join = rally._handle_rally_detail_popup(None, (0, 0, w5, h5), self.mock_adb, self.stop_event)
        self.assertTrue(is_pop)
        self.assertFalse(is_join)
        self.assertEqual(len(self.mock_adb.taps), 1)
        self.assertAlmostEqual(self.mock_adb.taps[0][0] / self.mock_adb.screen_size[0], 0.50, delta=0.08)
        self.assertAlmostEqual(self.mock_adb.taps[0][1] / self.mock_adb.screen_size[1], 0.955, delta=0.08)

        # Hình 6: Ảo ảnh có đường đánh (có nút Back tím) -> Bấm Back
        img6 = cv2.imread(user_files[5])
        h6, w6 = img6.shape[:2]
        self.mock_adb.clear()
        with patch("modules.rally.safe_grab", return_value=img6):
            is_pop, is_join = rally._handle_rally_detail_popup(None, (0, 0, w6, h6), self.mock_adb, self.stop_event)
        self.assertTrue(is_pop)
        self.assertFalse(is_join)
        self.assertEqual(len(self.mock_adb.taps), 1)
        self.assertAlmostEqual(self.mock_adb.taps[0][0] / self.mock_adb.screen_size[0], config.RALLY_POPUP_BACK_X, delta=0.08)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestRallyCases)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
