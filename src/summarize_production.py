"""Summarize the production requirements for a list of target wares,
resolved against an ordered build method priority list, to a configurable
search depth.

Input: JSON (a file path argument, or "-" to read from stdin), shaped like:
{
  "build_method_priority": ["Teladi", "Universal", ...],  # optional; case-
                                # insensitive; defaults to
                                # DEFAULT_BUILD_METHOD_PRIORITY (BUILD_METHODS
                                # in generate_ships_table.py -- every real
                                # build method, Universal first, Terran
                                # second, Recycling/Xenon last)
  "search_depth": 1,                    # optional, defaults to 1 (one layer)
  "verbose": true,                      # optional, defaults to true
  "group_by_component_type": false,     # optional, defaults to false
  "wares": [
    {
      "count": 5,
      "wares_list": [
        {"ware_id": "ship_bor_s_heavyfighter_01_a", "amount": 1},
        {"ware_id": "engine_bor_s_allround_01_mk1", "amount": 1},
        {"ware_id": "shield_bor_s_standard_01_mk1", "amount": 1},
        {"ware_id": "shield_bor_m_standard_01_mk1", "amount": 1, "category": "surface_element_shield"},
        {"ware_id": "weapon_bor_s_arc_01_mk1", "amount": 3}
      ]
    },
    {
      "count": 10,
      "wares_list": [
        {"ware_id": "ship_tel_l_trans_container_03_a", "amount": 1},
        {"ware_id": "engine_tel_l_allround_01_mk1", "amount": 2}
      ]
    }
  ]
}

"wares" is a list of *configurations*, not a flat ware list -- each one
bundles a "wares_list" (e.g. a ship plus all of its equipment, one entry
per ware/amount) with a "count" (how many of that whole configuration to
build). This is aggregate_target_wares' job: every ware in a
configuration's wares_list has its own amount multiplied by that
configuration's count, and the results are summed across *every*
configuration and ware -- so "5 of ship A" (with its own loadout) and "10
of ship B" (with a completely different one) combine into a single
shopping list before any production expansion happens, with matching
ware_ids (e.g. a turret type both ships happen to use) summed together
rather than listed twice -- unless they also specify different "category"
overrides (see below), in which case they're kept as separate target
entries instead of merged. Everything downstream of that point
(build_method_priority, search_depth, resolution_log, and so on) operates
on that one flattened list exactly as before -- it has no notion of
"configurations" at all. Every ware_id prefixed "software_" is still
priced (fetch_ware_prices()/PRICE_WARE_TABLES cover software_base, so
api.py's POST /api/price_summary "top_level" tier counts it), but
summarize() itself excludes software wares from "parts" entirely, at
every search_depth -- see summarize()'s own docstring for why.

A wares_list item's "category" is optional and only matters when
group_by_component_type is true (see below) -- it overrides whatever
category that ware_id would otherwise get from the DB-driven default,
which is the only way to distinguish two uses of the *same* ware_id that
should land in different categories. The one real case this exists for:
a "surface element" (bonus M) shield and an ordinary main shield can be
the exact same shield ware_id -- nothing about the ware itself says which
role it's playing, only which hardpoint *group* a specific ship's picker
put it in (see query_ship_groups()'s dedicated-shield handling in
query_ship_components.py) -- so the picker UI tags a bonus-shield
selection with "category": "surface_element_shield" explicitly rather
than leaving it to guess. Any wares_list item without a "category" key
falls back to the DB-driven default, same as always.

"verbose" controls whether each method's "resolution_log" (see "Output"
below) appears in the output at all: true (the default) includes it; false
omits the key entirely from every method entry, leaving just "parts"/
"ware_count". It's still computed internally either way (it costs nothing
extra to skip), only its presence in the output changes.

"group_by_component_type" controls the shape of "parts" (see "Output"
below): false (the default) is the original flat ware_id -> amount map;
true splits it into one such map per *top-level* target ware's own
category -- "chassis" (ships_base), "engine"/"main_shield"/"thruster"/
"turret"/"weapon" (equipment_wares_base.equipment_type, with "shield"
renamed to "main_shield" -- see "surface_element_shield" below),
"missile" (missiles_base), "drone" (drones_base), "deployable"
(deployables_base) -- so e.g. every raw material consumed building
engines ends up in its own "engine" bucket, separate from the same raw
material consumed building shields, rather than one combined total.
"surface_element_shield" is never assigned by this DB-driven default --
it only ever comes from a wares_list item's own explicit "category"
override (see above), since a bonus M shield and a main shield can share
the same ware_id. A target ware that isn't found in any of the above
tables (a hand-authored input listing a raw economy ware like
"energycells" directly, or any other unrecognized ware_id, and also not
carrying its own "category" override) falls into a catch-all
"production_wares" category instead of being dropped or raising an
error. The category is decided once per top-level target ware and
applies to that ware's *entire* expansion -- a sub-part several layers
into an engine's production chain is still counted under "engine", even
though the sub-part ware_id itself has no equipment_type of its own.

Method resolution (used at every level)
------------------------------------------
For a given ware, "the same process" always means: try each entry of
build_method_priority in order (exact match, case-insensitive) and use the
first available match; if none of them match, the ware can't be expanded
under this priority list at all, so it's folded into the output as-is (as
if it were a leaf ware) instead of being dropped.

summarize() resolves to at most one build method per call -- build_method_
priority names the one *ranked list* to try, not several independent
choices to compare; a side-by-side comparison of several priority
orderings means calling it once per ordering (e.g. this app's frontend: one
Ware Cost List column per procurement list, each with its own
build_method_priority), not one call enumerating every viable candidate
into separate buckets.

search_depth
---------------
Depth counts layers below the top-level target: depth 0 is the target ware
itself (a ship, a turret, whatever was asked for), depth 1 is its direct
components, depth 2 is those components' own components, and so on.
"resolution_log" entries (see "Output" below) are tagged with the depth of
the ware whose *own* resolution needed a substitution.

search_depth=1 (the default) expands each target ware exactly one level:
its production_wares rows (depth 1) become the output "parts" directly,
and depth-1 wares are never themselves resolved further -- this is the
original one-layer behavior.

search_depth=N (N>1) keeps going: depths 1..N-1 get resolved and expanded
into their own sub-parts, and depth-N wares are the terminal layer (shown
in "parts" as-is, not expanded further). The *original* build_method_
priority list (the same one given for the whole call -- see "Method
resolution" above) is retained at every depth, not whatever a parent had
to fall back to -- e.g. if hullparts (depth 1) resolves via "Teladi" but
one of its sub-parts, graphene (depth 2), has no Teladi recipe and falls
back to "Universal", graphene's own sub-parts (depth 3) still try "Teladi"
first (falling back again independently if needed) rather than inheriting
"Universal" from graphene.

A branch stops expanding, regardless of search_depth, once it bottoms out
at either a true leaf ware (no production recipe at all) or a ware with no
remaining method to try (the current focus nor any fallback available for
it) -- so a small search_depth is a "stop early" cap, and a search_depth
comfortably larger than the deepest real production chain (e.g. 10) is
"expand until nothing but leaves/unresolvable wares remain" in practice.
Only terminal wares (leaves, unresolvable, or cut off by search_depth)
appear in the output "parts"; anything successfully expanded along the way
does not. A cycle (a ware recursively depending on itself) is treated the
same as a fallback-exhausted ware -- expansion stops there and it's
included as-is -- rather than recursing forever; ABSOLUTE_MAX_DEPTH is a
second, blunter hard cap independent of search_depth, purely to stop a
runaway input (e.g. search_depth set absurdly high) from recursing
unboundedly.

Output
---------
"build_method_priority" echoes back the priority list this run actually
used -- the input verbatim, or DEFAULT_BUILD_METHOD_PRIORITY when none was
given.

"parts"/"ware_count"/"resolution_log" (see below) are only present at all
when build_method_priority is non-empty -- there's nothing to resolve
against otherwise, so every target ware would trivially become a leaf with
no real breakdown to report; an empty priority list short-circuits to just
the echoed-back (empty) list with no further keys, rather than reporting a
degenerate "everything is a leaf" result. Whenever they are present:
  - "parts": with group_by_component_type false (the default), required
    ware_id -> summed amount needed (across all target wares and every
    level of their expansion, including different target wares that fell
    back to different methods but shared the same top-priority one).
    With group_by_component_type true, this is instead category ->
    (ware_id -> summed amount), one flat map per category as described
    above -- a category with no contributions at all is omitted entirely
    rather than appearing as an empty map. Software target wares (ware_id
    prefixed "software_") never contribute here at all, regardless of
    search_depth -- see this function's own inline comment on the target
    loop for why.
  - "ware_count": how many distinct wares "parts" contains -- with
    group_by_component_type true, this counts each distinct ware_id once
    even if it appears under more than one category (e.g. a raw material
    needed by both engines and shields), matching what it would have been
    with grouping off.
  - "resolution_log" (only when verbose): see below

"resolution_log" is a record of every actual *substitution* within that
method's own expansion, in the order they happened -- a ware whose
requested method wasn't available, but a fallback method was found and
used in its place. Nothing else is logged: not a direct hit (the requested
method was available, nothing to substitute), not a plain leaf ware (no
production recipe at all), not a fallback-exhausted ware (no fallback
matched either), not a dependency cycle, and not a ware cut off by the
search_depth cap -- all of those are terminal outcomes that still
contribute to "parts" as-is, they just aren't substitutions. Each log entry
has "ware_id", "requested_method" (what this stage actually asked for),
"used_method" (the fallback method used instead), and "depth".

Monetary cost analysis (fetch_ware_prices / summarize_prices)
------------------------------------------------------------------
A separate, non-recursive companion to everything above: given any flat
ware_id -> amount map, summarize_prices() looks up each ware's
price_min/price_avg/price_max directly (no production_wares involvement,
no expansion of a ware into its own components) and sums them
into total_min/total_avg/total_max. It's deliberately just a lookup-and-
sum -- *which* ware_id -> amount map to price is entirely the caller's
choice, and different choices answer genuinely different questions that
are never meant to be combined into one number. api.py's
POST /api/price_summary is the actual caller, and asks this same question
at three different depths for the same cart:
  - the *unexpanded* top-level target list itself (aggregate_target_wares'
    own output) -- each ware's own market price ("buy it outright")
  - summarize()'s own "parts" at search_depth=1 -- each top-level ware's
    direct recipe inputs, priced directly ("buy what the shipyard itself
    consumes")
  - summarize()'s own "parts" at search_depth=ABSOLUTE_MAX_DEPTH -- fully
    expanded down to true leaf wares ("build everything from scratch")
See api.py's own docstring for exactly how these three are packaged into
one response. An optional price_overrides map (ware_id -> price)
substitutes a single price for all three tiers of a given ware, e.g. when
the game data's range doesn't match what the player actually pays. A ware
with no price data anywhere (and no override) is excluded from every total
and reported in "missing_prices" rather than being treated as free.

Each of the three depths above can additionally be priced *by component
type* instead of as one combined total -- summarize_prices_by_category()
and categorize_target_wares() are the by-category counterparts of
summarize_prices() for, respectively, an already-grouped "parts" map
(group_by_component_type's category -> ware_id -> amount shape) and the
unexpanded top-level target list (which summarize() itself never groups,
since it doesn't apply there -- categorize_target_wares() does the same
per-item resolution summarize() uses, just without any expansion). Both
return one summarize_prices()-shaped result per category rather than a
single combined one, mirroring group_by_component_type's own "parts"
polymorphism (flat vs. category-keyed) instead of introducing a separate
shape.
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from generate_ships_table import BUILD_METHODS

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "x4.db"

# The full, ordered list of real build methods (see BUILD_METHODS' own
# comment in generate_ships_table.py for how it was curated/ordered) --
# tried in this order for every ware, one whole call's worth of priority
# (see resolve_method()/summarize()). Re-exported under this name since
# every caller (api.py, this module's own CLI, summarize()'s default
# parameter) refers to it this way.
DEFAULT_BUILD_METHOD_PRIORITY = BUILD_METHODS
DEFAULT_SEARCH_DEPTH = 1
ABSOLUTE_MAX_DEPTH = 100
# group_by_component_type's catch-all category for any target ware_id not
# found in any of fetch_ware_categories' source tables.
DEFAULT_CATEGORY = "production_wares"


def load_input(source: str) -> dict:
    text = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
    return json.loads(text)


def aggregate_target_wares(configurations: list[dict]) -> list[dict]:
    """Flatten the input's "wares" configurations -- each a {"count",
    "wares_list"} group (e.g. one ship plus all of its equipment) -- into
    the single flat list of {"ware_id", "amount"} (plus "category" when at
    least one contributing item specified one -- see below) the rest of
    the pipeline expects. Every ware in a configuration's wares_list has
    its amount multiplied by that configuration's count (defaulting to 1
    if omitted), then summed across every configuration and ware entry --
    so "5 of ship A" and "10 of ship B" combine into one shopping list,
    with matching ware_ids (e.g. a turret type both ships use) summed
    together rather than listed twice.

    Software wares (ware_id prefixed "software_") pass through here like
    any other ware -- they're still priced (see PRICE_WARE_TABLES), just
    excluded from "parts" downstream in summarize() itself rather than
    here, so a caller pricing this *unexpanded* list directly (api.py's
    POST /api/price_summary "top_level" tier, priced straight off this
    function's own output with no involvement from summarize() at all)
    still sees them.

    A wares_list item's optional "category" (see this module's docstring)
    is part of the merge key alongside ware_id -- two items with the same
    ware_id but different "category" overrides are kept as separate
    output entries rather than summed together, since they're meant to
    land in different group_by_component_type buckets. Items that both
    omit "category" (the overwhelming majority) still merge exactly as
    before.
    """
    totals: dict[tuple[str, str | None], float] = {}
    for config in configurations:
        count = config.get("count", 1)
        for item in config["wares_list"]:
            key = (item["ware_id"], item.get("category"))
            totals[key] = totals.get(key, 0) + item["amount"] * count
    result = []
    for (ware_id, category), amount in totals.items():
        entry = {"ware_id": ware_id, "amount": amount}
        if category is not None:
            entry["category"] = category
        result.append(entry)
    return result


def fetch_production_rows(conn: sqlite3.Connection, ware_ids: list[str]) -> list[sqlite3.Row]:
    """One layer of lookup: every (method, input ware, amount) row for each
    target ware, straight from production_wares.
    """
    placeholders = ", ".join("?" for _ in ware_ids)
    query = f"""
        SELECT production_ware_id, production_method, ware, amount, produced_amount
        FROM production_wares
        WHERE production_ware_id IN ({placeholders})
    """
    return conn.execute(query, ware_ids).fetchall()


def fetch_all_production_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Every row in production_wares. Needed once search_depth > 1, since
    which wares might need expanding beyond the top level isn't known until
    they're already being expanded.
    """
    return conn.execute(
        "SELECT production_ware_id, production_method, ware, amount, produced_amount FROM production_wares"
    ).fetchall()


def fetch_ware_categories(conn: sqlite3.Connection) -> dict[str, str]:
    """ware_id -> component-type category, used only when
    group_by_component_type is requested (see this module's docstring).
    ships_base rows are "chassis"; equipment_wares_base rows use their own
    equipment_type column value directly ("engine"/"thruster"/"turret"/
    "weapon"), except "shield" which becomes "main_shield" here --
    "surface_element_shield" is deliberately never produced by this
    function, since a bonus M shield can share the exact same ware_id as
    an ordinary main shield; only a wares_list item's own "category"
    override (applied in summarize(), not here) can distinguish them.
    missiles_base/drones_base/deployables_base/countermeasures_base/
    crew_base/software_base rows are "missile"/"drone"/"deployable"/
    "countermeasure"/"crew"/"software". A ware_id absent from every one of
    these tables simply has no entry here -- summarize() falls back to
    DEFAULT_CATEGORY for it at lookup time rather than this function
    guessing or raising. Note software_base rows are categorized here even
    though summarize() itself never lets a software ware reach "parts" at
    all (see summarize()'s own docstring) -- this categorization is still
    used by api.py's POST /api/price_summary "top_level" tier (see
    categorize_target_wares()), which prices the *unexpanded* target list
    directly and does include software.
    """
    categories: dict[str, str] = {}
    for row in conn.execute("SELECT ware_id FROM ships_base"):
        categories[row["ware_id"]] = "chassis"
    for row in conn.execute("SELECT ware_id, equipment_type FROM equipment_wares_base"):
        equipment_type = row["equipment_type"]
        categories[row["ware_id"]] = "main_shield" if equipment_type == "shield" else equipment_type
    for row in conn.execute("SELECT ware_id FROM missiles_base"):
        categories[row["ware_id"]] = "missile"
    for row in conn.execute("SELECT ware_id FROM drones_base"):
        categories[row["ware_id"]] = "drone"
    for row in conn.execute("SELECT ware_id FROM deployables_base"):
        categories[row["ware_id"]] = "deployable"
    for row in conn.execute("SELECT ware_id FROM countermeasures_base"):
        categories[row["ware_id"]] = "countermeasure"
    for row in conn.execute("SELECT ware_id FROM crew_base"):
        categories[row["ware_id"]] = "crew"
    for row in conn.execute("SELECT ware_id FROM software_base"):
        categories[row["ware_id"]] = "software"
    return categories


PRICE_WARE_TABLES = [
    "ships_base",
    "equipment_wares_base",
    "missiles_base",
    "drones_base",
    "deployables_base",
    "economy_wares_base",
    "countermeasures_base",
    "crew_base",
    "software_base",
]


def fetch_ware_prices(conn: sqlite3.Connection) -> dict[str, dict[str, float]]:
    """ware_id -> {"price_min", "price_avg", "price_max"}, read directly
    off each ware-defining table's own price columns -- ships_base,
    equipment_wares_base, missiles_base, drones_base, deployables_base,
    economy_wares_base (raw/refined materials like energycells,
    hullparts), countermeasures_base, crew_base, and software_base all
    carry the same three columns (see PRICE_WARE_TABLES). This is a flat, one-shot
    lookup with no involvement from production_wares at all -- unlike
    summarize()'s recursive expansion, a ware's price here is exactly
    whatever the game data says it is, never derived from its components.
    A ware_id absent from every one of these tables simply has no entry
    here; callers (see summarize_prices()) treat that as "price unknown"
    rather than assuming zero.
    """
    prices: dict[str, dict[str, float]] = {}
    for table in PRICE_WARE_TABLES:
        for row in conn.execute(f"SELECT ware_id, price_min, price_avg, price_max FROM {table}"):
            prices[row["ware_id"]] = {
                "price_min": row["price_min"],
                "price_avg": row["price_avg"],
                "price_max": row["price_max"],
            }
    return prices


def fetch_all_wares(conn: sqlite3.Connection, lang: str = "en") -> list[dict]:
    """Every ware across PRICE_WARE_TABLES with its own name/price_min/
    price_avg/price_max, as a flat list -- the "browse everything" view
    used by api.py's GET /api/wares (the price-override picker, and the
    Ware Cost List's ware_id -> name lookup), as opposed to
    fetch_ware_prices()'s ware_id-keyed lookup shape. A ware_id appearing
    in more than one table (shouldn't normally happen) yields one row per
    table rather than being deduplicated, since each table's row is
    independently that table's own idea of this ware's price.

    "name" is resolved against localized_strings the same way as every
    other endpoint this session (COALESCE, falling back to the table's own
    base English name when lang has no row for this ware_id).
    """
    wares: list[dict] = []
    for table in PRICE_WARE_TABLES:
        rows = conn.execute(
            f"""
            SELECT {table}.ware_id AS ware_id,
                   COALESCE(localized_strings.text, {table}.name) AS name,
                   {table}.price_min AS price_min,
                   {table}.price_avg AS price_avg,
                   {table}.price_max AS price_max
            FROM {table}
            LEFT JOIN localized_strings
                ON localized_strings.ware_id = {table}.ware_id
                AND localized_strings.lang_id = ?
            """,
            (lang,),
        )
        for row in rows:
            wares.append(
                {
                    "ware_id": row["ware_id"],
                    "name": row["name"],
                    "price_min": row["price_min"],
                    "price_avg": row["price_avg"],
                    "price_max": row["price_max"],
                }
            )
    return wares


def summarize_prices(
    parts: dict[str, float],
    ware_prices: dict[str, dict[str, float]],
    price_overrides: dict[str, float] | None = None,
) -> dict:
    """Monetary total for a ware cost list's "parts" (a flat ware_id ->
    amount map, exactly as summarize() already produced it) -- multiplies
    each ware's amount by its price and sums across the whole list. Pure
    lookup and arithmetic, no recursion and no re-expansion of anything:
    "parts" is taken completely at face value, whatever depth/build_method_
    priority it was originally computed with.

    price_overrides is an optional ware_id -> price map. When a ware_id
    has an entry here, that single price is used in place of its price_min/
    price_avg/price_max alike for this ware -- a full substitute for all
    three, not a per-tier override -- e.g. for a ware whose in-game price
    range doesn't reflect what the player actually pays for it.

    A ware_id present in "parts" but absent from both ware_prices and
    price_overrides contributes nothing to any total and is listed in
    "missing_prices" instead of being silently treated as free.
    """
    price_overrides = price_overrides or {}
    total_min = 0.0
    total_avg = 0.0
    total_max = 0.0
    missing_prices: list[str] = []

    for ware_id, amount in parts.items():
        if ware_id in price_overrides:
            price = price_overrides[ware_id]
            total_min += price * amount
            total_avg += price * amount
            total_max += price * amount
            continue

        prices = ware_prices.get(ware_id)
        if prices is None:
            missing_prices.append(ware_id)
            continue

        total_min += prices["price_min"] * amount
        total_avg += prices["price_avg"] * amount
        total_max += prices["price_max"] * amount

    return {
        "total_min": round(total_min, 2),
        "total_avg": round(total_avg, 2),
        "total_max": round(total_max, 2),
        "missing_prices": sorted(missing_prices),
    }


def summarize_prices_by_category(
    parts_by_category: dict[str, dict[str, float]],
    ware_prices: dict[str, dict[str, float]],
    price_overrides: dict[str, float] | None = None,
) -> dict[str, dict]:
    """Like summarize_prices(), but for group_by_component_type's grouped
    parts shape (category -> ware_id -> amount) instead of a flat map --
    one independent summarize_prices() call per category, so a ware's
    price is only ever summed within its own category, never across
    categories (matching how summarize()'s own "ware_count" still counts a
    ware once per category it appears under, not merged into one total).
    """
    return {
        category: summarize_prices(category_parts, ware_prices, price_overrides)
        for category, category_parts in parts_by_category.items()
    }


def categorize_target_wares(
    target_wares: list[dict], category_by_ware: dict[str, str] | None = None
) -> dict[str, dict[str, float]]:
    """Buckets a flat target_wares list (aggregate_target_wares' own
    output) into category -> (ware_id -> amount), using the exact same
    per-item resolution rule summarize() itself uses for
    group_by_component_type -- an explicit "category" override on the
    item, else category_by_ware's DB-driven default, else DEFAULT_CATEGORY
    -- but without any of summarize()'s recursive expansion. This is for
    pricing the *unexpanded* top-level list directly (see api.py's
    POST /api/price_summary and its "top_level" tier) by component type,
    the same way summarize_prices_by_category() prices an already-expanded
    "parts" map.
    """
    category_by_ware = category_by_ware or {}
    buckets: dict[str, dict[str, float]] = {}
    for target in target_wares:
        category = target.get("category") or category_by_ware.get(target["ware_id"], DEFAULT_CATEGORY)
        bucket = buckets.setdefault(category, {})
        bucket[target["ware_id"]] = bucket.get(target["ware_id"], 0) + target["amount"]
    return buckets


def build_index(rows: list[sqlite3.Row]) -> tuple[dict[tuple[str, str], list[sqlite3.Row]], dict[str, set[str]]]:
    by_ware_method: dict[tuple[str, str], list[sqlite3.Row]] = {}
    methods_by_ware: dict[str, set[str]] = {}
    for row in rows:
        key = (row["production_ware_id"], row["production_method"])
        by_ware_method.setdefault(key, []).append(row)
        methods_by_ware.setdefault(row["production_ware_id"], set()).add(row["production_method"])
    return by_ware_method, methods_by_ware


def find_method(available_methods: set[str], wanted: str) -> str | None:
    wanted_lower = wanted.lower()
    return next((m for m in available_methods if m.lower() == wanted_lower), None)


def resolve_method(
    ware_id: str,
    available_methods: set[str],
    priority_methods: list[str],
    depth: int,
) -> tuple[str | None, dict | None]:
    """Try priority_methods in order, first available match wins. Only
    returns a log entry (a non-None `entry`) when an actual substitution
    happened -- a lower-priority method stood in because priority_methods[0]
    itself wasn't available. A direct hit (the top-priority method itself
    was available) or a total failure (nothing in the list matched,
    including an empty list) both return `entry=None`: neither is a
    substitution, so there's nothing to log, even though the caller still
    needs used_method to know what happened.
    """
    if not priority_methods:
        return None, None

    top_priority = priority_methods[0]
    match = find_method(available_methods, top_priority)
    if match is not None:
        return match, None

    fallback_match = next(
        (m for fb in priority_methods[1:] if (m := find_method(available_methods, fb)) is not None), None
    )
    if fallback_match is not None:
        return fallback_match, {
            "ware_id": ware_id,
            "requested_method": top_priority,
            "used_method": fallback_match,
            "depth": depth,
        }

    return None, None


def expand_ware(
    ware_id: str,
    amount: float,
    priority_methods: list[str],
    by_ware_method: dict[tuple[str, str], list[sqlite3.Row]],
    methods_by_ware: dict[str, set[str]],
    depth: int,
    ancestors: frozenset[str],
    depth_limit: int,
) -> tuple[dict[str, float], list[dict]]:
    """Recursively expand one ware into its terminal (leaf,
    priority-exhausted, cycle-stopped, or depth-limited) requirements,
    using `priority_methods` -- the *original* requested priority list,
    unchanged across the whole recursion -- to resolve this ware's own
    build method. `depth` is the layer `ware_id` itself belongs to (1 = a
    direct component of the top-level target, 2 = a component of one of
    those, etc.) -- it's what any substitution log entry for *this* ware's
    own resolution is tagged with. Returns (contributions,
    resolution_log_entries): only an actual substitution (a method other
    than priority_methods[0] stood in for it) adds a log entry -- a plain
    leaf ware, a direct hit, a priority-exhausted ware, a cycle, and
    hitting depth_limit are all terminal outcomes that still contribute to
    the totals but are common/uninteresting enough not to log.
    """
    available_methods = methods_by_ware.get(ware_id)

    if not available_methods:
        return {ware_id: amount}, []

    if ware_id in ancestors:
        return {ware_id: amount}, []

    if depth >= depth_limit:
        return {ware_id: amount}, []

    used_method, entry = resolve_method(ware_id, available_methods, priority_methods, depth)
    if used_method is None:
        return {ware_id: amount}, []

    rows_for_method = by_ware_method[(ware_id, used_method)]
    produced_amount = rows_for_method[0]["produced_amount"]
    scale = amount / produced_amount

    contributions: dict[str, float] = {}
    log = [entry] if entry is not None else []
    next_ancestors = ancestors | {ware_id}
    for row in rows_for_method:
        sub_contributions, sub_log = expand_ware(
            row["ware"],
            row["amount"] * scale,
            priority_methods,
            by_ware_method,
            methods_by_ware,
            depth + 1,
            next_ancestors,
            depth_limit,
        )
        for ware, qty in sub_contributions.items():
            contributions[ware] = contributions.get(ware, 0) + qty
        log.extend(sub_log)

    return contributions, log


def summarize(
    target_wares: list[dict],
    rows: list[sqlite3.Row],
    build_method_priority: list[str] | None = None,
    search_depth: int = DEFAULT_SEARCH_DEPTH,
    verbose: bool = True,
    group_by_component_type: bool = False,
    category_by_ware: dict[str, str] | None = None,
) -> dict:
    """Resolves to at most one build method per call, never a comparison
    across several -- build_method_priority names one *ranked list* to try
    (first available match wins, per ware), not several independent choices
    to compare. This mirrors the frontend's own one-priority-list-per-
    comparison-column model (see app.js's Build Method modal) -- comparing
    different priority orderings means comparing different *columns*, each
    configured with its own build_method_priority, not multiple method
    buckets stacked inside a single column/request.
    """
    build_method_priority = (
        build_method_priority if build_method_priority is not None else DEFAULT_BUILD_METHOD_PRIORITY
    )

    depth_limit = min(search_depth, ABSOLUTE_MAX_DEPTH)
    by_ware_method, methods_by_ware = build_index(rows)
    # Only consulted when group_by_component_type is true -- a caller that
    # doesn't pass one (or doesn't need to, with grouping off) still works,
    # every lookup just falls back to DEFAULT_CATEGORY.
    category_by_ware = category_by_ware or {}

    # Either a flat ware_id -> amount map (group_by_component_type false) or
    # a category -> (ware_id -> amount) map (true) -- the `target_bucket =
    # ...` line below is what actually picks which shape gets written to,
    # everything else treats "bucket" as an opaque accumulator. Stays empty
    # (and so does resolution_log) when build_method_priority is itself
    # empty -- nothing to resolve against at all, every target ware becomes
    # a leaf below.
    bucket: dict = {}
    resolution_log: list[dict] = []
    leaf_wares: list[tuple[str, float, str]] = []

    for target in target_wares:
        ware_id = target["ware_id"]
        amount = target["amount"]

        # Software wares (ware_id prefixed "software_" -- the same
        # convention generate_ships_table.py's SOFTWARE_WARE_RE relies on)
        # are a UI-only equipment choice (see query_ship_components.py's
        # "Software" docstring section) with no production recipe of
        # their own -- production_wares has zero rows for any of them,
        # since the game data itself requires no raw materials to obtain
        # one. Without this check they'd fall through to the leaf-ware
        # handling below and leak their own literal ware_id (e.g.
        # "software_trademk1: 1") into "parts" as if it were a raw
        # material still needing to be sourced, alongside genuine
        # production targets like the ship and its hardware components.
        # They're still priced -- just at the *unexpanded* top-level tier
        # (api.py's POST /api/price_summary "top_level", priced directly
        # off aggregate_target_wares()'s own output, never through here)
        # rather than counted as a part of anything.
        if ware_id.startswith("software_"):
            continue

        # Decided once per top-level target ware and carried through its
        # whole expansion -- see the module docstring's
        # "group_by_component_type" section. Looked up unconditionally
        # (cheap dict access) even when grouping is off, since it costs
        # nothing to compute and keeps leaf_wares' shape uniform either way.
        # An explicit per-item override (target.get("category"), set by
        # aggregate_target_wares from a wares_list item's own "category")
        # always wins over the DB-driven default -- it's the only way to
        # tell apart two uses of the same ware_id (e.g. a surface element
        # shield vs. an ordinary main shield of the same type).
        category = target.get("category") or category_by_ware.get(ware_id, DEFAULT_CATEGORY)

        available_methods = methods_by_ware.get(ware_id)
        used_method = None
        if available_methods and build_method_priority:
            used_method, entry = resolve_method(ware_id, available_methods, build_method_priority, 0)
            if entry is not None:
                resolution_log.append(entry)

        if used_method is None:
            # A plain leaf ware (no production recipe at all, under any
            # method), or this priority list simply doesn't cover it --
            # either way, required exactly as-is.
            leaf_wares.append((ware_id, amount, category))
            continue

        # With grouping off, every contribution lands directly in `bucket`
        # (the original flat shape); with grouping on, this target ware's
        # whole expansion lands in `bucket[category]` instead --
        # `target_bucket` is what the accumulation loop below actually
        # writes into either way.
        target_bucket = bucket.setdefault(category, {}) if group_by_component_type else bucket

        rows_for_method = by_ware_method[(ware_id, used_method)]
        produced_amount = rows_for_method[0]["produced_amount"]
        scale = amount / produced_amount
        next_ancestors = frozenset({ware_id})
        for row in rows_for_method:
            contributions, log = expand_ware(
                row["ware"],
                row["amount"] * scale,
                build_method_priority,
                by_ware_method,
                methods_by_ware,
                1,
                next_ancestors,
                depth_limit,
            )
            for ware, qty in contributions.items():
                target_bucket[ware] = target_bucket.get(ware, 0) + qty
            resolution_log.extend(log)

    # Leaf target wares (no recipe at all, or fallback-exhausted) are
    # required exactly as-is -- summed with any existing entry for that
    # same ware rather than listed separately.
    for ware_id, amount, category in leaf_wares:
        target_bucket = bucket.setdefault(category, {}) if group_by_component_type else bucket
        target_bucket[ware_id] = target_bucket.get(ware_id, 0) + amount

    # Rounded only here, once, on the fully-accumulated totals -- rounding
    # after every individual addition would compound small errors instead.
    result = {"build_method_priority": build_method_priority}
    if build_method_priority:
        if group_by_component_type:
            parts = {
                category: {ware: round(qty, 2) for ware, qty in category_bucket.items()}
                for category, category_bucket in bucket.items()
                if category_bucket  # omit a category with zero contributions rather than an empty map
            }
            # Distinct ware_ids across the whole bucket, same meaning as
            # the flat-mode count below even though a given ware_id can
            # legitimately appear under more than one category (e.g. a raw
            # material needed by both engines and shields).
            ware_count = len({ware for category_bucket in bucket.values() for ware in category_bucket})
        else:
            parts = {ware: round(qty, 2) for ware, qty in bucket.items()}
            ware_count = len(bucket)

        result["parts"] = parts
        result["ware_count"] = ware_count
        if verbose:
            result["resolution_log"] = resolution_log

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", help="Path to input JSON file, or '-' to read from stdin")
    args = parser.parse_args()

    payload = load_input(args.input)
    build_method_priority = payload.get("build_method_priority", DEFAULT_BUILD_METHOD_PRIORITY)
    search_depth = payload.get("search_depth", DEFAULT_SEARCH_DEPTH)
    verbose = payload.get("verbose", True)
    group_by_component_type = payload.get("group_by_component_type", False)
    target_wares = aggregate_target_wares(payload["wares"])

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        # Always the full table, even at search_depth=1: production_wares is
        # tiny (a few hundred rows), and fetching only the target wares'
        # rows would make resolution_log's "leaf ware (no production
        # recipe)" note for a one-layer request inaccurate for any ware
        # that has a recipe but just wasn't looked up -- it would look
        # identical to a genuine leaf.
        rows = fetch_all_production_rows(conn)
        # Only worth querying when actually needed -- summarize() falls
        # back to DEFAULT_CATEGORY for everything if this is left None.
        category_by_ware = fetch_ware_categories(conn) if group_by_component_type else None
    finally:
        conn.close()

    result = summarize(
        target_wares, rows, build_method_priority, search_depth, verbose, group_by_component_type, category_by_ware
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
