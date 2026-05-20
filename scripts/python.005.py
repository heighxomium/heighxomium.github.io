#!/usr/bin/env python3
import os
import re
import requests
from urllib.parse import urlparse

def download_filter_list(url):
    print(f"Downloading: {url}")
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text

def extract_filter_name(content):
    lines = content.splitlines()
    for line in lines:
        if line.startswith("! Name:"):
            parts = line.split("! Name:", 1)
            if len(parts) == 2:
                return parts[1].strip()
    for line in lines:
        if line.startswith("! Title:"):
            parts = line.split("! Title:", 1)
            if len(parts) == 2:
                return parts[1].strip()
    return None

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

def sanitize_filename(name):
    name = name.lower()
    name = re.sub(r'[^a-z0-9.]', '.', name)
    name = re.sub(r'\.+', '.', name)
    name = name.strip('.')
    return name if name else "filter"

def strip_optimized_suffix(name):
    if name.endswith('.optimized'):
        return name[:-9]
    return name

def get_output_filename(url, content, existing_names):
    filter_name = extract_filter_name(content)
    if filter_name:
        base = sanitize_filename(filter_name)
    else:
        parsed = urlparse(url)
        path = parsed.path
        base = os.path.basename(path)
        if not base:
            base = "filter"
        if '.' in base:
            base = base.rsplit('.', 1)[0]
        base = sanitize_filename(base)
    base = strip_optimized_suffix(base)
    candidate = f"{base}.optimized.txt"
    if candidate not in existing_names:
        existing_names.add(candidate)
        return candidate
    counter = 2
    while True:
        candidate = f"{base}.{counter}.optimized.txt"
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
            filter_name = extract_filter_name(content)
            content = modify_title(content)
            content = remove_generic_cosmetic(content)
            out_name = get_output_filename(url, content, existing_names)
            out_path = os.path.join(out_dir, out_name)
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Saved: {out_path} (from name: {filter_name or 'URL-derived'})")
        except Exception as e:
            print(f"Failed {url}: {e}")

if __name__ == "__main__":
    main()
