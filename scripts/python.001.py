#!/usr/bin/env python3
"""
Download a file from a given URL to the /downloads directory.
Handles redirects, extracts filename from Content-Disposition or URL.
Adds random User-Agent and delays to avoid rate limiting.
"""

import os
import sys
import time
import random
import requests
from pathlib import Path
from urllib.parse import urlparse, unquote
from datetime import datetime

# List of common User-Agents (browsers)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
]

def log(msg, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}")

def get_random_user_agent():
    return random.choice(USER_AGENTS)

def extract_filename_from_response(response, url):
    """
    Try to get filename from Content-Disposition header.
    Fallback to last part of the URL path, then 'downloaded_file'.
    """
    # Try Content-Disposition
    if "Content-Disposition" in response.headers:
        cd = response.headers["Content-Disposition"]
        if "filename=" in cd:
            # Handle quoted and unquoted filenames
            filename = cd.split("filename=")[-1].strip("'\"")
            return unquote(filename)

    # Fallback: last segment of URL path
    parsed = urlparse(url)
    path = unquote(parsed.path)
    if path and "/" in path:
        filename = path.split("/")[-1]
        if filename:
            return filename

    # Ultimate fallback
    return "downloaded_file"

def download_file(url, dest_dir="downloads"):
    """Download a file with random user-agent and delay."""
    # Random delay before download (1–5 seconds) to be polite
    delay = random.uniform(1, 5)
    log(f"Waiting {delay:.2f} seconds before download...")
    time.sleep(delay)

    headers = {"User-Agent": get_random_user_agent()}
    log(f"Downloading from {url} with UA: {headers['User-Agent']}")

    try:
        # Stream the download to handle large files
        with requests.get(url, headers=headers, stream=True, timeout=120) as resp:
            resp.raise_for_status()

            # Determine filename
            filename = extract_filename_from_response(resp, url)
            dest_path = Path(dest_dir) / filename

            # Write file in chunks
            total_size = int(resp.headers.get("content-length", 0))
            written = 0
            with open(dest_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        written += len(chunk)
                        if total_size:
                            percent = (written / total_size) * 100
                            print(f"\rProgress: {percent:.1f}%", end="", flush=True)
            print()  # newline after progress
            log(f"Downloaded {filename} ({written} bytes) to {dest_path}")
            return dest_path

    except requests.exceptions.RequestException as e:
        log(f"Download failed: {e}", "ERROR")
        sys.exit(1)

def main():
    if len(sys.argv) < 2:
        log("No URL provided. Usage: python download_from_url.py <URL>", "ERROR")
        sys.exit(1)

    url = sys.argv[1]
    # Ensure downloads directory exists
    Path("downloads").mkdir(exist_ok=True)

    download_file(url)

if __name__ == "__main__":
    main()
