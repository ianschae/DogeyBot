#!/usr/bin/env python3
"""Build Doge.app icon from src/assets/dogecoin.png. Run from repo root. Requires Pillow and macOS iconutil."""
import subprocess
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Need Pillow: pip install Pillow", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS = REPO_ROOT / "src" / "assets"
APP_RESOURCES = REPO_ROOT / "Doge.app" / "Contents" / "Resources"

# Iconset sizes: (filename_suffix, pixel_size)
ICONSET_SIZES = [
    ("16x16", 16),
    ("16x16@2x", 32),
    ("32x32", 32),
    ("32x32@2x", 64),
    ("128x128", 128),
    ("128x128@2x", 256),
    ("256x256", 256),
    ("256x256@2x", 512),
    ("512x512", 512),
    ("512x512@2x", 1024),
]


def main():
    src = ASSETS / "dogecoin.png"
    if not src.exists():
        src = ASSETS / "dogey.png"
    if not src.exists():
        print("No dogecoin.png or dogey.png in src/assets/", file=sys.stderr)
        sys.exit(1)

    img = Image.open(src).convert("RGBA")
    iconset = APP_RESOURCES / "AppIcon.iconset"
    iconset.mkdir(parents=True, exist_ok=True)

    for name, size in ICONSET_SIZES:
        resized = img.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(iconset / f"icon_{name}.png")

    APP_RESOURCES.mkdir(parents=True, exist_ok=True)
    icns_path = APP_RESOURCES / "AppIcon.icns"
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(icns_path)], check=True)

    # Remove iconset so the app bundle is clean
    for f in iconset.glob("*.png"):
        f.unlink()
    iconset.rmdir()

    print("Wrote", icns_path)


if __name__ == "__main__":
    main()
