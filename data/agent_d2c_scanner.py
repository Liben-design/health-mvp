import asyncio
import os
import json
import random
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
import google.generativeai as genai
from dotenv import load_dotenv

# 載入環境變數
script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # 回到專案根目錄
load_dotenv(os.path.join(script_dir, '.env'))

class AgentD2CScanner:
    """
    通用型 D2C 掃描 Agent
    不依賴特定 CSS Selector，而是抓取全頁文字後交由 LLM 提取結構化資料。
    """
    def __init__(self):
        self.api_key = os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            print("⚠️ [Agent] 未設定 GOOGLE_API_KEY，AI 分析將失效。")
        else:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash', generation_config={"response_mime_type": "application/json"})

    async def analyze_with_llm(self, html_content, url):
        """呼叫 Gemini 進行語義分析"""
        if not self.api_key: return {}

        soup = BeautifulSoup(html_content, 'html.parser')
        # 移除雜訊
        for tag in soup(['script', 'style', 'nav', 'footer', 'noscript', 'svg']):
            tag.decompose()
        text = soup.get_text(separator='\n', strip=True)[:15000] # 限制長度

        prompt = f"""
        你是一個專業的電商數據爬蟲。請分析以下產品頁面的 HTML 文字內容，並提取結構化資料。
        
        產品網址: {url}
        網頁內容:
        {text}

        請輸出 JSON 格式，包含以下欄位 (若找不到請填 null 或 0):
        - brand: 品牌名稱 (字串)
        - title: 產品完整名稱 (字串)
        - price: 目前售價 (整數，去除幣別符號)
        - unit_price: 平均單價 (浮點數，若無法計算填 0)
        - total_count: 總顆數/包數 (整數，若無法判斷填 0)
        - product_highlights: 產品亮點 (字串，以分號分隔，提取專利、認證、成分優勢等)
        """

        try:
            response = await self.model.generate_content_async(prompt)
            text = response.text
            
            # 清洗 Markdown 標記 (```json ... ```)
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            
            data = json.loads(text.strip())
            
            # 容錯：若 AI 回傳 List，取第一筆
            if isinstance(data, list):
                data = data[0] if data else {}
                
            return data
        except Exception as e:
            print(f"⚠️ [Agent] LLM 分析失敗: {e}")
            return {}

    async def scan_url(self, url):
        """掃描單一 URL"""
        print(f"🤖 [Agent] 正在掃描: {url}")
        data = None
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            await stealth_async(page)

            try:
                # 隨機延遲，模擬真人
                await asyncio.sleep(random.uniform(1, 3))
                
                response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                
                # 處理 403/429 重試邏輯 (簡單版)
                if response.status in [403, 429]:
                    print(f"⚠️ [Agent] 遇到 {response.status}，等待 10 秒後重試...")
                    await asyncio.sleep(10)
                    await page.reload()
                
                # [New] 等待價格元素渲染 (針對 Vitabox 等動態網站)
                try:
                    # 嘗試等待常見的價格符號或 class
                    await page.wait_for_selector("text=NT$", timeout=3000)
                except:
                    pass # 若沒等到也不要報錯，繼續執行
                
                # [New] 第二道濾網 - 動態驗身 (Smart Filter)
                # 檢查 og:type 或 JSON-LD 是否標記為 Product，避免浪費 AI Token 分析非產品頁
                is_product = await page.evaluate("""() => {
                    const ogType = document.querySelector('meta[property="og:type"]')?.content;
                    const jsonLd = Array.from(document.querySelectorAll('script[type="application/ld+json"]'))
                                        .map(el => el.innerText)
                                        .join('');
                    return ogType === 'product' || jsonLd.includes('"@type": "Product"') || jsonLd.includes('"@type":"Product"');
                }""")
                
                if not is_product:
                    print(f"⏩ [Agent] 跳過非產品頁面 (無 Product 標記): {url}")
                    return None

                # 滾動頁面觸發 Lazy Load
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)

                # 抓取基礎資料 (圖片與 HTML)
                content = await page.content()
                
                # 嘗試抓取 og:image
                image_url = await page.get_attribute("meta[property='og:image']", "content")
                if not image_url:
                    # Fallback: 找第一張大圖
                    imgs = await page.locator("img").all()
                    for img in imgs:
                        src = await img.get_attribute("src")
                        if src and "http" in src and ("jpg" in src or "png" in src):
                            image_url = src
                            break
                
                # LLM 分析
                ai_data = await self.analyze_with_llm(content, url)
                
                if ai_data:
                    # 整合資料
                    data = {
                        "source": "D2C_Hunter", # 標記來源
                        "brand": ai_data.get("brand", "Unknown"),
                        "title": ai_data.get("title", "Unknown"),
                        "price": ai_data.get("price", 0),
                        "unit_price": ai_data.get("unit_price", 0),
                        "total_count": ai_data.get("total_count", 0),
                        "url": url,
                        "image_url": image_url or "",
                        "product_highlights": ai_data.get("product_highlights", "")
                    }
                    print(f"✅ [Agent] 成功提取: {data['title']} (${data['price']})")
                
            except Exception as e:
                print(f"❌ [Agent] 掃描失敗 {url}: {e}")
            finally:
                await browser.close()
        
        return data

    async def scan_batch(self, urls):
        """批次掃描"""
        results = []
        # 限制並發數，避免被封鎖
        semaphore = asyncio.Semaphore(3) 
        
        async def sem_scan(u):
            async with semaphore:
                return await self.scan_url(u)

        tasks = [sem_scan(u) for u in urls]
        scanned = await asyncio.gather(*tasks)
        
        # 過濾失敗的結果
        for res in scanned:
            if res: results.append(res)
        return results