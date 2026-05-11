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

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
OUTPUT_FILE = "pages/archive/backup/output.txt"

# Default source lists (will be overridden by workflow inputs)
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

# Regex to match uBO scriptlet filters: ##+js(...)
SCRIPTLET_PATTERN = re.compile(r'^([^#]*?)##\+js\(([^)]+)\)$')

# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------
def convert_ubo_to_abp(filter_line):
    """
    Convert uBlock Origin scriptlet filter to AdBlock Plus snippet syntax.
    Example: 'example.com##+js(set-constant.js, test, value)'
    → 'example.com#%#//scriptlet("set-constant.js", "test", "value")'
    """
    match = SCRIPTLET_PATTERN.match(filter_line)
    if not match:
        return filter_line  # not a scriptlet

    domain_part = match.group(1).rstrip(',')  # domain(s) before ##
    scriptlet_args = match.group(2)

    # Split arguments by comma, but respect quoted strings? Simpler: split by comma and strip
    # Better: use simple splitting - ABP scriptlet expects quoted arguments.
    args = [arg.strip() for arg in scriptlet_args.split(',')]
    # Quote each argument (if not already quoted)
    quoted_args = []
    for arg in args:
        arg = arg.strip()
        if not (arg.startswith('"') or arg.startswith("'")):
            arg = f'"{arg}"'
        quoted_args.append(arg)

    new_filter = f"{domain_part}#%#//scriptlet({', '.join(quoted_args)})"
    return new_filter

def get_session_with_retries():
    session = requests.Session()
    retries = Retry(
        total=RETRIES,
        backoff_factor=BACKOFF_FACTOR,
        status_forcelist=[500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def download_list(url):
    session = get_session_with_retries()
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        if resp.encoding is None:
            resp.encoding = "utf-8"
        return resp.text
    except Exception as e:
        print(f"ERROR downloading {url}: {e}", file=sys.stderr)
        return None

def is_abp_filter_line(line):
    line = line.strip()
    if not line:
        return False
    if line.startswith(("!", "[", "#", "!")):
        return False
    return True

def parse_standard_abp(content):
    filters = set()
    for line in content.splitlines():
        if is_abp_filter_line(line):
            flt = line.strip()
            # Convert uBO scriptlet to ABP snippet
            flt = convert_ubo_to_abp(flt)
            filters.add(flt)
    return filters

def parse_peter_lowe_hosts(content):
    filters = set()
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[0] in ("0.0.0.0", "127.0.0.1"):
            domain = parts[1]
            filters.add(f"||{domain}^")
    return filters

def merge_all_lists(selected_sources):
    """Download and parse only the selected sources."""
    all_filters = set()
    for name, url in selected_sources.items():
        print(f"Processing: {name}")
        content = download_list(url)
        if content is None:
            print(f"  -> SKIPPED (download error)")
            continue

        if "pgl.yoyo.org" in url:
            filters = parse_peter_lowe_hosts(content)
        else:
            filters = parse_standard_abp(content)

        print(f"  -> {len(filters)} filters added")
        all_filters.update(filters)
        time.sleep(1)

    return all_filters

def write_output(filters, output_path):
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

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", nargs="+", help="List of source names to include")
    args = parser.parse_args()

    # Determine which sources to process
    if args.sources:
        selected = {name: DEFAULT_SOURCES[name] for name in args.sources if name in DEFAULT_SOURCES}
    else:
        selected = DEFAULT_SOURCES.copy()

    if not selected:
        print("No valid sources selected. Exiting.", file=sys.stderr)
        sys.exit(1)

    print(f"Selected sources: {', '.join(selected.keys())}")
    filters = merge_all_lists(selected)
    if not filters:
        print("No filters were collected. Exiting with error.", file=sys.stderr)
        sys.exit(1)

    write_output(filters, OUTPUT_FILE)
    print("Done.")

if __name__ == "__main__":
    main()
