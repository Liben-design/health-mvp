import asyncio
import os
import json
import random
import re
import html as html_lib
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from playwright_stealth import stealth_async
try:
    import google.generativeai as genai
except ImportError:
    genai = None

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        return False

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
        self.llm_timeout_seconds = int(os.environ.get("D2C_LLM_TIMEOUT", "15"))
        self.page_timeout_seconds = 30
        if not self.api_key or genai is None:
            if genai is None:
                print("⚠️ [Agent] 未安裝 google-generativeai，AI 分析將失效。")
            else:
                print("⚠️ [Agent] 未設定 GOOGLE_API_KEY，AI 分析將失效。")
        else:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash', generation_config={"response_mime_type": "application/json"})

    @staticmethod
    def _normalize_url(url):
        """容錯處理：支援純網址與 Markdown 格式 `[url](url)`。"""
        if not isinstance(url, str):
            return ""
        url = url.strip()
        md_match = re.search(r'\((https?://[^\s)]+)\)', url)
        if md_match:
            return md_match.group(1)
        raw_match = re.search(r'https?://[^\s\]]+', url)
        if raw_match:
            return raw_match.group(0)
        return url

    async def _wait_for_price_elements(self, page, url):
        """在 dump HTML 前先等待價格 DOM 渲染，提升動態站價格命中率。"""
        selector_candidates = [
            ".price",
            ".product-price",
            "div[class*='price']",
            ".price-regular .price",
            ".js-price .price"
        ]

        # Vitabox / Shopline 優先等待較精準的組合
        if "vitabox" in url or "shopline" in url:
            prioritized = ".same-price .price, .price-regular .price, .js-price .price, .product-price, .price"
            try:
                # 避免單頁等待過久導致整體 page timeout，被誤判為卡死
                await page.wait_for_selector(prioritized, state="attached", timeout=8000)
                return
            except:
                pass

        # 九五之丹：短等待價格區塊載入（避免太早抓到「已熱銷1000份」誤判為價格）
        if "95dan.com.tw" in (url or ""):
            try:
                await page.wait_for_selector("div.pro_dis_info", state="attached", timeout=5000)
                await page.wait_for_selector("div.pro_dis_info span.price", state="attached", timeout=5000)
            except:
                pass
            return

        # 通用 fallback：短等待嘗試，不命中就直接往下（避免單頁長時間卡住）
        for selector in selector_candidates:
            try:
                await page.wait_for_selector(selector, state="attached", timeout=1500)
                return
            except PlaywrightTimeoutError:
                continue
            except:
                continue

    async def _extract_price_from_dom(self, page):
        """DOM 優先策略：先直接抽價格，若成功可覆蓋 LLM 價格。"""
        current_url = (page.url or "").lower()

        # 九五之丹專用：優先讀取產品價格區塊
        # <div class="pro_dis_info"><span class="old-price">NT$400</span><span class="price">NT$350</span></div>
        if "95dan.com.tw" in current_url:
            try:
                exact_price_text = await page.evaluate("""() => {
                    const node = document.querySelector('div.pro_dis_info span.price');
                    return node ? node.textContent : '';
                }""")
                exact_price = int(re.sub(r'[^\d]', '', exact_price_text or '') or 0)
                if 100 <= exact_price <= 200000:
                    return exact_price
            except:
                pass

            # fallback：若 span.price 抓不到，再嘗試在 pro_dis_info 區塊中抽最後一個金額
            try:
                block_text = await page.evaluate("""() => {
                    const node = document.querySelector('div.pro_dis_info');
                    return node ? node.textContent : '';
                }""") or ""
                nums = re.findall(r'\d{2,6}', block_text.replace(',', ''))
                if nums:
                    # 通常最後一個是 sale price，前一個是 old-price
                    v = int(nums[-1])
                    if 100 <= v <= 200000:
                        return v
            except:
                pass

            # 九五之丹若未命中明確價格，直接回傳 0；交由 HTML/JSON-LD 價格來源處理
            return 0

        selectors = [
            ".same-price .price",
            ".same-price .price-regular .price",
            ".price-regular .price",
            ".js-price .price",
            ".price-sale .price",
            ".product-price",
            ".special-price",
            "div[class*='price']",
            "span.price",
            "div.price",
            ".price"
        ]

        for selector in selectors:
            try:
                locator = page.locator(selector)
                count = await locator.count()
                if count == 0:
                    continue

                # 只檢查前幾個元素，避免抓太慢
                check_n = min(count, 8)
                for i in range(check_n):
                    el = locator.nth(i)
                    if not await el.is_visible():
                        continue
                    p_text = (await el.text_content() or "").strip()
                    if not any(c.isdigit() for c in p_text):
                        continue
                    p_val = int(re.sub(r'[^\d]', '', p_text) or 0)
                    # 合理價格區間，避免誤抓評分/件數
                    if 100 <= p_val <= 200000:
                        return p_val
            except:
                continue

        # Fallback：全文找 NT$ / TWD / $
        try:
            body_text = await page.locator("body").text_content() or ""
            matches = re.findall(r'(?:NT\$|TWD\s*|\$)\s*(\d{1,3}(?:,\d{3})+|\d{3,6})', body_text)
            for m in matches:
                val = int(m.replace(',', ''))
                if 100 <= val <= 200000:
                    return val
        except:
            pass

        return 0

    @staticmethod
    def _looks_like_product_url(url):
        """URL 層級的產品判斷，避免部分站台缺少 og:type 時被誤判。"""
        u = (url or "").lower()
        product_tokens = ["/product", "/products", "/shop/", "lutein", "fish-oil", "probiotic"]
        return any(t in u for t in product_tokens)

    async def analyze_with_llm(self, html_content, url):
        """呼叫 Gemini 進行語義分析"""
        if not self.api_key or genai is None:
            return {}

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
            response = await asyncio.wait_for(
                self.model.generate_content_async(prompt),
                timeout=self.llm_timeout_seconds
            )
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
        except asyncio.TimeoutError:
            print(f"⚠️ [Agent] LLM 逾時（>{self.llm_timeout_seconds}s），改用非 LLM fallback")
            return {}
        except Exception as e:
            print(f"⚠️ [Agent] LLM 分析失敗: {e}")
            return {}

    def _extract_basic_info_from_html(self, html_content, url):
        """LLM 失敗時的最小可用資料。"""
        title = "Unknown"
        brand = "Unknown"

        try:
            soup = BeautifulSoup(html_content or "", 'html.parser')
            h1 = soup.select_one('h1')
            og_title = soup.select_one('meta[property="og:title"]')
            doc_title = soup.title.string.strip() if soup.title and soup.title.string else ""

            title = (
                (h1.get_text(strip=True) if h1 else "")
                or (og_title.get('content', '').strip() if og_title else "")
                or doc_title
                or "Unknown"
            )

            if "vitabox" in (url or "").lower() or "vitabox" in title.lower():
                brand = "Vitabox"
        except:
            pass

        return {"brand": brand, "title": title}

    def _extract_95dan_highlights_and_count(self, html_content):
        """九五之丹頁面專用：提取商品特色與單包裝數量（粒/包）。"""
        highlights = ""
        total_count = 0

        if not html_content:
            return {"product_highlights": highlights, "total_count": total_count}

        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # 商品特色：.pro_info_div 中 title 為「商品特色」的 ul/li
            for block in soup.select("div.pro_info_div"):
                title_node = block.select_one("div.pro_info_title")
                title_text = title_node.get_text(strip=True) if title_node else ""

                if "商品特色" in title_text:
                    items = [li.get_text(" ", strip=True) for li in block.select("ul.pro_info_ul li")]
                    items = [x for x in items if x]
                    if items:
                        highlights = ";".join(items)

                if "商品資訊" in title_text:
                    info_text = block.get_text(" ", strip=True)
                    # 例：規格：30粒/包，15天份
                    m = re.search(r"規格\s*[:：]\s*(\d+)\s*(?:粒|顆|錠|包)\s*/\s*包", info_text)
                    if m:
                        total_count = int(m.group(1))

            # fallback：若商品資訊區塊沒抓到，嘗試全頁規格文字
            if total_count == 0:
                full_text = soup.get_text(" ", strip=True)
                m = re.search(r"規格\s*[:：]\s*(\d+)\s*(?:粒|顆|錠|包)\s*/\s*包", full_text)
                if m:
                    total_count = int(m.group(1))
        except:
            pass

        return {"product_highlights": highlights, "total_count": total_count}

    def _extract_price_from_html_content(self, html_content):
        """
        第二輪價格策略：直接從 HTML / script 資料層提取價格。
        優先順序：
        1) JSON-LD Offer price
        2) app.value('product', JSON.parse('...')) 中的 price/price_sale/variations
        """
        if not html_content:
            return 0

        # 0) 九五之丹 HTML 區塊直抓：
        # <div class="pro_dis_info"><span class="old-price">NT$400</span> <span class="price">NT$350</span></div>
        try:
            block_match = re.search(r'<div[^>]*class="[^"]*pro_dis_info[^"]*"[^>]*>(.*?)</div>', html_content, re.IGNORECASE | re.DOTALL)
            if block_match:
                block = block_match.group(1)
                sale_match = re.search(r'<span[^>]*class="[^"]*price[^"]*"[^>]*>\s*NT\$?\s*([\d,]+)', block, re.IGNORECASE)
                if sale_match:
                    val = int(sale_match.group(1).replace(',', ''))
                    if val > 0:
                        return val
                nums = re.findall(r'NT\$?\s*([\d,]+)', block, re.IGNORECASE)
                if nums:
                    val = int(nums[-1].replace(',', ''))
                    if val > 0:
                        return val
        except:
            pass

        # 1) JSON-LD
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            for tag in soup.select("script[type='application/ld+json']"):
                raw = (tag.string or tag.text or "").strip()
                if not raw:
                    continue
                try:
                    data = json.loads(raw)
                except:
                    continue
                payloads = data if isinstance(data, list) else [data]
                for node in payloads:
                    if not isinstance(node, dict):
                        continue
                    offers = node.get("offers")
                    if isinstance(offers, dict):
                        p = offers.get("price")
                        if isinstance(p, (int, float)) and p > 0:
                            return int(round(p))
                        if isinstance(p, str):
                            val = int(re.sub(r'[^\d]', '', p) or 0)
                            if val > 0:
                                return val
        except:
            pass

        # 2) Shopline product data from app.value('product', JSON.parse('...'))
        try:
            m = re.search(r"app\.value\('product',\s*JSON\.parse\('(.+?)'\)\);", html_content, re.DOTALL)
            if m:
                payload = m.group(1)
                payload = payload.encode('utf-8').decode('unicode_escape')
                payload = html_lib.unescape(payload)
                product = json.loads(payload)

                candidates = []

                # 主價
                for key in ["price_sale", "price", "lowest_member_price"]:
                    obj = product.get(key) or {}
                    cents = obj.get("cents", 0)
                    if isinstance(cents, (int, float)) and cents > 0:
                        candidates.append(int(cents))

                # variations 價格（取最小正值，通常是顯示價）
                for v in product.get("variations", []) or []:
                    if not isinstance(v, dict):
                        continue
                    for key in ["price_sale", "price", "member_price"]:
                        obj = v.get(key) or {}
                        cents = obj.get("cents", 0)
                        if isinstance(cents, (int, float)) and cents > 0:
                            candidates.append(int(cents))

                if candidates:
                    return min(candidates)
        except Exception as e:
            print(f"⚠️ [Agent] HTML 價格解析失敗: {e}")

        return 0

    def _extract_shopline_price_legacy(self, html_content):
        """
        Legacy Vitabox/Shopline regex strategy transplant:
        app.value('product', {...});
        """
        if not html_content:
            return 0

        # 1) Legacy pattern: app.value('product', { ... });
        try:
            m = re.search(r"app\.value\('product',\s*(\{.*?\})\s*\);", html_content, re.DOTALL)
            if m:
                obj = json.loads(m.group(1))
                price = obj.get("price")
                if isinstance(price, dict):
                    cents = price.get("cents", 0)
                    if isinstance(cents, (int, float)) and cents > 0:
                        return int(cents)
                if isinstance(price, (int, float)) and price > 0:
                    return int(price)
                if isinstance(price, str):
                    v = int(re.sub(r'[^\d]', '', price) or 0)
                    if v > 0:
                        return v
        except Exception as e:
            print(f"⚠️ [Agent] Legacy Shopline 物件價格解析失敗: {e}")

        # 2) Backward compatible pattern currently used in scanner
        try:
            m = re.search(r"app\.value\('product',\s*JSON\.parse\('(.+?)'\)\);", html_content, re.DOTALL)
            if m:
                payload = m.group(1)
                payload = payload.encode('utf-8').decode('unicode_escape')
                payload = html_lib.unescape(payload)
                product = json.loads(payload)

                candidates = []
                for key in ["price_sale", "price", "lowest_member_price"]:
                    obj = product.get(key) or {}
                    cents = obj.get("cents", 0)
                    if isinstance(cents, (int, float)) and cents > 0:
                        candidates.append(int(cents))

                for v in product.get("variations", []) or []:
                    if not isinstance(v, dict):
                        continue
                    for key in ["price_sale", "price", "member_price"]:
                        obj = v.get(key) or {}
                        cents = obj.get("cents", 0)
                        if isinstance(cents, (int, float)) and cents > 0:
                            candidates.append(int(cents))

                if candidates:
                    return min(candidates)
        except Exception as e:
            print(f"⚠️ [Agent] Legacy Shopline JSON.parse 價格解析失敗: {e}")

        return 0

    async def scan_url(self, url):
        """掃描單一 URL"""
        url = self._normalize_url(url)
        if not url:
            print("❌ [Agent] 無效 URL，跳過")
            return None
        print(f"[INFO] Start scraping: {url}...")
        print(f"🤖 [Agent] 正在掃描: {url}")
        data = None
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            page.set_default_timeout(30000)
            page.set_default_navigation_timeout(30000)
            await stealth_async(page)

            async def _run_page_work():
                nonlocal data
                # 隨機延遲，模擬真人
                await asyncio.sleep(random.uniform(1, 3))
                
                response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                
                # 處理 403/429 重試邏輯 (簡單版)
                if response.status in [403, 429]:
                    print(f"⚠️ [Agent] 遇到 {response.status}，等待 10 秒後重試...")
                    await asyncio.sleep(10)
                    await page.reload(wait_until="domcontentloaded", timeout=30000)
                
                # 等待價格元素渲染 (在 dump HTML 前執行)
                await self._wait_for_price_elements(page, url)
                
                # 先抓 DOM 價格，供後續產品頁判斷與價格覆蓋
                dom_price = await self._extract_price_from_dom(page)

                # 第二道濾網 - 動態驗身 (Smart Filter)
                # 檢查 og:type 或 JSON-LD 是否標記為 Product，避免浪費 AI Token 分析非產品頁
                is_product_meta = await page.evaluate("""() => {
                    const ogType = document.querySelector('meta[property="og:type"]')?.content;
                    const jsonLd = Array.from(document.querySelectorAll('script[type="application/ld+json"]'))
                                        .map(el => el.innerText)
                                        .join('');
                    return ogType === 'product' || jsonLd.includes('"@type": "Product"') || jsonLd.includes('"@type":"Product"');
                }""")
                is_product = is_product_meta or self._looks_like_product_url(url) or dom_price > 0
                
                if not is_product:
                    print(f"⏩ [Agent] 跳過非產品頁面 (無 Product 標記): {url}")
                    return None

                # 滾動頁面觸發 Lazy Load
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)

                # 抓取基礎資料 (圖片與 HTML)
                content = await page.content()
                html_price = self._extract_price_from_html_content(content)
                legacy_shopline_price = 0
                if "vitabox" in url or "shopline" in url:
                    legacy_shopline_price = self._extract_shopline_price_legacy(content)
                if html_price == 0 and dom_price == 0 and ("vitabox" in url or "shopline" in url):
                    try:
                        with open("debug_vitabox_page.html", "w", encoding="utf-8") as f:
                            f.write(content)
                    except Exception as e:
                        print(f"⚠️ [Agent] 無法寫入 Vitabox debug HTML: {e}")
                
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
                
                # LLM 分析（九五之丹先走規則引擎，避免 API 延遲造成整體 timeout）
                if "95dan.com.tw" in (url or ""):
                    ai_data = {}
                else:
                    ai_data = await self.analyze_with_llm(content, url)
                basic_data = self._extract_basic_info_from_html(content, url)
                d95_meta = self._extract_95dan_highlights_and_count(content) if "95dan.com.tw" in (url or "") else {}

                # 整合資料（LLM 成功/失敗都會組裝結果，避免 pending）
                final_price = (ai_data or {}).get("price", 0)
                # DOM / HTML script 優先策略
                # 九五之丹先信任 HTML/JSON-LD（避免 DOM 抓到「已熱銷1000份」）
                if "95dan.com.tw" in (url or ""):
                    if html_price > 0:
                        final_price = html_price
                    elif dom_price > 0:
                        final_price = dom_price
                else:
                    if dom_price > 0:
                        final_price = dom_price
                    elif legacy_shopline_price > 0:
                        final_price = legacy_shopline_price
                    elif html_price > 0:
                        final_price = html_price

                data = {
                    "source": "D2C_Hunter", # 標記來源
                    "brand": (ai_data or {}).get("brand") or basic_data.get("brand", "Unknown"),
                    "title": (ai_data or {}).get("title") or basic_data.get("title", "Unknown"),
                    "price": int(final_price or 0),
                    "unit_price": (ai_data or {}).get("unit_price", 0),
                    "total_count": (ai_data or {}).get("total_count", 0) or d95_meta.get("total_count", 0),
                    "url": url,
                    "image_url": image_url or "",
                    "product_highlights": (ai_data or {}).get("product_highlights", "") or d95_meta.get("product_highlights", "")
                }
                print(f"✅ [Agent] 成功提取: {data['title']} (${data['price']})")
                
            try:
                await asyncio.wait_for(_run_page_work(), timeout=self.page_timeout_seconds)
            except (PlaywrightTimeoutError, asyncio.TimeoutError):
                print(f"[WARN] Timeout skipping: {url}")
                return None
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
            if res:
                results.append(res)
        return results


class D2CScanner:
    """向後相容封裝：提供同步介面，方便腳本直接呼叫。"""
    def __init__(self):
        self._scanner = AgentD2CScanner()

    def scan_url(self, url):
        return asyncio.run(self._scanner.scan_url(url))