"""
Generate a simple Windows .ico file with the letters "md" centered.
Requires Pillow (PIL). Usage:
    python tools\generate_icon.py --output build\app.ico
"""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

SZ = 512
TEXT = "md"
BG = (30, 30, 30, 255)
FG = (255, 255, 255, 255)


def make_icon(output: Path):
    output.parent.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGBA", (SZ, SZ), BG)
    draw = ImageDraw.Draw(img)

    # Try a large truetype font; fall back to default
    try:
        font = ImageFont.truetype("arial.ttf", int(SZ * 0.5))
    except Exception:
        font = ImageFont.load_default()

    w, h = draw.textsize(TEXT, font=font)
    draw.text(((SZ - w) / 2, (SZ - h) / 2), TEXT, font=font, fill=FG)

    # Save ICO with multiple sizes
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    # Pillow supports saving .ico with sizes parameter
    img.save(str(output), format="ICO", sizes=sizes)
    print(f"Wrote icon to: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="build\\app.ico")
    args = parser.parse_args()
    make_icon(Path(args.output))
