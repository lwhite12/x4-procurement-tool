"""Converts the raw ship-class icon textures extracted by
extract_game_data.py's "ship_icons" job into web-displayable PNGs.

Reads:
  - data/images/ships/symbols_raw/*.gz  (one gzip-compressed DDS texture
                                          per size+purpose combo, e.g.
                                          "ship_s_fighter_01.gz" -- see
                                          ships_base.icon in
                                          generate_ships_table.py for how a
                                          specific ship maps to one of
                                          these by name)

Writes:
  - data/images/ships/symbols/<name>.png  (same basename as the source
                                            .gz, decompressed and
                                            converted from DDS to PNG)

Run after `python src/extract_game_data.py --only ship_icons` (or a full
extraction run). Every output here is fully reproducible from
symbols_raw/, so the folder can be freely deleted and regenerated.
"""

import gzip
import io
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "images" / "ships" / "symbols_raw"
OUT_DIR = ROOT / "data" / "images" / "ships" / "symbols"


def convert_icon(gz_path: Path, out_dir: Path) -> None:
    dds_bytes = gzip.decompress(gz_path.read_bytes())
    with Image.open(io.BytesIO(dds_bytes)) as img:
        img.convert("RGBA").save(out_dir / f"{gz_path.stem}.png")


def main() -> None:
    if not RAW_DIR.exists():
        raise FileNotFoundError(
            f"{RAW_DIR} not found -- run `python src/extract_game_data.py --only ship_icons` first"
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    gz_paths = sorted(RAW_DIR.glob("*.gz"))
    for gz_path in gz_paths:
        convert_icon(gz_path, OUT_DIR)

    print(f"Converted {len(gz_paths)} ship icon(s) into {OUT_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
