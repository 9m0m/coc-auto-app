"""
Giao diện người dùng đồ họa (GUI) cho COC Auto App bằng CustomTkinter.
Thiết kế Dark Mode hiện đại, trực quan, dành cho cả người dùng non-code.
"""

import sys
import os
import time
import threading
from typing import Optional

import customtkinter as ctk

from core.viewport import setup_windows_environment, find_emulator_window, get_game_viewport, screen_to_android
from core.adb_manager import ADBManager

# Cấu hình giao diện
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class AutoApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Cài đặt cửa sổ chính
        self.title("COC Auto Master - Hybrid Edition (Không Chiếm Chuột)")
        self.geometry("560x650")
        self.resizable(False, False)

        # Trạng thái hệ thống
        self.adb = ADBManager()
        self.emulator_win = None
        self.game_vp = None
        self.is_running = False
        self.selected_mode = "rally"

        # Thiết lập bố cục
        self._build_header()
        self._build_status_card()
        self._build_mode_selector()
        self._build_control_buttons()
        self._build_log_console()

        # Tự động quét giả lập khi vừa mở app
        self.after(300, self.refresh_connection)

    def _build_header(self):
        """Tiêu đề ứng dụng."""
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(15, 5))

        title_label = ctk.CTkLabel(
            header_frame,
            text="CLASH OF CRITTERS AUTO",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#38bdf8",
        )
        title_label.pack(anchor="w")

        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="Công nghệ Hybrid: Nhận diện siêu tốc + Click ngầm 100% không giật chuột",
            font=ctk.CTkFont(size=12),
            text_color="#94a3b8",
        )
        subtitle_label.pack(anchor="w")

    def _build_status_card(self):
        """Khung trạng thái kết nối giả lập và ADB."""
        card = ctk.CTkFrame(self, corner_radius=10, fg_color="#1e293b")
        card.pack(fill="x", padx=20, pady=10)

        top_row = ctk.CTkFrame(card, fg_color="transparent")
        top_row.pack(fill="x", padx=15, pady=(10, 5))

        self.lbl_status_icon = ctk.CTkLabel(
            top_row, text="🔴", font=ctk.CTkFont(size=14)
        )
        self.lbl_status_icon.pack(side="left", padx=(0, 8))

        self.lbl_status_text = ctk.CTkLabel(
            top_row,
            text="Đang tìm kiếm giả lập...",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#e2e8f0",
        )
        self.lbl_status_text.pack(side="left")

        btn_rescan = ctk.CTkButton(
            top_row,
            text="🔄 Quét lại",
            width=80,
            height=28,
            font=ctk.CTkFont(size=12),
            fg_color="#334155",
            hover_color="#475569",
            command=self.refresh_connection,
        )
        btn_rescan.pack(side="right")

        # Hàng chi tiết thiết bị & nút test
        bottom_row = ctk.CTkFrame(card, fg_color="transparent")
        bottom_row.pack(fill="x", padx=15, pady=(0, 10))

        self.lbl_device_detail = ctk.CTkLabel(
            bottom_row,
            text="Cửa sổ: Chưa rõ | ADB: Chưa kết nối",
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8",
        )
        self.lbl_device_detail.pack(side="left")

        self.btn_test_click = ctk.CTkButton(
            bottom_row,
            text="🎯 Test Click Thử",
            width=110,
            height=28,
            font=ctk.CTkFont(size=12),
            fg_color="#0284c7",
            hover_color="#0369a1",
            command=self.test_single_click,
        )
        self.btn_test_click.pack(side="right")

    def _build_mode_selector(self):
        """Khung chọn tính năng Auto."""
        card = ctk.CTkFrame(self, corner_radius=10, fg_color="#1e293b")
        card.pack(fill="x", padx=20, pady=5)

        title = ctk.CTkLabel(
            card,
            text="CHỌN TÍNH NĂNG HOẠT ĐỘNG",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#94a3b8",
        )
        title.pack(anchor="w", padx=15, pady=(10, 5))

        self.seg_mode = ctk.CTkSegmentedButton(
            card,
            values=["⚔️ Auto Rally", "🎣 Auto Câu Cá", "🗺️ Auto Phiêu Lưu"],
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._on_mode_change,
        )
        self.seg_mode.set("⚔️ Auto Rally")
        self.seg_mode.pack(fill="x", padx=15, pady=(0, 15))

    def _build_control_buttons(self):
        """Nút bấm Bắt đầu / Tạm dừng to rõ."""
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=10)

        self.btn_start = ctk.CTkButton(
            btn_frame,
            text="▶ BẮT ĐẦU (F1)",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=46,
            fg_color="#10b981",
            hover_color="#059669",
            command=self.toggle_start_stop,
        )
        self.btn_start.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.btn_stop = ctk.CTkButton(
            btn_frame,
            text="⏸ TẠM DỪNG (F2)",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=46,
            fg_color="#ef4444",
            hover_color="#dc2626",
            command=self.stop_auto,
            state="disabled",
        )
        self.btn_stop.pack(side="right", fill="x", expand=True, padx=(8, 0))

    def _build_log_console(self):
        """Bảng hiển thị thông tin log theo thời gian thực."""
        log_frame = ctk.CTkFrame(self, corner_radius=10, fg_color="#0f172a")
        log_frame.pack(fill="both", expand=True, padx=20, pady=(5, 15))

        log_title = ctk.CTkLabel(
            log_frame,
            text="NHẬT KÝ HOẠT ĐỘNG (LOG)",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#64748b",
        )
        log_title.pack(anchor="w", padx=12, pady=(8, 2))

        self.txt_log = ctk.CTkTextbox(
            log_frame,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#020617",
            text_color="#38bdf8",
            corner_radius=6,
        )
        self.txt_log.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def log(self, msg: str):
        """Ghi log vào ô hiển thị và tự động cuộn xuống cuối."""
        t_str = time.strftime("%H:%M:%S")
        full_line = f"[{t_str}] {msg}\n"
        self.txt_log.insert("end", full_line)
        self.txt_log.see("end")

    def _on_mode_change(self, value: str):
        if "Rally" in value:
            self.selected_mode = "rally"
        elif "Câu Cá" in value:
            self.selected_mode = "fishing"
        elif "Phiêu Lưu" in value:
            self.selected_mode = "adventure"
        self.log(f"Đã chuyển sang chế độ: {value}")

    def refresh_connection(self):
        """Quét và kết nối lại tới cửa sổ giả lập và ADB."""
        self.log("Đang quét cửa sổ giả lập và cổng ADB...")
        self.emulator_win = find_emulator_window()

        if not self.emulator_win:
            self.lbl_status_icon.configure(text="🔴")
            self.lbl_status_text.configure(text="Chưa tìm thấy giả lập nào đang mở!")
            self.lbl_device_detail.configure(text="Hãy bật BlueStacks hoặc LDPlayer lên trước.")
            self.log("[Cảnh báo] Không tìm thấy cửa sổ giả lập nào trên màn hình.")
            return

        hwnd = self.emulator_win._hWnd
        title = self.emulator_win.title
        self.game_vp = get_game_viewport(hwnd, title)

        # Quét ADB
        serial = self.adb.auto_connect()
        if serial and self.adb.screen_size and self.adb.screen_size[0] > 0:
            screen_sz = self.adb.screen_size
            self.lbl_status_icon.configure(text="🟢")
            self.lbl_status_text.configure(text=f"Đã kết nối: {title}")
            self.lbl_device_detail.configure(
                text=f"Port: {serial} | Android: {screen_sz[0]}x{screen_sz[1]} | Win: {self.game_vp[2]}x{self.game_vp[3]}"
            )
            self.log(f"Đã kết nối thành công tới {title} ({serial}) - Kích thước: {screen_sz[0]}x{screen_sz[1]}")
        elif serial:
            self.lbl_status_icon.configure(text="🟡")
            self.lbl_status_text.configure(text=f"Thấy cửa sổ: {title} (Cần bật ADB)")
            self.lbl_device_detail.configure(text="Hãy bật 'Cầu gỡ lỗi Android (ADB)' trong Cài đặt BlueStacks")
            self.log(f"[CHÚ Ý] Đã thấy cửa sổ '{title}' nhưng ADB bị từ chối kết nối (Android: 0x0).")
            self.log("👉 Vui lòng vào BlueStacks: Bánh răng Cài đặt -> Cài đặt nâng cao -> BẬT 'Cầu gỡ lỗi Android (ADB)' rồi bấm 'Lưu thay đổi'.")
        else:
            self.lbl_status_icon.configure(text="🟡")
            self.lbl_status_text.configure(text=f"Thấy cửa sổ: {title} (Chưa kết nối ADB)")
            self.lbl_device_detail.configure(text="Đang thử tìm lại cổng ADB...")
            self.log(f"Phát hiện cửa sổ '{title}' nhưng chưa mở được cổng kết nối ADB.")

    def test_single_click(self):
        """Thử nghiệm click 1 điểm vào tâm màn hình giả lập mà không chiếm chuột."""
        if not self.adb.active_serial or not self.game_vp or not self.adb.screen_size:
            self.log("[Lỗi] Chưa kết nối được ADB hoặc chưa tìm thấy khung game để test.")
            return

        def _do_test():
            self.log("Chuẩn bị test click ngầm vào tâm màn hình trong 2 giây...")
            time.sleep(2)
            center_x = self.game_vp[0] + self.game_vp[2] // 2
            center_y = self.game_vp[1] + self.game_vp[3] // 2
            ax, ay = screen_to_android(center_x, center_y, self.game_vp, self.adb.screen_size)
            self.log(f"Đang gửi lệnh chạm ngầm tới tọa độ Android ({ax}, {ay})...")
            ok = self.adb.tap(ax, ay)
            if ok:
                self.log("✅ [THÀNH CÔNG] Đã chạm ngầm vào game! Chuột Windows không bị di chuyển.")
            else:
                self.log("❌ [THẤT BẠI] Lệnh chạm ADB không thành công.")

        threading.Thread(target=_do_test, daemon=True).start()

    def toggle_start_stop(self):
        """Bật / Tắt trạng thái Auto."""
        if not self.is_running:
            self.is_running = True
            self.btn_start.configure(text="ĐANG CHẠY...", fg_color="#64748b", state="disabled")
            self.btn_stop.configure(state="normal")
            self.log(f"🚀 BẮT ĐẦU chạy chế độ: {self.seg_mode.get()}")
            # Sẽ kết nối trực tiếp với module logic game tương ứng tại đây
        else:
            self.stop_auto()

    def stop_auto(self):
        """Dừng Auto."""
        self.is_running = False
        self.btn_start.configure(text="▶ BẮT ĐẦU (F1)", fg_color="#10b981", state="normal")
        self.btn_stop.configure(state="disabled")
        self.log("⏹ ĐÃ TẠM DỪNG Auto.")


def run():
    setup_windows_environment()
    app = AutoApp()
    app.mainloop()


if __name__ == "__main__":
    run()
