import asyncio
from urllib.parse import urljoin
from playwright.async_api import async_playwright


BASE = "https://www.95dan.com.tw"
URL = f"{BASE}/allproduct"


def is_product_slug(u: str) -> bool:
    lu = u.lower()
    deny_tokens = [
        "/allproduct", "/about", "/aboutus", "/news", "/blog", "/media", "/kol", "/corporate",
        "/shippingpolicy", "/refund", "/signin", "/sgs", "/shopee", "/terms", "/policy", "/privacy", "/contact",
        "/mondeselection", "/material", "/95danboss", "/cdn-cgi/", "/upload/"
    ]
    if any(t in lu for t in deny_tokens):
        return False
    if "95dan.com.tw" not in lu:
        return False
    path = lu.replace("https://www.95dan.com.tw", "").strip("/")
    if not path or "/" in path:
        return False
    return True


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(URL, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(4000)

        hrefs = await page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e => e.getAttribute('href')).filter(Boolean)",
        )

        full_links = []
        seen = set()
        for h in hrefs:
            u = urljoin(BASE + "/", h.strip())
            if u not in seen:
                seen.add(u)
                full_links.append(u)

        product_links = [u for u in full_links if is_product_slug(u)]

        print(f"[rendered anchors] {len(full_links)}")
        print(f"[rendered inferred product links] {len(product_links)}")
        for u in sorted(product_links):
            print(u)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
