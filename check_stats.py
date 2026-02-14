import json
from pathlib import Path

import pandas as pd


ISSUE_PATH = Path("data/issue_tracker/issues_20260213_114501.json")
DB_PATH = Path("data/d2c_full_database.csv")


def main():
    issue = json.loads(ISSUE_PATH.read_text(encoding="utf-8"))

    print("brand,parsed,capped,success,failed,success_rate")
    for brand, pm in issue["parse_metrics"].items():
        success = issue["success_metrics"].get(brand, 0)
        cap = pm.get("capped_urls", 0)
        fail = cap - success
        rate = (success / cap * 100) if cap else 0
        print(f"{brand},{pm.get('parsed_urls', 0)},{cap},{success},{fail},{rate:.1f}%")

    brands = list(issue["parse_metrics"].keys())
    df = pd.read_csv(DB_PATH)
    df11 = df[df["brand"].isin(brands)].copy()

    print("\nTop11 rows in full db:", len(df11))
    price = pd.to_numeric(df11["price"], errors="coerce").fillna(0)
    print("price<=0:", int((price <= 0).sum()))
    print("missing image:", int(df11["image_url"].isna().sum() + (df11["image_url"].fillna("") == "").sum()))
    print(
        "missing highlights:",
        int(df11["product_highlights"].isna().sum() + (df11["product_highlights"].fillna("") == "").sum()),
    )


if __name__ == "__main__":
    main()