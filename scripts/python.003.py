#!/usr/bin/env python3
"""
Archive each non‑media / non‑archive file individually using LZMA2 (.7z).
Skips already compressed media or archive files.
"""

import os
import shutil
from pathlib import Path
from datetime import datetime
import py7zr

# Extensions that should NOT be archived (already compressed or media)
SKIP_EXTS = {
    # Media (already handled by compression script)
    '.mp4', '.mkv', '.avi', '.mov',
    '.mp3', '.flac', '.wav',
    '.jpg', '.jpeg', '.png',
    # Archive formats
    '.7z', '.zip', '.xz', '.gz', '.bz2', '.tar', '.rar'
}

def log(msg, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}")

def compress_to_7z(file_path):
    """Compress a single file into a .7z archive and remove the original."""
    archive_path = file_path.with_suffix(file_path.suffix + ".7z")
    # Use py7zr with maximum LZMA2 compression
    with py7zr.SevenZipFile(archive_path, 'w', filters=[{'id': py7zr.FILTER_LZMA2}]) as archive:
        archive.write(file_path, arcname=file_path.name)
    # Remove original file if archive was created successfully
    if archive_path.exists():
        file_path.unlink()
        log(f"Archived: {file_path} -> {archive_path}")
    else:
        log(f"Failed to create archive for {file_path}", "ERROR")

def main():
    downloads_dir = Path("downloads")
    if not downloads_dir.exists():
        log("downloads/ folder not found, nothing to archive", "WARNING")
        return

    for root, dirs, files in os.walk(downloads_dir):
        # Skip the 'list' subdirectory
        if "list" in dirs:
            dirs.remove("list")
        for file in files:
            file_path = Path(root) / file
            ext = file_path.suffix.lower()
            # Skip files that are already compressed or media
            if ext in SKIP_EXTS:
                log(f"Skipping archiving for {file_path} (already compressed or media)")
                continue
            try:
                compress_to_7z(file_path)
            except Exception as e:
                log(f"Failed to archive {file_path}: {e}", "ERROR")
                continue

if __name__ == "__main__":
    main()
