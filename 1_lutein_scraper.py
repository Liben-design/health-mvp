import requests
import pandas as pd
import time
import re
import random
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

# ==========================================
# 工具函式
# ==========================================
def extract_brand(title):
    if not isinstance(title, str): return "未標示"
    # 嘗試抓取 【】 或 [] 裡面的品牌
    match = re.search(r"[【\[](.+?)[】\]]", title)
    if match:
        return match.group(1).strip()
    # 如果找不到，且標題夠長，暫時用前四個字當品牌
    return title[:4] if len(title) > 4 else "未標示"

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
# 1. PChome 爬蟲 (修復大小寫敏感問題)
# ==========================================
def scrape_pchome_lutein():
    print("🚀 [PChome] 開始抓取...")
    url = "https://ecshweb.pchome.com.tw/search/v3.3/all/results"
    params = {'q': '葉黃素', 'page': 1, 'sort': 'sale/dc'}
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
                    
                    data_list.append({
                        "source": "PChome",
                        "brand": extract_brand(name),
                        "title": name,
                        "price": int(price),
                        "url": f"https://24h.pchome.com.tw/prod/{pid}",
                        "image_url": image_url,
                        "tags": extract_tags(name),
                        "sales_volume": 0,  # PChome 不提供銷量數據，預設為 0
                        "raw_data": name
                    })
            time.sleep(1)
    except Exception as e:
        print(f"❌ [PChome] 錯誤: {e}")
        
    return data_list

# ==========================================
# 2. MOMO 爬蟲 (銷量排序版 - 優化效率)
# ==========================================
def scrape_momo_lutein(limit=100):
    print("🚀 [MOMO] 啟動隱身瀏覽器 (銷量排序)...")
    data_list = []

    with sync_playwright() as p:
        # 1. 啟動參數：移除自動化特徵
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
        )

        # 2. 設置 User Agent
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        # 3. 注入 JS 隱藏 webdriver 屬性
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        try:
            count = 0
            for page_num in range(1, 4):  # 只爬前 3 頁
                if count >= limit: break
                print(f"🔗 前往 MOMO 第 {page_num} 頁...")
                url = f"https://www.momoshop.com.tw/search/searchShop.jsp?keyword=葉黃素&searchType=6&curPage={page_num}"
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
                        print(f"   [進度] 正在解析第 {count+1}/{limit} 筆：{title[:10]}...", end="\r")

                        price_text = item.locator(".price, .money").first.inner_text()
                        price = int(re.sub(r'[^\d]', '', price_text))

                        link = item.get_attribute("href") or item.locator("a").first.get_attribute("href")
                        if link and not link.startswith("http"): link = "https://www.momoshop.com.tw" + link

                        # 進入內頁抓取詳細資訊 - 使用新分頁避免影響列表頁
                        inner_text = ""
                        if link:
                            new_page = None
                            try:
                                new_page = context.new_page()
                                new_page.goto(link, timeout=10000)
                                time.sleep(random.uniform(2, 5))  # 加入隨機延遲
                                try:
                                    inner_text = new_page.locator('.spec, .description, #spec').first.inner_text()
                                except:
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

                        data_list.append({
                            "source": "MOMO",
                            "brand": extract_brand(title),
                            "title": title,
                            "price": price,
                            "url": link,
                            "image_url": image_url,
                            "tags": tags,
                            "sales_volume": sales_volume,
                            "raw_data": title
                        })
                        count += 1
                    except Exception as e:
                        print(f"❌ 商品抓取失敗: {e}")
                        # 即使失敗，也嘗試記錄基本資料 (標題、價格)
                        try:
                            basic_title = item.locator(".prdName").first.inner_text()
                            basic_price_text = item.locator(".price, .money").first.inner_text()
                            basic_price = int(re.sub(r'[^\d]', '', basic_price_text))
                            basic_link = item.get_attribute("href") or item.locator("a").first.get_attribute("href")
                            if basic_link and not basic_link.startswith("http"): basic_link = "https://www.momoshop.com.tw" + basic_link

                            data_list.append({
                                "source": "MOMO",
                                "brand": extract_brand(basic_title),
                                "title": basic_title,
                                "price": basic_price,
                                "url": basic_link,
                                "image_url": "https://dummyimage.com/200x200/cccccc/ffffff.png&text=MOMO+Basic",
                                "tags": "",
                                "sales_volume": 0,
                                "raw_data": basic_title
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
    # 1. 執行 PChome
    df_p = pd.DataFrame(scrape_pchome_lutein())
    
    # 2. 執行 MOMO (限制前 30 筆商品)
    df_m = pd.DataFrame(scrape_momo_lutein(30))
    
    # 3. 合併與存檔
    all_df = pd.concat([df_p, df_m], ignore_index=True)
    
    if not all_df.empty:
        all_df.to_csv("lutein_market_data.csv", index=False, encoding="utf-8-sig")
        print("\n✅ 資料合併完成！")
        print(f"   PChome: {len(df_p)} 筆")
        print(f"   MOMO:   {len(df_m)} 筆")
        
        # 簡單檢查前幾筆 PChome 是否有抓到標題
        print("\n🔍 資料抽樣檢查 (PChome):")
        print(df_p[['title', 'price']].head(3))
    else:
        print("⚠️ 完全沒抓到資料，請檢查網路或程式碼。")
