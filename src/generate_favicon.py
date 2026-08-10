"""Converts the raw shipyard station-icon texture extracted by
extract_game_data.py's "favicon_icon" job into this website's favicon.

Reads:
  - data/images/favicon_raw/si_shipyard.gz

Writes:
  - data/images/favicon.png

Run after `python src/extract_game_data.py --only favicon` (or a full
extraction run). Fully reproducible from favicon_raw/, so the output can be
freely deleted and regenerated. Same gzip-compressed-DDS -> PNG conversion
generate_ship_icons.py already does for ship-class icons, kept as its own
small script since this is a different source folder and a single fixed
output file rather than a per-item lookup set.
"""

import gzip
import io
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
RAW_PATH = ROOT / "data" / "images" / "favicon_raw" / "si_shipyard.gz"
OUT_PATH = ROOT / "data" / "images" / "favicon.png"


def main() -> None:
    if not RAW_PATH.exists():
        raise FileNotFoundError(f"{RAW_PATH} not found -- run `python src/extract_game_data.py --only favicon` first")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    dds_bytes = gzip.decompress(RAW_PATH.read_bytes())
    with Image.open(io.BytesIO(dds_bytes)) as img:
        icon = img.convert("RGBA")
        # The source texture is a white icon on transparency -- nearly
        # invisible against a light browser tab background, so it's
        # composited onto a solid square first rather than shipped
        # transparent. Matches style.css's --bg-section (#0e1826), the same
        # dark blue every major <section> (Pick a ship, Procurement List,
        # ...) already uses, rather than plain black.
        background = Image.new("RGBA", icon.size, (0x0E, 0x18, 0x26, 255))
        Image.alpha_composite(background, icon).convert("RGB").save(OUT_PATH)

    print(f"Converted favicon into {OUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
