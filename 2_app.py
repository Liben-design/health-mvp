import streamlit as st
import pandas as pd

# 1. 設定網頁標題與圖示 (Layout 設為 wide 讓空間更像 YouTube)
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
#  介面設計：Header & Search (仿 YouTube 風格)
# ==========================================

# 標題區
st.title("💊 台灣合規保健食品資料庫")

# 建立一個容器來放搜尋與篩選，讓視覺更集中
with st.container():
    # --- A. 搜尋框 (移到主畫面) ---
    # label_visibility="collapsed" 可以隱藏 "輸入關鍵字" 這幾個字，讓介面更乾淨
    col1, col2 = st.columns([4, 1]) # 控制搜尋框寬度
    with col1:
        keyword = st.text_input(
            "搜尋", 
            placeholder="🔍 搜尋產品名稱、品牌或成分...", 
            label_visibility="collapsed"
        )
    
    # --- B. 標籤篩選器 (Tag Filter) ---
    # 準備標籤資料： "全部" + 所有功效
    all_effects = ["全部"] + sorted(list(df['approved_effect'].unique()))
    
    # 使用 st.pills (膠囊按鈕)
    # 注意：這需要 Streamlit 1.40.0 以上版本
    # 如果您的版本較舊，請執行 `pip install --upgrade streamlit`
    st.write("") # 增加一點間距
    selected_effect = st.pills(
        "快速篩選功效",  # 標題 (會顯示在 pills 上方，也可隱藏)
        options=all_effects,
        default="全部",
        selection_mode="single", # 單選模式，類似 YouTube 點一個換一個
        label_visibility="collapsed" # 隱藏標題，讓它緊貼搜尋框
    )

st.divider()

# ==========================================
#  篩選邏輯 (Backend Logic)
# ==========================================

# 複製資料以供篩選
result = df.copy()

# 1. 標籤篩選
if selected_effect and selected_effect != "全部":
    result = result[result['approved_effect'] == selected_effect]

# 2. 關鍵字搜尋
if keyword:
    result = result[
        result['product_name'].str.contains(keyword, case=False) | 
        result['brand'].str.contains(keyword, case=False) |
        result['key_ingredients'].str.contains(keyword, case=False)
    ]

# ==========================================
#  顯示結果區 (Result Grid)
# ==========================================

st.subheader(f"搜尋結果：共 {len(result)} 筆")

# 卡片樣式優化
st.markdown("""
<style>
    .stExpander { border: 1px solid #f0f0f0; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.04); }
    /* 讓 pills 能夠橫向捲動 (若標籤太多) */
    div[data-testid="stPills"] {
        overflow-x: auto;
        white-space: nowrap;
        padding-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

if len(result) > 100:
    st.warning(f"⚠️ 資料過多（{len(result)} 筆），僅顯示前 100 筆，請縮小搜尋範圍。")
    result = result.head(100)

# 使用 Grid 排版 (每行 2 個，寬螢幕下看起來更舒服)
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
