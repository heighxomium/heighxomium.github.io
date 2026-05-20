#!/usr/bin/env python3
import os
import re
import shutil
import tempfile
import time
import requests
import subprocess
from pathlib import Path
from bs4 import BeautifulSoup

# --- Configuration (unchanged) ---
ARCHITECTURES = ["arm64-v8a", "armeabi-v7a", "x86_64"]
FTP_BASE = "https://ftp.mozilla.org/pub/fenix/releases/"
IRONFOX_REPO = "https://github.com/ironfox-oss/IronFox.git"
IRONFOX_OVERLAY_DIR = "patches/fenix-overlay"
OUTPUT_DIR = Path("scripts/assets/generated/python.006")
ICON_CACHE_DIR = Path("ironfox_assets")
APKTOOL_JAR = "apktool.jar"
APKTOOL_URL = "https://bitbucket.org/iBotPeaches/apktool/downloads/apktool_2.11.0.jar"
SIGNER_JAR = "uber-apk-signer-1.3.0.jar"
SIGNER_URL = "https://github.com/patrickfav/uber-apk-signer/releases/download/1.3.0/uber-apk-signer-1.3.0.jar"

# --- Helper Functions (run_cmd, ensure_tool, fetch_with_retries remain unchanged) ---
def run_cmd(cmd, cwd=None):
    # ... (same as before) ...

def ensure_tool(jar_path, url):
    # ... (same as before) ...

def fetch_with_retries(url, retries=3, delay=5):
    # ... (same as before) ...

# --- Core Rebranding Logic (apply_overlay, replace_strings_in_file, rebrand_apk, sign_apk remain unchanged) ---
def apply_overlay(decompiled_dir, overlay_dir):
    # ... (same as before) ...

def replace_strings_in_file(file_path, replacements):
    # ... (same as before) ...

def rebrand_apk(apk_path, output_path, overlay_dir):
    # ... (same as before) ...

def sign_apk(apk_path, output_path):
    # ... (same as before) ...

# --- Enhanced Version Handling ---
def get_latest_beta_version():
    """Find the newest beta version by parsing the directory listing."""
    resp = fetch_with_retries(FTP_BASE)
    soup = BeautifulSoup(resp.text, "html.parser")
    versions = []

    for link in soup.find_all('a'):
        href = link.get('href')
        if href and href.endswith('/') and href != '../':
            ver = href.rstrip('/')
            # Catch both 'X.XbX' and 'X.X.X-beta.X' patterns
            if re.search(r'b\d+$', ver) or re.search(r'-beta\.\d+$', ver):
                versions.append(ver)

    if not versions:
        raise RuntimeError("No beta versions found.")

    # Convert 'X.XbX' and 'X.X.X-beta.X' to comparable numbers
    def version_key(v):
        match = re.match(r'^(\d+(?:\.\d+)+)b(\d+)$', v)
        if match:
            base, beta = match.groups()
            return tuple(map(int, base.split('.'))) + (int(beta),)
        match = re.match(r'^(\d+\.\d+\.\d+)-beta\.(\d+)$', v)
        if match:
            base, beta = match.groups()
            return tuple(map(int, base.split('.'))) + (int(beta),)
        return (0,)  # fallback for any other unexpected format

    versions.sort(key=version_key)
    return versions[-1]

def get_apk_urls(version):
    """Construct APK URLs based on the discovered version."""
    base_url = f"{FTP_BASE}{version}/android/"
    dir_name = f"fenix-{version}-android-"
    urls = {}
    for arch in ARCHITECTURES:
        full_dir = f"{dir_name}{arch}"
        apk_name = f"fenix-{version}.multi.android-{arch}.apk"
        urls[arch] = f"{base_url}{full_dir}/{apk_name}"
    return urls

def download_apk(url, dest):
    # ... (same as before) ...

def fetch_ironfox_overlay(overlay_dir):
    # ... (same as before) ...

def main():
    ensure_tool(APKTOOL_JAR, APKTOOL_URL)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    overlay_dir = ICON_CACHE_DIR / "fenix-overlay"
    fetch_ironfox_overlay(overlay_dir)

    version = get_latest_beta_version()
    print(f"Latest Firefox Beta version: {version}")
    apk_urls = get_apk_urls(version)

    downloaded = {}
    for arch, url in apk_urls.items():
        dest = OUTPUT_DIR / f"fenix-{version}-{arch}.apk"
        downloaded[arch] = download_apk(url, dest)

    final_apks = {}
    for arch, apk_path in downloaded.items():
        output_apk = OUTPUT_DIR / f"ironfox-{version}-{arch}-signed.apk"
        final_apks[arch] = rebrand_apk(apk_path, output_apk, overlay_dir)

    print("\n✅ All APKs successfully rebranded:")
    for arch, path in final_apks.items():
        print(f"  {arch}: {path}")

if __name__ == "__main__":
    main()
