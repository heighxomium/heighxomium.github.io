#!/usr/bin/env python3
import os
import re
import requests
from urllib.parse import urlparse
from collections import defaultdict

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

def get_optimized_filename(url, existing_names):
    """Generate filename: replace -/_ with ., add .optimized before extension, handle duplicates."""
    parsed = urlparse(url)
    path = parsed.path
    base = os.path.basename(path)
    if not base:
        base = "filter"
    # Remove extension if present
    if '.' in base:
        base, ext = base.rsplit('.', 1)
    else:
        ext = "txt"
    # Replace hyphens and underscores with dots
    base = base.replace('-', '.').replace('_', '.')
    # Collapse multiple dots
    base = re.sub(r'\.+', '.', base)
    candidate = f"{base}.optimized.{ext}"
    if candidate not in existing_names:
        existing_names.add(candidate)
        return candidate
    # Duplicate: append a number
    counter = 2
    while True:
        candidate = f"{base}.{counter}.optimized.{ext}"
        if candidate not in existing_names:
            existing_names.add(candidate)
            return candidate
        counter += 1

def main():
    url_list = "scripts/assets/url.filter.list.txt"
    out_dir = "scripts/assets/generated"
    os.makedirs(out_dir, exist_ok=True)

    if not os.path.exists(url_list):
        print(f"Error: {url_list} not found.")
        return

    with open(url_list, 'r') as f:
        urls = [line.strip() for line in f if line.strip()]

    existing_names = set(os.listdir(out_dir))
    for url in urls:
        try:
            content = download_filter_list(url)
            content = modify_title(content)
            content = remove_generic_cosmetic(content)
            out_name = get_optimized_filename(url, existing_names)
            out_path = os.path.join(out_dir, out_name)
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Saved: {out_path}")
        except Exception as e:
            print(f"Failed {url}: {e}")

if __name__ == "__main__":
    main()
