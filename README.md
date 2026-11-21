# COC AutoMaster

Ứng dụng tự động hóa thông minh cho game Clash of Critters trên các trình giả lập Android phổ biến (BlueStacks 5, LDPlayer, MuMu Player, NoxPlayer, MEmu Play).

Ứng dụng sử dụng cơ chế Hybrid: nhận diện hình ảnh siêu tốc bằng thư viện MSS kết hợp gửi tín hiệu cảm ứng ngầm qua giao thức ADB. Thao tác điều khiển diễn ra trực tiếp bên trong hệ điều hành Android của giả lập, hoàn toàn không chiếm giữ, không giật và không di chuyển con trỏ chuột máy tính.

---

## Tải Về

Tải file chạy phiên bản mới nhất tại:
**[GitHub Releases - COC AutoMaster](https://github.com/9m0m/coc-auto-app/releases/latest)**

Tải file `COC_AutoMaster.exe` về máy và mở trực tiếp. Ứng dụng đã đóng gói đầy đủ nhị phân ADB và thư viện cần thiết, không yêu cầu cài đặt Python hay thiết lập biến môi trường.

---

## Hướng Dẫn Kích Hoạt ADB Trên Từng Giả Lập

Ứng dụng tự động dò tìm và kết nối tới cổng ADB nội bộ của các giả lập. Bạn chỉ cần đảm bảo tùy chọn ADB đã được bật trên giả lập:

- **BlueStacks 5:**
  Vào Cài đặt (biểu tượng bánh răng) -> chọn thẻ Nâng cao -> gạt BẬT tùy chọn "Cầu gỡ lỗi Android" (Android Debug Bridge - ADB). Cổng mặc định thường là 5555, 5665, 5705...
- **LDPlayer 9 / 4:**
  Vào Cài đặt (biểu tượng bánh răng) -> chọn thẻ Nâng cao (hoặc Khác) -> tại mục "Gỡ lỗi ADB", chọn "Mở kết nối cục bộ" (Local Connection). Cổng mặc định thường là 5555, 5557, 5559...
- **MuMu Player 12 / 6:**
  Vào Trung tâm cài đặt -> chọn thẻ Khác -> tích chọn BẬT "Gỡ lỗi ADB". Cổng mặc định thường là 7555 hoặc 16384.
- **NoxPlayer:**
  Vào Cài đặt hệ thống -> Cài đặt điện thoại / Chung -> tích chọn BẬT "Gỡ lỗi USB / ADB". Cổng mặc định thường là 62001.
- **MEmu Play:**
  Vào Cài đặt -> Nâng cao -> BẬT kết nối ADB. Cổng mặc định thường là 21503.

---

## Lưu Ý Quan Trọng Khi Sử Dụng

1. **Tuyệt đối không thu nhỏ (Minimize) cửa sổ giả lập xuống thanh Taskbar:**
   - Cơ chế Hybrid chụp hình ảnh trực tiếp từ bộ đệm hiển thị cửa sổ trên Windows. Khi bạn bấm nút thu nhỏ (`_`) xuống thanh tác vụ, Windows sẽ lập tức ngắt luồng vẽ đồ họa của cửa sổ đó, khiến bot không thể quét được màn hình game.
   - **Cách chạy ngầm đúng:** Bạn chỉ cần để cửa sổ game mở trên màn hình, sau đó thoải mái mở trình duyệt, Discord, Word, xem phim hoặc chơi game khác đè lên trên cửa sổ giả lập. Thao tác click ngầm qua ADB vẫn hoạt động 100% bình thường kể cả khi cửa sổ game bị che khuất hoàn toàn.

2. **Lưu ý khi sử dụng nhiều màn hình (Multi-Monitor):**
   - Đặt toàn bộ cửa sổ game nằm trọn vẹn trong phạm vi một màn hình (màn hình chính hoặc màn hình phụ).
   - Tránh kéo cửa sổ game nằm lơ lửng ở ranh giới giữa hai màn hình vì Windows sẽ chia cắt tọa độ pixel.
   - Giữ nguyên tỉ lệ hiển thị (Windows Display Scaling) ở mức đồng nhất (khuyến nghị 100%).

3. **Độ phân giải & Tỉ lệ khung hình:**
   - Khuyến nghị thiết lập màn hình giả lập ở độ phân giải 1600 x 900 hoặc 1280 x 720 (Landscape tỉ lệ 16:9).
   - Toàn bộ tọa độ trong bot được tính toán theo tỉ lệ tương đối (Relative Ratio), tự động co giãn theo kích thước khung hình game.
   - Tránh dùng chuột co kéo thay đổi kích thước cửa sổ game khi bot đang trong trận kéo cá minigame.

---

## Hướng Dẫn Sử Dụng Nhanh

1. Khởi động giả lập và đăng nhập vào game Clash of Critters.
2. Mở file `COC_AutoMaster.exe`. Ứng dụng sẽ tự động quét và báo kết nối thành công tới giả lập.
3. Nhấp chọn chế độ tự động cần dùng: Auto Rally, Auto Câu Cá hoặc Auto Phiêu Lưu.
4. Nhấn nút BẮT ĐẦU trên giao diện hoặc nhấn phím tắt `F8` để chạy. Nhấn tiếp `F8` khi muốn tạm dừng.

---

## Cơ Chế Hoạt Động Chi Tiết Từng Chế Độ

### 1. Auto Rally (Sa Hải Mê Thành)

- **Chuẩn bị:** Mở sẵn màn hình bản đồ Sa Hải Mê Thành trước khi bật auto.
- **Nhận diện tổng tấn công:** Sử dụng lọc không gian màu HSV và Contour Detection để phát hiện nhãn tổng tấn công và nút "Tham gia" màu xanh lá, thích ứng chính xác trên mọi độ phân giải.
- **Tự động thu phóng bản đồ (Map Overview):** Tự động định vị và kích hoạt nút kính lúp thu nhỏ (`🔍-` tại tọa độ tương đối X: 0.084, Y: 0.770). Đảm bảo góc nhìn luôn được kéo rộng tối đa để bao quát toàn bộ 4 cứ điểm phe phái trên chiến trường mà không bị co hẹp góc nhìn khi lặp lại.
- **Xử lý trận đánh:** Tự động bỏ qua các cứ điểm đã hết thời hạn 5 phút chờ ("Đang Chiến Đấu!"), tự đóng các bảng chi tiết tồn đọng và tự động nhận rương phần thưởng sau khi trận đấu hoàn tất.

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
