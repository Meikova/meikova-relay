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
    """Generates precision points along MashLoop / EveryThingDownloader cubic bezier infinity loop."""
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

def create_tray_icon():
    """Creates pixel-perfect, transparent-background tray icon matching EveryThingDownloader & MashLoop."""
    size = 256
    s = size / 32.0  # scale = 8.0
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    points = generate_curve_points(s)

    # 1. Dark emerald contour (ensures razor-sharp contrast on light taskbars)
    for i in range(len(points)):
        p1 = points[i]
        p2 = points[(i + 1) % len(points)]
        d.line([p1, p2], fill=(4, 120, 87, 190), width=int(3.6 * s))

    # 2. Main vibrant emerald neon stroke
    for i in range(len(points)):
        p1 = points[i]
        p2 = points[(i + 1) % len(points)]
        d.line([p1, p2], fill=(34, 197, 94, 255), width=int(2.8 * s))

    # 3. Bright core highlight line
    for i in range(len(points)):
        p1 = points[i]
        p2 = points[(i + 1) % len(points)]
        d.line([p1, p2], fill=(220, 252, 231, 255), width=int(0.9 * s))

    # 4. Signature orbiting pulse beacon dot at cx=23.2, cy=12.4
    cx, cy = 23.2 * s, 12.4 * s
    r = 2.1 * s
    d.ellipse([cx - r * 1.35, cy - r * 1.35, cx + r * 1.35, cy + r * 1.35], fill=(4, 120, 87, 210))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, 255))

    res32 = img.resize((32, 32), Image.Resampling.LANCZOS)
    return res32

def create_app_icon():
    """Creates high-resolution squircle app icon for desktop window and installer."""
    size = 512
    s = size / 32.0  # scale = 16.0
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Rounded squircle background
    radius = int(8 * s)
    draw.rounded_rectangle((0, 0, size, size), radius=radius, fill="#070D17")

    # Subtle radial inner ambient chamber glow
    glow_img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(glow_img).ellipse(
        (int(size * 0.1), int(size * 0.1), int(size * 0.9), int(size * 0.9)),
        fill=(16, 27, 46, 140)
    )
    glow_img = glow_img.filter(ImageFilter.GaussianBlur(int(40)))
    img.alpha_composite(glow_img)

    # Re-clip to squircle mask
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size, size), radius=radius, fill=255)
    img.putalpha(mask)

    d = ImageDraw.Draw(img)
    points = generate_curve_points(s)

    # Outer neon green aura
    aura_img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ad = ImageDraw.Draw(aura_img)
    for i in range(len(points)):
        p1 = points[i]
        p2 = points[(i + 1) % len(points)]
        ad.line([p1, p2], fill=(34, 197, 94, 110), width=int(5.2 * s))
    aura_img = aura_img.filter(ImageFilter.GaussianBlur(int(6 * (s / 8.0))))
    img.alpha_composite(aura_img)

    # Main stroke
    for i in range(len(points)):
        p1 = points[i]
        p2 = points[(i + 1) % len(points)]
        d.line([p1, p2], fill=(34, 197, 94, 255), width=int(2.8 * s))

    # Inner core highlight
    for i in range(len(points)):
        p1 = points[i]
        p2 = points[(i + 1) % len(points)]
        d.line([p1, p2], fill=(220, 252, 231, 255), width=int(0.8 * s))

    # Beacon dot at cx=23.2, cy=12.4
    cx, cy = 23.2 * s, 12.4 * s
    r = 2.1 * s
    # Beacon aura
    b_aura = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(b_aura).ellipse(
        (cx - r * 2.5, cy - r * 2.5, cx + r * 2.5, cy + r * 2.5),
        fill=(34, 197, 94, 160)
    )
    b_aura = b_aura.filter(ImageFilter.GaussianBlur(8))
    img.alpha_composite(b_aura)

    # Core white dot
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 255, 255, 255))
    return img

def main():
    root = Path(__file__).resolve().parent
    out_dir = root
    os.makedirs(out_dir, exist_ok=True)

    # 1. Tray Icon (32x32 transparent)
    tray_img = create_tray_icon()
    tray_img.save(out_dir / "tray_icon.png", format="PNG")
    print(f"Generated {out_dir / 'tray_icon.png'}")

    # 2. App Icon (512x512)
    app_img = create_app_icon()
    app_img.save(out_dir / "icon.png", format="PNG")
    print(f"Generated {out_dir / 'icon.png'}")

    # 3. Multi-resolution ICO
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    app_img.save(out_dir / "icon.ico", format="ICO", sizes=sizes)
    print(f"Generated {out_dir / 'icon.ico'}")

if __name__ == "__main__":
    main()
