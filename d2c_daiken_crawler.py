import asyncio
import random
import pandas as pd
import os
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

async def random_sleep(min_sec=2, max_sec=5):
    """異步等待一個隨機的秒數，模擬真人停頓。"""
    sleep_time = random.uniform(min_sec, max_sec)
    # print(f"Simulating human behavior: waiting for {sleep_time:.2f} seconds...")
    await asyncio.sleep(sleep_time)

def calculate_unit_price(title, price, description=""):
    """從標題計算總顆粒數與單位價格"""
    if not isinstance(title, str) or not price: return None, 0
    unit_count, bundle_size = None, 1
    
    # 1. 尋找單品數量 (優先查標題，若無則查描述)
    # 排除 "30包入" 這種寫法造成的誤判，先找純數量詞
    count_regex = r'(\d+)\s*[粒顆錠包]'
    match = re.search(count_regex, title)
    if match: 
        unit_count = int(match.group(1))
    
    # 若標題沒找到，嘗試從描述中找，但優先尋找明確的 "內容量/規格" 標示
    if not unit_count and description:
        spec_match = re.search(r'(?:內容量|規格)[：:]\s*(\d+)\s*[粒顆錠包]', description)
        if spec_match:
            unit_count = int(spec_match.group(1))
        else:
            # 最後手段：搜尋描述中出現的第一個數量 (風險較高，但因為已過濾雜訊區塊，相對安全)
            match = re.search(count_regex, description)
            if match: unit_count = int(match.group(1))

    # 2. 尋找組數 (Bundle Size)
    # 使用更嚴格的 Regex 避免匹配到 "30包" 中的 30
    # 匹配 x3, *3, 3入 (通常組數不會太大，限制 1-2 位數以防誤判)
    bundle_match = re.search(r'[xX*]\s*(\d{1,2})\b', title)
    if bundle_match:
        bundle_size = int(bundle_match.group(1))
    else:
        # 匹配 " 3入", " 3件組", "(3入)" (需確認前面有空格、括號或標點)
        bundle_match = re.search(r'[\s\uff0c\(\uff08](\d{1,2})\s*[入件組]', title)
        if bundle_match: bundle_size = int(bundle_match.group(1))
    
    # 防呆：如果組數大於 10 且與單品數量相同，極可能是誤判 (例如 "30包入" 被誤判為 count=30, bundle=30)
    if unit_count and bundle_size > 10 and unit_count == bundle_size:
        bundle_size = 1
        
    if unit_count:
        total_count = unit_count * bundle_size
        return total_count, round(price / total_count, 2)
    return None, 0

def extract_tags(text):
    """從文本中提取產品標籤"""
    tags = []
    if not isinstance(text, str): return ""
    
    # 葉黃素
    if re.search(r"游離型|Free form", text, re.IGNORECASE): tags.append("✅游離型")
    if re.search(r"FloraGLO", text, re.IGNORECASE): tags.append("💎FloraGLO")
    if re.search(r"10[:：]2", text): tags.append("⚖️10:2比例")
    
    # 魚油
    if re.search(r"Omega-?3", text, re.IGNORECASE): tags.append("🐟Omega-3")
    if re.search(r"rTG", text, re.IGNORECASE): tags.append("🧬rTG型")
    if re.search(r"IFOS", text, re.IGNORECASE): tags.append("🏆IFOS認證")
    if re.search(r"80%|84%", text): tags.append("📈高濃度")

    # 益生菌/酵素/其他
    if re.search(r"益生菌|乳酸菌", text): tags.append("🦠益生菌")
    if re.search(r"300億", text): tags.append("🔢300億")
    if re.search(r"UC-?II|UC2", text, re.IGNORECASE): tags.append("🦴UC-II")
    if re.search(r"瑪卡|Maca", text, re.IGNORECASE): tags.append("💪瑪卡")
    if re.search(r"Q10", text, re.IGNORECASE): tags.append("⚡Q10")

    # 通用認證
    if re.search(r"SNQ", text, re.IGNORECASE): tags.append("🏅SNQ認證")
    if re.search(r"SGS", text, re.IGNORECASE): tags.append("🛡️SGS檢驗")
    if re.search(r"Monde Selection", text, re.IGNORECASE): tags.append("🥇世界金獎")
    
    return " ".join(tags) if tags else ""

async def scrape_daiken_all_products():
    """
    批量抓取大研生醫所有產品資料。
    1. 訪問全部商品頁面取得連結。
    2. 遍歷連結，使用隱身模式與 og:image 策略抓取詳情。
    """
    list_url = "https://www.daikenshop.com/allgoods.php"
    base_url = "https://www.daikenshop.com"
    all_data = []
    
    # 開啟 Headless 模式以加快批量處理速度，並減少干擾
    headless_mode = True 

    async with async_playwright() as p:
        print(f"啟動瀏覽器 (Headless: {headless_mode})...")
        browser = await p.chromium.launch(headless=headless_mode)
        
        # --- 步驟 1: 取得所有產品連結 ---
        # 先建立一個初始 Context 用於抓取列表
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        await stealth_async(page) # 啟用隱身

        print(f"正在前往全部商品頁面: {list_url}")
        await page.goto(list_url, wait_until='networkidle', timeout=60000)
        await random_sleep(2, 3)

        # 處理 Cookie (列表頁也可能有)
        try:
            if await page.locator('text="同意"').count() > 0:
                await page.locator('text="同意"').first.click()
                print("已接受 Cookie。")
        except:
            pass

        # 滾動頁面確保載入所有商品
        print("正在滾動頁面以載入列表...")
        for _ in range(3):
            await page.evaluate('window.scrollBy(0, window.innerHeight)')
            await asyncio.sleep(1)

        # 解析連結
        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        
        product_links = set()
        # 抓取所有含有 product.php?code= 的連結
        for a in soup.find_all('a', href=True):
            href = a['href']
            if 'product.php?code=' in href:
                full_link = urljoin(base_url, href)
                product_links.add(full_link)
        
        links = list(product_links)
        print(f"共發現 {len(links)} 個不重複的產品連結。")
        
        # 關閉列表頁的 Context，準備進入批量抓取
        await context.close()
        context = None
        page = None

        # --- 步驟 2: 批量抓取詳情 ---
        for i, link in enumerate(links):
            retries = 0
            max_retries = 2
            success = False

            while retries <= max_retries and not success:
                # 每 30 筆請求預防性重置一次 Context，或者如果剛才失敗了(context被設為None)
                if context is None or (i > 0 and i % 30 == 0 and retries == 0):
                    if context:
                        print(f"\n--- 已處理 {i} 筆資料，啟動預防性冷卻與環境重置 ---")
                        print("冷卻 20 秒...")
                        await asyncio.sleep(20)
                        await context.close()
                        print("舊瀏覽器環境已關閉。")
                    
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
                    # 前往產品頁
                    await page.goto(link, wait_until='networkidle', timeout=60000)
                    await random_sleep(4, 7) # 再次稍微增加等待時間

                    # 再次檢查 Cookie (有時換頁會重跳)
                    try:
                        if await page.locator('text="同意"').count() > 0:
                            await page.locator('text="同意"').first.click(timeout=2000)
                    except:
                        pass

                    # 等待關鍵元素 (價格)，確保頁面載入完成
                    try:
                        await page.locator('text="建議售價"').first.wait_for(state='visible', timeout=10000)
                    except:
                        print("等待價格超時，嘗試直接解析...")

                    # 解析內容
                    content = await page.content()
                    soup = BeautifulSoup(content, 'html.parser')

                    # 產品名稱
                    h1 = soup.find('h1')
                    name = h1.get_text(strip=True) if h1 else "Unknown"

                    # 檢查是否被封鎖 (403)
                    if "403" in name or "Forbidden" in name or "Access Denied" in name:
                        raise Exception(f"偵測到封鎖頁面 (Title: {name})")

                    # 價格
                    original_price_tag = soup.find(string=re.compile("建議售價"))
                    original_price_text = original_price_tag.parent.get_text() if original_price_tag else ""
                    
                    special_price_tag = soup.find(string=re.compile("優惠價"))
                    special_price_text = special_price_tag.parent.get_text() if special_price_tag else "0"

                    op_match = re.search(r'\d[\d,]*', original_price_text)
                    original_price_val = int(op_match.group().replace(',', '')) if op_match else 0
                    
                    sp_match = re.search(r'\d[\d,]*', special_price_text)
                    special_price_val = int(sp_match.group().replace(',', '')) if sp_match else 0

                    # 圖片 (優先使用 og:image 策略)
                    image_url = ""
                    og_img = soup.find("meta", property="og:image")
                    if og_img and og_img.get("content"):
                        image_url = og_img["content"]
                    
                    # --- 新增：抓取規格 ---
                    # 抓取整個描述區塊用於分析
                    # 改進：只抓取產品描述相關的區塊，避免抓到頁首頁尾的 "9折", "5包" 等雜訊
                    desc_text = ""
                    content_selectors = [".product-description", ".detail_content", ".product_detail_content", "div.editor", ".product-intro", ".product-info-main"]
                    
                    for selector in content_selectors:
                        elements = soup.select(selector)
                        for el in elements:
                            desc_text += el.get_text(" ", strip=True) + " "
                    
                    # 組合標題與描述供分析
                    full_text_for_analysis = name + " " + desc_text

                    # 計算規格
                    tags = extract_tags(full_text_for_analysis)
                    total_count, unit_price = calculate_unit_price(name, special_price_val, desc_text)

                    print(f"成功抓取: {name} | 特價: {special_price_val} | 標籤: '{tags}'")

                    all_data.append({
                        "product_name": name,
                        "original_price": original_price_val,
                        "special_price": special_price_val,
                        "total_count": total_count,
                        "unit_price": unit_price,
                        "tags": tags,
                        "image_url": image_url,
                        "product_url": link
                    })
                    
                    success = True # 標記成功，跳出 while 迴圈

                except Exception as e:
                    if "403" in str(e) or "封鎖" in str(e) or "Forbidden" in str(e) or "Access Denied" in str(e):
                        print(f"被封鎖或 403 錯誤: {e}")
                        retries += 1
                        if retries <= max_retries:
                            print("啟動冷卻機制：等待 30 秒後重試...")
                            await asyncio.sleep(30)
                            if context:
                                await context.close()
                            context = None # 強制下次迴圈重建 Context
                        else:
                            print(f"放棄此連結 {link}，已達最大重試次數。")
                    else:
                        print(f"抓取失敗 {link}: {e}")
                        break # 其他錯誤不重試，避免無窮迴圈
        
        await browser.close()

    # 存檔
    if all_data:
        if not os.path.exists('data'):
            os.makedirs('data')
        df = pd.DataFrame(all_data)
        output_path = 'data/d2c_daiken_all_products.csv'
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"\n全部完成！共 {len(df)} 筆資料已儲存至 {output_path}")
    else:
        print("\n未抓取到任何資料。")

if __name__ == '__main__':
    asyncio.run(scrape_daiken_all_products())