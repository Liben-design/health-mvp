import asyncio
import json
import re

from playwright.async_api import async_playwright
from playwright_stealth import stealth_async


TARGET_URL = "https://shop.vitabox.com.tw/products/lutein-z"


def _extract_price_from_jsonld(html: str) -> int:
    scripts = re.findall(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    for raw in scripts:
        raw = raw.strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        nodes = data if isinstance(data, list) else [data]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            offers = node.get("offers")
            if isinstance(offers, dict):
                p = offers.get("price")
                if isinstance(p, (int, float)) and p > 0:
                    return int(round(p))
                if isinstance(p, str):
                    v = int(re.sub(r"[^\\d]", "", p) or 0)
                    if v > 0:
                        return v
    return 0


async def main():
    print(f"[INFO] Start Vitabox debug: {TARGET_URL}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        page.set_default_timeout(30000)
        await stealth_async(page)

        resp = await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
        print(f"[INFO] Response status: {resp.status if resp else 'N/A'}")
        await page.wait_for_timeout(1500)

        # Critical: 強制截圖
        await page.screenshot(path="debug_vitabox.png", full_page=True)
        print("[INFO] Screenshot saved: debug_vitabox.png")

        # Strategy 1: DOM selector 等待
        selector_group = ".price, .product-price, .global-price"
        try:
            await page.wait_for_selector(selector_group, state="attached", timeout=10000)
            print(f"[INFO] wait_for_selector hit: {selector_group}")
        except Exception as e:
            print(f"[WARN] wait_for_selector timeout/fail: {e}")

        selectors = [".global-price", ".product-price", ".price", ".price-sale .price", ".price-regular .price"]
        dom_price = 0
        for sel in selectors:
            try:
                loc = page.locator(sel)
                c = await loc.count()
                print(f"[INFO] selector={sel} count={c}")
                for i in range(min(c, 5)):
                    t = (await loc.nth(i).text_content() or "").strip()
                    if t:
                        print(f"[INFO] selector_text {sel}[{i}]={t}")
                    v = int(re.sub(r"[^\\d]", "", t) or 0)
                    if 100 <= v <= 200000:
                        dom_price = v
                        break
                if dom_price > 0:
                    break
            except Exception as e:
                print(f"[WARN] selector read fail {sel}: {e}")

        html = await page.content()
        with open("debug_vitabox_runtime.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("[INFO] Runtime HTML saved: debug_vitabox_runtime.html")

        jsonld_price = _extract_price_from_jsonld(html)
        print(f"[RESULT] dom_price={dom_price}")
        print(f"[RESULT] jsonld_price={jsonld_price}")
        print(f"[RESULT] final_price={dom_price or jsonld_price}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
