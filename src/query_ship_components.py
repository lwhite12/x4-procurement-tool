"""Query the possible equipment components for a list of ships, broken down
by component type: engines, shields, weapons, missile_launchers, turrets,
thrusters, software.

Input: JSON (a file path argument, or "-" to read from stdin), shaped like:
{
  "ships": ["Barracuda", "ship_tel_l_trans_container_03_a"]
}
Each entry is tried first as a ware_id (ships_base.ware_id), then as a
resolved display name (ships_base.name).

For each ship, every hardpoint group in ship_component_groups is matched
against the corresponding equipment table (engines_base/shields_base/
weapons_base/turrets_base/thrusters_base) by size, then by a tag-set
*subset* test rather than an equality/membership test: both a group's
equipment_compatibility_class and an equipment row's own `compatibility`
are comma-joined sets of the raw <connection tags="..."/> tokens from the
game's own XML (see generate_ships_table.py's parse_component_slots/
parse_equipment_mount), and an equipment item is a valid option for a
group only when *every* tag in the equipment's own set is also present in
the group's set -- the equipment may not require anything the group
doesn't offer, but the group is allowed to offer more than the equipment
needs (see matching_items()'s own docstring for why this direction, not
the other way, and for the real cases -- destroyer main guns, mining ship
weapon mounts -- that motivated it). If a group has no recorded
compatibility class at all, it contributes no matches rather than
guessing broadly. Separately, mount-tag compatibility alone is not enough
to keep Xenon/Kha'ak-exclusive equipment off ordinary ships -- roughly
half of it carries no faction-exclusivity tag on its mount connection at
all, physically indistinguishable from ordinary equipment of the same
tier -- so matching_items() also takes whether the querying ship is itself
HOSTILE_ONLY_FACTIONS-owned (see is_hostile_only_ware()) and separately
excludes any equipment owned by a HOSTILE_ONLY_FACTIONS faction unless the
ship being queried is that same faction. The "thruster" group is one
exception: every ship's ship_component_groups row for it carries the
synthetic "universal" class (see generate_ships_table.py's
THRUSTER_COMPATIBILITY), since thrusters have no real per-ware faction/
tier lock in the game data -- every thruster of the matching size matches
every ship's thruster group (a trivial one-element-set-subset-of-itself
case of the same general rule).

"software" groups are matched completely differently -- there's no size or
compatibility-class concept for software at all (see
generate_ships_table.py's "Software" docstring section), only an explicit
per-ship list of exactly which software ware_ids that ship accepts.
equipment_compatibility_class holds that comma-joined ware_id list directly
(not shared tier tokens), and matching_items() matches by ware_id
membership against software_base rather than the (size, compatibility)
query used for every other type.

group_name is NOT unique per ship in ship_component_groups: a dedicated
medium shield protecting a specific engine/turret/weapon group shares that
group's own raw group_name, distinguished only by component_type =
"shield" (see generate_ships_table.py's parse_component_slots docstring).
query_ship()'s flat view excludes these linked shields from its "shields"
bucket (they're a different, fixed size tied to one specific group, not a
general-purpose ship shield slot) -- a shield group only lands in
"shields" when its group_name isn't also used by any non-shield group on
the same ship. query_ship_groups() surfaces them properly instead, joined
to their sibling group by the shared group_name.

Turrets keep a single "turret" component_type in ship_component_groups even
for missile-capable turret variants (one physical mount can take either),
so turret matching does not split on the missile_launcher flag. Weapons
and missile launchers, by contrast, are genuinely separate hardpoints on
the ship side, so weapons_base is filtered by its own missile_launcher
flag to keep the "weapons" and "missile_launchers" buckets clean -- a
dedicated missile launcher never appears in "weapons", and vice versa.

Output (via main(), the CLI entry point): one entry per input identifier,
each either
  {"input": ..., "error": "ship not found"}
or
  {"input": ..., "name": ..., "ware_id": ...,
   "components": {"engines": [...], "shields": [...], "weapons": [...],
                   "missile_launchers": [...], "turrets": [...],
                   "thrusters": [...], "software": [...]}}
Each component list is a flat, deduplicated, name-sorted list of
{"ware_id", "name", "size", "compatibility", "ammunition_tags",
"ammunition_capacity", "price_min", "price_avg", "price_max"} gathered
across all of that ship's groups of that type -- ammunition_tags/
ammunition_capacity are only ever non-null for missile-capable turrets/
weapons (see generate_ships_table.py's "Missiles and deployables" docstring
section); every other item has them as null for a consistent shape.
"software" items carry one extra field, "mk", not present on any other
type -- a software ware's display name doesn't reliably encode its tier
the way most equipment's own "... Mk1"/"Mk2" naming does, so this is the
one authoritative source for "which of this slot's options is the best/
worst" (see app.js's software preset buttons).

query_ship_groups() is a sibling entry point (used by src/api.py, not
exposed on the CLI) for callers that need per-*group* structure instead --
e.g. a UI picker, where two groups of the same component_type can
legitimately have different sizes/compatibility classes and so must not be
merged the way query_ship()'s flat view merges them. See its own
docstring for the shape it returns.
"""

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "x4.db"

# Factions that own real, real-priced equipment wares (so they're not
# filtered out as orphan/mission-only macros -- see
# generate_ships_table.py's filter_to_real_equipment_wares) but that a
# player can never actually buy or crew a ship for -- Xenon and Kha'ak are
# both purely hostile, not a real playable/ownable faction. Their equipment
# is not reliably excluded by the mount-tag subset check alone: roughly
# half of it (verified directly against the game's own component XML) has
# a mount connection tagged just "standard" with no "xenon"/"khaak"
# exclusivity tag at all, so it would otherwise show up as an ordinary
# option on any ship with a matching standard-tier slot. This is an
# entirely separate axis from mount-tag compatibility -- it's about who's
# allowed to own/buy the ware, not whether it physically fits -- so it's
# applied as its own filter in matching_items(), not folded into the tag
# comparison. Ships owned by one of these factions (a few appear in
# ships_base for comparison purposes even though a player can't fly one)
# still see their own faction's equipment -- see is_hostile_only_ware().
HOSTILE_ONLY_FACTIONS = {"xenon", "khaak"}

# Narrow, last-resort fallback for is_hostile_only_ware() below -- only
# used when the real maker_races table (see load_maker_races()) has no row
# at all for a given ware_id. Only the prefixes relevant to
# HOSTILE_ONLY_FACTIONS are mapped, since that's the only thing this
# fallback is for -- not a general race-mapping utility (see
# generate_ships_table.py's SHIP_CLASS_TO_SIZE_CODE/build_maker_race_rows()
# for the real, current one of those).
WARE_ID_RACE_PREFIXES = {
    "xen": "xenon",
    "kha": "khaak",
}


def load_maker_races(conn: sqlite3.Connection) -> dict[str, set[str]]:
    """{ware_id -> set(race_id)}, built once from the real maker_races
    table (see generate_ships_table.py's "Design race and race/faction
    shortcodes" docstring section -- the same golden-source design-race
    data every other part of this app now uses, replacing the ware_id-
    prefix guess this module used to make its own separate copy of).
    Covers ships and turrets/engines/shields/weapons; thrusters/missiles/
    software/deployables have no makerrace concept in the game's own data
    at all, and simply have no entry here -- same as is_hostile_only_ware()'s
    own fallback case for the handful of equipment items whose own macro
    has no <properties> block to read a makerrace from.
    """
    result: dict[str, set[str]] = {}
    for row in conn.execute("SELECT ware_id, race_id FROM maker_races").fetchall():
        result.setdefault(row["ware_id"], set()).add(row["race_id"])
    return result


def is_hostile_only_ware(ware_id: str, maker_races: dict[str, set[str]]) -> bool:
    """True if `ware_id` (a ship or equipment ware) is owned by a
    HOSTILE_ONLY_FACTIONS race (xenon/khaak) -- checked against the real
    maker_races table first (see load_maker_races()), falling back to the
    ware_id's own naming convention (<kind>_<race>_...) only when
    maker_races has no row for it at all.

    That fallback isn't just theoretical caution: shield_xen_m_standard_02_
    mk1 is a confirmed real case -- it's an alias macro
    (<macro alias="shield_xen_m_standard_04_mk1_macro" .../>) with no
    <properties> block of its own at all, so generate_ships_table.py never
    captures a makerrace for it (macro-alias inheritance is deliberately
    not resolved there -- see parse_equipment_component_wares()'s own
    docstring), even though it's unambiguously Xenon equipment by its own
    ware_id and carries no faction-exclusivity tag on its mount connection
    either (compatibility="standard", not "xenon"). Without this fallback,
    exactly this kind of ware would silently stop being recognized as
    Xenon-owned and start appearing as an ordinary option on non-Xenon
    ships, defeating the whole point of this check.
    """
    races = maker_races.get(ware_id)
    if races is not None:
        return bool(races & HOSTILE_ONLY_FACTIONS)
    match = re.match(r"^[a-z]+_([a-z]+)_", ware_id)
    return bool(match and WARE_ID_RACE_PREFIXES.get(match.group(1)) in HOSTILE_ONLY_FACTIONS)


COMPONENT_TYPE_TABLES = {
    "engine": "engines_base",
    "shield": "shields_base",
    "turret": "turrets_base",
    "weapon": "weapons_base",
    "missile_launcher": "weapons_base",
    "thruster": "thrusters_base",
    "software": "software_base",
}
COMPONENT_TYPE_TO_BUCKET = {
    "engine": "engines",
    "shield": "shields",
    "turret": "turrets",
    "weapon": "weapons",
    "missile_launcher": "missile_launchers",
    "thruster": "thrusters",
    "software": "software",
}


def load_input(source: str) -> dict:
    text = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
    return json.loads(text)


def resolve_ship(conn: sqlite3.Connection, identifier: str, lang: str = "en") -> sqlite3.Row | None:
    """`identifier` can be a ware_id or a display name (the CLI accepts
    either) -- the name lookup always matches against ships_base's own
    base English name column regardless of `lang` (a CLI user typing a
    name would type the English one), only the *returned* "name" field is
    localized, via the same COALESCE-against-localized_strings pattern
    GET /api/ships uses.
    """
    row = conn.execute(
        """
        SELECT
            COALESCE(localized_strings.text, ships_base.name) AS name,
            ships_base.ware_id AS ware_id,
            ships_base.icon AS icon,
            ships_base.production_method AS production_method
        FROM ships_base
        LEFT JOIN localized_strings
            ON localized_strings.ware_id = ships_base.ware_id AND localized_strings.lang_id = ?
        WHERE ships_base.ware_id = ?
        """,
        (lang, identifier),
    ).fetchone()
    if row is not None:
        return row
    return conn.execute(
        """
        SELECT
            COALESCE(localized_strings.text, ships_base.name) AS name,
            ships_base.ware_id AS ware_id,
            ships_base.icon AS icon,
            ships_base.production_method AS production_method
        FROM ships_base
        LEFT JOIN localized_strings
            ON localized_strings.ware_id = ships_base.ware_id AND localized_strings.lang_id = ?
        WHERE ships_base.name = ?
        """,
        (lang, identifier),
    ).fetchone()


def fetch_groups(conn: sqlite3.Connection, ship_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT group_name, component_type, size, slot_count, equipment_compatibility_class, connection_names
        FROM ship_component_groups
        WHERE ship_id = ?
        """,
        (ship_id,),
    ).fetchall()


def matching_items(
    conn: sqlite3.Connection,
    component_type: str,
    size: str,
    compat_class: str | None,
    maker_races: dict[str, set[str]],
    ship_is_hostile: bool = False,
    lang: str = "en",
) -> list[dict]:
    """Every equipment_wares_base-joined row from the type's table matching
    this group's size, whose own compatibility tag set is a *subset* of
    this group's (comma-joined) compat_class tag set -- see the module
    docstring for why the match direction is equipment-subset-of-group
    rather than an equality/membership test. An unset compat_class yields
    no matches -- see the module docstring for why.

    `ship_is_hostile` (whether the querying ship itself is
    HOSTILE_ONLY_FACTIONS-owned -- see is_hostile_only_ware()) gates an
    additional exclusion of equipment identified the same way as hostile-
    owned, unless the ship being queried is itself that same faction -- a
    separate ownership/licensing check, not part of the tag-subset mount
    compatibility above (see HOSTILE_ONLY_FACTIONS' own comment for why
    this can't be folded into the tag comparison). A no-op for thrusters
    and any other race's equipment (is_hostile_only_ware() is false for
    both), and for software (handled entirely separately below, never
    faction-locked).

    "software" is the one component_type that doesn't fit this (size,
    compatibility-tags) shape at all -- there's no mount/size/tier concept
    for software, only an explicit per-ship list of exactly which ware_ids
    are allowed (see generate_ships_table.py's "Software" docstring
    section). For that type, compat_class is repurposed to hold a comma-
    joined list of specific ware_ids instead of shared tier tokens, matched
    by direct ware_id membership against software_base -- which also has
    no equipment_wares_base parent row to join against, unlike every other
    type here.
    """
    if not compat_class:
        return []

    if component_type == "software":
        ware_ids = compat_class.split(",")
        placeholders = ", ".join("?" for _ in ware_ids)
        query = f"""
            SELECT
                software_base.ware_id AS ware_id,
                COALESCE(localized_strings.text, software_base.name) AS name,
                software_base.mk AS mk,
                software_base.price_min AS price_min,
                software_base.price_avg AS price_avg,
                software_base.price_max AS price_max
            FROM software_base
            LEFT JOIN localized_strings
                ON localized_strings.ware_id = software_base.ware_id AND localized_strings.lang_id = ?
            WHERE software_base.ware_id IN ({placeholders})
        """
        return [
            {
                "ware_id": row["ware_id"],
                "name": row["name"],
                "size": None,
                "compatibility": None,
                "ammunition_tags": None,
                "ammunition_capacity": None,
                # A software ware's display name doesn't reliably encode its
                # tier the way most equipment's "... Mk1"/"Mk2" naming does
                # (e.g. software_scannerobjectmk1/mk2 are named "Basic
                # Scanner"/"Police Scanner") -- `mk` is the one authoritative
                # tier indicator, used by app.js's High/Minimum software
                # preset buttons to pick the best/worst option in each slot
                # rather than assuming array or name order reflects tier.
                "mk": row["mk"],
                "price_min": row["price_min"],
                "price_avg": row["price_avg"],
                "price_max": row["price_max"],
            }
            for row in conn.execute(query, [lang, *ware_ids]).fetchall()
        ]

    table = COMPONENT_TYPE_TABLES[component_type]
    group_tags = set(compat_class.split(","))

    missile_filter = ""
    if component_type == "weapon":
        missile_filter = "AND ew.missile_launcher = 0"
    elif component_type == "missile_launcher":
        missile_filter = "AND ew.missile_launcher = 1"

    # turrets_base/weapons_base are the only tables with ammunition_tags/
    # ammunition_capacity (missile-capable turrets/weapons only -- see
    # generate_ships_table.py's "Missiles and deployables" docstring
    # section); every other type's table has neither column, so those
    # fields are just filled in as None below for a consistent option
    # shape regardless of component_type.
    has_ammo_columns = table in ("turrets_base", "weapons_base")
    ammo_select = ", t.ammunition_tags, t.ammunition_capacity" if has_ammo_columns else ""

    # Every size-matching row is fetched and then filtered in Python by the
    # subset test -- SQL has no clean way to express "this row's own
    # comma-joined tag set is a subset of that other set" as a WHERE
    # clause, and the per-size row count here is small (at most a few
    # hundred) so there's no real cost to doing it this way.
    query = f"""
        SELECT
            ew.ware_id AS ware_id,
            COALESCE(localized_strings.text, ew.name) AS name,
            t.size AS size,
            t.compatibility AS compatibility,
            ew.price_min AS price_min,
            ew.price_avg AS price_avg,
            ew.price_max AS price_max{ammo_select}
        FROM {table} t
        JOIN equipment_wares_base ew ON ew.ware_id = t.ware_id
        LEFT JOIN localized_strings
            ON localized_strings.ware_id = ew.ware_id AND localized_strings.lang_id = ?
        WHERE t.size = ? {missile_filter}
    """
    candidates = [dict(row) for row in conn.execute(query, [lang, size]).fetchall()]
    rows = [
        row
        for row in candidates
        if set(row["compatibility"].split(",") if row["compatibility"] else []) <= group_tags
    ]
    if not ship_is_hostile:
        rows = [row for row in rows if not is_hostile_only_ware(row["ware_id"], maker_races)]
    if not has_ammo_columns:
        for row in rows:
            row["ammunition_tags"] = None
            row["ammunition_capacity"] = None
    return rows


def query_ship(conn: sqlite3.Connection, identifier: str) -> dict:
    ship = resolve_ship(conn, identifier)
    if ship is None:
        return {"input": identifier, "error": "ship not found"}

    maker_races = load_maker_races(conn)
    ship_is_hostile = is_hostile_only_ware(ship["ware_id"], maker_races)
    all_groups = fetch_groups(conn, ship["ware_id"])
    types_by_group_name: dict[str, set[str]] = {}
    for group in all_groups:
        types_by_group_name.setdefault(group["group_name"], set()).add(group["component_type"])

    buckets: dict[str, dict[str, dict]] = {bucket: {} for bucket in COMPONENT_TYPE_TO_BUCKET.values()}
    for group in all_groups:
        if group["component_type"] == "shield" and len(types_by_group_name[group["group_name"]]) > 1:
            # This group_name is also used by a non-shield group on this
            # ship -- a dedicated shield protecting that other group, a
            # fundamentally different (fixed-size) slot than the ship's own
            # main shields, so it's excluded from this flat "shields"
            # catalog rather than silently mixing sizes into one merged
            # list. query_ship_groups() surfaces it properly instead.
            continue
        bucket_name = COMPONENT_TYPE_TO_BUCKET.get(group["component_type"])
        if bucket_name is None:
            continue
        for item in matching_items(
            conn,
            group["component_type"],
            group["size"],
            group["equipment_compatibility_class"],
            maker_races,
            ship_is_hostile,
        ):
            buckets[bucket_name][item["ware_id"]] = item

    return {
        "input": identifier,
        "name": ship["name"],
        "ware_id": ship["ware_id"],
        "components": {
            bucket: sorted(items.values(), key=lambda item: item["name"]) for bucket, items in buckets.items()
        },
    }


def query_ship_groups(conn: sqlite3.Connection, identifier: str, lang: str = "en") -> dict:
    """Like query_ship, but preserves per-group structure instead of
    flattening/deduplicating options across every group of the same
    component_type -- needed for a picker UI, since two groups of the same
    type can have different sizes/compatibility classes and so legitimately
    offer different options; merging them (as query_ship does) would be
    wrong here.

    "summary" is a small read-only readout (ship size, main shield count,
    bonus medium-shield count, missile ammo capacity, drone capacity, crew
    capacity, cargo capacity/type, S/M docks, S/M ship storage) pulled
    straight from ships_base -- it exists only for display, never to
    populate a picker's options (ships_base has no per-group size/
    compatibility info to do that correctly with). crew_capacity is
    ships_base.crew ("crew" is the summary key's own name since "crew"
    alone would collide with query_ship_groups()'s crew_base catalog
    concept on the frontend). There's no countermeasure_capacity here at
    all -- unlike crew, no ships_base column exists for it (see
    generate_ships_table.py's "Countermeasures and crew" docstring
    section); the frontend assumes a fixed default by ship size instead.
    cargo_type is untranslated raw tag text (e.g. "container", or
    "container solid" for a mixed hold) -- see generate_ships_table.py's
    parse_ship_docks() for what it means and GET /api/cargo_types for
    resolving it into real display names; the frontend splits and looks up
    each space-separated token itself, same reasoning as build_method_name
    staying untranslated on GET /api/build_methods (see that endpoint's
    own docstring) -- this is the real internal value, not something to
    bake a resolved display string into.

    A dedicated medium shield protecting a specific engine/turret group is
    its own group here too, with its own "options" the same as any other
    group -- but group_name is NOT unique in the returned "groups" list: it
    shares the exact same group_name as the engine/turret/weapon group it
    protects, distinguished only by component_type = "shield" (see
    parse_component_slots' docstring in generate_ships_table.py -- this
    mirrors the game's own XML "group" attribute directly, unrenamed).
    Callers that want to render a group's dedicated shields nested under it
    should group data.groups by group_name and pull out the "shield"
    entries. This is the *per-group* breakdown of that same
    ships_base.shields_bonus_m total: e.g. an L destroyer's four separate
    2-turret groups might each carry their own dedicated M shields (each
    independently pickable), and ships_base's flat total is just their
    summed slot counts.
    """
    ship = resolve_ship(conn, identifier, lang)
    if ship is None:
        return {"input": identifier, "error": "ship not found"}

    summary_row = conn.execute(
        """
        SELECT size, shields, shields_bonus_m, missile_capacity, drone_capacity, crew,
               cargo_capacity, cargo_type, s_docks, m_docks, s_ship_storage, m_ship_storage
        FROM ships_base WHERE ware_id = ?
        """,
        (ship["ware_id"],),
    ).fetchone()

    maker_races = load_maker_races(conn)
    ship_is_hostile = is_hostile_only_ware(ship["ware_id"], maker_races)
    groups = []
    for group in fetch_groups(conn, ship["ware_id"]):
        options = matching_items(
            conn,
            group["component_type"],
            group["size"],
            group["equipment_compatibility_class"],
            maker_races,
            ship_is_hostile,
            lang,
        )
        groups.append(
            {
                "group_name": group["group_name"],
                "component_type": group["component_type"],
                "size": group["size"],
                "slot_count": group["slot_count"],
                "compatibility": group["equipment_compatibility_class"],
                "connection_names": group["connection_names"],
                "options": sorted(options, key=lambda item: item["name"]),
            }
        )

    return {
        "input": identifier,
        "name": ship["name"],
        "ware_id": ship["ware_id"],
        "icon": ship["icon"],
        # This hull's own primary build method (ships_base.production_method
        # -- generate_ships_table.py's write_ships_csv() already picks one
        # canonical method per ship, "" when it has no production recipe at
        # all) -- the frontend uses this to seed a fresh fleet's build
        # method priority list when its first ship is added (see app.js's
        # addSelectedShipToCart()), not for anything display here.
        "production_method": ship["production_method"] or None,
        "summary": {
            "size": summary_row["size"] if summary_row is not None else None,
            "shields": summary_row["shields"] if summary_row is not None else None,
            "shields_bonus_m": summary_row["shields_bonus_m"] if summary_row is not None else None,
            "missile_capacity": summary_row["missile_capacity"] if summary_row is not None else None,
            "drone_capacity": summary_row["drone_capacity"] if summary_row is not None else None,
            "crew_capacity": summary_row["crew"] if summary_row is not None else None,
            "cargo_capacity": summary_row["cargo_capacity"] if summary_row is not None else None,
            "cargo_type": summary_row["cargo_type"] if summary_row is not None else None,
            "s_docks": summary_row["s_docks"] if summary_row is not None else None,
            "m_docks": summary_row["m_docks"] if summary_row is not None else None,
            "s_ship_storage": summary_row["s_ship_storage"] if summary_row is not None else None,
            "m_ship_storage": summary_row["m_ship_storage"] if summary_row is not None else None,
        },
        "groups": groups,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", help="Path to input JSON file, or '-' to read from stdin")
    args = parser.parse_args()

    payload = load_input(args.input)
    ship_identifiers = payload["ships"]

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        result = {"ships": [query_ship(conn, identifier) for identifier in ship_identifiers]}
    finally:
        conn.close()

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
