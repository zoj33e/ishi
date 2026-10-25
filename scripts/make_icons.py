"""Render the PWA icons (teacher mark: black stone with a brush stroke on kaya wood).

Usage: uv run --with pillow python scripts/make_icons.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "apps" / "web" / "public" / "icons"
WOOD, INK, PAPER = (220, 179, 92), (31, 27, 22), (246, 241, 231)


def render(size: int, maskable: bool) -> Image.Image:
    s = 4  # supersample for smooth edges
    n = size * s
    img = Image.new("RGB", (n, n), WOOD if maskable else PAPER)
    d = ImageDraw.Draw(img)
    if not maskable:
        d.ellipse([n * 0.03, n * 0.03, n * 0.97, n * 0.97], fill=WOOD)
    r = n * (0.27 if maskable else 0.32)  # maskable keeps the mark inside the 80% safe zone
    c = n / 2
    d.ellipse([c - r, c - r + n * 0.015, c + r, c + r + n * 0.015], fill=INK)
    # A short brush-like highlight arc on the upper-left of the stone.
    w = int(n * 0.045)
    hr = r * 0.68
    d.arc([c - hr, c - hr, c + hr, c + hr], start=200, end=260, fill=PAPER, width=w)
    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    render(192, False).save(OUT / "icon-192.png")
    render(512, False).save(OUT / "icon-512.png")
    render(512, True).save(OUT / "icon-maskable-512.png")
    render(180, True).save(OUT / "apple-touch-icon.png")
    render(64, False).convert("RGBA").save(OUT.parents[1] / "app" / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    print(f"icons written to {OUT}")


if __name__ == "__main__":
    main()
