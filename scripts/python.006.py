#!/usr/bin/env python3
import os
import re
import sys
import json
import time
import shutil
import tempfile
import subprocess
import tarfile
from itertools import chain
from pathlib import Path
from typing import Dict, List, Optional, Union, Tuple
import requests
from packaging import version as version_parser

class LogStatus:
    """Simple status logger with emoji indicators."""
    START = "▶️"
    SUCCESS = "✅"
    FAILURE = "❌"
    SKIP = "⏭️"
    WARNING = "⚠️"
    INFO = "ℹ️"
    STEP = "🔹"

    @staticmethod
    def print(icon: str, message: str) -> None:
        print(f"{icon} {message}")

    @staticmethod
    def start(message: str) -> None:
        LogStatus.print(LogStatus.START, message)

    @staticmethod
    def success(message: str) -> None:
        LogStatus.print(LogStatus.SUCCESS, message)

    @staticmethod
    def failure(message: str) -> None:
        LogStatus.print(LogStatus.FAILURE, message)

    @staticmethod
    def skip(message: str) -> None:
        LogStatus.print(LogStatus.SKIP, message)

    @staticmethod
    def warning(message: str) -> None:
        LogStatus.print(LogStatus.WARNING, message)

    @staticmethod
    def info(message: str) -> None:
        LogStatus.print(LogStatus.INFO, message)

    @staticmethod
    def step(message: str) -> None:
        LogStatus.print(LogStatus.STEP, message)

ARCHITECTURES: List[str] = ["arm64-v8a", "armeabi-v7a", "x86_64"]
MOZILLA_PRODUCT_DETAILS_API: str = "https://product-details.mozilla.org/1.0/"
FTP_BASE: str = "https://ftp.mozilla.org/pub/fenix/releases/"
IRONFOX_REPO: str = "https://github.com/ironfox-oss/IronFox.git"
IRONFOX_OVERLAY_DIR: str = "patches/gecko-overlay/ironfox"
OUTPUT_DIR: Path = Path("scripts/assets/generated/python.006")
ICON_CACHE_DIR: Path = Path("ironfox_assets")
OVERLAY_CACHE_DIR: Path = ICON_CACHE_DIR / "fenix-overlay"
APKTOOL_JAR: str = "apktool.jar"
APKTOOL_URL: str = "https://bitbucket.org/iBotPeaches/apktool/downloads/apktool_3.0.2.jar"
SIGNER_JAR: str = "uber-apk-signer.jar"
NEW_PACKAGE_NAME: str = "io.github.ironfox"
OLD_PACKAGE_NAME: str = "org.mozilla.firefox_beta"
APP_LABEL: str = "Iron Fox"
PRIMARY_COLOR: str = "#FF5722"

def run_cmd(cmd_args: List[Union[str, Path]], cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    """Execute a command safely with status logging."""
    cmd_str = ' '.join(str(arg) for arg in cmd_args)
    LogStatus.info(f"Executing: {cmd_str}")
    try:
        result = subprocess.run(
            [str(arg) for arg in cmd_args],
            shell=False,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            LogStatus.warning(f"Command returned non-zero exit code {result.returncode}")
            if result.stdout:
                print(f"STDOUT:\n{result.stdout}")
            if result.stderr:
                print(f"STDERR:\n{result.stderr}")
            raise RuntimeError(f"Command failed: {cmd_str}")
        return result
    except Exception as e:
        LogStatus.failure(f"Command execution failed: {e}")
        raise

def download_file(url: str, dest_path: Path, headers: Optional[Dict[str, str]] = None) -> bool:
    """Download a file with retries and status logging."""
    headers = headers or {'User-Agent': 'IronFox-Rebrander/1.0'}
    for attempt in range(3):
        try:
            LogStatus.info(f"Attempt {attempt+1}/3: Downloading {url}")
            response = requests.get(url, stream=True, headers=headers, timeout=30)
            response.raise_for_status()
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            with open(dest_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            dest_path.chmod(0o755)
            LogStatus.success(f"Downloaded to {dest_path}")
            return True
        except requests.exceptions.RequestException as e:
            LogStatus.warning(f"Attempt {attempt+1} failed: {e}")
            if attempt == 2:
                LogStatus.failure(f"Failed to download after 3 attempts: {url}")
                raise
            time.sleep(5)
    return False

def ensure_tool(jar_path: Path, url: str) -> Path:
    """Ensure tool exists, download if missing."""
    if jar_path.exists():
        LogStatus.skip(f"Tool {jar_path} already exists")
        return jar_path
    LogStatus.start(f"Downloading tool {jar_path.name}")
    download_file(url, jar_path, headers={'User-Agent': 'IronFox-Rebrander/1.0'})
    return jar_path

def fetch_latest_uber_apk_signer(jar_path: Path) -> Path:
    """Download latest uber-apk-signer from GitHub releases."""
    if jar_path.exists():
        LogStatus.skip(f"Signer {jar_path} already exists")
        return jar_path

    LogStatus.start("Fetching latest uber-apk-signer from GitHub")
    api_url = "https://api.github.com/repos/patrickfav/uber-apk-signer/releases/latest"
    headers = {
        'User-Agent': 'IronFox-Rebrander/1.0',
        'Accept': 'application/vnd.github.v3+json'
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
        LogStatus.info("Using GitHub token for higher rate limit")

    try:
        response = requests.get(api_url, headers=headers, timeout=30)
        response.raise_for_status()
        release = response.json()
    except Exception as e:
        LogStatus.failure(f"Failed to fetch release info: {e}")
        raise

    asset_url = None
    for asset in release.get("assets", []):
        if asset["name"].endswith(".jar"):
            asset_url = asset["browser_download_url"]
            LogStatus.info(f"Found asset: {asset['name']}")
            break

    if not asset_url:
        raise RuntimeError("No .jar asset found in the latest release")

    download_file(asset_url, jar_path, headers={'User-Agent': 'IronFox-Rebrander/1.0'})
    return jar_path

def get_latest_beta_version() -> str:
    """Fetch latest beta version from Mozilla API."""
    LogStatus.start("Fetching latest Firefox Beta version from Mozilla API")
    url = f"{MOZILLA_PRODUCT_DETAILS_API}mobile_versions.json"
    headers = {'User-Agent': 'IronFox-Rebrander/1.0'}
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        latest_version = data.get("beta_version")
        if not latest_version:
            raise RuntimeError("API response missing 'beta_version' field")
        LogStatus.success(f"Latest beta version: {latest_version}")
        return latest_version
    except Exception as e:
        LogStatus.failure(f"Failed to get version: {e}")
        raise

def get_apk_urls(version_str: str) -> Dict[str, str]:
    """Generate download URLs."""
    base_url = f"{FTP_BASE}{version_str}/android/fenix-{version_str}-android-"
    urls = {}
    for arch in ARCHITECTURES:
        urls[arch] = f"{base_url}{arch}/fenix-{version_str}.multi.android-{arch}.apk"
    LogStatus.info(f"Generated URLs for {len(urls)} architectures")
    return urls

def download_apk(url: str, dest_path: Path) -> Path:
    """Download APK with status."""
    LogStatus.start(f"Downloading APK for {dest_path.parent.name}/{dest_path.name}")
    download_file(url, dest_path, headers={'User-Agent': 'IronFox-Rebrander/1.0'})
    return dest_path

def locate_overlay(repo_root: Path) -> Path:
    """Search for overlay directory."""
    possible_paths = [
        "fenix-overlay",
        "patches/gecko-overlay/ironfox",
        "overlay",
        "branding"
    ]
    for rel_path in possible_paths:
        full_path = repo_root / rel_path
        if full_path.exists() and full_path.is_dir():
            LogStatus.success(f"Found overlay at {full_path}")
            return full_path
    raise RuntimeError(f"Could not find overlay directory in {repo_root}")

def fetch_ironfox_overlay(cache_dir: Path) -> Path:
    """Clone repo and cache overlay."""
    if cache_dir.exists():
        LogStatus.skip(f"Overlay already cached at {cache_dir}")
        return cache_dir

    LogStatus.start("Cloning IronFox repository to fetch overlay")
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_repo = Path(temp_dir)
        try:
            run_cmd(["git", "clone", "--depth", "1", IRONFOX_REPO, str(temp_repo)])
            src_overlay = locate_overlay(temp_repo)
            LogStatus.info(f"Copying overlay from {src_overlay} to {cache_dir}")
            shutil.copytree(src_overlay, cache_dir, symlinks=False, dirs_exist_ok=True)
            LogStatus.success("Overlay cached successfully")
        except Exception as e:
            LogStatus.failure(f"Failed to fetch overlay: {e}")
            raise
    return cache_dir

def compress_apk(apk_path: Path) -> Path:
    """
    Compress an APK file into a .tar.xz archive using maximum compression.
    Deletes the original APK after successful archiving.
    Returns the path to the archive.
    """
    LogStatus.start(f"Compressing {apk_path.name} with xz (max compression)")
    archive_path = apk_path.with_suffix(".tar.xz")
    try:
        with tarfile.open(archive_path, "w:xz", preset=9) as tar:
            tar.add(apk_path, arcname=apk_path.name)
        if not archive_path.exists() or archive_path.stat().st_size == 0:
            raise RuntimeError("Archive creation failed or resulted in empty file")
        apk_path.unlink()
        LogStatus.success(f"Compressed to {archive_path} (original deleted)")
        return archive_path
    except Exception as e:
        LogStatus.failure(f"Compression failed: {e}")
        raise

def apply_overlay(decompiled_dir: Path, overlay_dir: Path) -> None:
    """Copy overlay files."""
    LogStatus.start("Applying IronFox overlay")
    try:
        for item in overlay_dir.iterdir():
            dest = decompiled_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True, symlinks=False)
            else:
                shutil.copy2(item, dest)
        LogStatus.success("Overlay applied")
    except Exception as e:
        LogStatus.failure(f"Failed to apply overlay: {e}")
        raise

def update_all_strings_xml(decompiled_dir: Path) -> None:
    """Update strings in all locales."""
    LogStatus.start("Updating app strings in all locales")
    count = 0
    for strings_file in decompiled_dir.rglob("strings.xml"):
        try:
            with open(strings_file, "r", encoding="utf-8") as f:
                content = f.read()
        except (UnicodeDecodeError, IOError) as e:
            LogStatus.warning(f"Could not read {strings_file}: {e}")
            continue

        original = content
        content = re.sub(r'<string name="app_name">.*?</string>',
                         f'<string name="app_name">{APP_LABEL}</string>', content)
        content = content.replace("Firefox Beta", APP_LABEL)
        content = content.replace("Firefox", APP_LABEL)

        if content != original:
            with open(strings_file, "w", encoding="utf-8") as f:
                f.write(content)
            count += 1
    LogStatus.success(f"Updated strings in {count} files")

def update_colors_xml(decompiled_dir: Path) -> None:
    """Update primary color."""
    LogStatus.start("Updating brand colors")
    colors_file = decompiled_dir / "res/values/colors.xml"
    if not colors_file.exists():
        LogStatus.skip("colors.xml not found")
        return
    try:
        with open(colors_file, "r", encoding="utf-8") as f:
            content = f.read()
        original = content
        content = re.sub(r'<color name="primary">[^<]+</color>',
                         f'<color name="primary">{PRIMARY_COLOR}</color>', content)
        if content != original:
            with open(colors_file, "w", encoding="utf-8") as f:
                f.write(content)
            LogStatus.success("Colors updated")
        else:
            LogStatus.skip("Primary color already correct or not found")
    except Exception as e:
        LogStatus.warning(f"Could not update colors: {e}")

def replace_icons(decompiled_dir: Path, overlay_dir: Path) -> None:
    """Replace launcher icons if available."""
    LogStatus.start("Replacing app icons")
    custom_icons = overlay_dir / "icons"
    if not custom_icons.exists():
        LogStatus.skip("No custom icons found in overlay")
        return
    replaced = 0
    for mipmap_dir in decompiled_dir.glob("res/mipmap-*"):
        for old_icon in mipmap_dir.glob("ic_launcher*"):
            old_icon.unlink()
        density = mipmap_dir.name.replace("mipmap-", "")
        custom_density_dir = custom_icons / density
        if custom_density_dir.exists():
            for icon_file in custom_density_dir.glob("*.png"):
                shutil.copy2(icon_file, mipmap_dir / icon_file.name)
                replaced += 1
    if replaced:
        LogStatus.success(f"Replaced {replaced} icon files")
    else:
        LogStatus.warning("No matching icon densities found")

def update_apktool_yml(decompiled_dir: Path, version_code_increment: int = 1) -> None:
    """Update apktool.yml version fields."""
    LogStatus.start("Updating apktool.yml")
    yml_file = decompiled_dir / "apktool.yml"
    if not yml_file.exists():
        LogStatus.skip("apktool.yml not found")
        return
    try:
        with open(yml_file, "r", encoding="utf-8") as f:
            content = f.read()
        original = content
        content = re.sub(r'(versionName: ")(\d+\.\d+)b(\d+)"', r'\1\2.\3"', content)
        content = re.sub(r'(versionCode: )(\d+)',
                         lambda m: f'versionCode: {int(m.group(2)) + version_code_increment}',
                         content)
        if "renameManifestPackage:" not in content:
            content += f"\nrenameManifestPackage: {NEW_PACKAGE_NAME}\n"
        if content != original:
            with open(yml_file, "w", encoding="utf-8") as f:
                f.write(content)
            LogStatus.success("apktool.yml updated")
        else:
            LogStatus.skip("No changes needed")
    except Exception as e:
        LogStatus.failure(f"Failed to update apktool.yml: {e}")
        raise

def rename_package_in_smali(decompiled_dir: Path) -> None:
    """Replace package name in all smali files."""
    LogStatus.start("Renaming package in smali files")
    old_slashes = OLD_PACKAGE_NAME.replace(".", "/")
    new_slashes = NEW_PACKAGE_NAME.replace(".", "/")
    count = 0
    for smali_file in decompiled_dir.rglob("*.smali"):
        try:
            with open(smali_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception as e:
            LogStatus.warning(f"Could not read {smali_file}: {e}")
            continue
        if old_slashes in content:
            new_content = content.replace(old_slashes, new_slashes)
            with open(smali_file, "w", encoding="utf-8") as f:
                f.write(new_content)
            count += 1
    LogStatus.success(f"Updated package name in {count} smali files")

def update_manifest(decompiled_dir: Path) -> None:
    """Update AndroidManifest.xml."""
    LogStatus.start("Updating AndroidManifest.xml")
    manifest = decompiled_dir / "AndroidManifest.xml"
    if not manifest.exists():
        LogStatus.skip("AndroidManifest.xml not found")
        return
    try:
        with open(manifest, "r", encoding="utf-8") as f:
            content = f.read()
        original = content
        content = re.sub(f'package="{OLD_PACKAGE_NAME}"', f'package="{NEW_PACKAGE_NAME}"', content)
        content = re.sub(r'(versionName=")(\d+\.\d+)b(\d+)"', r'\1\2.\3"', content)
        content = re.sub(r'<application[^>]*', f'<application android:label="{APP_LABEL}"', content)
        if content != original:
            with open(manifest, "w", encoding="utf-8") as f:
                f.write(content)
            LogStatus.success("AndroidManifest.xml updated")
        else:
            LogStatus.skip("No changes needed")
    except Exception as e:
        LogStatus.failure(f"Failed to update manifest: {e}")
        raise

def sign_apk(apk_path: Path, output_path: Path) -> None:
    """Sign APK using uber-apk-signer."""
    LogStatus.start(f"Signing {apk_path.name}")
    signer_jar = fetch_latest_uber_apk_signer(Path(SIGNER_JAR))
    try:
        run_cmd([
            "java", "-jar", str(signer_jar),
            "-a", str(apk_path),
            "-o", str(output_path),
            "--allowResign"
        ])
        apk_path.unlink()
        LogStatus.success(f"Signed APK saved to {output_path}")
    except Exception as e:
        LogStatus.failure(f"Signing failed: {e}")
        raise

def rebrand_apk(apk_path: Path, output_path: Path, overlay_dir: Path) -> Path:
    """Main rebranding pipeline for one APK. Returns path to compressed archive."""
    LogStatus.step(f"Rebranding {apk_path.name}")
    with tempfile.TemporaryDirectory(prefix="rebrand_") as work_dir:
        decompiled_dir = Path(work_dir) / "decompiled"

        # Decompile
        LogStatus.start("Decompiling APK")
        run_cmd([
            "java", "-jar", APKTOOL_JAR,
            "d", str(apk_path),
            "--output", str(decompiled_dir),
            "--force"
        ])
        LogStatus.success("Decompiled successfully")
        apply_overlay(decompiled_dir, overlay_dir)
        update_all_strings_xml(decompiled_dir)
        replace_icons(decompiled_dir, overlay_dir)
        update_colors_xml(decompiled_dir)
        update_manifest(decompiled_dir)
        update_apktool_yml(decompiled_dir)
        rename_package_in_smali(decompiled_dir)
        LogStatus.start("Rebuilding APK")
        unsigned_apk = output_path.with_name(output_path.stem + "_unsigned.apk")
        run_cmd([
            "java", "-jar", APKTOOL_JAR,
            "b", str(decompiled_dir),
            "--output", str(unsigned_apk)
        ])
        LogStatus.success("APK rebuilt")
        sign_apk(unsigned_apk, output_path)
    archive_path = compress_apk(output_path)
    LogStatus.success(f"Rebranding complete for {apk_path.name} -> {archive_path}")
    return archive_path

def main() -> None:
    LogStatus.step("=== Iron Fox APK Rebranding Pipeline ===")
    ensure_tool(Path(APKTOOL_JAR), APKTOOL_URL)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for old_file in chain(OUTPUT_DIR.glob("*.apk"), OUTPUT_DIR.glob("*.tar.xz")):
        old_file.unlink()
        LogStatus.info(f"Cleaned old file: {old_file}")
    LogStatus.success(f"Output directory ready (cleaned): {OUTPUT_DIR}")
    overlay_dir = fetch_ironfox_overlay(OVERLAY_CACHE_DIR)
    version_str = get_latest_beta_version()
    apk_urls = get_apk_urls(version_str)
    downloaded = {}
    for arch, url in apk_urls.items():
        dest = OUTPUT_DIR / f"fenix-{version_str}-{arch}.apk"
        downloaded[arch] = download_apk(url, dest)
    final_archives = {}
    for arch, apk_path in downloaded.items():
        output_apk = OUTPUT_DIR / f"ironfox-{version_str}-{arch}-signed.apk"
        final_archives[arch] = rebrand_apk(apk_path, output_apk, overlay_dir)
        apk_path.unlink()
        LogStatus.success(f"Deleted original APK: {apk_path}")
    missing = [str(OUTPUT_DIR / f"ironfox-{version_str}-{arch}-signed.tar.xz") for arch in ARCHITECTURES
               if not (OUTPUT_DIR / f"ironfox-{version_str}-{arch}-signed.tar.xz").exists()]
    if missing:
        raise RuntimeError(f"Missing compressed archives: {missing}")
    LogStatus.step("\n=== Pipeline Summary ===")
    LogStatus.success(f"Successfully rebranded and compressed {len(final_archives)} APKs")
    for arch, archive_path in final_archives.items():
        size_mb = archive_path.stat().st_size / (1024 * 1024)
        print(f"  {arch}: {archive_path} ({size_mb:.2f} MB)")
if __name__ == "__main__":
    main()
