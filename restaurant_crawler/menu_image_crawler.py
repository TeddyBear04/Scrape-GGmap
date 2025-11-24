import os
import time
import requests
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# ----------------------------------------
# TẢI ẢNH TỪ URL
# ----------------------------------------
def download_image(url, save_path):
    try:
        data = requests.get(url, timeout=10).content
        with open(save_path, "wb") as f:
            f.write(data)
        return True
    except:
        return False

# ----------------------------------------
# SETUP SELENIUM
# ----------------------------------------
def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-infobars")
    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )

# ----------------------------------------
# CRAWL ẢNH MENU GOOGLE MAPS
# ----------------------------------------
def crawl_menu_images(map_url, restaurant_name):
    driver = setup_driver()
    driver.get(map_url)
    wait = WebDriverWait(driver, 15)

    # 1. Click tab MENU / THỰC ĐƠN
    try:
        menu_tab = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Menu') or contains(., 'Thực đơn')]"))
        )
        menu_tab.click()
        time.sleep(2)
    except:
        print(f"❌ {restaurant_name}: Không tìm thấy tab Menu/Thực đơn.")
        driver.quit()
        return

    # 2. Tìm SECTION chứa ảnh MENU
    menu_section = None

    # Cách 1: aria-label
    try:
        menu_section = wait.until(
            EC.presence_of_element_located((By.XPATH, "//div[@aria-label='Menu']"))
        )
    except:
        pass

    # Cách 2: role=region + aria-label chứa 'menu'
    if menu_section is None:
        try:
            menu_section = wait.until(
                EC.presence_of_element_located((By.XPATH, "//div[@role='region' and contains(@aria-label, 'Menu')]"))
            )
        except:
            pass

    # Cách 3: fallback container chứa ảnh
    if menu_section is None:
        try:
            menu_section = wait.until(
                EC.presence_of_element_located((By.XPATH, "//div[contains(@class,'m6QEr')]//img/ancestor::div[contains(@class,'m6QEr')]"))
            )
        except:
            pass

    if menu_section is None:
        print(f"❌ {restaurant_name}: Không tìm thấy section ảnh menu.")
        driver.quit()
        return

    # 3. SCROLL NGANG ĐỂ LOAD HẾT ẢNH
    for _ in range(25):
        try:
            driver.execute_script("arguments[0].scrollLeft += 800;", menu_section)
            time.sleep(0.6)
        except:
            break
    time.sleep(1)
    driver.execute_script("arguments[0].scrollLeft = 0;", menu_section)

    # 4. LẤY CHỈ ẢNH MENU CHUẨN (tránh highlight/review)
    try:
        menu_container = menu_section.find_element(By.XPATH, ".//div[contains(@aria-label, 'menu') or contains(@data-item-id, 'menu')]//following-sibling::div//div[@role='list']")
    except:
        menu_container = menu_section

    image_elements = menu_container.find_elements(By.CSS_SELECTOR, "img")

    image_urls = []
    for img in image_elements:
        src = img.get_attribute("src")
        if src and "lh3.googleusercontent.com" in src and ("=w" in src or "=h" in src):
            clean_src = src.split("?")[0].rsplit("=", 1)[0] + "=w4096-h4096"
            image_urls.append(clean_src)

    image_urls = list(dict.fromkeys(image_urls))    

    # 5. TẠO FOLDER LƯU ẢNH
    save_folder = f"menu_images/{restaurant_name}"
    os.makedirs(save_folder, exist_ok=True)

    # 6. TẢI ẢNH VỀ
    for idx, url in enumerate(image_urls):
        filename = os.path.join(save_folder, f"menu_{idx+1}.jpg")
        if download_image(url, filename):
            print(f"✔ Saved: {filename}")
        else:
            print(f"✘ Failed: {url}")

    driver.quit()
    print(f"🎯 Hoàn thành: {restaurant_name}")

# ----------------------------------------
# CHẠY CHÍNH: ĐỌC FILE EXCEL
# ----------------------------------------
if __name__ == "__main__":
    excel_path = r"D:\language\Work\Crawl\ĐN-HA\1.xlsx"
    try:
        df = pd.read_excel(excel_path)
        print(f"📊 Đọc được {len(df)} nhà hàng\n")

        for idx, row in df.iterrows():
            restaurant_name = row['Name']
            map_url = row['Google Maps Link']

            if pd.isna(map_url) or not map_url:
                print(f"⚠ Bỏ qua {restaurant_name} - không có URL")
                continue

            print(f"\n{'='*60}")
            print(f"🍽️ [{idx+1}/{len(df)}] Đang crawl: {restaurant_name}")
            print(f"{'='*60}")

            try:
                crawl_menu_images(map_url, restaurant_name)
            except Exception as e:
                print(f"❌ Lỗi khi crawl {restaurant_name}: {e}")

            time.sleep(3)  # tránh bị Google chặn

        print("\n✅ Hoàn thành tất cả!")
    except Exception as e:
        print(f"❌ Lỗi đọc file: {e}")
