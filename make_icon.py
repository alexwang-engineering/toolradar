#!/usr/bin/env python3
"""Generate ToolRadar's original, brand-neutral macOS radar icon."""

from pathlib import Path
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent
ICONSET = ROOT / "ToolRadar.iconset"
BACKGROUND = (8, 17, 31, 255)
PANEL = (15, 31, 50, 255)
GRID = (41, 84, 112, 255)
ACCENT = (83, 227, 168, 255)
SWEEP = (83, 227, 168, 80)
DOT = (255, 190, 92, 255)


def draw_icon(size: int) -> Image.Image:
    scale = size / 1024
    image = Image.new("RGBA", (size, size), BACKGROUND)
    draw = ImageDraw.Draw(image, "RGBA")

    margin = round(72 * scale)
    radius = round(190 * scale)
    draw.rounded_rectangle(
        (margin, margin, size - margin, size - margin),
        radius=radius,
        fill=PANEL,
    )

    centre = (size // 2, size // 2)
    radar_radius = round(330 * scale)
    line_width = max(1, round(10 * scale))

    for fraction in (1.0, 0.66, 0.33):
        ring = round(radar_radius * fraction)
        draw.ellipse(
            (
                centre[0] - ring,
                centre[1] - ring,
                centre[0] + ring,
                centre[1] + ring,
            ),
            outline=GRID,
            width=line_width,
        )

    draw.line(
        (centre[0] - radar_radius, centre[1], centre[0] + radar_radius, centre[1]),
        fill=GRID,
        width=line_width,
    )
    draw.line(
        (centre[0], centre[1] - radar_radius, centre[0], centre[1] + radar_radius),
        fill=GRID,
        width=line_width,
    )

    # A translucent scan sector and crisp leading edge make the mark readable
    # even at Finder's smallest icon sizes.
    box = (
        centre[0] - radar_radius,
        centre[1] - radar_radius,
        centre[0] + radar_radius,
        centre[1] + radar_radius,
    )
    draw.pieslice(box, start=315, end=360, fill=SWEEP)
    end = (
        centre[0] + round(radar_radius * 0.707),
        centre[1] - round(radar_radius * 0.707),
    )
    draw.line((*centre, *end), fill=ACCENT, width=max(2, round(18 * scale)))

    for x, y, radius in ((650, 360, 24), (378, 620, 20), (700, 640, 16)):
        px, py, pr = round(x * scale), round(y * scale), max(2, round(radius * scale))
        draw.ellipse((px - pr, py - pr, px + pr, py + pr), fill=DOT)

    centre_radius = max(2, round(20 * scale))
    draw.ellipse(
        (
            centre[0] - centre_radius,
            centre[1] - centre_radius,
            centre[0] + centre_radius,
            centre[1] + centre_radius,
        ),
        fill=ACCENT,
    )
    return image


def main() -> None:
    ICONSET.mkdir(exist_ok=True)
    master = draw_icon(1024)
    specifications = (
        (16, "icon_16x16.png"),
        (32, "icon_16x16@2x.png"),
        (32, "icon_32x32.png"),
        (64, "icon_32x32@2x.png"),
        (128, "icon_128x128.png"),
        (256, "icon_128x128@2x.png"),
        (256, "icon_256x256.png"),
        (512, "icon_256x256@2x.png"),
        (512, "icon_512x512.png"),
        (1024, "icon_512x512@2x.png"),
    )

    for pixels, name in specifications:
        icon = master if pixels == 1024 else master.resize((pixels, pixels), Image.Resampling.LANCZOS)
        icon.save(ICONSET / name, "PNG")

    print(f"Generated {len(specifications)} icons in {ICONSET}")
    print("Run: iconutil -c icns ToolRadar.iconset")


if __name__ == "__main__":
    main()
