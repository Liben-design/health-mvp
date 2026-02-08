import asyncio
import re
import random
from urllib.parse import urlparse
from playwright.async_api import async_playwright
try:
    from playwright_stealth import stealth_async
except Exception:
    # Fallback when playwright_stealth is not available in the environment
    async def stealth_async(page):
        return None

class SerpDiscovery:
    """
    SERP (Search Engine Results Page) 偵察模組
    負責搜尋關鍵字並過濾出潛在的 D2C 品牌官網。
    """
    def __init__(self):
        # 黑名單：排除電商平台、媒體、論壇、政府機構等非 D2C 網站
        self.blacklisted_domains = [
            "momo.com.tw", "pchome.com.tw", "shopee.tw", "yahoo.com", 
            "yahoo.com.tw", "books.com.tw", "rakuten.com.tw", "etmall.com.tw", "friDay.tw",
            "biggo.com.tw", "feebee.com.tw",
            "ptt.cc", "dcard.tw", "mobile01.com", "pixnet.net", "canceraway.com",
            "facebook.com", "instagram.com", "youtube.com", "wikipedia.org",
            "gov.tw", "edu.tw", "commonhealth.com.tw", "heho.com.tw",
            "edh.tw", "health.udn.com", "top1health.com"
        ]
        # 隨機 User-Agent 列表
        self.user_agents = [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
        ]

    def is_valid_d2c_domain(self, url):
        """SmartFilter: 判斷是否為潛在的 D2C 官網"""
        try:
            domain = urlparse(url).netloc.lower()
            # 移除 www. 前綴以便比對
            if domain.startswith("www."):
                domain = domain[4:]
            
            # 檢查黑名單
            for blocked in self.blacklisted_domains:
                if blocked in domain:
                    return False
            return True
        except:
            return False

    async def search_google(self, keyword, pages=10, results_per_page=10):
        """
        使用 Playwright 模擬瀏覽器搜尋 Google，規避簡單的爬蟲檢測。
        """
        print(f"🕵️ [SERP] 正在搜尋: {keyword} ...")
        results = set()
        
        async with async_playwright() as p:
            # 加入 args 降低被自動化偵測的機率
            # 改為 headless=False (有頭模式)，讓瀏覽器視窗彈出，大幅降低被 Google 封鎖機率，並允許人工驗證
            browser = await p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent=random.choice(self.user_agents)
            )
            page = await context.new_page()
            await stealth_async(page)

            try:
                for page_index in range(pages):
                    start = page_index * results_per_page
                    # 前往 Google 搜尋
                    # 加入 hl=zh-TW 強制中文介面，避免結構差異
                    await page.goto(
                        f"https://www.google.com/search?q={keyword}&num={results_per_page}&start={start}&hl=zh-TW",
                        wait_until="domcontentloaded"
                    )
                    
                    # 等待搜尋結果容器出現 (最多等 8 秒)
                    try:
                        await page.wait_for_selector("#search", timeout=8000)
                    except:
                        print(f"⚠️ [SERP] 等待搜尋結果超時，可能遇到 Captcha")
                        print("⏳ 偵測到異常，暫停 20 秒供人工排除 (請在彈出的瀏覽器視窗中完成驗證)...")
                        # 給予人工驗證時間
                        await asyncio.sleep(20)
                        
                        # 重試等待
                        try:
                            await page.wait_for_selector("#search", timeout=5000)
                        except:
                            await page.screenshot(path=f"debug_serp_error_{keyword}.png")

                    await asyncio.sleep(3) # 額外等待 JS 渲染

                    # 抓取搜尋結果連結 - 使用更寬鬆的選擇器
                    # 改為抓取 #search 區域內所有帶有 http 的連結，不再依賴 div.g
                    links = await page.locator("#search a[href^='http']").all()
                    
                    for link in links:
                        href = await link.get_attribute("href")
                        if href and href.startswith("http") and "google.com" not in href:
                            if self.is_valid_d2c_domain(href):
                                # 只保留首頁或根網域，方便後續 Sitemap 解析
                                parsed = urlparse(href)
                                root_url = f"{parsed.scheme}://{parsed.netloc}"
                                results.add(root_url)

                    # 模擬真人翻頁停留，避免觸發驗證
                    await asyncio.sleep(random.uniform(5, 8))
            
            except Exception as e:
                print(f"❌ [SERP] 搜尋失敗: {e}")
            finally:
                await browser.close()
        
        print(f"✅ [SERP] 找到 {len(results)} 個潛在 D2C 網域")
        return list(results)

# 測試用
if __name__ == "__main__":
    finder = SerpDiscovery()
    domains = asyncio.run(finder.search_google("葉黃素 推薦", pages=10, results_per_page=10))
    print(domains)
