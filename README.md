# ✨ Restaurant Crawler (Google Maps)

Thu thập dữ liệu nhà hàng một cách tuần tự & dễ mở rộng: thông tin → đánh giá → ảnh menu. Bạn có thể dừng ở bất kỳ bước nào tùy nhu cầu.

## 1. 🚀 Cài đặt nhanh
```bash
pip install -r requirements.txt
```

## 2. 🔧 Cấu hình (`restaurant_crawler/config.py`)
- `DISTRICTS`: Danh sách quận (mỗi quận sẽ tạo nhiều truy vấn dựa trên `SEARCH_QUERY`).
- `SEARCH_QUERY`: Chuỗi tìm kiếm nền (ví dụ: "nhà hàng quận").
- `WAIT_TIME`: Thời gian chờ cho thao tác load & scroll (mặc định 40s, tăng nếu bị timeout).
- `RESTAURANTS_OUTPUT`: Tên file Excel lưu thông tin nhà hàng (mặc định `restaurants.xlsx`).
- `HEADLESS`: (nếu có) Bật/tắt chế độ không mở UI trình duyệt.

## 3. 🧠 Kiến trúc & Luồng dữ liệu
```
 ┌─────────────────┐       ┌────────────────┐      ┌──────────────────────┐
 │RestaurantCrawler│ --->  │restaurants.xlsx│ ---> │ReviewCrawler / Menu  │
 └─────────────────┘       └────────────────┘      │ImageCrawler          │
                                                   └──────────┬───────────┘
                                                              │
                                            ┌─────────────────┴────────────────┐
                                            │reviews.xlsx   menu_images_output/│
                                            └──────────────────────────────────┘
```
Mỗi bước phụ thuộc đầu ra của bước trước. Không chạy song song review & menu nếu chưa có `restaurants.xlsx`.

## 4. 🔍 Quy trình chi tiết từng crawler

### 4.1 RestaurantCrawler
Mục tiêu: Lấy danh sách nhà hàng cơ bản (nền tảng cho các bước sau).
Luồng tóm tắt:
```
For mỗi quận trong DISTRICTS:
	Tạo query từ SEARCH_QUERY + tên quận
	Mở Google Maps
	Scroll danh sách kết quả (nhiều lần)
	Với mỗi item hiển thị:
		Mở chi tiết (panel bên trái / popup)
		Trích xuất: Name	Address	Phone	Rating	Review Count	Google Maps Link
	Ghi tạm vào bộ nhớ
Làm sạch & loại trùng (theo tên + địa chỉ hoặc URL)
Xuất ra Excel: restaurants.xlsx
```
Chạy:
```bash
python restaurant_crawler/restaurant_crawler.py
```
Kết quả: `restaurants.xlsx`.


### 4.2 ReviewCrawler
Mục tiêu: Thu thập đánh giá (giúp phân tích mức độ hài lòng & xu hướng).
Luồng tóm tắt:
```
Đọc restaurants.xlsx
For mỗi nhà hàng:
	Mở URL Google Maps
	Mở tab Reviews / nhấn nút xem thêm
	Lặp scroll (tải thêm) cho tới khi đủ hoặc hết
	Parse từng block: user, avatar (nếu cần), rating, nội dung, thời gian, số lượt like
	Chuẩn hoá thời gian (nếu lấy được dạng chuỗi tương đối)
Ghi toàn bộ vào reviews.xlsx
```
Chạy:
```bash
python restaurant_crawler/review_crawler.py
```
Kết quả: `reviews.xlsx`.
Lưu ý: Ngôn ngữ nội dung phụ thuộc ngôn ngữ trình duyệt/máy.


### 4.3 Menu Image Crawler
Mục tiêu: Tải ảnh menu & ảnh nổi bật (phục vụ gợi ý món / phân tích thị giác / classification).
Luồng tóm tắt:
```
Đọc restaurants.xlsx
For mỗi nhà hàng:
	Mở URL Maps
	Mở tab Photos / Menu (nếu có)
	Lọc ảnh (menu / highlight)
	Download tuần tự, delay ngắn giữa mỗi ảnh
	Lưu vào menu_images_output/{tên_nhà_hàng_sanitized}/
```
Chạy:
```bash
python restaurant_crawler/menu_image_crawler.py
```
Kết quả: Thư mục `menu_images_output/`.


## 5. ⚡ Quick Start (chạy tuần tự)
```bash
python restaurant_crawler/restaurant_crawler.py
python restaurant_crawler/review_crawler.py
python restaurant_crawler/menu_image_crawler.py
```
Hoặc dừng sau bước 1 nếu chỉ cần danh sách.

## 6. 💡 Mẹo tối ưu
- Tăng `WAIT_TIME` nếu bị thiếu dữ liệu hoặc lỗi timeout.
- Thêm backoff (sleep) giữa từng nhà hàng khi crawl review & ảnh.
- Giới hạn số review nếu không cần toàn bộ (ví dụ dùng counter & break).
- Sanitized tên thư mục để tránh lỗi ký tự đặc biệt.
 - Có thể bật `HEADLESS` để giảm tài nguyên.
 - Ghi log thời gian mỗi vòng để phát hiện điểm nghẽn.

## 7. 🖥️ Môi trường & độ tin cậy
- Cần Edge hoặc Chrome (selenium driver tương ứng). Đảm bảo phiên bản driver khớp bản browser.
- Không mở nhiều phiên đồng thời để tránh bị rate limit.
- Kiểm tra log/stack trace khi lỗi phần tử (element not found) — thường do layout thay đổi.
 - Nếu Google Maps thay đổi UI → cần cập nhật lại selectors.

## 8. 📦 Tóm tắt output
- `restaurants.xlsx`: Danh sách nhà hàng & meta cơ bản.
- `reviews.xlsx`: Tập hợp đánh giá chi tiết.
- `menu_images_output/`: Cây thư mục ảnh theo từng nhà hàng.

## 9. 🛠️ Script tự động (PowerShell ví dụ)
Tạo file `run_all.ps1` nếu muốn một lệnh duy nhất:
```powershell
Write-Host "[1/3] Crawl restaurants" -ForegroundColor Cyan
python restaurant_crawler/restaurant_crawler.py

Write-Host "[2/3] Crawl reviews" -ForegroundColor Cyan
python restaurant_crawler/review_crawler.py

Write-Host "[3/3] Download menu images" -ForegroundColor Cyan
python restaurant_crawler/menu_image_crawler.py

Write-Host "Done ✅" -ForegroundColor Green
```
Chạy:
```powershell
powershell -ExecutionPolicy Bypass -File .\run_all.ps1
```

## 10. 🔭 Hướng mở rộng
- Thêm phân tích sentiment từ `reviews.xlsx`.
- Nhận diện món ăn từ ảnh menu (CV model).
- Chuẩn hoá địa chỉ → tọa độ (geocoding) để vẽ heatmap.
- Xuất ra database thay vì Excel.




