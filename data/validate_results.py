import pandas as pd
import os

def validate():
    csv_path = "data/d2c_full_database.csv"
    if not os.path.exists(csv_path):
        print("❌ 找不到資料檔，請先執行 batch_scanner.py")
        return

    df = pd.read_csv(csv_path)
    print(f"📊 資料總筆數: {len(df)}")
    print("-" * 30)

    # 1. 品牌分佈
    print("🏷️  品牌統計:")
    print(df['brand'].value_counts())
    print("-" * 30)

    # 2. 價格檢查
    zero_price = df[df['price'] == 0]
    print(f"💰 價格異常 (Price=0): {len(zero_price)} 筆")
    if not zero_price.empty:
        print("   ⚠️ 異常品牌分佈:")
        print(zero_price['brand'].value_counts())
        # 列出前 3 筆異常網址供檢查
        print("   🔍 範例網址:")
        for url in zero_price['url'].head(3):
            print(f"      - {url}")
    print("-" * 30)

    # 3. 圖片檢查
    missing_img = df[df['image_url'].isna() | (df['image_url'] == "")]
    print(f"🖼️  缺圖數量: {len(missing_img)} 筆")
    
    # 4. 亮點檢查
    missing_highlights = df[df['product_highlights'].isna() | (df['product_highlights'] == "")]
    print(f"✨ 缺產品亮點: {len(missing_highlights)} 筆")
    
    print("-" * 30)
    print("✅ 驗收報告完畢")

if __name__ == "__main__":
    validate()