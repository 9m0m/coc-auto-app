# COC AutoMaster

Ứng dụng tự động hóa thông minh cho game Clash of Critters trên BlueStacks 5 và các trình giả lập Android (LDPlayer, MuMu Player, NoxPlayer).

Ứng dụng sử dụng cơ chế Hybrid: nhận diện hình ảnh siêu tốc bằng thư viện MSS kết hợp gửi tín hiệu cảm ứng ngầm qua giao thức ADB. Thao tác điều khiển diễn ra trực tiếp bên trong máy ảo Android, hoàn toàn không chiếm giữ, không giật và không di chuyển con trỏ chuột máy tính.

---

## Tải Về

Tải file chạy phiên bản mới nhất tại:
**[GitHub Releases - COC AutoMaster](https://github.com/9m0m/coc-auto-app/releases/latest)**

Tải file `COC_AutoMaster.exe` về máy và mở trực tiếp. Ứng dụng đã đóng gói đầy đủ nhị phân và thư viện cần thiết, không yêu cầu cài đặt Python.

---

## Cài Đặt Giả Lập (Bắt buộc)

Để ứng dụng có thể truyền lệnh chạm ngầm vào game qua ADB:

1. Mở BlueStacks 5, chọn biểu tượng Cài đặt (bánh răng) ở thanh công cụ bên phải.
2. Chọn thẻ Nâng cao, gạt BẬT tùy chọn "Cầu gỡ lỗi Android" (Android Debug Bridge - ADB).
3. Thiết lập độ phân giải màn hình giả lập khuyến nghị: 1600 x 900 (Landscape).
4. Ứng dụng tự động dò tìm và kết nối tới cổng ADB nội bộ (127.0.0.1:5555 hoặc các cổng đa lập trình), người dùng không cần cấu hình cổng bằng tay.

---

## Hướng Dẫn Sử Dụng Nhanh

1. Khởi động giả lập và đăng nhập vào game Clash of Critters.
2. Mở file `COC_AutoMaster.exe`. Ứng dụng sẽ tự động quét cửa sổ game và kết nối ADB.
3. Chọn một trong ba chế độ tự động: Auto Rally, Auto Câu Cá hoặc Auto Phiêu Lưu.
4. Nhấn nút BẮT ĐẦU trên màn hình hoặc nhấn phím tắt `F8` để chạy. Nhấn tiếp `F8` khi muốn tạm dừng.

---

## Cơ Chế Hoạt Động Chi Tiết Từng Chế Độ

### 1. Auto Rally (Sa Hải Mê Thành)

- **Chuẩn bị:** Mở sẵn màn hình bản đồ Sa Hải Mê Thành trước khi bật auto.
- **Nhận diện tổng tấn công:** Sử dụng lọc không gian màu HSV và Contour Detection để phát hiện nhãn tổng tấn công và nút "Tham gia" màu xanh lá, thích ứng chính xác trên mọi tỉ lệ hiển thị.
- **Tự động thu phóng bản đồ (Map Overview):** Tự động định vị và kích hoạt nút kính lúp thu nhỏ (`🔍-` tại tọa độ tương đối X: 0.084, Y: 0.770). Đảm bảo góc nhìn luôn được kéo rộng tối đa để bao quát toàn bộ 4 cứ điểm phe phái trên chiến trường mà không bị thu hẹp góc nhìn khi lặp lại.
- **Xử lý trạng thái trận đánh:** Tự động bỏ qua các cứ điểm đã hết thời hạn 5 phút chờ ("Đang Chiến Đấu!"), tự đóng các bảng chi tiết tồn đọng và tự động nhận rương phần thưởng sau khi trận đấu hoàn tất.

### 2. Auto Câu Cá

- **Chuẩn bị:** Mở sẵn màn hình hồ câu cá.
- **Máy trạng thái 4 bước liên tục:**
  - **Bước 1 - Chuẩn bị thả cần (READY_TO_CAST):** Quét vùng nút câu (Rel X: 0.406, Rel Y: 0.814). Khi nút hiển thị màu xanh lá sẵn sàng (Green HSV > 400 pixel), gửi lệnh chạm quăng cần xuống nước.
  - **Bước 2 - Chờ cá cắn câu (WAITING_BITE):** Nút câu chuyển sang màu xám dưới nước (độ bão hòa S < 50, độ sáng 80 <= V <= 220). Bot giữ trạng thái chờ và liên tục đọc màu. Khi phát hiện nút đổi sang màu tím rực (Purple HSV > 700 pixel), lập tức gửi lệnh giật cần trong 350ms để chuyển vào minigame.
  - **Bước 3 - Minigame kéo cá (MINIGAME_SLIDER):** Quét vùng rãnh trượt ở tần số cao (100+ FPS). Sử dụng thuật toán phân tích hình thái học để cô lập ô vàng mục tiêu và phao câu màu đỏ. Khi phao câu tiến vào hoặc chuẩn bị giao cắt với phạm vi rãnh vàng, bot tự động nhấn giữ nhịp kéo cá. Tự động xử lý tình huống phao đỏ che khuất ô vàng hẹp của cá hiếm.
  - **Bước 4 - Nhận thưởng (CLAIM_REWARD):** Thực hiện chuỗi nhấp đa điểm vào nút "Nhận Ngay" (Rel Y: 0.870) và tâm thẻ bài (Rel Y: 0.480) để đóng nhanh các bảng popup "Cá Mới", "Kỷ Lục Đội" và nhận cá thường mà không chạm vào nút X.

### 3. Auto Phiêu Lưu (Mê Cung Cổ Vật)

- **Chuẩn bị:** Mở sẵn màn hình Vượt Ải hoặc Sảnh chính Mê Cung Cổ Vật.
- **Nhận diện mẫu đa tỉ lệ (FLEX Template Matching):** Quét màn hình đối chiếu với bộ 9 mẫu hình ảnh (Bắt đầu, Bắt đầu chiến đấu, Tiến lên, Chiến đấu, Chấp nhận, Chạm tiếp tục, Tiếp tục, Mở tất cả, Nút xác nhận OK).
- **Cơ chế chống kẹt thông minh:** Tích hợp bộ đếm giám sát chu kỳ (Watchdog). Khi phát hiện màn hình giữ nguyên một trạng thái quá 6 chu kỳ liên tiếp (kẹt đuốc hoặc popup sự kiện bất ngờ), bot tự động thực hiện thao tác giải phóng vị trí đuốc và nhấn tâm màn hình để đưa tiến trình vượt ải tiếp tục.

---

## Phím Tắt Hệ Thống

- **F8 (Global Hotkey):** Phím tắt điều khiển thông minh toàn hệ thống.
  - Khi auto đang dừng: Nhấn `F8` để Bắt đầu.
  - Khi auto đang chạy: Nhấn `F8` để Tạm dừng khẩn cấp.
  - Hoạt động toàn cục ngay cả khi cửa sổ ứng dụng đang bị thu nhỏ hoặc đang chạy nền phía sau game.
- **Nút [ ? ]:** Nằm ở góc trên bên phải giao diện ứng dụng, bấm vào để mở bảng tóm tắt hướng dẫn và thông tin liên hệ.

---

## Hỗ Trợ & Liên Hệ

- Discord: **9m0m**
- Repository: **https://github.com/9m0m/coc-auto-app**
