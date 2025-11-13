import pandas as pd
import time
import os
import sys
from pathlib import Path
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Import config để lấy danh sách quận
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'restaurant_crawler'))
import config
DISTRICTS = config.DISTRICTS

def setup_driver():
    """
    Setup Chrome driver với options phù hợp
    """
    chrome_options = Options()
    # chrome_options.add_argument('--headless')  # Tắt headless để debug
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Chrome(options=chrome_options)
    return driver

def get_coordinates_from_google_maps_link(driver, url):
    """
    Lấy tọa độ (latitude, longitude) chính xác nhất từ link Google Maps
    - Hỗ trợ cả link rút gọn (maps.app.goo.gl)
    - Ưu tiên lấy tọa độ marker (!3d...!4d...), fallback sang viewport (@lat,lng)
    """
    try:
        driver.get(url)
        time.sleep(5)  # chờ load trang

        # Lấy URL sau khi redirect (nếu là link rút gọn)
        current = driver.current_url

        # Đợi cho đến khi URL ổn định
        for _ in range(10):
            time.sleep(1)
            new_url = driver.current_url
            if new_url != current:
                current = new_url
            else:
                break

        # Ưu tiên tìm tọa độ marker thật (!3d...!4d...)
        match = re.search(r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)', current)
        if match:
            lat = float(match.group(1))
            lng = float(match.group(2))
            return lat, lng

        # Fallback: nếu không có !3d...!4d..., tìm @lat,lng
        match = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', current)
        if match:
            lat = float(match.group(1))
            lng = float(match.group(2))
            return lat, lng

        # Nếu vẫn không tìm thấy, thử click vào tiêu đề để Maps load marker
        try:
            title = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "h1.DUwDvf"))
            )
            title.click()
            time.sleep(3)
            current = driver.current_url

            match = re.search(r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)', current)
            if match:
                return float(match.group(1)), float(match.group(2))
        except:
            pass

        print("⚠️ Không tìm thấy tọa độ trong URL:", current)
        return None, None

    except Exception as e:
        print(f"❌ Lỗi khi lấy tọa độ: {e}")
        return None, None


def process_excel_file(driver, file_path, output_folder):
    """
    Xử lý một file Excel và lấy tọa độ
    """
    try:
        output_file = os.path.join(output_folder, os.path.basename(file_path))
        
        # Kiểm tra xem file đã được xử lý chưa
        if os.path.exists(output_file):
            print(f"\n⏭️  Bỏ qua (đã xử lý): {os.path.basename(file_path)}")
            return True
        
        print(f"\nĐang xử lý file: {file_path}")
        
        # Đọc file Excel
        df = pd.read_excel(file_path)
        
        # Thêm cột Latitude và Longitude
        df['Latitude'] = None
        df['Longitude'] = None
        
        # Lấy tọa độ cho từng nhà hàng
        for index, row in df.iterrows():
            if pd.notna(row['Google Maps Link']):
                print(f"  [{index+1}/{len(df)}] Đang lấy tọa độ cho: {row['Name'][:50]}")
                
                lat, lng = get_coordinates_from_google_maps_link(driver, row['Google Maps Link'])
                
                if lat and lng:
                    df.at[index, 'Latitude'] = lat
                    df.at[index, 'Longitude'] = lng
                    print(f"    ✓ Đã lưu: {lat}, {lng}")
                else:
                    print(f"    ✗ Không lấy được tọa độ")
                
                # Delay để tránh bị block
                time.sleep(2)
        
        # Lưu kết quả
        df.to_excel(output_file, index=False)
        print(f"✓ Đã lưu: {output_file}")
        
        # Thống kê
        total = len(df)
        success = df['Latitude'].notna().sum()
        print(f"Thống kê: {success}/{total} nhà hàng có tọa độ ({success/total*100:.1f}%)")
        
        return True
        
    except Exception as e:
        print(f"Lỗi khi xử lý file {file_path}: {e}")
        return False

def main():
    # Đường dẫn folder
    restaurant_folder = "d:/language/Work/Crawl/Restaurant"
    output_folder = "d:/language/Work/Crawl/toạ độ"
    
    # Tạo folder output nếu chưa có
    Path(output_folder).mkdir(exist_ok=True)
    
    # Lấy tất cả file Excel
    all_excel_files = [f for f in os.listdir(restaurant_folder) if f.endswith('.xlsx')]
    
    # Lọc file theo quận trong config.py
    excel_files = []
    for file_name in all_excel_files:
        # Kiểm tra xem file có chứa tên quận nào trong DISTRICTS không
        for district in DISTRICTS:
            # Tạo pattern từ tên quận (vd: "Quận 7" -> "quận_7")
            district_pattern = district.lower().replace(' ', '_')   
            if district_pattern in file_name.lower():
                excel_files.append(file_name)
                break
    
    if not excel_files:
        print(f"⚠️ Không tìm thấy file Excel nào cho các quận được chọn trong config.py")
        print(f"Các quận trong config: {', '.join(DISTRICTS)}")
        print(f"Các file có sẵn: {', '.join(all_excel_files)}")
        return
    
    print(f"📍 Khu vực được chọn trong config.py: {', '.join(DISTRICTS)}")
    print(f"📁 Tìm thấy {len(excel_files)} file Excel phù hợp:")
    for f in excel_files:
        print(f"   - {f}")
    print("="*60)
    
    # Setup driver
    print("Đang khởi tạo Chrome driver...")
    driver = setup_driver()
    
    try:
        # Xử lý từng file
        success_count = 0
        for file_name in excel_files:
            file_path = os.path.join(restaurant_folder, file_name)
            if process_excel_file(driver, file_path, output_folder):
                success_count += 1
            print("-"*60)
        
        print(f"\n{'='*60}")
        print(f"Hoàn thành! Đã xử lý {success_count}/{len(excel_files)} file thành công")
        print(f"Kết quả được lưu trong folder: {output_folder}")
    
    finally:
        # Đóng driver
        driver.quit()
        print("Đã đóng Chrome driver")

if __name__ == "__main__":
    main()
