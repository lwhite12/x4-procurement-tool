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
                                             generate_ship_icons.py.
                                             "maker_races" (e.g. ["argon"],
                                             occasionally more than one, e.g.
                                             ["argon", "teladi"] -- from the
                                             maker_races table, the ship's
                                             own real design race(s), not
                                             its sales-owner list; see
                                             generate_ships_table.py's
                                             "Design race and race/faction
                                             shortcodes" docstring section)
                                             each name a PNG under
                                             /images/factions/<race_id>.png
                                             -- see generate_faction_icons.py.
                                             Empty for the handful of
                                             raceless drone/utility ships.
                                             "production_method" (e.g.
                                             "Universal", from ships_base.
                                             production_method -- the same
                                             vocabulary GET /api/build_methods
                                             returns) is null for the
                                             handful of unbuildable ships
                                             (Khaak hulls, drop/terraforming
                                             drones) with no production
                                             block at all -- powers the
                                             ship picker's Build Method
                                             filter.
                                             "?lang=de" (any code, default
                                             "en") returns each ship's own
                                             name in that language where a
                                             real translation exists
                                             (localized_strings table --
                                             see generate_ships_table.py's
                                             parse_localized_strings()),
                                             falling back to English
                                             per-ship rather than per-
                                             request. This is game-data
                                             localization -- entirely
                                             separate from the website's
                                             own UI text (src/static/
                                             i18n.js), which this endpoint
                                             has no effect on
  GET  /api/ships/{identifier}/groups    -- query_ship_groups() as JSON.
                                             "?lang=de" works the same way
                                             as /api/ships' own -- the
                                             ship's own name and every
                                             equipment option's name in
                                             every group are both resolved
                                             through it (query_ship_
                                             components.py's resolve_ship()/
                                             matching_items())
  GET  /api/missiles                     -- list every missile (ware_id/
                                             name/compatibility), for the
                                             frontend to filter client-side
                                             against whichever launchers'
                                             ammunition_tags are currently
                                             selected -- see the "Missiles
                                             and deployables" docstring
                                             section in
                                             generate_ships_table.py.
                                             "?lang=de" works the same way
                                             as /api/ships' own
  GET  /api/drones                       -- list every drone (ware_id/
                                             name); unlike missiles, no
                                             per-launcher compatibility
                                             concept -- any drone can fill
                                             a ship's shared drone_capacity
                                             pool (ships_base.drone_capacity,
                                             see the "Drones" docstring
                                             section in
                                             generate_ships_table.py).
                                             "?lang=de" works the same way
                                             as /api/ships' own
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
                                             something this API returns.
                                             "?lang=de" works the same way
                                             as /api/ships' own
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
                                             generate_ships_table.py.
                                             "?lang=de" works the same way
                                             as /api/ships' own
  GET  /api/crew                         -- list the single "crew" ware
                                             (ware_id/name); the shared pool
                                             it fills is ships_base.crew
                                             (query_ship_groups()'s own
                                             summary.crew_capacity), a real
                                             per-ship column unlike
                                             countermeasures/deployables.
                                             "?lang=de" resolves this one
                                             real ware's own name the same
                                             way as /api/ships, but note
                                             app.js's own loadCrew()
                                             immediately overwrites it with
                                             GET /api/crew_roles' own
                                             "Marines"/"Service Crew" split
                                             names instead -- see that
                                             endpoint's own docstring
  GET  /api/crew_roles                    -- crew_role_id -> crew_role_name
                                             for the two real crew-role
                                             codes (crew_roles table -- see
                                             generate_ships_table.py's
                                             parse_crew_roles()/
                                             CREW_ROLE_NAME_REF), for the
                                             ship builder's Marines/Service
                                             Crew rows. "?lang=de" works the
                                             same way as /api/ships' own
  GET  /api/build_methods                 -- every real build method
                                             (DEFAULT_BUILD_METHOD_PRIORITY --
                                             see BUILD_METHODS in
                                             generate_ships_table.py for how
                                             it was curated/ordered), for the
                                             frontend's per-column editable
                                             build-method-priority list
                                             (defaults to this same list)
  GET  /api/factions                      -- faction_id -> faction_name/
                                             faction_shortname for every
                                             real faction (factions table --
                                             see generate_ships_table.py's
                                             parse_factions()), for the ship
                                             picker's owner-faction icon
                                             tooltips and the Vendor filter
                                             group's own labels. "?lang=de"
                                             works the same way as
                                             /api/ships' own -- see that
                                             endpoint's docstring. Confirmed
                                             faction_shortname genuinely
                                             differs by language (unlike
                                             /api/races' own)
  GET  /api/races                         -- race_id -> race_name/
                                             race_shortname for every real
                                             race (races table -- see
                                             generate_ships_table.py's
                                             parse_races()), for the ship
                                             picker's per-ship race badges
                                             (keyed against /api/ships' own
                                             "maker_races") and the Race
                                             filter group's labels.
                                             "?lang=de" works the same way
  GET  /api/purposes                      -- purpose_id -> purpose_name for
                                             every real purpose (purposes
                                             table -- see
                                             generate_ships_table.py's
                                             parse_purposes()), for the ship
                                             picker's Purpose filter labels.
                                             "?lang=de" works the same way
                                             as /api/ships' own
  GET  /api/ship_types                    -- ship_type_id -> ship_type_name
                                             for every real ship_type value
                                             actually present in ships_base
                                             (ship_types table -- see
                                             generate_ships_table.py's
                                             parse_ship_types()/
                                             SHIP_TYPE_NAME_REF), for the
                                             ship picker's Type filter
                                             labels. "?lang=de" works the
                                             same way as /api/ships' own
  GET  /api/build_method_names            -- build_method_name ->
                                             build_method_display_name for
                                             every real build method
                                             (build_methods table -- see
                                             generate_ships_table.py's
                                             parse_build_methods()). Purely
                                             a display-text lookup for the
                                             same stable English keys
                                             GET /api/build_methods returns
                                             unlocalized -- see that
                                             endpoint's own docstring for
                                             why. "?lang=de" works the same
                                             way as /api/ships' own
  GET  /api/source_versions               -- the base game's and every
                                             installed extension's own
                                             version (source_versions table
                                             -- see generate_ships_table.py's
                                             parse_source_versions()), for
                                             the About page's "built from
                                             these versions" section
                                             alongside /api/config's own
                                             tool "version". "?lang=de"
                                             resolves each DLC's display
                                             name (not the base game's own
                                             row, which has no ref) -- see
                                             SOURCE_VERSION_NAME_REF
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
                                             each resolve to the same single
                                             build_method_priority as
                                             /api/summarize; top_level is a
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
                                             Body's "lang" (default "en")
                                             resolves part_names against
                                             localized_strings.
  GET  /api/config                         -- {"remote_mode": bool}, true
                                             when this process is running as
                                             a deployed Fly.io app (detected
                                             via the FLY_APP_NAME env var
                                             Fly sets automatically) rather
                                             than a plain local
                                             `python src/api.py`. Lets the
                                             frontend hide UI that only
                                             makes sense locally -- see
                                             IS_REMOTE below, and
                                             POST /api/import_loadouts'
                                             own use of the same flag for
                                             the actual enforcement.
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
                                             `path` is rejected outright
                                             when IS_REMOTE (it would
                                             otherwise let any visitor read
                                             an arbitrary file off the
                                             server's own filesystem, not
                                             just whichever machine is
                                             running this app locally) --
                                             `xml_text` (the file-upload
                                             path, read client-side via the
                                             browser's File API) is
                                             unaffected either way.
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

Originally local-only; now also deployed publicly (Fly.io) -- see
IS_REMOTE and its one actual enforcement point (POST /api/import_loadouts'
`path` rejection) below for the one endpoint that needed to change
behavior for that. Otherwise still permissive by default (no auth) since
this remains a small, no-login, no-personal-data tool -- see the module
docstring in summarize_production.py/query_ship_components.py for the
actual production logic this wraps.
"""

import json
import os
import sqlite3
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from import_loadouts import build_saved_loadout_entry, parse_loadouts_xml
from query_ship_components import query_ship_groups
from share_storage import get_share, put_share
from summarize_production import (
    ABSOLUTE_MAX_DEPTH,
    DEFAULT_BUILD_METHOD_PRIORITY,
    DEFAULT_SEARCH_DEPTH,
    aggregate_target_wares,
    categorize_target_wares,
    fetch_all_production_rows,
    fetch_all_wares,
    fetch_ware_categories,
    fetch_ware_prices,
    summarize,
    summarize_prices,
    summarize_prices_by_category,
)

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "x4.db"
STATIC_DIR = Path(__file__).resolve().parent / "static"

# FLY_APP_NAME is set automatically by Fly.io on every deployed machine
# (never set for a plain local `python src/api.py`) -- used as the signal
# for "this server is reachable by the public internet, not just its own
# operator." /api/import_loadouts's `path` field lets the caller name any
# file for this server to read off its own filesystem -- fine when the
# server only ever runs on the same machine as whoever's using it (the
# original design), but an arbitrary-file-read hole once deployed
# publicly, since nothing stops any visitor from POSTing an arbitrary path
# directly to the endpoint regardless of what the frontend's UI shows.
# GET /api/config surfaces this to the frontend too, so it can hide the
# path-input field entirely in that mode -- a UX nicety, not the actual
# enforcement (that's the check inside import_loadouts_endpoint() below).
IS_REMOTE = bool(os.environ.get("FLY_APP_NAME"))

# Single source of truth for the app's version -- a plain-text VERSION file
# at the repo root (baked into the Docker image alongside src/ and data/)
# rather than a hardcoded string here, so CHANGELOG.md and this endpoint
# can't drift out of sync with each other.
VERSION = (ROOT / "VERSION").read_text().strip()


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
    build_method_priority: list[str] | None = None
    search_depth: int = DEFAULT_SEARCH_DEPTH
    verbose: bool = True
    group_by_component_type: bool = False
    wares: list[WaresConfiguration]


class PriceSummaryRequest(BaseModel):
    # The cart itself -- same shape as SummarizeRequest.wares. All three
    # response tiers are derived from this directly; unlike the old design,
    # nothing here is taken from a prior /api/summarize call.
    wares: list[WaresConfiguration]
    # Same build_method_priority semantics as SummarizeRequest -- used for
    # the production_wares/raw_materials tiers' own method resolution
    # (top_level needs neither, it's a direct price lookup).
    build_method_priority: list[str] | None = None
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
    build_method_priority: list[str] | None = None
    lang: str = "en"


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


# The three independently-shareable slices of frontend state (see app.js's
# own SHARE_SECTIONS) -- a Literal (not a bare str) so FastAPI 422s on
# anything else automatically, rather than this module needing to validate
# it before ever reaching share_storage.py (which has no opinion on what
# sections exist).
ShareSection = Literal["fleets", "price_overrides", "loadouts"]


class ShareCreateRequest(BaseModel):
    # Deliberately untyped beyond "some JSON object" -- this endpoint has no
    # opinion on any given section's own shape (fleets/priceOverrides/
    # importedLoadoutsResult each look completely different), it's just a
    # blob store. The frontend is the only place that shape is meaningful.
    data: dict


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
def list_ships(lang: str = "en") -> list[dict]:
    """`lang` (default "en", the only language guaranteed correct today --
    see localized_strings' own module-docstring note in
    generate_ships_table.py) left-joins against localized_strings for that
    ware_id/lang_id pair, falling back to ships_base's own English "name"
    whenever no row exists there -- a ware with no real translation for
    the requested language (or a request for a language that was never
    generated at all -- there's no validation against a known-language
    list here, since a garbage/unsupported value just naturally never
    matches any row and safely falls back to English the same way) reads
    as pure English, never a raw {page,id} ref or an error. Sorted by the
    resolved (COALESCEd) name, not always the English one, so a non-English
    ship list is actually alphabetized in that language.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                COALESCE(localized_strings.text, ships_base.name) AS name,
                ships_base.ware_id AS ware_id,
                ships_base.size AS size,
                ships_base.ship_type AS ship_type,
                ships_base.purpose AS purpose,
                ships_base.owners AS owners,
                ships_base.icon AS icon,
                ships_base.production_method AS production_method
            FROM ships_base
            LEFT JOIN localized_strings
                ON localized_strings.ware_id = ships_base.ware_id AND localized_strings.lang_id = ?
            ORDER BY name
            """,
            (lang,),
        ).fetchall()
        ships = [dict(row) for row in rows]

        # A ship's real design race(s) -- see generate_ships_table.py's
        # "Design race and race/faction shortcodes" docstring section.
        # Usually one race_id, occasionally more (e.g. the Envoy is both
        # "argon" and "teladi") -- ordinal preserves makerrace's own listed
        # order. No FK-friendly array type in SQLite, so this is a second
        # query merged in here rather than a single joined row per ship.
        maker_race_rows = conn.execute(
            "SELECT ware_id, race_id FROM maker_races ORDER BY ware_id, ordinal"
        ).fetchall()
        maker_races_by_ware_id: dict[str, list[str]] = {}
        for row in maker_race_rows:
            maker_races_by_ware_id.setdefault(row["ware_id"], []).append(row["race_id"])
        for ship in ships:
            ship["maker_races"] = maker_races_by_ware_id.get(ship["ware_id"], [])

        return ships
    finally:
        conn.close()


@app.get("/api/ships/{identifier}/groups")
def ship_groups(identifier: str, lang: str = "en") -> dict:
    conn = get_connection()
    try:
        return query_ship_groups(conn, identifier, lang)
    finally:
        conn.close()


# Powers the price-override picker -- every ware in the database, not just
# ones appearing in the current procurement list, so the popup can offer
# an override for anything regardless of whether it's in use yet -- and the
# Cost Analysis Ware Cost List's ware_id -> name lookup (see app.js's
# wareNames/loadWareNames()). ?lang=de resolves each ware's name against
# localized_strings, same COALESCE pattern as every other endpoint.
@app.get("/api/wares")
def list_wares(lang: str = "en") -> list[dict]:
    conn = get_connection()
    try:
        return fetch_all_wares(conn, lang)
    finally:
        conn.close()


@app.get("/api/missiles")
def list_missiles(lang: str = "en") -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                missiles_base.ware_id AS ware_id,
                COALESCE(localized_strings.text, missiles_base.name) AS name,
                missiles_base.compatibility AS compatibility
            FROM missiles_base
            LEFT JOIN localized_strings
                ON localized_strings.ware_id = missiles_base.ware_id AND localized_strings.lang_id = ?
            ORDER BY name
            """,
            (lang,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


@app.get("/api/drones")
def list_drones(lang: str = "en") -> list[dict]:
    conn = get_connection()
    try:
        # UI-only exclusion: faction-specific police drones (ware_id
        # prefixed "ship_<faction>_", e.g. "ship_arg_xs_police_01_a") are
        # dropped from the picker's offered list, keeping only the generic
        # "ship_gen_" ones (fighting/mining/building/cargo/repair) --
        # drones_base itself still has all 13 rows, this only narrows what
        # the UI shows as addable.
        rows = conn.execute(
            """
            SELECT
                drones_base.ware_id AS ware_id,
                COALESCE(localized_strings.text, drones_base.name) AS name
            FROM drones_base
            LEFT JOIN localized_strings
                ON localized_strings.ware_id = drones_base.ware_id AND localized_strings.lang_id = ?
            WHERE drones_base.ware_id LIKE 'ship_gen_%'
            ORDER BY name
            """,
            (lang,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


@app.get("/api/deployables")
def list_deployables(lang: str = "en") -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                deployables_base.ware_id AS ware_id,
                COALESCE(localized_strings.text, deployables_base.name) AS name,
                deployables_base.deployable_type AS deployable_type
            FROM deployables_base
            LEFT JOIN localized_strings
                ON localized_strings.ware_id = deployables_base.ware_id AND localized_strings.lang_id = ?
            ORDER BY name
            """,
            (lang,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


@app.get("/api/countermeasures")
def list_countermeasures(lang: str = "en") -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                countermeasures_base.ware_id AS ware_id,
                COALESCE(localized_strings.text, countermeasures_base.name) AS name
            FROM countermeasures_base
            LEFT JOIN localized_strings
                ON localized_strings.ware_id = countermeasures_base.ware_id AND localized_strings.lang_id = ?
            ORDER BY name
            """,
            (lang,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


@app.get("/api/crew")
def list_crew(lang: str = "en") -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                crew_base.ware_id AS ware_id,
                COALESCE(localized_strings.text, crew_base.name) AS name
            FROM crew_base
            LEFT JOIN localized_strings
                ON localized_strings.ware_id = crew_base.ware_id AND localized_strings.lang_id = ?
            ORDER BY name
            """,
            (lang,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# crew_role_id -> real display name (e.g. "marine" -> "Marines") for the
# ship builder's Marines/Service Crew rows (see app.js's CREW_ROLES) --
# crew_roles table, see generate_ships_table.py's parse_crew_roles()/
# CREW_ROLE_NAME_REF. Confirmed real, verified in-game text (traced through
# the game's own crew-assignment UI Lua -- see CREW_ROLE_NAME_REF's own
# docstring for the full story), not this app's own invented UI labels, so
# it's localized this way rather than through i18next. "lang" works exactly
# like GET /api/ship_types' own.
@app.get("/api/crew_roles")
def list_crew_roles(lang: str = "en") -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                crew_roles.crew_role_id AS crew_role_id,
                COALESCE(localized_strings.text, crew_roles.crew_role_name) AS crew_role_name
            FROM crew_roles
            LEFT JOIN localized_strings
                ON localized_strings.ware_id = crew_roles.crew_role_id AND localized_strings.lang_id = ?
            """,
            (lang,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


@app.get("/api/build_methods")
def list_build_methods() -> list[str]:
    return DEFAULT_BUILD_METHOD_PRIORITY


# build_method_name -> real display name (e.g. "Terran" -> "Terraner" in
# German) for every real production method (build_methods table -- see
# generate_ships_table.py's parse_build_methods()/collect_build_method_refs()).
# Deliberately separate from GET /api/build_methods above, not a `lang`
# param added to it: this app's own internal build-method "id" is the
# plain English name itself (ships_base.production_method, persisted fleet
# build_method_priority state, summarize_production.py's own cost-calc
# grouping all key off it directly), so GET /api/build_methods must keep
# returning that exact, unlocalized list for anything that matches/
# persists/calculates against it -- see collect_build_method_refs()'s own
# docstring for why that's deliberately not being changed. This endpoint
# is purely for resolving a real display string for that same stable key
# wherever a build method name is actually shown to a user (the Build
# Method filter, the Cost Analysis Build Method modal, the fleet-tab
# priority button). "lang" works exactly like GET /api/ship_types' own.
@app.get("/api/build_method_names")
def list_build_method_names(lang: str = "en") -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                build_methods.build_method_name AS build_method_name,
                COALESCE(localized_strings.text, build_methods.build_method_name) AS build_method_display_name
            FROM build_methods
            LEFT JOIN localized_strings
                ON localized_strings.ware_id = build_methods.build_method_name AND localized_strings.lang_id = ?
            """,
            (lang,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# faction_id -> real display name (e.g. "buccaneers" -> "Duke's
# Buccaneers") for every faction id that can appear in ships_base.owners
# (and, later, other wares' own owner lists) -- see generate_ships_table.py's
# parse_factions(). Powers the ship picker's owner-faction icon tooltips
# and the Vendor filter group's own labels (src/static/app.js) today.
#
# "lang" (default "en") works exactly like GET /api/ships' own -- left-joins
# localized_strings on this faction's own id (parse_factions() feeds its
# rows into parse_localized_strings() the same way every ware list does,
# under "ware_id" even though a faction isn't really a ware -- see that
# function's own docstring), COALESCING to the English faction_name
# whenever no translation row exists, sorted by the resolved name so a
# non-English list is actually alphabetized in that language too.
#
# faction_shortname (e.g. "YAK" for Yaki) is resolved the same way but
# against the separate localized_shortnames table (see
# generate_ships_table.py's "Design race and race/faction shortcodes"
# docstring section for why shortname needed its own table rather than a
# second row per faction in localized_strings). Confirmed several faction
# shortcodes genuinely differ by language (e.g. "buccaneers" is "BUC" in
# English, "KDH" in German) -- unlike race_shortname (see GET /api/races),
# which is identical in every language this app currently supports, so this
# join is not a no-op the way it might look.
@app.get("/api/factions")
def list_factions(lang: str = "en") -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                factions.faction_id AS faction_id,
                COALESCE(localized_strings.text, factions.faction_name) AS faction_name,
                COALESCE(localized_shortnames.text, factions.faction_shortname) AS faction_shortname
            FROM factions
            LEFT JOIN localized_strings
                ON localized_strings.ware_id = factions.faction_id AND localized_strings.lang_id = ?
            LEFT JOIN localized_shortnames
                ON localized_shortnames.ware_id = factions.faction_id AND localized_shortnames.lang_id = ?
            ORDER BY faction_name
            """,
            (lang, lang),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# race_id -> real display name + short in-game callsign (e.g. "argon" ->
# "Argon"/"ARG") -- see generate_ships_table.py's parse_races(). Powers the
# ship picker's per-ship race badges (src/static/app.js, one per entry in
# GET /api/ships' own "maker_races") and the Race filter group's labels.
#
# "lang" works like GET /api/factions' own, but joins against
# localized_race_names/localized_race_shortnames instead of
# localized_strings/localized_shortnames -- races get their own dedicated
# pair of tables because several race ids collide with a same-named
# faction id (e.g. "argon" is both), and sharing factions' tables was
# confirmed (via a live query) to silently return the faction's own
# translation for the race. See generate_ships_table.py's "Design race and
# race/faction shortcodes" docstring section. Confirmed separately that
# race_shortname (unlike faction_shortname) is identical across every
# language this app currently supports, so in practice this join always
# falls back to races.race_shortname today -- but it's still wired the
# same principled way in case a future language (or a mod's own race)
# ever makes it not a no-op.
@app.get("/api/races")
def list_races(lang: str = "en") -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                races.race_id AS race_id,
                COALESCE(localized_race_names.text, races.race_name) AS race_name,
                COALESCE(localized_race_shortnames.text, races.race_shortname) AS race_shortname
            FROM races
            LEFT JOIN localized_race_names
                ON localized_race_names.ware_id = races.race_id AND localized_race_names.lang_id = ?
            LEFT JOIN localized_race_shortnames
                ON localized_race_shortnames.ware_id = races.race_id AND localized_race_shortnames.lang_id = ?
            ORDER BY race_name
            """,
            (lang, lang),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# purpose_id -> real display name (e.g. "dismantling" -> "Dismantling") for
# every real purpose the game defines (purposes table -- see
# generate_ships_table.py's parse_purposes()), covering ships_base.purpose's
# own vocabulary and more (several purposes only ever apply to stations).
# Powers the ship picker's Purpose filter labels, replacing the raw
# internal code capitalized client-side with no real translation behind
# it. "lang" works exactly like GET /api/ships'/GET /api/factions' own.
@app.get("/api/purposes")
def list_purposes(lang: str = "en") -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                purposes.purpose_id AS purpose_id,
                COALESCE(localized_strings.text, purposes.purpose_name) AS purpose_name
            FROM purposes
            LEFT JOIN localized_strings
                ON localized_strings.ware_id = purposes.purpose_id AND localized_strings.lang_id = ?
            ORDER BY purpose_name
            """,
            (lang,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# ship_type_id -> real display name (e.g. "destroyer" -> "Destroyer") for
# every real ship_type value actually present in ships_base (ship_types
# table -- see generate_ships_table.py's parse_ship_types()/
# SHIP_TYPE_NAME_REF). Powers the ship picker's Type filter labels,
# replacing the raw internal code shown unstyled. "lang" works exactly
# like GET /api/purposes' own.
@app.get("/api/ship_types")
def list_ship_types(lang: str = "en") -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                ship_types.ship_type_id AS ship_type_id,
                COALESCE(localized_strings.text, ship_types.ship_type_name) AS ship_type_name
            FROM ship_types
            LEFT JOIN localized_strings
                ON localized_strings.ware_id = ship_types.ship_type_id AND localized_strings.lang_id = ?
            ORDER BY ship_type_name
            """,
            (lang,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# Powers the About page's "built from these versions" section, alongside
# /api/config's own "version" (this tool's own version -- see VERSION at
# module scope) -- the base game and every installed extension's own
# version, base game first, then extensions in source_versions' own
# insertion order (see generate_ships_table.py's parse_source_versions()).
# Regenerated fresh every time the data pipeline runs, so it's always in
# sync with whatever game files actually built the current database --
# unlike VERSION, which is this tool's own code version and bumped
# independently (see CHANGELOG.md).
# ?lang=de resolves each DLC's own display name against localized_strings
# (see SOURCE_VERSION_NAME_REF in generate_ships_table.py) -- the base
# game's own row has no ref and always shows its literal "X4: Foundations"
# name regardless of lang.
@app.get("/api/source_versions")
def list_source_versions(lang: str = "en") -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT source_versions.source_id AS source_id,
                   COALESCE(localized_strings.text, source_versions.source_name) AS source_name,
                   source_versions.source_version AS source_version
            FROM source_versions
            LEFT JOIN localized_strings
                ON localized_strings.ware_id = source_versions.source_id
                AND localized_strings.lang_id = ?
            """,
            (lang,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


@app.post("/api/summarize")
def summarize_endpoint(request: SummarizeRequest) -> dict:
    configurations = [config.model_dump() for config in request.wares]
    target_wares = aggregate_target_wares(configurations)

    conn = get_connection()
    try:
        rows = fetch_all_production_rows(conn)
        category_by_ware = fetch_ware_categories(conn) if request.group_by_component_type else None
    finally:
        conn.close()

    return summarize(
        target_wares,
        rows,
        request.build_method_priority,
        request.search_depth,
        request.verbose,
        request.group_by_component_type,
        category_by_ware,
    )


def _price_methods(
    target_wares,
    rows,
    build_method_priority,
    search_depth,
    ware_prices,
    price_overrides,
    group_by_component_type,
    category_by_ware,
):
    """summarize() at a given depth, then prices the resulting "parts" --
    flat (summarize_prices()) or, when group_by_component_type is set, by
    category (summarize_prices_by_category()), mirroring "parts" itself
    being either a flat ware_id -> amount map or a category -> ware_id ->
    amount map. Returns None when build_method_priority resolved to nothing
    (summarize() has no "parts" to price at all -- see its own docstring).
    Shared by the production_wares (depth=1) and raw_materials
    (depth=ABSOLUTE_MAX_DEPTH) tiers below, which differ only in which
    depth they ask summarize() for.
    """
    result = summarize(
        target_wares, rows, build_method_priority, search_depth, False, group_by_component_type, category_by_ware
    )
    if "parts" not in result:
        return None
    if group_by_component_type:
        return summarize_prices_by_category(result["parts"], ware_prices, price_overrides)
    return summarize_prices(result["parts"], ware_prices, price_overrides)


@app.post("/api/price_summary")
def price_summary_endpoint(request: PriceSummaryRequest) -> dict:
    configurations = [config.model_dump() for config in request.wares]
    target_wares = aggregate_target_wares(configurations)

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
        request.build_method_priority,
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
        request.build_method_priority,
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
    production recipe at all (a true leaf, or one this build_method_
    priority list can't resolve) gets an empty {} rather than being
    omitted, so the caller can still render a row for it. part_names covers
    every part_ware_id that appears in any row, looked up from whichever of
    economy_wares_base/equipment_wares_base actually has it (a depth-1
    input is normally a raw/economy ware, but doesn't have to be).
    request.lang (default "en") resolves each part_names entry against
    localized_strings, same COALESCE pattern as every other endpoint --
    see app.js's openEquipmentPickerModal().
    """
    conn = get_connection()
    try:
        rows = fetch_all_production_rows(conn)

        parts_by_ware: dict[str, dict[str, float]] = {}
        all_part_ids: set[str] = set()
        for ware_id in request.ware_ids:
            result = summarize([{"ware_id": ware_id, "amount": 1}], rows, request.build_method_priority, 1, False)
            parts = result.get("parts", {})
            parts_by_ware[ware_id] = parts
            all_part_ids.update(parts.keys())

        part_names: dict[str, str] = {}
        for table in ("economy_wares_base", "equipment_wares_base", "ships_base"):
            remaining = [pid for pid in all_part_ids if pid not in part_names]
            if not remaining:
                break
            placeholders = ", ".join("?" for _ in remaining)
            for row in conn.execute(
                f"""
                SELECT {table}.ware_id AS ware_id,
                       COALESCE(localized_strings.text, {table}.name) AS name
                FROM {table}
                LEFT JOIN localized_strings
                    ON localized_strings.ware_id = {table}.ware_id
                    AND localized_strings.lang_id = ?
                WHERE {table}.ware_id IN ({placeholders})
                """,
                (request.lang, *remaining),
            ).fetchall():
                part_names[row["ware_id"]] = row["name"]
    finally:
        conn.close()

    return {"parts": parts_by_ware, "part_names": part_names}


@app.get("/api/config")
def config_endpoint() -> dict:
    return {"remote_mode": IS_REMOTE, "version": VERSION}


@app.post("/api/import_loadouts")
def import_loadouts_endpoint(request: ImportLoadoutsRequest) -> dict:
    if request.path and IS_REMOTE:
        return {"error": "Path-based import only works when this app is running locally -- use the file upload option instead."}
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


# Generous but not unbounded -- this endpoint has no auth (any visitor can
# create shares), so a size cap keeps one bad request from writing an
# absurdly large object rather than actually limiting real usage. A share
# with dozens of fully-loaded-out ships across several fleets is still well
# under this.
MAX_SHARE_BYTES = 5 * 1024 * 1024


@app.post("/api/share/{section}")
def create_share_endpoint(section: ShareSection, request: ShareCreateRequest) -> dict:
    if len(json.dumps(request.data)) > MAX_SHARE_BYTES:
        return {"error": "This is too large to share -- try sharing fewer fleets/loadouts at once."}
    return {"uuid": put_share(section, request.data)}


@app.get("/api/share/{section}/{share_uuid}")
def read_share_endpoint(section: ShareSection, share_uuid: str) -> dict:
    data = get_share(section, share_uuid)
    if data is None:
        return {"error": "This share link doesn't exist (it may be mistyped, or the share may have been removed)."}
    return {"data": data}


# Ship-class symbol PNGs (see generate_ship_icons.py) -- served under
# /images/... so the frontend can build an <img src> straight from a
# ships_base.icon value, e.g. /images/ships/symbols/ship_s_fighter_01.png.
# Mounted before the catch-all "/" mount below for the same reason as that
# comment explains: earlier-registered routes/mounts win.
app.mount("/images", StaticFiles(directory=ROOT / "data" / "images"), name="ship_images")

# Mounted last so it doesn't shadow the /api/... routes registered above.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    import os

    import uvicorn

    # 0.0.0.0 so a container (Fly.io etc.) can actually route traffic in --
    # harmless locally too, still reachable at 127.0.0.1. PORT follows
    # Fly's own convention for "what port should this app listen on",
    # falling back to this app's original default (plain local
    # `python src/api.py`) when unset.
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
