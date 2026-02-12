import asyncio
import re
from playwright.async_api import async_playwright


TARGET_URL = "https://www.95dan.com.tw/maca"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        html_snippet = await page.evaluate(
            """() => {
                const box = document.querySelector('div.pro_dis_info');
                return box ? box.innerHTML : '';
            }"""
        )
        text_snippet = await page.evaluate(
            """() => {
                const box = document.querySelector('div.pro_dis_info');
                return box ? box.textContent : '';
            }"""
        )
        price_text = await page.evaluate(
            """() => {
                const node = document.querySelector('div.pro_dis_info span.price');
                return node ? node.textContent : '';
            }"""
        )

        print("[URL]", TARGET_URL)
        print("[pro_dis_info.innerHTML]\n", html_snippet[:1000])
        print("[pro_dis_info.text]\n", text_snippet[:300])
        print("[pro_dis_info span.price text]", price_text)

        nums = re.findall(r"\d{2,6}", text_snippet.replace(",", ""))
        print("[numbers in pro_dis_info text]", nums)

        script_hits = await page.evaluate(
            """() =>
                Array.from(document.scripts)
                    .map(s => s.textContent || '')
                    .filter(t => /pro_dis_info|old-price|price|NT\$/i.test(t))
                    .slice(0, 8)
            """
        )

        print("[script hits count]", len(script_hits))
        for idx, hit in enumerate(script_hits, 1):
            txt = hit.replace("\n", " ")
            print(f"--- script[{idx}] ---")
            print(txt[:800])

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
