import requests
import pandas as pd
import time
import re
import random
import os
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup

# ==========================================
# 產品清單定義
# ==========================================
TARGET_KEYWORDS = ["葉黃素", "益生菌", "魚油"]

# User-Agent 池：隨機化以降低被封鎖風險
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15"
]

# ==========================================
# 工具函式
# ==========================================
# 品牌白名單：優先匹配這些品牌，避免抓取錯誤標題前綴，提升資料準確性
BRAND_WHITELIST = [
    "大研生醫", "營養師輕食", "Swisse", "Nature's Way", "Blackmores", "GNC",
    "Kemin", "FloraGLO", "Lutemax", "DSM", "BASF", "NOW Foods", "Doctor's Best"
]

def extract_brand(title):
    if not isinstance(title, str): return "未標示"

    # 優先匹配品牌白名單（大小寫不敏感）
    for brand in BRAND_WHITELIST:
        if brand.lower() in title.lower():
            return brand

    # 嘗試抓取 【】 或 [] 裡面的品牌
    match = re.search(r"[【\[](.+?)[】\]]", title)
    if match:
        return match.group(1).strip()
    # 如果找不到，且標題夠長，暫時用前四個字當品牌
    return title[:4] if len(title) > 4 else "未標示"

def calculate_unit_price(title, price):
    if not isinstance(title, str): return None, 0
    unit_count = None
    bundle_size = 1

    # 提取「單瓶顆數」
    match = re.search(r'(\d+)\s*[粒顆錠]', title)
    if match:
        unit_count = int(match.group(1))

    # 提取「組數」
    match = re.search(r'(\d+)\s*[入件盒罐包]組?', title)
    if match:
        bundle_size = int(match.group(1))
    else:
        match = re.search(r'[xX*]\s*(\d+)', title)
        if match:
            bundle_size = int(match.group(1))

    if unit_count is not None:
        total_count = unit_count * bundle_size
        unit_price = round(price / total_count, 2)
    else:
        total_count = None
        unit_price = 0

    return total_count, unit_price

def extract_tags(text):
    tags = []
    if not isinstance(text, str): return ""

    # 1. 型態 (游離型優於酯化型)
    if re.search(r"游離型|Free form", text, re.IGNORECASE):
        tags.append("✅游離型")
    elif re.search(r"酯化型|Ester", text, re.IGNORECASE):
        tags.append("⚠️酯化型")

    # 2. 原料 (FloraGLO 為大廠指標)
    if re.search(r"FloraGLO|Kemin", text, re.IGNORECASE):
        tags.append("💎FloraGLO")
    elif re.search(r"Lutemax", text, re.IGNORECASE):
        tags.append("💎Lutemax")

    # 3. 比例 (10:2 黃金比例)
    if re.search(r"10[:：]2|10比2", text):
        tags.append("⚖️10:2比例")

    # 4. 複方 (蝦紅素、花青素)
    if re.search(r"蝦紅素|藻紅素", text):
        tags.append("🦐蝦紅素")
    if re.search(r"花青素|山桑子|黑醋栗|智利酒果", text):
        tags.append("🫐花青素")

    # 新增：進階複方 (針對情境)
    if re.search(r"玻尿酸|魚油|DHA", text):
        tags.append("💧水潤配方")
    if re.search(r"蝦紅素|黑豆", text):
        tags.append("🦐舒緩專注")
    if re.search(r"馬奇莓|山桑子|花青素", text):
        tags.append("🫐夜視守護")

    # 新增：劑型偵測
    if re.search(r"膠囊", text):
        tags.append("💊膠囊")
    if re.search(r"飲|凍", text):
        tags.append("🧃飲品/凍")

    # 5. 檢驗與認證 - 更新為具體的
    if re.search(r"SNQ", text, re.IGNORECASE):
        tags.append("🏅SNQ認證")
    if re.search(r"SGS", text, re.IGNORECASE):
        tags.append("🛡️SGS檢驗")
    if re.search(r"國家認證", text, re.IGNORECASE):
        tags.append("🛡️獲認證")

    # 如果完全沒有標籤，標記為一般
    if not tags:
        return ""

    return " ".join(tags)

# ==========================================
# 1. PChome 爬蟲 (泛化版)
# ==========================================
def scrape_pchome(keyword):
    print(f"🚀 [PChome] 開始抓取關鍵字：{keyword}")
    url = "https://ecshweb.pchome.com.tw/search/v3.3/all/results"
    params = {'q': keyword, 'page': 1, 'sort': 'sale/dc'}
    data_list = []

    try:
        for page in range(1, 4): # 抓前 3 頁
            params['page'] = page
            res = requests.get(url, params=params)
            if res.status_code == 200:
                products = res.json().get('prods', [])
                print(f"   📄 PChome 第 {page} 頁抓到 {len(products)} 筆...")

                for p in products:
                    # --- 關鍵修正：同時嘗試大小寫 key ---
                    name = p.get('Name') or p.get('name') or ""
                    # 清洗標題，避免 CSV 錯位
                    name = name.replace(",", " ").replace("\n", " ")

                    # 價格有時候叫 Price, price, 或是 originPrice
                    price = p.get('Price') or p.get('price') or p.get('originPrice') or 0

                    pid = p.get('Id') or p.get('id')

                    # 圖片 key 也可能變
                    img_filename = p.get('PicS') or p.get('picS') or p.get('PicB') or p.get('picB')
                    # --------------------------------

                    if img_filename:
                        # 補上 PChome 圖片網域
                        if img_filename.startswith('http'):
                             image_url = img_filename
                        else:
                             image_url = f"https://cs-a.ecimg.tw{img_filename}"
                    else:
                        image_url = "https://dummyimage.com/200x200/cccccc/ffffff.png&text=No+Image"

                    if not pid: continue

                    total_count, unit_price = calculate_unit_price(name, int(price))

                    data_list.append({
                        "source": "PChome",
                        "brand": extract_brand(name),
                        "title": name,
                        "price": int(price),
                        "url": f"https://24h.pchome.com.tw/prod/{pid}",
                        "image_url": image_url,
                        "tags": extract_tags(name),
                        "sales_volume": 0,  # PChome 不提供銷量數據，預設為 0
                        "raw_data": name,
                        "total_count": total_count,
                        "unit_price": unit_price
                    })
            time.sleep(1)
    except Exception as e:
        print(f"❌ [PChome] 錯誤: {e}")

    return data_list

# ==========================================
# 2. MOMO 爬蟲 (泛化版)
# ==========================================
def scrape_momo(keyword, limit=100):
    print(f"🚀 [MOMO] 啟動隱身瀏覽器 (銷量排序) 關鍵字：{keyword}")
    data_list = []

    with sync_playwright() as p:
        # 1. 啟動參數：移除自動化特徵
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
        )

        # 2. 設置 User Agent（隨機化以降低被封鎖風險）
        random_user_agent = random.choice(USER_AGENTS)
        context = browser.new_context(
            user_agent=random_user_agent
        )

        # 3. 注入 JS 隱藏 webdriver 屬性
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        try:
            count = 0
            for page_num in range(1, 4):  # 只爬前 3 頁
                if count >= limit: break
                print(f"🔗 前往 MOMO 第 {page_num} 頁...")
                url = f"https://www.momoshop.com.tw/search/searchShop.jsp?keyword={keyword}&searchType=6&curPage={page_num}"
                page.goto(url)
                time.sleep(random.uniform(2, 5))  # 加入隨機延遲

                # 增加載入等待時間
                try:
                    page.wait_for_selector(".listGoodsData, .goodsUrl", timeout=8000)
                except:
                    print("⏳ MOMO 載入較慢，繼續嘗試...")

                # 抓取資料 - 調整選擇器確保抓到所有商品
                items = page.locator(".listGoodsData").all()
                if not items: items = page.locator(".goodsUrl").all()
                if not items: items = page.locator("li.goodsItemLi").all()
                if not items: items = page.locator(".EachGood").all()
                if not items: items = page.locator("#CategoryContent li").all()

                print(f"📦 MOMO 第 {page_num} 頁找到 {len(items)} 個商品...")

                for item in items:
                    if count >= limit: break
                    try:
                        title = item.locator(".prdName").first.inner_text()
                        # 清洗標題中的逗號和換行符，避免 CSV 錯位
                        title = title.replace(",", " ").replace("\n", " ")
                        print(f"   [進度] 正在解析第 {count+1}/{limit} 筆：{title[:10]}...", end="\r")

                        price_text = item.locator(".price, .money").first.inner_text()
                        price = int(re.sub(r'[^\d]', '', price_text))

                        link = item.get_attribute("href") or item.locator("a").first.get_attribute("href")
                        if link and not link.startswith("http"): link = "https://www.momoshop.com.tw" + link

                        # 進入內頁抓取詳細資訊 - 使用新分頁避免影響列表頁
                        # 增加 try-except 捕捉特定的超時錯誤，確保某一筆資料失敗不影響整體抓取
                        inner_text = ""
                        if link:
                            new_page = None
                            try:
                                new_page = context.new_page()
                                new_page.goto(link, wait_until="domcontentloaded", timeout=60000)
                                time.sleep(random.uniform(2, 5))  # 加入隨機延遲
                                try:
                                    inner_text = new_page.locator('.spec, .description, #spec').first.inner_text()
                                except:
                                    inner_text = ""
                            except (TimeoutError, PlaywrightTimeoutError) as e:
                                print(f"⏰ 內頁超時 ({link}): {e} - 跳過此筆，繼續下一筆")
                                inner_text = ""
                            except Exception as e:
                                print(f"❌ 內頁抓取失敗 ({link}): {e}")
                                inner_text = ""
                            finally:
                                if new_page:
                                    try:
                                        new_page.close()
                                    except:
                                        pass

                        # 圖片抓取
                        image_url = None
                        imgs = item.locator("img").all()
                        for img in imgs:
                            src = img.get_attribute("data-original") or img.get_attribute("src")
                            # 過濾無效圖片
                            if src and "ecm" not in src and "icon" not in src:
                                if "goodsimg" in src or "i1.momoshop" in src:
                                    image_url = src
                                    break
                                if not image_url and "dummy" not in src and "data:image" not in src:
                                    image_url = src

                        # 標準化圖片網址：補上 "https:"
                        if image_url and image_url.startswith('//'):
                            image_url = 'https:' + image_url
                        
                        if not image_url: image_url = "https://dummyimage.com/200x200/cccccc/ffffff.png&text=MOMO+No+Img"

                        # 抓取銷量 - 如果抓不到預設為 0
                        sales_volume = 0
                        try:
                            slogan_text = item.locator(".money .slogan").first.inner_text()
                            match = re.search(r'總銷量\D*(\d+(?:,\d+)*)', slogan_text)  # 放寬 Regex
                            if match:
                                sales_volume = int(match.group(1).replace(',', ''))
                        except:
                            pass

                        # 合併 title 和內頁文字用於 extract_tags
                        combined_text = title + " " + inner_text
                        tags = extract_tags(combined_text)

                        total_count, unit_price = calculate_unit_price(title, price)

                        data_list.append({
                            "source": "MOMO",
                            "brand": extract_brand(title),
                            "title": title,
                            "price": price,
                            "url": link,
                            "image_url": image_url,
                            "tags": tags,
                            "sales_volume": sales_volume,
                            "raw_data": title,
                            "total_count": total_count,
                            "unit_price": unit_price
                        })
                        count += 1
                    except Exception as e:
                        print(f"❌ 商品抓取失敗: {e}")
                        # 即使失敗，也嘗試記錄基本資料 (標題、價格)
                        try:
                            basic_title = item.locator(".prdName").first.inner_text().replace(",", " ").replace("\n", " ")
                            basic_price_text = item.locator(".price, .money").first.inner_text()
                            basic_price = int(re.sub(r'[^\d]', '', basic_price_text))
                            basic_link = item.get_attribute("href") or item.locator("a").first.get_attribute("href")
                            if basic_link and not basic_link.startswith("http"): basic_link = "https://www.momoshop.com.tw" + basic_link

                            total_count, unit_price = calculate_unit_price(basic_title, basic_price)

                            data_list.append({
                                "source": "MOMO",
                                "brand": extract_brand(basic_title),
                                "title": basic_title,
                                "price": basic_price,
                                "url": basic_link,
                                "image_url": "https://dummyimage.com/200x200/cccccc/ffffff.png&text=MOMO+Basic",
                                "tags": "",
                                "sales_volume": 0,
                                "raw_data": basic_title,
                                "total_count": total_count,
                                "unit_price": unit_price
                            })
                            count += 1
                        except:
                            continue

                time.sleep(1)

        except Exception as e:
            print(f"❌ [MOMO] 錯誤: {e}")
        finally:
            browser.close()

    return data_list

# ==========================================
# 主程式
# ==========================================
if __name__ == "__main__":
    # 建立 data 資料夾
    os.makedirs("data", exist_ok=True)

    for keyword in TARGET_KEYWORDS:
        print(f"\n🔍 開始抓取關鍵字：{keyword}")
        # 1. 執行 PChome
        df_p = pd.DataFrame(scrape_pchome(keyword))

        # 2. 執行 MOMO (限制前 30 筆商品)
        df_m = pd.DataFrame(scrape_momo(keyword, 30))

        # 3. 合併與存檔
        all_df = pd.concat([df_p, df_m], ignore_index=True)

        if not all_df.empty:
            filename = f"data/{keyword}_data.csv"
            all_df.to_csv(filename, index=False, encoding="utf-8-sig")
            print(f"\n✅ {keyword} 資料存檔完成！")
            print(f"   PChome: {len(df_p)} 筆")
            print(f"   MOMO:   {len(df_m)} 筆")

            # 簡單檢查前幾筆 PChome 是否有抓到標題
            print(f"\n🔍 資料抽樣檢查 ({keyword} PChome):")
            print(df_p[['title', 'price']].head(3))
        else:
            print(f"⚠️ {keyword} 完全沒抓到資料，請檢查網路或程式碼。")

        # 關鍵字間延遲，避免對電商平台造成太大瞬間流量
        if keyword != TARGET_KEYWORDS[-1]:  # 最後一個不需要延遲
            print(f"⏳ 休息 10 秒後繼續下一個關鍵字...")
            time.sleep(10)
