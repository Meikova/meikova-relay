# -*- coding: utf-8 -*-
"""
Unified Brand Icon Generator for Meikova Relay.
Renders official Meikova Relay 'Duplex Bridge' brand identity:
- Dark squircle #11151B (rx=22% on 100x100 canvas)
- Duplex bridge polygons in luminescent neon green #83E8AC
- 4x supersampled anti-aliased vector rendering
"""

import os
import sys
from pathlib import Path
from PIL import Image, ImageDraw


def draw_duplex_bridge(size: int = 512) -> Image.Image:
    """Renders the official Meikova Relay Duplex Bridge icon at specified size."""
    scale = size / 100.0
    ss = 4
    canvas_size = size * ss
    img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 1. Dark squircle background (#11151B, rx=22)
    rx = int(22 * scale * ss)
    d.rounded_rectangle((0, 0, canvas_size, canvas_size), radius=rx, fill="#11151B")

    # 2. Vector transform: translate(7, 7) scale(0.86)
    def t(pt):
        x, y = pt
        tx = (7.0 + 0.86 * x) * scale * ss
        ty = (7.0 + 0.86 * y) * scale * ss
        return (tx, ty)

    # Path 1: M12 29H45L57 41L45 53H30V41H40L43 38H24V62H40V74H12Z
    p1 = [
        (12, 29), (45, 29), (57, 41), (45, 53), (30, 53), (30, 41),
        (40, 41), (43, 38), (24, 38), (24, 62), (40, 62), (40, 74), (12, 74)
    ]
    # Path 2: M88 71H55L43 59L55 47H70V59H60L57 62H76V38H60V26H88Z
    p2 = [
        (88, 71), (55, 71), (43, 59), (55, 47), (70, 47), (70, 59),
        (60, 59), (57, 62), (76, 62), (76, 38), (60, 38), (60, 26), (88, 26)
    ]

    d.polygon([t(pt) for pt in p1], fill="#83E8AC")
    d.polygon([t(pt) for pt in p2], fill="#83E8AC")

    return img.resize((size, size), Image.Resampling.LANCZOS)


def render_unified_icon(size: int = 512) -> Image.Image:
    """
    Returns the unified brand icon for Meikova Relay (Duplex Bridge).
    Attempts to read from existing asset or renders procedurally.
    """
    base_dirs = [
        Path(__file__).resolve().parent,
        Path.cwd(),
    ]
    for b in base_dirs:
        for fname in ("icon.png", "tray_icon.png"):
            candidate = b / fname
            if candidate.is_file():
                try:
                    with Image.open(candidate) as im:
                        if im.size == (size, size):
                            return im.copy()
                        return im.resize((size, size), Image.Resampling.LANCZOS)
                except Exception:
                    pass

    return draw_duplex_bridge(size)


def main():
    root = Path(__file__).resolve().parent
    os.makedirs(root, exist_ok=True)

    master = draw_duplex_bridge(512)

    # 1. App Icon PNG (512x512)
    master.save(root / "icon.png", format="PNG")
    print(f"Generated {root / 'icon.png'}")

    # 2. Tray Icon PNG (32x32 Lanczos)
    tray_img = master.resize((32, 32), Image.Resampling.LANCZOS)
    tray_img.save(root / "tray_icon.png", format="PNG")
    print(f"Generated {root / 'tray_icon.png'}")

    # 3. Multi-resolution ICO
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    master.save(root / "icon.ico", format="ICO", sizes=sizes)
    print(f"Generated {root / 'icon.ico'}")


if __name__ == "__main__":
    main()
