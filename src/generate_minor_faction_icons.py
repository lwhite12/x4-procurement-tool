"""Converts the raw minor-faction badge textures extracted by
extract_game_data.py's "minor_faction_icons" job into web-displayable,
tinted PNGs -- the sibling of generate_faction_icons.py (majors), which
this script does NOT touch or depend on.

Reads:
  - data/images/factions_minor_raw/faction_<name>_diffhq.gz  (one per minor
                                          faction -- see
                                          minor_faction_icon_jobs() in
                                          extract_game_data.py for the full
                                          list and why it's this specific
                                          16, not the game's every minor/
                                          story faction)
  - data/libraries/colors.xml            (real per-faction UI colors -- see
                                          colors_xml_job())

Writes:
  - data/images/factions/<name>.png  (same output directory
                                       generate_faction_icons.py's majors
                                       already write into -- no filename
                                       collisions, the two sets are
                                       disjoint -- so the frontend can build
                                       a faction icon URL from any owner
                                       faction key, major or minor, with
                                       the exact same /images/factions/
                                       <key>.png pattern)

Run after `python src/extract_game_data.py --only minor_faction_icons
colors_xml` (or a full extraction run). Fully reproducible from
factions_minor_raw/ + colors.xml, so data/images/factions/'s minor entries
can be freely deleted and regenerated (the major ones alongside them are
untouched, since this script only ever writes the 16 names below).

Each source texture is a plain white/light-grey glyph on transparent, same
as the major faction badges -- recolor_icon() below is the exact technique
generate_nav_icons.py/generate_faction_icons.py already use, just fed a
color resolved from colors.xml instead of a hand-picked one, since a minor
faction's real in-game color isn't otherwise known/guessed at.
"""

import gzip
import io
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "images" / "factions_minor_raw"
COLORS_XML = ROOT / "data" / "libraries" / "colors.xml"
OUT_DIR = ROOT / "data" / "images" / "factions"

FACTION_GZ_NAME_RE = re.compile(r"^faction_(.+)_diffhq$")


def load_faction_colors(colors_xml: Path) -> dict[str, tuple[int, int, int]]:
    """Every <mapping id="faction_<name>" ref="<color id>"/> in colors.xml,
    resolved through to its base <color r="" g="" b=""/> entry -- e.g.
    "buccaneers" -> (0, 100, 102) via "cyan_very_dark_moderate_glow".
    "glow" (a bloom-intensity render parameter, not a color component) is
    ignored, same as generate_nav_icons.py's own module docstring already
    notes for the majors it hand-resolved the same way.
    """
    root = ET.parse(colors_xml).getroot()
    base_colors = {
        color_el.get("id"): (int(color_el.get("r")), int(color_el.get("g")), int(color_el.get("b")))
        for color_el in root.iter("color")
        if color_el.get("id") is not None
    }
    faction_colors: dict[str, tuple[int, int, int]] = {}
    for mapping_el in root.iter("mapping"):
        mapping_id = mapping_el.get("id") or ""
        if not mapping_id.startswith("faction_"):
            continue
        faction_key = mapping_id.removeprefix("faction_")
        ref = mapping_el.get("ref")
        if ref in base_colors:
            faction_colors[faction_key] = base_colors[ref]
    return faction_colors


def recolor_icon(gz_path: Path, out_path: Path, tint: tuple[int, int, int]) -> None:
    """Same luminance-blend recolor generate_nav_icons.py/
    generate_faction_icons.py use -- see either module's own recolor_icon()
    docstring for the full explanation. Dark regions stay black (outline/
    shadow), light regions become `tint`, alpha (the badge's own outer
    silhouette) is preserved untouched.
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
            f"{RAW_DIR} not found -- run `python src/extract_game_data.py --only minor_faction_icons` first"
        )
    if not COLORS_XML.exists():
        raise FileNotFoundError(f"{COLORS_XML} not found -- run `python src/extract_game_data.py --only colors_xml` first")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    faction_colors = load_faction_colors(COLORS_XML)

    gz_paths = sorted(RAW_DIR.glob("*.gz"))
    written = 0
    for gz_path in gz_paths:
        match = FACTION_GZ_NAME_RE.match(gz_path.stem)
        faction_key = match.group(1) if match else gz_path.stem
        tint = faction_colors.get(faction_key)
        if tint is None:
            print(f"WARNING: no colors.xml mapping for '{faction_key}' ({gz_path.name}), skipping")
            continue
        recolor_icon(gz_path, OUT_DIR / f"{faction_key}.png", tint)
        written += 1

    print(f"Converted {written} minor faction icon(s) into {OUT_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
