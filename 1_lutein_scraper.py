import requests
import pandas as pd
import time
import re
from playwright.sync_api import sync_playwright

# ==========================================
# 1. 定義簡單的規格提取器
# ==========================================
def extract_tags(text):
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
# 2. PChome 爬蟲 (修復欄位抓取問題)
# ==========================================
def scrape_pchome_lutein():
    print("🚀 [PChome] 開始抓取...")
    # 注意：這裡加上 &fields=... 是為了強制 API 回傳我們需要的欄位，避免它偷懶
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
                    # 1. 名稱抓取 (嘗試多種可能性)
                    name = p.get('Name') or p.get('name') or ""
                    
                    # 2. 描述抓取
                    desc = p.get('Describe') or p.get('describe') or ""
                    
                    # 3. 價格抓取 (PChome 有時候會有 originPrice 或 price)
                    price = p.get('Price') or p.get('price') or p.get('originPrice') or 0
                    
                    # 4. ID 抓取 (如果沒有 Id，就無法組出連結)
                    pid = p.get('Id') or p.get('id')
                    
                    if not pid: 
                        continue # 沒有 ID 的資料沒用，跳過
                        
                    raw_text = str(name) + " " + str(desc)
                    
                    data_list.append({
                        "source": "PChome",
                        "title": name,
                        "price": int(price) if str(price).isdigit() else 0, # 強制轉成數字
                        "url": f"https://24h.pchome.com.tw/prod/{pid}",
                        "tags": extract_tags(raw_text),
                        "raw_data": raw_text[:200]
                    })
            else:
                print(f"⚠️ [PChome] 第 {page} 頁請求失敗: {res.status_code}")
                
            time.sleep(1)
            
        print(f"✅ [PChome] 成功抓取 {len(data_list)} 筆")
        
        # --- 除錯用：偷看一下第一筆資料長怎樣 ---
        if len(data_list) > 0:
            print("👀 [PChome 第一筆資料範例]:", data_list[0])
            
    except Exception as e:
        print(f"❌ [PChome] 失敗: {e}")
        
    return data_list

# ==========================================
# 3. MOMO 爬蟲 (改用桌機版 + 視覺除錯)
# ==========================================
def scrape_momo_lutein(limit=50):
    print("🚀 [MOMO] 啟動瀏覽器 (你會看到視窗跳出來)...")
    data_list = []
    
    with sync_playwright() as p:
        # --- 修正點：headless=False 讓你看得到瀏覽器運作 ---
        browser = p.chromium.launch(headless=False) 
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            # --- 修正點：改用桌機版搜尋網址，結構較穩定 ---
            page.goto("https://www.momoshop.com.tw/search/searchShop.jsp?keyword=葉黃素&searchType=1")
            
            # 等待一下，確保載入
            page.wait_for_timeout(3000)
            
            # 抓取桌機版的商品列表
            # MOMO 桌機版的商品卡片通常是 .listGoodsData (列表模式) 或 .goodsUrl (連結)
            # 我們嘗試抓取所有商品連結
            print("👀 正在掃描頁面上的商品...")
            
            # 取得所有商品卡片
            items = page.locator(".listGoodsData").all()
            
            if len(items) == 0:
                print("⚠️ 找不到 '.listGoodsData'，嘗試抓取 '.goodsUrl'...")
                # 備用方案
                items = page.locator(".goodsUrl").all()

            print(f"📦 找到 {len(items)} 個潛在商品，開始解析...")
            
            count = 0
            for item in items:
                if count >= limit: break
                
                try:
                    # 桌機版選擇器
                    title = item.locator(".prdName").first.inner_text()
                    
                    # 價格處理
                    try:
                        price_str = item.locator(".price, .money").first.inner_text()
                        # 清理 "$", ",", "元"
                        price_str = re.sub(r'[^\d]', '', price_str)
                        price = int(price_str)
                    except:
                        price = 0

                    # 連結處理
                    # 如果 item 本身是 <a> 標籤
                    link = item.get_attribute("href")
                    # 如果 item 是 div，往下找 <a>
                    if not link:
                        link = item.locator("a").first.get_attribute("href")
                    
                    if link and not link.startswith("http"):
                        link = "https://www.momoshop.com.tw" + link
                        
                    data_list.append({
                        "source": "MOMO",
                        "title": title,
                        "price": price,
                        "url": link,
                        "tags": extract_tags(title),
                        "raw_data": title
                    })
                    count += 1
                except Exception as inner_e:
                    # 這一筆失敗沒關係，繼續下一筆
                    continue
                    
            print(f"✅ [MOMO] 成功抓取 {len(data_list)} 筆")
            
        except Exception as e:
            print(f"❌ [MOMO] 失敗: {e}")
            # 截圖看看到底發生什麼事
            page.screenshot(path="momo_error.png")
            print("📷 已儲存錯誤截圖至 momo_error.png")
        finally:
            browser.close()
            
    return data_list

# ==========================================
# 主程式
# ==========================================
if __name__ == "__main__":
    
    # 1. 執行爬蟲 (暫時移除 Google 以確保穩定)
    df_pchome = pd.DataFrame(scrape_pchome_lutein())
    df_momo = pd.DataFrame(scrape_momo_lutein())
    
    # 2. 合併資料
    all_df = pd.concat([df_pchome, df_momo], ignore_index=True)
    
    # 3. 存檔
    if len(all_df) > 0:
        all_df.to_csv("lutein_market_data.csv", index=False, encoding="utf-8-sig")
        print("\n🎉 全部完成！資料已儲存為 'lutein_market_data.csv'")
        print(f"總筆數: {len(all_df)} (PChome: {len(df_pchome)}, MOMO: {len(df_momo)})")
    else:
        print("\n⚠️ 兩邊都沒抓到資料，請檢查網路或錯誤訊息。")