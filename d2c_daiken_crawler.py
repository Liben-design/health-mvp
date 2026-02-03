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
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
        )
        
        # --- 步驟 1: 取得所有產品連結 ---
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
        
        # --- 步驟 2: 批量抓取詳情 ---
        for i, link in enumerate(links):
            print(f"\n[{i+1}/{len(links)}] 正在處理: {link}")
            
            try:
                # 前往產品頁
                await page.goto(link, wait_until='networkidle', timeout=60000)
                await random_sleep(2, 4) # 隨機等待，避免被封鎖

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

                # 價格
                original_price_tag = soup.find(string=re.compile("建議售價"))
                original_price_text = original_price_tag.parent.get_text() if original_price_tag else ""
                
                special_price_tag = soup.find(string=re.compile("優惠價"))
                special_price_text = special_price_tag.parent.get_text() if special_price_tag else ""

                op_match = re.search(r'\d[\d,]*', original_price_text)
                original_price = op_match.group().replace(',', '') if op_match else "0"
                
                sp_match = re.search(r'\d[\d,]*', special_price_text)
                special_price = sp_match.group().replace(',', '') if sp_match else "0"

                # 圖片 (優先使用 og:image 策略)
                image_url = ""
                og_img = soup.find("meta", property="og:image")
                if og_img and og_img.get("content"):
                    image_url = og_img["content"]

                print(f"成功抓取: {name} | 特價: {special_price}")
                
                all_data.append({
                    "product_name": name,
                    "original_price": original_price,
                    "special_price": special_price,
                    "image_url": image_url,
                    "product_url": link
                })

            except Exception as e:
                print(f"抓取失敗 {link}: {e}")
        
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