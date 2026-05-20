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
from packaging import version

# ========== Configuration ==========
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

# ========== Helper Functions ==========
def run_cmd(cmd, cwd=None):
    print(f"[CMD] {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        raise RuntimeError(f"Command failed: {cmd}")
    return result

def ensure_tool(jar_path, url):
    if not os.path.exists(jar_path):
        print(f"Downloading {jar_path}...")
        r = requests.get(url, stream=True)
        r.raise_for_status()
        with open(jar_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        os.chmod(jar_path, 0o755)
    return jar_path

def fetch_with_retries(url, retries=3, delay=5):
    for attempt in range(retries):
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            resp = requests.get(url, timeout=30, headers=headers)
            resp.raise_for_status()
            return resp
        except requests.exceptions.RequestException as e:
            print(f"Attempt {attempt+1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                raise

def get_latest_beta_version():
    """
    Fetches the latest Fenix beta version from Mozilla's official
    Product Details API (fenix_beta_version.json).
    """
    print("📡 Fetching latest beta version from Mozilla API...")
    url = "https://product-details.mozilla.org/1.0/fenix_beta_version.json"
    try:
        resp = fetch_with_retries(url)
        data = resp.json()
        latest_version = data.get("version")
        if not latest_version:
            raise RuntimeError("API response missing 'version' field")
        print(f"📦 Latest beta version found: {latest_version}")
        return latest_version
    except Exception as e:
        raise RuntimeError(f"Failed to get beta version from API: {e}") from e

def get_apk_urls(version):
    """Generates correct download URLs for all architectures."""
    base_url = f"{FTP_BASE}{version}/android/fenix-{version}-android-"
    urls = {}
    for arch in ARCHITECTURES:
        folder = f"{base_url}{arch}/"
        apk_file = f"fenix-{version}.multi.android-{arch}.apk"
        urls[arch] = folder + apk_file
    return urls

def download_apk(url, dest):
    print(f"Downloading {url} -> {dest}")
    r = requests.get(url, stream=True)
    r.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    return dest

def fetch_ironfox_overlay(overlay_dir):
    if overlay_dir.exists():
        print(f"Using existing overlay at {overlay_dir}")
        return overlay_dir
    temp_repo = Path(tempfile.mkdtemp())
    print("Cloning Iron Fox repository...")
    run_cmd(f"git clone --depth 1 {IRONFOX_REPO} {temp_repo}")
    src_overlay = temp_repo / IRONFOX_OVERLAY_DIR
    if not src_overlay.exists():
        raise RuntimeError(f"Overlay directory not found: {src_overlay}")
    shutil.copytree(src_overlay, overlay_dir, symlinks=False, dirs_exist_ok=True)
    shutil.rmtree(temp_repo)
    print(f"Overlay copied to {overlay_dir}")
    return overlay_dir

def apply_overlay(decompiled_dir, overlay_dir):
    for item in overlay_dir.iterdir():
        dest = decompiled_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True, symlinks=False)
        else:
            shutil.copy2(item, dest)
    print(f"Applied overlay from {overlay_dir}")

def replace_strings_in_file(file_path, replacements):
    if not file_path.exists():
        return
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    modified = False
    for old, new in replacements.items():
        if old in content:
            content = content.replace(old, new)
            modified = True
    if modified:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Updated strings in {file_path}")

def rebrand_apk(apk_path, output_path, overlay_dir):
    work_dir = tempfile.mkdtemp(prefix="rebrand_")
    try:
        run_cmd(f"java -jar {APKTOOL_JAR} d {apk_path} -o {work_dir}/decompiled -f")
        decompiled = Path(work_dir) / "decompiled"
        apply_overlay(decompiled, overlay_dir)
        strings_file = decompiled / "res/values/strings.xml"
        if strings_file.exists():
            replace_strings_in_file(strings_file, {
                "Firefox Beta": "Iron Fox",
                "firefox_beta": "iron_fox",
                "Firefox": "Iron Fox"
            })
        manifest = decompiled / "AndroidManifest.xml"
        if manifest.exists():
            with open(manifest, "r", encoding="utf-8") as f:
                content = f.read()
            content = re.sub(r'(versionName=")(\d+\.\d+)b(\d+)"', r'\1\2.\3"', content)
            with open(manifest, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Updated version name in {manifest}")
        unsigned_apk = output_path.with_name(output_path.stem + "_unsigned.apk")
        run_cmd(f"java -jar {APKTOOL_JAR} b {decompiled} -o {unsigned_apk}")
        sign_apk(unsigned_apk, output_path)
        return output_path
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

def sign_apk(apk_path, output_path):
    ensure_tool(SIGNER_JAR, SIGNER_URL)
    run_cmd(f"java -jar {SIGNER_JAR} -a {apk_path} -o {output_path} --allowResign")
    os.remove(apk_path)
    print(f"Signed APK: {output_path}")

def main():
    ensure_tool(APKTOOL_JAR, APKTOOL_URL)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    overlay_dir = ICON_CACHE_DIR / "fenix-overlay"
    fetch_ironfox_overlay(overlay_dir)
    version_str = get_latest_beta_version()
    print(f"Latest Firefox Beta version: {version_str}")
    apk_urls = get_apk_urls(version_str)
    downloaded = {}
    for arch, url in apk_urls.items():
        dest = OUTPUT_DIR / f"fenix-{version_str}-{arch}.apk"
        downloaded[arch] = download_apk(url, dest)
    final_apks = {}
    for arch, apk_path in downloaded.items():
        output_apk = OUTPUT_DIR / f"ironfox-{version_str}-{arch}-signed.apk"
        final_apks[arch] = rebrand_apk(apk_path, output_apk, overlay_dir)
    print("\n✅ All APKs successfully rebranded:")
    for arch, path in final_apks.items():
        print(f"  {arch}: {path}")

if __name__ == "__main__":
    main()
