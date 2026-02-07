import asyncio
import time
import os
from d2c_daiken_crawler import scrape_daiken_all_products
from d2c_dietician_crawler import scrape_dietician_all_products
from d2c_vitabox_crawler import VitaboxStealthCrawler

async def run_vitabox():
    """封裝 Vitabox 爬蟲執行邏輯"""
    print("🚀 [Vitabox] 任務啟動...")
    crawler = VitaboxStealthCrawler()
    await crawler.run()
    crawler.save_csv()
    print("✅ [Vitabox] 任務完成")

async def run_daiken():
    """封裝大研生醫爬蟲執行邏輯"""
    print("🚀 [Daiken] 任務啟動...")
    await scrape_daiken_all_products()
    print("✅ [Daiken] 任務完成")

async def run_dietician():
    """封裝營養師輕食爬蟲執行邏輯"""
    print("🚀 [Dietician] 任務啟動 (含 AI 分析)...")
    await scrape_dietician_all_products()
    print("✅ [Dietician] 任務完成")

async def main():
    start_time = time.time()
    print("="*50)
    print("🤖 VITAGUIDE D2C 聯合爬蟲任務開始")
    print("="*50)

    # 確保資料夾存在
    os.makedirs("data", exist_ok=True)

    # 平行執行所有爬蟲
    # 注意：這會同時開啟多個瀏覽器視窗，請確保系統資源充足
    await asyncio.gather(
        run_daiken(),
        run_vitabox(),
        run_dietician()
    )

    end_time = time.time()
    duration = end_time - start_time
    
    print("\n" + "="*50)
    print(f"🎉 所有 D2C 爬蟲任務已完成！總耗時: {duration:.2f} 秒")
    print("="*50)
    
    # 簡單驗證檔案產出
    expected_files = [
        "data/d2c_daiken_all_products.csv",
        "data/d2c_vitabox.csv",
        "data/d2c_dietician_products.csv"
    ]
    for f in expected_files:
        status = "✅ 存在" if os.path.exists(f) else "❌ 缺失"
        print(f"檔案檢查 [{f}]: {status}")

if __name__ == "__main__":
    asyncio.run(main())