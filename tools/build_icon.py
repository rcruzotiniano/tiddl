"""Regenerate the Windows icon assets from a single square PNG master.

Usage::

    python tools/build_icon.py [source.png]

Any square image (transparency optional) works as source.  Both
``assets/tiddl-icon.png`` (512 px master for docs and packaging) and
``assets/tiddl.ico`` (Windows multi-resolution icon embedded in the EXE and
shown in the window title bar) are written from it.  Pass no argument to
rebuild the ``.ico`` from the committed ``tiddl-icon.png`` master.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
PNG_MASTER = ASSETS / "tiddl-icon.png"
ICO_TARGET = ASSETS / "tiddl.ico"
MASTER_SIZE = 512

# Windows expects 16/32/48 in the shell, 256 for large thumbnails.  The extra
# in-between sizes keep the high-DPI Explorer and taskbar renderings sharp.
ICO_SIZES = (256, 128, 96, 64, 48, 40, 32, 24, 20, 16)
# Small layers need a hint of sharpening: Lanczos alone turns the thin diamond
# outlines into a grey mush below 48 px.
SHARPEN_AT_OR_BELOW = 48


def load_square(source: Path) -> Image.Image:
    image = Image.open(source).convert("RGBA")
    width, height = image.size
    if width != height:
        side = min(width, height)
        left = (width - side) // 2
        top = (height - side) // 2
        image = image.crop((left, top, left + side, top + side))
    # Trim fully transparent padding so the artwork fills the canvas; without
    # this the mark looks undersized next to other taskbar icons.
    box = image.getchannel("A").getbbox()
    if box and box != (0, 0, image.width, image.height):
        image = image.crop(box)
    return image


def render_layer(master: Image.Image, size: int) -> Image.Image:
    layer = master.resize((size, size), Image.LANCZOS)
    if size <= SHARPEN_AT_OR_BELOW:
        layer = layer.filter(ImageFilter.UnsharpMask(radius=1.0, percent=60, threshold=0))
    return layer


def main() -> int:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else PNG_MASTER
    if not source.exists():
        print(f"source icon not found: {source}", file=sys.stderr)
        return 1

    # Loaded before writing so re-running against the committed master is safe.
    master = load_square(source)
    master.resize((MASTER_SIZE, MASTER_SIZE), Image.LANCZOS).save(PNG_MASTER, format="PNG", optimize=True)

    layers = [render_layer(master, size) for size in ICO_SIZES]
    layers[0].save(
        ICO_TARGET,
        format="ICO",
        sizes=[(size, size) for size in ICO_SIZES],
        append_images=layers[1:],
    )

    with Image.open(ICO_TARGET) as check:
        written = sorted(check.info.get("sizes", []))
    print(f"wrote {PNG_MASTER.relative_to(ROOT)} ({MASTER_SIZE}x{MASTER_SIZE})")
    print(f"wrote {ICO_TARGET.relative_to(ROOT)} ({', '.join(f'{w}x{h}' for w, h in written)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
