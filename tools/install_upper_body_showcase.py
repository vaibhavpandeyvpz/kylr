"""Compose the README gallery from high-resolution authored Blender portraits.

First run library/tools/render_customisation.py in Blender with
--section upper_bodies --proof --resolution 1024, then run this script from the
repository root with library/.venv/Scripts/python.exe.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "library/build/customisation/upper_bodies"
TARGET = ROOT / "docs/media/tensor-upper-bodies.webp"
VARIANTS = ("default", "aegis", "lamellar", "vesper", "conduit", "reactor")


def main():
    canvas = Image.new("RGB", (1080, 840), "#17212a")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=24)
    for index, name in enumerate(VARIANTS):
        with Image.open(SOURCE / name / "blue.png") as source:
            if min(source.size) < 1024:
                raise ValueError(f"Regenerate high-resolution Blender portrait: {name}")
            portrait = source.convert("RGBA")
        x, y = (index % 3) * 360, (index // 3) * 420
        card = Image.new("RGBA", (352, 360), "#dce2e5")
        portrait.thumbnail((352, 352), Image.Resampling.LANCZOS)
        card.alpha_composite(portrait, ((352-portrait.width)//2, (360-portrait.height)//2))
        canvas.paste(card.convert("RGB"), (x+4, y+4))
        draw.text((x+18, y+379), name.upper(), fill="#eef3f5", font=font)
    canvas.save(TARGET, "WEBP", quality=92, method=6)
    print(f"Installed {TARGET.relative_to(ROOT)} from six native Blender portraits")


if __name__ == "__main__":
    main()
