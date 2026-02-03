
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
    print(f"Simulating human behavior: waiting for {sleep_time:.2f} seconds...")
    await asyncio.sleep(sleep_time)

async def scrape_daiken_lutein():
    """
    使用 Playwright-stealth 腳本，抓取大研生醫葉黃素頁面的產品資訊。
    - 產品名稱
    - 原價
    - 特價
    - 圖片 URL
    """
    url = "https://www.daikenshop.com/product.php?code=0000000000028"
    product_data = []
    
    # --- 調試模式開關 ---
    # 將 headless_mode 改為 False，即可在執行時看到瀏覽器畫面。
    headless_mode = True 

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless_mode)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
        )
        page = await context.new_page()

        # 核心步驟：應用 stealth.js 隱身插件
        await stealth_async(page)

        print(f"Navigating to Daiken Lutein page: {url}")
        try:
            await page.goto(url, wait_until='networkidle', timeout=60000)
            await random_sleep()

            # 優先處理 Cookie 同意橫幅
            try:
                print("Checking for and accepting cookie consent banner...")
                # 使用文本選擇器定位「同意」按鈕，更具彈性
                await page.locator('text="同意"').click(timeout=5000)
                print("Cookie consent banner accepted.")
                await random_sleep(1, 2) # 點擊後短暫等待
            except Exception:
                print("Cookie consent banner not found or already accepted. Continuing...")

            # 模擬向下滾動，觸發 Lazy-load 內容
            print("Simulating scrolling to trigger lazy-loaded content...")
            for i in range(3):
                await page.evaluate(f'window.scrollBy(0, window.innerHeight * {i/2})')
                await random_sleep(1, 2)
            
            await page.evaluate('window.scrollTo(0, 0)') # 滾動回頂部以確保元素可見
            print("Page scrolled. Waiting for content to be visible...")

            # 增加明確等待，確保關鍵元素已渲染
            print("Waiting for product title text to be visible...")
            # 改用更穩定的文本選擇器，並用 .first 確保唯一性
            title_locator = page.locator('text="視易適葉黃素"').first
            await title_locator.wait_for(state='visible', timeout=30000)
            print("Product title is visible. Starting data extraction.")

            # 抓取價格元素可見性 (確保資料已加載)
            print("Waiting for price text to be visible...")
            await page.locator('text="建議售價"').first.wait_for(state='visible', timeout=10000)
            print("Price text is visible.")

            # --- 使用 BeautifulSoup 解析 HTML ---
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')

            # 抓取產品名稱 (嘗試 h1 或 fallback)
            product_name_tag = soup.find('h1')
            product_name = product_name_tag.get_text(strip=True) if product_name_tag else "Unknown Product"

            # 抓取價格
            original_price_tag = soup.find(string=re.compile("建議售價"))
            original_price_text = original_price_tag.parent.get_text() if original_price_tag else ""
            
            special_price_tag = soup.find(string=re.compile("優惠價"))
            special_price_text = special_price_tag.parent.get_text() if special_price_tag else ""

            # 清理價格文字 (使用正則表達式提取數字，更可靠)
            original_price_match = re.search(r'\d[\d,]*', original_price_text)
            original_price = original_price_match.group().replace(',', '') if original_price_match else "0"
            
            special_price_match = re.search(r'\d[\d,]*', special_price_text)
            special_price = special_price_match.group().replace(',', '') if special_price_match else "0"

            # 抓取圖片 URL - 策略優化
            # 優先嘗試從 Meta Tag (og:image) 抓取，這通常是最穩定且高畫質的來源，不需要等待元素渲染
            image_url = ""
            relative_img_url = ""
            
            og_image = soup.find("meta", property="og:image")
            if og_image and og_image.get("content"):
                relative_img_url = og_image["content"]
                print(f"Found image URL from og:image: {relative_img_url}")
            else:
                # Fallback: 如果沒有 og:image，嘗試從頁面元素抓取
                print("og:image not found. Trying to extract from visible element...")
                try:
                    # 使用 :visible 確保抓到可見圖片
                    img_locator = page.locator('.pic_box img:visible').first
                    await img_locator.wait_for(state='visible', timeout=5000)
                    relative_img_url = await img_locator.get_attribute('src')
                    print(f"Found relative image URL from element: {relative_img_url}")
                except Exception as img_error:
                    print(f"Warning: Could not extract image URL. Error: {img_error}")
                    relative_img_url = ""

            if relative_img_url:
                # 使用 urljoin 來正確處理相對路徑 (例如 ../)
                image_url = urljoin(page.url, relative_img_url)

            product_info = {
                'product_name': product_name.strip(),
                'original_price': int(original_price.strip()),
                'special_price': int(special_price.strip()),
                'image_url': image_url
            }
            product_data.append(product_info)
            
            print("\n--- Data Extracted Successfully ---")
            print(product_info)
            print("---------------------------------")


        except Exception as e:
            print(f"\n[ERROR] An error occurred during scraping: {e}")
            screenshot_path = 'debug_screenshot_daiken.png'
            await page.screenshot(path=screenshot_path)
            print(f"A screenshot has been saved to '{screenshot_path}' for debugging.")

        finally:
            print("Closing browser.")
            await browser.close()
    
    if product_data:
        # 確保 data 資料夾存在
        if not os.path.exists('data'):
            os.makedirs('data')
            
        output_path = 'data/d2c_daiken_data.csv'
        print(f"\nSaving data to '{output_path}'...")
        df = pd.DataFrame(product_data)
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"Data saved successfully to {output_path}")
    else:
        print("\nNo data was extracted. Please check the selectors or the webpage structure.")


if __name__ == '__main__':
    print("Starting the D2C Daiken stealth scraper...")
    asyncio.run(scrape_daiken_lutein())
