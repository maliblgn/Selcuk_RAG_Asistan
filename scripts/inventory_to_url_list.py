import argparse
import json


def _iter_pdf_links(payload):
    if isinstance(payload.get("pdf_links"), list):
        yield from payload["pdf_links"]
    for source in payload.get("sources", []) or []:
        yield from source.get("pdf_links", []) or []


def inventory_to_urls(inventory_paths):
    seen = set()
    urls = []
    for path in inventory_paths:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        for link in _iter_pdf_links(payload):
            url = link.get("normalized_url") or link.get("url")
            if not url or url in seen:
                continue
            seen.add(url)
            urls.append(url)
    return urls


def parse_args():
    parser = argparse.ArgumentParser(description="PDF inventory JSON dosyalarindan URL listesi uretir.")
    parser.add_argument("--inventory", action="append", required=True, help="Inventory JSON dosyasi")
    parser.add_argument("--out", required=True, help="Cikti .txt dosyasi")
    return parser.parse_args()


def main():
    args = parse_args()
    urls = inventory_to_urls(args.inventory)
    with open(args.out, "w", encoding="utf-8") as f:
        for url in urls:
            f.write(url + "\n")
    print(f"{len(urls)} benzersiz PDF URL yazildi: {args.out}")


if __name__ == "__main__":
    main()
