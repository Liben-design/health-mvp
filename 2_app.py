import streamlit as st
import pandas as pd

st.set_page_config(page_title="葉黃素市場分析", page_icon="👁️", layout="wide")

# 讀取資料
@st.cache_data
def load_data():
    try:
        df = pd.read_csv("lutein_market_data.csv")
        # 處理價格欄位 (轉為數字，錯誤則補0)
        df['price'] = pd.to_numeric(df['price'], errors='coerce').fillna(0).astype(int)
        return df
    except FileNotFoundError:
        return None

df = load_data()

if df is None:
    st.error("❌ 找不到資料！請先執行 1_lutein_scraper.py")
    st.stop()

# ==========================================
# Header & 數據概況
# ==========================================
st.title("👁️ 葉黃素 (Lutein) 產品市場資料庫")
st.markdown("匯集 **MOMO**、**PChome** 與 **Google** 前 50 名熱搜產品")

# 數據指標
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("總收錄產品", f"{len(df)} 項")
with col2:
    # 只計算有價格的商品
    avg_price = df[df['price'] > 0]['price'].mean()
    st.metric("市場平均價格", f"${int(avg_price)}")
with col3:
    flora_count = df['tags'].str.contains("FloraGLO").sum()
    st.metric("FloraGLO 認證產品", f"{flora_count} 項")
with col4:
    free_form_count = df['tags'].str.contains("游離型").sum()
    st.metric("標榜「游離型」", f"{free_form_count} 項")

st.divider()

# ==========================================
# 側邊欄篩選
# ==========================================
st.sidebar.header("🔍 篩選條件")

# 平台篩選
sources = st.sidebar.multiselect("資料來源", df['source'].unique(), default=df['source'].unique())

# 關鍵字搜尋
keyword = st.sidebar.text_input("搜尋產品名稱")

# 特殊規格篩選 (使用我們剛剛爬蟲自動打的標籤)
st.sidebar.subheader("✨ 高價值規格篩選")
tag_filter = st.sidebar.radio("只想看：", ["全部", "💎FloraGLO 原料", "✅游離型", "➕含有蝦紅素"])

# ==========================================
# 資料過濾邏輯
# ==========================================
result = df[df['source'].isin(sources)]

if keyword:
    result = result[result['title'].str.contains(keyword, case=False)]

if tag_filter == "💎FloraGLO 原料":
    result = result[result['tags'].str.contains("FloraGLO", na=False)]
elif tag_filter == "✅游離型":
    result = result[result['tags'].str.contains("游離型", na=False)]
elif tag_filter == "➕含有蝦紅素":
    result = result[result['tags'].str.contains("蝦紅素", na=False)]

# ==========================================
# 顯示結果
# ==========================================
st.subheader(f"篩選結果：共 {len(result)} 筆")

# 顯示表格模式 (方便比較價格)
st.dataframe(
    result[['source', 'title', 'price', 'tags', 'url']],
    column_config={
        "source": "來源",
        "title": "產品名稱",
        "price": st.column_config.NumberColumn("價格", format="$%d"),
        "tags": "自動標籤 (規格亮點)",
        "url": st.column_config.LinkColumn("連結")
    },
    use_container_width=True,
    hide_index=True
)

# 顯示卡片模式 (Google 結果比較適合這樣看)
st.subheader("📝 詳細列表")
for index, row in result.iterrows():
    with st.expander(f"[{row['source']}] {row['title']} - ${row['price']}"):
        st.write(f"🏷️ **標籤**: {row['tags']}")
        st.caption(f"原始資料片段: {str(row['raw_data'])[:100]}...")
        st.markdown(f"[👉 前往商品頁面]({row['url']})")
