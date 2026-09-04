# -*- coding: utf-8 -*-
"""Erzeugt App-Icon und Splash-Screen für die Android-App aus den Illustrationen.

  .venv/bin/python build/make_android_assets.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "img" / "raw"
RES = ROOT / "android" / "app" / "src" / "main" / "res"
BG = (11, 16, 32)          # --bg der App

# Launcher-Icons: mipmap-Ordner mit Kantenlänge
ICON_SIZES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
# Adaptive Icons brauchen einen größeren Vordergrund (Sicherheitsrand)
FG_SIZES = {"mdpi": 108, "hdpi": 162, "xhdpi": 216, "xxhdpi": 324, "xxxhdpi": 432}
SPLASH_SIZES = {"drawable": (480, 800), "drawable-land-hdpi": (800, 480),
                "drawable-port-hdpi": (480, 800), "drawable-land-xhdpi": (1280, 720),
                "drawable-port-xhdpi": (720, 1280), "drawable-land-xxhdpi": (1600, 960),
                "drawable-port-xxhdpi": (960, 1600), "drawable-land-xxxhdpi": (1920, 1280),
                "drawable-port-xxxhdpi": (1280, 1920)}


def crop_cover(im, w, h):
    """Bild formatfüllend zuschneiden (wie CSS object-fit: cover)."""
    from PIL import Image
    scale = max(w / im.width, h / im.height)
    im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def make_icon(src, size, inset=0.0):
    """Quadratisches Icon; inset lässt Rand für die adaptive Maske."""
    from PIL import Image
    inner = round(size * (1 - inset))
    base = Image.new("RGB", (size, size), BG)
    base.paste(crop_cover(src, inner, inner), ((size - inner) // 2, (size - inner) // 2))
    return base


def main():
    from PIL import Image

    hero = RAW / "hero.png"
    if not hero.exists():
        sys.exit("hero.png fehlt – zuerst build/make_images.py laufen lassen")
    src = Image.open(hero).convert("RGB")
    # Die schwebende Insel in der Bildmitte gibt das prägnanteste Icon.
    w, h = src.size
    motif = src.crop((round(w * .52), round(h * .22), round(w * .84), round(h * .78)))

    n = 0
    for dpi, size in ICON_SIZES.items():
        d = RES / f"mipmap-{dpi}"
        d.mkdir(parents=True, exist_ok=True)
        icon = make_icon(motif, size)
        icon.save(d / "ic_launcher.png")
        icon.save(d / "ic_launcher_round.png")
        n += 2
    for dpi, size in FG_SIZES.items():
        d = RES / f"mipmap-{dpi}"
        # Vordergrund der adaptiven Maske: 25 % Rand, sonst wird beschnitten
        make_icon(motif, size, inset=.25).save(d / "ic_launcher_foreground.png")
        n += 1

    for folder, (w2, h2) in SPLASH_SIZES.items():
        d = RES / folder
        d.mkdir(parents=True, exist_ok=True)
        crop_cover(src, w2, h2).save(d / "splash.png")
        n += 1

    print(f"{n} Grafiken nach {RES.relative_to(ROOT)} geschrieben")
    print(f"   Icons {', '.join(f'{k}:{v}px' for k,v in ICON_SIZES.items())}")
    print(f"   Splash {len(SPLASH_SIZES)} Auflösungen")


if __name__ == "__main__":
    main()
