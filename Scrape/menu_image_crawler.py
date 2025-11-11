import pandas as pd
import time, random, os, re, logging, requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import urlparse, parse_qs, urlencode
from selenium.webdriver.common.action_chains import ActionChains

# ====================================
# CẤU HÌNH CHỐNG BAN
# ====================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Danh sách User-Agent để rotate
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
]

# Cấu hình đơn giản
REQUEST_DELAY_MIN = 2  # giây
REQUEST_DELAY_MAX = 4  # giây
RETRY_MAX_ATTEMPTS = 2
RETRY_DELAY_BASE = 3  # giây

def get_chrome_options():
    """
    Tạo Chrome options với cấu hình chống phát hiện bot
    """
    chrome_options = Options()
    
    # Chọn random User-Agent
    user_agent = random.choice(USER_AGENTS)
    chrome_options.add_argument(f"user-agent={user_agent}")
    
    # Các tùy chọn chống phát hiện
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Tắt các tính năng không cần thiết
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    
    # Ngôn ngữ
    chrome_options.add_argument("--lang=en")
    chrome_options.add_argument("--disable-features=Translate")
    chrome_options.add_experimental_option('prefs', {
        'intl.accept_languages': 'en-US,en',
        'profile.default_content_setting_values.notifications': 2,
        'profile.managed_default_content_settings.images': 1
    })
    
    return chrome_options

def setup_driver():
    """
    Khởi tạo driver với script chống phát hiện
    """
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), 
        options=get_chrome_options()
    )
    
    # Thêm script để ẩn dấu hiệu webdriver
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': '''
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Giả lập plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // Giả lập languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            
            // Chrome object
            window.chrome = {
                runtime: {}
            };
            
            // Permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        '''
    })
    
    return driver

def smart_delay(min_sec=REQUEST_DELAY_MIN, max_sec=REQUEST_DELAY_MAX):
    """Delay random"""
    time.sleep(random.uniform(min_sec, max_sec))

def human_like_click(driver, element):
    """Click đơn giản"""
    try:
        driver.execute_script("arguments[0].click();", element)
        return True
    except:
        try:
            element.click()
            return True
        except:
            return False

def retry_on_failure(func, max_attempts=RETRY_MAX_ATTEMPTS, *args, **kwargs):
    """Retry đơn giản"""
    for attempt in range(max_attempts):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt < max_attempts - 1:
                time.sleep(RETRY_DELAY_BASE)
            else:
                raise


# ====================================
# HÀM ÉP NGÔN NGỮ GỐC
# ====================================
def force_original_language_url(base_url):
    parsed = urlparse(base_url)
    query = parse_qs(parsed.query)
    query.pop('hl', None)
    query['gl'] = ['vn']
    query['authuser'] = ['0']
    new_query = urlencode(query, doseq=True)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{new_query}"


# ====================================
# HÀM LÀM SẠCH TÊN FILE
# ====================================
def clean_filename(name):
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '')
    return name.replace(' ', '_').strip()[:100]


# ====================================
# HÀM TẢI ẢNH TỪ URL
# ====================================
def download_image(url, save_path, timeout=15):
    """
    Tải ảnh từ URL và lưu vào đường dẫn với anti-ban headers
    """
    try:
        # Rotate User-Agent và thêm headers giống trình duyệt
        headers = {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.google.com/maps/',
            'Sec-Fetch-Dest': 'image',
            'Sec-Fetch-Mode': 'no-cors',
            'Sec-Fetch-Site': 'cross-site'
        }
        
        # Delay nhỏ trước khi download
        time.sleep(random.uniform(0.2, 0.5))
        
        response = requests.get(url, headers=headers, timeout=timeout, stream=True)
        response.raise_for_status()
        
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        return True
    except Exception as e:
        logging.warning(f"Lỗi tải ảnh {save_path}: {e}")
        return False


# ====================================
# HÀM TRÍCH XUẤT TÊN QUẬN TỪ TÊN NHÀ HÀNG
# ====================================
def extract_district_from_name(location_name):
    """
    Trích xuất tên quận từ tên nhà hàng
    VD: "Ẩm Thực Quê Nhà Quận 3" -> "Quận_3"
    """
    # Tìm pattern "Quận X" hoặc "District X"
    match = re.search(r'[Qq]uận\s*(\d+|[A-Z]+)', location_name, re.IGNORECASE)
    if match:
        return f"Quận_{match.group(1)}"
    
    match = re.search(r'[Dd]istrict\s*(\d+|[A-Z]+)', location_name, re.IGNORECASE)
    if match:
        return f"District_{match.group(1)}"
    
    # Mặc định nếu không tìm thấy
    return "Unknown_District"


# ====================================
# HÀM CUỘN PHẦN MENU
# ====================================
def scroll_menu_section(driver):
    """Cuộn đơn giản để load ảnh"""
    try:
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.5)
        for i in range(5):
            driver.execute_script("window.scrollBy(0, 800);")
            time.sleep(0.5)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)
        logging.info("✓ Đã cuộn xong để load ảnh menu.")
    except Exception as e:
        logging.warning(f"Lỗi khi cuộn: {e}")

def extract_full_menu_images(driver, location_name, restaurant_folder, timeout_per_image=15):
    """
    Trích xuất ảnh menu và lưu vào thư mục nhà hàng (VERSION ĐƠN GIẢN - KHÔNG LẤY NGÀY)
    """
    images_downloaded = 0
    start_time = time.time()
    
    try:
        logging.info("Đang tìm ảnh menu...")
        time.sleep(2)
        
        # Tìm ảnh - selector đơn giản
        img_elements = []
        selectors = [
            "//button[@aria-label and .//img[contains(@src,'googleusercontent.com')]]",
            "//button[contains(@jsaction,'pane.heroHeaderImage.click')]//img",
            "//img[contains(@src,'googleusercontent.com') and @loading='lazy']",
            "//button[@data-photo-index]//img"
        ]
        
        for selector in selectors:
            try:
                img_elements = driver.find_elements(By.XPATH, selector)
                if img_elements:
                    logging.info(f"✓ Tìm thấy {len(img_elements)} ảnh")
                    break
            except:
                continue
        
        if not img_elements:
            logging.warning("❌ Không tìm thấy ảnh menu nào!")
            return 0
        
        max_images = min(len(img_elements), 50)
        logging.info(f"Bắt đầu tải {max_images} ảnh vào: {restaurant_folder}")
        
        for index in range(max_images):
            img_start_time = time.time()
            
            if time.time() - img_start_time > timeout_per_image:
                logging.warning(f"⏱ Timeout ảnh {index+1}, bỏ qua")
                continue
                
            try:
                smart_delay(0.5, 1)
                
                # Tìm lại element
                try:
                    img_elements = WebDriverWait(driver, 3).until(
                        lambda d: d.find_elements(By.XPATH, selectors[0])
                    )
                    if not img_elements:
                        img_elements = driver.find_elements(By.XPATH, selectors[2])
                except:
                    logging.warning(f"Không tìm lại được elements ở ảnh {index+1}")
                    break
                
                if index >= len(img_elements):
                    logging.info(f"Hết ảnh tại index {index}")
                    break
                    
                img = img_elements[index]
                
                # Lấy link trực tiếp từ thumbnail
                try:
                    thumb_img = img.find_element(By.XPATH, ".//img") if img.tag_name != "img" else img
                    thumb_src = thumb_img.get_attribute("src")
                    
                    if thumb_src and "googleusercontent.com" in thumb_src:
                        base_url = thumb_src.split("=")[0]
                        full_src = base_url + "=w4096-h4096-p-k-no-nu"
                        
                        # Đặt tên file đơn giản: 001.jpg, 002.jpg, ...
                        image_filename = f"{index+1:03d}.jpg"
                        image_path = os.path.join(restaurant_folder, image_filename)
                        
                        # Download
                        if retry_on_failure(download_image, RETRY_MAX_ATTEMPTS, full_src, image_path):
                            images_downloaded += 1
                            logging.info(f"✓ Tải ảnh {index+1}/{max_images}: {image_filename} ({round(time.time()-img_start_time,1)}s)")
                        else:
                            logging.warning(f"⚠ Không tải được ảnh {index+1}")
                        
                        continue
                        
                except Exception as e:
                    logging.debug(f"Không lấy được link trực tiếp ảnh {index+1}: {e}")

            except Exception as e:
                logging.warning(f"⚠ Lỗi ảnh {index+1}: {str(e)[:80]}")
                continue

        logging.info(f"✓✓✓ Hoàn thành: Đã tải {images_downloaded}/{max_images} ảnh trong {round(time.time()-start_time,1)} giây.")
        
    except Exception as e:
        logging.error(f"❌ Lỗi extract_full_menu_images: {e}")
    
    return images_downloaded

# ====================================
# MAIN SCRIPT
# ====================================
driver = None

try:
    # Setup driver với cấu hình chống phát hiện
    driver = setup_driver()

    excel_path = r"D:\language\Work\Crawl\Restaurant\restaurants_quận_3.xlsx"
    df_locations = pd.read_excel(excel_path)

    output_dir = r"D:\language\Work\Crawl\menu_images_output"
    os.makedirs(output_dir, exist_ok=True)
    
    # Timeout tổng thể cho mỗi nhà hàng (phút)
    RESTAURANT_TIMEOUT = 5 * 60  # 5 phút

    for index, row in df_locations.iterrows():
        restaurant_start_time = time.time()
        location_name = row["Name"]
        url = force_original_language_url(row["Google Maps Link"])
        safe_name = clean_filename(location_name)
        
        # Trích xuất tên quận từ tên nhà hàng
        district_name = extract_district_from_name(location_name)
        
        # Tạo cấu trúc thư mục: menu_images_output/Quận_X/Tên_Nhà_Hàng/
        district_folder = os.path.join(output_dir, district_name)
        restaurant_folder = os.path.join(district_folder, safe_name)
        os.makedirs(restaurant_folder, exist_ok=True)
        
        logging.info(f"\n{'='*60}")
        logging.info(f"[{index+1}/{len(df_locations)}] Xử lý: {location_name}")
        logging.info(f"Quận: {district_name}")
        logging.info(f"Thư mục: {restaurant_folder}")
        logging.info(f"{'='*60}")

        try:
            # Load trang
            driver.get(url)
            smart_delay(2, 3)

            # Mở tab Menu - thử cả tiếng Anh và tiếng Việt
            menu_opened = False
            menu_selectors = [
                "//button[@role='tab' and contains(., 'Menu')]",
                "//button[@role='tab' and contains(., 'Thực đơn')]",
                "//button[contains(@aria-label, 'Menu')]",
                "//button[.//div[contains(text(),'Menu')]]"
            ]
            
            for selector in menu_selectors:
                try:
                    menu_tab = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    
                    # Click với human-like behavior
                    human_like_click(driver, menu_tab)
                    logging.info(f"✓ Đã mở tab Menu")
                    menu_opened = True
                    smart_delay(2, 3)
                    break
                except:
                    continue
            
            if not menu_opened:
                logging.warning("❌ Không tìm thấy tab Menu, bỏ qua.")
                # Tạo file note trong folder
                note_file = os.path.join(restaurant_folder, "no_menu.txt")
                with open(note_file, 'w', encoding='utf-8') as f:
                    f.write(f"Không tìm thấy tab Menu cho {location_name}\n")
                    f.write(f"URL: {url}\n")
                continue

            scroll_menu_section(driver)
            
            # Kiểm tra timeout trước khi extract
            if time.time() - restaurant_start_time > RESTAURANT_TIMEOUT:
                logging.warning(f"⏱ Timeout cho {location_name}, bỏ qua")
                continue
                
            images_count = extract_full_menu_images(driver, location_name, restaurant_folder, timeout_per_image=15)

            if images_count > 0:
                logging.info(f"✓✓✓ Đã lưu {images_count} ảnh vào: {restaurant_folder}")
            else:
                logging.warning(f"⚠ Không tải được ảnh menu nào cho {location_name}")
                # Tạo file note
                note_file = os.path.join(restaurant_folder, "no_images.txt")
                with open(note_file, 'w', encoding='utf-8') as f:
                    f.write(f"Không tìm thấy/tải được ảnh menu cho {location_name}\n")
                    f.write(f"URL: {url}\n")
            
            # Thời gian xử lý nhà hàng
            elapsed = round(time.time() - restaurant_start_time, 1)
            logging.info(f"⏱ Hoàn thành {location_name} trong {elapsed}s")

        except KeyboardInterrupt:
            logging.warning("\n\n⚠⚠⚠ Người dùng dừng chương trình (Ctrl+C)")
            raise
        except Exception as e:
            logging.error(f"❌ Lỗi khi xử lý {location_name}: {e}")
            try:
                # Kiểm tra driver còn hoạt động không
                try:
                    driver.current_url
                    driver.save_screenshot(os.path.join(output_dir, f"error_{safe_name}.png"))
                except:
                    logging.warning("⚠ Driver bị crash, khởi động lại...")
                    try:
                        driver.quit()
                    except:
                        pass
                    driver = setup_driver()
                    smart_delay(2, 3)
            except:
                pass
            continue

        # Delay ngẫu nhiên giữa các nhà hàng (quan trọng cho chống ban!)
        smart_delay(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)

except KeyboardInterrupt:
    logging.warning("\n\n⚠⚠⚠ Chương trình bị dừng bởi người dùng!")
except Exception as e:
    logging.error(f"❌ Lỗi nghiêm trọng: {e}")
    import traceback
    traceback.print_exc()
finally:
    try:
        if driver:
            driver.quit()
        logging.info("\n✓ Đã đóng trình duyệt.")
    except:
        pass
