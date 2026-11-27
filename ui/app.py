"""
Giao diện người dùng COC AutoMaster - Chuẩn Modern Slate & Cyber Blue.
Gam màu công thái học chuyên nghiệp, tương phản sắc nét, loại bỏ chi tiết thừa.
Tích hợp cửa sổ Hướng dẫn & Lưu ý qua nút [?] góc trên, hỗ trợ liên hệ Discord: 9m0m.
"""

import sys
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

# Cấu hình giao diện chuẩn Dark Mode
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class HelpDialog(ctk.CTkToplevel):
    """Cửa sổ Hướng dẫn sử dụng, lưu ý thiết lập và thông tin liên hệ Discord."""

    def __init__(self, parent):
        super().__init__(parent)

        # 1. Ẩn cửa sổ ngay khi khởi tạo để loại bỏ 100% hiện tượng chớp trắng trên Windows
        self.withdraw()

        self.title("Hướng Dẫn Sử Dụng & Lưu Ý")
        self.resizable(False, False)
        self.configure(fg_color="#0c1017")

        # 2. Xây dựng toàn bộ nội dung Dark Mode trước khi hiện ra
        self._build_content()

        # 3. Tính toán vị trí căn giữa cửa sổ cha và đặt kích thước
        width, height = 480, 585
        try:
            x = max(0, parent.winfo_x() + (parent.winfo_width() - width) // 2)
            y = max(0, parent.winfo_y() + (parent.winfo_height() - height) // 2)
            self.geometry(f"{width}x{height}+{x}+{y}")
        except Exception:
            self.geometry(f"{width}x{height}")

        # 4. Cố định luôn ở trên cửa sổ chính
        self.transient(parent)

        # 5. Đồng bộ màu thanh tiêu đề Windows 11 với màu nền Dark Slate
        if pywinstyles is not None:
            try:
                pywinstyles.change_header_color(self, color="#0c1017")
                pywinstyles.change_border_color(self, color="#243044")
            except Exception:
                pass

        # 6. Đợi 15ms cho Windows áp dụng trọn vẹn màu tiêu đề rồi mới hiển thị mượt mà (Zero Flicker)
        self.after(15, self._show_smooth)

    def _show_smooth(self):
        try:
            self.deiconify()
            self.grab_set()
            self.focus_force()
        except Exception:
            pass

    def _build_content(self):
        # Tiêu đề Popup
        lbl_title = ctk.CTkLabel(
            self,
            text="HƯỚNG DẪN SỬ DỤNG & LƯU Ý",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color="#f8fafc",
        )
        lbl_title.pack(pady=(14, 8))

        # Khung 1: Thiết lập giả lập
        f1 = ctk.CTkFrame(self, fg_color="#151c28", border_width=1, border_color="#243044", corner_radius=10)
        f1.pack(fill="x", padx=18, pady=4)
        ctk.CTkLabel(
            f1,
            text="Cài Đặt Giả Lập & ADB",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#38bdf8",
        ).pack(anchor="w", padx=14, pady=(8, 3))
        txt1 = (
            "• BlueStacks 5: Cài đặt -> Nâng cao -> Bật Cầu gỡ lỗi Android (ADB)\n"
            "• LDPlayer / MuMu / Nox: Bật kết nối ADB (nếu đã bật sẵn thì giữ nguyên)\n"
            "• Game màn hình dọc: Khuyến nghị 900x1600 hoặc 720x1280 (Phone mode)\n"
            "  (Hỗ trợ tự động đồng bộ kể cả khi giả lập đang để chế độ Tablet ngang)"
        )
        ctk.CTkLabel(
            f1, text=txt1, font=ctk.CTkFont(family="Segoe UI", size=11), text_color="#94a3b8", justify="left"
        ).pack(anchor="w", padx=14, pady=(0, 8))

        # Khung 2: Lưu ý cửa sổ & đa màn hình
        f2 = ctk.CTkFrame(self, fg_color="#151c28", border_width=1, border_color="#243044", corner_radius=10)
        f2.pack(fill="x", padx=18, pady=4)
        ctk.CTkLabel(
            f2,
            text="Lưu Ý Quan Trọng (Tránh Lỗi Nhận Diện)",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#38bdf8",
        ).pack(anchor="w", padx=14, pady=(8, 3))
        txt2 = (
            "• Chế độ Hiển thị (MSS) & Auto Câu Cá: KHÔNG thu nhỏ (minimize) và\n"
            "  không để cửa sổ khác che mất vùng game vì tool đọc trực tiếp từ màn hình.\n"
            "• Rally / Phiêu Lưu: Có thể bật 'Chạy ngầm (ADB)' để che hoặc thu nhỏ\n"
            "  (nhớ tắt Eco Mode của BlueStacks để game không bị đóng băng khung hình)."
        )
        ctk.CTkLabel(
            f2, text=txt2, font=ctk.CTkFont(family="Segoe UI", size=11), text_color="#94a3b8", justify="left"
        ).pack(anchor="w", padx=14, pady=(0, 8))

        # Khung 3: Hướng dẫn 3 tính năng
        f3 = ctk.CTkFrame(self, fg_color="#151c28", border_width=1, border_color="#243044", corner_radius=10)
        f3.pack(fill="x", padx=18, pady=4)
        ctk.CTkLabel(
            f3,
            text="3 Chế Độ Hoạt Động",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#38bdf8",
        ).pack(anchor="w", padx=14, pady=(8, 3))
        txt3 = (
            "• Auto Rally: Mở sẵn Sa Hải Mê Thành. Tự động thu phóng (🔍-)\n"
            "  và canh 5 phút tổng tấn công đánh boss liên tục.\n"
            "• Auto Câu Cá: Mở sẵn hồ câu cá. Tự quăng cần và kéo cá rãnh vàng.\n"
            "• Auto Phiêu Lưu: Mở sẵn Mê Cung. Tự vượt ải và chống kẹt đuốc."
        )
        ctk.CTkLabel(
            f3, text=txt3, font=ctk.CTkFont(family="Segoe UI", size=11), text_color="#94a3b8", justify="left"
        ).pack(anchor="w", padx=14, pady=(0, 8))

        # Khung 4: Phím tắt & Liên hệ Discord
        f4 = ctk.CTkFrame(self, fg_color="#151c28", border_width=1, border_color="#243044", corner_radius=10)
        f4.pack(fill="x", padx=18, pady=4)
        ctk.CTkLabel(
            f4,
            text="Phím Tắt & Liên Hệ Hỗ Trợ",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#38bdf8",
        ).pack(anchor="w", padx=14, pady=(8, 3))
        txt4 = (
            "• Phím F8: Bật / Tắt Auto nhanh (Phím tắt toàn cục)\n"
            "• Hỗ trợ, góp ý & liên hệ: Discord: 9m0m"
        )
        ctk.CTkLabel(
            f4, text=txt4, font=ctk.CTkFont(family="Segoe UI", size=11), text_color="#94a3b8", justify="left"
        ).pack(anchor="w", padx=14, pady=(0, 8))

        # Nút Đóng
        btn_close = ctk.CTkButton(
            self,
            text="ĐÃ HIỂU",
            height=34,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#0284c7",
            hover_color="#0369a1",
            corner_radius=8,
            text_color="#ffffff",
            command=self.destroy,
        )
        btn_close.pack(fill="x", padx=18, pady=(10, 12))


class AutoApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Thiết lập cửa sổ chính
        self.title("COC AutoMaster")
        self.geometry("520x840")
        self.minsize(480, 720)
        self.resizable(True, True)
        
        # Gam màu nền Slate trung tính dịu mắt (#0c1017)
        self.configure(fg_color="#0c1017")

        # Đồng bộ màu thanh tiêu đề Windows 11 với cửa sổ ứng dụng
        if pywinstyles is not None:
            try:
                self.update()
                pywinstyles.change_header_color(self, color="#0c1017")
                pywinstyles.change_border_color(self, color="#243044")
            except Exception:
                pass

        # Quản lý hệ thống & tiến trình
        self.adb = ADBManager()
        self.emulator_win = None
        self.game_vp: Optional[Tuple[int, int, int, int]] = None

        self.worker_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.is_running = False
        self.selected_mode = "rally"
        self.rally_mode = "map"             # "map" (Gold Rush thường) hoặc "dune" (Sa Hải Dune - Chat)
        self.capture_mode = "mss"           # "mss" (siêu tốc, không che) hoặc "adb" (chạy ngầm cho Rally/Phiêu Lưu)
        self.fishing_click_mode = "mouse"  # "mouse" (Win32 siêu tốc 0.02s) hoặc "adb" (ADB ngầm)
        self.card_rally_options = None
        self.card_capture_options = None
        self.card_fishing_options = None

        # Khởi tạo các thành phần giao diện chuẩn Slate & Blue
        self._build_header()
        self._build_device_card()
        self._build_mode_selector()
        self._build_rally_options()
        self._build_capture_options()
        self._build_fishing_options()
        self._build_action_controls()
        self._build_terminal_log()

        # Phím tắt toàn cục F8 (Bật / Tắt thông minh)
        self._last_toggle_time: float = 0.0
        self._setup_global_hotkey()

        # Đăng ký đóng ứng dụng an toàn
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Tự động quét giả lập khi mở app
        self.after(300, self.refresh_connection)

    def _build_header(self):
        """Header gọn gàng: Bỏ bớt tên app trùng lặp, bỏ chữ HYBRID, thêm nút [?] trợ giúp."""
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(14, 6))

        # Tiêu đề thanh tác vụ nhỏ gọn, tinh tế
        title = ctk.CTkLabel(
            header,
            text="Bảng Điều Khiển",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color="#f8fafc",
        )
        title.pack(side="left")

        # Nút [?] mở cửa sổ Hướng Dẫn & Lưu Ý (Discord: 9m0m)
        self.btn_help = ctk.CTkButton(
            header,
            text="?",
            width=28,
            height=28,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color="#1f2838",
            hover_color="#2c3a50",
            border_width=1,
            border_color="#374763",
            corner_radius=14,
            text_color="#38bdf8",
            command=self.open_help_dialog,
        )
        self.btn_help.pack(side="right")

    def open_help_dialog(self):
        """Mở cửa sổ Hướng dẫn sử dụng (chống mở đè nhiều cửa sổ)."""
        if hasattr(self, "_help_dlg") and self._help_dlg is not None and self._help_dlg.winfo_exists():
            self._help_dlg.focus_force()
            return
        self._help_dlg = HelpDialog(self)

    def _setup_global_hotkey(self):
        """Đăng ký phím tắt toàn cục F8 qua thư viện keyboard. Fallback Tkinter bind nếu lỗi."""
        try:
            import keyboard
            keyboard.add_hotkey("F8", lambda: self.after(0, self.toggle_auto))
        except Exception:
            self.bind("<F8>", lambda e: self.toggle_auto())

    def toggle_auto(self):
        """Bật / Tắt trạng thái Auto nhanh bằng 1 phím thông minh F8 (có chống dội phím 0.5s)."""
        now = time.time()
        if now - getattr(self, "_last_toggle_time", 0.0) < 0.5:
            return
        self._last_toggle_time = now

        if self.is_running:
            self.stop_auto()
        else:
            self.start_auto()

    def _build_device_card(self):
        """Card thông tin giả lập với nền Slate dịu mắt và viền rõ ràng."""
        self.card_device = ctk.CTkFrame(
            self,
            corner_radius=14,
            fg_color="#151c28",
            border_width=1,
            border_color="#243044",
        )
        self.card_device.pack(fill="x", padx=24, pady=6)

        # Dòng 1: Đèn trạng thái & Tên giả lập
        status_row = ctk.CTkFrame(self.card_device, fg_color="transparent")
        status_row.pack(fill="x", padx=18, pady=(14, 4))

        self.lbl_status_dot = ctk.CTkLabel(
            status_row,
            text="●",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#f59e0b",
        )
        self.lbl_status_dot.pack(side="left", padx=(0, 8))

        self.lbl_emulator_name = ctk.CTkLabel(
            status_row,
            text="Đang tìm kiếm giả lập...",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color="#f8fafc",
        )
        self.lbl_emulator_name.pack(side="left")

        # Dòng 2: Thông số chi tiết (Cổng & Viewport)
        self.lbl_details = ctk.CTkLabel(
            self.card_device,
            text="Cổng: Đang dò • Màn hình: Đang đọc",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#94a3b8",
            anchor="w",
        )
        self.lbl_details.pack(fill="x", padx=18, pady=(0, 12))

        # Dòng 3: 2 Nút thao tác cân bằng 50/50
        action_row = ctk.CTkFrame(self.card_device, fg_color="transparent")
        action_row.pack(fill="x", padx=16, pady=(0, 16))

        self.btn_rescan = ctk.CTkButton(
            action_row,
            text="Quét Giả Lập",
            height=36,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#1f2838",
            hover_color="#2c3a50",
            border_width=1,
            border_color="#374763",
            corner_radius=9,
            text_color="#f8fafc",
            command=self.refresh_connection,
        )
        self.btn_rescan.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.btn_test = ctk.CTkButton(
            action_row,
            text="Thử Click Ngầm",
            height=36,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#0284c7",
            hover_color="#0369a1",
            border_width=1,
            border_color="#38bdf8",
            corner_radius=9,
            text_color="#ffffff",
            command=self.test_single_click,
        )
        self.btn_test.pack(side="right", fill="x", expand=True, padx=(6, 0))

    def _build_mode_selector(self):
        """Khung chọn chế độ chuẩn màu Cobalt Blue dịu mắt, cực kỳ dễ nhận biết."""
        self.card_mode = ctk.CTkFrame(
            self,
            corner_radius=14,
            fg_color="#151c28",
            border_width=1,
            border_color="#243044",
        )
        self.card_mode.pack(fill="x", padx=24, pady=6)

        # Tiêu đề Card
        lbl_card_title = ctk.CTkLabel(
            self.card_mode,
            text="CHẾ ĐỘ TỰ ĐỘNG",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#64748b",
            anchor="w",
        )
        lbl_card_title.pack(fill="x", padx=18, pady=(12, 8))

        # Khay chứa nút chọn chế độ (dạng Segmented Control chìm)
        capsule_box = ctk.CTkFrame(
            self.card_mode,
            corner_radius=10,
            fg_color="#090d15",
            border_width=1,
            border_color="#1e2738",
        )
        capsule_box.pack(fill="x", padx=14, pady=(0, 10))

        btn_inner_row = ctk.CTkFrame(capsule_box, fg_color="transparent")
        btn_inner_row.pack(fill="x", padx=4, pady=4)

        # Nút Auto Rally (Mặc định chọn: Nền xanh dương dịu mắt #0284c7, chữ trắng nổi bật)
        self.btn_mode_rally = ctk.CTkButton(
            btn_inner_row,
            text="Auto Rally",
            height=34,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#0284c7",
            hover_color="#0369a1",
            corner_radius=8,
            text_color="#ffffff",
            command=lambda: self._select_mode("rally"),
        )
        self.btn_mode_rally.pack(side="left", fill="x", expand=True, padx=2)

        self.btn_mode_fishing = ctk.CTkButton(
            btn_inner_row,
            text="Auto Câu Cá",
            height=34,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="transparent",
            hover_color="#182030",
            corner_radius=8,
            text_color="#94a3b8",
            command=lambda: self._select_mode("fishing"),
        )
        self.btn_mode_fishing.pack(side="left", fill="x", expand=True, padx=2)

        self.btn_mode_adventure = ctk.CTkButton(
            btn_inner_row,
            text="Auto Phiêu Lưu",
            height=34,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="transparent",
            hover_color="#182030",
            corner_radius=8,
            text_color="#94a3b8",
            command=lambda: self._select_mode("adventure"),
        )
        self.btn_mode_adventure.pack(side="left", fill="x", expand=True, padx=2)

        # Huy hiệu viên thuốc hiển thị chế độ đang chọn (ngắn gọn, xúc tích, vừa khít nội dung)
        self.lbl_mode_status = ctk.CTkLabel(
            self.card_mode,
            text="● Auto Rally (Map Thường)",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#0c1728",
            text_color="#38bdf8",
            corner_radius=8,
            padx=16,
            pady=5,
        )
        self.lbl_mode_status.pack(pady=(0, 14))

    def _build_rally_options(self):
        """Khung tùy chọn chế độ cho Auto Rally (Map Thường vs Sa Hải Dune Chat)."""
        self.card_rally_options = ctk.CTkFrame(
            self,
            corner_radius=12,
            fg_color="#151c28",
            border_width=1,
            border_color="#243044",
        )
        self.card_rally_options.pack(fill="x", padx=24, pady=4)

        capsule = ctk.CTkFrame(
            self.card_rally_options,
            corner_radius=8,
            fg_color="#090d15",
            border_width=1,
            border_color="#1e2738",
        )
        capsule.pack(fill="x", padx=12, pady=(8, 4))

        inner_row = ctk.CTkFrame(capsule, fg_color="transparent")
        inner_row.pack(fill="x", padx=3, pady=3)

        self.btn_rally_map = ctk.CTkButton(
            inner_row,
            text="Map Thường",
            height=28,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#0284c7",
            hover_color="#0369a1",
            corner_radius=6,
            text_color="#ffffff",
            command=lambda: self._set_rally_mode("map"),
        )
        self.btn_rally_map.pack(side="left", fill="x", expand=True, padx=2)

        self.btn_rally_dune = ctk.CTkButton(
            inner_row,
            text="Sa Hải Dune (Chat)",
            height=28,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="transparent",
            hover_color="#182030",
            corner_radius=6,
            text_color="#94a3b8",
            command=lambda: self._set_rally_mode("dune"),
        )
        self.btn_rally_dune.pack(side="left", fill="x", expand=True, padx=2)

        self.lbl_rally_note = ctk.CTkLabel(
            self.card_rally_options,
            text="🗺️ Gold Rush thường: Tự zoom toàn cảnh 4 phe và bấm Rally trực tiếp trên Map.",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#38bdf8",
            anchor="w",
            justify="left",
        )
        self.lbl_rally_note.pack(fill="x", padx=14, pady=(0, 6))

    def _set_rally_mode(self, rmode: str):
        """Chuyển đổi giữa Gold Rush Map Thường và Sa Hải Dune (Chat Liên Minh)."""
        if self.is_running:
            return
        self.rally_mode = rmode
        if rmode == "map":
            self.btn_rally_map.configure(fg_color="#0284c7", hover_color="#0369a1", text_color="#ffffff")
            self.btn_rally_dune.configure(fg_color="transparent", hover_color="#182030", text_color="#94a3b8")
            self.lbl_rally_note.configure(
                text="🗺️ Gold Rush thường: Tự zoom toàn cảnh 4 phe và bấm Rally trực tiếp trên Map.",
                text_color="#38bdf8",
            )
            self.lbl_mode_status.configure(text="● Auto Rally (Map Thường)")
            self.log("Chế độ Rally: Map Thường (Gold Rush toàn cảnh)")
        else:
            self.btn_rally_map.configure(fg_color="transparent", hover_color="#182030", text_color="#94a3b8")
            self.btn_rally_dune.configure(fg_color="#0284c7", hover_color="#0369a1", text_color="#ffffff")
            self.lbl_rally_note.configure(
                text="🏜️ Dune (Map lớn): Canh Chat Liên Minh, chống trôi tin & tự bấm Popup Rally.",
                text_color="#38bdf8",
            )
            self.lbl_mode_status.configure(text="● Auto Rally (Sa Hải Dune)")
            self.log("Chế độ Rally: Sa Hải Dune (Quét Chat Liên Minh)")

    def _build_capture_options(self):
        """Khung tùy chọn chế độ đọc màn hình (Hiển thị MSS vs Chạy ngầm ADB) cho Rally & Phiêu Lưu."""
        self.card_capture_options = ctk.CTkFrame(
            self,
            corner_radius=12,
            fg_color="#151c28",
            border_width=1,
            border_color="#243044",
        )
        self.card_capture_options.pack(fill="x", padx=24, pady=4)

        capsule = ctk.CTkFrame(
            self.card_capture_options,
            corner_radius=8,
            fg_color="#090d15",
            border_width=1,
            border_color="#1e2738",
        )
        capsule.pack(fill="x", padx=12, pady=(8, 4))

        inner_row = ctk.CTkFrame(capsule, fg_color="transparent")
        inner_row.pack(fill="x", padx=3, pady=3)

        self.btn_cap_mss = ctk.CTkButton(
            inner_row,
            text="Hiển thị (Nhanh - MSS)",
            height=28,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#0284c7",
            hover_color="#0369a1",
            corner_radius=6,
            text_color="#ffffff",
            command=lambda: self._set_capture_mode("mss"),
        )
        self.btn_cap_mss.pack(side="left", fill="x", expand=True, padx=2)

        self.btn_cap_adb = ctk.CTkButton(
            inner_row,
            text="Chạy ngầm (ADB - Che/Ẩn)",
            height=28,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="transparent",
            hover_color="#182030",
            corner_radius=6,
            text_color="#94a3b8",
            command=lambda: self._set_capture_mode("adb"),
        )
        self.btn_cap_adb.pack(side="left", fill="x", expand=True, padx=2)

        self.lbl_capture_note = ctk.CTkLabel(
            self.card_capture_options,
            text="⚡ Quét siêu tốc 5ms qua màn hình. Không minimize hay để cửa sổ khác che giả lập.",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#38bdf8",
            anchor="w",
            justify="left",
        )
        self.lbl_capture_note.pack(fill="x", padx=14, pady=(0, 6))

    def _set_capture_mode(self, cmode: str):
        """Chuyển đổi giữa chụp màn hình trực tiếp MSS và chụp ngầm ADB."""
        if self.is_running:
            return
        self.capture_mode = cmode
        if cmode == "mss":
            self.btn_cap_mss.configure(fg_color="#0284c7", hover_color="#0369a1", text_color="#ffffff")
            self.btn_cap_adb.configure(fg_color="transparent", hover_color="#182030", text_color="#94a3b8")
            self.lbl_capture_note.configure(
                text="⚡ Quét siêu tốc 5ms qua màn hình. Không minimize hay để cửa sổ khác che giả lập.",
                text_color="#38bdf8",
            )
            self.log("Chế độ đọc màn hình: Hiển thị (Nhanh - MSS)")
        else:
            self.btn_cap_mss.configure(fg_color="transparent", hover_color="#182030", text_color="#94a3b8")
            self.btn_cap_adb.configure(fg_color="#0284c7", hover_color="#0369a1", text_color="#ffffff")
            self.lbl_capture_note.configure(
                text="🛡️ Chụp ngầm từ Android (~0.4s/nhịp). Che cửa sổ hoặc thu nhỏ đều chạy (tắt Eco Mode).",
                text_color="#94a3b8",
            )
            self.log("Chế độ đọc màn hình: Chạy ngầm (ADB - Hỗ trợ che/thu nhỏ)")

    def _build_fishing_options(self):
        """Khung tùy chọn cơ chế click riêng cho Auto Câu Cá (Chiếm chuột vs Click ảo)."""
        self.card_fishing_options = ctk.CTkFrame(
            self,
            corner_radius=12,
            fg_color="#151c28",
            border_width=1,
            border_color="#243044",
        )

        capsule = ctk.CTkFrame(
            self.card_fishing_options,
            corner_radius=8,
            fg_color="#090d15",
            border_width=1,
            border_color="#1e2738",
        )
        capsule.pack(fill="x", padx=12, pady=(8, 4))

        inner_row = ctk.CTkFrame(capsule, fg_color="transparent")
        inner_row.pack(fill="x", padx=3, pady=3)

        self.btn_fish_mouse = ctk.CTkButton(
            inner_row,
            text="Chiếm chuột",
            height=28,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#0284c7",
            hover_color="#0369a1",
            corner_radius=6,
            text_color="#ffffff",
            command=lambda: self._set_fishing_click_mode("mouse"),
        )
        self.btn_fish_mouse.pack(side="left", fill="x", expand=True, padx=2)

        self.btn_fish_adb = ctk.CTkButton(
            inner_row,
            text="Click ảo",
            height=28,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="transparent",
            hover_color="#182030",
            corner_radius=6,
            text_color="#94a3b8",
            command=lambda: self._set_fishing_click_mode("adb"),
        )
        self.btn_fish_adb.pack(side="left", fill="x", expand=True, padx=2)

        self.lbl_fishing_note = ctk.CTkLabel(
            self.card_fishing_options,
            text="⚡ Siêu nhạy 0.02s, 100% Hoàn Hảo (Mô phỏng rung tay ±2px). Tạm giữ chuột khi giật.",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#38bdf8",
            anchor="w",
            justify="left",
        )
        self.lbl_fishing_note.pack(fill="x", padx=14, pady=(0, 6))

    def _set_fishing_click_mode(self, mode: str):
        """Chuyển đổi giữa 2 cơ chế click câu cá: Chiếm chuột vs Click ảo."""
        if self.is_running:
            return
        self.fishing_click_mode = mode
        if mode == "mouse":
            self.btn_fish_mouse.configure(fg_color="#0284c7", hover_color="#0369a1", text_color="#ffffff")
            self.btn_fish_adb.configure(fg_color="transparent", hover_color="#182030", text_color="#94a3b8")
            self.lbl_fishing_note.configure(
                text="⚡ Siêu nhạy 0.02s, 100% Hoàn Hảo (Mô phỏng rung tay ±2px). Tạm giữ chuột khi giật.",
                text_color="#38bdf8",
            )
            self.lbl_mode_status.configure(text="● Auto Câu Cá (Chiếm chuột)")
            self.log("Cơ chế câu cá: Chiếm chuột (0.02s - Mô phỏng người)")
        else:
            self.btn_fish_mouse.configure(fg_color="transparent", hover_color="#182030", text_color="#94a3b8")
            self.btn_fish_adb.configure(fg_color="#0284c7", hover_color="#0369a1", text_color="#ffffff")
            self.lbl_fishing_note.configure(
                text="🛡️ Chạy ngầm ADB, rảnh tay làm việc. (Trễ ~300ms, dễ hụt cá hiếm).",
                text_color="#94a3b8",
            )
            self.lbl_mode_status.configure(text="● Auto Câu Cá (Click ảo)")
            self.log("Cơ chế câu cá: Click ảo (ADB ngầm - Không chiếm chuột)")

    def _select_mode(self, mode: str):
        """Xử lý đổi chế độ với tên gọi ngắn gọn, không dài dòng."""
        if self.is_running:
            return

        self.selected_mode = mode

        # Cấu hình nút Active (Xanh dương hiện đại) và Inactive (Xám bạc chìm)
        inactive_cfg = {
            "fg_color": "transparent",
            "hover_color": "#182030",
            "text_color": "#94a3b8",
        }
        active_cfg = {
            "fg_color": "#0284c7",
            "hover_color": "#0369a1",
            "text_color": "#ffffff",
        }

        self.btn_mode_rally.configure(**inactive_cfg)
        self.btn_mode_fishing.configure(**inactive_cfg)
        self.btn_mode_adventure.configure(**inactive_cfg)

        if mode == "rally":
            self.btn_mode_rally.configure(**active_cfg)
            rally_desc = "Sa Hải Dune" if self.rally_mode == "dune" else "Map Thường"
            self.lbl_mode_status.configure(text=f"● Auto Rally ({rally_desc})")
            if self.card_fishing_options:
                self.card_fishing_options.pack_forget()
            if self.card_rally_options:
                self.card_rally_options.pack(fill="x", padx=24, pady=4, after=self.card_mode)
            if self.card_capture_options:
                anchor = self.card_rally_options if self.card_rally_options else self.card_mode
                self.card_capture_options.pack(fill="x", padx=24, pady=4, after=anchor)
            self.log(f"Chuyển chế độ: Auto Rally ({rally_desc})")
        elif mode == "fishing":
            self.btn_mode_fishing.configure(**active_cfg)
            mode_desc = "Chiếm chuột" if self.fishing_click_mode == "mouse" else "Click ảo"
            self.lbl_mode_status.configure(text=f"● Auto Câu Cá ({mode_desc})")
            if self.card_rally_options:
                self.card_rally_options.pack_forget()
            if self.card_capture_options:
                self.card_capture_options.pack_forget()
            if self.card_fishing_options:
                self.card_fishing_options.pack(fill="x", padx=24, pady=4, after=self.card_mode)
            self.log(f"Chuyển chế độ: Auto Câu Cá ({mode_desc})")
        elif mode == "adventure":
            self.btn_mode_adventure.configure(**active_cfg)
            self.lbl_mode_status.configure(text="● Auto Phiêu Lưu")
            if self.card_rally_options:
                self.card_rally_options.pack_forget()
            if self.card_fishing_options:
                self.card_fishing_options.pack_forget()
            if self.card_capture_options:
                self.card_capture_options.pack(fill="x", padx=24, pady=4, after=self.card_mode)
            self.log("Chuyển chế độ: Auto Phiêu Lưu")

    def _build_action_controls(self):
        """2 Nút Bắt đầu / Tạm dừng chuẩn màu Semantic: Emerald Green & Crimson Red."""
        btn_box = ctk.CTkFrame(self, fg_color="transparent")
        btn_box.pack(fill="x", padx=24, pady=8)

        # Xanh ngọc lục bảo Emerald (#10b981)
        self.btn_start = ctk.CTkButton(
            btn_box,
            text="▶ BẮT ĐẦU (F8)",
            height=44,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color="#10b981",
            hover_color="#059669",
            border_width=1,
            border_color="#34d399",
            corner_radius=12,
            text_color="#ffffff",
            command=self.start_auto,
        )
        self.btn_start.pack(side="left", fill="x", expand=True, padx=(0, 6))

        # Đỏ Crimson (#ef4444)
        self.btn_stop = ctk.CTkButton(
            btn_box,
            text="⏸ TẠM DỪNG (F8)",
            height=44,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color="#ef4444",
            hover_color="#dc2626",
            border_width=1,
            border_color="#f87171",
            corner_radius=12,
            text_color="#ffffff",
            command=self.stop_auto,
            state="disabled",
        )
        self.btn_stop.pack(side="right", fill="x", expand=True, padx=(6, 0))

    def _build_terminal_log(self):
        """Khung Console nhật ký phong cách Slate sắc nét, chuyên nghiệp."""
        log_box = ctk.CTkFrame(
            self,
            corner_radius=14,
            fg_color="#151c28",
            border_width=1,
            border_color="#243044",
        )
        log_box.pack(fill="both", expand=True, padx=24, pady=(4, 18))

        # Thanh tiêu đề nhật ký + nút Xóa
        log_top = ctk.CTkFrame(log_box, fg_color="transparent")
        log_top.pack(fill="x", padx=16, pady=(10, 4))

        lbl_log = ctk.CTkLabel(
            log_top,
            text="NHẬT KÝ HOẠT ĐỘNG",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#64748b",
        )
        lbl_log.pack(side="left")

        btn_clear = ctk.CTkButton(
            log_top,
            text="Xóa",
            width=52,
            height=22,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color="#1f2838",
            hover_color="#2c3a50",
            border_width=1,
            border_color="#374763",
            corner_radius=6,
            text_color="#94a3b8",
            command=self.clear_log,
        )
        btn_clear.pack(side="right")

        self.txt_log = ctk.CTkTextbox(
            log_box,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#080b11",
            text_color="#38bdf8",
            corner_radius=8,
            wrap="word",
        )
        self.txt_log.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def log(self, msg: str):
        """Ghi log kèm mốc thời gian."""
        timestamp = time.strftime("%H:%M:%S")
        self.txt_log.insert("end", f"[{timestamp}] {msg}\n")
        self.txt_log.see("end")

    def clear_log(self):
        self.txt_log.delete("1.0", "end")

    def refresh_connection(self):
        """Quét cửa sổ game và kết nối cổng ADB tự động trên luồng ngầm (tránh đơ UI)."""
        def _worker():
            self.log("Đang quét giả lập và kết nối ADB...")
            self.emulator_win = find_emulator_window()

            if not self.emulator_win:
                self.lbl_status_dot.configure(text_color="#ef4444")
                self.lbl_emulator_name.configure(text="Chưa tìm thấy giả lập!")
                self.lbl_details.configure(text="Vui lòng mở BlueStacks 5 hoặc LDPlayer lên trước.")
                self.log("[Cảnh báo] Chưa tìm thấy cửa sổ giả lập trên màn hình.")
                return

            hwnd = self.emulator_win._hWnd
            title = self.emulator_win.title
            self.game_vp = get_game_viewport(hwnd, title)

            serial = self.adb.auto_connect(emulator_hint=title)
            if serial and self.adb.screen_size and self.adb.screen_size[0] > 0:
                sw, sh = self.adb.screen_size
                vw, vh = self.game_vp[2], self.game_vp[3]
                # Tự động đồng bộ hướng xoay (Portrait / Landscape) giữa Viewport và Android
                if (vw < vh and sw > sh) or (vw > vh and sw < sh):
                    sw, sh = sh, sw
                    self.adb.screen_size = (sw, sh)

                self.lbl_status_dot.configure(text_color="#10b981")
                self.lbl_emulator_name.configure(text=f"{title}")
                self.lbl_details.configure(
                    text=f"Cổng: {serial} • Android: {sw}x{sh} • Viewport: {vw}x{vh}"
                )
                self.log(f"Đã kết nối thành công: {title} ({serial})")
            elif serial:
                self.lbl_status_dot.configure(text_color="#f59e0b")
                self.lbl_emulator_name.configure(text=f"{title} (Cần bật ADB)")
                self.lbl_details.configure(text="Hãy bật 'Cầu gỡ lỗi Android' trong Cài đặt giả lập.")
                self.log("Cửa sổ giả lập sẵn sàng nhưng ADB chưa mở. Hãy kiểm tra Cài đặt giả lập.")
            else:
                self.lbl_status_dot.configure(text_color="#f59e0b")
                self.lbl_emulator_name.configure(text=f"{title} (Đang dò cổng)")
                self.lbl_details.configure(text="Đang thử các cổng ADB khác...")

        threading.Thread(target=_worker, daemon=True).start()

    def test_single_click(self):
        """Chạm ngầm thử một phát vào tâm game để kiểm tra phản hồi."""
        if not self.adb.active_serial or not self.game_vp or not self.adb.screen_size:
            self.log("[Lỗi] Chưa kết nối được ADB hoặc chưa tìm thấy khung game để test.")
            return

        def _worker():
            self.log("Chuẩn bị test click ngầm vào tâm màn hình trong 1 giây...")
            time.sleep(1)
            cx = self.game_vp[0] + self.game_vp[2] // 2
            cy = self.game_vp[1] + self.game_vp[3] // 2
            ax, ay = screen_to_android(cx, cy, self.game_vp, self.adb.screen_size)
            ok = self.adb.tap(ax, ay)
            if ok:
                self.log(f"✅ [THÀNH CÔNG] Đã chạm ngầm vào game (Android: {ax}, {ay})! Chuột không di chuyển.")
            else:
                err_detail = f" [Chi tiết ADB: {self.adb.last_error}]" if self.adb.last_error else ""
                self.log(f"❌ Lệnh chạm không gửi được.{err_detail}")
                self.log("💡 Các bước kiểm tra LDPlayer:\n"
                         "  1. Cài đặt khác -> Gỡ lỗi ADB: chọn 'Mở kết nối cục bộ' (Open local connection).\n"
                         "  2. Cài đặt khác -> Quyền root: BẬT.\n"
                         "  3. BẮT BUỘC: Bấm 'Lưu cài đặt' và chọn 'Khởi động lại ngay' (Restart emulator).\n"
                         "  4. Nhìn vào màn hình LDPlayer xem có hiện popup 'Cho phép gỡ lỗi USB' (RSA key), tích Luôn cho phép -> OK.")

        threading.Thread(target=_worker, daemon=True).start()

    def get_current_viewport(self) -> Optional[Tuple[int, int, int, int]]:
        """Lấy kích thước viewport mới nhất của giả lập."""
        if not self.emulator_win:
            self.emulator_win = find_emulator_window()
        if self.emulator_win:
            self.game_vp = get_game_viewport(self.emulator_win._hWnd, self.emulator_win.title)
            return self.game_vp
        return None

    def start_auto(self):
        """Khởi động luồng chạy Auto theo chế độ đã chọn."""
        if self.is_running:
            return

        if not self.adb.active_serial:
            self.log("[Lỗi] Chưa kết nối được ADB tới giả lập. Bấm 'Quét Giả Lập' để thử lại.")
            return

        self.is_running = True
        self.stop_event.clear()

        self.btn_start.configure(text="ĐANG CHẠY...", fg_color="#334155", state="disabled")
        self.btn_stop.configure(state="normal")
        self.btn_mode_rally.configure(state="disabled")
        self.btn_mode_fishing.configure(state="disabled")
        self.btn_mode_adventure.configure(state="disabled")
        self.btn_rally_map.configure(state="disabled")
        self.btn_rally_dune.configure(state="disabled")
        self.btn_cap_mss.configure(state="disabled")
        self.btn_cap_adb.configure(state="disabled")

        mode = self.selected_mode
        rally_desc = "Sa Hải Dune" if self.rally_mode == "dune" else "Map Thường"
        mode_names = {
            "rally": f"Auto Rally ({rally_desc})",
            "fishing": "Auto Câu Cá",
            "adventure": "Auto Phiêu Lưu",
        }
        self.log(f"🚀 BẮT ĐẦU CHẠY: {mode_names.get(mode, mode)}")

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

    def stop_auto(self):
        """Yêu cầu dừng tiến trình Auto an toàn."""
        if not self.is_running:
            return

        self.log("Đang yêu cầu dừng tiến trình...")
        self.stop_event.set()

    def _on_worker_finished(self):
        """Khôi phục trạng thái nút bấm khi auto dừng."""
        self.is_running = False
        self.btn_start.configure(text="▶ BẮT ĐẦU (F8)", fg_color="#10b981", state="normal")
        self.btn_stop.configure(state="disabled")
        self.btn_mode_rally.configure(state="normal")
        self.btn_mode_fishing.configure(state="normal")
        self.btn_mode_adventure.configure(state="normal")
        self.btn_rally_map.configure(state="normal")
        self.btn_rally_dune.configure(state="normal")
        self.btn_cap_mss.configure(state="normal")
        self.btn_cap_adb.configure(state="normal")
        self.log("⏹ Đã dừng hoạt động.")

    def on_closing(self):
        """Đóng ứng dụng và giải phóng sạch daemon adb cùng hook bàn phím."""
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


def run():
    setup_windows_environment()
    app = AutoApp()
    app.mainloop()


if __name__ == "__main__":
    run()
