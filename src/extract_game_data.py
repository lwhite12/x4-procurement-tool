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
(assets/units/size_X/...), so each size class is its own job with a plain
path-segment include pattern. Equipment (engine/shield/weapon/turret) files
have no such subfolder -- all sizes sit flat together under a per-type
folder (assets/props/Engines/, assets/props/SurfaceElements/, or, for
weapons/turrets which share the same per-damage-class subfolders, assets/
props/WeaponSystems/<class>/) -- so their jobs instead match the size token
embedded in the filename itself (e.g. "engine_arg_s_..."). See
EQUIPMENT_TYPE_PATH_PREFIXES.

To add a new extraction (e.g. language files, ware macros), append an
ExtractionJob to EXTRACTION_JOBS under a suitable group name.

Every file this script writes is fully reproducible from the game install,
so groups can be freely skipped or deleted and regenerated later with no
data-loss concern (see --only / --skip).
"""

import argparse
import shutil
import subprocess
import tempfile
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


def game_input_paths() -> list[str]:
    """Catalog files for the base game plus every installed extension."""
    paths = catalog_files(GAME_ROOT)
    for ext_dir in extension_dirs():
        paths.extend(catalog_files(ext_dir))
    return paths


def ship_macro_jobs() -> list[ExtractionJob]:
    """Ship hull, cockpit, and per-ship storage/cargo macros, one job per size class."""
    return [
        ExtractionJob(
            name=f"ship_macros_size_{size}",
            group="ships",
            include_pattern=rf"assets/units/size_{size}/macros/.*\.xml",
            out_dir=SHIPS_DIR / f"size_{size}_macros",
        )
        for size in SHIP_SIZES
    ]


def ship_component_jobs() -> list[ExtractionJob]:
    """Ship component/model definition files, one job per size class.

    These are what a ship macro's own <component ref="..."/> points to (e.g.
    ship_bor_l_destroyer_01_a_macro -> ship_bor_l_destroyer_01), and define
    the actual hardpoints (engine/shield/weapon/turret connections). They
    live directly under assets/units/size_X/ -- NOT the macros/ subfolder --
    so the include pattern excludes any further path segments.
    """
    return [
        ExtractionJob(
            name=f"ship_components_size_{size}",
            group="ship_components",
            include_pattern=rf"assets/units/size_{size}/[^/]+\.xml$",
            out_dir=SHIPS_DIR / f"size_{size}_components",
        )
        for size in SHIP_SIZES
    ]


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


EXTRACTION_JOBS: list[ExtractionJob] = [
    *ship_macro_jobs(),
    *ship_component_jobs(),
    *equipment_macro_jobs(),
    *equipment_component_jobs(),
    *missile_jobs(),
    *deployable_jobs(),
    *wares_xml_jobs(),
    *ship_icon_jobs(),
    *favicon_icon_jobs(),
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


if __name__ == "__main__":
    main()
