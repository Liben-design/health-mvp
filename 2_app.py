import streamlit as st
import pandas as pd

# 1. 頁面設定
st.set_page_config(page_title="葉黃素市場分析", page_icon="👁️", layout="wide")

# 2. CSS 優化 (讓圖片在表格中美觀顯示)
st.markdown("""
<style>
    img {
        max-width: 100%;
        height: auto;
        border-radius: 4px;
    }
    .stMetric {
        background-color: #f9f9f9;
        padding: 10px;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)

# 3. 讀取資料 (加入防呆機制)
@st.cache_data
def load_data():
    try:
        # 嘗試讀取資料
        df = pd.read_csv("lutein_market_data.csv")
        
        # 處理價格 (轉為數字)
        df['price'] = pd.to_numeric(df['price'], errors='coerce').fillna(0).astype(int)
        
        # --- 防呆補強：如果 CSV 缺欄位，自動補上，避免報錯 ---
        if 'brand' not in df.columns:
            df['brand'] = "未標示"
        if 'image_url' not in df.columns:
            df['image_url'] = None
        if 'tags' not in df.columns:
            df['tags'] = ""
        # ------------------------------------------------
            
        return df
    except FileNotFoundError:
        return None

df = load_data()

# 如果找不到資料或是資料是空的
if df is None or df.empty:
    st.error("❌ 找不到資料檔！請確認是否已執行 1_lutein_scraper.py 並產生了 lutein_market_data.csv")
    st.stop()

# ==========================================
# 介面設計：Header & 數據概況
# ==========================================
st.title("👁️ 葉黃素 (Lutein) 產品資料庫")
st.markdown("匯集 **MOMO** 與 **PChome** 即時比價資訊")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("總收錄產品", f"{len(df)} 項")
with col2:
    # 排除價格為 0 的商品再計算平均
    valid_prices = df[df['price'] > 0]['price']
    avg_price = valid_prices.mean() if not valid_prices.empty else 0
    st.metric("市場平均價格", f"${int(avg_price)}")
with col3:
    # 統計最多產品的品牌
    if 'brand' in df.columns and not df['brand'].empty:
        top_brand = df['brand'].value_counts().idxmax()
        st.metric("產品最多品牌", top_brand)
    else:
        st.metric("產品最多品牌", "N/A")
with col4:
    # 統計游離型
    if 'tags' in df.columns:
        free_form_count = df['tags'].str.contains("游離型", na=False).sum()
        st.metric("標榜「游離型」", f"{free_form_count} 項")

st.divider()

# ==========================================
# 側邊欄篩選
# ==========================================
st.sidebar.header("🔍 篩選條件")

# 關鍵字搜尋
keyword = st.sidebar.text_input("搜尋產品名稱或品牌")

# 平台篩選
if 'source' in df.columns:
    sources = st.sidebar.multiselect("來源平台", df['source'].unique(), default=df['source'].unique())
else:
    sources = []

# 品牌篩選
all_brands = ["全部"] + sorted(df['brand'].astype(str).unique().tolist())
selected_brand = st.sidebar.selectbox("品牌篩選", all_brands)

# 規格篩選
tag_filter = st.sidebar.radio("規格亮點：", ["全部", "💎FloraGLO 原料", "✅游離型", "➕含有蝦紅素"])

# ==========================================
# 資料過濾邏輯
# ==========================================
result = df.copy()

# 1. 來源篩選
if sources:
    result = result[result['source'].isin(sources)]

# 2. 關鍵字篩選
if keyword:
    result = result[
        result['title'].str.contains(keyword, case=False, na=False) | 
        result['brand'].str.contains(keyword, case=False, na=False)
    ]

# 3. 品牌篩選
if selected_brand != "全部":
    result = result[result['brand'] == selected_brand]

# 4. 標籤篩選
if tag_filter == "💎FloraGLO 原料":
    result = result[result['tags'].str.contains("FloraGLO", na=False)]
elif tag_filter == "✅游離型":
    result = result[result['tags'].str.contains("游離型", na=False)]
elif tag_filter == "➕含有蝦紅素":
    result = result[result['tags'].str.contains("蝦紅素", na=False)]

# ==========================================
# 顯示結果
# ==========================================
st.subheader(f"搜尋結果：共 {len(result)} 筆")

# 檢視模式切換
view_mode = st.radio("檢視模式", ["📊 表格模式 (快速比價)", "🖼️ 卡片模式 (瀏覽詳情)"], horizontal=True)

if "表格" in view_mode:
    # 使用 st.column_config 來美化表格
    st.data_editor(
        result,
        column_config={
            "image_url": st.column_config.ImageColumn("圖片", help="產品預覽圖"),
            "brand": "品牌",
            "title": "產品名稱",
            "price": st.column_config.NumberColumn("價格", format="$%d"),
            "tags": "規格亮點",
            "url": st.column_config.LinkColumn("購買連結", display_text="前往賣場"),
            "source": "來源",
            "raw_data": None # 隱藏原始資料欄位
        },
        use_container_width=True,
        hide_index=True,
        disabled=True # 禁止編輯，只供瀏覽
    )

else:
    # 卡片模式 (Grid Layout)
    if len(result) == 0:
        st.info("沒有符合條件的商品")
    else:
        cols = st.columns(3) # 每行 3 個
        for index, (idx, row) in enumerate(result.iterrows()):
            with cols[index % 3]:
                with st.container():
                    # 顯示圖片
                    if row.get('image_url') and str(row['image_url']).startswith('http'):
                        st.image(row['image_url'], use_column_width=True)
                    else:
                        st.markdown("🖼️ *(無圖片)*")
                    
                    # 顯示資訊
                    st.markdown(f"**{row['brand']}**")
                    st.markdown(f"[{row['title']}]({row['url']})")
                    st.markdown(f"💰 **${row['price']}**")
                    
                    # 顯示標籤
                    if row.get('tags'):
                        tags = str(row['tags']).split(" ")
                        st.markdown(" ".join([f"`{t}`" for t in tags if t]))
                    
                    st.markdown("---")