import asyncio
from scrapers.daiken_scraper import DaikenScraper
from scrapers.vitabox_scraper import VitaboxScraper
# 未來可加入: from scrapers.dietician_scraper import DieticianScraper

async def run_scraper_task(scraper_class):
    """封裝單一爬蟲的執行與錯誤處理"""
    scraper_name = scraper_class.__name__
    try:
        print(f"🏁 [{scraper_name}] 準備啟動...")
        # 實例化並執行
        scraper = scraper_class()
        await scraper.run()
        print(f"✅ [{scraper_name}] 執行完畢")
    except Exception as e:
        print(f"❌ [{scraper_name}] 發生未預期錯誤: {e}")

async def main():
    # 1. 註冊要執行的爬蟲清單
    scrapers_to_run = [
        DaikenScraper,
        VitaboxScraper
    ]
    
    print(f"🚀 總指揮啟動：準備平行執行 {len(scrapers_to_run)} 個爬蟲任務...")
    
    # 2. 建立異步任務清單 (平行執行)
    tasks = [run_scraper_task(cls) for cls in scrapers_to_run]
    
    # 3. 等待所有任務完成
    await asyncio.gather(*tasks)
    print("🎉 所有 D2C 爬蟲任務皆已結束！")

if __name__ == "__main__":
    asyncio.run(main())