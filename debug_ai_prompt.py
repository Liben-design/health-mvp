import asyncio
from data.agent_d2c_scanner import AgentD2CScanner


async def main():
    # 可替換為任何高行銷語氣商品頁
    test_url = "https://www.daikenshop.com/product.php?code=4710255450067"
    print(f"[INFO] 測試網址: {test_url}")

    scanner = AgentD2CScanner()
    result = await scanner.scan_url(test_url)

    if not result:
        print("[ERROR] 掃描失敗，未取得結果")
        return

    print("\n===== AI Prompt Debug Result =====")
    print(f"title: {result.get('title', '')}")
    print(f"product_highlights: {result.get('product_highlights', '')}")


if __name__ == "__main__":
    asyncio.run(main())