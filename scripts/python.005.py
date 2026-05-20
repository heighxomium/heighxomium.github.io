#!/usr/bin/env python3
import os
import requests
from urllib.parse import urlparse

def download_filter_list(url):
    print(f"Downloading: {url}")
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text

def modify_title(content):
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("! Title:"):
            parts = line.split("! Title:", 1)
            if len(parts) == 2 and "(Optimized)" not in parts[1]:
                lines[i] = f"! Title: {parts[1].strip()} (Optimized)"
            break
    else:
        lines.insert(0, "! Title: Optimized Filter List")
    return "\n".join(lines)

def remove_generic_cosmetic(content):
    lines = content.splitlines()
    filtered = [line for line in lines if not (line.startswith("##") or line.startswith("#@#"))]
    return "\n".join(filtered)

def get_output_filename(url):
    name = os.path.basename(urlparse(url).path)
    return name if name else "filter.txt"

def main():
    url_list = "scripts/assets/url.filter.list.txt"
    out_dir = "scripts/assets/generated"
    os.makedirs(out_dir, exist_ok=True)

    with open(url_list) as f:
        urls = [line.strip() for line in f if line.strip()]

    for url in urls:
        try:
            content = download_filter_list(url)
            content = modify_title(content)
            content = remove_generic_cosmetic(content)
            out_path = os.path.join(out_dir, get_output_filename(url))
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Saved: {out_path}")
        except Exception as e:
            print(f"Failed {url}: {e}")

if __name__ == "__main__":
    main()
