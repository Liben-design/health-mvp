import requests
import pandas as pd
import time
import re
from playwright.sync_api import sync_playwright

# ==========================================
# 1. 工具函式：提取標籤與品牌
# ==========================================

def extract_brand(title):
    """
    從標題中提取品牌，通常格式為 【品牌】或是 [品牌]
    """
    if not isinstance(title, str):
        return "未標示"
    
    # 抓取 【】 或 [] 裡面的文字
    match = re.search(r"[【\[](.+?)[】\]]", title)
    if match:
        return match.group(1).strip()
    
    # 如果找不到括號，嘗試抓前兩個字當品牌（比較不準，但可當備案）
    return title[:4] if len(title) > 4 else "未標示"

def extract_tags(text):
    """
    提取規格標籤
    """
    tags = []
    if not isinstance(text, str):
        return ""
    
    # 葉黃素關鍵字
    if re.search(r"游離型|Free form", text, re.IGNORECASE):
        tags.append("✅游離型")
    if re.search(r"酯化型|Ester", text, re.IGNORECASE):
        tags.append("⚠️酯化型")
    
    # 專利原料關鍵字
    if re.search(r"FloraGLO", text, re.IGNORECASE):
        tags.append("💎FloraGLO")
    if re.search(r"Kemin", text, re.IGNORECASE):
        tags.append("💎Kemin")
    
    # 複方
    if "蝦紅素" in text:
        tags.append("➕蝦紅素")
    if "花青素" in text:
        tags.append("➕花青素")
        
    return " ".join(tags)

# ==========================================
# 2. PChome 爬蟲 (新增：圖片與品牌)
# ==========================================
def scrape_pchome_lutein():
    print("🚀 [PChome] 開始抓取...")
    url = "https://ecshweb.pchome.com.tw/search/v3.3/all/results"
    params = {'q': '葉黃素', 'page': 1, 'sort': 'sale/dc'}
    
    data_list = []
    try:
        for page in range(1, 4):
            params['page'] = page
            res = requests.get(url, params=params)
            
            if res.status_code == 200:
                data = res.json()
                products = data.get('prods', [])
                
                print(f"   📄 第 {page} 頁抓到 {len(products)} 筆資料...")

                for p in products:
                    name = p.get('Name') or p.get('name') or ""
                    desc = p.get('Describe') or p.get('describe') or ""
                    price = p.get('Price') or p.get('price') or p.get('originPrice') or 0
                    pid = p.get('Id') or p.get('id')
                    
                    # --- 新增：圖片處理 ---
                    # PChome 圖片通常在 PicS (小圖) 或 PicB (大圖)
                    img_file = p.get('PicS') or p.get('PicB')
                    if img_file:
                        # PChome 圖片伺服器通常是 cs-a.ecimg.tw
                        image_url = f"https://cs-a.ecimg.tw{img_file}"
                    else:
                        image_url = "https://dummyimage.com/200x200/cccccc/000000.png&text=No+Image"

                    if not pid: continue
                        
                    raw_text = str(name) + " " + str(desc)
                    
                    data_list.append({
                        "source": "PChome",
                        "brand": extract_brand(name),  # 新增品牌欄位
                        "title": name,
                        "price": int(price) if str(price).isdigit() else 0,
                        "url": f"https://24h.pchome.com.tw/prod/{pid}",
                        "image_url": image_url,        # 新增圖片欄位
                        "tags": extract_tags(raw_text),
                        "raw_data": raw_text[:200]
                    })
            time.sleep(1)
            
        print(f"✅ [PChome] 成功抓取 {len(data_list)} 筆")
            
    except Exception as e:
        print(f"❌ [PChome] 失敗: {e}")
        
    return data_list

# ==========================================
# 3. MOMO 爬蟲 (新增：圖片與品牌)
# ==========================================
def scrape_momo_lutein(limit=50):
    print("🚀 [MOMO] 啟動瀏覽器...")
    data_list = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) 
        context = browser.new_context()
        page = context.new_page()
        
        try:
            page.goto("https://www.momoshop.com.tw/search/searchShop.jsp?keyword=葉黃素&searchType=1")
            page.wait_for_timeout(3000)
            
            # 模擬滾動以觸發圖片 Lazy Loading (懶加載)
            for _ in range(3):
                page.mouse.wheel(0, 1000)
                page.wait_for_timeout(500)

            print("👀 正在掃描頁面...")
            items = page.locator(".listGoodsData").all()
            if len(items) == 0:
                items = page.locator(".goodsUrl").all()

            print(f"📦 找到 {len(items)} 個潛在商品...")
            
            count = 0
            for item in items:
                if count >= limit: break
                
                try:
                    title = item.locator(".prdName").first.inner_text()
                    
                    # --- 新增：圖片抓取 ---
                    # MOMO 的圖片通常在 img.goodsImg
                    try:
                        img_src = item.locator("img").first.get_attribute("src")
                    except:
                        img_src = "https://dummyimage.com/200x200/cccccc/000000.png&text=No+Image"

                    # 價格處理
                    try:
                        price_str = item.locator(".price, .money").first.inner_text()
                        price_str = re.sub(r'[^\d]', '', price_str)
                        price = int(price_str)
                    except:
                        price = 0

                    link = item.get_attribute("href")
                    if not link:
                        link = item.locator("a").first.get_attribute("href")
                    if link and not link.startswith("http"):
                        link = "https://www.momoshop.com.tw" + link
                        
                    data_list.append({
                        "source": "MOMO",
                        "brand": extract_brand(title), # 解析品牌
                        "title": title,
                        "price": price,
                        "url": link,
                        "image_url": img_src,          # 儲存圖片連結
                        "tags": extract_tags(title),
                        "raw_data": title
                    })
                    count += 1
                except:
                    continue
                    
            print(f"✅ [MOMO] 成功抓取 {len(data_list)} 筆")
            
        except Exception as e:
            print(f"❌ [MOMO] 失敗: {e}")
        finally:
            browser.close()
            
    return data_list

# ==========================================
# 主程式
# ==========================================
if __name__ == "__main__":
    df_pchome = pd.DataFrame(scrape_pchome_lutein())
    df_momo = pd.DataFrame(scrape_momo_lutein())
    
    all_df = pd.concat([df_pchome, df_momo], ignore_index=True)
    
    if len(all_df) > 0:
        all_df.to_csv("lutein_market_data.csv", index=False, encoding="utf-8-sig")
        print("\n🎉 資料更新完成！包含圖片連結與品牌欄位。")
    else:
        print("\n⚠️ 未抓取到任何資料。")
