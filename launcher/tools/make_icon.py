"""Генерация иконки PixelPeak.

Если положить картинку в assets/icon_source.png — скрипт сделает из неё
квадратную иконку icon.png (256x256) и icon.ico (multi-size).
Если исходника нет — нарисует плейсхолдер с логотипом "PP".

Запуск:
    python tools/make_icon.py
"""
from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ASSETS = Path(__file__).resolve().parent.parent / "assets"
SOURCE = ASSETS / "icon_source.png"
ICON_PNG = ASSETS / "icon.png"
ICON_ICO = ASSETS / "icon.ico"

ACCENT = (124, 92, 255, 255)
ACCENT2 = (74, 214, 255, 255)
BG = (11, 13, 23, 255)


def gradient(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), BG)
    px = img.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * size)
            r = int(ACCENT[0] * (1 - t) + ACCENT2[0] * t)
            g = int(ACCENT[1] * (1 - t) + ACCENT2[1] * t)
            b = int(ACCENT[2] * (1 - t) + ACCENT2[2] * t)
            px[x, y] = (r, g, b, 255)
    return img


def find_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\segoeuib.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def make_placeholder(size: int = 256) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    # rounded square with gradient
    grad = gradient(size)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * 0.22), fill=255)
    img.paste(grad, (0, 0), mask)

    draw = ImageDraw.Draw(img)
    font = find_font(int(size * 0.5))
    text = "PP"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1]), text, font=font, fill=BG)
    return img


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    if SOURCE.exists():
        base = Image.open(SOURCE).convert("RGBA")
        side = max(base.size)
        square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        square.paste(base, ((side - base.width) // 2, (side - base.height) // 2))
        icon = square.resize((512, 512), Image.LANCZOS)
        print(f"Иконка создана из {SOURCE.name}")
    else:
        icon = make_placeholder(512)
        print("Исходник не найден — создан плейсхолдер 'PP'.")

    icon.resize((256, 256), Image.LANCZOS).save(ICON_PNG)
    icon.save(ICON_ICO, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"Готово:\n  {ICON_PNG}\n  {ICON_ICO}")


if __name__ == "__main__":
    main()
