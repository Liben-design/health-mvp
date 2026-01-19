import streamlit as st
import pandas as pd

st.set_page_config(page_title="葉黃素市場分析", page_icon="👁️", layout="wide")

# ==========================================
# CSS 優化：讓圖片在表格中顯示大一點
# ==========================================
st.markdown("""
<style>
    /* 調整表格圖片大小 */
    img {
        max-width: 100%;
        height: auto;
        border-radius: 4px;
    }
</style>
""", unsafe_allow_html=True)

# 讀取資料
@st.cache_data
def load_data():
    try:
        df = pd.read_csv("lutein_market_data.csv")
        df['price'] = pd.to_numeric(df['price'], errors='coerce').fillna(0).astype(int)
        # 確保有 brand 欄位，如果沒有則補上預設值
        if 'brand' not in df.columns:
            df['brand'] = "未標示"
        return df
    except FileNotFoundError:
        return None

df = load_data()

if df is None:
    st.error("❌ 找不到資料！請先執行 1_lutein_scraper.py 更新資料庫。")
    st.stop()

# ==========================================
# Header & 數據概況
# ==========================================
st.title("👁️ 葉黃素 (Lutein) 產品資料庫")
st.markdown("匯集 **MOMO** 與 **PChome** 即時比價資訊")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("總收錄產品", f"{len(df)} 項")
with col2:
    avg_price = df[df['price'] > 0]['price'].mean()
    st.metric("市場平均價格", f"${int(avg_price)}")
with col3:
    # 統計最多產品的品牌 Top 1
    top_brand = df['brand'].value_counts().idxmax()
    st.metric("產品最多品牌", top_brand)
with col4:
    free_form_count = df['tags'].str.contains("游離型").sum()
    st.metric("標榜「游離型」", f"{free_form_count} 項")

st.divider()

# ==========================================
# 側邊欄篩選
# ==========================================
st.sidebar.header("🔍 篩選條件")

keyword = st.sidebar.text_input("搜尋產品名稱或品牌")
sources = st.sidebar.multiselect("來源平台", df['source'].unique(), default=df['source'].unique())

# 新增：品牌篩選
all_brands = ["全部"] + sorted(df['brand'].unique().tolist())
selected_brand = st.sidebar.selectbox("品牌篩選", all_brands)

tag_filter = st.sidebar.radio("規格亮點：", ["全部", "💎FloraGLO 原料", "✅游離型", "➕含有蝦紅素"])

# ==========================================
# 資料過濾邏輯
# ==========================================
result = df[df['source'].isin(sources)]

if keyword:
    result = result[result['title'].str.contains(keyword, case=False) | result['brand'].str.contains(keyword, case=False)]

if selected_brand != "全部":
    result = result[result['brand'] == selected_brand]

if tag_filter == "💎FloraGLO 原料":
    result = result[result['tags'].str.contains("FloraGLO", na=False)]
elif tag_filter == "✅游離型":
    result = result[result['tags'].str.contains("游離型", na=False)]
elif tag_filter == "➕含有蝦紅素":
    result = result[result['tags'].str.contains("蝦紅素", na=False)]

# ==========================================
# 顯示結果 (圖文並茂版)
# ==========================================
st.subheader(f"搜尋結果：共 {len(result)} 筆")

# 模式切換
view_mode = st.radio("檢視模式", ["📊 表格模式 (快速比價)", "🖼️ 卡片模式 (瀏覽詳情)"], horizontal=True)

if "表格" in view_mode:
    # 使用 st.column_config.ImageColumn 來顯示圖片
    st.data_editor(
        result[['image_url', 'brand', 'title', 'price', 'tags', 'url']],
        column_config={
            "image_url": st.column_config.ImageColumn("圖片", help="產品預覽圖"),
            "brand": "品牌",
            "title": "產品名稱",
            "price": st.column_config.NumberColumn("價格", format="$%d"),
            "tags": "規格亮點",
            "url": st.column_config.LinkColumn("購買連結", display_text="前往賣場")
        },
        use_container_width=True,
        hide_index=True,
        disabled=True # 禁止編輯，只供瀏覽
    )

else:
    # 卡片模式 (Grid Layout)
    cols = st.columns(3) # 每行顯示 3 個
    for index, (idx, row) in enumerate(result.iterrows()):
        with cols[index % 3]:
            with st.container():
                # 顯示圖片 (如果沒有圖片連結，用預設圖)
                if row['image_url'] and str(row['image_url']).startswith('http'):
                    st.image(row['image_url'], use_column_width=True)
                else:
                    st.markdown("🖼️ *(無圖片)*")
                
                st.markdown(f"**{row['brand']}**")
                st.markdown(f"[{row['title']}]({row['url']})")
                st.markdown(f"💰 **${row['price']}**")
                
                # 顯示標籤膠囊
                if row['tags']:
                    tags = row['tags'].split(" ")
                    st.markdown(" ".join([f"`{t}`" for t in tags]))
                
                st.markdown("---")
