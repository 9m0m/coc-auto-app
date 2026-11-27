# COC AutoMaster

Tool hỗ trợ tự động cho **Clash of Critters** trên giả lập Android (**BlueStacks 5, LDPlayer, MuMu, Nox, MEmu**).

- **Tải bản chạy ngay:** [GitHub Releases - COC AutoMaster](https://github.com/9m0m/coc-auto-app/releases/latest)
- Mở trực tiếp `COC_AutoMaster.exe` (đã đóng gói sẵn ADB & thư viện, không cần cài Python).

---

## 1. Bật ADB Trên Giả Lập (Bắt buộc)

Tool dùng kết nối nội bộ `127.0.0.1` để gửi chạm/vuốt ngầm vào giả lập (an toàn, nhẹ máy, không sửa file game). Nếu giả lập đã bật sẵn ADB thì giữ nguyên.

- **BlueStacks 5:** Cài đặt (`Ctrl + Shift + I`) → **Nâng cao** → Bật **Cầu gỡ lỗi Android (ADB)** → **Lưu thay đổi**.
- **LDPlayer 9 / 4:** Cài đặt → **Khác** → Gỡ lỗi ADB chọn **Mở kết nối từ xa (Open remote connection)** → thẻ **Cơ bản** bật **Quyền Root** → Lưu & khởi động lại giả lập. *(Đóng quảng cáo/sidebar trồi ra nếu có).*
- **MuMu 12 / 6:** Cài đặt → **Khác / Cài đặt chung** (MuMu 12) hoặc **Cơ bản** (MuMu 6) → Bật **ADB Debugging** → Lưu & khởi động lại.
- **NoxPlayer:** Cài đặt → **Cài đặt chung** bật **Root** → **Điện thoại & Mạng / Nâng cao** bật **ADB / USB Debugging** → Lưu & khởi động lại.
- **MEmu Play:** Cài đặt → **Nâng cao** → Bật **Root** & **Kết nối ADB** → Lưu & khởi động lại.

> **Độ phân giải khuyến nghị:** Portrait **900x1600** hoặc **720x1280** (Phone mode). Vẫn tự đồng bộ nếu đang để Tablet ngang.

---

## 2. Hướng Dẫn Nhanh

1. Mở giả lập, vào sẵn màn hình game tương ứng với chế độ cần chạy.
2. Mở `COC_AutoMaster.exe` → kiểm tra trạng thái **xanh lá** (hoặc bấm **Quét Giả Lập**).
3. Chọn chế độ → bấm **▶ BẮT ĐẦU (`F8`)** hoặc **⏸ TẠM DỪNG (`F8`)**.

---

## 3. Các Chế Độ Hoạt Động

### Auto Rally
- **Map Thường (Gold Rush):** Mở sẵn bản đồ Sa Hải Mê Thành. Tự thu nhỏ toàn cảnh (`🔍-`), canh bắt Rally và nhận thưởng.
- **Sa Hải Dune (Chat):** Mở sẵn Mapview hoặc khung Chat. Tự canh tab **Liên Minh**, lọc thẻ Rally (tím / hồng san hô / vàng `Cồn Cát`), chống trôi tin mỗi `8s`, xử lý popup & nhận quà.

### Auto Câu Cá
- Mở sẵn hồ câu cá. Tự quăng cần, chờ cá cắn, kéo rãnh vàng và đóng thẻ nhận thưởng.
- **Chiếm chuột:** Phản xạ `0.02s`, tỉ lệ Hoàn Hảo cao nhất (tạm chiếm chuột lúc giật cá).
- **Click ảo:** Chạy ngầm qua ADB, không chiếm chuột (trễ ~300ms).

### Auto Phiêu Lưu
- Mở sẵn sảnh hoặc trong Mê Cung Cổ Vật. Tự bấm Tiến Lên, Chiến Đấu, nhận cổ vật, kết toán và chống kẹt đuốc.

---

## 4. Chế Độ Đọc Màn Hình (MSS vs ADB)

- **Hiển thị (Nhanh - MSS)** *(mặc định, bắt buộc cho Auto Câu Cá)*:
  - Tốc độ ~5ms/frame.
  - **Không thu nhỏ (minimize)** giả lập và **không để cửa sổ khác (kể cả cửa sổ tool) che vùng game**.
- **Chạy ngầm (ADB - Che/Ẩn)** *(chỉ dành cho Auto Rally & Auto Phiêu Lưu)*:
  - Chụp thẳng từ Android (~0.4s/nhịp).
  - **Che cửa sổ khác hoặc thu nhỏ giả lập vẫn chạy.** Nếu minimize BlueStacks, hãy tắt **Eco Mode** để game không bị dừng hình.

---

## 5. Phím Tắt & Hỗ Trợ

- **`F8`:** Bật / Tắt Auto nhanh (toàn cục).
- **`[ ? ]`:** Mở hướng dẫn nhanh ngay trong app.
- **Discord hỗ trợ:** `9m0m`
- **Repo:** https://github.com/9m0m/coc-auto-app
