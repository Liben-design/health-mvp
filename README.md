# VITAGUIDE 維他評選指南 | Ascent Lab

## 1. 專案簡介
**VitaGuide** 是一個致力於解決保健品資訊不對稱的 AI 數據平台。我們的目標是透過自動化爬蟲與 LLM 語義分析，將散落在電商平台（Momo, PChome）與品牌官網（D2C）的產品資訊整合，提供消費者一個透明、可比較的評選指南。

📅 **里程碑目標**：預計於 **2026/02/23** 上線 MVP 版本。

---
🛠️ 雙 AI 協作開發聲明 (AI Collaboration Manifesto)
[注意] 本專案採用 Gemini Code Assist 與 GitHub Copilot 雙引擎並行開發。為了確保系統一致性與資料對齊，所有 AI 助手必須嚴格遵守以下規範：

1. 職責分工 (Area of Responsibility)
Gemini Code Assist (左側)：負責 D2C 語義引擎 (agent_d2c_scanner.py)。專注於 LLM 語義解析、產品亮點提取與複雜結構判讀。

GitHub Copilot (右側)：負責 電商規則引擎 (general_scraper.py)。專注於 PChome/Momo 的 CSS Selector 優化、分頁邏輯與重複性代碼生成。

2. 資料欄位標準化 (Unified Schema)
所有爬蟲與 Agent 輸出的 CSV/DataFrame 必須統一欄位名稱，嚴禁自創名稱：

source: 來源平台 (如: Momo, Dietician, Daiken)

brand: 品牌名稱 (若無則填 "未標示")

title: 完整產品名稱

price: 特價/現價 (整數)

url: 產品詳細頁連結

image_url: 圖片完整連結 (需含 https:)

product_highlights: 產品亮點 (由 Gemini 提取，以分號 ; 分隔)
product_highlights: 產品亮點 (由 Gemini 提取，以分號 ; 分隔) (格式：字串，以分號 `;` 分隔，如 '亮點A;亮點B')

total_count: 總顆粒/包數

unit_price: 平均單價

3. 代碼風格與互操作性 (Code Integrity)
禁止衝突修改：未經指令，不要修改非負責範圍內的檔案。

共用工具函式：所有關於價格計算與文字清洗的 logic，優先參考 general_scraper.py 中的 calculate_unit_price。

Context 共享：在提供解決方案前，請先讀取 @workspace 中的最新 README.md 以確保掌握最新戰鬥位置。
---

## 2. 開發進度 (Status)

### ✅ 已完成 (Done)
- **綜合電商爬蟲** (`general_scraper.py`)：
  - 支援 Momo 與 PChome 關鍵字搜尋。
  - 自動清洗標題、計算單價、提取基礎標籤（如：游離型、FloraGLO）。
- **大研生醫 D2C 爬蟲** (`d2c_daiken_crawler.py`)：
  - 針對大研生醫官網結構客製化。
  - 支援 `og:image` 高畫質圖片抓取與規格解析。
- **Streamlit 前台儀表板** (`2_lutein_app.py`)：
  - 整合多來源資料（CSV 合併）。
  - 實作「卡片模式」與「表格模式」切換。
  - 支援品牌、價格、標籤篩選與排序。
  - **[New]** 修復圖片容器塌陷問題 (CSS) 與整合 AI 產品亮點顯示。
  - **[New]** 新增營養師輕食來源篩選與圖片網址修復。
- **D2C 爬蟲架構重構 (Strategy Pattern)**：
  - 建立 `scrapers/` 模組，實作 `BaseScraper` 父類別。
  - 完成 `DaikenScraper` 與 `VitaboxScraper` 子類別遷移。
  - 建立 `d2c_main.py` 總指揮，支援平行執行多品牌爬蟲。
- **營養師輕食 D2C 爬蟲** (`d2c_dietician_crawler.py`)：
  - 整合 Google Gemini 2.0 Flash API 進行「產品亮點」語義提取。
  - 實作 API Rate Limit (429) 自動重試機制。

### ✅ 今日完成 (2026/02/05) - general_scraper.py 升級
- **欄位標準化 (Schema Alignment)**：
  - ✅ 確保輸出 DataFrame 包含所有規範欄位：`source`, `brand`, `title`, `price`, `unit_price`, `total_count`, `url`, `image_url`, `product_highlights`。
  - ✅ 移除舊的 `tags`、`raw_data` 等非標準欄位，統一使用 `product_highlights`。
- **亮點提取器實現 (Highlight Extractor)**：
  - ✅ 建立 `extract_highlights(title)` 函式，使用 Regex 規則庫從標題中提取關鍵字。
  - ✅ 規則庫涵蓋：規格類 (rTG, EE, 游離型, 酯化型)、專利類 (FloraGLO, Lutemax, MenaQ7, BCM-95)、認證類 (IFOS, SGS, SNQ)、飲食類 (全素, 素食, 無糖, 無麩質)、營養素類 (蝦紅素, 花青素, DHA/EPA)。
  - ✅ 輸出格式：分號 `;` 分隔的字串（如 "游離型;全素"）。
- **圖片 URL 清洗強化**：
  - ✅ 實現 `clean_image_url(url)` 函式，確保所有網址都以 `https:` 開頭。
  - ✅ 修復協議雙重前綴問題（如：`https://domain/https://...`）。
- **品牌提取優化**：
  - ✅ 優先匹配標題開頭的 `【XXX】` 或 `[XXX]` 格式為品牌。
  - ✅ 次優先匹配品牌白名單（Swisse, Blackmores 等）。
  - ✅ 建立品牌白名單以減少誤判。
- **代碼驗證**：
  - ✅ 無語法錯誤。
  - ✅ `extract_highlights()` 函式測試通過（測試案例："【大研】視易適葉黃素(游離型/全素)" → "游離型;全素"）。

### 🚧 進行中 / 優化中 (In Progress)
- **全品牌 D2C 爬蟲任務執行 (Scheduled for Tomorrow - 2026/02/06)**：
  - 執行 `d2c_main.py` (大研、Vitabox) 與 `d2c_dietician_crawler.py`。
  - 驗證所有 CSV 資料的合併與前台顯示效果。
  - 驗證 `general_scraper.py` 產出的 CSV 能被 `2_lutein_app.py` 正確讀取。
- **Dietician Scraper 重構**：
  - 將 `d2c_dietician_crawler.py` 遷移至 `scrapers/dietician_scraper.py` 以符合新架構。

---

## 3. 特別備註 (Technical Notes)

### 🖼️ 圖片顯示修復邏輯
在 `2_lutein_app.py` 中，我們實作了 `clean_image_url` 函式來處理跨平台的圖片問題：
1. **協議補全**：自動將以 `//` 開頭的 URL 補上 `https:`（常見於大研生醫 CDN）。
2. **錯誤修正**：修復爬蟲可能產生的重複前綴（如 `https://domain/https://...`）。
3. **預設圖機制**：若圖片連結無效或遺失，自動替換為質感灰底的 Placeholder 圖片，避免版面破圖。

### 🤖 AI 整合
- 使用 `google.generativeai` (Gemini 1.5/2.0 Flash) 進行非結構化文本分析。
- 需配置 `.env` 檔案設定 `GOOGLE_API_KEY`。

---

## 4. 檔案地圖 (File Map)

| 檔案名稱 | 功能描述 |
| :--- | :--- |
| `2_lutein_app.py` | **[主程式]** Streamlit 前台入口，負責資料展示與互動。 |
| `d2c_daiken_crawler.py` | **[爬蟲]** 大研生醫官網專用，含規格計算邏輯。 |
| `d2c_dietician_crawler.py` | **[爬蟲]** 營養師輕食官網專用，整合 **Gemini AI** 提取亮點。 |
| `general_scraper.py` | **[爬蟲]** 綜合電商（Momo, PChome）通用爬蟲。 |
| `d2c_scraper.py` | **[模組]** D2C 爬蟲的通用框架原型。 |
| `1_fetch_data.py` | **[工具]** 用於處理與清洗本地原始 CSV 資料（如政府公開資料）。 |
| `app.py` / `2_app.py` | *[備份]* 舊版或測試用的 Streamlit 介面。 |
| `data/` | *[資料]* 存放所有爬蟲產出的 CSV 檔案。 |

## 5. 快速啟動 (Quick Start for AI)
請閱讀本文件掌握 Schema 與分工。Gemini 負責 D2C 語義解析，Copilot 負責電商規則優化。開工前請先檢查 `data/` 資料夾狀態。
---

## 6. Tomorrow 爬蟲執行計畫 (2026/02/06)

### 🎯 目標
實際執行所有爬蟲，生成統一格式的 CSV 資料，驗證前台展示效果。

### ✅ 執行清單

**Phase 1: 電商爬蟲** (~10 分鐘)
1. 執行 `general_scraper.py` 爬取 Momo 與 PChome 葉黃素產品
   - 輸出：`data/general_momo_lutein.csv` 與 `data/general_pchome_lutein.csv`
   - 驗證：檢查所有欄位（brand, title, product_highlights, image_url）完整度

**Phase 2: D2C 爬蟲** (~20 分鐘)
2. 執行 `d2c_main.py` 爬取大研與 Vitabox
   - 輸出：`data/d2c_daiken_all_products.csv` 與 `data/d2c_vitabox.csv`
3. 執行 `d2c_dietician_crawler.py` 爬取營養師輕食
   - 輸出：`data/d2c_dietician_products.csv`
   - 注意：需配置 `GOOGLE_API_KEY` 以使用 Gemini API

**Phase 3: 資料驗證** (~5 分鐘)
4. 檢查所有 CSV 是否都包含統一欄位：`source, brand, title, price, unit_price, total_count, url, image_url, product_highlights`
5. 執行 CSV 合併邏輯（參考 `2_lutein_app.py` 的資料載入部分）
6. 啟動 Streamlit：`streamlit run 2_lutein_app.py`
   - 驗證：圖片、品牌、亮點、價格排序等是否正常顯示

**Phase 4: 迭代修復** (as needed)
7. 根據前台顯示結果調整爬蟲邏輯
   - 品牌提取不準確？→ 擴展 `BRAND_WHITELIST`
   - 亮點缺失？→ 擴展 `extract_highlights()` 規則庫
   - 圖片破圖？→ 檢查 `clean_image_url()` 邏輯

### 💡 注意事項
- **環境變數**：確保 `.env` 配置了 `GOOGLE_API_KEY`（Gemini API Key）
- **網路連接**：爬蟲會發送大量 HTTP 請求，確保網路穩定
- **執行時間**：預計總耗時 ~30-40 分鐘，D2C 爬蟲可能因 API Rate Limit 而延長
- **備份**：執行前建議備份 `data/` 資料夾

### 📊 成功指標
- [ ] 所有 CSV 檔案生成無錯誤
- [ ] 每個 CSV 至少包含 10+ 筆產品記錄
- [ ] 前台正常加載所有數據、圖片完整、亮點資訊豐富
- [ ] 篩選與排序功能正常
- [ ] 達成上述指標 → **MVP 資料層就緒**
