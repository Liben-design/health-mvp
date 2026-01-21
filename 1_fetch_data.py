import pandas as pd
import os

# 設定您剛剛下載並改名的檔案名稱
LOCAL_FILE_NAME = "raw_data.csv"

print(f"📂 準備讀取本地檔案: {LOCAL_FILE_NAME} ...")

# 檢查檔案是否存在
if not os.path.exists(LOCAL_FILE_NAME):
    print(f"❌ 錯誤：找不到檔案！請確認您有把下載的檔案改名為 '{LOCAL_FILE_NAME}' 並且放在同一個資料夾內。")
else:
    try:
        # --- 嘗試讀取 CSV (處理台灣常見的編碼問題) ---
        # 政府資料有時候是 UTF-8，有時候是 Big5 (繁體中文舊編碼)
        try:
            # 先試試看通用的 utf-8
            df = pd.read_csv(LOCAL_FILE_NAME, encoding='utf-8')
        except UnicodeDecodeError:
            print("⚠️ UTF-8 讀取失敗，嘗試使用 Big5 編碼...")
            # 如果失敗，改用 big5 讀取
            df = pd.read_csv(LOCAL_FILE_NAME, encoding='cp950') # cp950 是標準繁體中文編碼

        print(f"✅ 讀取成功！原始資料共有 {len(df)} 筆")

        # --- 資料清洗與對應 (Mapping) ---
        # 請根據您下載的 CSV 實際欄位名稱調整這裡的 Key
        # 政府 CSV 的欄位名稱通常是中文，例如：「許可證字號」、「中文品名」
        
        # 我們先印出欄位名稱，讓您確認
        print("🔍 檔案內的欄位名稱有：", df.columns.tolist())

        # 定義欄位對照表 (左邊是您想改成的英文，右邊是 CSV 裡的中文標題)
        # 注意：如果您的 CSV 欄位名稱不同，請修改右邊的中文字
        rename_dict = {
            "license_id": "許可證字號",
            "product_name": "中文品名",
            "brand": "申請商",
            "approved_effect": "保健功效",
            "key_ingredients": "保健功效相關成分"
        }

        # 為了容錯，我們使用反向查找，或者直接建立新 DataFrame
        # 簡單一點：直接用中文欄位來篩選，最後再改名
        
        # 檢查 CSV 裡有沒有這些中文欄位
        valid_columns = []
        for eng_col, chin_col in rename_dict.items():
            if chin_col in df.columns:
                valid_columns.append(chin_col)
            else:
                print(f"⚠️ 警告：找不到欄位 '{chin_col}'，可能會影響顯示。")

        # 只保留存在的欄位
        df = df[valid_columns]
        
        # 將中文欄位改名為英文 (為了給 app.py 用)
        # 製作一個反向字典： {"許可證字號": "license_id", ...}
        reverse_rename = {v: k for k, v in rename_dict.items()}
        df.rename(columns=reverse_rename, inplace=True)

        # --- 存成我們系統專用的 health_data.csv ---
        df.to_csv("health_data.csv", index=False, encoding="utf-8-sig")
        print(f"🎉 處理完成！已產出乾淨的資料檔 'health_data.csv' (共 {len(df)} 筆)")
        
    except Exception as e:
        print(f"❌ 發生預期外的錯誤: {e}")