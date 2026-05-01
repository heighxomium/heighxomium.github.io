#!/usr/bin/env python3
"""
Compress media files (video, audio, images) using ffmpeg and Pillow.
Overwrites original files with compressed versions.
"""

import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from PIL import Image

# File extensions to process
VIDEO_EXTS = {'.mp4', '.mkv', '.avi', '.mov'}
AUDIO_EXTS = {'.mp3', '.flac', '.wav'}
IMAGE_EXTS = {'.jpg', '.jpeg', '.png'}

def log(msg, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}")

def compress_video(file_path):
    """Compress video with H.265/HEVC (CRF 26) and AAC audio."""
    temp_output = file_path.with_suffix(".temp.mp4")
    cmd = [
        "ffmpeg", "-i", str(file_path),
        "-c:v", "libx265", "-crf", "26", "-preset", "medium",
        "-c:a", "aac", "-b:a", "128k",
        "-y", str(temp_output)
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        os.replace(temp_output, file_path)
        log(f"Compressed video: {file_path}")
    except subprocess.CalledProcessError as e:
        log(f"FFmpeg error for {file_path}: {e.stderr}", "ERROR")
        if temp_output.exists():
            temp_output.unlink()
        raise

def compress_audio(file_path):
    """Re-encode audio to AAC 128kbps."""
    temp_output = file_path.with_suffix(".temp.aac")
    # Use ffmpeg to convert to AAC in a container (m4a) that preserves metadata
    cmd = [
        "ffmpeg", "-i", str(file_path),
        "-c:a", "aac", "-b:a", "128k",
        "-y", str(temp_output)
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        # Replace original with new file, keeping original extension? Better to keep .m4a?
        # For simplicity, replace original with same extension (ffmpeg can output .mp4 container for AAC)
        # We'll output to .m4a and then rename to original extension if needed.
        # Instead: output to .mp4 (AAC in MP4 container) and rename.
        final_output = file_path.with_suffix(".mp4")
        os.replace(temp_output, final_output)
        # If original extension was different, remove the old file
        if final_output != file_path:
            file_path.unlink()
        log(f"Compressed audio: {file_path} -> {final_output}")
    except subprocess.CalledProcessError as e:
        log(f"FFmpeg error for {file_path}: {e.stderr}", "ERROR")
        if temp_output.exists():
            temp_output.unlink()
        raise

def compress_image(file_path):
    """Compress JPEG (quality 75) or quantize PNG."""
    img = Image.open(file_path)
    if file_path.suffix.lower() in {'.jpg', '.jpeg'}:
        img.save(file_path, "JPEG", quality=75, optimize=True)
    elif file_path.suffix.lower() == '.png':
        # Quantize to 256 colors, use PNG8
        img = img.convert("P", palette=Image.ADAPTIVE, colors=256)
        img.save(file_path, "PNG", optimize=True)
    log(f"Compressed image: {file_path}")

def main():
    downloads_dir = Path("downloads")
    if not downloads_dir.exists():
        log("downloads/ folder not found, nothing to compress", "WARNING")
        return

    for root, dirs, files in os.walk(downloads_dir):
        # Skip the 'list' subdirectory
        if "list" in dirs:
            dirs.remove("list")
        for file in files:
            file_path = Path(root) / file
            ext = file_path.suffix.lower()
            try:
                if ext in VIDEO_EXTS:
                    compress_video(file_path)
                elif ext in AUDIO_EXTS:
                    compress_audio(file_path)
                elif ext in IMAGE_EXTS:
                    compress_image(file_path)
            except Exception as e:
                log(f"Failed to compress {file_path}: {e}", "ERROR")
                continue

if __name__ == "__main__":
    main()
