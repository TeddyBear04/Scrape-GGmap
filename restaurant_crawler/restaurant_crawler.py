from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException, TimeoutException, StaleElementReferenceException, WebDriverException
)
from selenium.webdriver.edge.options import Options as EdgeOptions
import pandas as pd
import time, random, re, urllib.parse

# config.py cần có: RESTAURANT_NAMES, SEARCH_QUERY_NAME, WAIT_TIME=25, SCROLL_PAUSE_TIME=1.0
from config import *

class RestaurantCrawler:
    def __init__(self):
        opts = EdgeOptions()
        opts.add_argument("--start-maximized")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)

        self.driver = webdriver.Edge(options=opts)   # Selenium Manager tự lấy msedgedriver
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self.wait = WebDriverWait(self.driver, WAIT_TIME)
        self.restaurants_data = []
        self.processed_restaurants = set()  # Theo dõi các nhà hàng đã xử lý

    # ---------- helpers ----------
    def _wait_feed(self):
        return self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='feed']")))

    def _ensure_list_mode(self):
        try:
            WebDriverWait(self.driver, 2).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "h1.fontHeadlineLarge, h1.DUwDvf"))
            )
            self.driver.find_element(By.CSS_SELECTOR, 'button[aria-label*="Back"]').click()
            self._wait_feed()
        except TimeoutException:
            pass

    def _maybe_consent(self):
        try:
            btn = WebDriverWait(self.driver, 3).until(EC.element_to_be_clickable((
                By.XPATH, "//button[normalize-space()='I agree' or normalize-space()='Accept all' or "
                          "normalize-space()='Tôi đồng ý' or normalize-space()='Chấp nhận tất cả']")))
            btn.click()
            time.sleep(1)
        except Exception:
            pass

    def _get_cards(self):
        feed = self._wait_feed()
        try:
            self.driver.execute_script("arguments[0].scrollTop = 10", feed)
        except Exception:
            pass
        for sel in [
            "div[role='feed'] div[role='article']",
            "div[role='feed'] a.hfpxzc",
            "div[role='feed'] div[data-result-index]",
        ]:
            els = self.driver.find_elements(By.CSS_SELECTOR, sel)
            if els:
                return els
        return []

    def _safe_click_card(self, el):
        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        time.sleep(random.uniform(0.3, 0.8))
        try:
            WebDriverWait(self.driver, 8).until(EC.element_to_be_clickable(el))
            ActionChains(self.driver).move_to_element(el).pause(0.1).click().perform()
        except WebDriverException:
            self.driver.execute_script("arguments[0].click();", el)

    def _wait_details_name(self):
        name_selectors = [
            "h1.fontHeadlineLarge",  # UI mới
            "h1.DUwDvf",             # UI cũ
            "[role='main'] h1"       # fallback
        ]
        end = time.time() + WAIT_TIME
        while time.time() < end:
            for sel in name_selectors:
                els = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if els and els[0].text.strip():
                    return els[0]
            time.sleep(0.2)
        raise TimeoutException("No details title")

    def _first_text(self, selectors, default="N/A"):
        for sel in selectors:
            try:
                t = self.driver.find_element(By.CSS_SELECTOR, sel).text.strip()
                if t:
                    return t
            except NoSuchElementException:
                continue
        return default

    def _get_share_link(self, name):
        """Ưu tiên link từ dialog Share. Fallback dùng current_url hoặc api=1"""
        # Thử mở dialog Share
        try:
            btn = WebDriverWait(self.driver, 3).until(EC.element_to_be_clickable((
                By.CSS_SELECTOR,
                'button[aria-label*="Share"], button[aria-label*="Chia sẻ"]'
            )))
            btn.click()
            time.sleep(0.5)  # Chờ dialog mở
            
            # Tìm input trong dialog với timeout ngắn
            try:
                link_input = WebDriverWait(self.driver, 3).until(EC.presence_of_element_located((
                    By.CSS_SELECTOR,
                    'div[role="dialog"] input[aria-label*="Link"], div[role="dialog"] input[readonly], input[type="text"][readonly]'
                )))
                url = link_input.get_attribute("value") or link_input.get_attribute("aria-label")
                
                # Đóng dialog bằng ESC
                try:
                    ActionChains(self.driver).send_keys("\u001b").perform()
                    time.sleep(0.3)
                except:
                    pass
                
                if url and url.startswith("http"):
                    return url
            except TimeoutException:
                # Không tìm thấy input, đóng dialog và fallback
                try:
                    ActionChains(self.driver).send_keys("\u001b").perform()
                    time.sleep(0.3)
                except:
                    pass
        except (TimeoutException, NoSuchElementException):
            pass
        
        # Fallback 1: current_url khi đã ở trang place
        cur = self.driver.current_url
        if "/place/" in cur or "cid=" in cur:
            return cur
        
        # Fallback 2: api=1
        q = urllib.parse.quote_plus(name)
        return f"https://www.google.com/maps/search/?api=1&query={q}"

    # ---------- steps ----------
    def search_restaurant_by_name(self, restaurant_name):
        """Tìm kiếm nhà hàng theo tên cụ thể"""
        q = SEARCH_QUERY_NAME.format(restaurant_name=restaurant_name)
        self.driver.get("https://www.google.com/maps")
        self._maybe_consent()
        box = self.wait.until(EC.presence_of_element_located((By.ID, "searchboxinput")))
        box.clear(); box.send_keys(q); box.send_keys(Keys.ENTER)
        time.sleep(2)
        # Nếu chỉ có 1 kết quả, Google Maps sẽ tự động mở trang chi tiết
        # Nếu có nhiều kết quả, sẽ hiện list
        try:
            self._wait_feed()
            self._ensure_list_mode()
        except TimeoutException:
            # Có thể đã vào trang chi tiết trực tiếp
            pass

    def extract_restaurant_info(self):
        self._ensure_list_mode()
        cards = self._get_cards()
        if not cards:
            raise TimeoutException("No results list")

        idx = 0
        consecutive_failures = 0  # Đếm số lần thất bại liên tiếp
        
        while True:
            cards = self._get_cards()
            if idx >= len(cards): 
                break
            
            # Nếu quá nhiều lỗi liên tiếp, có thể đã hết kết quả
            if consecutive_failures >= 5:
                print("Too many consecutive failures, stopping...")
                break
                
            el = cards[idx]
            
            # Lấy identifier trước khi click để kiểm tra trùng lặp
            try:
                # Lấy tên từ card để làm identifier
                card_name = ""
                name_selectors = [
                    'div.qBF1Pd',
                    'a.hfpxzc div.qBF1Pd',
                    'div[role="article"] div.fontHeadlineSmall',
                    'div.NrDZNb'
                ]
                for sel in name_selectors:
                    try:
                        card_name = el.find_element(By.CSS_SELECTOR, sel).text.strip()
                        if card_name:
                            break
                    except NoSuchElementException:
                        continue
                
                # Kiểm tra đã xử lý chưa
                if card_name and card_name in self.processed_restaurants:
                    print(f"Skipping duplicate: {card_name}")
                    idx += 1
                    continue
                    
            except Exception as e:
                print(f"Error checking card name: {e}")
            
            idx += 1
            tries = 0
            processed_this_item = False
            
            while tries <= 2:
                try:
                    self._safe_click_card(el)
                    time.sleep(2)  # Đợi trang load đầy đủ

                    # Name - thử nhiều cách lấy tên
                    name_el = self._wait_details_name()
                    name = name_el.text.strip()
                    if not name:  # thử thêm các selector khác
                        name = self._first_text([
                            'div.TIHn2 h1',
                            'div[role="main"] h1.DUwDvf',
                            'div.x3AX1-LfntMc-header-title-title span'
                        ])
                    
                    # Kiểm tra lại trong trang chi tiết
                    if name in self.processed_restaurants:
                        print(f"Already processed (detail page): {name}")
                        try:
                            self.driver.find_element(By.CSS_SELECTOR, 'button[aria-label*="Back"]').click()
                            self._wait_feed()
                        except Exception:
                            pass
                        break

                    # Address - click để mở rộng nếu cần
                    try:
                        addr_btn = self.driver.find_element(By.CSS_SELECTOR,
                            'button[data-item-id="address"], button[data-tooltip="Copy address"]')
                        addr_btn.click()
                        time.sleep(0.5)
                    except: pass

                    address = self._first_text([
                        'button[data-item-id="address"] div.rogA2c',
                        'div[data-item-id="address"] div.rogA2c',
                        'button[data-tooltip="Copy address"] div.rogA2c',
                        '[data-tooltip*="address"] .rogA2c',
                        'div[aria-label*="Address"] .rogA2c',
                        'div[aria-label*="Địa chỉ"] .rogA2c'
                    ])

                    # Phone - click để hiện số điện thoại
                    try:
                        phone_btn = self.driver.find_element(By.CSS_SELECTOR,
                            'button[data-item-id*="phone"], button[aria-label*="phone"]')
                        phone_btn.click()
                        time.sleep(0.5)
                    except: pass

                    phone = self._first_text([
                        'div[data-item-id*="phone"] div.rogA2c',
                        'button[data-item-id*="phone"] div.rogA2c',
                        '[data-tooltip*="phone"] div.rogA2c',
                        'a[data-item-id*="phone"]',
                        '[aria-label*="Phone:"] .rogA2c',
                        '[aria-label*="Điện thoại"] .rogA2c'
                    ])

                    # Rating & Reviews count
                    rating = "N/A"
                    review_count = "0"
                    
                    # Thử nhiều cách khác nhau để lấy rating
                    rating_selectors = [
                        # UI mới
                        'div.F7nice span[aria-hidden="true"]',
                        'span.ceNzKf',
                        'div.fontDisplayLarge',
                        # UI review panel
                        'div.jANrlb div.fontDisplayLarge',
                        'div.jANrlb span[aria-hidden="true"]',
                        # Các aria-label
                        '[aria-label*="rating"]',
                        '[aria-label*="stars"]',
                        '[aria-label*="sao"]',
                        # Fallback
                        '[role="img"][aria-label*="stars"]',
                        '[role="img"][aria-label*="sao"]'
                    ]
                    
                    for selector in rating_selectors:
                        try:
                            element = self.driver.find_element(By.CSS_SELECTOR, selector)
                            # Thử lấy từ aria-label trước
                            aria_label = element.get_attribute('aria-label') or ''
                            if aria_label:
                                # Tìm số trong aria-label (e.g., "4.5 stars" hoặc "4,5 sao")
                                matches = re.findall(r'(\d+[.,]?\d*)', aria_label)
                                if matches:
                                    rating = matches[0].replace(',', '.')
                                    break
                            # Nếu không có aria-label, lấy text
                            text = element.text.strip()
                            if text and re.match(r'\d+[.,]?\d*', text):
                                rating = text.replace(',', '.')
                                break
                        except NoSuchElementException:
                            continue
                        except Exception as e:
                            print(f"Error getting rating from {selector}: {str(e)}")
                            continue

                    # Review count với nhiều cách khác nhau
                    review_selectors = [
                        # UI mới
                        'div.F7nice span:not([aria-hidden="true"])',
                        'span.HHrUdb',
                        'div.fontBodyMedium > span',
                        # UI review panel
                        'div.jANrlb div.fontBodyMedium span',
                        # Các aria-label
                        '[aria-label*="reviews"]',
                        '[aria-label*="đánh giá"]',
                        # Text nodes
                        'span[jsan*="reviews"]',
                        'button[jsaction*="reviews"]'
                    ]
                    
                    for selector in review_selectors:
                        try:
                            element = self.driver.find_element(By.CSS_SELECTOR, selector)
                            text = element.text.strip()
                            # Tìm số lượng review, bỏ qua các ký tự không phải số
                            matches = re.findall(r'(\d+(?:[,\.]\d+)*)', text)
                            if matches:
                                review_count = matches[0].replace(',', '').replace('.', '')
                                break
                        except NoSuchElementException:
                            continue
                        except Exception as e:
                            print(f"Error getting review count from {selector}: {str(e)}")
                            continue

                    # Link - lấy từ dialog Share hoặc URL hiện tại
                    maps_link = self._get_share_link(name)
                    if "?entry=" in maps_link:  # Làm sạch URL
                        maps_link = maps_link.split("?entry=")[0]

                    # Thêm vào set và data
                    self.processed_restaurants.add(name)
                    self.restaurants_data.append({
                        "Name": name,
                        "Address": address,
                        "Phone": phone,
                        "Rating": rating,
                        "Review Count": review_count,
                        "Google Maps Link": maps_link
                    })
                    print(f"Found: {name} | {address} | {phone} | {rating} ({review_count} reviews)")
                    
                    processed_this_item = True
                    consecutive_failures = 0  # Reset counter

                    # Quay lại danh sách
                    try:
                        back_btn = self.driver.find_element(By.CSS_SELECTOR,
                            'button[jsaction*="back"], button[aria-label*="Back"]')
                        back_btn.click()
                        self._wait_feed()
                    except Exception:
                        pass
                    break

                except StaleElementReferenceException:
                    tries += 1
                    time.sleep(0.8)
                    cards = self._get_cards()
                    if idx - 1 < len(cards): 
                        el = cards[idx - 1]
                except TimeoutException as e:
                    print("Timeout while reading details:", repr(e))
                    consecutive_failures += 1
                    try:
                        self.driver.find_element(By.CSS_SELECTOR, 'button[aria-label*="Back"]').click()
                        self._wait_feed()
                    except Exception:
                        pass
                    break
                except Exception as e:
                    print("Error:", type(e).__name__, repr(e))
                    consecutive_failures += 1
                    try:
                        self.driver.find_element(By.CSS_SELECTOR, 'button[aria-label*="Back"]').click()
                        self._wait_feed()
                    except Exception:
                        pass
                    break
            
            if not processed_this_item:
                consecutive_failures += 1

    def extract_single_restaurant(self, restaurant_name):
        """Lấy thông tin 1 nhà hàng cụ thể (khi tìm kiếm trực tiếp)"""
        print(f"  Extracting info for: {restaurant_name}")
        
        try:
            # Kiểm tra xem có đang ở trang chi tiết không
            try:
                name_el = self._wait_details_name()
                # Đang ở trang chi tiết, lấy thông tin luôn
                name = name_el.text.strip()
            except TimeoutException:
                # Có thể đang ở list view, thử click vào kết quả đầu tiên
                try:
                    cards = self._get_cards()
                    if cards:
                        self._safe_click_card(cards[0])
                        time.sleep(2)
                        name_el = self._wait_details_name()
                        name = name_el.text.strip()
                    else:
                        print(f"  No results found for {restaurant_name}")
                        return False
                except Exception as e:
                    print(f"  Error clicking card: {e}")
                    return False
            
            if not name:
                print(f"  Could not get name for {restaurant_name}")
                return False
                
            # Kiểm tra đã xử lý chưa
            if name in self.processed_restaurants:
                print(f"  Already processed: {name}")
                return True
            
            # Address - click để mở rộng nếu cần
            try:
                addr_btn = self.driver.find_element(By.CSS_SELECTOR,
                    'button[data-item-id="address"], button[data-tooltip="Copy address"]')
                addr_btn.click()
                time.sleep(0.5)
            except: pass

            address = self._first_text([
                'button[data-item-id="address"] div.rogA2c',
                'div[data-item-id="address"] div.rogA2c',
                'button[data-tooltip="Copy address"] div.rogA2c',
                '[data-tooltip*="address"] .rogA2c',
                'div[aria-label*="Address"] .rogA2c',
                'div[aria-label*="Địa chỉ"] .rogA2c'
            ])

            # Phone - click để hiện số điện thoại
            try:
                phone_btn = self.driver.find_element(By.CSS_SELECTOR,
                    'button[data-item-id*="phone"], button[aria-label*="phone"]')
                phone_btn.click()
                time.sleep(0.5)
            except: pass

            phone = self._first_text([
                'div[data-item-id*="phone"] div.rogA2c',
                'button[data-item-id*="phone"] div.rogA2c',
                '[data-tooltip*="phone"] div.rogA2c',
                'a[data-item-id*="phone"]',
                '[aria-label*="Phone:"] .rogA2c',
                '[aria-label*="Điện thoại"] .rogA2c'
            ])

            # Rating
            rating = "N/A"
            rating_selectors = [
                'div.F7nice span[aria-hidden="true"]',
                'span.ceNzKf',
                'div.fontDisplayLarge',
                'div.jANrlb div.fontDisplayLarge',
            ]
            
            for selector in rating_selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    text = element.text.strip()
                    if text and re.match(r'\d+[.,]?\d*', text):
                        rating = text.replace(',', '.')
                        break
                except: continue

            # Review count
            review_count = "0"
            review_selectors = [
                'div.F7nice span:not([aria-hidden="true"])',
                'span.HHrUdb',
                'div.fontBodyMedium > span',
            ]
            
            for selector in review_selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    text = element.text.strip()
                    matches = re.findall(r'(\d+(?:[,\.]\d+)*)', text)
                    if matches:
                        review_count = matches[0].replace(',', '').replace('.', '')
                        break
                except: continue

            # Link
            maps_link = self._get_share_link(name)
            if "?entry=" in maps_link:
                maps_link = maps_link.split("?entry=")[0]

            # Thêm vào data
            self.processed_restaurants.add(name)
            self.restaurants_data.append({
                "Name": name,
                "Address": address,
                "Phone": phone,
                "Rating": rating,
                "Review Count": review_count,
                "Google Maps Link": maps_link
            })
            print(f"  ✓ {name} | {address} | {phone} | {rating} ({review_count} reviews)")
            return True
            
        except Exception as e:
            print(f"  Error extracting info for {restaurant_name}: {e}")
            return False
    
    def crawl_restaurant(self, restaurant_name):
        """Crawl 1 nhà hàng theo tên"""
        print(f"\n{'='*60}")
        print(f"Crawling: {restaurant_name}")
        print(f"{'='*60}")
        
        try:
            self.search_restaurant_by_name(restaurant_name)
            time.sleep(1)
            success = self.extract_single_restaurant(restaurant_name)
            
            if not success:
                print(f"  ✗ Failed to crawl: {restaurant_name}")
        except Exception as e:
            print(f"  Error crawling {restaurant_name}: {e}")

    def close(self): self.driver.quit()

def main():
    crawler = RestaurantCrawler()
    try:
        # Crawl theo danh sách tên nhà hàng
        print(f"\nTotal restaurants to crawl: {len(RESTAURANT_NAMES)}")
        print("="*60)
        
        for idx, restaurant_name in enumerate(RESTAURANT_NAMES, 1):
            print(f"\n[{idx}/{len(RESTAURANT_NAMES)}] Processing: {restaurant_name}")
            crawler.crawl_restaurant(restaurant_name)
            time.sleep(random.uniform(1, 3))  # Delay giữa các tìm kiếm
        
        # Lưu tất cả vào 1 file
        output_file = "restaurants_danang_hoian3.xlsx"
        df = pd.DataFrame(crawler.restaurants_data)
        if df.empty:
            print("\nNo restaurants found")
        else:
            df = df.drop_duplicates(subset=['Name', 'Address'], keep='first')
            df.to_excel(output_file, index=False)
            print(f"\n{'='*60}")
            print(f"Saved {len(df)} restaurants -> {output_file}")
            print(f"{'='*60}")
    finally:
        crawler.close()

if __name__ == "__main__":
    main()
