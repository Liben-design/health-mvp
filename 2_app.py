import streamlit as st
import pandas as pd

# 1. 設定網頁標題與圖示
st.set_page_config(
    page_title="台灣合規保健品資料庫", 
    page_icon="💊", 
    layout="wide"
)

# 2. 讀取資料
# 這裡會讀取您剛剛產生的 health_data.csv
try:
    df = pd.read_csv("health_data.csv")
    # 把 NaN (空值) 填補為 "未標示"，避免顯示錯誤
    df.fillna("未標示", inplace=True)
except FileNotFoundError:
    st.error("❌ 找不到資料檔！請確認 health_data.csv 是否在同一個資料夾內。")
    st.stop()

# 3. 網站主標題區
st.title("💊 台灣合規保健食品資料庫 (MVP)")
st.markdown(f"目前收錄 **{len(df)}** 筆衛福部核准產品，資料來源：政府資料開放平台 (CSV匯入)")
st.divider()

# 4. 側邊欄：搜尋與篩選條件
st.sidebar.header("🔍 搜尋篩選")

# 關鍵字搜尋
keyword = st.sidebar.text_input("輸入產品名稱、品牌或成分")

# 功效篩選 (製作下拉選單)
# 取得所有不重複的功效，並加上 "全部" 選項
all_effects = ["全部"] + sorted(list(df['approved_effect'].unique()))
selected_effect = st.sidebar.selectbox("選擇保健功效", all_effects)

# 5. 篩選邏輯 (核心功能)
# 先複製一份資料來篩選
result = df.copy()

# 如果有選功效，就過濾功效
if selected_effect != "全部":
    result = result[result['approved_effect'] == selected_effect]

# 如果有輸入關鍵字，就過濾名稱、品牌或成分
if keyword:
    result = result[
        result['product_name'].str.contains(keyword, case=False) | 
        result['brand'].str.contains(keyword, case=False) |
        result['key_ingredients'].str.contains(keyword, case=False)
    ]

# 6. 顯示結果區
st.subheader(f"搜尋結果：共 {len(result)} 筆")

# 使用 CSS 美化一下卡片 (非必要，但比較好看)
st.markdown("""
<style>
    .stExpander { border: 1px solid #ddd; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
</style>
""", unsafe_allow_html=True)

# 迴圈顯示每一筆產品
# 為了避免畫面太長，如果超過 50 筆，只顯示前 50 筆並提示
if len(result) > 100:
    st.warning(f"⚠️ 資料過多（{len(result)} 筆），僅顯示前 100 筆，請縮小搜尋範圍。")
    result = result.head(100)

# 使用 Grid 排版 (每行顯示 2 個)
cols = st.columns(2)

for index, (idx, row) in enumerate(result.iterrows()):
    # 決定顯示在左欄還是右欄
    with cols[index % 2]:
        # 建立可展開的卡片
        with st.expander(f"📌 {row['product_name']}"):
            st.caption(f"廠商：{row['brand']}")
            
            st.markdown(f"**許可證字號**：`{row['license_id']}`")
            
            # 用藍色醒目提示功效
            st.info(f"✅ **核准功效**：\n{row['approved_effect']}")
            
            st.markdown(f"🧪 **主要成分**：\n{row['key_ingredients']}")
            
            # 這裡未來可以加上價格查詢連結
            search_url = f"https://www.google.com/search?q={row['product_name']}"
            st.markdown(f"[🔎 Google 搜尋此產品]({search_url})")

# 7. 頁尾
st.divider()
st.caption("本網站僅為資訊彙整 MVP 原型，所有數據以衛生福利部公告為準。")