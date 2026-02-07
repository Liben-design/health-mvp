import asyncio
import random
import pandas as pd
import os
from datetime import datetime
from playwright.async_api import async_playwright

# 嘗試匯入 playwright_stealth，若無則提醒安裝
try:
    from playwright_stealth import stealth_async
except ImportError:
    print("Error: 'playwright-stealth' module not found. Please install it using: pip install playwright-stealth")
    exit(1)

# ==========================================
# 設定與常數
# ==========================================
TARGET_URL = "https://shop.vitabox.com.tw/categories/featured-products"  # Vitabox 產品列表頁
OUTPUT_FILE = "data/d2c_vitabox.csv"
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0"
]

class VitaboxStealthCrawler:
    def __init__(self):
        self.data = []

    async def human_like_delay(self, min_seconds=2, max_seconds=5):
        """模擬人類隨機思考/閱讀時間"""
        delay = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(delay)

    async def random_mouse_move(self, page):
        """
        模擬人類滑鼠隨機移動
        繞過部分基於滑鼠軌跡的 Bot Detection
        """
        width = 1920
        height = 1080
        # 隨機生成 3-5 個移動點
        for _ in range(random.randint(3, 5)):
            x = random.randint(100, width - 100)
            y = random.randint(100, height - 100)
            # steps 讓移動有軌跡感，不是瞬間跳躍
            await page.mouse.move(x, y, steps=random.randint(10, 25))
            await asyncio.sleep(random.uniform(0.1, 0.3))

    async def progressive_scroll(self, page):
        """
        漸進式滾動 (Progressive Scrolling)
        確保 Lazy Load 圖片被觸發，並模擬人類閱讀行為
        (僅負責滾動當前頁面，分頁邏輯移至 run 方法處理)
        """
        print("🖱️ 開始漸進式滾動載入頁面...")
        
        last_height = await page.evaluate("document.body.scrollHeight")
        
        while True:
            # 隨機滾動距離 (模擬滾輪或 PageDown)
            scroll_amount = random.randint(400, 800)
            await page.mouse.wheel(0, scroll_amount)
            
            # 滾動後隨機停頓，模擬閱讀
            await self.human_like_delay(1.5, 3.0)
            
            # 偶爾往回滾一點點，增加真實感
            if random.random() < 0.3:
                await page.mouse.wheel(0, -random.randint(50, 150))
                await asyncio.sleep(random.uniform(0.5, 1.0))

            # 檢查是否到底
            new_height = await page.evaluate("document.body.scrollHeight")
            current_scroll = await page.evaluate("window.scrollY + window.innerHeight")
            
            # 如果目前的視窗底部已經接近頁面總高度，則停止
            if current_scroll >= new_height - 200:
                print("✅ 已滾動至頁面底部 (或已無更多頁面)")
                break
                
            # 如果高度沒有變化持續太久(可選邏輯)，這裡簡化為依賴 current_scroll
            last_height = new_height

    async def extract_product_data(self, page):
        """
        解析產品卡片資料
        使用較為寬鬆的 Selector 策略以適應改版
        """
        print("🔍 開始解析產品資料...")
        
        # 定位產品卡片：通常在 Collection 頁面會有特定的 Grid Item Class
        # 這裡嘗試抓取常見的 Shopify/Cyberbiz 結構
        # 策略：尋找包含 'product' 且有 'item' 或 'card' 的容器，或是直接找連結
        # product_cards = await page.locator(".product-item, .product-card, .grid__item").all()
        
        # Shopline 策略：直接抓取所有指向 /products/ 的 <a> 標籤
        # Shopline 的產品連結通常是 /products/product-slug
        product_cards = await page.locator("a[href*='/products/'], a[href*='/product/']").all()
        
        if not product_cards:
            print("⚠️ 未偵測到任何產品連結，嘗試等待更久...")
            # Fallback: 抓取所有包含價格的連結區塊
            product_cards = await page.locator("a[href*='/products/'], a[href*='/product/']").all()

        print(f"📊 偵測到 {len(product_cards)} 個潛在產品項目")

        for card in product_cards:
            try:
                # 1. Title
                title_el = card.locator("h3, h4, .title, .product-title").first
                # 如果找不到標題元素，嘗試直接讀取連結內的文字
                if await title_el.count() > 0:
                    title = await title_el.text_content()
                else:
                    title = await card.text_content()
                
                title = title.strip()
                # 過濾掉太短的標題 (可能是 "查看更多" 之類的按鈕)
                if len(title) < 2: continue
                
                # 過濾非保健食品 (盤子、提袋等)
                if any(keyword in title for keyword in ["瓷盤", "禮袋", "提袋", "購物袋"]):
                    continue

                # 2. Price
                # 優先找特價，若無則找原價
                price_el = card.locator(".price, .money, span:has-text('NT$')").first
                # 如果卡片內找不到價格，嘗試往上層找 (有時 a 標籤只是圖片，價格在兄弟元素)
                if await price_el.count() == 0:
                    # 嘗試找父層容器
                    parent = card.locator("..")
                    price_el = parent.locator(".price, .money, span:has-text('NT$')").first

                price_text = await price_el.text_content() if await price_el.count() > 0 else ""
                # 清洗價格: 去除 NT$, 逗號, 空白
                price = int(''.join(filter(str.isdigit, price_text)) or 0)

                # 3. URL
                # 如果 card 本身是 <a> 標籤
                raw_url = await card.get_attribute("href")
                
                full_url = f"https://shop.vitabox.com.tw{raw_url}" if raw_url.startswith("/") else raw_url

                # 4. Image
                img_el = card.locator("img").first
                raw_img_url = await img_el.get_attribute("src") or await img_el.get_attribute("data-src") or ""
                if raw_img_url.startswith("//"):
                    image_url = f"https:{raw_img_url}"
                elif raw_img_url.startswith("http"):
                    image_url = raw_img_url
                else:
                    image_url = ""

                # 去重檢查：避免同一個產品抓到兩次 (圖片連結和文字連結)
                if any(d['url'] == full_url for d in self.data):
                    continue

                # 5. Highlights (嘗試從卡片文字中提取非標題/價格的描述)
                text_content = await card.text_content()
                # 簡單過濾：把標題和價格扣掉剩下的字串當作潛在亮點 (這很粗略，但符合"嘗試抓取")
                highlights = text_content.replace(title, "").replace(price_text, "").strip()
                highlights = highlights.replace("\n", ";").strip()[:50] # 截斷避免過長

                item = {
                    "source": "Vitabox",
                    "brand": "Vitabox",
                    "title": title,
                    "price": price,
                    "unit_price": 0, # 依指示填 0
                    "url": full_url,
                    "image_url": image_url,
                    "product_highlights": highlights,
                    "total_count": "" # 暫空
                }
                self.data.append(item)
                # print(f"   Found: {title} | ${price}")

            except Exception as e:
                # 容錯：單一產品解析失敗不中斷整個爬蟲
                continue

    async def run(self):
        async with async_playwright() as p:
            # 隨機選取 User-Agent
            user_agent = random.choice(USER_AGENTS)
            
            # 啟動瀏覽器 (Headless=True 也可以，但 False 方便除錯且有時較不易被擋)
            browser = await p.chromium.launch(headless=True) 
            context = await browser.new_context(
                user_agent=user_agent,
                viewport={"width": 1920, "height": 1080},
                locale="zh-TW"
            )
            
            page = await context.new_page()
            
            # 應用 Stealth 插件
            await stealth_async(page)

            print(f"🚀 啟動隱身爬蟲，目標: {TARGET_URL}")
            try:
                # 改用 networkidle 確保動態內容載入完成
                await page.goto(TARGET_URL, wait_until="networkidle", timeout=60000)
            except Exception:
                print("⚠️ NetworkIdle 超時，嘗試繼續執行...")
            
            print(f"📄 當前頁面標題: {await page.title()}")

            # 執行擬人行為
            await self.random_mouse_move(page)
            
            while True:
                await self.human_like_delay(2, 4)
                await self.progressive_scroll(page)
                
                # 再次隨機移動滑鼠確保元素穩定
                await self.random_mouse_move(page)
                
                # 提取當前頁面資料
                await self.extract_product_data(page)

                # 檢查並處理下一頁 (Shopline 分頁結構)
                # 嘗試多種選擇器以確保能抓到按鈕
                next_selectors = [
                    "a[rel='next']",                      # 標準語義
                    "li.next a",                          # 常見 Bootstrap 結構
                    ".pagination .next a",                # 另一種結構
                    ".pagination-next a",                 # Shopline 變體
                    "a:has-text('下一頁')",               # 中文文字
                    "a:has-text('Next')",                 # 英文文字
                    "a:has(i.fa-angle-right)",            # FontAwesome 圖示
                    "a:has(i.fa-chevron-right)"           # 另一種圖示
                ]
                
                next_btn = None
                for selector in next_selectors:
                    btn = page.locator(selector).first
                    if await btn.count() > 0 and await btn.is_visible():
                        next_btn = btn
                        print(f"🔎 發現下一頁按鈕 (Selector: {selector})")
                        break
                
                if next_btn:
                    print("👉 點擊下一頁...")
                    # 點擊並等待頁面導航完成
                    await next_btn.click()
                    await page.wait_for_load_state("networkidle", timeout=60000)
                else:
                    print("✅ 已無下一頁，停止爬取")
                    break
            
            await browser.close()

    def save_csv(self):
        if not self.data:
            print("❌ 未抓取到任何資料。")
            return
            
        df = pd.DataFrame(self.data)
        
        # 確保目錄存在
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        
        df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
        print(f"💾 資料已儲存至: {OUTPUT_FILE} (共 {len(df)} 筆)")

if __name__ == "__main__":
    crawler = VitaboxStealthCrawler()
    asyncio.run(crawler.run())
    crawler.save_csv()
