import asyncio
import csv
import json
import os
import sys
import traceback
from datetime import datetime

import pandas as pd

# 確保可從專案根目錄匯入模組
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.sitemap_parser import SitemapParser
from data.agent_d2c_scanner import AgentD2CScanner


DOMAINS_CSV = "data/d2c_domains_list.csv"
TARGET_JSON = "data/target_product_urls.json"
OUTPUT_CSV = "data/d2c_full_database.csv"
ERROR_LOG = "data/batch_scanner_error.log"

TOP_N_BRANDS = 10
MAX_URLS_PER_BRAND = 30
MAX_RETRIES = 3
CONCURRENCY = 3


def log_error(stage, brand, url, err):
    os.makedirs("data", exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = (
        f"[{ts}] stage={stage} brand={brand} url={url}\n"
        f"error={repr(err)}\n"
        f"traceback={traceback.format_exc()}\n"
        f"{'-' * 80}\n"
    )
    with open(ERROR_LOG, "a", encoding="utf-8") as f:
        f.write(msg)


def load_top_domains(path, top_n=10):
    domains = []
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            brand = (row.get("brand") or "").strip()
            domain = (row.get("domain") or "").strip()
            if brand and domain:
                domains.append((brand, domain))
    return domains[:top_n]


def save_to_csv(data, filepath):
    if not data:
        return

    schema = [
        "source",
        "brand",
        "title",
        "price",
        "unit_price",
        "total_count",
        "url",
        "image_url",
        "product_highlights",
    ]

    df_new = pd.DataFrame(data)
    for c in schema:
        if c not in df_new.columns:
            df_new[c] = ""
    df_new = df_new[schema]

    # 若舊檔存在則合併去重
    if os.path.exists(filepath):
        try:
            df_old = pd.read_csv(filepath)
            for c in schema:
                if c not in df_old.columns:
                    df_old[c] = ""
            df_old = df_old[schema]
            df_all = pd.concat([df_old, df_new], ignore_index=True)
            if "url" in df_all.columns:
                df_all = df_all.drop_duplicates(subset=["url"], keep="last")
        except Exception:
            df_all = df_new
    else:
        df_all = df_new

    df_all.to_csv(filepath, index=False, encoding="utf-8-sig")
    print(f"💾 已更新存檔: {filepath} (共 {len(df_all)} 筆)")


async def scan_url_with_retry(scanner, brand, url, max_retries=3):
    for attempt in range(1, max_retries + 1):
        try:
            result = await scanner.scan_url(url)
            if result:
                if not result.get("brand") or result.get("brand") == "Unknown":
                    result["brand"] = brand
                return result
            return None
        except Exception as e:
            log_error("scan_url", brand, url, e)
            if attempt < max_retries:
                wait_sec = min(2 ** attempt, 8)
                print(f"⚠️ [{brand}] URL 重試 {attempt}/{max_retries}: {url} ({wait_sec}s)")
                await asyncio.sleep(wait_sec)
            else:
                print(f"❌ [{brand}] URL 最終失敗: {url}")
    return None


async def main():
    os.makedirs("data", exist_ok=True)

    if not os.path.exists(DOMAINS_CSV):
        print(f"❌ 找不到網域清單: {DOMAINS_CSV}")
        return

    domains = load_top_domains(DOMAINS_CSV, TOP_N_BRANDS)
    print(f"🎯 今日任務：掃描前 {len(domains)} 個品牌")
    for i, (brand, domain) in enumerate(domains, 1):
        print(f"  {i:02d}. {brand} -> {domain}")

    parser = SitemapParser()
    scanner = AgentD2CScanner()

    # 1) 先做 sitemap 解析（每個品牌可重試）
    target_list = []
    for brand, domain in domains:
        parsed_ok = False
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                items = parser.process_domain(brand, domain)
                # 每品牌限制前 N 個，控時與穩定
                items = items[:MAX_URLS_PER_BRAND]
                target_list.extend(items)
                parsed_ok = True
                break
            except Exception as e:
                log_error("parse_domain", brand, domain, e)
                if attempt < MAX_RETRIES:
                    wait_sec = min(2 ** attempt, 8)
                    print(f"⚠️ [{brand}] Sitemap 重試 {attempt}/{MAX_RETRIES} ({wait_sec}s)")
                    await asyncio.sleep(wait_sec)
                else:
                    print(f"❌ [{brand}] Sitemap 最終失敗，略過")
        if not parsed_ok:
            continue

    # 存 target json（方便追蹤）
    with open(TARGET_JSON, "w", encoding="utf-8") as f:
        json.dump(target_list, f, ensure_ascii=False, indent=2)

    # URL 去重
    dedup_map = {}
    for item in target_list:
        u = item.get("url")
        b = item.get("brand", "Unknown")
        if u:
            dedup_map[u] = b
    pending = [{"url": u, "brand": b} for u, b in dedup_map.items()]

    if not pending:
        print("⚠️ 本次沒有可掃描的產品 URL")
        return

    print(f"🔗 待掃描 URL 數量: {len(pending)}")

    # 2) 掃描（自動重試 + 錯誤記錄 + 不中斷）
    sem = asyncio.Semaphore(CONCURRENCY)
    scanned_results = []

    async def _job(item):
        async with sem:
            res = await scan_url_with_retry(scanner, item["brand"], item["url"], MAX_RETRIES)
            if res:
                scanned_results.append(res)

    await asyncio.gather(*[_job(it) for it in pending])

    # 3) 輸出
    save_to_csv(scanned_results, OUTPUT_CSV)

    print("\n✅ 任務完成")
    print(f"- 目標品牌數: {len(domains)}")
    print(f"- 提取目標 URL: {len(pending)}")
    print(f"- 成功抓取筆數: {len(scanned_results)}")
    print(f"- Error Log: {ERROR_LOG}")


if __name__ == "__main__":
    asyncio.run(main())
