import streamlit as st
import pandas as pd
import os
import glob
import re

st.set_page_config(page_title="VITAGUIDE 維他評選指南 | 最懂你的保健品顧問", page_icon="🧭", layout="wide")

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

    /* 強制圖片容器保持比例，防止塌陷 */
    [data-testid="stImage"] {
        min-height: 200px; /* 給予最小高度 */
        display: flex;
        align-items: center;
        justify-content: center;
        background-color: #f8f9fa; /* 載入前的底色 */
        border-radius: 8px;
        overflow: hidden;
    }
    [data-testid="stImage"] img {
        object-fit: contain !important; /* 確保圖片不變形地填充 */
        width: 100% !important;
        height: auto !important;
        max-height: 250px;
    }
</style>
""", unsafe_allow_html=True)

# 讀取資料（優化：兼容多個關鍵字的 CSV 檔案合併讀取，減少重複代碼並支援擴展）
@st.cache_data
def calculate_specs_from_title(title, price):
    """從標題計算規格 (顆數/單位價格)，用於補全 Momo/PChome 資料"""
    if not isinstance(title, str) or not price or price == 0: return 0, 0.0
    unit_count, bundle_size = 0, 1
    
    # 1. 尋找數量 (30粒, 60顆)
    match = re.search(r'(\d+)\s*[粒顆錠包]', title)
    if match: unit_count = int(match.group(1))
    
    # 2. 尋找組數 (x3, 3入)
    match = re.search(r'[xX*]\s*(\d{1,2})\b', title)
    if match:
        bundle_size = int(match.group(1))
    else:
        match = re.search(r'[\s\uff0c\(\uff08](\d{1,2})\s*[入件組]', title)
        if match: bundle_size = int(match.group(1))
        
    if unit_count > 0:
        total_count = unit_count * bundle_size
        unit_price = round(price / total_count, 2) if total_count > 0 else 0
        return total_count, unit_price
    return 0, 0.0

def get_category_from_title(title):
    """從標題推斷產品類別"""
    if '葉黃素' in title: return '葉黃素'
    if '魚油' in title: return '魚油'
    if '益生菌' in title or '乳酸菌' in title: return '益生菌'
    return '其他'

def load_data(keywords=["葉黃素", "益生菌", "魚油"]):
    all_files = glob.glob("data/*.csv")
    df_list = []

    for filename in all_files:
        try:
            df = pd.read_csv(filename)
            
            # 欄位標準化
            rename_map = {'product_name': 'title', 'special_price': 'price', 'product_url': 'url'}
            df = df.rename(columns=rename_map)
            
            # 推斷來源
            if 'source' not in df.columns:
                if 'daiken' in filename.lower(): df['source'] = '大研生醫官網'
                elif 'dietician' in filename.lower(): df['source'] = '營養師輕食官網'
                elif 'momo' in filename.lower(): df['source'] = 'Momo'
                elif 'pchome' in filename.lower(): df['source'] = 'PChome'
                else: df['source'] = 'Other'
            
            # 推斷類別
            if 'd2c_daiken' in filename.lower() or 'd2c_dietician' in filename.lower():
                df['category'] = df['title'].apply(get_category_from_title)
            else:
                for cat in keywords:
                    if cat in filename:
                        df['category'] = cat
                        break
                else:
                    if 'category' not in df.columns:
                        df['category'] = '其他'
            
            df_list.append(df)
        except Exception as e:
            print(f"⚠️ 檔案 {filename} 讀取失敗: {e}")

    if not df_list: return None
    combined_df = pd.concat(df_list, ignore_index=True)

    # --- 資料清洗與補全 ---
    for col in ['price', 'total_count', 'unit_price']:
        if col not in combined_df.columns: combined_df[col] = 0
        combined_df[col] = pd.to_numeric(combined_df[col], errors='coerce').fillna(0)

    # 補全規格
    # 優化：若 total_count 為 0 或 unit_price 為 0，嘗試重新計算 (針對 D2C 資料補強)
    mask = (combined_df['total_count'] == 0) | (combined_df['unit_price'] == 0)
    if mask.any():
        specs = combined_df.loc[mask].apply(lambda x: calculate_specs_from_title(x['title'], x['price']), axis=1)
        combined_df.loc[mask, 'total_count'] = specs.apply(lambda x: x[0])
        combined_df.loc[mask, 'unit_price'] = specs.apply(lambda x: x[1])

    if 'brand' not in combined_df.columns:
        combined_df['brand'] = "未標示"
    else:
        combined_df['brand'] = combined_df['brand'].fillna("未標示").astype(str)

    # Schema 對齊：新欄位為 product_highlights，兼容舊 CSV 的 tags
    if 'product_highlights' not in combined_df.columns:
        combined_df['product_highlights'] = combined_df.get('tags', "")
    combined_df['product_highlights'] = combined_df['product_highlights'].fillna("").astype(str)

    # 圖片 URL 容錯處理：確保每個產品都有圖片，並修復 D2C 格式問題
    placeholder_img = "https://via.placeholder.com/300x200/f8f9fa/6c757d?text=VitaGuide"
    
    def clean_image_url(url):
        if pd.isna(url): return placeholder_img
        s_url = str(url).strip()
        if not s_url: return placeholder_img
        
        # 補全協議 (針對 //imgc.daikenshop.com)
        if s_url.startswith("//"):
            s_url = "https:" + s_url
            
        # 修正重複的 URL (針對營養師輕食爬蟲可能產生的錯誤)
        if "https://www.dietician.com.tw/https" in s_url:
            s_url = s_url.replace("https://www.dietician.com.tw/", "")
            
        # 簡單驗證
        if not s_url.startswith("http"):
            return placeholder_img
            
        return s_url

    combined_df['image_url'] = combined_df['image_url'].apply(clean_image_url)

    return combined_df

# ==========================================
# 側邊欄篩選（優化：基於合併資料的動態選擇器，提供更全面的產品類別檢視）
# ==========================================
st.sidebar.header("🔍 篩選條件")

# 載入所有資料
df = load_data(keywords=["葉黃素", "益生菌", "魚油"])
if df is None:
    st.error("目前尚無任何資料，請稍後再試。")
    st.stop()

# 產品類別選擇器（基於合併資料）
selected_category = st.sidebar.selectbox("產品類別", ["全部"] + sorted(df['category'].unique().tolist()))

# ==========================================
# Header & 數據概況
# ==========================================
st.title(f"VitaGuide 維他嚮導 - {selected_category} 評選指南")
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
    free_form_count = df['product_highlights'].str.contains("游離型", na=False).sum()
    st.metric("標榜「游離型」", f"{free_form_count} 項")

st.divider()

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

# 根據選擇的類別過濾
if selected_category != "全部":
    result = result[result['category'] == selected_category]

if keyword:
    result = result[result['title'].str.contains(keyword, case=False) | result['brand'].str.contains(keyword, case=False)]

if selected_brand != "全部":
    result = result[result['brand'] == selected_brand]

if tag_filter == "💎FloraGLO 原料":
    result = result[result['product_highlights'].str.contains("FloraGLO", na=False)]
elif tag_filter == "✅游離型":
    result = result[result['product_highlights'].str.contains("游離型", na=False)]
elif tag_filter == "➕含有蝦紅素":
    result = result[result['product_highlights'].str.contains("蝦紅素", na=False)]

# 排序邏輯
if sort_option == "價格由低到高":
    result = result.sort_values('price')
elif sort_option == "價格由高到低":
    result = result.sort_values('price', ascending=False)
elif sort_option == "單價由低到高":
    df_valid = result[result['unit_price'] > 0].sort_values('unit_price', ascending=True)
    df_invalid = result[result['unit_price'] == 0]
    result = pd.concat([df_valid, df_invalid])

# ==========================================
# 顯示結果 (圖文並茂版)
# ==========================================
st.subheader(f"搜尋結果：共 {len(result)} 筆")

# 模式切換
view_mode = st.radio("檢視模式", ["📊 表格模式 (快速比價)", "🖼️ 卡片模式 (瀏覽詳情)"], horizontal=True)

if "表格" in view_mode:
    # 使用 st.column_config.ImageColumn 來顯示圖片
    st.dataframe(
        result[['image_url', 'brand', 'title', 'price', 'product_highlights', 'url']],
        column_config={
            "image_url": st.column_config.ImageColumn("商品圖", help="產品預覽圖"),
            "brand": "品牌",
            "title": "產品名稱",
            "price": st.column_config.NumberColumn("價格", format="$%d"),
            "product_highlights": "規格亮點",
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
                # 顯示圖片 (優化：若 image_url 為空，顯示質感的預設佔位圖，提升使用者體驗)
                if row['image_url'] and str(row['image_url']).startswith('http') and 'dummyimage' not in str(row['image_url']):
                    st.image(row['image_url'], use_container_width=True)
                else:
                    # 質感預設佔位圖
                    st.image("https://via.placeholder.com/300x200/f8f9fa/6c757d?text=VitaGuide", use_container_width=True, caption="商品圖片")

                st.markdown(f"**{row['brand']}**")
                st.markdown(f"[{row['title']}]({row['url']})")
                st.markdown(f"💰 **${row['price']}**")

                # 顯示單價
                if row['unit_price'] > 0:
                    st.markdown(f"<span style='color:orange;'>💸 (每顆 ${row['unit_price']:.2f})</span>", unsafe_allow_html=True)

                # 顯示標籤膠囊
                highlights = [t.strip() for t in str(row['product_highlights']).split(";") if t.strip()]
                if highlights:
                    st.markdown(" ".join([f"`{t}`" for t in highlights]))

                # 顯示 AI 分析亮點
                if row['product_highlights']:
                    top_highlights = [t.strip() for t in str(row['product_highlights']).split(";") if t.strip()]
                    st.caption(" • ".join(top_highlights[:3]))

                st.markdown("---")
