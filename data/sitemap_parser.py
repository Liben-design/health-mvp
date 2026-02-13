import requests
import xml.etree.ElementTree as ET
import csv
import json
import os
import re
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

class SitemapParser:
    """
    輕量化 Sitemap 解析器 (Phase 2 Core Module)
    不依賴瀏覽器，使用 Requests 與 XML Parser 快速提取產品連結。
    """
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            # 改用一般瀏覽器 UA，降低被防火牆阻擋機率 (解決配方時代等網站連線問題)
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        # 關鍵過濾：網址必須包含這些特徵之一
        # 新增 'product.php' 支援大研生醫
        self.include_patterns = ['/product/', '/products/', '/item/', '/goods/', '/merch/', '/shop/', 'product.php']
        
        # [New] 針對特定網域放寬過濾標準 (如配方時代使用自定義 URL，不含 product 前綴)
        self.relaxed_domains = ['healthformula.com.tw']
        
        # [New] 網域白名單規則：可覆蓋一般 include/exclude 邏輯
        # 配方時代 (formula-time) 產品 URL 結構可能不固定，且有時不含 /product/
        # 允許短路徑 slug (e.g. /lutein-ex)，但仍排除常見內容頁
        self.domain_whitelist_rules = {
            "www.95dan.com.tw": {
                "allow_patterns": [
                    "/alcohol-enzyme",
                    "/maca",
                    "/macaplus",
                    "/lutein",
                    "/b+zinc",
                    "/b+fe",
                    "/arginine",
                    "/pumpkin",
                    "/withania",
                    "/curcumin",
                    "/fishoil",
                    "/calcium",
                    "/calciumplus",
                    "/collagen",
                    "/vitaminc",
                    "/vitamine",
                    "/probiotics",
                    "/fiberplus",
                    "/cranberry",
                    "/dmannose",
                    "/gsh-enzyme",
                    "/gaba-enzyme",
                    "/simply-enzyme",
                    "/superhca",
                    "/tryptophan",
                    "/polypeptide-p",
                    "/pct2",
                    "/biotin",
                    "/msm"
                ],
                "deny_patterns": [
                    "/allproduct",
                    "/home",
                    "/about",
                    "/aboutus",
                    "/news",
                    "/blog",
                    "/media",
                    "/kol",
                    "/corporate",
                    "/shippingpolicy",
                    "/refund",
                    "/signin",
                    "/sgs",
                    "/shopee",
                    "/terms",
                    "/policy",
                    "/privacy",
                    "/contact"
                ],
                "allow_short_slug": False
            },
            "www.formula-time.com": {
                "allow_patterns": [
                    "/products/",
                    "/product/",
                    "/shop/",
                    "lutein",
                    "fish-oil",
                    "probiotic",
                    "omega",
                    "collagen",
                    "calcium",
                    "magnesium",
                    "vitamin",
                    "b-complex",
                    "zinc",
                    "iron"
                ],
                "deny_patterns": [
                    "/blog",
                    "/news",
                    "/article",
                    "/about",
                    "/contact",
                    "/faq",
                    "/policy",
                    "/member",
                    "/cart",
                    "/account",
                    "/terms",
                    "/privacy",
                    "/page",
                    "/pages"
                ],
                "allow_short_slug": True
            },
            "formula-time.com": {
                "allow_patterns": [
                    "/products/",
                    "/product/",
                    "/shop/",
                    "lutein",
                    "fish-oil",
                    "probiotic",
                    "omega",
                    "collagen",
                    "calcium",
                    "magnesium",
                    "vitamin",
                    "b-complex",
                    "zinc",
                    "iron"
                ],
                "deny_patterns": [
                    "/blog",
                    "/news",
                    "/article",
                    "/about",
                    "/contact",
                    "/faq",
                    "/policy",
                    "/member",
                    "/cart",
                    "/account",
                    "/terms",
                    "/privacy",
                    "/page",
                    "/pages"
                ],
                "allow_short_slug": True
            }
        }

        # 排除雜訊：網址不能包含這些特徵
        # 新增 'knowledge', 'about' 等常見非產品頁面
        self.exclude_patterns = ['/blog', '/news', '/article', '/page', '/about', '/contact', '/faq', '/terms', 
                                 '/collections/', '/category/', '/tag/', '/knowledge/', '/media/', '/policy/', '/account/', '/cart/', '/member/']

    def fetch_content(self, url):
        """輕量化抓取內容，含超時控制"""
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                return response.text
        except Exception as e:
            # 靜默失敗，僅在 debug 時輸出
            # print(f"⚠️ 連線失敗 {url}: {e}")
            pass
        return None

    def get_sitemaps_from_robots(self, domain):
        """從 robots.txt 尋找 Sitemap 宣告"""
        robots_url = urljoin(domain, "/robots.txt")
        content = self.fetch_content(robots_url)
        sitemaps = []
        if content:
            for line in content.splitlines():
                if line.lower().startswith("sitemap:"):
                    try:
                        sitemap_url = line.split(":", 1)[1].strip()
                        sitemaps.append(sitemap_url)
                    except: pass
        return sitemaps

    def is_likely_product(self, url):
        """網址過濾邏輯：只保留產品頁"""
        u = url.lower()
        parsed = urlparse(u)
        host = parsed.netloc
        
        # [New] 0. 全域清洗規則 (針對悠活原力等)
        # 排除非 ASCII (亂碼/中文路徑)
        if re.search(r'[^\x00-\x7F]', u):
            return False
        # 排除結尾長數字 (時間戳記/變體) e.g. -20220719115000
        if re.search(r'-\d{6,}', u):
            return False

        # [New] 0.5 網域白名單規則 (配方時代專用)
        if host in self.domain_whitelist_rules:
            rules = self.domain_whitelist_rules[host]
            if any(deny in u for deny in rules["deny_patterns"]):
                return False
            if any(allow in u for allow in rules["allow_patterns"]):
                return True
            if rules.get("allow_short_slug"):
                path = parsed.path.strip("/")
                # 允許單一 slug 且長度足夠（避免 /about 這類頁面）
                if path and "/" not in path and len(path) >= 5:
                    return True
            # 白名單網域但沒有明顯產品特徵時，保守不放行
            return False

        # 1. 排除特徵 (優先執行)
        if any(ex in u for ex in self.exclude_patterns):
            return False

        # [New] 2. 寬鬆網域檢查 (跳過包含特徵檢查)
        for domain in self.relaxed_domains:
            if domain in u:
                return True

        # 3. 必須包含產品特徵
        if not any(p in u for p in self.include_patterns):
            return False
        return True

    def parse_xml(self, xml_content):
        """解析 XML 並處理 Namespace 問題"""
        try:
            # 移除 xmlns 屬性以簡化 ElementTree 的查找 (避免處理複雜的 namespace map)
            xml_content = re.sub(r'xmlns="[^"]+"', '', xml_content, count=1)
            root = ET.fromstring(xml_content)
            return root
        except ET.ParseError:
            return None

    def process_domain(self, brand, domain):
        """處理單一網域的完整流程：Robots -> Sitemap -> URLs"""
        print(f"🔍 [Sitemap] 開始掃描: {brand} ({domain})")
        found_urls = set()
        total_scanned = 0
        
        # 1. 收集種子 Sitemaps
        sitemap_queue = self.get_sitemaps_from_robots(domain)
        if not sitemap_queue:
            # Fallback: 若 robots.txt 沒寫，嘗試常見路徑
            defaults = [
                "/sitemap.xml",
                "/sitemap_index.xml",
                "/sitemap_products_1.xml", # Shopify 常見
                "/wp-sitemap.xml" # WordPress 5.5+ 預設
            ]
            sitemap_queue = [urljoin(domain, p) for p in defaults]

        processed_sitemaps = set()

        # 2. 遞迴解析 (廣度優先搜尋)
        while sitemap_queue:
            current_sitemap = sitemap_queue.pop(0)
            if current_sitemap in processed_sitemaps:
                continue
            processed_sitemaps.add(current_sitemap)

            xml_content = self.fetch_content(current_sitemap)
            if not xml_content:
                continue

            root = self.parse_xml(xml_content)
            if root is None:
                continue

            # A. 處理 Sitemap Index (巢狀 Sitemap)
            # 格式: <sitemap><loc>...</loc></sitemap>
            for sitemap in root.findall(".//sitemap"):
                loc = sitemap.find("loc")
                if loc is not None and loc.text:
                    sitemap_queue.append(loc.text.strip())

            # B. 處理 URL Set (實際連結)
            # 格式: <url><loc>...</loc></url>
            for url_tag in root.findall(".//url"):
                loc = url_tag.find("loc")
                if loc is not None and loc.text:
                    url = loc.text.strip()
                    total_scanned += 1
                    if self.is_likely_product(url):
                        found_urls.add(url)

        # 九五之丹補強：從產品總覽頁補抓產品詳情連結（固定執行），避免 sitemap 欄位不足
        if "95dan.com.tw" in domain:
            all_product_page = urljoin(domain, "/allproduct")
            html = self.fetch_content(all_product_page)
            if html:
                hrefs = re.findall(r'href=["\']([^"\']+)["\']', html)
                for href in hrefs:
                    full_url = urljoin(domain, href)
                    if self.is_likely_product(full_url):
                        found_urls.add(full_url)

            # 95dan 補強：有些產品卡片由前端渲染，直接以白名單 slug 合成 URL 補齊
            rule = self.domain_whitelist_rules.get("www.95dan.com.tw", {})
            for token in rule.get("allow_patterns", []):
                if token.startswith("/"):
                    candidate = urljoin(domain, token)
                    if self.is_likely_product(candidate):
                        found_urls.add(candidate)

        filter_rate = (1 - len(found_urls) / total_scanned) * 100 if total_scanned > 0 else 0
        print(f"✅ [Sitemap] {brand} 完成，掃描 {total_scanned} 連結 -> 提取 {len(found_urls)} 產品 (過濾率 {filter_rate:.1f}%)")
        return [{"brand": brand, "url": u} for u in found_urls]

def main():
    input_csv = "data/test_domains.csv"
    output_json = "data/target_product_urls.json"
    
    # 檢查輸入檔
    if not os.path.exists(input_csv):
        print(f"❌ 找不到輸入檔案: {input_csv}，請先建立品牌清單。")
        return

    results = []
    parser = SitemapParser()
    domains = []

    # 讀取 CSV
    with open(input_csv, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("domain") and row.get("brand"):
                domains.append((row["brand"], row["domain"]))

    # [測試模式] 僅處理前 5 個品牌進行校準
    print(f"⚠️ 測試模式啟動：僅處理清單中的前 5 個品牌 (共 {len(domains)} 個)")
    domains = domains[:5]

    # 平行處理 (加速)
    print(f"🚀 啟動 Sitemap 解析器，共 {len(domains)} 個目標...")
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_brand = {executor.submit(parser.process_domain, b, d): b for b, d in domains}
        for future in as_completed(future_to_brand):
            results.extend(future.result())

    # 輸出結果
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n🎉 解析完成！共收集 {len(results)} 個產品連結，已儲存至 {output_json}")

if __name__ == "__main__":
    main()