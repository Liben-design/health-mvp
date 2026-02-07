import asyncio
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
from .base_scraper import BaseScraper

class DaikenScraper(BaseScraper):
    def __init__(self):
        # 初始化父類別，指定輸出檔案路徑
        super().__init__("data/d2c_daiken_all_products.csv")
        self.list_url = "https://www.daikenshop.com/allgoods.php"
        self.base_url = "https://www.daikenshop.com"

    async def run(self):
        print(f"🚀 [DaikenScraper] 啟動爬蟲...")
        
        async with async_playwright() as p:
            # 啟動瀏覽器 (使用父類別定義的 User-Agent)
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=random.choice(self.user_agents),
                viewport={'width': 1920, 'height': 1080}
            )
            page = await context.new_page()
            await stealth_async(page)

            # --- 階段 1: 抓取產品列表 ---
            print(f"🔗 前往列表頁: {self.list_url}")
            await page.goto(self.list_url, wait_until='networkidle')
            
            # 處理 Cookie 同意按鈕
            try:
                if await page.locator('text="同意"').count() > 0:
                    await page.locator('text="同意"').first.click()
            except: pass

            # 滾動頁面確保載入
            for _ in range(3):
                await page.evaluate('window.scrollBy(0, window.innerHeight)')
                await asyncio.sleep(1)

            # 解析所有產品連結
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            links = []
            for a in soup.find_all('a', href=True):
                if 'product.php?code=' in a['href']:
                    links.append(urljoin(self.base_url, a['href']))
            
            links = list(set(links))
            print(f"📊 發現 {len(links)} 個產品連結")

            # --- 階段 2: 遍歷詳情頁 ---
            for i, link in enumerate(links):
                print(f"   [{i+1}/{len(links)}] 處理: {link}")
                try:
                    await page.goto(link, wait_until='networkidle', timeout=60000)
                    await self.random_sleep(2, 4)
                    
                    # 解析詳情
                    content = await page.content()
                    soup = BeautifulSoup(content, 'html.parser')
                    
                    # 提取資料
                    h1 = soup.find('h1')
                    title = h1.get_text(strip=True) if h1 else "Unknown"
                    
                    # 價格處理
                    price_tag = soup.find(string=re.compile("優惠價"))
                    price_text = price_tag.parent.get_text() if price_tag else "0"
                    price = int(re.sub(r'[^\d]', '', price_text) or 0)
                    
                    # 圖片 (優先使用 og:image)
                    og_img = soup.find("meta", property="og:image")
                    image_url = og_img["content"] if og_img else ""
                    
                    # 描述與規格 (用於計算單價與提取標籤)
                    desc_text = ""
                    for selector in [".product-description", ".detail_content"]:
                        for el in soup.select(selector):
                            desc_text += el.get_text(" ", strip=True)
                    
                    # 使用父類別的工具函式
                    total_count, unit_price = self.calculate_unit_price(title, price, desc_text)
                    tags = self.extract_tags(title + " " + desc_text)

                    # 加入資料列表
                    self.data.append({
                        "source": "大研生醫官網",
                        "brand": "大研生醫",
                        "title": title,
                        "price": price,
                        "unit_price": unit_price,
                        "url": link,
                        "image_url": image_url,
                        "product_highlights": "", # 大研暫無 AI 分析
                        "total_count": total_count,
                        "tags": tags
                    })

                except Exception as e:
                    print(f"❌ 抓取失敗 {link}: {e}")

            await browser.close()
            
            # 最後統一存檔
            self.save_to_csv()

# 讓此檔案可直接執行測試
if __name__ == "__main__":
    scraper = DaikenScraper()
    asyncio.run(scraper.run())
