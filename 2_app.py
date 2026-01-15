import streamlit as st
import pandas as pd

# 1. 設定網頁標題與圖示
st.set_page_config(
    page_title="台灣合規保健品資料庫", 
    page_icon="💊", 
    layout="wide"
)

# 2. 讀取資料
try:
    df = pd.read_csv("health_data.csv")
    df.fillna("未標示", inplace=True)
except FileNotFoundError:
    st.error("❌ 找不到資料檔！請確認 health_data.csv 是否在同一個資料夾內。")
    st.stop()

# ==========================================
#  介面設計：Header & Search
# ==========================================

st.title("💊 台灣合規保健食品資料庫")

with st.container():
    # --- A. 搜尋框 ---
    col1, col2 = st.columns([4, 1])
    with col1:
        keyword = st.text_input(
            "搜尋", 
            placeholder="🔍 搜尋產品名稱、品牌或成分...", 
            label_visibility="collapsed"
        )
    
    # --- B. 標籤篩選器 (st.pills) ---
    all_effects = ["全部"] + sorted(list(df['approved_effect'].unique()))
    
    st.write("") 
    # 這裡的 pills 會被下方的 CSS 改造為垂直捲動區塊
    selected_effect = st.pills(
        "快速篩選功效",
        options=all_effects,
        default="全部",
        selection_mode="single",
        label_visibility="collapsed"
    )

st.divider()

# ==========================================
#  篩選邏輯
# ==========================================

result = df.copy()

if selected_effect and selected_effect != "全部":
    result = result[result['approved_effect'] == selected_effect]

if keyword:
    result = result[
        result['product_name'].str.contains(keyword, case=False) | 
        result['brand'].str.contains(keyword, case=False) |
        result['key_ingredients'].str.contains(keyword, case=False)
    ]

# ==========================================
#  顯示結果區 & CSS 優化 (關鍵修改處)
# ==========================================

st.subheader(f"搜尋結果：共 {len(result)} 筆")

# ↓↓↓↓↓ 這裡做了重要的 CSS 修改 ↓↓↓↓↓
st.markdown("""
<style>
    /* 1. 優化卡片外觀 */
    .stExpander { 
        border: 1px solid #f0f0f0; 
        border-radius: 12px; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.04); 
    }

    /* 2. 改造 stPills 為垂直捲動容器 */
    div[data-testid="stPills"] {
        display: flex;         /* 啟用彈性盒模型 */
        flex-wrap: wrap;       /* 讓標籤自動換行 (關鍵！) */
        gap: 8px;              /* 標籤之間的間距 */
        
        /* 限制高度與捲動設定 */
        max-height: 180px;     /* 約 4.5 行的高度 (一行約 40px) */
        overflow-y: auto;      /* 超過高度時顯示垂直捲動軸 */
        overflow-x: hidden;    /* 隱藏水平捲動軸 */
        
        /* 視覺優化 */
        padding: 10px;         /* 內距，避免文字貼邊 */
        background-color: rgba(240, 242, 246, 0.3); /* 極淡的灰色背景示意容器範圍 (可選) */
        border-radius: 8px;    /* 容器圓角 */
    }

    /* 3. 美化捲動條 (Scrollbar) - 讓它看起來更現代 */
    div[data-testid="stPills"]::-webkit-scrollbar {
        width: 8px;            /* 捲動條寬度 */
    }
    div[data-testid="stPills"]::-webkit-scrollbar-track {
        background: transparent; 
    }
    div[data-testid="stPills"]::-webkit-scrollbar-thumb {
        background-color: #d1d5db; /* 捲動條顏色 (淺灰) */
        border-radius: 4px;    /* 捲動條圓角 */
    }
    div[data-testid="stPills"]::-webkit-scrollbar-thumb:hover {
        background-color: #9ca3af; /* 滑鼠移過去變深灰 */
    }
</style>
""", unsafe_allow_html=True)
# ↑↑↑↑↑ 修改結束 ↑↑↑↑↑

if len(result) > 100:
    st.warning(f"⚠️ 資料過多（{len(result)} 筆），僅顯示前 100 筆，請縮小搜尋範圍。")
    result = result.head(100)

cols = st.columns(2)

for index, (idx, row) in enumerate(result.iterrows()):
    with cols[index % 2]:
        with st.expander(f"📌 {row['product_name']}"):
            st.caption(f"廠商：{row['brand']}")
            st.markdown(f"**許可證字號**：`{row['license_id']}`")
            st.info(f"✅ **核准功效**：\n{row['approved_effect']}")
            st.markdown(f"🧪 **主要成分**：\n{row['key_ingredients']}")
            
            search_url = f"https://www.google.com/search?q={row['product_name']}"
            st.markdown(f"[🔎 Google 搜尋]({search_url})")

st.divider()
st.caption("本網站僅為資訊彙整 MVP 原型，所有數據以衛生福利部公告為準。")
