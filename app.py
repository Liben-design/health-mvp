import streamlit as st
import pandas as pd
import os
import glob

# --- 頁面設定 ---
st.set_page_config(page_title="大研生醫產品儀表板", layout="wide")

# --- 資料載入與快取 ---
@st.cache_data
def load_data(folder_path):
    """從資料夾載入所有 CSV 並合併 (包含大研官網、Momo、PChome)"""
    all_files = glob.glob(os.path.join(folder_path, "*.csv"))
    df_list = []
    
    for filename in all_files:
        try:
            df = pd.read_csv(filename)
            
            # 欄位標準化：將大研生醫爬蟲的欄位對應到通用格式
            # product_name -> title, special_price -> price, product_url -> url
            rename_map = {
                'product_name': 'title',
                'special_price': 'price',
                'product_url': 'url'
            }
            df = df.rename(columns=rename_map)
            
            # 若沒有 source 欄位，嘗試從檔名推斷來源
            if 'source' not in df.columns:
                if 'daiken' in filename.lower():
                    df['source'] = '大研生醫官網'
                elif 'momo' in filename.lower():
                    df['source'] = 'Momo'
                elif 'pchome' in filename.lower():
                    df['source'] = 'PChome'
                else:
                    df['source'] = 'Other'

            # 數值轉換 (確保 price, total_count, unit_price 為數字)
            for col in ['price', 'total_count', 'unit_price']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            df_list.append(df)
        except Exception as e:
            st.warning(f"略過檔案 {filename}: {e}")
            
    if not df_list:
        return pd.DataFrame()
        
    # 合併所有來源的資料
    return pd.concat(df_list, ignore_index=True)

# --- 產品卡片顯示函式 ---
def display_products(df):
    """以卡片形式顯示產品資訊"""
    if df.empty:
        st.warning("此分類下沒有找到對應的產品。")
        return

    # 每行顯示 3 個產品
    cols = st.columns(3)
    for i, row in enumerate(df.itertuples()):
        col = cols[i % 3]
        with col:
            # 顯示產品名稱與圖片
            st.subheader(row.title)
            st.caption(f"來源: {getattr(row, 'source', '未知')}")
            
            if hasattr(row, 'image_url') and pd.notna(row.image_url) and row.image_url:
                st.image(row.image_url, use_column_width=True, caption=f"價格: ${row.price:,.0f}")

            # 顯示規格與標籤
            if hasattr(row, 'total_count') and row.total_count > 0 and hasattr(row, 'unit_price') and row.unit_price > 0:
                st.markdown(f"**規格:** {int(row.total_count)} 粒/包 (每單位: ${row.unit_price:.2f})")
            
            if hasattr(row, 'tags') and pd.notna(row.tags) and row.tags:
                st.markdown(f"**特色:** `{row.tags}`")

            # 提供購買連結
            if hasattr(row, 'url') and pd.notna(row.url):
                st.link_button("前往購買 ➔", row.url)
            st.markdown("---")

# --- 主應用程式 ---
st.title("大研生醫產品儀表板")

df = load_data('data')

if not df.empty:
    # 側邊欄篩選：讓使用者可以選擇要看哪個平台的資料
    st.sidebar.header("篩選條件")
    if 'source' in df.columns:
        sources = list(df['source'].unique())
        selected_sources = st.sidebar.multiselect("選擇來源平台", sources, default=sources)
        if selected_sources:
            df = df[df['source'].isin(selected_sources)]

    # 建立分類標籤頁
    tab1, tab2, tab3 = st.tabs(["葉黃素系列", "魚油系列", "益生菌系列"])

    with tab1:
        display_products(df[df['title'].str.contains("葉黃素", na=False)])
    with tab2:
        display_products(df[df['title'].str.contains("魚油", na=False)])
    with tab3:
        display_products(df[df['title'].str.contains("益生菌|乳酸菌", na=False)])