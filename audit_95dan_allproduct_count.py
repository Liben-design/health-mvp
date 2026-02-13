import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import pandas as pd


BASE = "https://www.95dan.com.tw"
LIST_URL = f"{BASE}/allproduct"


def normalize(href: str) -> str:
    return urljoin(BASE + "/", href.strip())


def main():
    html = requests.get(LIST_URL, timeout=20).text
    soup = BeautifulSoup(html, "html.parser")

    # 產品卡片常見是導向單一 slug 頁面
    candidates = []
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        if not href:
            continue
        u = normalize(href)
        if "95dan.com.tw" not in u:
            continue
        candidates.append(u)

    # 過濾明顯非產品路徑
    deny_tokens = [
        "/allproduct", "/about", "/aboutus", "/news", "/blog", "/media", "/kol", "/corporate",
        "/shippingpolicy", "/refund", "/signin", "/sgs", "/shopee", "/terms", "/policy", "/privacy", "/contact",
        "/mondeselection", "/material", "/95danboss", "/cdn-cgi/", "/upload/"
    ]

    products = []
    seen = set()
    for u in candidates:
        lu = u.lower()
        if any(t in lu for t in deny_tokens):
            continue
        # 單層 slug 規則
        path = lu.replace("https://www.95dan.com.tw", "").strip("/")
        if not path or "/" in path:
            continue
        if u not in seen:
            seen.add(u)
            products.append(u)

    print(f"[allproduct inferred count] {len(products)}")
    for u in sorted(products):
        print(u)

    # 與目前資料庫比對
    df = pd.read_csv("data/d2c_full_database.csv")
    cur = (
        df[df["brand"].astype(str).str.strip() == "九五之丹"]["url"]
        .astype(str).str.strip().tolist()
    )
    cur_set = set(cur)
    missing = [u for u in sorted(products) if u not in cur_set]

    print(f"[current db count for 95dan] {len(cur_set)}")
    print(f"[missing from db] {len(missing)}")
    for u in missing:
        print("MISSING", u)


if __name__ == "__main__":
    main()
