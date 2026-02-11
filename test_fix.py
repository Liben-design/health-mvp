from data.agent_d2c_scanner import D2CScanner
from data.sitemap_parser import SitemapParser


# 測試 1: Vitabox 價格
scanner = D2CScanner()
vitabox_res = scanner.scan_url("https://shop.vitabox.com.tw/products/lutein-z")
print(f"Vitabox Price: {(vitabox_res or {}).get('price')}")

# 測試 2: 配方時代過濾
parser = SitemapParser()
is_product = parser.is_likely_product("https://www.formula-time.com/products/lutein-ex")
print(f"Health Formula Allowed: {is_product}")
