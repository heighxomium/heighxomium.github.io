#!/usr/bin/env python3
"""
Merge multiple adblock filter lists, convert uBO scriptlets to ABP syntax,
deduplicate, and save as a single ABP-compatible file.
"""

import os
import sys
import re
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import argparse

# Configuration
OUTPUT_FILE = "pages/archive/backup/output.txt"

DEFAULT_SOURCES = {
    "EasyList": "https://easylist.to/easylist/easylist.txt",
    "uBlock Origin (Default)": "https://ublockorigin.github.io/uAssets/filters/filters.txt",
    "uBlock Origin (Quick fixes)": "https://ublockorigin.github.io/uAssets/filters/quick-fixes.txt",
    "uBlock Origin (Unbreak)": "https://ublockorigin.github.io/uAssets/filters/unbreak.txt",
    "Online Malicious URL Blocklist (URLhaus)": "https://malware-filter.gitlab.io/malware-filter/urlhaus-filter-online.txt",
    "RU AdList (Classic)": "https://easylist-downloads.adblockplus.org/advblock.txt",
    "Peter Lowe's Ad server list": "https://pgl.yoyo.org/adservers/serverlist.php?hostformat=hosts&showintro=1&mimetype=plaintext",
}

REQUEST_TIMEOUT = 30
RETRIES = 3
BACKOFF_FACTOR = 2

SCRIPTLET_PATTERN = re.compile(r'^([^#]*?)##\+js\(([^)]+)\)$')

# Helper functions
def convert_ubo_to_abp(filter_line):
    """Convert uBlock Origin scriptlet filter to AdBlock Plus snippet syntax."""
    match = SCRIPTLET_PATTERN.match(filter_line)
    if not match:
        return filter_line

    domain_part = match.group(1).rstrip(',')
    scriptlet_args = match.group(2)

    args = [arg.strip() for arg in scriptlet_args.split(',')]
    
    quoted_args = []
    for arg in args:
        arg = arg.strip()
        if not (arg.startswith('"') or arg.startswith("'")):
            arg = f'"{arg}"'
        quoted_args.append(arg)

    new_filter = f"{domain_part}#%#//scriptlet({', '.join(quoted_args)})"
    return new_filter

def get_session_with_retries():
    """Create a requests session with automatic retry logic."""
    session = requests.Session()
    retries = Retry(
        total=RETRIES,
        backoff_factor=BACKOFF_FACTOR,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"],
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def download_list(url):
    """Download a filter list with error handling and retries."""
    session = get_session_with_retries()
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        if resp.encoding is None:
            resp.encoding = "utf-8"
        return resp.text
    except requests.exceptions.Timeout:
        print(f"ERROR downloading {url}: Request timed out", file=sys.stderr)
        return None
    except requests.exceptions.HTTPError as e:
        print(f"ERROR downloading {url}: HTTP {e.response.status_code}", file=sys.stderr)
        return None
    except requests.exceptions.ConnectionError as e:
        print(f"ERROR downloading {url}: Connection error - {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"ERROR downloading {url}: {e}", file=sys.stderr)
        return None

def is_abp_filter_line(line):
    """Check if a line is a valid ABP filter (not a comment or metadata)."""
    line = line.strip()
    if not line:
        return False
    if line.startswith(("!", "[", "#")):
        return False
    return True

def parse_standard_abp(content):
    """Parse standard ABP format and convert uBO scriptlets to ABP syntax."""
    filters = set()
    for line in content.splitlines():
        if is_abp_filter_line(line):
            flt = line.strip()
            flt = convert_ubo_to_abp(flt)
            if flt:
                filters.add(flt)
    return filters

def parse_peter_lowe_hosts(content):
    """Parse Peter Lowe's hosts format and convert to ABP syntax."""
    filters = set()
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[0] in ("0.0.0.0", "127.0.0.1"):
            domain = parts[1].strip()
            if domain:
                filters.add(f"||{domain}^")
    return filters

def merge_all_lists(selected_sources):
    """Download and parse only the selected sources."""
    all_filters = set()
    total_sources = len(selected_sources)
    
    for idx, (name, url) in enumerate(selected_sources.items(), 1):
        print(f"[{idx}/{total_sources}] Processing: {name}")
        content = download_list(url)
        if content is None:
            print(f"  -> SKIPPED (download failed)")
            continue

        try:
            if "pgl.yoyo.org" in url:
                filters = parse_peter_lowe_hosts(content)
            else:
                filters = parse_standard_abp(content)

            print(f"  -> {len(filters)} filters added")
            all_filters.update(filters)
        except Exception as e:
            print(f"  -> ERROR parsing: {e}", file=sys.stderr)
            continue
        
        if idx < total_sources:
            time.sleep(1)

    return all_filters

def write_output(filters, output_path):
    """Write the combined filter list to output file."""
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("[Adblock Plus 2.0]\n")
            f.write("! Title: Combined Adblock Filter List\n")
            f.write("! Description: Merged & deduplicated from selected sources.\n")
            f.write(f"! Generated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n")
            f.write("! Expires: 7 days\n")
            f.write(f"! Total unique filters: {len(filters)}\n")
            f.write("\n")
            for flt in sorted(filters):
                f.write(flt + "\n")
        print(f"Output written to {output_path} ({len(filters)} unique filters)")
        return True
    except IOError as e:
        print(f"ERROR writing output file: {e}", file=sys.stderr)
        return False

# Main
def main():
    parser = argparse.ArgumentParser(description="Merge adblock filter lists")
    parser.add_argument(
        "--sources",
        nargs="+",
        help="List of source names to include"
    )
    args = parser.parse_args()

    if args.sources:
        selected = {
            name: DEFAULT_SOURCES[name]
            for name in args.sources
            if name in DEFAULT_SOURCES
        }
    else:
        selected = DEFAULT_SOURCES.copy()

    if not selected:
        print("No valid sources selected. Exiting.", file=sys.stderr)
        sys.exit(1)

    print(f"Selected sources: {', '.join(selected.keys())}")
    print(f"Total sources: {len(selected)}\n")
    
    filters = merge_all_lists(selected)
    
    if not filters:
        print("\nNo filters were collected. Exiting with error.", file=sys.stderr)
        sys.exit(1)

    print()
    success = write_output(filters, OUTPUT_FILE)
    if not success:
        sys.exit(1)
    
    print("Done.")

if __name__ == "__main__":
    main()