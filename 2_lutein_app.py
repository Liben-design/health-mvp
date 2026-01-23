import streamlit as st
import pandas as pd

st.set_page_config(page_title="VitaGuide 維他嚮導 | 最懂你的保健品顧問", page_icon="🧭", layout="wide")

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
        # 檢查並補齊欄位
        if 'unit_price' not in df.columns:
            df['unit_price'] = 0
        if 'total_count' not in df.columns:
            df['total_count'] = 1
        # 原本的轉換邏輯
        df['price'] = pd.to_numeric(df['price'], errors='coerce').fillna(0).astype(int)
        # 確保有 brand 欄位，如果沒有則補上預設值
        if 'brand' not in df.columns:
            df['brand'] = "未標示"
        df['tags'] = df['tags'].fillna("")
        df['unit_price'] = pd.to_numeric(df['unit_price'], errors='coerce').fillna(0)
        df['total_count'] = pd.to_numeric(df['total_count'], errors='coerce').fillna(1)
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
st.title("🧭 VitaGuide 維他嚮導")
st.markdown("帶你穿越保健品迷霧，只買對的，不買貴的。")

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

# 新增：排序選項
sort_option = st.sidebar.selectbox("排序方式", ["預設", "價格由低到高", "價格由高到低", "單價由低到高"])

st.sidebar.warning("**⚠️ 免責聲明**：\n\n本平台資訊僅供參考，不代表醫療建議。產品規格與價格以電商平台當下顯示為準。食用前請諮詢專業醫師或藥師。")

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

# 排序邏輯
if sort_option == "價格由低到高":
    result = result.sort_values('price')
elif sort_option == "價格由高到低":
    result = result.sort_values('price', ascending=False)
elif sort_option == "單價由低到高":
    result = result[result['unit_price'] > 0].sort_values('unit_price')

# ==========================================
# 顯示結果 (圖文並茂版)
# ==========================================
st.subheader(f"搜尋結果：共 {len(result)} 筆")

# 模式切換
view_mode = st.radio("檢視模式", ["📊 表格模式 (快速比價)", "🖼️ 卡片模式 (瀏覽詳情)"], horizontal=True)

if "表格" in view_mode:
    # 使用 st.column_config.ImageColumn 來顯示圖片
    st.dataframe(
        result[['image_url', 'brand', 'title', 'price', 'tags', 'url']],
        column_config={
            "image_url": st.column_config.ImageColumn("商品圖", help="產品預覽圖"),
            "brand": "品牌",
            "title": "產品名稱",
            "price": st.column_config.NumberColumn("價格", format="$%d"),
            "tags": "規格亮點",
            "url": st.column_config.LinkColumn("前往購買", display_text="前往購買")
        },
        use_container_width=True,
        hide_index=True
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

                # 顯示單價
                if row['unit_price'] > 0:
                    st.markdown(f"<span style='color:orange;'>💸 (每顆 ${row['unit_price']:.2f})</span>", unsafe_allow_html=True)

                # 顯示標籤膠囊
                tags = row['tags'].split(" ") if row['tags'] else []
                if tags:
                    st.markdown(" ".join([f"`{t}`" for t in tags]))

                st.markdown("---")
