import pandas as pd


def main():
    df = pd.read_csv("data/d2c_full_database.csv")
    sub = df[df["brand"].astype(str).str.strip() == "九五之丹"].copy()
    sub = sub.sort_values("url").drop_duplicates(subset=["url"], keep="last")

    print(f"[95dan rows] {len(sub)}")
    if len(sub) == 0:
        return

    cols = [c for c in ["brand", "title", "price", "url"] if c in sub.columns]
    print(sub[cols].to_string(index=False))

    out_path = "data/95dan_products_full.csv"
    sub.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"[exported] {out_path}")


if __name__ == "__main__":
    main()
