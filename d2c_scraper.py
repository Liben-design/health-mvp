import asyncio
import pandas as pd
import time
import re
import random
import os
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from playwright_stealth import stealth_sync
from bs4 import BeautifulSoup

# ==========================================
# 共享工具函式 (從 general_scraper.py 移轉)
# ==========================================
BRAND_WHITELIST = [
    "大研生醫", "營養師輕食", "Swisse", "Nature's Way", "Blackmores", "GNC",
    "Kemin", "FloraGLO", "Lutemax", "DSM", "BASF", "NOW Foods", "Doctor's Best"
]

def extract_brand(title):
    if not isinstance(title, str): return "未標示"
    for brand in BRAND_WHITELIST:
        if brand.lower() in title.lower():
            return brand
    match = re.search(r"[【\[](.+?)[】\]]", title)
    if match: return match.group(1).strip()
    return title[:4] if len(title) > 4 else "未標示"

def calculate_unit_price(title, price):
    if not isinstance(title, str): return None, 0
    unit_count, bundle_size = None, 1
    match = re.search(r'(\d+)\s*[粒顆錠]', title)
    if match: unit_count = int(match.group(1))
    match = re.search(r'(\d+)\s*[入件盒罐包]組?', title)
    if match: bundle_size = int(match.group(1))
    else:
        match = re.search(r'[xX*]\s*(\d+)', title)
        if match: bundle_size = int(match.group(1))
    if unit_count:
        total_count = unit_count * bundle_size
        return total_count, round(price / total_count, 2)
    return None, 0

def extract_tags(text):
    tags = []
    if not isinstance(text, str): return ""
    # 簡化版標籤提取，可根據D2C的詳細描述進行擴充
    if re.search(r"游離型|Free form", text, re.IGNORECASE): tags.append("✅游離型")
    if re.search(r"FloraGLO|Kemin", text, re.IGNORECASE): tags.append("💎FloraGLO")
    if re.search(r"10[:：]2", text): tags.append("⚖️10:2比例")
    if re.search(r"蝦紅素|藻紅素", text): tags.append("🦐蝦紅素")
    if re.search(r"花青素|山桑子", text): tags.append("🫐花青素")
    if re.search(r"玻尿酸|魚油|DHA", text): tags.append("💧水潤配方")
    if re.search(r"SNQ", text, re.IGNORECASE): tags.append("🏅SNQ認證")
    if re.search(r"SGS", text, re.IGNORECASE): tags.append("🛡️SGS檢驗")
    return " ".join(tags) if tags else ""

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# ==========================================
# D2C 品牌設定檔
# ==========================================
DAIKEN_CONFIG = {
    "brand_name": "大研生醫",
    "product_list_url": "https://www.daikenshop.com/allgoods.php",
    # "direct_links": [
    #     "https://www.daikenshop.com/product.php?code=4710255450081" # 視易適葉黃素
    # ],
    "selectors": {
        # 列表頁選擇器 (備用)
        "list_item": ".product-wrap",
        "list_title": "h3.product-name",
        "product_url": ".product-image a",
        "product_img": ".product-image img",
        "product_price": ".product-price",
        # 詳情頁選擇器
        "details": {
            "title": "h1.product-name",
            "description": ".product-description",
            "ingredients": ".product-description" # 抓取整個描述區塊讓tag提取
        }
    }
}

# ==========================================
# 核心爬蟲函式
# ==========================================
def scrape_d2c_site(config, keyword_filter, max_retries=2):
    print(f"🚀 [D2C Scraper] 啟動瀏覽器，目標品牌：{config['brand_name']}")
    data_list = []
    product_links = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=random.choice(USER_AGENTS))
        
        try:
            # --- 策略選擇：優先使用直接連結，否則從列表頁發現 ---
            if "direct_links" in config and config["direct_links"]:
                print("🎯 使用直接連結模式...")
                product_links = config["direct_links"]
            else:
                print("🧭 使用列表頁發現模式...")
                page = context.new_page()
                stealth_sync(page)

                # 1. 前往產品列表頁
                print(f"🔗 前往列表頁: {config['product_list_url']}")
                page.goto(config['product_list_url'], wait_until="domcontentloaded", timeout=60000)
                try:
                    # 點擊 Cookie 同意按鈕
                    print("... 正在尋找並點擊 Cookie 同意按鈕 ...")
                    agree_button = page.locator('text="同意"').first
                    agree_button.click(timeout=5000)
                    print("✅ Cookie 同意按鈕已點擊。")
                except Exception as e:
                    print("ℹ️ 未找到 Cookie 同意按鈕，或點擊時發生錯誤，繼續執行...")
                
                print("⏳ 等待產品列表出現...")
                page.wait_for_selector(config["selectors"]["list_item"], timeout=20000)
                print("✅ 產品列表已載入。")

                # 2. 模擬滾動，載入所有商品
                print("🔄 模擬滾動以載入所有商品...")
                for _ in range(5): # 滾動5次以盡可能載入
                    page.mouse.wheel(0, 15000)
                    time.sleep(random.uniform(2, 4))

                # 3. 抓取所有商品連結
                all_items = page.locator(config["selectors"]["list_item"]).all()
                print(f"🕵️‍♂️ 找到 {len(all_items)} 個產品項目，開始過濾...")
                for item in all_items:
                    try:
                        # 過濾出包含關鍵字的商品
                        title_text = item.locator(config["selectors"]["list_title"]).inner_text()
                        print(f"   - 正在檢查: {title_text.strip()}") # 除錯：印出所有抓到的標題
                        if keyword_filter.lower() in title_text.lower():
                            link = item.locator(config["selectors"]["product_url"]).get_attribute("href")
                            if link and not link.startswith("http"):
                                base_url = config['product_list_url'].split('/allgoods.php')[0]
                                link = base_url + "/" + link.lstrip("/")
                            product_links.append(link)
                    except Exception as e:
                        print(f"⚠️ 列表項目解析錯誤: {e}")
                
                page.close()

            print(f"✅ 共需抓取 {len(product_links)} 個商品連結。")

            # 4. 逐一進入詳情頁抓取
            for i, link in enumerate(product_links):
                if not link: continue
                print(f"   [進度 {i+1}/{len(product_links)}] 正在解析: {link}")
                
                # --- 控制論：錯誤重試機制 ---
                for attempt in range(max_retries):
                    detail_page = None
                    try:
                        # 在每次循環中創建新頁面
                        detail_page = context.new_page()
                        stealth_sync(detail_page)
                        
                        detail_page.goto(link, wait_until="domcontentloaded", timeout=30000)
                        try:
                            # 點擊 Cookie 同意按鈕
                            print("... 正在尋找並點擊 Cookie 同意按鈕 ...")
                            agree_button = detail_page.locator('text="同意"').first
                            agree_button.click(timeout=5000)
                            print("✅ Cookie 同意按鈕已點擊。")
                        except Exception as e:
                            print("ℹ️ 未找到 Cookie 同意按鈕，或點擊時發生錯誤，繼續執行...")
                        
                        time.sleep(random.uniform(2, 3))

                        # --- 抓取核心數據 ---
                        detail_page.wait_for_selector(config["selectors"]["details"]["title"], state='visible', timeout=60000)
                        title = detail_page.locator(config["selectors"]["details"]["title"]).inner_text()
                        price_text = detail_page.locator(config["selectors"]["product_price"]).first.inner_text()
                        price = int(re.sub(r'[^\d]', '', price_text))

                        # --- 擴充數據字段 ---
                        description = detail_page.locator(config["selectors"]["details"]["description"]).first.inner_text()
                        ingredients = detail_page.locator(config["selectors"]["details"]["ingredients"]).first.inner_text()
                        
                        # 在詳情頁重新抓取圖片，確保是最高畫質
                        img_element = detail_page.locator(config["selectors"]["product_img"]).first
                        image_url = img_element.get_attribute("src") or img_element.get_attribute("data-src")
                        if image_url and image_url.startswith('//'):
                            image_url = 'https:' + image_url

                        # --- 整合與清洗 ---
                        title = title.replace(",", " ").replace("\n", " ")
                        full_text = f"{title} {description} {ingredients}"
                        
                        total_count, unit_price = calculate_unit_price(title, price)
                        tags = extract_tags(full_text)

                        data_list.append({
                            "source": config["brand_name"],
                            "brand": config["brand_name"],
                            "title": title,
                            "price": price,
                            "url": link,
                            "image_url": image_url,
                            "tags": tags,
                            "sales_volume": 0, # D2C 無法得知銷量
                            "raw_data": f"{title} {description}",
                            "total_count": total_count,
                            "unit_price": unit_price
                        })
                        
                        break # 成功，跳出重試循環

                    except Exception as e:
                        print(f"      ❌ 第 {attempt+1} 次抓取失敗: {e}")
                        if attempt == max_retries - 1:
                            print(f"      ‼️ 無法抓取該頁面，已達最大重試次數，跳過。")
                            if detail_page:
                                detail_page.screenshot(path=f"debug_screenshot.png")
                        else:
                            time.sleep(random.uniform(3, 5)) # 等待後重試
                    finally:
                        if detail_page:
                            try:
                                detail_page.close()
                            except:
                                pass # 頁面可能已因錯誤而關閉

        except Exception as e:
            print(f"❌ [D2C Scraper] 發生嚴重錯誤: {e}")
        finally:
            browser.close()
            print("✅ 瀏覽器已關閉。")

    return data_list

# ==========================================
# 主程式執行區
# ==========================================
if __name__ == "__main__":
    # --- 任務設定 ---
    TARGET_KEYWORD = "視易適葉黃素"
    
    # 1. 執行 D2C 爬蟲
    d2c_data = scrape_d2c_site(DAIKEN_CONFIG, keyword_filter=TARGET_KEYWORD)
    df_d2c = pd.DataFrame(d2c_data)

    # 2. 檢查與存檔
    if not df_d2c.empty:
        # 確保存檔資料夾存在
        os.makedirs("data", exist_ok=True)
        
        # --- 輸出 CSV，與現有格式兼容 ---
        filename = f"data/D2C_{TARGET_KEYWORD}_data.csv"
        df_d2c.to_csv(filename, index=False, encoding="utf-8-sig")
        
        print("\n\n" + "="*50)
        print("🎉 D2C 爬蟲任務完成！")
        print(f"💾 資料已存檔至: {filename}")
        print(f"總共抓取到 {len(df_d2c)} 筆 '{TARGET_KEYWORD}' 相關商品。")
        print("="*50)

        # --- 提供測試抓取的結果範例 ---
        print("\n📜 資料範例預覽：")
        print(df_d2c[['brand', 'title', 'price', 'tags']].head())
    else:
        print("\n⚠️ 本次 D2C 爬蟲未抓取到任何資料。")

    print("\n\n--- 快速擴充指南 ---")
    print("如何支援下一個 D2C 品牌？")
    print("1. 在 d2c_scraper.py 中，仿照 DAIKEN_CONFIG 建立一個新的設定檔，例如 LITE_CONFIG。")
    print("2. 填寫新品牌的 `brand_name`, `product_list_url`。")
    print("3. 手動觀察新品牌網站的 HTML 結構，更新 `selectors` 字典中的 CSS 選擇器。")
    print("4. 在主程式區塊，呼叫 `scrape_d2c_site(LITE_CONFIG, ...)` 即可開始抓取。")
    print("工匠原則的核心在於模組化，讓擴充變得簡單！")
