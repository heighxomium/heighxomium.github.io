#!/usr/bin/env python3
"""
Upload each file (recursively) to EasySend API, collect share URLs.
Writes one URL per line into downloads/list/list.txt.
"""

import os
import time
import requests
from pathlib import Path
from datetime import datetime

EASYSEND_UPLOAD_URL = "https://easysend.co/api/v1/upload"
MAX_FILE_SIZE_BYTES = 1_000_000_000  # 1 GB
DELAY_SECONDS = 1

def log(msg, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}")

def upload_file(file_path):
    """Upload a single file and return the full share URL or None on failure."""
    if file_path.stat().st_size > MAX_FILE_SIZE_BYTES:
        log(f"Skipping {file_path}: exceeds 1 GB limit", "WARNING")
        return None

    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f)}
        try:
            response = requests.post(EASYSEND_UPLOAD_URL, files=files, timeout=120)
            response.raise_for_status()
            data = response.json()
            share_url = data.get("share_url")
            if not share_url:
                log(f"No share_url in response for {file_path}: {data}", "ERROR")
                return None
            full_url = f"https://easysend.co{share_url}"
            log(f"Uploaded {file_path} -> {full_url}")
            return full_url
        except requests.exceptions.RequestException as e:
            log(f"Upload failed for {file_path}: {e}", "ERROR")
            return None

def main():
    downloads_dir = Path("downloads")
    if not downloads_dir.exists():
        log("downloads/ folder not found, nothing to upload", "WARNING")
        return

    # Ensure list directory and empty list.txt
    list_dir = downloads_dir / "list"
    list_dir.mkdir(exist_ok=True)
    list_txt = list_dir / "list.txt"
    # Clear previous content (idempotent)
    list_txt.write_text("")

    # Gather all files recursively, excluding the list/ folder
    all_files = []
    for root, dirs, files in os.walk(downloads_dir):
        # Skip the 'list' subdirectory entirely
        if "list" in dirs:
            dirs.remove("list")
        for file in files:
            file_path = Path(root) / file
            all_files.append(file_path)

    log(f"Found {len(all_files)} files to upload")

    for file_path in all_files:
        url = upload_file(file_path)
        if url:
            with open(list_txt, "a") as f:
                f.write(url + "\n")
        time.sleep(DELAY_SECONDS)

    log(f"Upload finished. Share links saved to {list_txt}")

if __name__ == "__main__":
    main()
