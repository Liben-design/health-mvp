import asyncio
import json
import os
import sys
import pandas as pd

# 確保可以從專案根目錄匯入模組
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.agent_d2c_scanner import AgentD2CScanner

async def main():
    # 設定檔案路徑
    input_json = "data/target_product_urls.json"
    output_csv = "data/d2c_full_database.csv"

    # 1. 讀取目標清單
    if not os.path.exists(input_json):
        print(f"❌ 找不到輸入檔案: {input_json}")
        return

    print(f"📂 讀取目標清單: {input_json}")
    with open(input_json, "r", encoding="utf-8") as f:
        target_list = json.load(f)
    
    # 建立 URL -> Brand 的映射，用於補全 AI 可能漏掉的品牌資訊
    url_map = {item['url']: item['brand'] for item in target_list}
    urls_to_scan = [item['url'] for item in target_list]
    
    total_urls = len(urls_to_scan)
    print(f"🚀 準備掃描 {total_urls} 個產品連結...")

    # 2. 初始化掃描器
    scanner = AgentD2CScanner()
    all_data = []
    
    # 3. 批次執行 (避免一次性請求過多導致被封鎖或記憶體不足)
    batch_size = 5
    for i in range(0, total_urls, batch_size):
        batch_urls = urls_to_scan[i : i + batch_size]
        current_batch_num = (i // batch_size) + 1
        total_batches = (total_urls + batch_size - 1) // batch_size
        
        print(f"\n📦 [Batch {current_batch_num}/{total_batches}] 處理中 ({len(batch_urls)} items)...")
        
        # 呼叫 Agent 進行掃描
        results = await scanner.scan_batch(batch_urls)
        
        # 資料後處理：補全品牌資訊
        for res in results:
            if res.get('url') in url_map:
                known_brand = url_map[res['url']]
                # 若 AI 判斷為 Unknown 或空，則使用 Sitemap 的品牌資訊
                if not res.get('brand') or res.get('brand') == "Unknown":
                    res['brand'] = known_brand
        
        all_data.extend(results)
        
        # 4. 即時存檔 (每批次存一次，防止中斷遺失)
        save_to_csv(all_data, output_csv)
        
        # 批次間休息，降低被封鎖風險
        if i + batch_size < total_urls:
            print("⏳ 冷卻 3 秒...")
            await asyncio.sleep(3)

    print(f"\n🎉 掃描完成！共 {len(all_data)} 筆有效資料已儲存至 {output_csv}")

def save_to_csv(data, filepath):
    if not data: return
    df = pd.DataFrame(data)
    # 確保欄位符合 Unified Schema
    schema = ["source", "brand", "title", "price", "unit_price", "total_count", "url", "image_url", "product_highlights"]
    for col in schema:
        if col not in df.columns: df[col] = ""
    df = df[schema]
    df.to_csv(filepath, index=False, encoding="utf-8-sig")
    print(f"💾 已更新存檔: {len(df)} 筆")

if __name__ == "__main__":
    asyncio.run(main())