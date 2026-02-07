import asyncio
import random
import pandas as pd
import os
import re
from abc import ABC, abstractmethod
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

class BaseScraper(ABC):
    """
    D2C 爬蟲的基礎抽象類別 (Strategy Pattern Base Class)
    負責處理瀏覽器生命週期、隱身偽裝、資料儲存與通用工具函式。
    """
    def __init__(self, output_file: str):
        self.output_file = output_file
        self.data = []
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
        ]

    async def random_sleep(self, min_sec=2, max_sec=5):
        """模擬真人隨機等待"""
        await asyncio.sleep(random.uniform(min_sec, max_sec))

    def save_to_csv(self):
        """統一儲存邏輯，確保 Schema 一致性"""
        if not self.data:
            print(f"⚠️ [{self.__class__.__name__}] 未抓取到資料，跳過存檔。")
            return
        
        # 確保目錄存在
        os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
        
        df = pd.DataFrame(self.data)
        
        # 嚴格遵守 README.md 定義的 Schema
        required_columns = [
            "source", "brand", "title", "price", "unit_price", 
            "url", "image_url", "product_highlights", "total_count", "tags"
        ]
        
        # 補全缺失欄位
        for col in required_columns:
            if col not in df.columns:
                df[col] = "" 
                
        # 重新排序欄位
        df = df.reindex(columns=required_columns)
        
        df.to_csv(self.output_file, index=False, encoding='utf-8-sig')
        print(f"💾 [{self.__class__.__name__}] 資料已儲存至: {self.output_file} (共 {len(df)} 筆)")

    @abstractmethod
    async def run(self):
        """
        [抽象方法] 執行爬蟲的主流程。
        子類別必須實作此方法來定義該品牌的抓取邏輯。
        """
        pass

    # ==========================================
    # 通用工具函式 (封裝自 general_scraper.py)
    # ==========================================
    def calculate_unit_price(self, title, price, description=""):
        """通用規格計算邏輯 (從標題或描述提取顆數)"""
        if not isinstance(title, str) or not price: return None, 0
        unit_count, bundle_size = None, 1
        
        # 1. 尋找單品數量 (優先查標題)
        count_regex = r'(\d+)\s*[粒顆錠包]'
        match = re.search(count_regex, title)
        if match: 
            unit_count = int(match.group(1))
        
        # 2. 若標題沒找到，嘗試從描述找
        if not unit_count and description:
            spec_match = re.search(r'(?:內容量|規格)[：:]\s*(\d+)\s*[粒顆錠包]', description)
            if spec_match:
                unit_count = int(spec_match.group(1))

        # 3. 尋找組數 (x3, 3入)
        bundle_match = re.search(r'[xX*]\s*(\d{1,2})\b', title)
        if bundle_match:
            bundle_size = int(bundle_match.group(1))
        else:
            bundle_match = re.search(r'[\s\uff0c\(\uff08](\d{1,2})\s*[入件組]', title)
            if bundle_match: bundle_size = int(bundle_match.group(1))
            
        if unit_count:
            total_count = unit_count * bundle_size
            u_price = round(price / total_count, 2) if total_count > 0 else 0
            return total_count, u_price
        return None, 0

    def extract_tags(self, text):
        """通用標籤提取邏輯"""
        tags = []
        if not isinstance(text, str): return ""
        
        if re.search(r"游離型|Free form", text, re.IGNORECASE): tags.append("✅游離型")
        if re.search(r"FloraGLO", text, re.IGNORECASE): tags.append("💎FloraGLO")
        if re.search(r"Omega-?3", text, re.IGNORECASE): tags.append("🐟Omega-3")
        if re.search(r"rTG", text, re.IGNORECASE): tags.append("🧬rTG型")
        if re.search(r"SNQ", text, re.IGNORECASE): tags.append("🏅SNQ認證")
        if re.search(r"SGS", text, re.IGNORECASE): tags.append("🛡️SGS檢驗")
        if re.search(r"IFOS", text, re.IGNORECASE): tags.append("🏆IFOS認證")
        
        return " ".join(tags)
