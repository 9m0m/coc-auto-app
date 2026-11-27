"""
Giao diện người dùng COC AutoMaster - Thiết kế tối giản, gọn nhẹ & dễ thao tác.
"""

import os
import time
import threading
from typing import Optional, Tuple

import customtkinter as ctk

try:
    import pywinstyles
except ImportError:
    pywinstyles = None

from core.viewport import setup_windows_environment, find_emulator_window, get_game_viewport, screen_to_android
from core.adb_manager import ADBManager
from modules.rally import run_rally_loop
from modules.fishing import run_fishing_loop
from modules.adventure import run_adventure_loop

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Bảng màu Slate đồng nhất (1 màu nhấn xanh dương, hạn chế màu chói)
BG_CANVAS = "#0b0f17"
BG_SURFACE = "#131924"
BG_INSET = "#090d14"
BORDER_SUBTLE = "#1e293b"
BTN_GHOST_BG = "#1b2434"
BTN_GHOST_HOVER = "#263348"
BTN_GHOST_BORDER = "#2d3b52"
ACCENT_BLUE = "#0284c7"
ACCENT_BLUE_HOVER = "#0369a1"
TEXT_PRIMARY = "#f1f5f9"
TEXT_MUTED = "#94a3b8"
TEXT_SUBTLE = "#64748b"


class HelpDialog(ctk.CTkToplevel):
    """Cửa sổ tóm tắt cách thiết lập ADB và phân biệt các chế độ chạy."""

    def __init__(self, parent):
        super().__init__(parent)
        self.withdraw()
        self.title("Hướng Dẫn Nhanh")
        self.resizable(False, False)
        self.configure(fg_color=BG_CANVAS)

        self._build_content()

        width, height = 440, 470
        try:
            x = max(0, parent.winfo_x() + (parent.winfo_width() - width) // 2)
            y = max(0, parent.winfo_y() + (parent.winfo_height() - height) // 2)
            self.geometry(f"{width}x{height}+{x}+{y}")
        except Exception:
            self.geometry(f"{width}x{height}")

        self.transient(parent)

        if pywinstyles is not None:
            try:
                pywinstyles.change_header_color(self, color=BG_CANVAS)
                pywinstyles.change_border_color(self, color=BORDER_SUBTLE)
            except Exception:
                pass

        self.after(15, self._show_smooth)

    def _show_smooth(self):
        try:
            self.deiconify()
            self.grab_set()
            self.focus_force()
        except Exception:
            pass

    def _add_section(self, title: str, body: str) -> None:
        card = ctk.CTkFrame(self, fg_color=BG_SURFACE, border_width=1, border_color=BORDER_SUBTLE, corner_radius=10)
        card.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(
            card,
            text=title,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#38bdf8",
        ).pack(anchor="w", padx=12, pady=(8, 2))
        ctk.CTkLabel(
            card,
            text=body,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=TEXT_MUTED,
            justify="left",
        ).pack(anchor="w", padx=12, pady=(0, 8))

    def _build_content(self):
        ctk.CTkLabel(
            self,
            text="HƯỚNG DẪN SỬ DỤNG",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).pack(pady=(12, 6))

        self._add_section(
            "1. Bật ADB & Khổ màn hình",
            "• BlueStacks 5: Cài đặt -> Nâng cao -> Bật Cầu gỡ lỗi Android (ADB)\n"
            "• LDPlayer: Chọn 'Mở kết nối từ xa' + Bật Root rồi khởi động lại\n"
            "• Khổ dọc khuyến nghị: 900x1600 hoặc 720x1280 (Phone mode)",
        )
        self._add_section(
            "2. Hiển thị (MSS) vs Chạy ngầm (ADB)",
            "• Hiển thị (MSS) & Câu Cá: Không minimize và không để cửa sổ khác\n"
            "  (kể cả app Auto) che vùng game.\n"
            "• Rally / Phiêu Lưu: Chọn 'Chạy ngầm (ADB)' để che hoặc thu nhỏ\n"
            "  (tắt Eco Mode của BlueStacks để game không bị dừng hình).",
        )
        self._add_section(
            "3. Chế độ & Phím tắt",
            "• Auto Rally: Map Thường (zoom toàn cảnh) hoặc Sa Hải Dune (Chat)\n"
            "• Auto Câu Cá: Mở sẵn hồ câu · Hỗ trợ Chiếm chuột (0.02s) / Click ảo\n"
            "• Auto Phiêu Lưu: Mở sẵn Mê Cung · Phím F8: Bật/Tắt nhanh · Discord: 9m0m",
        )

        ctk.CTkButton(
            self,
            text="Đóng",
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color=ACCENT_BLUE,
            hover_color=ACCENT_BLUE_HOVER,
            corner_radius=8,
            text_color="#ffffff",
            command=self.destroy,
        ).pack(fill="x", padx=16, pady=(8, 12))


class AutoApp(ctk.CTk):
    """Cửa sổ điều khiển chính của COC AutoMaster."""

    def __init__(self):
        super().__init__()

        self.title("COC AutoMaster")
        self.geometry("470x650")
        self.minsize(430, 560)
        self.resizable(True, True)
        self.configure(fg_color=BG_CANVAS)

        if pywinstyles is not None:
            try:
                self.update()
                pywinstyles.change_header_color(self, color=BG_CANVAS)
                pywinstyles.change_border_color(self, color=BORDER_SUBTLE)
            except Exception:
                pass

        self.adb = ADBManager()
        self.emulator_win = None
        self.game_vp: Optional[Tuple[int, int, int, int]] = None

        self.worker_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.is_running = False
        self.selected_mode = "rally"
        self.rally_mode = "map"
        self.capture_mode = "mss"
        self.fishing_click_mode = "mouse"
        self._log_lock = threading.Lock()
        self._log_dir, self._log_file_path = self._init_log_file()

        self._build_header()
        self._build_device_card()
        self._build_control_card()
        self._build_action_button()
        self._build_log_card()

        self._last_toggle_time: float = 0.0
        self._setup_global_hotkey()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self._refresh_option_rows()
        self.after(300, self.refresh_connection)

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(12, 6))

        ctk.CTkLabel(
            header,
            text="Bảng Điều Khiển",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).pack(side="left")

        ctk.CTkButton(
            header,
            text="?",
            width=26,
            height=26,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color=BTN_GHOST_BG,
            hover_color=BTN_GHOST_HOVER,
            border_width=1,
            border_color=BTN_GHOST_BORDER,
            corner_radius=8,
            text_color=TEXT_MUTED,
            command=self.open_help_dialog,
        ).pack(side="right")

    def open_help_dialog(self) -> None:
        if hasattr(self, "_help_dlg") and self._help_dlg is not None and self._help_dlg.winfo_exists():
            self._help_dlg.focus_force()
            return
        self._help_dlg = HelpDialog(self)

    def _setup_global_hotkey(self) -> None:
        try:
            import keyboard
            keyboard.add_hotkey("F8", lambda: self.after(0, self.toggle_auto))
        except Exception:
            self.bind("<F8>", lambda e: self.toggle_auto())

    def toggle_auto(self) -> None:
        now = time.time()
        if now - getattr(self, "_last_toggle_time", 0.0) < 0.5:
            return
        self._last_toggle_time = now
        if self.is_running:
            self.stop_auto()
        else:
            self.start_auto()

    def _build_device_card(self) -> None:
        card = ctk.CTkFrame(
            self,
            corner_radius=10,
            fg_color=BG_SURFACE,
            border_width=1,
            border_color=BORDER_SUBTLE,
        )
        card.pack(fill="x", padx=18, pady=(0, 8))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=10)

        # Thông tin giả lập bên trái
        info_col = ctk.CTkFrame(row, fg_color="transparent")
        info_col.pack(side="left", fill="x", expand=True)

        title_line = ctk.CTkFrame(info_col, fg_color="transparent")
        title_line.pack(fill="x")

        self.lbl_status_dot = ctk.CTkLabel(
            title_line,
            text="●",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#f59e0b",
        )
        self.lbl_status_dot.pack(side="left", padx=(0, 6))

        self.lbl_emulator_name = ctk.CTkLabel(
            title_line,
            text="Đang tìm giả lập...",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        self.lbl_emulator_name.pack(side="left", fill="x", expand=True)

        self.lbl_details = ctk.CTkLabel(
            info_col,
            text="Đang quét cổng ADB...",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=TEXT_MUTED,
            anchor="w",
        )
        self.lbl_details.pack(fill="x", pady=(1, 0))

        # Nút thao tác gọn bên phải
        btn_col = ctk.CTkFrame(row, fg_color="transparent")
        btn_col.pack(side="right", padx=(8, 0))

        self.btn_rescan = ctk.CTkButton(
            btn_col,
            text="Quét lại",
            width=66,
            height=28,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=BTN_GHOST_BG,
            hover_color=BTN_GHOST_HOVER,
            border_width=1,
            border_color=BTN_GHOST_BORDER,
            corner_radius=7,
            text_color=TEXT_PRIMARY,
            command=self.refresh_connection,
        )
        self.btn_rescan.pack(side="left", padx=(0, 5))

        self.btn_test = ctk.CTkButton(
            btn_col,
            text="Test click",
            width=72,
            height=28,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=BTN_GHOST_BG,
            hover_color=BTN_GHOST_HOVER,
            border_width=1,
            border_color=BTN_GHOST_BORDER,
            corner_radius=7,
            text_color=TEXT_MUTED,
            command=self.test_single_click,
        )
        self.btn_test.pack(side="left")

    def _make_segmented_row(self, parent, label_text: str, left_text: str, right_text: str, on_left, on_right):
        """Tạo một hàng tùy chọn 2 cột gọn gàng: Nhãn bên trái + 2 nút chuyển bên phải."""
        row = ctk.CTkFrame(parent, fg_color="transparent")

        ctk.CTkLabel(
            row,
            text=label_text,
            width=64,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=TEXT_SUBTLE,
            anchor="w",
        ).pack(side="left")

        pill = ctk.CTkFrame(
            row,
            corner_radius=7,
            fg_color=BG_INSET,
            border_width=1,
            border_color=BORDER_SUBTLE,
        )
        pill.pack(side="left", fill="x", expand=True)

        inner = ctk.CTkFrame(pill, fg_color="transparent")
        inner.pack(fill="x", padx=2, pady=2)

        btn_l = ctk.CTkButton(
            inner,
            text=left_text,
            height=26,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=ACCENT_BLUE,
            hover_color=ACCENT_BLUE_HOVER,
            corner_radius=5,
            text_color="#ffffff",
            command=on_left,
        )
        btn_l.pack(side="left", fill="x", expand=True, padx=(0, 2))

        btn_r = ctk.CTkButton(
            inner,
            text=right_text,
            height=26,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="transparent",
            hover_color="#182030",
            corner_radius=5,
            text_color=TEXT_MUTED,
            command=on_right,
        )
        btn_r.pack(side="left", fill="x", expand=True)

        return row, btn_l, btn_r

    def _build_control_card(self) -> None:
        """Gộp chọn chế độ và các tùy chọn phụ vào 1 card duy nhất gọn gàng."""
        self.card_control = ctk.CTkFrame(
            self,
            corner_radius=10,
            fg_color=BG_SURFACE,
            border_width=1,
            border_color=BORDER_SUBTLE,
        )
        self.card_control.pack(fill="x", padx=18, pady=(0, 8))

        # Thanh chọn chế độ chính
        mode_track = ctk.CTkFrame(
            self.card_control,
            corner_radius=8,
            fg_color=BG_INSET,
            border_width=1,
            border_color=BORDER_SUBTLE,
        )
        mode_track.pack(fill="x", padx=12, pady=(10, 8))

        mode_inner = ctk.CTkFrame(mode_track, fg_color="transparent")
        mode_inner.pack(fill="x", padx=3, pady=3)

        self.btn_mode_rally = ctk.CTkButton(
            mode_inner,
            text="Auto Rally",
            height=30,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color=ACCENT_BLUE,
            hover_color=ACCENT_BLUE_HOVER,
            corner_radius=6,
            text_color="#ffffff",
            command=lambda: self._select_mode("rally"),
        )
        self.btn_mode_rally.pack(side="left", fill="x", expand=True, padx=(0, 2))

        self.btn_mode_fishing = ctk.CTkButton(
            mode_inner,
            text="Câu Cá",
            height=30,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="transparent",
            hover_color="#182030",
            corner_radius=6,
            text_color=TEXT_MUTED,
            command=lambda: self._select_mode("fishing"),
        )
        self.btn_mode_fishing.pack(side="left", fill="x", expand=True, padx=(0, 2))

        self.btn_mode_adventure = ctk.CTkButton(
            mode_inner,
            text="Phiêu Lưu",
            height=30,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="transparent",
            hover_color="#182030",
            corner_radius=6,
            text_color=TEXT_MUTED,
            command=lambda: self._select_mode("adventure"),
        )
        self.btn_mode_adventure.pack(side="left", fill="x", expand=True)

        # Đường kẻ phân cách mảnh
        ctk.CTkFrame(self.card_control, height=1, fg_color=BORDER_SUBTLE).pack(fill="x", padx=12, pady=(0, 8))

        # Các hàng tùy chọn theo ngữ cảnh
        self.options_container = ctk.CTkFrame(self.card_control, fg_color="transparent")
        self.options_container.pack(fill="x", padx=12)

        self.row_rally_map, self.btn_rally_map, self.btn_rally_dune = self._make_segmented_row(
            self.options_container,
            "Bản đồ",
            "Map Thường",
            "Sa Hải Dune",
            lambda: self._set_rally_mode("map"),
            lambda: self._set_rally_mode("dune"),
        )
        self.row_capture, self.btn_cap_mss, self.btn_cap_adb = self._make_segmented_row(
            self.options_container,
            "Đọc ảnh",
            "Hiển thị (MSS)",
            "Chạy ngầm (ADB)",
            lambda: self._set_capture_mode("mss"),
            lambda: self._set_capture_mode("adb"),
        )
        self.row_fishing, self.btn_fish_mouse, self.btn_fish_adb = self._make_segmented_row(
            self.options_container,
            "Thao tác",
            "Chiếm chuột (0.02s)",
            "Click ảo (ADB)",
            lambda: self._set_fishing_click_mode("mouse"),
            lambda: self._set_fishing_click_mode("adb"),
        )

        # 1 dòng gợi ý ngắn gọn duy nhất
        self.lbl_mode_hint = ctk.CTkLabel(
            self.card_control,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=TEXT_SUBTLE,
            anchor="w",
            justify="left",
        )
        self.lbl_mode_hint.pack(fill="x", padx=12, pady=(4, 10))

    def _update_pair_style(self, btn_active, btn_inactive) -> None:
        btn_active.configure(fg_color=ACCENT_BLUE, hover_color=ACCENT_BLUE_HOVER, text_color="#ffffff")
        btn_inactive.configure(fg_color="transparent", hover_color="#182030", text_color=TEXT_MUTED)

    def _update_mode_hint(self) -> None:
        if self.selected_mode == "rally":
            map_txt = "Canh Chat Liên Minh" if self.rally_mode == "dune" else "Zoom toàn cảnh 4 phe"
            cap_txt = "Chạy ngầm ADB (che/thu nhỏ vẫn chạy, tắt Eco Mode)" if self.capture_mode == "adb" else "Hiển thị MSS (không che/thu nhỏ giả lập)"
            self.lbl_mode_hint.configure(text=f"{map_txt} · {cap_txt}")
        elif self.selected_mode == "fishing":
            click_txt = "Phản xạ 0.02s (tạm giữ chuột khi giật)" if self.fishing_click_mode == "mouse" else "ADB ngầm (trễ ~300ms)"
            self.lbl_mode_hint.configure(text=f"{click_txt} · Không che hoặc thu nhỏ giả lập")
        else:
            cap_txt = "Chạy ngầm ADB (che/thu nhỏ vẫn chạy, tắt Eco Mode)" if self.capture_mode == "adb" else "Hiển thị MSS (không che/thu nhỏ giả lập)"
            self.lbl_mode_hint.configure(text=f"Tự vượt ải & chống kẹt · {cap_txt}")

    def _refresh_option_rows(self) -> None:
        self.row_rally_map.pack_forget()
        self.row_capture.pack_forget()
        self.row_fishing.pack_forget()

        if self.selected_mode == "rally":
            self.row_rally_map.pack(fill="x", pady=(0, 6))
            self.row_capture.pack(fill="x", pady=(0, 4))
        elif self.selected_mode == "fishing":
            self.row_fishing.pack(fill="x", pady=(0, 4))
        elif self.selected_mode == "adventure":
            self.row_capture.pack(fill="x", pady=(0, 4))

        self._update_mode_hint()

    def _set_rally_mode(self, rmode: str) -> None:
        if self.is_running:
            return
        self.rally_mode = rmode
        if rmode == "map":
            self._update_pair_style(self.btn_rally_map, self.btn_rally_dune)
            self.log("Rally: Map Thường")
        else:
            self._update_pair_style(self.btn_rally_dune, self.btn_rally_map)
            self.log("Rally: Sa Hải Dune (Chat)")
        self._update_mode_hint()

    def _set_capture_mode(self, cmode: str) -> None:
        if self.is_running:
            return
        self.capture_mode = cmode
        if cmode == "mss":
            self._update_pair_style(self.btn_cap_mss, self.btn_cap_adb)
            self.log("Đọc ảnh: Hiển thị (MSS)")
        else:
            self._update_pair_style(self.btn_cap_adb, self.btn_cap_mss)
            self.log("Đọc ảnh: Chạy ngầm (ADB)")
        self._update_mode_hint()

    def _set_fishing_click_mode(self, mode: str) -> None:
        if self.is_running:
            return
        self.fishing_click_mode = mode
        if mode == "mouse":
            self._update_pair_style(self.btn_fish_mouse, self.btn_fish_adb)
            self.log("Câu cá: Chiếm chuột (0.02s)")
        else:
            self._update_pair_style(self.btn_fish_adb, self.btn_fish_mouse)
            self.log("Câu cá: Click ảo (ADB)")
        self._update_mode_hint()

    def _select_mode(self, mode: str) -> None:
        if self.is_running:
            return
        self.selected_mode = mode

        inactive_cfg = {"fg_color": "transparent", "hover_color": "#182030", "text_color": TEXT_MUTED}
        active_cfg = {"fg_color": ACCENT_BLUE, "hover_color": ACCENT_BLUE_HOVER, "text_color": "#ffffff"}
        self.btn_mode_rally.configure(**inactive_cfg)
        self.btn_mode_fishing.configure(**inactive_cfg)
        self.btn_mode_adventure.configure(**inactive_cfg)

        if mode == "rally":
            self.btn_mode_rally.configure(**active_cfg)
            self.log("Chế độ: Auto Rally")
        elif mode == "fishing":
            self.btn_mode_fishing.configure(**active_cfg)
            self.log("Chế độ: Auto Câu Cá")
        elif mode == "adventure":
            self.btn_mode_adventure.configure(**active_cfg)
            self.log("Chế độ: Auto Phiêu Lưu")

        self._refresh_option_rows()

    def _build_action_button(self) -> None:
        """1 nút điều khiển chính duy nhất (Bắt đầu / Dừng), đồng bộ với phím F8."""
        self.btn_toggle = ctk.CTkButton(
            self,
            text="BẮT ĐẦU (F8)",
            height=42,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color="#059669",
            hover_color="#047857",
            corner_radius=10,
            text_color="#ffffff",
            command=self.toggle_auto,
        )
        self.btn_toggle.pack(fill="x", padx=18, pady=(0, 8))

    def _build_log_card(self) -> None:
        log_box = ctk.CTkFrame(
            self,
            corner_radius=10,
            fg_color=BG_SURFACE,
            border_width=1,
            border_color=BORDER_SUBTLE,
        )
        log_box.pack(fill="both", expand=True, padx=18, pady=(0, 14))

        log_top = ctk.CTkFrame(log_box, fg_color="transparent")
        log_top.pack(fill="x", padx=12, pady=(8, 4))

        ctk.CTkLabel(
            log_top,
            text="NHẬT KÝ",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=TEXT_SUBTLE,
        ).pack(side="left")

        ctk.CTkButton(
            log_top,
            text="Xóa",
            width=44,
            height=20,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=BTN_GHOST_BG,
            hover_color=BTN_GHOST_HOVER,
            border_width=1,
            border_color=BTN_GHOST_BORDER,
            corner_radius=5,
            text_color=TEXT_MUTED,
            command=self.clear_log,
        ).pack(side="right")

        ctk.CTkButton(
            log_top,
            text="File log",
            width=54,
            height=20,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=BTN_GHOST_BG,
            hover_color=BTN_GHOST_HOVER,
            border_width=1,
            border_color=BTN_GHOST_BORDER,
            corner_radius=5,
            text_color=TEXT_MUTED,
            command=self.open_log_folder,
        ).pack(side="right", padx=(0, 5))

        self.txt_log = ctk.CTkTextbox(
            log_box,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color=BG_INSET,
            text_color="#cbd5e1",
            corner_radius=7,
            wrap="word",
        )
        self.txt_log.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def _init_log_file(self) -> Tuple[str, str]:
        """Tạo thư mục lưu nhật ký theo ngày trong %LOCALAPPDATA%/COC_AutoMaster/logs."""
        base_dir = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        log_dir = os.path.join(base_dir, "COC_AutoMaster", "logs")
        try:
            os.makedirs(log_dir, exist_ok=True)
        except Exception:
            return "", ""
        log_path = os.path.join(log_dir, f"auto_{time.strftime('%Y-%m-%d')}.log")
        return log_dir, log_path

    def open_log_folder(self) -> None:
        if not self._log_dir or not os.path.isdir(self._log_dir):
            self.log("[Cảnh báo] Chưa tạo được thư mục file log.")
            return
        try:
            os.startfile(self._log_dir)  # type: ignore[attr-defined]
        except Exception as e:
            self.log(f"[Lỗi] Không mở được thư mục log: {e}")

    def _append_log(self, line: str) -> None:
        try:
            self.txt_log.insert("end", line)
            self.txt_log.see("end")
        except Exception:
            pass

    def log(self, msg: str) -> None:
        """Ghi log an toàn ra UI và file nhật ký theo ngày."""
        line = f"[{time.strftime('%H:%M:%S')}] {msg}\n"
        if self._log_file_path:
            try:
                with self._log_lock:
                    with open(self._log_file_path, "a", encoding="utf-8") as f:
                        f.write(line)
            except Exception:
                pass
        if threading.current_thread() is threading.main_thread():
            self._append_log(line)
        else:
            try:
                self.after(0, lambda text=line: self._append_log(text))
            except Exception:
                pass

    def clear_log(self) -> None:
        self.txt_log.delete("1.0", "end")

    def refresh_connection(self) -> None:
        """Quét cửa sổ game và kết nối cổng ADB trên luồng ngầm."""
        def _worker():
            self.log("Đang quét giả lập và kết nối ADB...")
            self.emulator_win = find_emulator_window()

            if not self.emulator_win:
                self.after(0, lambda: self._set_device_status("#ef4444", "Chưa tìm thấy giả lập", "Hãy mở BlueStacks / LDPlayer trước"))
                self.log("[Cảnh báo] Chưa tìm thấy cửa sổ giả lập trên màn hình.")
                return

            hwnd = self.emulator_win._hWnd
            title = self.emulator_win.title
            self.game_vp = get_game_viewport(hwnd, title)

            serial = self.adb.auto_connect(emulator_hint=title)
            if serial and self.adb.screen_size and self.adb.screen_size[0] > 0:
                sw, sh = self.adb.screen_size
                vw, vh = self.game_vp[2], self.game_vp[3]
                if (vw < vh and sw > sh) or (vw > vh and sw < sh):
                    sw, sh = sh, sw
                    self.adb.screen_size = (sw, sh)

                details = f"{serial} · {sw}x{sh} · VP {vw}x{vh}"
                self.after(0, lambda t=title, d=details: self._set_device_status("#10b981", t, d))
                self.log(f"Đã kết nối: {title} ({serial})")
            elif serial:
                self.after(0, lambda t=title: self._set_device_status("#f59e0b", f"{t} (Cần bật ADB)", "Bật Cầu gỡ lỗi Android (ADB) trong Cài đặt"))
                self.log("Cửa sổ sẵn sàng nhưng ADB chưa bật.")
            else:
                self.after(0, lambda t=title: self._set_device_status("#f59e0b", f"{t} (Đang dò cổng)", "Đang thử kết nối ADB..."))

        threading.Thread(target=_worker, daemon=True).start()

    def _set_device_status(self, dot_color: str, name: str, details: str) -> None:
        self.lbl_status_dot.configure(text_color=dot_color)
        self.lbl_emulator_name.configure(text=name)
        self.lbl_details.configure(text=details)

    def test_single_click(self) -> None:
        if not self.adb.active_serial or not self.game_vp or not self.adb.screen_size:
            self.log("[Lỗi] Chưa kết nối được ADB hoặc chưa tìm thấy khung game để test.")
            return

        def _worker():
            self.log("Chuẩn bị test click ngầm vào tâm màn hình sau 1s...")
            time.sleep(1)
            cx = self.game_vp[0] + self.game_vp[2] // 2
            cy = self.game_vp[1] + self.game_vp[3] // 2
            ax, ay = screen_to_android(cx, cy, self.game_vp, self.adb.screen_size)
            ok = self.adb.tap(ax, ay)
            if ok:
                self.log(f"[OK] Đã chạm ngầm tại Android ({ax}, {ay}) — không chiếm chuột.")
            else:
                err_detail = f" ({self.adb.last_error})" if self.adb.last_error else ""
                self.log(f"[Lỗi] Không gửi được lệnh chạm{err_detail}. Kiểm tra cài đặt ADB/Root.")

        threading.Thread(target=_worker, daemon=True).start()

    def get_current_viewport(self) -> Optional[Tuple[int, int, int, int]]:
        if not self.emulator_win:
            self.emulator_win = find_emulator_window()
        if self.emulator_win:
            self.game_vp = get_game_viewport(self.emulator_win._hWnd, self.emulator_win.title)
            return self.game_vp
        return None

    def _set_controls_state(self, state: str) -> None:
        for btn in (
            self.btn_rescan,
            self.btn_mode_rally,
            self.btn_mode_fishing,
            self.btn_mode_adventure,
            self.btn_rally_map,
            self.btn_rally_dune,
            self.btn_cap_mss,
            self.btn_cap_adb,
            self.btn_fish_mouse,
            self.btn_fish_adb,
        ):
            btn.configure(state=state)

    def start_auto(self) -> None:
        if self.is_running:
            return
        if not self.adb.active_serial:
            self.log("[Lỗi] Chưa kết nối được ADB. Bấm 'Quét lại' để thử.")
            return

        self.is_running = True
        self.stop_event.clear()
        self._set_controls_state("disabled")
        self.btn_toggle.configure(
            text="ĐANG CHẠY — DỪNG (F8)",
            fg_color="#dc2626",
            hover_color="#b91c1c",
        )

        mode = self.selected_mode
        rally_desc = "Sa Hải Dune" if self.rally_mode == "dune" else "Map Thường"
        mode_names = {
            "rally": f"Auto Rally ({rally_desc})",
            "fishing": "Auto Câu Cá",
            "adventure": "Auto Phiêu Lưu",
        }
        self.log(f"Bắt đầu: {mode_names.get(mode, mode)}")

        def _runner():
            try:
                if mode == "rally":
                    run_rally_loop(
                        self.adb,
                        self.get_current_viewport,
                        self.stop_event,
                        self.log,
                        rally_mode=self.rally_mode,
                        capture_mode=self.capture_mode,
                    )
                elif mode == "fishing":
                    run_fishing_loop(
                        self.adb,
                        self.get_current_viewport,
                        self.stop_event,
                        self.log,
                        click_mode=self.fishing_click_mode,
                    )
                elif mode == "adventure":
                    run_adventure_loop(
                        self.adb,
                        self.get_current_viewport,
                        self.stop_event,
                        self.log,
                        capture_mode=self.capture_mode,
                    )
            except Exception as e:
                self.log(f"[Lỗi tiến trình] {e}")
            finally:
                self.after(0, self._on_worker_finished)

        self.worker_thread = threading.Thread(target=_runner, daemon=True)
        self.worker_thread.start()

    def stop_auto(self) -> None:
        if not self.is_running:
            return
        self.log("Đang dừng tiến trình...")
        self.stop_event.set()

    def _on_worker_finished(self) -> None:
        self.is_running = False
        self._set_controls_state("normal")
        self.btn_toggle.configure(
            text="BẮT ĐẦU (F8)",
            fg_color="#059669",
            hover_color="#047857",
        )
        self.log("Đã dừng.")

    def on_closing(self) -> None:
        self.stop_event.set()
        try:
            import keyboard
            keyboard.remove_all_hotkeys()
        except Exception:
            pass
        try:
            self.adb.run_cmd(["kill-server"], timeout=1.0)
        except Exception:
            pass
        self.destroy()


def run() -> None:
    setup_windows_environment()
    app = AutoApp()
    app.mainloop()


if __name__ == "__main__":
    run()
