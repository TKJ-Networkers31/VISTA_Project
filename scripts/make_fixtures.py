"""Generate synthetic OCR fixtures (no personal data). Run: python -m scripts.make_fixtures

Output: tests/fixtures/*.png and tests/fixtures/manifest.json (expected text per image).
Fixtures are committed so results do not drift with Pillow's font rendering.
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures"

# (file, size, font_px, bg, fg, lines, category)
SPECS = [
    ("printed_en.png", (900, 260), 56, "white", "black", ["Hello VISTA", "Invoice 2026 Total 150"], "small"),
    ("printed_id.png", (900, 260), 56, "white", "black", ["Terima kasih", "Selamat datang di VISTA"], "small"),
    ("multiline.png", (1000, 520), 52, "white", "black",
     ["Line one: alpha beta", "Line two: gamma 12345", "Line three: delta", "Line four: END"], "medium"),
    ("inverted.png", (900, 260), 56, "black", "white", ["NIGHT MODE", "Contrast 100 percent"], "small"),
    ("large_downscale.png", (3000, 2000), 150, "white", "black",
     ["Large image", "Downscale test 2026", "VISTA OCR"], "large"),
    ("blank.png", (640, 240), 40, "white", "black", [], "blank"),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for name, size, px, bg, fg, lines, cat in SPECS:
        img = Image.new("RGB", size, bg)
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default(size=px)
        y = 30
        for line in lines:
            draw.text((40, y), line, fill=fg, font=font)
            y += int(px * 1.6)
        img.save(OUT / name, "PNG", optimize=True)
        manifest.append({"file": name, "category": cat, "width": size[0], "height": size[1], "expected_lines": lines})
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"wrote {len(manifest)} fixtures to {OUT}")


if __name__ == "__main__":
    main()
