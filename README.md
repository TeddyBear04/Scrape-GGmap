# Restaurant Crawler

Thu thập thông tin nhà hàng, đánh giá và hình ảnh menu từ Google Maps.

## Cài đặt

```bash
pip install -r requirements.txt
```

## Cấu hình

Chỉnh sửa file `config.py`:
- `DISTRICTS`: Danh sách quận cần crawl
- `WAIT_TIME`: Thời gian chờ load (mặc định 40s)
- `RESTAURANTS_OUTPUT`: Tên file output (mặc định `restaurants.xlsx`)

## Sử dụng

### 1. Thu thập thông tin nhà hàng
```python
from restaurant_crawler import RestaurantCrawler
crawler = RestaurantCrawler()
crawler.run()
```
Output: `restaurants.xlsx` (tên, địa chỉ, rating, số điện thoại, website, URL...)
* Nếu muốn thay đổi nơi crawl thì vào file config thay đổi trong phần "DISTRICTS"

### 2. Thu thập đánh giá
```python
from review_crawler import ReviewCrawler
crawler = ReviewCrawler('restaurants.xlsx')
crawler.run()
```
Output: `reviews.xlsx` (tên nhà hàng, người đánh giá, số sao, nội dung, ngày tháng...)
* Hiện tại ngôn ngữ của review đang được crawl theo ngôn ngữ của máy chứ chưa phải ngôn ngữ gốc

### 3. Tải hình ảnh menu
```python
from menu_image_crawler import MenuImageCrawler
crawler = MenuImageCrawler('restaurants.xlsx', 'menu_images_output')
crawler.run()
```
Output: Thư mục `menu_images_output/{restaurant_name}/`
* Hiện ảnh tải về bao gồm phần menu và phần highlight của nhà hàng 
## Lưu ý

- Cần Microsoft Edge hoặc Chrome browser
- Không crawl quá nhanh để tránh bị block
- Kiểm tra log nếu gặp lỗi
- Tăng `WAIT_TIME` nếu gặp TimeoutException
