"""Converts the raw faction badge textures extracted by
extract_game_data.py's "faction_icons" job into web-displayable, tinted
PNGs.

Reads:
  - data/images/factions_raw/faction_<name>_diffhq.gz  (one gzip-compressed
                                          DDS texture per race -- see
                                          faction_icon_jobs() in
                                          extract_game_data.py for why this
                                          is narrowed to the 9 real races
                                          this app tracks, not the game's
                                          full 38-faction badge set)

Writes:
  - data/images/factions/<name>.png  (decompressed, converted from DDS,
                                       tinted, and renamed to just the bare
                                       race key -- "faction_argon_diffhq.gz"
                                       -> "argon.png" -- matching
                                       ships_base.owner_faction's own values
                                       directly, so the frontend can build
                                       the URL straight from that column
                                       with no extra lookup)

Run after `python src/extract_game_data.py --only faction_icons` (or a full
extraction run). Every output here is fully reproducible from
factions_raw/, so the folder can be freely deleted and regenerated.

Each source texture is a plain white/light-grey glyph (antialiased against
a black/transparent background) on a transparent canvas, not a pre-colored
badge -- same "runtime-tinted grayscale mask" convention
generate_nav_icons.py's own recolor_icon() already handles for the map
station icons and ship-class icons, and the exact same technique is reused
here verbatim, just with each faction's own real color (FACTION_TINTS
below, matching src/static/app.js's FACTION_COLORS exactly -- these are
the game's own per-race UI colors, not picked independently) instead of
nav_icons' one fixed player-green.
"""

import gzip
import io
import re
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "images" / "factions_raw"
OUT_DIR = ROOT / "data" / "images" / "factions"

FACTION_GZ_NAME_RE = re.compile(r"^faction_(.+)_diffhq$")

# Must match src/static/app.js's FACTION_COLORS exactly (only the 9 keys
# faction_icon_jobs() actually extracts -- "neutral" has no real texture,
# see that job's own docstring).
FACTION_TINTS: dict[str, tuple[int, int, int]] = {
    "argon": (0x00, 0x69, 0xB3),
    "boron": (0x4D, 0xB5, 0xFF),
    "paranid": (0xB3, 0x00, 0xB3),
    "split": (0xB3, 0x61, 0x00),
    "teladi": (0xB3, 0xB3, 0x00),
    "terran": (0x99, 0xD5, 0xFF),
    "xenon": (0xB3, 0x00, 0x00),
    "khaak": (0xFF, 0x00, 0xFF),
    "yaki": (0xFF, 0x4D, 0x4D),
}


def recolor_icon(gz_path: Path, out_path: Path, tint: tuple[int, int, int]) -> None:
    """Same luminance-blend recolor generate_nav_icons.py uses -- see that
    module's own recolor_icon() docstring for the full explanation. Dark
    regions stay black (outline/shadow), light regions become `tint`,
    alpha (the shape's own outer silhouette) is preserved untouched.
    """
    dds_bytes = gzip.decompress(gz_path.read_bytes())
    with Image.open(io.BytesIO(dds_bytes)) as img:
        img = img.convert("RGBA")
        r, g, b, a = img.split()
        luminance = Image.merge("RGB", (r, g, b)).convert("L")
        tint_layer = Image.new("RGB", img.size, tint)
        black_layer = Image.new("RGB", img.size, (0, 0, 0))
        colored_rgb = Image.composite(tint_layer, black_layer, luminance)
        Image.merge("RGBA", (*colored_rgb.split(), a)).save(out_path)


def main() -> None:
    if not RAW_DIR.exists():
        raise FileNotFoundError(
            f"{RAW_DIR} not found -- run `python src/extract_game_data.py --only faction_icons` first"
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    gz_paths = sorted(RAW_DIR.glob("*.gz"))
    written = 0
    for gz_path in gz_paths:
        match = FACTION_GZ_NAME_RE.match(gz_path.stem)
        race_key = match.group(1) if match else gz_path.stem
        tint = FACTION_TINTS.get(race_key)
        if tint is None:
            print(f"WARNING: no tint color for '{race_key}' ({gz_path.name}), skipping")
            continue
        recolor_icon(gz_path, OUT_DIR / f"{race_key}.png", tint)
        written += 1

    print(f"Converted {written} faction icon(s) into {OUT_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
