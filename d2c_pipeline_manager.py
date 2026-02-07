import asyncio
import pandas as pd
import os
from data.serp_discovery import SerpDiscovery
from data.sitemap_parser import SitemapParser
from data.agent_d2c_scanner import AgentD2CScanner

async def run_pipeline():
    print("🚀 [Pipeline] D2C 獵人自動化系統啟動...")
    
    # 初始化模組
    serp = SerpDiscovery()
    parser = SitemapParser()
    scanner = AgentD2CScanner()
    
    all_products_data = []
    
    # --- Step 1: Target Discovery (目標鎖定) ---
    # 建議：使用手動精選名單，品質遠高於自動搜尋
    MANUAL_TARGETS = [
        "https://www.daikenshop.com",
        "https://www.biomedimei.com",
        "https://www.dietician.com.tw",
        "https://shop.vitabox.com.tw"
    ]
    
    target_domains = set()
    
    if MANUAL_TARGETS:
        print(f"\n--- Phase 1: Manual Target List ({len(MANUAL_TARGETS)} domains) ---")
        target_domains.update(MANUAL_TARGETS)
    else:
        # 若無手動名單，才啟用 SERP 搜尋
        print("\n--- Phase 1: SERP Discovery ---")
        keywords = ["葉黃素 推薦", "魚油 推薦", "益生菌 品牌"]
        for kw in keywords:
            domains = await serp.search_google(kw, num_results=15)
            target_domains.update(domains)
    
    print(f"🎯 鎖定 {len(target_domains)} 個目標網域: {list(target_domains)[:5]}...")

    # --- Step 2: Sitemap Parsing (導航) ---
    print("\n--- Phase 2: Sitemap Parsing ---")
    product_urls_pool = []
    
    for domain in target_domains:
        urls = await parser.parse_sitemap(domain)
        # 簡單過濾：每個網域最多取 10 個產品連結測試，避免掃描太久
        product_urls_pool.extend(urls[:10])
    
    print(f"🔗 共提取 {len(product_urls_pool)} 個產品連結待掃描")

    # --- Step 3: Agent Scanning (採集) ---
    print("\n--- Phase 3: Agent Scanning ---")
    
    # 批次執行，每批 5 個 (避免 API Rate Limit)
    batch_size = 5
    for i in range(0, len(product_urls_pool), batch_size):
        batch_urls = product_urls_pool[i : i + batch_size]
        print(f"📦 處理批次 {i//batch_size + 1} / {(len(product_urls_pool)//batch_size) + 1}")
        
        results = await scanner.scan_batch(batch_urls)
        all_products_data.extend(results)
        
        # 批次間休息
        await asyncio.sleep(5)

    # --- Step 4: Save Data (存檔) ---
    print("\n--- Phase 4: Data Saving ---")
    if all_products_data:
        df = pd.DataFrame(all_products_data)
        
        # 確保欄位順序符合 Unified Schema
        schema = ["source", "brand", "title", "price", "unit_price", "total_count", "url", "image_url", "product_highlights"]
        # 補全缺失欄位
        for col in schema:
            if col not in df.columns:
                df[col] = ""
        
        df = df[schema] # 重排
        
        os.makedirs("data", exist_ok=True)
        output_file = "data/d2c_full_database.csv"
        df.to_csv(output_file, index=False, encoding="utf-8-sig")
        print(f"💾 資料已儲存至: {output_file} (共 {len(df)} 筆)")
    else:
        print("⚠️ 本次任務未採集到任何有效資料。")

if __name__ == "__main__":
    asyncio.run(run_pipeline())