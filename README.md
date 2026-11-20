# Clash of Critters - Auto App (Hybrid Edition)

Ứng dụng Macro và Tự động hóa thông minh cho game **Clash of Critters** trên các trình giả lập Android (BlueStacks 5, LDPlayer 9/5/4, MuMu Player, NoxPlayer).

## 🌟 Điểm nổi bật
- **100% Không Chiếm Chuột (Background / Non-intrusive Tap):** Sử dụng cơ chế Hybrid (Nhận diện siêu tốc bằng MSS + Bấm ngầm trực tiếp qua ADB). Con trỏ chuột Windows hoàn toàn rảnh tay để bạn làm việc, lướt web hoặc chơi game khác.
- **Tự động dò tìm cổng giả lập (Zero-Config):** Tự động phát hiện cổng kết nối ADB của BlueStacks, LDPlayer, MuMu mà người dùng không cần cấu hình thủ công.
- **Tích hợp sẵn file chạy ADB:** Đã bao gồm binary ADB trong thư mục `binaries/`, người dùng tải về là chạy ngay, không cần cài thêm Python hay SDK Android.

## 📁 Cấu trúc thư mục chuẩn (Clean Architecture)
```text
coc-auto-app/
├── core/                        # Nền tảng lõi
│   ├── adb_manager.py           # Quản lý và kết nối ADB ngầm
│   ├── viewport.py              # Xử lý cửa sổ giả lập & ánh xạ tọa độ
│   └── vision.py                # Quét màn hình siêu tốc (MSS + OpenCV)
│
├── modules/                     # Các chức năng game
│   ├── rally.py                 # Auto Tổng Tấn Công (Rally)
│   ├── fishing.py               # Auto Câu Cá
│   └── adventure.py             # Auto Phiêu Lưu
│
├── ui/                          # Giao diện người dùng đồ họa (GUI)
├── assets/                      # Ảnh mẫu và tài nguyên nhúng
├── binaries/                    # File thực thi adb.exe đi kèm
├── test_adb_click.py            # Script kiểm thử click ngầm
└── README.md
```

## 🚀 Hướng dẫn kiểm tra nhanh
1. Mở BlueStacks hoặc LDPlayer và vào game Clash of Critters.
2. Chạy lệnh kiểm tra click ngầm:
```bash
python test_adb_click.py
```
3. Quan sát: Tool sẽ bấm thử vào tâm màn hình giả lập mà con trỏ chuột của bạn hoàn toàn đứng yên!
