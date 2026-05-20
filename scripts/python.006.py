#!/usr/bin/env python3
import os
import re
import shutil
import tempfile
import time
import requests
import subprocess
from pathlib import Path
from packaging import version

# ========== Configuration ==========
ARCHITURES = ["arm64-v8a", "armeabi-v7a", "x86_64"]
FTP_BASE = "https://ftp.mozilla.org/pub/fenix/releases/"
IRONFOX_REPO = "https://github.com/ironfox-oss/IronFox.git"
IRONFOX_OVERLAY_DIR = "patches/gecko-overlay/ironfox"   # current location
OUTPUT_DIR = Path("scripts/assets/generated/python.006")
ICON_CACHE_DIR = Path("ironfox_assets")
APKTOOL_JAR = "apktool.jar"
APKTOOL_URL = "https://bitbucket.org/iBotPeaches/apktool/downloads/apktool_2.11.0.jar"
SIGNER_JAR = "uber-apk-signer.jar"   # generic name, will be overwritten each run

# ========== Helper Functions ==========
def run_cmd(cmd_args, cwd=None):
    """Execute a command safely using a list of arguments (no shell)."""
    if isinstance(cmd_args, str):
        print(f"[WARNING] Using string command: {cmd_args}")
        result = subprocess.run(cmd_args, shell=True, cwd=cwd, capture_output=True, text=True)
    else:
        print(f"[CMD] {' '.join(cmd_args)}")
        result = subprocess.run(cmd_args, shell=False, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        raise RuntimeError(f"Command failed: {cmd_args if isinstance(cmd_args, str) else ' '.join(cmd_args)}")
    return result

def ensure_tool(jar_path, url):
    """Download a tool from a direct URL with proper User-Agent header."""
    if not os.path.exists(jar_path):
        print(f"Downloading {jar_path}...")
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        r = requests.get(url, stream=True, headers=headers, allow_redirects=True)
        r.raise_for_status()
        with open(jar_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        os.chmod(jar_path, 0o755)
    return jar_path

def download_uber_apk_signer(jar_path):
    """
    Download the latest uber-apk-signer .jar from GitHub releases.
    This avoids hardcoded URLs and version numbers.
    """
    if os.path.exists(jar_path):
        print(f"Using existing {jar_path}")
        return jar_path

    print("Fetching latest uber-apk-signer release from GitHub...")
    api_url = "https://api.github.com/repos/patrickfav/uber-apk-signer/releases/latest"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        resp = requests.get(api_url, headers=headers)
        resp.raise_for_status()
        release = resp.json()
    except Exception as e:
        raise RuntimeError(f"Failed to fetch GitHub release info: {e}")

    # Find the asset that ends with .jar (usually the standalone JAR)
    asset_url = None
    for asset in release.get("assets", []):
        if asset["name"].endswith(".jar"):
            asset_url = asset["browser_download_url"]
            break

    if not asset_url:
        raise RuntimeError("No .jar asset found in the latest release")

    print(f"Downloading {asset_url} -> {jar_path}")
    r = requests.get(asset_url, stream=True, headers=headers)
    r.raise_for_status()
    with open(jar_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    os.chmod(jar_path, 0o755)
    return jar_path

def fetch_with_retries(url, retries=3, delay=5):
    """Fetch a URL with retries and a user-agent header."""
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
    """Fetch latest Fenix beta version from Mozilla's mobile_versions.json."""
    print("📡 Fetching latest beta version from Mozilla API...")
    url = "https://product-details.mozilla.org/1.0/mobile_versions.json"
    try:
        resp = fetch_with_retries(url)
        data = resp.json()
        latest_version = data.get("beta_version")
        if not latest_version:
            raise RuntimeError("API response missing 'beta_version' field")
        print(f"📦 Latest beta version found: {latest_version}")
        return latest_version
    except Exception as e:
        raise RuntimeError(f"Failed to get beta version from API: {e}") from e

def get_apk_urls(version_str):
    """Generate download URLs for all architectures."""
    base_url = f"{FTP_BASE}{version_str}/android/fenix-{version_str}-android-"
    urls = {}
    for arch in ARCHITURES:
        folder = f"{base_url}{arch}/"
        apk_file = f"fenix-{version_str}.multi.android-{arch}.apk"
        urls[arch] = folder + apk_file
    return urls

def download_apk(url, dest):
    """Download an APK from a given URL."""
    print(f"Downloading {url} -> {dest}")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    r = requests.get(url, stream=True, headers=headers)
    r.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    return dest

def locate_overlay(repo_root):
    """Search for the overlay directory inside the cloned IronFox repo."""
    possible_paths = [
        "fenix-overlay",
        "patches/gecko-overlay/ironfox",
        "overlay",
        "branding"
    ]
    for rel_path in possible_paths:
        full_path = repo_root / rel_path
        if full_path.exists() and full_path.is_dir():
            print(f"Found overlay at {full_path}")
            return full_path
    raise RuntimeError(f"Could not find overlay directory in {repo_root}. Tried: {possible_paths}")

def fetch_ironfox_overlay(overlay_dir):
    """Clone IronFox repository and copy the overlay directory to cache."""
    if overlay_dir.exists():
        print(f"Using existing overlay at {overlay_dir}")
        return overlay_dir
    temp_repo = Path(tempfile.mkdtemp())
    print("Cloning Iron Fox repository...")
    run_cmd(["git", "clone", "--depth", "1", IRONFOX_REPO, str(temp_repo)])
    src_overlay = locate_overlay(temp_repo)
    shutil.copytree(src_overlay, overlay_dir, symlinks=False, dirs_exist_ok=True)
    shutil.rmtree(temp_repo)
    print(f"Overlay copied to {overlay_dir}")
    return overlay_dir

def apply_overlay(decompiled_dir, overlay_dir):
    """Copy overlay files into the decompiled APK directory."""
    for item in overlay_dir.iterdir():
        dest = decompiled_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True, symlinks=False)
        else:
            shutil.copy2(item, dest)
    print(f"Applied overlay from {overlay_dir}")

def replace_strings_in_file(file_path, replacements):
    """Perform string replacements in a file."""
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

def sign_apk(apk_path, output_path):
    """Sign an APK using uber-apk-signer (always fetch latest version)."""
    download_uber_apk_signer(SIGNER_JAR)
    run_cmd(["java", "-jar", SIGNER_JAR, "-a", str(apk_path), "-o", str(output_path), "--allowResign"])
    os.remove(apk_path)
    print(f"Signed APK: {output_path}")

def rebrand_apk(apk_path, output_path, overlay_dir):
    """
    Decompile, apply branding overlay, and recompile an APK.
    Uses Apktool 2.11.0+ flags: --force after the 'd' command.
    """
    work_dir = tempfile.mkdtemp(prefix="rebrand_")
    try:
        decompiled_dir = Path(work_dir) / "decompiled"
        run_cmd(["java", "-jar", APKTOOL_JAR, "d", str(apk_path), "-o", str(decompiled_dir), "--force"])
        apply_overlay(decompiled_dir, overlay_dir)

        # Apply branding to strings.xml
        strings_file = decompiled_dir / "res/values/strings.xml"
        if strings_file.exists():
            replace_strings_in_file(strings_file, {
                "Firefox Beta": "Iron Fox",
                "firefox_beta": "iron_fox",
                "Firefox": "Iron Fox"
            })

        # Update version name in AndroidManifest.xml
        manifest = decompiled_dir / "AndroidManifest.xml"
        if manifest.exists():
            with open(manifest, "r", encoding="utf-8") as f:
                content = f.read()
            # Convert e.g. versionName="152.0b1" -> versionName="152.0.1"
            content = re.sub(r'(versionName=")(\d+\.\d+)b(\d+)"', r'\1\2.\3"', content)
            with open(manifest, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Updated version name in {manifest}")

        # Recompile the APK
        unsigned_apk = output_path.with_name(output_path.stem + "_unsigned.apk")
        run_cmd(["java", "-jar", APKTOOL_JAR, "b", str(decompiled_dir), "-o", str(unsigned_apk)])
        sign_apk(unsigned_apk, output_path)
        return output_path
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

def main():
    """Main orchestration function."""
    ensure_tool(APKTOOL_JAR, APKTOOL_URL)   # apktool still from fixed URL
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
