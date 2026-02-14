from data.agent_d2c_scanner import D2CScanner


def main():
    url = "https://shop.vitabox.com.tw/products/lutein"
    scanner = D2CScanner()
    result = scanner.scan_url(url)

    print("\n===== Vitabox Fix Debug =====")
    print(f"URL: {url}")
    if not result:
        print("Result: None")
        return

    print(f"Title: {result.get('title')}")
    print(f"Brand: {result.get('brand')}")
    print(f"Price: {result.get('price')}")
    print(f"Resolved URL: {result.get('url')}")


if __name__ == "__main__":
    main()
