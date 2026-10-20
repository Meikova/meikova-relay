import math
import os
from PIL import Image, ImageDraw, ImageFilter

def bezier_point(p0, p1, p2, p3, u):
    u1 = 1.0 - u
    x = u1**3 * p0[0] + 3 * u1**2 * u * p1[0] + 3 * u1 * u**2 * p2[0] + u**3 * p3[0]
    y = u1**3 * p0[1] + 3 * u1**2 * u * p1[1] + 3 * u1 * u**2 * p2[1] + u**3 * p3[1]
    return (x, y)

def create_favicon_icon():
    size = 1024
    s = size / 64.0  # Scale factor = 16.0

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    # 1. Background Chamber (Pure Dark Squircle, NO BORDER)
    radius = int(18 * s)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0, 0, size, size), radius=radius, fill="#070D17")

    # Subtle radial depth gradient (seamless, no harsh border)
    grad_img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    grad_draw = ImageDraw.Draw(grad_img)
    grad_draw.ellipse((int(size*0.12), int(size*0.12), int(size*0.88), int(size*0.88)), fill=(15, 23, 42, 120))
    grad_img = grad_img.filter(ImageFilter.GaussianBlur(int(45 * s)))
    img.alpha_composite(grad_img)

    # Re-mask strictly to rounded squircle
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size, size), radius=radius, fill=255)
    img.putalpha(mask)

    # 2. Cubic Bezier curve segments from favicon.svg:
    # M32 32 C 40 20, 54 20, 54 32 C 54 44, 40 44, 32 32 C 24 20, 10 20, 10 32 C 10 44, 24 44, 32 32 Z
    segs = [
        ((32*s, 32*s), (40*s, 20*s), (54*s, 20*s), (54*s, 32*s)),
        ((54*s, 32*s), (54*s, 44*s), (40*s, 44*s), (32*s, 32*s)),
        ((32*s, 32*s), (24*s, 20*s), (10*s, 20*s), (10*s, 32*s)),
        ((10*s, 32*s), (10*s, 44*s), (24*s, 44*s), (32*s, 32*s)),
    ]

    points = []
    steps_per_seg = 600
    for p0, p1, p2, p3 in segs:
        for i in range(steps_per_seg):
            u = i / float(steps_per_seg)
            points.append(bezier_point(p0, p1, p2, p3, u))

    # Glow layer
    glow_img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_img)
    glow_r = int(5.5 * s)
    for x, y in points:
        glow_draw.ellipse((x - glow_r, y - glow_r, x + glow_r, y + glow_r), fill=(34, 197, 94, 95))
    glow_img = glow_img.filter(ImageFilter.GaussianBlur(int(2.5 * s)))
    img.alpha_composite(glow_img)

    # Main stroke: stroke-width="4.5" -> radius = 2.25 * s = 36px
    stroke_r = 2.25 * s
    draw_main = ImageDraw.Draw(img)
    for x, y in points:
        draw_main.ellipse((x - stroke_r, y - stroke_r, x + stroke_r, y + stroke_r), fill="#22C55E")

    # 3. Core Phosphor Pulse Dot: cx="32" cy="32" r="3.2" -> radius = 3.2 * s = 51.2px
    dot_cx, dot_cy = 32 * s, 32 * s
    dot_glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    dot_glow_draw = ImageDraw.Draw(dot_glow)
    dot_glow_draw.ellipse(
        (dot_cx - 60, dot_cy - 60, dot_cx + 60, dot_cy + 60),
        fill=(34, 197, 94, 180)
    )
    dot_glow = dot_glow.filter(ImageFilter.GaussianBlur(16))
    img.alpha_composite(dot_glow)

    dot_r = 3.2 * s
    ImageDraw.Draw(img).ellipse((dot_cx - dot_r, dot_cy - dot_r, dot_cx + dot_r, dot_cy + dot_r), fill="#FFFFFF")

    os.makedirs("host_agent", exist_ok=True)
    img.save("host_agent/icon.png", format="PNG")

    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save("host_agent/icon.ico", format="ICO", sizes=sizes)
    print("Border removed, clean infinity icon created!")

create_favicon_icon()
