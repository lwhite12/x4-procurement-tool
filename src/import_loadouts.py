"""Parse a player's saved X4 ship loadouts (loadouts.xml, from the game's
own save-adjacent config folder -- typically
Documents\\Egosoft\\X4\\<id>\\loadouts.xml, NOT inside a savegame itself)
into this app's own cart-entry shape, so they can be loaded straight into
the ship builder instead of being rebuilt by hand.

This module never writes to the input file or anywhere near it -- read-only,
one-shot parse to an in-memory result. See src/api.py's POST
/api/import_loadouts for the actual entry point; this module's own main()
is a CLI-testable wrapper around the same logic. The same endpoint also
backs the frontend's "Import raw XML loadout" paste-a-snippet feature,
whose result the frontend merges into its existing imported-loadouts
working set rather than replacing it (a server-side concern only in the
sense that parse_loadouts_xml() accepts a bare <loadout> root -- root.tag
== "loadout" -- as well as the usual <loadouts> wrapper, since a
hand-copied single-loadout snippet won't have one).

Alias substitution: a real loadout can reference an equipment ware_id this
app's own picker deliberately excludes as a true duplicate/alias of
another ware (e.g. shield_bor_m_standard_01_mk3, a redundant "virtual"
copy of shield_bor_m_standard_02_mk3 -- see generate_ships_table.py's
parse_equipment_component_wares docstring). The game itself never removed
that ware, only this app's own picker did, so every turret/engine/shield/
weapon macro reference in this module is resolved through
resolve_ware_id(), which substitutes the still-listed target ware
transparently (via the equipment_ware_aliases table, loaded once per
import into WareCatalog.alias_map) rather than reporting it as an invalid
choice.

Schema (confirmed by hand against a real 119-loadout save; see this
project's own investigation notes)
---------------------------------------------------------------------------
<loadouts> contains many <loadout id name description macro player version
revision>, each either a real ship (macro resolves to a real ships_base
ware_id) or a *station module* (macro like "defence_bor_tube_01_macro",
"storage_par_l_container_01_macro" -- a turret/shield/storage module, not a
ship at all). Station loadouts are always skipped entirely -- see
classify_loadout().

Within a ship loadout:
  - <macros>: ungrouped hardpoints, addressed by connection path
    (e.g. path="../con_weapon_02") rather than by name -- <engine>,
    <weapon>, <shield>, <turret> children. This project's own
    ship_component_groups has no record of raw connection *names* (only
    per-group counts), so these are matched by bucket (component_type +
    size, and -- for engines specifically -- by the single shared "engine"
    group every physical engine connection belongs to regardless of
    grouping) rather than by exact connection identity. Confirmed empty
    empirically (see match_ungrouped()) that this doesn't need to handle a
    *mixed* combined-engine-group case in practice, but the code still
    detects and warns about one if it ever occurs, rather than silently
    picking one macro and hiding the discrepancy.
  - <groups>: grouped hardpoints, addressed by a real group="..." name
    with an exact="N" slot count -- only <shields>/<turrets> ever appear
    here (no grouped engines/weapons in this file format). Matches
    ship_component_groups' own group_name/component_type/slot_count
    directly and exactly -- confirmed empirically that a single group is
    always filled by exactly one macro, never split across two (see
    match_grouped()).
  - <software>: ware="..." is already a real ware_id (not "..._macro"
    suffixed like everything else) -- matched by finding which of the
    ship's own software groups' options contains it.
  - <virtualmacros>/<thruster>: always exactly one, matched directly onto
    this app's own single synthesized "thruster" group per ship -- with
    nothing to validate the macro against (thrusters have no real
    per-ware compatibility concept at all -- see generate_ships_table.py's
    "Thrusters" docstring section and THRUSTER_COMPATIBILITY).
  - <ammunition>: a grab-bag of missiles, countermeasures, deployables
    (satellites/probes/mines/lasertowers/the nav beacon), and drones (as
    nested <unit> elements) with no type tag at all -- classified purely by
    looking each ware_id up against missiles_base/countermeasures_base/
    deployables_base/drones_base. Anything matching none of them is
    reported as unmapped rather than silently dropped -- e.g. the other 9
    env_deco_nav_beacon_t*_macro decoration variants (t2-t10) and the
    t1_mission variant, none of which are real wares (see
    generate_ships_table.py's deployable_jobs() docstring), would still
    fall into this bucket if a save ever somehow referenced one.
  - <crew role="marine"/"service" exact="N">: X4 has no separate
    marine/service *ware* -- confirmed against wares.xml and every ship
    macro's own <people capacity="..."/>, neither ever subdivides by role
    (see this project's own investigation notes). This maps directly onto
    this app's own crewAmounts role split (see app.js's CREW_ROLES) with
    no conversion needed at all.

<patches> (DLC dependency declarations) and per-entry `weaponmode`/
`ammunition=` attributes (turret AI behavior, default loaded missile type)
have no representation in this app's schema and are intentionally ignored
-- neither affects procurement cost, which is this app's whole scope.
"""

import argparse
import json
import random
import re
import sqlite3
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from query_ship_components import query_ship_groups

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "x4.db"


def macro_to_ware_id(macro: str | None) -> str | None:
    return macro.removesuffix("_macro") if macro else macro


def resolve_ware_id(macro: str | None, alias_map: dict[str, str]) -> str | None:
    """macro_to_ware_id() plus alias substitution: a real player-saved
    loadout can reference a ware_id this app's own picker excludes as a
    true duplicate/alias of another ware (see generate_ships_table.py's
    parse_equipment_component_wares docstring and the
    equipment_ware_aliases table it populates) -- the game itself never
    removed that ware, only this app's own picker did (to avoid showing
    two indistinguishable options), so it's substituted here for the
    still-listed target ware rather than reported as an invalid choice
    (see match_grouped()/match_ungrouped()'s own "not a listed option"
    warning, which only fires for a ware this can't resolve at all).
    """
    ware_id = macro_to_ware_id(macro)
    return alias_map.get(ware_id, ware_id)


def group_key(group: dict) -> str:
    """Matches app.js's own groupKey() exactly -- group_name alone isn't
    unique (a dedicated bonus shield shares its group_name with the group
    it protects), so every selections map in this app is keyed by
    "<group_name>::<component_type>" instead.
    """
    return f"{group['group_name']}::{group['component_type']}"


def is_linked_shield_group(group: dict, all_groups: list[dict]) -> bool:
    """True when `group` is a dedicated bonus/surface-element shield --
    mirrors app.js's isLinkedShieldGroup() (see equipment picker's "apply
    to all matching slots" checkbox) so ungrouped <shield> loadout entries
    only ever get bucket-matched against ordinary standalone main shield
    slots, never a bonus M shield slot of the same size.
    """
    if group["component_type"] != "shield":
        return False
    return any(g["group_name"] == group["group_name"] and g["component_type"] != "shield" for g in all_groups)


class WareCatalog:
    """Every real ware_id from the four "shared pool" tables an
    <ammunition>/<unit> entry might reference, plus the alias->target
    substitution map (see resolve_ware_id()), loaded once per import run
    (not per loadout -- these tables are tiny) rather than re-querying per
    entry.
    """

    def __init__(self, conn: sqlite3.Connection):
        self.missiles = {row[0] for row in conn.execute("SELECT ware_id FROM missiles_base")}
        self.countermeasures = {row[0] for row in conn.execute("SELECT ware_id FROM countermeasures_base")}
        self.deployables = {row[0] for row in conn.execute("SELECT ware_id FROM deployables_base")}
        self.drones = {row[0] for row in conn.execute("SELECT ware_id FROM drones_base")}
        self.ship_macro_to_ware_id = {
            row[1]: row[0] for row in conn.execute("SELECT ware_id, macro FROM ships_base")
        }
        # missiles_base/deployables_base/drones_base's own macro column,
        # keyed the other way round -- macro_to_ware_id()'s naive "_macro"
        # suffix strip silently produces the wrong string whenever a ware's
        # underlying macro/model asset was named differently from its own
        # ware_id (a leftover of whichever internal art team authored it --
        # e.g. ware "satellite_mk1"/"resourceprobe_01"/"waypointmarker_01"
        # but macro "eq_arg_satellite_01_macro"/"eq_arg_resourceprobe_01_
        # macro"/"env_deco_nav_beacon_t1_macro"). Built once here, same
        # shape as ship_macro_to_ware_id above, and consulted first in
        # classify_ammunition() before falling back to the naive strip
        # (which is correct for the majority of missiles/deployables/
        # drones, where macro and ware_id do match). countermeasures_base
        # has no macro column -- its one ware ("Flares") always has, so
        # the naive strip alone already handles it.
        self.ammo_macro_to_ware_id: dict[str, str] = {}
        for table in ("missiles_base", "deployables_base", "drones_base"):
            for row in conn.execute(f"SELECT ware_id, macro FROM {table} WHERE macro IS NOT NULL"):
                self.ammo_macro_to_ware_id[row[1]] = row[0]
        self.alias_map = {
            row[0]: row[1] for row in conn.execute("SELECT alias_ware_id, target_ware_id FROM equipment_ware_aliases")
        }


def classify_loadout(loadout_el: ET.Element, catalog: WareCatalog) -> str | None:
    """The ships_base ware_id this <loadout> targets, or None if its macro
    doesn't resolve to a real ship at all -- a station module (defence/
    storage/etc.) loadout, which this importer always skips entirely.
    """
    macro = loadout_el.get("macro")
    return catalog.ship_macro_to_ware_id.get(macro)


def match_grouped(
    groups_el: ET.Element | None, ship_groups: list[dict], selections: dict, warnings: list[str], catalog: WareCatalog
) -> None:
    """<groups><shields>/<turrets> entries -- each carries the game's own
    real group_name, so this matches ship_component_groups' group_name +
    the component_type implied by the XML tag directly and exactly (see
    this module's docstring for why that's safe: a single group is never
    split across two macros in practice).
    """
    if groups_el is None:
        return

    for tag, component_type in (("shields", "shield"), ("turrets", "turret")):
        for entry in groups_el.findall(tag):
            ware_id = resolve_ware_id(entry.get("macro"), catalog.alias_map)
            group_name = entry.get("group")
            group = next(
                (g for g in ship_groups if g["component_type"] == component_type and g["group_name"] == group_name),
                None,
            )
            if group is None:
                warnings.append(f"No matching {component_type} group '{group_name}' on this ship -- skipped {ware_id}")
                continue

            exact = entry.get("exact")
            if exact is not None and int(exact) != group["slot_count"]:
                warnings.append(
                    f"Group '{group_name}' ({component_type}): loadout expects {exact} slots, "
                    f"this ship's data has {group['slot_count']} -- may be a different DLC configuration"
                )

            if not any(o["ware_id"] == ware_id for o in group["options"]):
                warnings.append(
                    f"'{ware_id}' is not a listed option for group '{group_name}' ({component_type}) -- "
                    "applied anyway, but verify it's actually correct"
                )

            selections[group_key(group)] = ware_id


def match_ungrouped(
    macros_el: ET.Element | None, ship_groups: list[dict], selections: dict, warnings: list[str], catalog: WareCatalog
) -> None:
    """<macros><engine>/<weapon>/<shield>/<turret> entries -- ungrouped,
    addressed by connection path rather than name. Bucket-matched against
    this ship's own same-(component_type, size) standalone groups (this
    app's own synthesized "weapon_1"/"turret_1"/"shield_1"/... rows) in
    whatever order they appear, since raw connection identity isn't
    preserved anywhere in this app's schema and doesn't affect cost either
    way -- see this module's docstring.
    """
    if macros_el is None:
        return

    already_grouped_names = {sel_key.split("::", 1)[0] for sel_key in selections}
    claimed: set[str] = set()

    # Engines (and missile-capable weapons, see below) always combine into
    # one shared group regardless of grouping (COMBINED_GROUP_TYPES in
    # generate_ships_table.py) -- every <engine> entry in this loadout
    # targets that *same* group, so they're collected first and resolved
    # together rather than one-by-one like the others.
    engine_macros = [resolve_ware_id(el.get("macro"), catalog.alias_map) for el in macros_el.findall("engine")]
    if engine_macros:
        engine_group = next((g for g in ship_groups if g["component_type"] == "engine"), None)
        if engine_group is None:
            warnings.append(f"No engine group on this ship -- skipped {set(engine_macros)}")
        else:
            distinct = set(engine_macros)
            if len(distinct) > 1:
                warnings.append(
                    f"Loadout uses different engines across its own slots ({sorted(distinct)}) -- "
                    "this app only supports one engine choice per ship, so the most common one was used"
                )
            chosen = max(distinct, key=engine_macros.count)
            selections[group_key(engine_group)] = chosen

    # <weapon> entries split into two buckets: an ordinary weapon (its own
    # standalone "weapon_N" group) or a missile launcher (the single
    # shared "missile_launcher" combined group, same COMBINED_GROUP_TYPES
    # reasoning as engines above) -- which one depends on the *ware*
    # itself (weapons_base.missile_launcher), not anything in the loadout
    # file, so this needs a quick lookup per entry.
    launcher_macros = []
    weapon_entries = []
    for el in macros_el.findall("weapon"):
        # Resolved before the missile-launcher check below, not just at
        # final selection time -- an excluded alias ware_id would never
        # appear in any group's own options (that's exactly why it was
        # excluded), so checking with the raw, unresolved ware_id here
        # would always misclassify an aliased launcher as an ordinary
        # weapon instead.
        ware_id = resolve_ware_id(el.get("macro"), catalog.alias_map)
        is_launcher = any(
            g["component_type"] == "missile_launcher" and any(o["ware_id"] == ware_id for o in g["options"])
            for g in ship_groups
        )
        if is_launcher:
            launcher_macros.append(ware_id)
        else:
            weapon_entries.append(ware_id)

    if launcher_macros:
        launcher_group = next((g for g in ship_groups if g["component_type"] == "missile_launcher"), None)
        if launcher_group is None:
            warnings.append(f"No missile launcher group on this ship -- skipped {set(launcher_macros)}")
        else:
            distinct = set(launcher_macros)
            if len(distinct) > 1:
                warnings.append(
                    f"Loadout uses different missile launchers across its own slots ({sorted(distinct)}) -- "
                    "this app only supports one choice per ship, so the most common one was used"
                )
            selections[group_key(launcher_group)] = max(distinct, key=launcher_macros.count)

    # Ordinary standalone weapon/shield/turret entries: each is its own
    # separate group (slot_count 1) in this app's schema, consumed
    # one-for-one in whatever order they're listed -- see this function's
    # own docstring for why order doesn't matter here.
    standalone_entries = [("weapon", ware_id) for ware_id in weapon_entries]
    standalone_entries += [
        ("shield", resolve_ware_id(el.get("macro"), catalog.alias_map)) for el in macros_el.findall("shield")
    ]
    standalone_entries += [
        ("turret", resolve_ware_id(el.get("macro"), catalog.alias_map)) for el in macros_el.findall("turret")
    ]

    for component_type, ware_id in standalone_entries:
        candidates = [
            g
            for g in ship_groups
            if g["component_type"] == component_type
            and g["group_name"] not in already_grouped_names
            and group_key(g) not in claimed
            and (component_type != "shield" or not is_linked_shield_group(g, ship_groups))
        ]
        # Prefer a candidate that actually lists this ware as one of its
        # own options (confirms size/compatibility genuinely matches);
        # fall back to any unclaimed same-type candidate otherwise, since
        # a real loadout's own choice is still the best information
        # available even when this app's option list can't confirm it
        # (e.g. a duplicate/alias ware excluded from the picker -- see
        # generate_ships_table.py's alias-duplicate handling).
        match = next((g for g in candidates if any(o["ware_id"] == ware_id for o in g["options"])), None)
        if match is None and candidates:
            match = candidates[0]
            warnings.append(f"'{ware_id}' is not a listed option for any open {component_type} slot -- applied anyway")
        if match is None:
            warnings.append(f"No open {component_type} slot left for '{ware_id}' -- skipped")
            continue
        claimed.add(group_key(match))
        selections[group_key(match)] = ware_id


def match_software(software_el: ET.Element | None, ship_groups: list[dict], selections: dict, warnings: list[str]) -> None:
    """<software><software ware="..."/> -- `ware` is already a real
    ware_id (not "..._macro" suffixed), matched by finding which
    software group's own options list contains it.
    """
    if software_el is None:
        return
    for entry in software_el.findall("software"):
        ware_id = entry.get("ware")
        group = next(
            (g for g in ship_groups if g["component_type"] == "software" and any(o["ware_id"] == ware_id for o in g["options"])),
            None,
        )
        if group is None:
            warnings.append(f"'{ware_id}' is not a valid software choice for this ship -- skipped")
            continue
        selections[group_key(group)] = ware_id


def match_thruster(virtualmacros_el: ET.Element | None, ship_groups: list[dict], selections: dict, warnings: list[str]) -> None:
    """<virtualmacros><thruster macro="..."/></virtualmacros> -- always
    exactly one, matching this app's own single synthesized "thruster"
    group per ship (thrusters have no real per-ware compatibility concept
    at all -- see generate_ships_table.py's "Thrusters" docstring section
    and THRUSTER_COMPATIBILITY -- so there's nothing to validate the
    macro against, unlike every other equipment type here).
    """
    if virtualmacros_el is None:
        return
    thruster_el = virtualmacros_el.find("thruster")
    if thruster_el is None:
        return
    ware_id = macro_to_ware_id(thruster_el.get("macro"))
    group = next((g for g in ship_groups if g["component_type"] == "thruster"), None)
    if group is None:
        warnings.append(f"No thruster group on this ship -- skipped {ware_id}")
        return
    selections[group_key(group)] = ware_id


def classify_ammunition(
    ammunition_el: ET.Element | None,
    catalog: WareCatalog,
    missile_amounts: dict,
    drone_amounts: dict,
    deployable_amounts: dict,
    countermeasure_amounts: dict,
    warnings: list[str],
) -> None:
    """<ammunition> is a grab-bag of <ammunition macro=.../> (missiles,
    countermeasures, deployables) and <unit macro=.../> (drones) with no
    type tag distinguishing them -- classified purely by which of this
    app's own catalogs the resolved ware_id actually belongs to.
    """
    if ammunition_el is None:
        return
    for entry in list(ammunition_el.findall("ammunition")) + list(ammunition_el.findall("unit")):
        macro = entry.get("macro")
        ware_id = catalog.ammo_macro_to_ware_id.get(macro, macro_to_ware_id(macro))
        amount = int(entry.get("exact", "1"))
        if ware_id in catalog.missiles:
            missile_amounts[ware_id] = missile_amounts.get(ware_id, 0) + amount
        elif ware_id in catalog.countermeasures:
            countermeasure_amounts[ware_id] = countermeasure_amounts.get(ware_id, 0) + amount
        elif ware_id in catalog.deployables:
            deployable_amounts[ware_id] = deployable_amounts.get(ware_id, 0) + amount
        elif ware_id in catalog.drones:
            drone_amounts[ware_id] = drone_amounts.get(ware_id, 0) + amount
        else:
            warnings.append(f"'{ware_id}' is not a missile/countermeasure/deployable/drone this app tracks -- skipped")


def parse_crew(crew_el: ET.Element | None) -> dict:
    """<crew role="marine"/"service" exact="N"> maps directly onto this
    app's own crewAmounts role split (app.js's CREW_ROLES) -- no
    conversion needed, since neither role was ever a separate ware to
    begin with on either side (see this module's docstring).
    """
    amounts = {}
    if crew_el is None:
        return amounts
    for entry in crew_el.findall("crew"):
        role = entry.get("role")
        if role not in ("marine", "service"):
            continue
        amount = int(entry.get("exact", "0"))
        if amount > 0:
            amounts[role] = amounts.get(role, 0) + amount
    return amounts


def parse_ship_loadout(loadout_el: ET.Element, ship_ware_id: str, conn: sqlite3.Connection, catalog: WareCatalog) -> dict:
    ship_groups_data = query_ship_groups(conn, ship_ware_id)
    ship_groups = ship_groups_data["groups"]

    warnings: list[str] = []
    selections: dict[str, str] = {}
    match_grouped(loadout_el.find("groups"), ship_groups, selections, warnings, catalog)
    match_ungrouped(loadout_el.find("macros"), ship_groups, selections, warnings, catalog)
    match_software(loadout_el.find("software"), ship_groups, selections, warnings)
    match_thruster(loadout_el.find("virtualmacros"), ship_groups, selections, warnings)

    missile_amounts: dict[str, int] = {}
    drone_amounts: dict[str, int] = {}
    deployable_amounts: dict[str, int] = {}
    countermeasure_amounts: dict[str, int] = {}
    classify_ammunition(
        loadout_el.find("ammunition"),
        catalog,
        missile_amounts,
        drone_amounts,
        deployable_amounts,
        countermeasure_amounts,
        warnings,
    )
    crew_amounts = parse_crew(loadout_el.find("crew"))

    return {
        "id": loadout_el.get("id"),
        "name": loadout_el.get("name") or "",
        "shipWareId": ship_ware_id,
        "shipName": ship_groups_data["name"],
        "shipIcon": ship_groups_data.get("icon"),
        "selections": selections,
        "missileAmounts": missile_amounts,
        "droneAmounts": drone_amounts,
        "deployableAmounts": deployable_amounts,
        "countermeasureAmounts": countermeasure_amounts,
        "crewAmounts": crew_amounts,
        "warnings": warnings,
        # The original <loadout>...</loadout> element, verbatim (re-
        # serialized from the parsed tree, not the source bytes -- attribute
        # order/whitespace may differ, but every element/attribute is
        # unchanged, so it's semantically identical XML). Kept so the
        # frontend's "Export Loadouts" button can hand back exactly what
        # was imported/pasted, wrapped in a fresh <loadouts> root, with no
        # server-side reconstruction needed -- this app doesn't store raw
        # per-connection path names for ungrouped hardpoints (see this
        # module's docstring), so rebuilding valid game XML from
        # `selections` alone wouldn't be reliably round-trippable, but
        # replaying the original element always is.
        "rawXml": ET.tostring(loadout_el, encoding="unicode"),
    }


def generate_loadout_id() -> str:
    """A fresh id for a loadout built entirely inside this app (the "Add to
    Saved Loadouts" button), in the same "player_<10 digits>" shape every
    id in a real loadouts.xml already uses (e.g. "player_1786142268") --
    this app never inspects id content itself (see WareCatalog/
    classify_loadout(), neither of which read it), so any 10-digit string
    is fine; this just keeps a hand-built entry indistinguishable in shape
    from a real one if the user later exports and inspects the file.
    """
    return "player_" + "".join(random.choices("0123456789", k=10))


# The exact fallback name parse_component_slots() (generate_ships_table.py)
# synthesizes for a shield/turret connection with no real "group" XML
# attribute -- e.g. "shield_2", "turret_5". A real in-game group name never
# takes this shape in any save examined this session (they're either
# descriptive, e.g. "group_front_up_mid", or the fixed "engine"/
# "missile_launcher" -- neither of which build_loadout_xml() ever routes
# through this check, see below). Used to tell a synthesized bucket label
# apart from a real one when choosing which XML shape to emit.
SYNTHESIZED_GROUP_NAME_RE = re.compile(r"^(shield|turret)_\d+$")


def build_loadout_xml(
    conn: sqlite3.Connection,
    ship_groups_data: dict,
    ship_macro: str,
    name: str,
    loadout_id: str,
    selections: dict,
    missile_amounts: dict,
    drone_amounts: dict,
    deployable_amounts: dict,
    countermeasure_amounts: dict,
    crew_amounts: dict,
) -> str:
    """The reverse of parse_ship_loadout(): builds a real <loadout> XML
    element from this app's own ship-builder state (the "Add to Saved
    Loadouts" button), so a loadout built entirely inside this app is
    still exportable via "Export Loadouts" (see api.py's rawXml field) --
    not just ones parsed from a real save.

    Engine/weapon connections are addressed by ship_component_groups'
    connection_names (the ship's own real <connection name="..."/> values,
    e.g. "con_weapon_01") when available -- which member of a group gets
    which specific name doesn't matter (every member is interchangeable
    for compatibility/cost purposes, see connection_names' own schema
    comment), so this just hands them out in whatever order they were
    stored in. Only falls back to a synthesized sequential placeholder
    ("con_engine_01", "con_weapon_02", ...) if a ship's data somehow has
    fewer real names than slots -- shouldn't normally happen, since both
    are counted together at parse time, but degrades gracefully rather
    than raising if it ever does (e.g. a re-generated DB from before
    connection_names existed). This app's own importer round-trips either
    way regardless -- match_ungrouped() bucket-matches by component_type+
    size only and never reads path content at all (see its own docstring)
    -- so a synthesized fallback only matters if the exported file is
    dropped directly into a real game's loadouts.xml, where a genuinely
    wrong path would be silently skipped by the game for that one slot
    rather than misapplied -- not a corruption risk, just a possible
    partial no-op.

    Shield/turret shape (<groups> vs <macros>) is chosen per group by
    SYNTHESIZED_GROUP_NAME_RE -- <groups> only actually matches anything in
    a real save for a connection that carries a real "group" XML attribute
    to begin with. A "missile_launcher" group's <macros> entries are
    emitted as <weapon>, not "<missile_launcher>" (no such tag exists in a
    real save) -- mirrors match_ungrouped()'s own is_launcher check, which
    classifies by ware_id membership in that group's options, never by a
    distinct XML tag.
    """
    macros_entries: list[tuple[str, dict]] = []
    groups_entries: list[tuple[str, dict]] = []
    software_ware_ids: list[str] = []
    thruster_macro: str | None = None
    path_counters: dict[str, int] = {}

    for group in ship_groups_data.get("groups", []):
        component_type = group["component_type"]
        group_name = group["group_name"]
        ware_id = selections.get(f"{group_name}::{component_type}")
        if not ware_id:
            continue

        if component_type == "software":
            software_ware_ids.append(ware_id)
            continue
        if component_type == "thruster":
            thruster_macro = f"{ware_id}_macro"
            continue

        macro = f"{ware_id}_macro"
        slot_count = group["slot_count"]
        use_groups_shape = component_type in ("shield", "turret") and not SYNTHESIZED_GROUP_NAME_RE.match(group_name)
        if use_groups_shape:
            tag = "shields" if component_type == "shield" else "turrets"
            groups_entries.append((tag, {"macro": macro, "group": group_name, "exact": str(slot_count)}))
        else:
            # A real save has no "<missile_launcher>" tag at all -- missile
            # launchers are ordinary <weapon> entries there, disambiguated
            # only by ware_id membership in the ship's own "missile_
            # launcher" group's options (see match_ungrouped()'s own
            # is_launcher check, which this must stay the XML-shape mirror
            # of). Every other component_type's tag matches its own name.
            xml_tag = "weapon" if component_type == "missile_launcher" else component_type
            # Real connection names (ship_component_groups.connection_names,
            # see its schema comment) when this ship's data has them --
            # every member of this group is interchangeable, so assignment
            # order within the group doesn't matter. Falls back to a
            # synthesized placeholder only for whatever's left uncovered
            # (shouldn't normally happen -- real_names and slot_count are
            # counted together at parse time -- but degrades gracefully
            # rather than raising if it ever does).
            real_names = [n for n in (group.get("connection_names") or "").split(",") if n]
            for i in range(slot_count):
                if i < len(real_names):
                    path = f"../{real_names[i]}"
                else:
                    path_counters[xml_tag] = path_counters.get(xml_tag, 0) + 1
                    path = f"../con_{xml_tag}_{path_counters[xml_tag]:02d}"
                macros_entries.append((xml_tag, {"macro": macro, "path": path}))

    # <ammunition>: missiles/deployables/countermeasures as <ammunition
    # macro exact=".../>, drones as <unit macro exact=.../> -- mirrors
    # classify_ammunition()'s grouping in reverse. missiles_base/
    # deployables_base/drones_base's own macro column is the exact reverse
    # of WareCatalog.ammo_macro_to_ware_id above; countermeasures_base has
    # no macro column (see generate_ships_table.py's schema) since the
    # naive "<ware_id>_macro" convention already holds for it -- same
    # reasoning classify_ammunition()'s own fallback relies on.
    missile_macros = {row[0]: row[1] for row in conn.execute("SELECT ware_id, macro FROM missiles_base")}
    deployable_macros = {row[0]: row[1] for row in conn.execute("SELECT ware_id, macro FROM deployables_base")}
    drone_macros = {row[0]: row[1] for row in conn.execute("SELECT ware_id, macro FROM drones_base")}

    ammunition_entries: list[tuple[str, dict]] = []
    for ware_id, amount in missile_amounts.items():
        if amount > 0:
            ammunition_entries.append(
                ("ammunition", {"macro": missile_macros.get(ware_id, f"{ware_id}_macro"), "exact": str(amount)})
            )
    for ware_id, amount in deployable_amounts.items():
        if amount > 0:
            ammunition_entries.append(
                ("ammunition", {"macro": deployable_macros.get(ware_id, f"{ware_id}_macro"), "exact": str(amount)})
            )
    for ware_id, amount in countermeasure_amounts.items():
        if amount > 0:
            ammunition_entries.append(("ammunition", {"macro": f"{ware_id}_macro", "exact": str(amount)}))
    for ware_id, amount in drone_amounts.items():
        if amount > 0:
            ammunition_entries.append(("unit", {"macro": drone_macros.get(ware_id, f"{ware_id}_macro"), "exact": str(amount)}))

    crew_entries = [(role, amount) for role, amount in crew_amounts.items() if amount > 0 and role in ("marine", "service")]

    loadout_el = ET.Element(
        "loadout",
        {
            "id": loadout_id,
            "name": name,
            "description": "",
            "macro": ship_macro,
            "player": "1",
            "version": "900",
            "revision": "1",
        },
    )
    if macros_entries:
        macros_el = ET.SubElement(loadout_el, "macros")
        for tag, attrs in macros_entries:
            ET.SubElement(macros_el, tag, attrs)
    if groups_entries:
        groups_el = ET.SubElement(loadout_el, "groups")
        for tag, attrs in groups_entries:
            ET.SubElement(groups_el, tag, attrs)
    if ammunition_entries:
        ammunition_el = ET.SubElement(loadout_el, "ammunition")
        for tag, attrs in ammunition_entries:
            ET.SubElement(ammunition_el, tag, attrs)
    if software_ware_ids:
        software_el = ET.SubElement(loadout_el, "software")
        for ware_id in software_ware_ids:
            ET.SubElement(software_el, "software", {"ware": ware_id})
    if thruster_macro:
        virtualmacros_el = ET.SubElement(loadout_el, "virtualmacros")
        ET.SubElement(virtualmacros_el, "thruster", {"macro": thruster_macro})
    if crew_entries:
        crew_el = ET.SubElement(loadout_el, "crew")
        for role, amount in crew_entries:
            ET.SubElement(crew_el, "crew", {"role": role, "exact": str(amount)})

    return ET.tostring(loadout_el, encoding="unicode")


def build_saved_loadout_entry(
    conn: sqlite3.Connection,
    ship_ware_id: str,
    name: str,
    selections: dict,
    missile_amounts: dict,
    drone_amounts: dict,
    deployable_amounts: dict,
    countermeasure_amounts: dict,
    crew_amounts: dict,
) -> dict:
    """The "Add to Saved Loadouts" button's entry point -- builds a full
    entry in the exact same shape parse_ship_loadout() returns (so the
    frontend can drop it into importedLoadoutsResult.ships and treat it
    identically to an imported one for every downstream feature: Select
    Saved Loadout, Select Chassis Loadout, Export Loadouts), plus a fresh
    generate_loadout_id().
    """
    ship_groups_data = query_ship_groups(conn, ship_ware_id)
    ship_row = conn.execute("SELECT macro FROM ships_base WHERE ware_id = ?", (ship_ware_id,)).fetchone()
    ship_macro = ship_row[0] if ship_row else f"{ship_ware_id}_macro"
    loadout_id = generate_loadout_id()

    raw_xml = build_loadout_xml(
        conn,
        ship_groups_data,
        ship_macro,
        name,
        loadout_id,
        selections,
        missile_amounts,
        drone_amounts,
        deployable_amounts,
        countermeasure_amounts,
        crew_amounts,
    )

    return {
        "id": loadout_id,
        "name": name,
        "shipWareId": ship_ware_id,
        "shipName": ship_groups_data["name"],
        "shipIcon": ship_groups_data.get("icon"),
        "selections": selections,
        "missileAmounts": missile_amounts,
        "droneAmounts": drone_amounts,
        "deployableAmounts": deployable_amounts,
        "countermeasureAmounts": countermeasure_amounts,
        "crewAmounts": crew_amounts,
        "warnings": [],
        "rawXml": raw_xml,
    }


def parse_loadouts_xml(xml_text: str, conn: sqlite3.Connection) -> dict:
    """Parse a real loadouts.xml's <loadouts> root, OR (for the "Import raw
    XML loadout" paste-a-snippet feature) a single bare <loadout> element
    with no wrapper at all -- both are real shapes a user might reasonably
    copy out of a saved loadouts.xml, and ET.fromstring() gives no signal
    beyond the root tag itself to tell them apart.
    """
    root = ET.fromstring(xml_text)
    catalog = WareCatalog(conn)
    loadout_els = [root] if root.tag == "loadout" else root.findall("loadout")

    ships: list[dict] = []
    failed: list[dict] = []
    skipped_station_count = 0
    total = 0

    # Repeated <loadout> entries commonly target the same ship (seen
    # heavily in real saves -- multiple "Standard"/"expensive" variants of
    # the same trans_container) -- cached per import run so each ship's
    # own group/option data is only fetched once regardless of how many
    # loadouts reference it.
    ship_groups_cache: dict[str, dict] = {}

    for loadout_el in loadout_els:
        total += 1
        ship_ware_id = classify_loadout(loadout_el, catalog)
        if ship_ware_id is None:
            skipped_station_count += 1
            continue

        try:
            if ship_ware_id not in ship_groups_cache:
                ship_groups_cache[ship_ware_id] = query_ship_groups(conn, ship_ware_id)
            ships.append(parse_ship_loadout(loadout_el, ship_ware_id, conn, catalog))
        except Exception as exc:  # noqa: BLE001 -- one bad loadout shouldn't abort the whole import
            failed.append({"id": loadout_el.get("id"), "name": loadout_el.get("name") or "", "reason": str(exc)})

    return {
        "ships": ships,
        "failed": failed,
        "total_loadouts": total,
        "skipped_station_loadouts": skipped_station_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", help="Path to a loadouts.xml file")
    args = parser.parse_args()

    xml_text = Path(args.path).read_text(encoding="utf-8-sig")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        result = parse_loadouts_xml(xml_text, conn)
    finally:
        conn.close()

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
