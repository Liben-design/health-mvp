import asyncio
import random
import pandas as pd
import os
import re
import json
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
import google.generativeai as genai

# 注意：請確保環境變數 GOOGLE_API_KEY 已設定，或在此處直接填入您的 Key
# 如果您已在終端機設定 export GOOGLE_API_KEY="..."，這行會自動讀取
# 如果沒有，請將下方的 "AIzaSy..." 替換為您真實的 API Key
if "GOOGLE_API_KEY" not in os.environ:
    os.environ["GOOGLE_API_KEY"] = "AIzaSy..."  # <--- 請在此貼上您的真實 API Key

async def extract_highlights_with_llm(html_content):
    """
    使用 LLM 分析網頁內容，提取產品核心亮點。
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 1. 清洗 HTML：移除無關的標籤以減少 Token 使用並降低雜訊
    for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'noscript', 'iframe', 'svg', 'button', 'input']):
        tag.decompose()
        
    # 2. 取得主要文字內容 (限制長度以免超過 Token 上限，通常產品重點在前 10000 字元內)
    text_content = soup.get_text(separator='\n', strip=True)[:10000] 

    # 3. 定義 LLM Prompt (依據您的需求客製化)
    prompt = f"""
    你是一位專業的營養師與數據分析師。請分析以下產品網頁內容，並提取產品的『核心亮點』。
    
    網頁內容摘要：
    {text_content}
    
    任務要求：
    1. 找出該產品的『核心亮點』。這通常包含：專利成分、原料來源、認證(如IFOS, SGS)、加工型態(如rTG, 游離型)、或是針對特定族群的設計。
    2. 請將其整理成 3-5 個簡短的關鍵短句（如：『採用 FloraGLO® 游離型葉黃素』、『84% 高濃度 rTG 魚油』）。
    3. 自動移除描述中的廣告詞（如「超值特惠」、「手刀快搶」、「限時下殺」），只保留技術規格與產品優勢。
    4. 請以 JSON 格式輸出，包含 'product_name' (產品名稱) 和 'product_highlights' (以分號分隔的亮點字串) 兩個欄位。
    
    輸出範例：
    {{
        "product_name": "視易適葉黃素",
        "product_highlights": "游離型葉黃素15mg;添加蝦紅素與智利酒果;FloraGLO®專利原料;全素可食"
    }}
    """

    try:
        # 檢查 API Key
        if "GOOGLE_API_KEY" not in os.environ:
            print("⚠️ 未設定 GOOGLE_API_KEY，跳過 AI 分析")
            return {"product_name": "Unknown", "product_highlights": ""}

        # 設定 Gemini (使用 gemini-1.5-flash 模型，速度快且支援 JSON mode)
        genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
        model = genai.GenerativeModel('gemini-1.5-flash', generation_config={"response_mime_type": "application/json", "temperature": 0.2})
        
        # 呼叫 API
        full_prompt = f"You are a helpful assistant that extracts structured product data from HTML text.\n\n{prompt}"
        response = await model.generate_content_async(full_prompt)

        # 監控 Token 使用量
        if response.usage_metadata:
            print(f"   📊 Token 使用量: 輸入 {response.usage_metadata.prompt_token_count} + 輸出 {response.usage_metadata.candidates_token_count} = 總計 {response.usage_metadata.total_token_count}")
        
        result = json.loads(response.text)
        return result
    except Exception as e:
        print(f"LLM 分析失敗: {e}")
        # 回傳預設空值以免程式崩潰
        return {"product_name": "Unknown", "product_highlights": ""}

async def random_sleep(min_sec=3, max_sec=7):
    """異步等待一個隨機的秒數，模擬真人停頓。"""
    sleep_time = random.uniform(min_sec, max_sec)
    # print(f"Simulating human behavior: waiting for {sleep_time:.2f} seconds...")
    await asyncio.sleep(sleep_time)

def calculate_unit_price(title, price, description=""):
    """從標題計算總顆粒數與單位價格 (針對營養師輕食優化)"""
    if not isinstance(title, str): return None, 0
    unit_count, bundle_size = None, 1
    
    # 1. 尋找單品數量 (優先級：描述中的明確定義 > 標題 > 描述中的推測)
    
    # 策略 A: 描述中的明確定義 (例如 "每盒 60 顆", "內容量：30條")
    if description:
        spec_match = re.search(r'(?:每盒|每瓶|內容量|規格|容量)[：:\s]*(\d+)\s*[粒顆錠包條入]', description)
        if spec_match:
            unit_count = int(spec_match.group(1))

    # 策略 B: 標題中的數量
    if not unit_count:
        count_regex = r'(\d+)\s*[粒顆錠包條入]'
        match = re.search(count_regex, title)
        if match: 
            unit_count = int(match.group(1))

    # 策略 C: 描述中的推測 (找最大的數字，通常總數 > 每日食用量)
    if not unit_count and description:
        # 找出所有 "數字 + 單位" 的組合
        matches = re.findall(r'(\d+)\s*[粒顆錠包條入]', description)
        if matches:
            # 過濾掉小於 10 的數字 (假設單品數量通常 >= 10，避開 "每日2顆" 這種資訊)
            candidates = [int(m) for m in matches if int(m) >= 10]
            if candidates:
                unit_count = max(candidates) # 取最大值最保險

    # 2. 尋找組數 (Bundle Size)
    # 匹配 x3, *3, 3入, 3盒組
    bundle_match = re.search(r'[xX*]\s*(\d{1,2})\b', title)
    if bundle_match:
        bundle_size = int(bundle_match.group(1))
    else:
        # 匹配 "3入", "3件組", "3盒組"
        bundle_match = re.search(r'[\s\uff0c\(\uff08](\d{1,2})\s*[入件組盒]', title)
        if bundle_match: bundle_size = int(bundle_match.group(1))
    
    # 防呆：如果組數大於 10 且與單品數量相同，極可能是誤判
    if unit_count and bundle_size > 10 and unit_count == bundle_size:
        bundle_size = 1
        
    if unit_count:
        total_count = unit_count * bundle_size
        u_price = round(price / total_count, 2) if price else 0
        return total_count, u_price
    return None, 0

def extract_tags(text):
    """從文本中提取產品標籤"""
    tags = []
    if not isinstance(text, str): return ""
    
    # 葉黃素/護眼
    if re.search(r"游離型|Free form", text, re.IGNORECASE): tags.append("✅游離型")
    if re.search(r"FloraGLO", text, re.IGNORECASE): tags.append("💎FloraGLO")
    if re.search(r"10[:：]2", text): tags.append("⚖️10:2比例")
    
    # 魚油
    if re.search(r"Omega-?3", text, re.IGNORECASE): tags.append("🐟Omega-3")
    if re.search(r"rTG", text, re.IGNORECASE): tags.append("🧬rTG型")
    if re.search(r"IFOS", text, re.IGNORECASE): tags.append("🏆IFOS認證")
    if re.search(r"80%|84%|90%", text): tags.append("📈高濃度")

    # 益生菌/酵素
    if re.search(r"益生菌|乳酸菌", text): tags.append("🦠益生菌")
    if re.search(r"300億|260億|1000億", text): tags.append("🔢高菌數")
    if re.search(r"保證菌數", text): tags.append("🛡️保證菌數")
    if re.search(r"無添加", text): tags.append("🌿無添加")

    # 認證
    if re.search(r"SNQ", text, re.IGNORECASE): tags.append("🏅SNQ認證")
    if re.search(r"SGS", text, re.IGNORECASE): tags.append("🛡️SGS檢驗")
    if re.search(r"A\.A\. Clean Label", text, re.IGNORECASE): tags.append("🌱潔淨標章")
    
    return " ".join(tags) if tags else ""

async def scrape_dietician_all_products():
    """
    批量抓取營養師輕食所有產品資料。
    """
    list_url = "https://www.dietician.com.tw/"
    base_url = "https://www.dietician.com.tw"
    all_data = []
    
    headless_mode = True 

    async with async_playwright() as p:
        print(f"啟動瀏覽器 (Headless: {headless_mode})...")
        browser = await p.chromium.launch(headless=headless_mode)
        
        # --- 步驟 1: 取得所有產品連結 ---
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        await stealth_async(page)

        print(f"正在前往首頁抓取選單連結: {list_url}")
        await page.goto(list_url, wait_until='networkidle', timeout=60000)
        await random_sleep(2, 3)

        # 滾動頁面確保載入
        print("正在滾動頁面以載入列表...")
        for _ in range(3):
            await page.evaluate('window.scrollBy(0, window.innerHeight)')
            await asyncio.sleep(1)

        # 解析連結
        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        
        product_links = set()
        current_url = page.url

        for a in soup.find_all('a', href=True):
            href = a['href']
            full_link = urljoin(current_url, href)
            
            # 篩選條件：包含 /products/item/ (根據使用者提供的範例連結結構)
            if '/products/item/' in full_link and base_url in full_link:
                product_links.add(full_link)
        
        links = list(product_links)
        print(f"共發現 {len(links)} 個不重複的產品連結。")
        
        await context.close()
        context = None
        page = None

        # --- 步驟 2: 批量抓取詳情 ---
        for i, link in enumerate(links):
            retries = 0
            max_retries = 2
            success = False

            while retries <= max_retries and not success:
                # 每 30 筆請求預防性重置 Context
                if context is None or (i > 0 and i % 30 == 0 and retries == 0):
                    if context:
                        print(f"\n--- 已處理 {i} 筆資料，啟動預防性冷卻與環境重置 ---")
                        print("冷卻 20 秒...")
                        await asyncio.sleep(20)
                        await context.close()
                    
                    print("正在建立新的瀏覽器環境（更換身份）...")
                    context = await browser.new_context(
                        viewport={'width': 1920, 'height': 1080},
                        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
                    )
                    page = await context.new_page()
                    await stealth_async(page)

                if retries > 0:
                    print(f"\n[{i+1}/{len(links)}] 正在重試: {link} (第 {retries} 次重試)")
                else:
                    print(f"\n[{i+1}/{len(links)}] 正在處理: {link}")
            
                try:
                    await page.goto(link, wait_until='networkidle', timeout=60000)
                    await random_sleep(3, 7) # 隨機等待 3-7 秒

                    # 等待價格相關文字出現，確保動態內容已載入
                    try:
                        await page.locator('body').filter(has_text="NT$").first.wait_for(timeout=5000)
                    except:
                        pass

                    # 等待關鍵元素 (價格或標題)
                    try:
                        await page.locator('h1').first.wait_for(state='visible', timeout=10000)
                    except:
                        print("等待標題超時，嘗試直接解析...")

                    content = await page.content()
                    soup = BeautifulSoup(content, 'html.parser')

                    # 1. 產品名稱
                    h1 = soup.find('h1')
                    name = h1.get_text(strip=True) if h1 else ""

                    # 檢查是否被封鎖
                    if "403" in name or "Forbidden" in name:
                        raise Exception(f"偵測到封鎖頁面 (Title: {name})")

                    # 2. 價格解析 (多重策略)
                    price_text_all = soup.get_text()
                    prices = []
                    original_price_val = 0
                    special_price_val = 0
                    
                    # 策略 A: JSON-LD (最準確，營養師輕食有使用)
                    json_ld = soup.find('script', type='application/ld+json')
                    if json_ld:
                        try:
                            data = json.loads(json_ld.string)
                            # 處理可能的列表或單一物件
                            if isinstance(data, list): data = data[0]
                            
                            if data.get('@type') == 'Product':
                                if not name: name = data.get('name', "Unknown")
                                offers = data.get('offers', {})
                                if isinstance(offers, dict):
                                    p = offers.get('price')
                                    if p:
                                        special_price_val = int(float(p))
                                        original_price_val = special_price_val # 暫時設為相同
                        except:
                            pass

                    # 策略 B: Meta Tags (備用)
                    meta_price = soup.find("meta", property="product:price:amount") or \
                                 soup.find("meta", property="og:price:amount")
                    if not special_price_val and meta_price and meta_price.get("content"):
                        try:
                            special_price_val = int(float(meta_price["content"]))
                            original_price_val = special_price_val
                        except:
                            pass

                    # 策略 C: 內文正則搜索 (最後手段)
                    if not special_price_val:
                        matches = re.findall(r'(?:NT\$?|\$)\s*(\d{1,3}(?:,\d{3})*|\d+)', price_text_all, re.IGNORECASE)
                        for m in matches:
                            try:
                                prices.append(int(m.replace(',', '')))
                            except:
                                pass
                        if prices:
                            prices = sorted(list(set(prices)))
                            if len(prices) > 1:
                                original_price_val = prices[-1]
                                special_price_val = prices[0]
                            else:
                                original_price_val = prices[0]
                                special_price_val = prices[0]
                    
                    if not name: name = "Unknown"

                    # 3. 圖片
                    image_url = ""
                    og_img = soup.find("meta", property="og:image")
                    if og_img and og_img.get("content"):
                        image_url = urljoin(base_url, og_img["content"])
                    
                    # 4. 規格與標籤
                    # 抓取主要內容區塊
                    desc_text = ""
                    # 優先抓取 .description (營養師輕食的規格通常在這裡)
                    for selector in [".description", ".product-detail", ".content", "main"]:
                        elements = soup.select(selector)
                        for el in elements:
                            desc_text += el.get_text(" ", strip=True) + " "
                    
                    full_text_for_analysis = name + " " + desc_text
                    tags = extract_tags(full_text_for_analysis)
                    total_count, unit_price = calculate_unit_price(name, special_price_val, desc_text)
                    
                    # 5. AI 亮點分析
                    print("   🤖 正在呼叫 AI 進行語義分析...")
                    ai_result = await extract_highlights_with_llm(content)
                    highlights = ai_result.get("product_highlights", "")

                    print(f"成功抓取: {name} | 特價: {special_price_val} | 規格: {total_count} | 標籤: '{tags}' | 亮點: {highlights[:20]}...")

                    all_data.append({
                        "product_name": name,
                        "original_price": original_price_val,
                        "special_price": special_price_val,
                        "total_count": total_count,
                        "unit_price": unit_price,
                        "tags": tags,
                        "product_highlights": highlights,
                        "image_url": image_url,
                        "product_url": link
                    })
                    
                    success = True

                except Exception as e:
                    if "403" in str(e) or "Forbidden" in str(e):
                        print(f"被封鎖或 403 錯誤: {e}")
                        retries += 1
                        if retries <= max_retries:
                            print("啟動冷卻機制：等待 30 秒後重試...")
                            await asyncio.sleep(30)
                            if context: await context.close()
                            context = None
                        else:
                            print(f"放棄此連結 {link}")
                    else:
                        print(f"抓取失敗 {link}: {e}")
                        break
        
        await browser.close()

    # 存檔
    if all_data:
        if not os.path.exists('data'):
            os.makedirs('data')
        df = pd.DataFrame(all_data)
        output_path = 'data/d2c_dietician_products.csv'
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"\n全部完成！共 {len(df)} 筆資料已儲存至 {output_path}")
    else:
        print("\n未抓取到任何資料。")

if __name__ == '__main__':
    asyncio.run(scrape_dietician_all_products())