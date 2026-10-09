"""Genera iconos PWA y pantallas de splash de iOS a partir de frontend/assets-src/logo.png.

Uso:  python scripts/gen_icons.py   (requiere Pillow)
"""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "assets-src" / "logo.png"
PUBLIC = ROOT / "frontend" / "public"

BG = (11, 26, 16)  # verde casi negro (fondo del splash)
GREEN = (49, 169, 67)  # verde del escudo

# (ancho, alto, device-width, device-height, pixel-ratio) de iPhones en vertical
IOS_SPLASH = [
    (1320, 2868, 440, 956, 3),
    (1206, 2622, 402, 874, 3),
    (1290, 2796, 430, 932, 3),
    (1179, 2556, 393, 852, 3),
    (1284, 2778, 428, 926, 3),
    (1170, 2532, 390, 844, 3),
    (1125, 2436, 375, 812, 3),
    (1242, 2688, 414, 896, 3),
    (828, 1792, 414, 896, 2),
    (1242, 2208, 414, 736, 3),
    (750, 1334, 375, 667, 2),
    (640, 1136, 320, 568, 2),
]


def round_logo(size: int) -> Image.Image:
    """El logo es un círculo sobre fondo blanco: lo recortamos con transparencia."""
    logo = Image.open(SRC).convert("RGBA").resize((size * 4, size * 4), Image.LANCZOS)
    mask = Image.new("L", logo.size, 0)
    inset = int(size * 4 * 0.004)
    ImageDraw.Draw(mask).ellipse((inset, inset, size * 4 - inset, size * 4 - inset), fill=255)
    logo.putalpha(mask)
    return logo.resize((size, size), Image.LANCZOS)


def icon(size: int, scale: float, bg) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), bg)
    inner = int(size * scale)
    logo = round_logo(inner)
    off = (size - inner) // 2
    canvas.alpha_composite(logo, (off, off))
    return canvas


def main() -> None:
    (PUBLIC / "icons").mkdir(parents=True, exist_ok=True)
    (PUBLIC / "splash").mkdir(parents=True, exist_ok=True)

    round_logo(512).save(PUBLIC / "logo.png", optimize=True)
    round_logo(256).save(PUBLIC / "logo-256.png", optimize=True)
    round_logo(256).save(PUBLIC / "logo-256.webp", quality=88, method=6)
    for size in (192, 512):
        icon(size, 0.96, (0, 0, 0, 0)).save(PUBLIC / "icons" / f"icon-{size}.png", optimize=True)
    # maskable: zona segura del 80 % → logo al 76 % sobre fondo sólido
    icon(512, 0.76, BG + (255,)).save(PUBLIC / "icons" / "maskable-512.png", optimize=True)
    icon(180, 0.84, BG + (255,)).convert("RGB").save(PUBLIC / "icons" / "apple-touch-icon.png", optimize=True)
    icon(64, 1.0, (0, 0, 0, 0)).save(PUBLIC / "favicon.png", optimize=True)

    links = []
    for w, h, dw, dh, ratio in IOS_SPLASH:
        img = Image.new("RGB", (w, h), BG)
        logo_size = int(w * 0.42)
        logo = round_logo(logo_size)
        img.paste(logo, ((w - logo_size) // 2, int(h * 0.5 - logo_size * 0.6)), logo)
        name = f"splash-{w}x{h}.png"
        img.save(PUBLIC / "splash" / name, optimize=True)
        links.append(
            f'<link rel="apple-touch-startup-image" href="/splash/{name}" media="(device-width: {dw}px) '
            f'and (device-height: {dh}px) and (-webkit-device-pixel-ratio: {ratio}) and (orientation: portrait)">'
        )
    print("\n".join(links))


if __name__ == "__main__":
    main()
