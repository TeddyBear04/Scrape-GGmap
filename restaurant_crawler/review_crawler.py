import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import random
import logging
import re
import os
from urllib.parse import urlparse, parse_qs, urlencode  # THÊM DÒNG NÀY

# Cấu hình logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ================================
# CHROME OPTIONS: TẮT DỊCH + ÉP GỐC
# ================================
chrome_options = Options()
chrome_options.add_argument("--disable-notifications")
chrome_options.add_argument("--disable-extensions")
chrome_options.add_argument("--start-maximized")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--lang=en")  # UI tiếng Anh, không ảnh hưởng review
chrome_options.add_argument('--disable-features=Translate')  # TẮT DỊCH TỰ ĐỘNG
chrome_options.add_experimental_option('prefs', {
    'intl.accept_languages': 'en-US,en',
    'translate': {'enabled': False}
})
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")
chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])

# ================================
# 1. Hàm ép URL giữ ngôn ngữ gốc
# ================================
def force_original_language_url(base_url):
    parsed = urlparse(base_url)
    query = parse_qs(parsed.query)
    query.pop('hl', None)           # Xóa hl= nếu có
    query['gl'] = ['vn']            # Ép quốc gia Việt Nam
    query['authuser'] = ['0']       # Giữ nội dung gốc
    new_query = urlencode(query, doseq=True)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{new_query}"

# ================================
# 2. Hàm cuộn + nhấn "Thêm"/"More"
# ================================
def scroll_reviews(driver):
    try:
        scrollable_div = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'm6QErb') and contains(@class, 'DxyBCb')]"))
        )
        max_scroll_attempts = 50
        attempt = 0
        last_review_count = 0

        while attempt < max_scroll_attempts:
            driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scrollable_div)
            time.sleep(random.uniform(1.2, 2.0))
            click_add_buttons(driver)

            review_count = driver.execute_script("return document.querySelectorAll('.jftiEf').length;")
            logging.info(f"Đã tải {review_count} đánh giá.")

            if review_count == last_review_count:
                driver.execute_script("arguments[0].scrollTop += 1000", scrollable_div)
                time.sleep(1.5)
                new_count = driver.execute_script("return document.querySelectorAll('.jftiEf').length;")
                if new_count == review_count:
                    break
            last_review_count = review_count
            attempt += 1

        return review_count
    except Exception as e:
        logging.error(f"Lỗi cuộn: {str(e)}")
        return 0

# ================================
# 3. Hàm nhấn nút "Thêm"/"More"
# ================================
def click_add_buttons(driver):
    try:
        buttons = driver.find_elements(By.XPATH, "//button[contains(text(), 'Thêm') or contains(text(), 'More')]")
        clicked = 0
        for button in buttons:
            try:
                if button.is_displayed() and button.is_enabled():
                    driver.execute_script("arguments[0].click();", button)
                    clicked += 1
                    time.sleep(random.uniform(0.2, 0.5))
            except:
                continue
        if clicked > 0:
            logging.info(f"Đã nhấn {clicked} nút 'Thêm'/'More'.")
    except:
        pass

# ================================
# 4. Hàm làm sạch tên file
# ================================
def clean_filename(name):
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '')
    return name.replace(' ', '_').strip()[:100]

# ================================
# 5. Hàm trích xuất review (sau khi mở hết "More")
# ================================
def extract_reviews(driver, location_name):
    reviews_data = []
    try:
        click_add_buttons(driver)
        time.sleep(1.5)
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        # Điểm trung bình
        average_rating = "N/A"
        try:
            el = soup.find('div', class_='fontDisplayLarge') or soup.find('span', class_='F7nice')
            if el:
                text = el.get_text(strip=True)
                match = re.search(r'[\d,]+\.?\d*', text)
                if match:
                    average_rating = match.group().replace(',', '.')
        except:
            pass

        # Trích xuất từng review
        for review in soup.find_all('div', class_='jftiEf'):
            try:
                name_el = review.find('div', class_='d4r55')
                reviewer = name_el.get_text(strip=True) if name_el else "N/A"

                rating_el = review.find('span', class_='kvMYJc')
                rating = "N/A"
                if rating_el and rating_el.get('aria-label'):
                    rating = rating_el['aria-label'].split()[0].replace(',', '.')
                else:
                    stars = review.find_all('img', class_='hCCjke')
                    rating = len(stars) if stars else "N/A"

                date_el = review.find('span', class_='rsqaWe')
                date = date_el.get_text(strip=True) if date_el else "N/A"

                text_el = review.find('span', class_='wiI7pd')
                text = text_el.get_text(strip=True).replace('\n', ' ').replace('\r', ' ') if text_el else "N/A"

                reviews_data.append({
                    'Người đánh giá': reviewer,
                    'Điểm số': rating,
                    'Nội dung': text,
                    'Ngày': date,
                    'Điểm số trung bình': average_rating,
                    'Nguồn': 'Google Maps',
                    'Địa điểm': location_name,
                    'Ngôn ngữ': 'gốc'
                })
            except:
                continue

        logging.info(f"Trích xuất {len(reviews_data)} review (ngôn ngữ gốc).")
        return reviews_data
    except Exception as e:
        logging.error(f"Lỗi trích xuất: {e}")
        return []

# ==================================
# 6. MAIN - LƯU EXCEL + NGÔN NGỮ GỐC
# ==================================
try:
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    logging.info("Khởi tạo WebDriver.")

    # Đọc Excel
    excel_path = r"D:\language\Work\Crawl\restaurants_quận_3.xlsx"
    df_locations = pd.read_excel(excel_path)
    logging.info(f"Đọc file: {excel_path}")

    required_columns = ["Name", "Google Maps Link"]
    if not all(col in df_locations.columns for col in required_columns):
        logging.error("Thiếu cột bắt buộc!")
        exit(1)

    # Thư mục lưu Excel
    output_dir = r"D:\language\Work\Crawl\reviews_output"
    os.makedirs(output_dir, exist_ok=True)
    logging.info(f"Lưu Excel tại: {output_dir}")

    for index, row in df_locations.iterrows():
        location_name = row["Name"]
        url = row["Google Maps Link"]
        safe_name = clean_filename(location_name)
        logging.info(f"[{index+1}] Xử lý: {location_name}")

        all_reviews = []

        try:
            # ÉP NGÔN NGỮ GỐC TRƯỚC KHI MỞ
            url = force_original_language_url(url)
            logging.info(f"URL gốc (không dịch): {url}")
            driver.get(url)
            time.sleep(3)

            # Mở tab Đánh giá
            try:
                tab = WebDriverWait(driver, 30).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Đánh giá') or contains(., 'Reviews')]"))
                )
                driver.execute_script("arguments[0].click();", tab)
                logging.info("Đã mở tab Đánh giá.")
                time.sleep(2)
            except Exception as e:
                logging.error(f"Không mở tab Đánh giá: {e}")
                driver.save_screenshot(os.path.join(output_dir, f"error_tab_{safe_name}.png"))
                continue

            # Cuộn + mở "More"
            scroll_reviews(driver)
            time.sleep(1)

            # Trích xuất
            reviews = extract_reviews(driver, location_name)
            all_reviews.extend(reviews)

        except Exception as e:
            logging.error(f"Lỗi xử lý {location_name}: {e}")
            driver.save_screenshot(os.path.join(output_dir, f"error_{safe_name}.png"))
            continue

        # Loại trùng
        unique = []
        seen = set()
        for r in all_reviews:
            key = (r['Người đánh giá'], r['Nội dung'], r['Ngày'])
            if key not in seen:
                seen.add(key)
                unique.append(r)

        # LƯU VÀO FILE EXCEL (.XLSX)
        output_file = os.path.join(output_dir, f"{safe_name}_reviews.xlsx")
        if unique:
            pd.DataFrame(unique).to_excel(output_file, index=False, engine='openpyxl')
            logging.info(f"ĐÃ LƯU: {len(unique)} review → {output_file}")
        else:
            pd.DataFrame(columns=[
                'Người đánh giá', 'Điểm số', 'Nội dung', 'Ngày',
                'Điểm số trung bình', 'Nguồn', 'Địa điểm', 'Ngôn ngữ'
            ]).to_excel(output_file, index=False, engine='openpyxl')
            logging.warning(f"Không có review → tạo file rỗng: {output_file}")

        if len(unique) < 100:
            logging.warning(f"Chỉ lấy được {len(unique)} review.")

        time.sleep(random.uniform(3, 6))  # Nghỉ giữa các địa điểm

except Exception as e:
    logging.error(f"Lỗi nghiêm trọng: {e}")
finally:
    driver.quit()
    logging.info("ĐÃ ĐÓNG BROWSER.")