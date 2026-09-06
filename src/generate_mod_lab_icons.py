"""Converts the raw Modifications Lab icons extract_game_data.py's
"mod_lab_icons" job pulls into this website's own PNGs.

Reads:
  - data/images/mod_lab_icons_raw/mods_grade_circle_01.gz (Basic -- 1 chevron)
  - data/images/mod_lab_icons_raw/mods_grade_circle_02.gz (Enhanced -- 2 chevrons)
  - data/images/mod_lab_icons_raw/mods_grade_circle_03.gz (Exceptional -- 3 chevrons)
  - data/images/mod_lab_icons_raw/mapob_buildstorage.gz

Writes:
  - data/images/mod_lab_icons/mods_grade_circle_01.png
  - data/images/mod_lab_icons/mods_grade_circle_02.png
  - data/images/mod_lab_icons/mods_grade_circle_03.png
  - data/images/mod_lab_icons/mod_lab_button.png
  - data/images/mod_lab_icons/mods_lab.png

The three mods_grade_circle_* sources are plain white/light-grey (the
game's own mod-quality-tier badges from the equipment mods menu, one per
tier -- see mod_lab_icon_jobs()' own docstring in extract_game_data.py),
recolored to each tier's own real in-game color -- see
MOD_QUALITY_COLORS below for the extractor and its libraries/colors.xml
source. Not wired into any real mod logic yet -- pulled/colored now so
they're on hand once mod-application logic gets built and a component's
own launcher button can show whichever tier is actually applied to it.

mod_lab_button.png is the same Exceptional (3-chevron) badge shape but
tinted plain white instead -- used as every Modifications Lab launcher
button's icon (table header + per-row) while no mod is applied yet, so
the neutral/unmodded state doesn't visually claim a tier that isn't
actually selected.

mapob_buildstorage.gz, by contrast, is a black-fill/white-glyph map_objects
hex badge exactly like nav_icon_jobs()' own mapob_* sources (see
generate_nav_icons.py's module docstring for the full story on why those
get recolored rather than shipped black) -- tinted the same
"faction_player" green here, used as the Modifications Lab modal's own
header icon.
"""

import gzip
import io
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "images" / "mod_lab_icons_raw"
OUT_DIR = ROOT / "data" / "images" / "mod_lab_icons"

# Same green_bright as generate_nav_icons.py's own PLAYER_GREEN (see that
# module's docstring for the libraries/colors.xml source).
BUILD_STORAGE_GREEN = (0x4D, 0xFF, 0x4D)

# The real in-game color extractor for the three mod quality tiers --
# libraries/colors.xml's own <mapping id="equipmentmod_quality_basic"
# ref="green_bright"/>, id="equipmentmod_quality_advanced"
# ref="azure_bright"/>, id="equipmentmod_quality_exceptional"
# ref="magenta_dark"/>, each resolved to that ref's own base <color .../>
# (confirmed real, not invented -- Exceptional's magenta_dark really is
# purple: r=179 g=0 b=179, equal red/blue with no green). "advanced" is
# colors.xml's own internal id for what page 20110 ("Equipment Mods")
# localizes as "Enhanced Quality" -- same mod tier, just a different
# codename in this one file.
MOD_QUALITY_COLORS = {
    "mods_grade_circle_01": (0x4D, 0xFF, 0x4D),  # Basic -- green_bright
    "mods_grade_circle_02": (0x4D, 0xB5, 0xFF),  # Enhanced -- azure_bright
    "mods_grade_circle_03": (0xB3, 0x00, 0xB3),  # Exceptional -- magenta_dark (purple)
}

# The neutral/unmodded launcher-button icon -- same source badge as
# Exceptional's 3-chevron circle, tinted plain white rather than any real
# tier color (see mod_lab_button.png's own note in the module docstring).
NEUTRAL_BUTTON_SOURCE_STEM = "mods_grade_circle_03"
NEUTRAL_BUTTON_TINT = (0xFF, 0xFF, 0xFF)


def recolor_icon(gz_path: Path, out_path: Path, tint: tuple[int, int, int]) -> None:
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
        raise FileNotFoundError(f"{RAW_DIR} not found -- run `python src/extract_game_data.py --only mod_lab_icons` first")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    written = 0
    for stem, tint in MOD_QUALITY_COLORS.items():
        gz_path = RAW_DIR / f"{stem}.gz"
        if not gz_path.exists():
            print(f"WARNING: {gz_path.relative_to(ROOT)} not found, skipping")
            continue
        recolor_icon(gz_path, OUT_DIR / f"{stem}.png", tint)
        written += 1

    neutral_src = RAW_DIR / f"{NEUTRAL_BUTTON_SOURCE_STEM}.gz"
    if neutral_src.exists():
        recolor_icon(neutral_src, OUT_DIR / "mod_lab_button.png", NEUTRAL_BUTTON_TINT)
        written += 1
    else:
        print(f"WARNING: {neutral_src.relative_to(ROOT)} not found, skipping")

    buildstorage_src = RAW_DIR / "mapob_buildstorage.gz"
    if buildstorage_src.exists():
        recolor_icon(buildstorage_src, OUT_DIR / "mods_lab.png", BUILD_STORAGE_GREEN)
        written += 1
    else:
        print(f"WARNING: {buildstorage_src.relative_to(ROOT)} not found, skipping")

    print(f"Generated {written} mod lab icon(s) into {OUT_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
