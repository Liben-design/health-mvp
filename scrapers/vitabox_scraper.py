import asyncio
import random
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
from .base_scraper import BaseScraper

class VitaboxScraper(BaseScraper):
    def __init__(self):
        # 1. 初始化父類別，指定這個品牌專屬的存檔路徑
        super().__init__("data/d2c_vitabox.csv")
        self.target_url = "https://shop.vitabox.com.tw/collections/all"

    async def random_mouse_move(self, page):
        """[Vitabox 專用] 模擬人類滑鼠隨機移動，繞過行為偵測"""
        width, height = 1920, 1080
        for _ in range(random.randint(3, 5)):
            x = random.randint(100, width - 100)
            y = random.randint(100, height - 100)
            await page.mouse.move(x, y, steps=random.randint(10, 25))
            await asyncio.sleep(random.uniform(0.1, 0.3))

    async def progressive_scroll(self, page):
        """[Vitabox 專用] 漸進式滾動，確保 Lazy Load 圖片載入"""
        print("🖱️ [Vitabox] 開始漸進式滾動...")
        last_height = await page.evaluate("document.body.scrollHeight")
        
        while True:
            scroll_amount = random.randint(400, 800)
            await page.mouse.wheel(0, scroll_amount)
            await self.random_sleep(1.5, 3.0) # 使用父類別的 random_sleep

            # 偶爾回滾
            if random.random() < 0.3:
                await page.mouse.wheel(0, -random.randint(50, 150))
                await asyncio.sleep(random.uniform(0.5, 1.0))

            new_height = await page.evaluate("document.body.scrollHeight")
            current_scroll = await page.evaluate("window.scrollY + window.innerHeight")
            
            if current_scroll >= new_height - 100:
                break
            last_height = new_height

    async def run(self):
        """實作父類別規定的 run 方法"""
        print(f"🚀 [VitaboxScraper] 啟動爬蟲...")
        
        async with async_playwright() as p:
            # 使用父類別定義的 User-Agents
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=random.choice(self.user_agents),
                viewport={"width": 1920, "height": 1080},
                locale="zh-TW"
            )
            page = await context.new_page()
            await stealth_async(page)

            print(f"🔗 前往: {self.target_url}")
            await page.goto(self.target_url, wait_until="domcontentloaded")
            
            # 執行 Vitabox 特有的擬人行為
            await self.random_mouse_move(page)
            await self.random_sleep(2, 4)
            await self.progressive_scroll(page)
            
            # 解析資料
            print("🔍 開始解析產品資料...")
            product_cards = await page.locator(".product-item, .product-card, .grid__item").all()
            
            # Fallback 機制
            if not product_cards:
                product_cards = await page.locator("a[href*='/products/']").all()

            print(f"📊 偵測到 {len(product_cards)} 個潛在產品")

            for card in product_cards:
                try:
                    # 標題
                    title_el = card.locator("h3, h4, .title, .product-title").first
                    if await title_el.count() == 0: continue
                    title = (await title_el.text_content()).strip()

                    # 價格
                    price_el = card.locator(".price, .money, span:has-text('NT$')").first
                    price_text = await price_el.text_content() if await price_el.count() > 0 else "0"
                    price = int(''.join(filter(str.isdigit, price_text)) or 0)

                    # 連結
                    tag_name = await card.evaluate("el => el.tagName.toLowerCase()")
                    if tag_name == 'a':
                        raw_url = await card.get_attribute("href")
                    else:
                        link_el = card.locator("a").first
                        raw_url = await link_el.get_attribute("href")
                    full_url = f"https://shop.vitabox.com.tw{raw_url}" if raw_url and raw_url.startswith("/") else raw_url

                    # 圖片
                    img_el = card.locator("img").first
                    raw_img_url = await img_el.get_attribute("src") or await img_el.get_attribute("data-src") or ""
                    image_url = f"https:{raw_img_url}" if raw_img_url.startswith("//") else raw_img_url

                    # 亮點 (簡單提取)
                    text_content = await card.text_content()
                    highlights = text_content.replace(title, "").replace(price_text, "").strip()[:50].replace("\n", ";")

                    # 2. 將資料加入父類別的 self.data 列表
                    # 注意：這裡不需要自己算 unit_price，也不用管 CSV 欄位順序，父類別會處理
                    self.data.append({
                        "source": "Vitabox",
                        "brand": "Vitabox",
                        "title": title,
                        "price": price,
                        "unit_price": 0, # 後續由 App 計算
                        "url": full_url,
                        "image_url": image_url,
                        "product_highlights": highlights,
                        "total_count": 0,
                        "tags": ""
                    })

                except Exception:
                    continue

            await browser.close()
            
            # 3. 最後呼叫父類別的存檔方法
            self.save_to_csv()

# 測試區塊
if __name__ == "__main__":
    scraper = VitaboxScraper()
    asyncio.run(scraper.run())
