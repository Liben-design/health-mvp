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

### 🚧 進行中 / 優化中 (In Progress)
- **營養師輕食 D2C 爬蟲** (`d2c_dietician_crawler.py`)：
  - [x] 基礎爬取邏輯（Playwright）。
  - [x] 整合 Google Gemini API 進行「產品亮點」語義提取。
  - [ ] **待辦**：優化價格抓取策略（解決 JSON-LD 解析問題）與自動化排程。
- **通用型 D2C 語義 Agent**：
  - 目標：建立一個不依賴特定 CSS Selector，能通用於大多數 Shopify/91APP 架構網站的 AI 爬蟲。

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
