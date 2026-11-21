"""
Giao diện người dùng đồ họa Glass UI hiện đại cho COC AutoMaster.
Thiết kế tối giản, loại bỏ chữ thừa, cân bằng kích thước nút bấm, thẩm mỹ cao.
"""

import sys
import os
import time
import threading
from typing import Optional, Tuple

import customtkinter as ctk

from core.viewport import setup_windows_environment, find_emulator_window, get_game_viewport, screen_to_android
from core.adb_manager import ADBManager
from modules.rally import run_rally_loop
from modules.fishing import run_fishing_loop
from modules.adventure import run_adventure_loop

# Cấu hình giao diện chuẩn Dark Glass
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class AutoApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Thiết lập cửa sổ chính
        self.title("COC AutoMaster")
        self.geometry("520x640")
        self.resizable(False, False)
        self.configure(fg_color="#0a0e17")  # Nền tối sâu sang trọng

        # Quản lý hệ thống & tiến trình
        self.adb = ADBManager()
        self.emulator_win = None
        self.game_vp: Optional[Tuple[int, int, int, int]] = None

        self.worker_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.is_running = False
        self.selected_mode = "rally"

        # Khởi tạo các thành phần giao diện
        self._build_header()
        self._build_device_card()
        self._build_mode_card()
        self._build_action_controls()
        self._build_log_console()

        # Phím tắt F1 (Bắt đầu) / F2 (Tạm dừng)
        self.bind("<F1>", lambda e: self.start_auto())
        self.bind("<F2>", lambda e: self.stop_auto())

        # Đăng ký đóng ứng dụng an toàn
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Tự động quét giả lập khi mở app
        self.after(300, self.refresh_connection)

    def _build_header(self):
        """Header tối giản, tinh tế, không chữ thừa."""
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(18, 10))

        # Tiêu đề ứng dụng
        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left")

        title = ctk.CTkLabel(
            title_box,
            text="COC AutoMaster",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color="#f8fafc",
        )
        title.pack(side="left")

        badge = ctk.CTkLabel(
            title_box,
            text="HYBRID",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color="#1e293b",
            text_color="#38bdf8",
            corner_radius=6,
            padx=8,
            pady=2,
        )
        badge.pack(side="left", padx=10)

        # Nhãn trạng thái không chiếm chuột
        sub_tag = ctk.CTkLabel(
            header,
            text="100% Không Chiếm Chuột",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#64748b",
        )
        sub_tag.pack(side="right")

    def _build_device_card(self):
        """Card trạng thái giả lập phong cách Glass UI với nút bấm cân bằng."""
        self.card_device = ctk.CTkFrame(
            self,
            corner_radius=12,
            fg_color="#111827",
            border_width=1,
            border_color="#1f293d",
        )
        self.card_device.pack(fill="x", padx=24, pady=6)

        # Dòng 1: Đèn báo & Tên giả lập
        status_row = ctk.CTkFrame(self.card_device, fg_color="transparent")
        status_row.pack(fill="x", padx=16, pady=(12, 4))

        self.lbl_status_dot = ctk.CTkLabel(
            status_row,
            text="●",
            font=ctk.CTkFont(size=14),
            text_color="#f59e0b",
        )
        self.lbl_status_dot.pack(side="left", padx=(0, 6))

        self.lbl_emulator_name = ctk.CTkLabel(
            status_row,
            text="Đang tìm kiếm giả lập...",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color="#f1f5f9",
        )
        self.lbl_emulator_name.pack(side="left")

        # Dòng 2: Thông số kỹ thuật (Cổng & Độ phân giải)
        self.lbl_details = ctk.CTkLabel(
            self.card_device,
            text="Cổng: Đang dò • Màn hình: Đang đọc",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#94a3b8",
            anchor="w",
        )
        self.lbl_details.pack(fill="x", padx=16, pady=(0, 10))

        # Dòng 3: 2 Nút thao tác kích thước cân bằng 50/50
        action_row = ctk.CTkFrame(self.card_device, fg_color="transparent")
        action_row.pack(fill="x", padx=16, pady=(0, 14))

        self.btn_rescan = ctk.CTkButton(
            action_row,
            text="🔄 Quét Lại",
            height=34,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#1e293b",
            hover_color="#334155",
            border_width=1,
            border_color="#334155",
            corner_radius=8,
            command=self.refresh_connection,
        )
        self.btn_rescan.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.btn_test = ctk.CTkButton(
            action_row,
            text="🎯 Test Click",
            height=34,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#0284c7",
            hover_color="#0369a1",
            corner_radius=8,
            command=self.test_single_click,
        )
        self.btn_test.pack(side="right", fill="x", expand=True, padx=(6, 0))

    def _build_mode_card(self):
        """Card chọn tính năng Auto trực quan, rõ ràng, không lỗi font."""
        card_mode = ctk.CTkFrame(
            self,
            corner_radius=12,
            fg_color="#111827",
            border_width=1,
            border_color="#1f293d",
        )
        card_mode.pack(fill="x", padx=24, pady=6)

        # Tiêu đề Card
        lbl_card_title = ctk.CTkLabel(
            card_mode,
            text="CHỌN TÍNH NĂNG",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#64748b",
            anchor="w",
        )
        lbl_card_title.pack(fill="x", padx=16, pady=(12, 8))

        # 3 Nút bấm riêng biệt cân bằng, không dùng segmented button để tránh lỗi font glyph
        mode_btn_box = ctk.CTkFrame(card_mode, fg_color="transparent")
        mode_btn_box.pack(fill="x", padx=14, pady=(0, 10))

        self.btn_mode_rally = ctk.CTkButton(
            mode_btn_box,
            text="⚔️ Rally",
            height=38,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#0284c7",
            hover_color="#0369a1",
            border_width=1,
            border_color="#38bdf8",
            corner_radius=8,
            command=lambda: self._select_mode("rally"),
        )
        self.btn_mode_rally.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.btn_mode_fishing = ctk.CTkButton(
            mode_btn_box,
            text="🎣 Câu Cá",
            height=38,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#1e293b",
            hover_color="#334155",
            border_width=1,
            border_color="#334155",
            corner_radius=8,
            text_color="#94a3b8",
            command=lambda: self._select_mode("fishing"),
        )
        self.btn_mode_fishing.pack(side="left", fill="x", expand=True, padx=4)

        self.btn_mode_adventure = ctk.CTkButton(
            mode_btn_box,
            text="🧭 Phiêu Lưu",
            height=38,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#1e293b",
            hover_color="#334155",
            border_width=1,
            border_color="#334155",
            corner_radius=8,
            text_color="#94a3b8",
            command=lambda: self._select_mode("adventure"),
        )
        self.btn_mode_adventure.pack(side="left", fill="x", expand=True, padx=(4, 0))

        # Thanh chỉ báo trạng thái kích hoạt rõ ràng
        desc_box = ctk.CTkFrame(card_mode, fg_color="#0d1424", corner_radius=6)
        desc_box.pack(fill="x", padx=14, pady=(0, 12))

        self.lbl_mode_status = ctk.CTkLabel(
            desc_box,
            text="🎯 Đang chọn: Auto Rally (Tổng Tấn Công Sa Hải Mê Thành)",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#38bdf8",
            padx=10,
            pady=6,
        )
        self.lbl_mode_status.pack()

    def _select_mode(self, mode: str):
        """Xử lý chuyển đổi tính năng và cập nhật giao diện trực quan."""
        if self.is_running:
            return

        self.selected_mode = mode

        # Đặt lại màu cho cả 3 nút
        inactive_cfg = {
            "fg_color": "#1e293b",
            "hover_color": "#334155",
            "border_color": "#334155",
            "text_color": "#94a3b8",
        }
        active_cfg = {
            "fg_color": "#0284c7",
            "hover_color": "#0369a1",
            "border_color": "#38bdf8",
            "text_color": "#ffffff",
        }

        self.btn_mode_rally.configure(**inactive_cfg)
        self.btn_mode_fishing.configure(**inactive_cfg)
        self.btn_mode_adventure.configure(**inactive_cfg)

        if mode == "rally":
            self.btn_mode_rally.configure(**active_cfg)
            self.lbl_mode_status.configure(
                text="🎯 Đang chọn: Auto Rally (Tổng Tấn Công Sa Hải Mê Thành)"
            )
            self.log("Chuyển chế độ: ⚔️ Auto Rally")
        elif mode == "fishing":
            self.btn_mode_fishing.configure(**active_cfg)
            self.lbl_mode_status.configure(
                text="🎯 Đang chọn: Auto Câu Cá (Tự Động Kéo Cá Theo Rãnh Vàng)"
            )
            self.log("Chuyển chế độ: 🎣 Auto Câu Cá")
        elif mode == "adventure":
            self.btn_mode_adventure.configure(**active_cfg)
            self.lbl_mode_status.configure(
                text="🎯 Đang chọn: Auto Phiêu Lưu (Tự Vượt Ải Mê Cung Cổ Vật)"
            )
            self.log("Chuyển chế độ: 🧭 Auto Phiêu Lưu")

    def _build_action_controls(self):
        """2 Nút Bắt đầu / Tạm dừng đồng đều 50/50, chuẩn đẹp."""
        btn_box = ctk.CTkFrame(self, fg_color="transparent")
        btn_box.pack(fill="x", padx=24, pady=8)

        self.btn_start = ctk.CTkButton(
            btn_box,
            text="▶ BẮT ĐẦU (F1)",
            height=44,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            fg_color="#10b981",
            hover_color="#059669",
            corner_radius=8,
            command=self.start_auto,
        )
        self.btn_start.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.btn_stop = ctk.CTkButton(
            btn_box,
            text="⏸ TẠM DỪNG (F2)",
            height=44,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            fg_color="#ef4444",
            hover_color="#dc2626",
            corner_radius=8,
            command=self.stop_auto,
            state="disabled",
        )
        self.btn_stop.pack(side="right", fill="x", expand=True, padx=(6, 0))

    def _build_log_console(self):
        """Khung Console nhật ký phong cách Glass Terminal."""
        log_box = ctk.CTkFrame(
            self,
            corner_radius=12,
            fg_color="#070c18",
            border_width=1,
            border_color="#1f293d",
        )
        log_box.pack(fill="both", expand=True, padx=24, pady=(4, 16))

        # Tiêu đề log + nút xoá
        log_top = ctk.CTkFrame(log_box, fg_color="transparent")
        log_top.pack(fill="x", padx=12, pady=(8, 4))

        lbl_log = ctk.CTkLabel(
            log_top,
            text="NHẬT KÝ HOẠT ĐỘNG",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#64748b",
        )
        lbl_log.pack(side="left")

        btn_clear = ctk.CTkButton(
            log_top,
            text="Xóa",
            width=48,
            height=20,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            fg_color="transparent",
            hover_color="#1e293b",
            text_color="#94a3b8",
            command=self.clear_log,
        )
        btn_clear.pack(side="right")

        self.txt_log = ctk.CTkTextbox(
            log_box,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#030712",
            text_color="#38bdf8",
            corner_radius=8,
            wrap="word",
        )
        self.txt_log.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def log(self, msg: str):
        """Ghi log kèm mốc thời gian."""
        timestamp = time.strftime("%H:%M:%S")
        self.txt_log.insert("end", f"[{timestamp}] {msg}\n")
        self.txt_log.see("end")

    def clear_log(self):
        self.txt_log.delete("1.0", "end")

    def refresh_connection(self):
        """Quét cửa sổ game và kết nối cổng ADB tự động."""
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

        serial = self.adb.auto_connect()
        if serial and self.adb.screen_size and self.adb.screen_size[0] > 0:
            sz = self.adb.screen_size
            self.lbl_status_dot.configure(text_color="#10b981")  # Xanh ngọc kết nối thành công
            self.lbl_emulator_name.configure(text=f"{title}")
            self.lbl_details.configure(
                text=f"Cổng: {serial} • Android: {sz[0]}x{sz[1]} • Viewport: {self.game_vp[2]}x{self.game_vp[3]}"
            )
            self.log(f"Đã kết nối thành công: {title} ({serial})")
        elif serial:
            self.lbl_status_dot.configure(text_color="#f59e0b")
            self.lbl_emulator_name.configure(text=f"{title} (Cần bật ADB)")
            self.lbl_details.configure(text="Hãy bật 'Cầu gỡ lỗi Android' trong Cài đặt BlueStacks.")
            self.log("Cửa sổ giả lập sẵn sàng nhưng ADB chưa mở. Hãy kiểm tra Cài đặt -> Nâng cao.")
        else:
            self.lbl_status_dot.configure(text_color="#f59e0b")
            self.lbl_emulator_name.configure(text=f"{title} (Đang dò cổng)")
            self.lbl_details.configure(text="Đang thử các cổng ADB khác...")

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
                self.log("❌ Lệnh chạm không gửi được.")

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
            self.log("[Lỗi] Chưa kết nối được ADB tới giả lập. Bấm 'Quét Lại' để thử lại.")
            return

        self.is_running = True
        self.stop_event.clear()

        self.btn_start.configure(text="ĐANG CHẠY...", fg_color="#334155", state="disabled")
        self.btn_stop.configure(state="normal")
        self.btn_mode_rally.configure(state="disabled")
        self.btn_mode_fishing.configure(state="disabled")
        self.btn_mode_adventure.configure(state="disabled")

        mode = self.selected_mode
        mode_names = {"rally": "⚔️ Auto Rally", "fishing": "🎣 Auto Câu Cá", "adventure": "🧭 Auto Phiêu Lưu"}
        self.log(f"🚀 BẮT ĐẦU CHẠY: {mode_names.get(mode, mode)}")

        def _runner():
            try:
                if mode == "rally":
                    run_rally_loop(self.adb, self.get_current_viewport, self.stop_event, self.log)
                elif mode == "fishing":
                    run_fishing_loop(self.adb, self.get_current_viewport, self.stop_event, self.log)
                elif mode == "adventure":
                    run_adventure_loop(self.adb, self.get_current_viewport, self.stop_event, self.log)
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
        self.btn_start.configure(text="▶ BẮT ĐẦU (F1)", fg_color="#10b981", state="normal")
        self.btn_stop.configure(state="disabled")
        self.btn_mode_rally.configure(state="normal")
        self.btn_mode_fishing.configure(state="normal")
        self.btn_mode_adventure.configure(state="normal")
        self.log("⏹ Đã dừng hoạt động.")

    def on_closing(self):
        """Đóng ứng dụng và giải phóng sạch daemon adb."""
        self.stop_event.set()
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
