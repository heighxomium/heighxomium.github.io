#!/usr/bin/env python3
"""
Upload each file (recursively) to EasySend API, collect share URLs.
Writes one URL per line into scripts/generated/easy.send.list.txt.
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
    if not file_path.exists():
        log(f"File not found: {file_path}", "ERROR")
        return None

    file_size = file_path.stat().st_size
    if file_size > MAX_FILE_SIZE_BYTES:
        log(f"Skipping {file_path}: exceeds 1 GB limit ({file_size} bytes)", "WARNING")
        return None

    try:
        with open(file_path, "rb") as f:
            # API requires field name 'files[]' (not 'file')
            files = {"files[]": (file_path.name, f)}
            log(f"Uploading {file_path}...")
            response = requests.post(
                EASYSEND_UPLOAD_URL,
                files=files,
                timeout=120
            )

            # Log response details for debugging
            if response.status_code != 201:  # 201 Created is expected success code
                log(f"Response status: {response.status_code}", "WARNING")
                log(f"Response text: {response.text[:500]}", "WARNING")

            response.raise_for_status()
            data = response.json()

            if not data.get("success", False):
                error_msg = data.get("error", "Unknown error")
                log(f"API returned success=false: {error_msg}", "ERROR")
                return None

            share_url = data.get("share_url")
            if share_url:
                full_url = f"https://easysend.co{share_url}"
                log(f"Uploaded {file_path} -> {full_url}")
                return full_url
            else:
                log(f"No share_url in response: {data}", "ERROR")
                return None

    except requests.exceptions.RequestException as e:
        log(f"Upload failed for {file_path}: {e}", "ERROR")
        return None

def main():
    downloads_dir = Path("downloads")
    if not downloads_dir.exists():
        log("downloads/ folder not found, nothing to upload", "WARNING")
        return

    # Output file at new location
    output_path = Path("scripts/generated/easy.send.list.txt")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Clear previous content
    output_path.write_text("")

    # Gather all files recursively, excluding the old list/ folder (if present)
    all_files = []
    for root, dirs, files in os.walk(downloads_dir):
        if "list" in dirs:
            dirs.remove("list")
        for file in files:
            file_path = Path(root) / file
            all_files.append(file_path)

    log(f"Found {len(all_files)} files to upload")

    for file_path in all_files:
        url = upload_file(file_path)
        if url:
            with open(output_path, "a") as f:
                f.write(url + "\n")
        time.sleep(DELAY_SECONDS)

    log(f"Upload finished. Share links saved to {output_path}")

if __name__ == "__main__":
    main()
