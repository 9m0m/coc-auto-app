# QUY CHUẨN PHÁT TRIỂN & KIỂM THỬ TỰ ĐỘNG DÀNH CHO AI AGENT (AGENTS.MD)

Tài liệu này là **bản hợp đồng quy chuẩn bắt buộc** cho bất kỳ AI Agent nào (Antigravity, Cursor, Claude Code, Copilot, v.v.) làm việc trên dự án này.
Mục tiêu tối thượng: **Độ ổn định 100% trong môi trường chạy thật - Code sạch (Clean Code), chuẩn mực (Best Practices), sửa đúng nơi (Proper Scoping) và tuyệt đối không phát sinh lỗi crash lúc runtime.**

---

## 1. PHẠM VI DỰ ÁN & NGUYÊN TẮC DUY NHẤT (SINGLE REPO OF TRUTH)
* **Kho mã nguồn chính thức duy nhất**: `c:\ky_9_FPT\coc-auto-app`
  - Đây là phiên bản hoàn chỉnh gồm giao diện CustomTkinter, hệ thống ADB, xử lý hình ảnh OpenCV, quản lý đa luồng và cấu hình đóng gói PyInstaller.
* **TUYỆT ĐỐI KHÔNG ĐỤNG TỚI `scripauto`**:
  - Repo `c:\ky_9_FPT\scripauto` là phiên bản cũ đã ngừng sử dụng (DEPRECATED).
  - Không đọc, không sửa đổi, không test, không build và không commit vào thư mục này.

---

## 2. KIẾN TRÚC PHÂN LỚP & NGUYÊN TẮC "SỬA ĐÚNG NƠI CẦN THIẾT" (SCOPED RESPONSIBILITY)

Dự án được tổ chức theo kiến trúc phân tách trách nhiệm rõ ràng. Khi nhận yêu cầu, Agent **phải sửa đúng tệp tin chịu trách nhiệm tương ứng**, tuyệt đối không viết chéo hay rải rác:

```
c:\ky_9_FPT\coc-auto-app\
├── config.py             # [CẤU HÌNH] Nơi duy nhất chứa tham số, ngưỡng threshold, scale, offset
├── assets.py             # [TÀI NGUYÊN] Nơi duy nhất chứa Base64 templates và hàm decode hình ảnh
├── main.py               # [ENTRYPOINT] Điểm khởi động ứng dụng và khởi tạo cửa sổ
├── core/                 # [HẠ TẦNG DÙNG CHUNG] Tuyệt đối không chứa logic game
│   ├── adb_manager.py    # Kết nối ADB, gửi lệnh chạm (tap), vuốt (swipe), phím bấm
│   ├── window_manager.py # Bắt cửa sổ giả lập Win32, tính toán viewport, DPI scaling
│   ├── vision.py         # Hàm thị giác nguyên bản (matchTemplate, inRange, color mask)
│   └── logger.py         # Quản lý ghi log đa luồng ra giao diện và tệp tin
├── modules/              # [NGHIỆP VỤ TỪNG CHẾ ĐỘ CHƠI]
│   ├── rally.py          # Nghiệp vụ Auto Rally (quét bản đồ, lọc trùng NMS, click tâm Avatar)
│   ├── fishing.py        # Nghiệp vụ Auto Câu Cá
│   └── adventure.py      # Nghiệp vụ Auto Phiêu Lưu
├── ui/                   # [GIAO DIỆN NGƯỜI DÙNG]
│   └── main_window.py    # Giao diện CustomTkinter, sự kiện nút bấm, cập nhật trạng thái UI
└── tests/                # [BỘ KIỂM THỬ CHẤT LƯỢNG TỰ ĐỘNG]
    └── test_code_quality.py # Cổng kiểm thử AST, Assets, Config và Mock Pipeline
```

### Bảng phân định sửa đúng nơi:
| Khi cần làm gì? | Nơi BẮT BUỘC sửa | Nơi TUYỆT ĐỐI KHÔNG sửa lung tung |
| :--- | :--- | :--- |
| **Thay đổi ngưỡng nhận diện, scale, bán kính, offset** | `config.py` | Không hardcode số trong `modules/` |
| **Thêm / cập nhật template hình ảnh mẫu** | `assets.py` | Không nhúng chuỗi Base64 vào `modules/` |
| **Sửa logic xử lý Rally, lọc trùng, click** | `modules/rally.py` | Không can thiệp vào `core/` hay `ui/` |
| **Cải tiến kết nối ADB hoặc tọa độ Win32** | `core/adb_manager.py`, `window_manager.py` | Không sửa trong các file `modules/` |
| **Chỉnh sửa nút bấm, màu sắc, bố cục giao diện** | `ui/main_window.py` | Không viết logic OpenCV trong file UI |

---

## 3. NGUYÊN TẮC CLEAN CODE & BEST PRACTICES BẮT BUỘC

### 3.1. Cấm tuyệt đối Magic Numbers (No Hardcoded Constants)
* Mọi hằng số toán học, tỉ lệ tọa độ, ngưỡng nhận diện, thời gian chờ đều phải được đặt tên rõ nghĩa trong `config.py`:
  - ❌ `res = cv2.matchTemplate(crop, tpl, 0.52)` và `y - int(th * 0.85)`
  -  `thresh = getattr(config, "RALLY_TIMER_MATCH_THRESHOLD", 0.52)` và `avatar_offset = getattr(config, "RALLY_TIMER_AVATAR_OFFSET_Y", 0.85)`

### 3.2. An toàn mảng NumPy & OpenCV (NumPy / OpenCV Safety)
* **CẤM TUYỆT ĐỐI**: Không bao giờ được đánh giá mảng NumPy như một giá trị boolean:
  - ❌ `if arr:` hoặc `if not arr:`
  - ❌ `arr or fallback_arr`
  - ❌ `if arr1 and arr2:`
  *(Lý do: Trong Python, ép kiểu boolean trên mảng NumPy có $>1$ phần tử sẽ ném `ValueError: The truth value of an array with more than one element is ambiguous`).*
* **BẮT BUỘC SỬ DỤNG**:
  - Kiểm tra tồn tại: `if arr is not None:`
  - Kiểm tra rỗng: `if arr is not None and arr.size > 0:`
  - Gán giá trị mặc định: `arr = primary_arr if primary_arr is not None else fallback_arr`
  - So sánh điều kiện mảng: `if np.any(condition):` hoặc `if np.all(condition):`

### 3.3. An toàn Template Matching & Xử lý kích thước (Vision Safety)
* Trước khi gọi `cv2.matchTemplate(image, template, ...)`:
  - Phải kiểm tra kích thước: `template.shape[0] <= image.shape[0]` và `template.shape[1] <= image.shape[1]`.
  - Phải kiểm tra kích thước tối thiểu sau khi resize: `max(5, int(w * scale))`.
* Tọa độ click và vùng cắt crop phải luôn được ép kiểu số nguyên: `int(x)`.
* Giới hạn tọa độ luôn nằm trong khung hình hợp lệ: `max(0, min(max_bound, coord))`.

### 3.4. Chuẩn Naming & Type Hints (PEP 8 & Readability)
* **Biến & Hàm**: `snake_case`, tên thể hiện rõ hành động (ví dụ: `scan_and_join_map_rallies`, `detect_faction_name`).
* **Hằng số**: `UPPER_CASE_SNAKE` (ví dụ: `RALLY_TIMER_MATCH_THRESHOLD`).
* **Lớp (Class)**: `PascalCase` (ví dụ: `ADBManager`, `MainWindow`).
* **Type Hints**: Toàn bộ hàm mới hoặc hàm sửa đổi phải có type hints đầy đủ cho tham số và giá trị trả về:
  ```python
  def find_targets(crop: np.ndarray, threshold: float = 0.52) -> List[Tuple[int, int, float]]:
  ```

### 3.5. Xử lý Ngoại lệ chuẩn mực (Graceful Error Handling)
* **CẤM NUỐT LỖI IM LẶNG**: Tuyệt đối không dùng `try: ... except: pass` mà không có log.
* Phải bắt đúng ngoại lệ cụ thể và ghi log rõ ràng:
  ```python
  try:
      res = cv2.matchTemplate(...)
  except cv2.error as e:
      logger.warning(f"Lỗi khớp ảnh mẫu OpenCV: {e}")
  ```

### 3.6. An toàn Đa luồng (Threading & Graceful Exit)
* Mọi vòng lặp worker (`while True:`, `while _is_running:`) bắt buộc phải kiểm tra cờ dừng:
  ```python
  if _stop_event.is_set() or _is_paused:
      break
  ```
* Không chạy tác vụ nặng (OpenCV, ADB, OCR) trực tiếp trên Main Thread của GUI.

---

## 4. QUY TRÌNH KIỂM THỬ CHẤT LƯỢNG 4 BƯỚC BẮT BUỘC (4-STEP VERIFICATION GATE)

Trước khi xác nhận hoàn thành, commit hoặc build `.exe`, Agent **BẮT BUỘC** phải chạy đủ 4 bước sau:

### Bước 1: Kiểm tra Cú pháp Tĩnh (Static Syntax Compilation)
```powershell
python -m compileall -q .
```
*Yêu cầu*: 0 lỗi cú pháp.

### Bước 2: Quét AST Chống Anti-Pattern (Anti-Pattern Static AST Scan)
```powershell
python tests/test_code_quality.py -k test_ast_no_array_boolean_coercion
```
*Yêu cầu*: Không có bất kỳ biểu thức `or`, `and`, `not` nào chứa biến mảng hình ảnh (`template`, `crop`, `frame`, `arr`, `img`, `pill`).

### Bước 3: Chạy Test Suite Tự Động (Automated Quality Test Suite)
```powershell
python tests/test_code_quality.py
```
*Yêu cầu*: Tất cả bài test đều PASS (Asset decoding, Config schema, Mock pipeline safety).

### Bước 4: Kiểm tra Đóng gói Bản dựng (Build & Binary Verification)
Khi có thay đổi logic ảnh hưởng đến file chạy:
- Chạy lệnh build: `pyinstaller --noconfirm coc_auto.spec`
- Kiểm tra file `dist/COC_AutoMaster.exe` được tạo thành công với mã thoát 0.

---

## 5. CHECKLIST DÀNH CHO AGENT TRƯỚC KHI TRẢ LỜI NGƯỜI DÙNG

1. [ ] Đã sửa đúng file theo bảng phân định trách nhiệm mục 2 (không sửa lan man).
2. [ ] Đã tuân thủ nguyên tắc Clean Code & Best Practices mục 3 (Type hints, không magic number, không ép boolean mảng).
3. [ ] Đã chạy `python tests/test_code_quality.py` và toàn bộ test đạt trạng thái PASS.
4. [ ] Chỉ làm việc duy nhất trên repo `coc-auto-app` (không đụng tới `scripauto`).
5. [ ] Nếu có sửa đổi logic, đã build lại file thực thi `.exe` thành công.
6. [ ] Đã commit và push lên GitHub `coc-auto-app`.
