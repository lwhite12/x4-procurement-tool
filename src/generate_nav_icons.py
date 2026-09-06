"""Converts the raw map-object station icons extracted by
extract_game_data.py's "nav_icons" job, plus the existing full ship-class
icon set ship_icon_jobs() already extracts, into this website's top-nav
page icons (Fleet Planner/Cost Analysis/About/Component Analyzer), their
small "you are here" player-location markers, and the Fleet Lists tab
bar's own per-fleet ship icon + selected-fleet indicator.

Reads:
  - data/images/nav_icons_raw/mapob_shipyard.gz
  - data/images/nav_icons_raw/mapob_tradestation.gz
  - data/images/nav_icons_raw/mapob_equipmentdock.gz
  - data/images/nav_icons_raw/mapob_hightech.gz (a microchip glyph -- the
    closest real game asset to issue #4's "advanced electronics station
    symbol" spec for the Component Analyzer tab; see nav_icon_jobs()'s own
    docstring in extract_game_data.py)
  - data/images/nav_icons_raw/bordersquare.gz (the map's own "selected
    item" white frame -- see SELECTION_BOX_SRC below)
  - data/images/ships/symbols_raw/*.gz (every ship-class icon, already
    extracted by ship_icon_jobs() for the ship picker -- reused here as-is
    rather than adding a second extraction job for the same in-catalog
    files)

Writes, per station type ("fleet_planner"/"cost_analysis"/"about"/
"component_analyzer"):
  - data/images/nav_icons/<name>.png            (normal, unselected page)
  - data/images/nav_icons/<name>_highlight.png   (that page currently selected)

Writes two markers per ship-class icon:
  - data/images/nav_icons/player_location/<ship icon name>.png -- e.g.
    player_location/ship_s_fighter_01.png, tinted the bright "currently
    here"/"selected" green. The frontend uses this both for the nav bar's
    "you are here" marker (swapped to match whichever ship is currently
    loaded in the builder, defaulting to ship_s_fighter_01 when none is --
    see app.js's updatePlayerLocationMarker()) and for the Fleet Lists tab
    bar's own ship icon when that fleet is the active one.
  - data/images/nav_icons/fleet_tab/<ship icon name>.png -- the same icon
    in the plain, un-highlighted green, for the Fleet Lists tab bar's ship
    icon when that fleet is *not* the active one.

Writes one selected-fleet indicator:
  - data/images/nav_icons/selection_box_corner.png -- one corner of the
    game's own white "this map item is selected" frame (bordersquare.gz),
    cropped down to just its L-shaped bracket (see SELECTION_BOX_CORNER_SIZE
    below) -- the source texture is a plain, fully-connected square frame,
    but the game only ever actually *renders* it as four thin floating
    corner brackets with a gap along each straight edge, not a solid
    connected outline, so this crops out one corner (top-left) for the
    frontend to place at all four corners of the active fleet's tab-bar
    ship icon via CSS rotation (90/180/270deg -- the source frame is
    perfectly symmetric under rotation, so one crop covers all four),
    mirroring how the in-game map marks a selected object.

Run after `python src/extract_game_data.py --only nav_icons ship_icons`
(or a full extraction run). Fully reproducible from the raw/ folders
above, so the output can be freely deleted and regenerated.

Each mapob_ source texture is the game's own map icon exactly as it
appears in the universe map -- hexagon badge and station-type glyph
already combined in one image -- but shipped as a flat black hex fill
with a white glyph/border, since the game tints the black fill to a
context color at runtime (faction ownership, selection state, ...) rather
than baking color into the texture. This script recreates two of those
runtime tint states:

  - Normal: libraries/colors.xml's own
    <mapping id="faction_player" ref="green_bright_weak_glow"/>, resolved
    to its base <color id="green_bright" r="77" g="255" b="77"/>.
  - Highlight (the page currently selected, mirroring how the map
    highlights a station you're actually *at*): colors.xml's own
    <mapping id="holomap_playerlocation_playerowned"
    ref="green_extra_bright_weak_glow"/>, resolved to its base
    <color id="green_extra_bright" r="204" g="255" b="204"/> -- this is
    the one and only station/location-specific highlight color in the
    whole file (every other "highlight"/"selected" mapping is a generic
    UI azure/white, not this map-specific player-location one).

("glow" in a color id is a bloom-intensity parameter for the game's own
renderer, not a color component, so it's dropped here.)

Ship-class icons (symbols_raw/*.gz) are plain white fill + black outline
on transparent -- a different shape than the mapob_ files' black-fill/
white-glyph hex badges, but the same recolor_icon() luminance-blend
technique works for either, since both are ultimately grayscale masks
with the tint only ever going where luminance is high. Includes
shipicons_atlas_diff.gz (a combined sprite sheet, not a single icon --
ship_icon_jobs() pulls the whole folder unfiltered, see that function's
own docstring) -- harmless since nothing ever looks up that name as a
real ships_base.icon value, same as generate_ship_icons.py's own
unfiltered conversion of it.

SELECTION_BOX_SRC (widget/bordersquare.gz) is different from every icon
above: it's already plain opaque white (255,255,255) with the frame shape
carried entirely in the alpha channel, not a black/white luminance mask
the game recolors at runtime -- confirmed against libraries/colors.xml's
own holomap_selection_bracket/holomap_selected mappings, both plain
"white*" colors, never a green/faction one. So it's converted straight to
PNG with no recolor_icon() tint step, just a crop down to one corner (see
SELECTION_BOX_CORNER_SIZE).
"""

import gzip
import io
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "images" / "nav_icons_raw"
SHIP_ICONS_RAW_DIR = ROOT / "data" / "images" / "ships" / "symbols_raw"
OUT_DIR = ROOT / "data" / "images" / "nav_icons"
PLAYER_LOCATION_OUT_DIR = OUT_DIR / "player_location"
FLEET_TAB_OUT_DIR = OUT_DIR / "fleet_tab"
SELECTION_BOX_SRC = RAW_DIR / "bordersquare.gz"

# bordersquare.gz is a 64x64 fully-connected square frame, 8px thick on
# every side (verified by inspecting its alpha channel directly) -- that
# 8px thickness is baked into the source pixels and can't be cropped
# thinner directly, so a crop this size (rather than the original 24) is
# what actually halves the *rendered* thickness: the frontend displays
# this crop at a fixed pixel size (see .fleet-list-tab-selection-corner in
# style.css), so doubling the crop's arm length halves the fraction of
# that fixed display size the same 8px-thick line ends up covering.
SELECTION_BOX_CORNER_SIZE = 48

# green_bright / green_extra_bright from libraries/colors.xml (see module
# docstring) -- normal vs. this-page-is-selected (or this-fleet-is-active)
# tint.
PLAYER_GREEN = (0x4D, 0xFF, 0x4D)
PLAYER_GREEN_HIGHLIGHT = (0xCC, 0xFF, 0xCC)

# source .gz stem -> output basename, one per top-nav page.
ICON_MAP = {
    "mapob_shipyard": "fleet_planner",
    "mapob_tradestation": "cost_analysis",
    "mapob_equipmentdock": "about",
    "mapob_hightech": "component_analyzer",
}


def recolor_icon(gz_path: Path, out_path: Path, tint: tuple[int, int, int]) -> None:
    dds_bytes = gzip.decompress(gz_path.read_bytes())
    with Image.open(io.BytesIO(dds_bytes)) as img:
        img = img.convert("RGBA")
        r, g, b, a = img.split()

        # Every source here is effectively grayscale (a black/dark region,
        # a white/light region, antialiased blends between them at edges)
        # -- treat that luminance as a 0..255 blend factor between black
        # (dark regions stay black, providing an outline/fill-shadow) and
        # the target tint (light regions become that color), so edges
        # blend smoothly instead of leaving a hard black/color seam. Alpha
        # (fully transparent background, antialiased at each shape's own
        # outer edge) is preserved untouched.
        luminance = Image.merge("RGB", (r, g, b)).convert("L")
        tint_layer = Image.new("RGB", img.size, tint)
        black_layer = Image.new("RGB", img.size, (0, 0, 0))
        colored_rgb = Image.composite(tint_layer, black_layer, luminance)

        Image.merge("RGBA", (*colored_rgb.split(), a)).save(out_path)


def convert_selection_box_corner(gz_path: Path, out_path: Path) -> None:
    dds_bytes = gzip.decompress(gz_path.read_bytes())
    with Image.open(io.BytesIO(dds_bytes)) as img:
        n = SELECTION_BOX_CORNER_SIZE
        img.convert("RGBA").crop((0, 0, n, n)).save(out_path)


def main() -> None:
    if not RAW_DIR.exists():
        raise FileNotFoundError(f"{RAW_DIR} not found -- run `python src/extract_game_data.py --only nav_icons` first")
    if not SHIP_ICONS_RAW_DIR.exists():
        raise FileNotFoundError(
            f"{SHIP_ICONS_RAW_DIR} not found -- run `python src/extract_game_data.py --only ship_icons` first"
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PLAYER_LOCATION_OUT_DIR.mkdir(parents=True, exist_ok=True)
    FLEET_TAB_OUT_DIR.mkdir(parents=True, exist_ok=True)

    written = 0
    for stem, out_name in ICON_MAP.items():
        gz_path = RAW_DIR / f"{stem}.gz"
        if not gz_path.exists():
            print(f"WARNING: {gz_path.relative_to(ROOT)} not found, skipping")
            continue
        recolor_icon(gz_path, OUT_DIR / f"{out_name}.png", PLAYER_GREEN)
        recolor_icon(gz_path, OUT_DIR / f"{out_name}_highlight.png", PLAYER_GREEN_HIGHLIGHT)
        written += 2

    ship_icon_paths = sorted(SHIP_ICONS_RAW_DIR.glob("*.gz"))
    for gz_path in ship_icon_paths:
        # Bright tint: nav bar's "you are here" marker, and the Fleet Lists
        # tab bar's ship icon when that fleet is the active one.
        recolor_icon(gz_path, PLAYER_LOCATION_OUT_DIR / f"{gz_path.stem}.png", PLAYER_GREEN_HIGHLIGHT)
        # Plain tint: the tab bar's ship icon for every other, inactive fleet.
        recolor_icon(gz_path, FLEET_TAB_OUT_DIR / f"{gz_path.stem}.png", PLAYER_GREEN)
    written += len(ship_icon_paths) * 2

    if SELECTION_BOX_SRC.exists():
        convert_selection_box_corner(SELECTION_BOX_SRC, OUT_DIR / "selection_box_corner.png")
        written += 1
    else:
        print(f"WARNING: {SELECTION_BOX_SRC.relative_to(ROOT)} not found, skipping")

    print(f"Generated {written} nav icon(s) into {OUT_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
