from data.sitemap_parser import SitemapParser
import data.batch_scanner as batch


def main():
    brand = "BHK's"
    domain = "https://www.bhks.com.tw/"

    parser = SitemapParser()
    items = parser.process_domain(brand, domain)

    filtered_count = len(items)
    cap = batch.MAX_URLS_PER_BRAND
    capped_count = min(filtered_count, cap)

    print(f"brand={brand}")
    print(f"filtered_urls={filtered_count}")
    print(f"scan_cap={cap}")
    print(f"would_scan_urls={capped_count}")


if __name__ == "__main__":
    main()