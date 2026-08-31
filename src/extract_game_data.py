"""Extract data files from the X4: Foundations game installation using XRCatTool.

Runs XTools_1.11/XRCatTool.exe against the local Steam install (base game +
every installed extension) to pull specific file patterns out of the game's
.cat/.dat catalogs and into data/.

XRCatTool only reads catalogs when given explicit .cat file paths for -in --
passing a bare folder (base game root or an extension folder) silently
matches zero files, it does not auto-discover 01.cat../ext_01.cat inside it.
So -in is built from the actual *.cat files (excluding the *_sig.cat
signature catalogs) found in the game root and each extensions/<name> folder.

XRCatTool also always writes matched files nested under their full in-catalog
path (e.g. <out>/assets/units/size_s/macros/...), there is no CLI flag to
flatten this (that's a GUI-only "Keep folder hierarchy" checkbox). Since this
project keeps macros flat under data/ships/size_*_macros, each job extracts
into a temporary staging folder first, then the matched files are copied up
into the flat destination and the staging folder is discarded.

Ship macro/component files live in-catalog under a per-size subfolder
(assets/units/size_X/...), but which size-folder *names* actually exist
isn't assumed (a generic assets/units/[^/]+/... pattern matches whatever's
really there) -- each job is a single flat pull into a *_raw/ staging
folder, then sort_ship_files_by_class() (called from main(), after the
matching job runs) re-sorts every file into <class>_macros/<class>_
components/ based on what each file's own <macro class="..."/>/<component
class="..."/> attribute actually says, not which folder it happened to be
found in. See ship_macro_jobs()/ship_component_jobs()/
sort_ship_files_by_class() for the full reasoning.

Equipment (engine/shield/weapon/turret) files have no per-size subfolder at
all -- all sizes sit flat together under a per-type folder (assets/props/
Engines/, assets/props/SurfaceElements/, or, for weapons/turrets which
share the same per-damage-class subfolders, assets/props/WeaponSystems/
<class>/) -- so their jobs instead match the size token embedded in the
filename itself (e.g. "engine_arg_s_..."). See EQUIPMENT_TYPE_PATH_PREFIXES.
This is a real, separate fragility from ships' own (a mod whose equipment
filenames don't follow the type_race_size_variant_mk convention would be
silently skipped at the extraction step, not just mis-sorted afterward) --
not addressed by this round of changes, since equipment's own *size* comes
from a completely different source (each component's own mount-tag, e.g.
tags="small"/"medium", not a macro-level class attribute the way ship size
does -- confirmed: an equipment macro's own class is its component *type*,
e.g. class="turret"/"engine"/"shieldgenerator"/"weapon", not a size at
all) -- revisit separately if this becomes a real problem.

To add a new extraction (e.g. language files, ware macros), append an
ExtractionJob to EXTRACTION_JOBS under a suitable group name.

Every file this script writes is fully reproducible from the game install,
so groups can be freely skipped or deleted and regenerated later with no
data-loss concern (see --only / --skip).

Also copies version.dat and every installed extension's content.xml into
data/ on every run (see copy_metadata_files()) -- these two aren't inside
any .cat/.dat catalog so XRCatTool plays no part in it, and this step isn't
one of the --only/--skip groups below.
"""

import argparse
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
XRCATTOOL_EXE = ROOT / "XTools_1.11" / "XRCatTool.exe"
DATA_DIR = ROOT / "data"
SHIPS_DIR = DATA_DIR / "ships"

GAME_ROOT = Path(r"C:\Program Files (x86)\Steam\steamapps\common\X4 Foundations")

SHIP_SIZES = ["s", "m", "l", "xl"]

# Short suffix used to disambiguate per-extension copies of files that share
# the same in-catalog name across the base game and every DLC (e.g.
# libraries/wares.xml). Falls back to the extension folder name (minus the
# "ego_dlc_" prefix) for any extension not listed here.
EXTENSION_SUFFIXES = {
    "ego_dlc_boron": "bor",
    "ego_dlc_split": "spl",
    "ego_dlc_terran": "ter",
    "ego_dlc_pirate": "pir",
    "ego_dlc_timelines": "tim",
    "ego_dlc_mini_01": "mini01",
    "ego_dlc_mini_02": "mini02",
}


@dataclass
class ExtractionJob:
    name: str
    group: str
    include_pattern: str
    out_dir: Path
    # Overrides for jobs that don't fit the "combine every source, keep
    # original filenames" default (e.g. per-extension files that must be
    # renamed since every source uses the same in-catalog filename).
    in_paths: list[str] | None = None
    dest_name: str | None = None


def catalog_files(root: Path) -> list[str]:
    """Real (non-signature) .cat files directly in `root`, in load order."""
    return sorted(
        str(p) for p in root.glob("*.cat") if not p.name.endswith("_sig.cat")
    )


def extension_dirs() -> list[Path]:
    ext_root = GAME_ROOT / "extensions"
    if not ext_root.exists():
        return []
    return sorted(p for p in ext_root.iterdir() if p.is_dir())


def copy_metadata_files() -> None:
    """Copies version.dat (the base game's own build number) and every
    installed extension's content.xml (id/name/version/date -- see
    generate_ships_table.py's parse_source_versions(), which reads these
    back out for the About page's "built from these versions" section)
    straight from the Steam install into data/. Unlike everything else this
    script pulls, neither file lives inside a .cat/.dat catalog -- both are
    plain loose files already sitting on disk -- so there's nothing for
    XRCatTool to do here, just a copy. Always runs, not gated by
    --only/--skip like the real extraction jobs below, since it's two kinds
    of tiny, cheap file copy, not worth its own group.
    """
    dest_version = DATA_DIR / "version.dat"
    shutil.copyfile(GAME_ROOT / "version.dat", dest_version)

    ext_dirs = extension_dirs()
    ext_out_dir = DATA_DIR / "extensions"
    for ext_dir in ext_dirs:
        content_xml = ext_dir / "content.xml"
        if not content_xml.exists():
            print(f"WARNING: no content.xml found for extension {ext_dir.name}")
            continue
        dest = ext_out_dir / ext_dir.name / "content.xml"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(content_xml, dest)

    print(f"Copied version.dat -> {dest_version.relative_to(ROOT)}")
    print(f"Copied content.xml for {len(ext_dirs)} extension(s) -> {ext_out_dir.relative_to(ROOT)}")


def game_input_paths() -> list[str]:
    """Catalog files for the base game plus every installed extension."""
    paths = catalog_files(GAME_ROOT)
    for ext_dir in extension_dirs():
        paths.extend(catalog_files(ext_dir))
    return paths


def ship_macro_jobs() -> list[ExtractionJob]:
    """Ship hull, cockpit, and per-ship storage/cargo macros -- one flat job,
    not one per assumed size-folder name. assets/units/ is a real, stable
    catalog convention (confirmed: a generic assets/units/[^/]+/macros/
    scan matches exactly the 5 folders the base game actually ships --
    size_xs/size_s/size_m/size_l/size_xl -- nothing else sweeps in), but
    which *names* exist under it is not: enumerating SHIP_SIZES here would
    silently miss "size_xs" (a real folder this pipeline never pulled
    before -- see sort_ship_files_by_class()'s own docstring for why that
    turned out to be harmless, and would silently miss whatever a mod
    calls its own new size folder, if it ever adds one.

    Extracted flat into macros_raw/ (no size-named subfolder at all,
    since none can be assumed at this stage) -- sort_ship_files_by_class(),
    called from main() right after this job runs, re-sorts every file from
    there into <class>_macros/ based on each macro's own real <macro
    class="..."/> attribute, which is what generate_ships_table.py actually
    treats as authoritative (see that module's "Ship stats and flight
    model" docstring section) -- not a guess from a folder name a mod has
    no obligation to follow.
    """
    return [
        ExtractionJob(
            name="ship_macros",
            group="ships",
            include_pattern=r"assets/units/[^/]+/macros/.*\.xml$",
            out_dir=SHIPS_DIR / "macros_raw",
        )
    ]


def ship_component_jobs() -> list[ExtractionJob]:
    """Ship component/model definition files -- one flat job, same reasoning
    as ship_macro_jobs() above.

    These are what a ship macro's own <component ref="..."/> points to (e.g.
    ship_bor_l_destroyer_01_a_macro -> ship_bor_l_destroyer_01), and define
    the actual hardpoints (engine/shield/weapon/turret connections). They
    live directly under assets/units/<folder>/ -- NOT the macros/ subfolder
    -- so the include pattern excludes any further path segments. Sorted
    into <class>_components/ by sort_ship_files_by_class() the same way,
    reading each file's own <component class="..."/> attribute (confirmed
    present and equal to its macro's own class for every real tracked ship,
    but read independently here rather than assumed/inherited, in case a
    mod's component and macro ever disagree).
    """
    return [
        ExtractionJob(
            name="ship_components",
            group="ship_components",
            include_pattern=r"assets/units/[^/]+/[^/]+\.xml$",
            out_dir=SHIPS_DIR / "components_raw",
        )
    ]


def sort_ship_files_by_class(raw_dir: Path, child_tag: str, suffix: str) -> None:
    """Sorts every XML file in `raw_dir` into SHIPS_DIR/<class>_<suffix>/,
    based on that file's own <macro class="..."/> or <component
    class="..."/> attribute (child_tag picks which) -- e.g. a macro with
    <macro class="ship_l"> lands in SHIPS_DIR/ship_l_macros/. This is the
    step that replaces "assume the class from which catalog folder the
    file came from" with "read the class the file itself actually
    declares" -- see ship_macro_jobs()/ship_component_jobs() above.

    Harmless by construction for the one real behavior change this causes:
    "size_xs" ships (spacesuits, escape pods, distress beacons, drop/repair
    drones, and a handful of NPC-only "pv"/police craft, none of them
    previously extracted at all) now get sorted into their own ship_xs_*
    folders alongside everything else -- confirmed via a direct wares.xml
    grep that no real <ware tags="ship"> references any of them, so this
    can't silently add new ships_base rows; it just means a real XS-class
    ship (base game or mod) would no longer need a pipeline code change to
    become visible, only a SHIP_CLASS_TO_SIZE_CODE entry in
    generate_ships_table.py.

    A file with no recognizable class (shouldn't happen for anything a
    real ExtractionJob's include_pattern already matched, but XML content
    isn't guaranteed by a path-based regex the way a path itself is) is
    left where it landed and warned about, rather than silently dropped.
    """
    if not raw_dir.exists():
        return
    counts: dict[str, int] = {}
    unclassified = 0
    for path in sorted(raw_dir.glob("*.xml")):
        root = ET.parse(path).getroot()
        child = root.find(child_tag)
        class_value = child.get("class") if child is not None else None
        if not class_value:
            print(f"  WARNING: {path.name} has no <{child_tag} class=\"...\"/> -- left unsorted in {raw_dir.name}")
            unclassified += 1
            continue
        dest_dir = SHIPS_DIR / f"{class_value}_{suffix}"
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest_dir / path.name)
        counts[class_value] = counts.get(class_value, 0) + 1
    summary = ", ".join(f"{cls}_{suffix} ({n})" for cls, n in sorted(counts.items()))
    print(f"  Sorted {sum(counts.values())} file(s) from {raw_dir.name}/ by class: {summary}")
    if unclassified:
        print(f"  ({unclassified} file(s) left unsorted -- see warnings above)")


# In-catalog folder each equipment type's macro/component files live under.
# Unlike ships (assets/units/size_X/...), these have no per-size subfolder --
# all sizes sit flat together, so size is only recoverable from the 3rd
# underscore-delimited token of the filename itself (e.g.
# "engine_arg_s_allround_01_mk1_macro.xml"). Weapons and turrets additionally
# share the same per-damage-class subfolders (WeaponSystems/energy/,
# WeaponSystems/dumbfire/, etc.), disambiguated only by filename prefix, so
# the subcategory segment is a wildcard.
#
# Deliberately out of scope: personal spacesuit/EVA equipment (e.g.
# "engine_gen_spacesuit_01_mk1_macro.xml", tagged "inventory"/
# "personalupgrade" in wares.xml) has no ship-size class at all, so its
# filename skips the size token these patterns require and it's silently
# not matched -- that's intentional, since it's personal gear, not ship
# equipment.
EQUIPMENT_TYPE_PATH_PREFIXES = {
    "engine": "assets/props/Engines",
    "shield": "assets/props/SurfaceElements",
    "weapon": "assets/props/WeaponSystems/[^/]+",
    "turret": "assets/props/WeaponSystems/[^/]+",
}


def equipment_macro_jobs() -> list[ExtractionJob]:
    """Engine/shield/weapon/turret macro files, one job per type + size class."""
    return [
        ExtractionJob(
            name=f"{equip_type}_macros_size_{size}",
            group=f"{equip_type}s",
            include_pattern=rf"{path_prefix}/macros/{equip_type}_[a-z]+_{size}_.*\.xml$",
            out_dir=DATA_DIR / f"{equip_type}s" / f"{equip_type}_{size}_macros",
        )
        for equip_type, path_prefix in EQUIPMENT_TYPE_PATH_PREFIXES.items()
        for size in SHIP_SIZES
    ]


def equipment_component_jobs() -> list[ExtractionJob]:
    """Engine/shield/weapon/turret component/model definition files, one job
    per type + size class.

    These are what an equipment macro's own <component ref="..."/> points
    to -- for engines/shields this is a shared generic model per size (e.g.
    "engine_gen_s_virtual_01"), for weapons/turrets it's a dedicated file
    per ware. They live directly under the type's folder (or, for weapons/
    turrets, the damage-class subfolder) -- NOT the macros/ subfolder -- so
    the include pattern excludes any further path segments.
    """
    return [
        ExtractionJob(
            name=f"{equip_type}_components_size_{size}",
            group=f"{equip_type}s",
            include_pattern=rf"{path_prefix}/{equip_type}_[a-z]+_{size}_[^/]*\.xml$",
            out_dir=DATA_DIR / f"{equip_type}s" / f"{equip_type}_{size}_components",
        )
        for equip_type, path_prefix in EQUIPMENT_TYPE_PATH_PREFIXES.items()
        for size in SHIP_SIZES
    ]


def missile_jobs() -> list[ExtractionJob]:
    """Missile macro files. Unlike engine/shield/weapon/turret, missiles
    aren't ship-mounted hardpoint equipment with a size/compatibility mount
    tag on a component file -- they're self-contained (their own <missile>/
    <explosiondamage>/<physics> stats live directly on the macro), and their
    in-catalog folder is dedicated to missiles only, so every file in it is
    pulled flat with no per-size split or filename-prefix filtering needed.
    """
    return [
        ExtractionJob(
            name="missile_macros",
            group="missiles",
            include_pattern=r"assets/props/WeaponSystems/missile/macros/.*\.xml$",
            out_dir=DATA_DIR / "missiles" / "macros",
        )
    ]


def deployable_jobs() -> list[ExtractionJob]:
    """Satellite/resource probe/mine/lasertower/navbeacon macro files. Like
    missiles, these are standalone deployables rather than ship-mounted
    equipment -- no size variants, no mount-tag compatibility.

    Satellites/probes/mines each live in their own dedicated in-catalog
    folder, so every file in each is pulled flat. Laser towers and the nav
    beacon don't get that luxury:

    - Laser towers (tags="equipment lasertower" in wares.xml) are filed as
      actual ships (assets/units/size_s|xs/macros/), not standalone
      equipment -- the "s" one already rides along with ship_macro_jobs(),
      but "xs" is invisible to this whole pipeline since SHIP_SIZES has no
      "xs" entry. Pulled explicitly here instead of widening SHIP_SIZES,
      since nothing else needs XS ships.
    - The nav beacon (ware "waypointmarker_01", tags="equipment navbeacon")
      lives under assets/environments/deco/macros/ alongside 9 other
      env_deco_nav_beacon_t*_macro.xml decoration variants (t2-t10) and a
      t1_mission variant -- none of which are wares (no wares.xml
      <component ref> points at them) -- so the pattern pins to exactly
      "t1_macro.xml" rather than pulling the whole folder.
    """
    return [
        ExtractionJob(
            name="satellite_macros",
            group="deployables",
            include_pattern=r"assets/props/Equipment/Satelite/macros/.*\.xml$",
            out_dir=DATA_DIR / "deployables" / "satellites",
        ),
        ExtractionJob(
            name="resourceprobe_macros",
            group="deployables",
            include_pattern=r"assets/props/Equipment/Probe/macros/.*\.xml$",
            out_dir=DATA_DIR / "deployables" / "probes",
        ),
        ExtractionJob(
            name="mine_macros",
            group="deployables",
            include_pattern=r"assets/props/WeaponSystems/mines/macros/.*\.xml$",
            out_dir=DATA_DIR / "deployables" / "mines",
        ),
        ExtractionJob(
            name="lasertower_macros",
            group="deployables",
            include_pattern=r"assets/units/size_x?s/macros/ship_gen_x?s_lasertower_01_a_macro\.xml$",
            out_dir=DATA_DIR / "deployables" / "lasertowers",
        ),
        ExtractionJob(
            name="navbeacon_macros",
            group="deployables",
            include_pattern=r"assets/environments/deco/macros/env_deco_nav_beacon_t1_macro\.xml$",
            out_dir=DATA_DIR / "deployables" / "navbeacons",
        ),
    ]


def ship_icon_jobs() -> list[ExtractionJob]:
    """Small ship-class icon textures -- one per size+purpose combo (e.g.
    "ship_s_fighter_01.gz"), referenced by name from each ship macro's own
    <identification icon="..."/> (see generate_ships_table.py, which
    captures that name into ships_base.icon). Pulled flat, unfiltered by
    size/type, since the whole folder is small (~70 files, a few KB each)
    and every entry in it is a genuine, currently-used ship-class icon --
    unlike ship/equipment macros there's no filename convention to filter
    on here anyway.

    Extracted as-is (still gzip-compressed DDS, XRCatTool does no format
    conversion) -- generate_ship_icons.py is the separate step that
    decompresses and converts these into web-displayable PNGs under
    data/images/ships/symbols/.
    """
    return [
        ExtractionJob(
            name="ship_icons",
            group="ship_icons",
            include_pattern=r"assets/textures/ui/shipicon/.*\.gz$",
            out_dir=DATA_DIR / "images" / "ships" / "symbols_raw",
        )
    ]


def faction_icon_jobs() -> list[ExtractionJob]:
    """Per-faction badge textures (assets/textures/ui/factions/
    faction_<name>_diffhq.gz), for the ship picker's manufacturer-race
    icon (see generate_ships_table.py's build_maker_race_rows() and
    generate_faction_icons.py).

    The game ships 38 of these (every minor/story faction included, e.g.
    "buccaneers"/"holyorder"/"scaleplate"), but this app only ever displays
    a ship's own *design race* (SHIP_RACE_PREFIX_TO_FACTION in
    generate_ships_table.py -- argon/boron/paranid/split/teladi/terran/
    xenon/khaak/yaki), matching src/static/app.js's own FACTION_COLORS --
    so unlike ship_icon_jobs() this pattern is deliberately narrowed to
    just those 9 real races rather than pulling the whole folder
    unfiltered. "neutral" (the pseudo-faction gen/pir hulls map to) has no
    real in-game texture and is correctly absent here.
    """
    return [
        ExtractionJob(
            name="faction_icons",
            group="faction_icons",
            include_pattern=(
                r"assets/textures/ui/factions/faction_"
                r"(argon|boron|paranid|split|teladi|terran|xenon|khaak|yaki)_diffhq\.gz$"
            ),
            out_dir=DATA_DIR / "images" / "factions_raw",
        )
    ]


def minor_faction_icon_jobs() -> list[ExtractionJob]:
    """The same assets/textures/ui/factions/faction_<name>_diffhq.gz badge
    textures faction_icon_jobs() pulls the 9 major races from, but for the
    *minor* factions that actually appear in ships_base.owners (the ship's
    sales list, e.g. "buccaneers"/"hatikvah"/"scaleplate" alongside the
    major race that actually designed the hull) -- one icon per owner
    faction shown in the ship picker, not just the design race. A separate
    job/group from faction_icon_jobs() (own raw output dir, own group name)
    so the major pipeline stays completely untouched -- see
    generate_minor_faction_icons.py, which tints each of these using its
    own real in-game UI color from libraries/colors.xml (colors_xml_job()
    below) rather than a hand-picked one.

    This list is every faction name in ships_base.owners across the whole
    ship dataset, minus the 9 majors already covered -- confirmed present
    both here (real texture files) and in colors.xml (real faction_<name>
    color mappings) before being added to this list; a future new owner
    faction showing up in the game data would need both re-checked and
    added here explicitly, not auto-discovered.
    """
    minor_names = (
        "alliance|antigone|buccaneers|court|freesplit|hatikvah|holyorder|kaori"
        "|loanshark|ministry|ownerless|pioneers|player|scaleplate|scavenger|trinity"
    )
    return [
        ExtractionJob(
            name="minor_faction_icons",
            group="minor_faction_icons",
            include_pattern=rf"assets/textures/ui/factions/faction_({minor_names})_diffhq\.gz$",
            out_dir=DATA_DIR / "images" / "factions_minor_raw",
        )
    ]


def colors_xml_job() -> list[ExtractionJob]:
    """libraries/colors.xml -- the game's own UI color palette, including a
    <mapping id="faction_<name>" ref="<color id>"/> for every real faction
    (major and minor alike) resolving to a base <color r="" g="" b=""/>
    entry elsewhere in the same file. Used by
    generate_minor_faction_icons.py to tint each minor faction's badge with
    its own real in-game color -- see minor_faction_icon_jobs() above.

    Unlike wares.xml, this isn't diff-patched per extension -- pulling it
    from the combined base-game-plus-every-extension catalog list (the
    default `in_paths`) already returns the fully-patched result in one
    file (confirmed: DLC-only factions like "kaori"/"court"/"freesplit" are
    present), so this is one plain job, not one per extension.
    """
    return [
        ExtractionJob(
            name="colors_xml",
            group="colors_xml",
            include_pattern=r"libraries/colors\.xml$",
            out_dir=DATA_DIR / "libraries",
        )
    ]


def races_xml_job() -> list[ExtractionJob]:
    """libraries/races.xml -- the game's own race definitions: id plus
    name/shortname="{page,id}" language refs, one <race> per real race the
    game itself recognizes (argon/boron/split/paranid/teladi/terran/xenon/
    khaak/drone). Used by generate_ships_table.py's parse_races() for each
    race's own display name and short in-game callsign (e.g. "ARG" for
    Argon) -- see that module's "Design race and race/faction shortcodes"
    docstring section. A ship/turret/engine/shield/weapon's own design
    race itself is read directly off its macro's own makerrace attribute
    (build_maker_race_rows()), not derived from this table at all.

    Base-game-only, single file -- confirmed the same way colors.xml/
    purposes.xml/the language files were: extracting each installed
    extension's own catalogs individually finds none of them ship a
    races.xml of their own.
    """
    return [
        ExtractionJob(
            name="races_xml",
            group="races_xml",
            include_pattern=r"libraries/races\.xml$",
            out_dir=DATA_DIR / "libraries",
        )
    ]


def purposes_xml_job() -> list[ExtractionJob]:
    """libraries/purposes.xml -- the game's own ship/station purpose
    category definitions (id + name="{page,id}" display-name ref -- see
    generate_ships_table.py's parse_purposes()), for real localized Purpose
    filter labels instead of the raw internal code (ships_base.purpose,
    e.g. "dismantling") capitalized client-side with no actual translation
    behind it.

    Base-game-only, single file -- confirmed by extracting each installed
    extension's own catalogs individually and finding none of them ship a
    purposes.xml of their own at all, same situation as colors.xml/the
    language files -- so this is one plain job, not one per extension.
    """
    return [
        ExtractionJob(
            name="purposes_xml",
            group="purposes_xml",
            include_pattern=r"libraries/purposes\.xml$",
            out_dir=DATA_DIR / "libraries",
        )
    ]


# X4's language ids are international phone country codes, zero-padded to
# 3 digits in the actual in-catalog filename (t/0001-l<id>.xml) -- e.g. 44
# (UK) = English, 49 (Germany) = German. See generate_ships_table.py's
# LANGUAGE_FILES for the language-code -> filename mapping this must stay
# in sync with (that's the one other place a new language needs adding).
LANGUAGE_IDS = ["044", "049", "034", "033", "039", "055", "042", "048", "007", "380", "086", "082", "081", "359", "090"]


def language_jobs() -> list[ExtractionJob]:
    """The game's own text/language files (t/0001-l<id>.xml) -- id/page-keyed
    strings, resolved via load_language_table()/resolve_ref_attr() in
    generate_ships_table.py for every ship/ware/equipment name (and, for a
    non-English language, into the localized_strings DB table -- see
    parse_localized_strings() there).

    Base-game-only, unlike wares.xml/factions.xml/colors.xml -- confirmed
    by extracting each installed extension's own catalogs individually and
    finding that none of them ship a t/0001-l*.xml of their own at all;
    the base game's single copy of each language file already contains
    every installed DLC's own strings too (Egosoft manages localization
    centrally across the whole product line, not per-DLC -- unlike
    wares.xml, where each DLC genuinely does patch in its own new
    content). This is also why data/names/0001-l044.xml already worked
    correctly for every DLC ship's name even before this job existed --
    it was pulled once by hand from the base game only, which turns out to
    have always been sufficient.
    """
    return [
        ExtractionJob(
            name=f"language_l{lang_id}",
            group="languages",
            include_pattern=rf"t/0001-l{lang_id}\.xml$",
            out_dir=DATA_DIR / "names",
            in_paths=catalog_files(GAME_ROOT),
        )
        for lang_id in LANGUAGE_IDS
    ]


def nav_icon_jobs() -> list[ExtractionJob]:
    """Three station-type icons *as they actually appear on the map*
    (assets/textures/ui/map_objects/mapob_<type>.gz), not the plain glyph
    set under stationicon/ favicon_icon_jobs() uses -- each mapob_ texture
    already has the hexagon badge baked in (black hex fill, white glyph +
    border), unlike si_shipyard.gz which is just the bare glyph. Used for
    this website's own top-nav page icons (Fleet Planner/Cost Analysis/
    About -- see generate_nav_icons.py, which recolors the black fill to
    the game's own "faction_player" green from libraries/colors.xml
    instead of shipping it black).

    Also pulls widget/bordersquare.gz, the game's own generic "this map
    item is selected" white square-bracket frame (see libraries/colors.xml's
    holomap_selection_bracket/holomap_selected mappings, both plain white)
    -- reused by generate_nav_icons.py for the Fleet Lists tab bar's
    selected-fleet indicator, the same role it plays around a selected
    object on the in-game map.
    """
    return [
        ExtractionJob(
            name="nav_icons",
            group="nav_icons",
            include_pattern=r"assets/textures/ui/map_objects/mapob_(shipyard|tradestation|equipmentdock)\.gz$",
            out_dir=DATA_DIR / "images" / "nav_icons_raw",
        ),
        ExtractionJob(
            name="selection_box_icon",
            group="nav_icons",
            include_pattern=r"assets/textures/ui/widget/bordersquare\.gz$",
            out_dir=DATA_DIR / "images" / "nav_icons_raw",
        ),
    ]


def favicon_icon_jobs() -> list[ExtractionJob]:
    """The shipyard station-type icon (si_shipyard.gz), from the game's own
    per-station-type icon set under assets/textures/ui/stationicon/ --
    parallel to shipicon/'s per-ship-class icons (see ship_icon_jobs()),
    just for station types instead of ship classes. Used as this
    website's own favicon -- a shipyard is where ships get built, a
    fitting symbol for a ship-building/procurement planner.

    Only this one file, not the whole stationicon/ folder -- unlike
    ship_icon_jobs() (which needs every ship-class icon, since this app
    displays all of them somewhere), nothing else in this app has any use
    for station-type icons; si_wharf/si_equipmentdock/si_factory/etc. are
    all left alone.
    """
    return [
        ExtractionJob(
            name="favicon_icon",
            group="favicon",
            include_pattern=r"assets/textures/ui/stationicon/si_shipyard\.gz$",
            out_dir=DATA_DIR / "images" / "favicon_raw",
        )
    ]


def extension_suffix(ext_dir: Path) -> str:
    return EXTENSION_SUFFIXES.get(ext_dir.name, ext_dir.name.removeprefix("ego_dlc_"))


def wares_xml_jobs() -> list[ExtractionJob]:
    """libraries/wares.xml from the base game and each extension.

    Every source uses the same in-catalog filename, and each extension's
    copy is a diff-patch (not a full ware list), so each source must be
    extracted separately and renamed rather than combined into one job.
    """
    jobs = [
        ExtractionJob(
            name="wares_base",
            group="wares",
            include_pattern=r"libraries/wares\.xml",
            out_dir=DATA_DIR / "libraries",
            in_paths=catalog_files(GAME_ROOT),
            dest_name="wares.xml",
        )
    ]
    for ext_dir in extension_dirs():
        suffix = extension_suffix(ext_dir)
        jobs.append(
            ExtractionJob(
                name=f"wares_{suffix}",
                group="wares",
                include_pattern=r"libraries/wares\.xml",
                out_dir=DATA_DIR / "libraries",
                in_paths=catalog_files(ext_dir),
                dest_name=f"wares_{suffix}.xml",
            )
        )
    return jobs


def factions_xml_jobs() -> list[ExtractionJob]:
    """libraries/factions.xml from the base game and each extension -- the
    game's own faction *definitions* (id, name="{page,id}" display-name
    ref, primary race, etc.), for the factions DB table backing the ship
    picker's owner-faction icon tooltips (see generate_ships_table.py's
    parse_factions()) and a planned owner-faction filter group.

    Diff-patched per extension exactly like wares.xml above (each DLC's own
    factions.xml is a <diff> that <add sel="/factions">-appends its own new
    <faction> entries, not a full list) -- same reasoning, same per-source
    job-per-extension shape. Two of the seven extensions (ego_dlc_mini_01/
    mini_02) don't actually ship a factions.xml at all -- like
    wares_xml_jobs(), this doesn't special-case that; their own job here
    just extracts 0 files (run_job()'s own "0 files matched" warning is
    accurate and harmless), and generate_ships_table.py's factions_files()
    simply never finds a factions_mini01.xml/factions_mini02.xml to read.
    """
    jobs = [
        ExtractionJob(
            name="factions_base",
            group="factions",
            include_pattern=r"libraries/factions\.xml",
            out_dir=DATA_DIR / "libraries",
            in_paths=catalog_files(GAME_ROOT),
            dest_name="factions.xml",
        )
    ]
    for ext_dir in extension_dirs():
        suffix = extension_suffix(ext_dir)
        jobs.append(
            ExtractionJob(
                name=f"factions_{suffix}",
                group="factions",
                include_pattern=r"libraries/factions\.xml",
                out_dir=DATA_DIR / "libraries",
                in_paths=catalog_files(ext_dir),
                dest_name=f"factions_{suffix}.xml",
            )
        )
    return jobs


EXTRACTION_JOBS: list[ExtractionJob] = [
    *ship_macro_jobs(),
    *ship_component_jobs(),
    *equipment_macro_jobs(),
    *equipment_component_jobs(),
    *missile_jobs(),
    *deployable_jobs(),
    *wares_xml_jobs(),
    *factions_xml_jobs(),
    *ship_icon_jobs(),
    *favicon_icon_jobs(),
    *nav_icon_jobs(),
    *faction_icon_jobs(),
    *minor_faction_icon_jobs(),
    *colors_xml_job(),
    *purposes_xml_job(),
    *races_xml_job(),
    *language_jobs(),
]


def run_job(job: ExtractionJob, default_in_paths: list[str]) -> None:
    in_paths = job.in_paths if job.in_paths is not None else default_in_paths
    job.out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[{job.name}] {job.include_pattern} -> {job.out_dir.relative_to(ROOT)}")

    with tempfile.TemporaryDirectory(prefix="xrcattool_") as staging:
        cmd = [
            str(XRCATTOOL_EXE),
            "-in",
            *in_paths,
            "-out",
            staging,
            "-include",
            job.include_pattern,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(result.stderr)
            raise RuntimeError(f"XRCatTool failed for job '{job.name}' (exit {result.returncode})")

        extracted_files = [p for p in Path(staging).rglob("*") if p.is_file()]
        if job.dest_name and len(extracted_files) > 1:
            print(
                f"  WARNING: dest_name='{job.dest_name}' set but {len(extracted_files)} "
                "files matched; only the last one copied will survive"
            )
        for src in extracted_files:
            shutil.copy2(src, job.out_dir / (job.dest_name or src.name))

    if not extracted_files:
        print("  WARNING: 0 files matched -- check the include pattern")
    total = sum(1 for _ in job.out_dir.iterdir())
    print(f"  -> {len(extracted_files)} extracted this run, {total} total in folder")


def parse_args() -> argparse.Namespace:
    groups = sorted({job.group for job in EXTRACTION_JOBS})
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only",
        nargs="+",
        metavar="GROUP",
        choices=groups,
        help=f"Only run these extraction groups (default: all). Choices: {', '.join(groups)}",
    )
    parser.add_argument(
        "--skip",
        nargs="+",
        metavar="GROUP",
        choices=groups,
        default=[],
        help=f"Skip these extraction groups. Choices: {', '.join(groups)}",
    )
    parser.add_argument(
        "--list-groups",
        action="store_true",
        help="List available extraction groups and their jobs, then exit",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.list_groups:
        for group in sorted({job.group for job in EXTRACTION_JOBS}):
            job_names = [job.name for job in EXTRACTION_JOBS if job.group == group]
            print(f"{group}: {', '.join(job_names)}")
        return

    if not XRCATTOOL_EXE.exists():
        raise FileNotFoundError(f"XRCatTool.exe not found at {XRCATTOOL_EXE}")
    if not GAME_ROOT.exists():
        raise FileNotFoundError(f"Game install not found at {GAME_ROOT}")

    copy_metadata_files()

    jobs = EXTRACTION_JOBS
    if args.only:
        jobs = [job for job in jobs if job.group in args.only]
    jobs = [job for job in jobs if job.group not in args.skip]

    if not jobs:
        print("No extraction jobs selected (check --only / --skip).")
        return

    in_paths = game_input_paths()
    print(f"Input catalogs: {len(in_paths)} (base game + {len(extension_dirs())} extensions)")
    print(f"Running groups: {', '.join(sorted({job.group for job in jobs}))}")
    print()

    for job in jobs:
        run_job(job, in_paths)

    # Post-processing, not another ExtractionJob: XRCatTool only matches on
    # catalog path, it can't sort by a file's own XML content -- see
    # sort_ship_files_by_class()'s own docstring. Gated on which groups
    # actually ran this invocation so `--only <unrelated-group>` doesn't
    # re-sort stale macros_raw/components_raw leftovers from a previous run.
    ran_groups = {job.group for job in jobs}
    if "ships" in ran_groups:
        print("[sort_ship_macros_by_class]")
        sort_ship_files_by_class(SHIPS_DIR / "macros_raw", "macro", "macros")
    if "ship_components" in ran_groups:
        print("[sort_ship_components_by_class]")
        sort_ship_files_by_class(SHIPS_DIR / "components_raw", "component", "components")


if __name__ == "__main__":
    main()
