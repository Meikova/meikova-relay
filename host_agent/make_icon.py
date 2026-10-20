import math
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

def bezier_point(p0, p1, p2, p3, u):
    u1 = 1.0 - u
    return (
        u1**3 * p0[0] + 3 * u1**2 * u * p1[0] + 3 * u1 * u**2 * p2[0] + u**3 * p3[0],
        u1**3 * p0[1] + 3 * u1**2 * u * p1[1] + 3 * u1 * u**2 * p2[1] + u**3 * p3[1]
    )

def generate_curve_points(s, steps=400):
    """Cubic Bezier curve matching MashLoop & EveryThingDownloader."""
    segs = [
        ((16*s, 16*s), (19.5*s, 10.5*s), (27*s, 10.5*s), (27*s, 16*s)),
        ((27*s, 16*s), (27*s, 21.5*s), (19.5*s, 21.5*s), (16*s, 16*s)),
        ((16*s, 16*s), (12.5*s, 10.5*s), (5*s, 10.5*s), (5*s, 16*s)),
        ((5*s, 16*s), (5*s, 21.5*s), (12.5*s, 21.5*s), (16*s, 16*s)),
    ]
    points = []
    for p0, p1, p2, p3 in segs:
        for i in range(steps):
            points.append(bezier_point(p0, p1, p2, p3, i / float(steps)))
    return points

def render_unified_icon(size=512):
    """
    Renders unified brand icon:
    1. Nền đen sâu (Dark squircle #070D17, rx=7 on 32 scale)
    2. Vô cực màu xanh (#22C55E, stroke 2.8 on 32 scale)
    3. Chấm trắng (#FFFFFF, cx=23.2, cy=12.4, r=2.1 on 32 scale)
    """
    s = size / 32.0
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 1. Nền đen squircle
    rx = int(7 * s)
    d.rounded_rectangle((0, 0, size, size), radius=rx, fill="#070D17")

    # 2. Vô cực xanh
    points = generate_curve_points(s)
    w = int(2.8 * s)
    for i in range(len(points)):
        p1 = points[i]
        p2 = points[(i + 1) % len(points)]
        d.line([p1, p2], fill="#22C55E", width=w)

    r_cap = w / 2.0
    for x, y in points[::10]:
        d.ellipse([x - r_cap, y - r_cap, x + r_cap, y + r_cap], fill="#22C55E")

    # 3. Chấm trắng tại (23.2, 12.4)
    cx, cy = 23.2 * s, 12.4 * s
    cr = 2.1 * s
    d.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill="#FFFFFF")

    return img

def main():
    root = Path(__file__).resolve().parent
    out_dir = root
    os.makedirs(out_dir, exist_ok=True)

    master = render_unified_icon(512)

    # 1. App Icon PNG
    master.save(out_dir / "icon.png", format="PNG")
    print(f"Generated {out_dir / 'icon.png'}")

    # 2. Tray Icon PNG (32x32 Lanczos)
    tray_img = master.resize((32, 32), Image.Resampling.LANCZOS)
    tray_img.save(out_dir / "tray_icon.png", format="PNG")
    print(f"Generated {out_dir / 'tray_icon.png'}")

    # 3. Multi-resolution ICO for Windows PE and titlebar
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    master.save(out_dir / "icon.ico", format="ICO", sizes=sizes)
    print(f"Generated {out_dir / 'icon.ico'}")

if __name__ == "__main__":
    main()
