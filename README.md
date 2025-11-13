# Restaurant Crawler (Google Maps)

Thu thập 3 nhóm dữ liệu: (1) thông tin nhà hàng, (2) đánh giá, (3) ảnh menu. Các file đầu ra nối tiếp nhau: thông tin → dùng để lấy đánh giá & ảnh.

## 1. Cài đặt
```bash
pip install -r requirements.txt
```

## 2. Cấu hình (`restaurant_crawler/config.py`)
- `DISTRICTS`: Danh sách quận (mỗi quận sẽ tạo nhiều truy vấn dựa trên `SEARCH_QUERY`).
- `SEARCH_QUERY`: Chuỗi tìm kiếm nền (ví dụ: "nhà hàng quận").
- `WAIT_TIME`: Thời gian chờ cho thao tác load & scroll (mặc định 40s, tăng nếu bị timeout).
- `RESTAURANTS_OUTPUT`: Tên file Excel lưu thông tin nhà hàng (mặc định `restaurants.xlsx`).
- `HEADLESS`: (nếu có) Bật/tắt chế độ không mở UI trình duyệt.

## 3. Kiến trúc & Luồng dữ liệu
```
 ┌────────────────┐      ┌────────────────┐      ┌──────────────────────┐
 │RestaurantCrawler│ ---> │restaurants.xlsx│ ---> │ReviewCrawler / Menu  │
 └────────────────┘      └────────────────┘      │ImageCrawler           │
																									 └─────────┬──────────┘
																														 │
																						┌─────────────────┴────────────────┐
																						│reviews.xlsx   menu_images_output/│
																						└──────────────────────────────────┘
```
Mỗi bước phụ thuộc đầu ra của bước trước. Không chạy song song review & menu nếu chưa có `restaurants.xlsx`.

## 4. Quy trình chi tiết từng crawler

### 4.1 RestaurantCrawler
Mục tiêu: Lấy danh sách nhà hàng cơ bản.
Luồng:
```
For mỗi quận trong DISTRICTS:
	Tạo query từ SEARCH_QUERY + tên quận
	Mở Google Maps
	Scroll danh sách kết quả (nhiều lần)
	Với mỗi item hiển thị:
		Mở chi tiết (panel bên trái / popup)
		Trích xuất: tên, địa chỉ, rating, số đánh giá, loại hình, điện thoại, website, URL Maps
	Ghi tạm vào bộ nhớ
Làm sạch & loại trùng (theo tên + địa chỉ hoặc URL)
Xuất ra Excel: restaurants.xlsx
```
Chạy:
```bash
python restaurant_crawler/restaurant_crawler.py
```
Kết quả: `restaurants.xlsx`.

ASCII sơ đồ:
```
DISTRICTS -> Query Builder -> Browser -> Scroll/Load -> Parse Cards -> Deduplicate -> Write Excel
```

### 4.2 ReviewCrawler
Mục tiêu: Thu thập đánh giá chi tiết cho từng nhà hàng.
Luồng:
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

ASCII sơ đồ:
```
restaurants.xlsx -> Iterate Rows -> Open Place -> Open Reviews -> Scroll -> Extract Blocks -> Write reviews.xlsx
```

### 4.3 MenuImageCrawler
Mục tiêu: Tải ảnh menu & ảnh nổi bật.
Luồng:
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

ASCII sơ đồ:
```
restaurants.xlsx -> Iterate -> Open Place -> Photos Tab -> Filter Menu/Highlight -> Download -> Save Folder
```

## 5. Ví dụ chạy hàng loạt
```bash
python restaurant_crawler/restaurant_crawler.py
python restaurant_crawler/review_crawler.py
python restaurant_crawler/menu_image_crawler.py
```
Hoặc dừng sau bước 1 nếu chỉ cần danh sách.

## 6. Tối ưu & Khuyến nghị
- Tăng `WAIT_TIME` nếu bị thiếu dữ liệu hoặc lỗi timeout.
- Thêm backoff (sleep) giữa từng nhà hàng khi crawl review & ảnh.
- Giới hạn số review nếu không cần toàn bộ (ví dụ dùng counter & break).
- Sanitized tên thư mục để tránh lỗi ký tự đặc biệt.

## 7. Lưu ý môi trường
- Cần Edge hoặc Chrome (selenium driver tương ứng). Đảm bảo phiên bản driver khớp bản browser.
- Không mở nhiều phiên đồng thời để tránh bị rate limit.
- Kiểm tra log/stack trace khi lỗi phần tử (element not found) — thường do layout thay đổi.

## 8. Tóm tắt output
- `restaurants.xlsx`: Danh sách nhà hàng & meta cơ bản.
- `reviews.xlsx`: Tập hợp đánh giá chi tiết.
- `menu_images_output/`: Cây thư mục ảnh theo từng nhà hàng.

