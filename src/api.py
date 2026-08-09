"""FastAPI backend for the X4 fleet planner UI. Wraps the existing
summarize_production.py / query_ship_components.py logic as HTTP
endpoints -- no business logic lives here, it's a thin adapter.

Run directly: `python src/api.py` (serves on http://127.0.0.1:8000).
The frontend (src/static/) is served at "/"; the API is under "/api/...".

Endpoints:
  GET  /api/ships                        -- list every ship for a picker.
                                             Each row's "icon" (e.g.
                                             "ship_s_fighter_01", from
                                             ships_base.icon) names a PNG
                                             served under /images/ships/
                                             symbols/<icon>.png (mounted
                                             below) -- see
                                             generate_ship_icons.py
  GET  /api/ships/{identifier}/groups    -- query_ship_groups() as JSON
  GET  /api/missiles                     -- list every missile (ware_id/
                                             name/compatibility), for the
                                             frontend to filter client-side
                                             against whichever launchers'
                                             ammunition_tags are currently
                                             selected -- see the "Missiles
                                             and deployables" docstring
                                             section in
                                             generate_ships_table.py
  GET  /api/drones                       -- list every drone (ware_id/
                                             name); unlike missiles, no
                                             per-launcher compatibility
                                             concept -- any drone can fill
                                             a ship's shared drone_capacity
                                             pool (ships_base.drone_capacity,
                                             see the "Drones" docstring
                                             section in
                                             generate_ships_table.py)
  GET  /api/deployables                  -- list every deployable (ware_id/
                                             name/deployable_type); same
                                             "shared pool" shape as drones,
                                             except the game data has no
                                             per-ship deployable capacity
                                             stat at all -- the frontend
                                             assumes a fixed default by
                                             ship size (DEPLOYABLE_CAPACITY_
                                             BY_SIZE in app.js: 50/100/250/
                                             450 for S/M/L/XL) rather than
                                             something this API returns
  GET  /api/countermeasures               -- list every countermeasure
                                             (ware_id/name) -- just "Flares"
                                             in the base game. Same "shared
                                             pool, no per-ship capacity
                                             stat" situation as deployables
                                             -- the frontend assumes a fixed
                                             default by ship size
                                             (COUNTERMEASURE_CAPACITY_BY_SIZE
                                             in app.js) -- see the
                                             "Countermeasures and crew"
                                             docstring section in
                                             generate_ships_table.py
  GET  /api/crew                         -- list the single "crew" ware
                                             (ware_id/name); the shared pool
                                             it fills is ships_base.crew
                                             (query_ship_groups()'s own
                                             summary.crew_capacity), a real
                                             per-ship column unlike
                                             countermeasures/deployables
  GET  /api/build_methods                 -- every real build method
                                             (DEFAULT_FALLBACK_METHODS --
                                             see BUILD_METHODS in
                                             generate_ships_table.py for how
                                             it was curated/ordered), for
                                             the frontend's build-focus
                                             dropdown and its per-column
                                             editable fallback-methods list
                                             (defaults to this same list)
  POST /api/summarize                    -- aggregate_target_wares() +
                                             summarize(), same input shape
                                             as the CLI's input JSON files
  POST /api/price_summary                -- three independent monetary
                                             totals for the same cart, all
                                             self-contained (recomputed
                                             here from "wares" directly,
                                             not dependent on whatever
                                             search_depth a prior
                                             /api/summarize call used) and
                                             deliberately never added
                                             together, since each answers a
                                             different question:
                                               "top_level" -- every
                                                 top-level item (the ship
                                                 hull, each piece of
                                                 equipment) priced at its
                                                 own market price, no
                                                 expansion at all ("buy it
                                                 outright")
                                               "production_wares" -- each
                                                 top-level item's own
                                                 direct recipe inputs
                                                 (summarize() at
                                                 search_depth=1) priced
                                                 directly -- "buy what the
                                                 shipyard itself consumes"
                                               "raw_materials" -- fully
                                                 expanded down to true leaf
                                                 wares (summarize() at
                                                 ABSOLUTE_MAX_DEPTH,
                                                 independent of any
                                                 configured search_depth)
                                                 -- "build everything from
                                                 scratch"
                                             production_wares/raw_materials
                                             are per build method (like
                                             /api/summarize's own
                                             "methods"); top_level is a
                                             single total, since no method
                                             resolution is involved. Also
                                             takes its own
                                             group_by_component_type flag
                                             (same semantics as
                                             /api/summarize's) -- when set,
                                             every tier's own total(s)
                                             become one summarize_prices()
                                             result per component-type
                                             category instead of one
                                             combined number, mirroring how
                                             /api/summarize's own "parts"
                                             turns from a flat map into a
                                             category-keyed one. See
                                             summarize_production.py's
                                             "Monetary cost analysis"
                                             docstring section.
  POST /api/level1_parts                  -- for each given ware_id, its
                                             own direct (depth-1) recipe
                                             inputs, resolved independently
                                             (not summed across the
                                             list like /api/summarize
                                             does) -- one summarize() call
                                             per ware_id. Powers the
                                             equipment picker modal's
                                             dynamic "level 1 wares"
                                             columns (see app.js's
                                             openEquipmentPickerModal()).
  POST /api/import_loadouts               -- parses a player's saved
                                             loadouts.xml (either a
                                             server-side `path` or
                                             already-read `xml_text`) into
                                             this app's own cart-entry
                                             shape -- see
                                             import_loadouts.py's module
                                             docstring for the schema this
                                             wraps and how each field maps
                                             across. Read-only: never
                                             writes to the input file.
                                             Station-module loadouts
                                             (macro not a real ship) are
                                             silently skipped; every real
                                             ship loadout comes back with
                                             its own "warnings" list for
                                             anything that couldn't be
                                             matched exactly.
  POST /api/build_saved_loadout            -- the "Add to Saved Loadouts"
                                             button's entry point: builds a
                                             fresh loadout entry (same shape
                                             POST /api/import_loadouts
                                             returns per ship, including a
                                             generated "player_<10 digits>"
                                             id and a synthesized rawXml --
                                             see import_loadouts.py's
                                             build_loadout_xml() docstring
                                             for the one way this differs
                                             from a real imported loadout's
                                             rawXml) from the current ship-
                                             builder state, so it can be
                                             merged into the frontend's
                                             existing imported-loadouts
                                             working set exactly like an
                                             imported one.

Intentionally local-only for now (no auth, permissive by default since
everything is served from the same origin) -- see the module docstring in
summarize_production.py/query_ship_components.py for the actual production
logic this wraps.
"""

import sqlite3
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from import_loadouts import build_saved_loadout_entry, parse_loadouts_xml
from query_ship_components import query_ship_groups
from summarize_production import (
    ABSOLUTE_MAX_DEPTH,
    DEFAULT_FALLBACK_METHODS,
    DEFAULT_SEARCH_DEPTH,
    aggregate_target_wares,
    categorize_target_wares,
    fetch_all_production_rows,
    fetch_ware_categories,
    fetch_ware_prices,
    summarize,
    summarize_prices,
    summarize_prices_by_category,
)

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "x4.db"
STATIC_DIR = Path(__file__).resolve().parent / "static"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


class WaresListItem(BaseModel):
    ware_id: str
    amount: float
    category: str | None = None


class WaresConfiguration(BaseModel):
    count: int = 1
    wares_list: list[WaresListItem]


class SummarizeRequest(BaseModel):
    build_focus: str | None = None
    fallback_methods: list[str] | None = None
    search_depth: int = DEFAULT_SEARCH_DEPTH
    verbose: bool = True
    group_by_component_type: bool = False
    wares: list[WaresConfiguration]


class PriceSummaryRequest(BaseModel):
    # The cart itself -- same shape as SummarizeRequest.wares. All three
    # response tiers are derived from this directly; unlike the old design,
    # nothing here is taken from a prior /api/summarize call.
    wares: list[WaresConfiguration]
    # Same build_focus/fallback_methods semantics as SummarizeRequest --
    # used for the production_wares/raw_materials tiers' own method
    # resolution (top_level needs neither, it's a direct price lookup).
    build_focus: str | None = None
    fallback_methods: list[str] | None = None
    # Same semantics as SummarizeRequest's own flag: false (the default)
    # prices each tier as one combined total; true prices each tier *by
    # component type* instead -- see summarize_prices_by_category()/
    # categorize_target_wares() in summarize_production.py.
    group_by_component_type: bool = False
    # ware_id -> price, substituted for that ware's price_min/price_avg/
    # price_max alike wherever it appears, across all three tiers.
    price_overrides: dict[str, float] | None = None


class Level1PartsRequest(BaseModel):
    ware_ids: list[str]
    build_focus: str | None = None
    fallback_methods: list[str] | None = None


class ImportLoadoutsRequest(BaseModel):
    # Exactly one of these two is expected -- `path` reads the file
    # server-side (the "path to a loadout file" case, e.g. pasting in
    # Documents\Egosoft\X4\<id>\loadouts.xml directly, convenient since
    # this app only ever runs locally on the same machine as the game);
    # `xml_text` is already-read XML text -- either a full file's contents
    # (the "upload a file" case, read client-side via the browser's File
    # API since a browser can't hand the server an arbitrary local path
    # itself) or a hand-pasted <loadout>/<loadouts> snippet (the "Import
    # raw XML loadout" case -- see parse_loadouts_xml()'s bare-<loadout>-
    # root handling). If both are given, `path` wins.
    path: str | None = None
    xml_text: str | None = None


class BuildSavedLoadoutRequest(BaseModel):
    # Mirrors the ship-builder state the frontend already holds (see
    # addToCartBtn's own gathering of the same fields in app.js) -- the
    # "Add to Saved Loadouts" button's request body. selections is keyed
    # "<group_name>::<component_type>" -> ware_id, same shape
    # parse_ship_loadout() produces on the import side.
    shipWareId: str
    name: str
    selections: dict[str, str] = {}
    missileAmounts: dict[str, int] = {}
    droneAmounts: dict[str, int] = {}
    deployableAmounts: dict[str, int] = {}
    countermeasureAmounts: dict[str, int] = {}
    crewAmounts: dict[str, int] = {}


app = FastAPI(title="X4 Fleet Planner")


# The DB gets rebuilt out-of-band (rerunning generate_ships_table.py) far
# more often than this app restarts during dev -- explicitly disabling
# caching on every /api/... response avoids a stale ship/groups payload
# ever surviving a page refresh, no matter what a browser's default
# heuristics would otherwise do with an unmarked response.
@app.middleware("http")
async def no_cache_api_responses(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/ships")
def list_ships() -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT name, ware_id, size, ship_type, owners, icon FROM ships_base ORDER BY name"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


@app.get("/api/ships/{identifier}/groups")
def ship_groups(identifier: str) -> dict:
    conn = get_connection()
    try:
        return query_ship_groups(conn, identifier)
    finally:
        conn.close()


@app.get("/api/missiles")
def list_missiles() -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT ware_id, name, compatibility FROM missiles_base ORDER BY name").fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


@app.get("/api/drones")
def list_drones() -> list[dict]:
    conn = get_connection()
    try:
        # UI-only exclusion: faction-specific police drones (ware_id
        # prefixed "ship_<faction>_", e.g. "ship_arg_xs_police_01_a") are
        # dropped from the picker's offered list, keeping only the generic
        # "ship_gen_" ones (fighting/mining/building/cargo/repair) --
        # drones_base itself still has all 13 rows, this only narrows what
        # the UI shows as addable.
        rows = conn.execute(
            "SELECT ware_id, name FROM drones_base WHERE ware_id LIKE 'ship_gen_%' ORDER BY name"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


@app.get("/api/deployables")
def list_deployables() -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT ware_id, name, deployable_type FROM deployables_base ORDER BY name"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


@app.get("/api/countermeasures")
def list_countermeasures() -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT ware_id, name FROM countermeasures_base ORDER BY name").fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


@app.get("/api/crew")
def list_crew() -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT ware_id, name FROM crew_base ORDER BY name").fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


@app.get("/api/build_methods")
def list_build_methods() -> list[str]:
    return DEFAULT_FALLBACK_METHODS


@app.post("/api/summarize")
def summarize_endpoint(request: SummarizeRequest) -> dict:
    configurations = [config.model_dump() for config in request.wares]
    target_wares = aggregate_target_wares(configurations)
    fallback_methods = request.fallback_methods if request.fallback_methods is not None else DEFAULT_FALLBACK_METHODS

    conn = get_connection()
    try:
        rows = fetch_all_production_rows(conn)
        category_by_ware = fetch_ware_categories(conn) if request.group_by_component_type else None
    finally:
        conn.close()

    return summarize(
        target_wares,
        rows,
        request.build_focus,
        fallback_methods,
        request.search_depth,
        request.verbose,
        request.group_by_component_type,
        category_by_ware,
    )


def _price_methods(
    target_wares,
    rows,
    build_focus,
    fallback_methods,
    search_depth,
    ware_prices,
    price_overrides,
    group_by_component_type,
    category_by_ware,
):
    """summarize() at a given depth, then prices each resulting method
    bucket's "parts" -- flat (summarize_prices()) or, when
    group_by_component_type is set, by category (summarize_prices_by_
    category()), mirroring "parts" itself being either a flat ware_id ->
    amount map or a category -> ware_id -> amount map. Shared by the
    production_wares (depth=1) and raw_materials (depth=ABSOLUTE_MAX_DEPTH)
    tiers below, which differ only in which depth they ask summarize() for.
    """
    result = summarize(
        target_wares, rows, build_focus, fallback_methods, search_depth, False, group_by_component_type, category_by_ware
    )
    if group_by_component_type:
        return {
            method: summarize_prices_by_category(data["parts"], ware_prices, price_overrides)
            for method, data in result["methods"].items()
        }
    return {
        method: summarize_prices(data["parts"], ware_prices, price_overrides)
        for method, data in result["methods"].items()
    }


@app.post("/api/price_summary")
def price_summary_endpoint(request: PriceSummaryRequest) -> dict:
    configurations = [config.model_dump() for config in request.wares]
    target_wares = aggregate_target_wares(configurations)
    fallback_methods = request.fallback_methods if request.fallback_methods is not None else DEFAULT_FALLBACK_METHODS

    conn = get_connection()
    try:
        ware_prices = fetch_ware_prices(conn)
        rows = fetch_all_production_rows(conn)
        category_by_ware = fetch_ware_categories(conn) if request.group_by_component_type else None
    finally:
        conn.close()

    # Market Purchase Price: every top-level item priced at its own market
    # price directly, no expansion or method resolution involved at all.
    if request.group_by_component_type:
        top_level_by_category = categorize_target_wares(target_wares, category_by_ware)
        top_level_summary = summarize_prices_by_category(top_level_by_category, ware_prices, request.price_overrides)
    else:
        # aggregate_target_wares keeps (ware_id, category) pairs separate
        # (needed by summarize()'s group_by_component_type), but a flat
        # price total doesn't depend on category -- merge back down to a
        # flat ware_id -> amount total first, so e.g. a shield used as
        # both a main and surface element shield is still priced as one
        # combined quantity.
        top_level_totals: dict[str, float] = {}
        for target in target_wares:
            top_level_totals[target["ware_id"]] = top_level_totals.get(target["ware_id"], 0) + target["amount"]
        top_level_summary = summarize_prices(top_level_totals, ware_prices, request.price_overrides)

    # Production Wares Price: each top-level item's own direct recipe
    # inputs (exactly what search_depth=1 already means -- see
    # summarize_production.py's docstring), priced directly rather than
    # expanded any further.
    production_wares_summary = _price_methods(
        target_wares,
        rows,
        request.build_focus,
        fallback_methods,
        1,
        ware_prices,
        request.price_overrides,
        request.group_by_component_type,
        category_by_ware,
    )

    # Raw Materials Price: fully expanded down to true leaf wares,
    # regardless of whatever search_depth a prior /api/summarize call for
    # this same cart used.
    raw_materials_summary = _price_methods(
        target_wares,
        rows,
        request.build_focus,
        fallback_methods,
        ABSOLUTE_MAX_DEPTH,
        ware_prices,
        request.price_overrides,
        request.group_by_component_type,
        category_by_ware,
    )

    return {
        "top_level": top_level_summary,
        "production_wares": production_wares_summary,
        "raw_materials": raw_materials_summary,
    }


@app.post("/api/level1_parts")
def level1_parts_endpoint(request: Level1PartsRequest) -> dict:
    """Each of `request.ware_ids`' own direct (depth-1) recipe inputs,
    resolved independently -- unlike /api/summarize, which combines every
    target ware's expansion into one shared total, this calls summarize()
    once per ware_id (each as its own single-item target list, amount 1)
    specifically so a picker table can show one row per ware_id with that
    ware's own inputs, not a fleet-wide sum. Used by the equipment picker
    modal (see app.js's openEquipmentPickerModal()) to build its dynamic
    "level 1 wares" columns -- one column per distinct ware_id that shows
    up in any row's own parts, so a shield's inputs and a turret's inputs
    don't need to share a column layout.

    Response: {"parts": {ware_id: {part_ware_id: amount, ...}, ...},
    "part_names": {part_ware_id: name, ...}} -- a ware_id with no
    production recipe at all (a true leaf, or one this build_focus/
    fallback_methods combination can't resolve) gets an empty {} rather
    than being omitted, so the caller can still render a row for it.
    part_names covers every part_ware_id that appears in any row, looked
    up from whichever of economy_wares_base/equipment_wares_base actually
    has it (a depth-1 input is normally a raw/economy ware, but doesn't
    have to be).
    """
    fallback_methods = request.fallback_methods if request.fallback_methods is not None else DEFAULT_FALLBACK_METHODS

    conn = get_connection()
    try:
        rows = fetch_all_production_rows(conn)

        parts_by_ware: dict[str, dict[str, float]] = {}
        all_part_ids: set[str] = set()
        for ware_id in request.ware_ids:
            result = summarize([{"ware_id": ware_id, "amount": 1}], rows, request.build_focus, fallback_methods, 1, False)
            method = result["build_focus"]
            parts = result["methods"][method]["parts"] if method and method in result["methods"] else {}
            parts_by_ware[ware_id] = parts
            all_part_ids.update(parts.keys())

        part_names: dict[str, str] = {}
        for table in ("economy_wares_base", "equipment_wares_base", "ships_base"):
            remaining = [pid for pid in all_part_ids if pid not in part_names]
            if not remaining:
                break
            placeholders = ", ".join("?" for _ in remaining)
            for row in conn.execute(
                f"SELECT ware_id, name FROM {table} WHERE ware_id IN ({placeholders})", remaining
            ).fetchall():
                part_names[row["ware_id"]] = row["name"]
    finally:
        conn.close()

    return {"parts": parts_by_ware, "part_names": part_names}


@app.post("/api/import_loadouts")
def import_loadouts_endpoint(request: ImportLoadoutsRequest) -> dict:
    if request.path:
        try:
            xml_text = Path(request.path).read_text(encoding="utf-8-sig")
        except OSError as exc:
            return {"error": f"Could not read '{request.path}': {exc}"}
    elif request.xml_text:
        xml_text = request.xml_text
    else:
        return {"error": "Provide either 'path' or 'xml_text'."}

    conn = get_connection()
    try:
        return parse_loadouts_xml(xml_text, conn)
    except Exception as exc:  # noqa: BLE001 -- malformed/foreign XML shouldn't 500, just report it
        return {"error": f"Could not parse this file as loadouts.xml: {exc}"}
    finally:
        conn.close()


@app.post("/api/build_saved_loadout")
def build_saved_loadout_endpoint(request: BuildSavedLoadoutRequest) -> dict:
    conn = get_connection()
    try:
        return build_saved_loadout_entry(
            conn,
            request.shipWareId,
            request.name,
            request.selections,
            request.missileAmounts,
            request.droneAmounts,
            request.deployableAmounts,
            request.countermeasureAmounts,
            request.crewAmounts,
        )
    finally:
        conn.close()


# Ship-class symbol PNGs (see generate_ship_icons.py) -- served under
# /images/... so the frontend can build an <img src> straight from a
# ships_base.icon value, e.g. /images/ships/symbols/ship_s_fighter_01.png.
# Mounted before the catch-all "/" mount below for the same reason as that
# comment explains: earlier-registered routes/mounts win.
app.mount("/images", StaticFiles(directory=ROOT / "data" / "images"), name="ship_images")

# Mounted last so it doesn't shadow the /api/... routes registered above.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
