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
                                             name/compatibility/
                                             weapon_system), for the
                                             frontend to filter client-side
                                             against whichever launchers'
                                             ammunition_tags are currently
                                             selected -- see the "Missiles
                                             and deployables" docstring
                                             section in
                                             generate_ships_table.py.
                                             "?lang=de" works the same way
                                             as /api/ships' own
  GET  /api/missile_weapon_systems        -- weapon_system_id ->
                                             weapon_system_name for every
                                             real value missiles_base.
                                             weapon_system takes (see
                                             generate_ships_table.py's
                                             parse_missile_weapon_systems()/
                                             MISSILE_WEAPON_SYSTEM_NAME_REF),
                                             for the Component Analyzer's
                                             missile "Weapon System" filter
                                             group. "?lang=de" works the same
                                             way as /api/ship_types' own
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
  GET  /api/components/{component_type}   -- flat, ship-agnostic list of
                                             every real ware of one
                                             equipment type ("engine"/
                                             "shield"/"turret"/"thruster"/
                                             "weapon"/"missile_launcher"/
                                             "software"), for the Component
                                             Analyzer's "Select Components"
                                             picker -- unlike GET
                                             /api/ships/{id}/groups, not
                                             scoped to any one ship's own
                                             hardpoints. See
                                             COMPONENT_LIST_SPECS
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
  GET  /api/cargo_types                   -- cargo_type_id -> cargo_type_name
                                             for every distinct cargo-type
                                             token actually present across
                                             ships_base.cargo_type
                                             (cargo_types table -- see
                                             generate_ships_table.py's
                                             parse_cargo_types()/
                                             CARGO_TYPE_NAME_REF), for the
                                             ship builder's cargo capacity
                                             summary line. "?lang=de" works
                                             the same way as /api/ships' own
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

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from component_export import build_csv_zip, build_xlsx_zip
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


# The four independently-shareable slices of frontend state (see app.js's
# own SHARE_SECTIONS) -- a Literal (not a bare str) so FastAPI 422s on
# anything else automatically, rather than this module needing to validate
# it before ever reaching share_storage.py (which has no opinion on what
# sections exist).
ShareSection = Literal["fleets", "price_overrides", "loadouts", "component_analyzer_tables"]


class ShareCreateRequest(BaseModel):
    # Deliberately untyped beyond "some JSON value" -- this endpoint has no
    # opinion on any given section's own shape (fleets/priceOverrides/
    # importedLoadoutsResult are each a dict, componentAnalyzerTables is a
    # list), it's just a blob store. The frontend is the only place that
    # shape is meaningful. `dict | list` (not bare `dict`) -- a bare `dict`
    # here 422'd every real share attempt for the list-shaped
    # component_analyzer_tables section.
    data: dict | list


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

    s_docks/m_docks/s_ship_storage/m_ship_storage are read straight off
    ships_base (see generate_ships_table.py's parse_ship_docks()) -- the
    Fleet Lists panel's own per-entry and fleet-wide S/M Ship Capacity
    totals (shipCapacity() in app.js) are computed client-side from these
    four, not a separate endpoint, since allShips is already loaded before
    any fleet list ever renders.

    Also carries every other ships_base stat (hull/crew/traveldrivestability/
    weapon_heat_modifier/shield_capacity_modifier/shield_rechargerate_modifier/
    shield_rechargedelay_modifier/missile_capacity/drone_capacity/
    cargo_capacity/cargo_type/shields/engines/weapons/missile_launchers/
    turret_<size>/bonus_<size>_weapons/shields_bonus_m/price_min/price_avg/
    price_max/production_time) plus a LEFT JOIN of every flight_model column
    (flight_model.ware_id is a real FK to ships_base.ware_id, a clean 1:1 --
    every ship has exactly one row) -- together these back the Component
    Analyzer's chassis stat groups (app.js's CHASSIS_STAT_DEFINITIONS:
    core/components/capacities/modifiers/flight/economy). The four
    *_modifier columns are real hull-wide multipliers confirmed in-game
    (verified against a live ship, not just the extracted XML) -- see
    generate_ships_table.py's load_macro_data() for where they're parsed
    from each ship macro's own <modifiers><weapon heat="..."/><shield
    capacity="..." rechargerate="..." rechargedelay="..."/></modifiers>
    block; absence there means an implicit, unmodified 1.0, not unknown, so
    every ship always has a real value for all four, never NULL.
    turret_<size>/bonus_<size>_weapons are the two dynamically-
    named column families explained in generate_ships_table.py's
    write_ships_csv() -- only the sizes actually present across this
    dataset exist as real columns, so this list only names the ones that
    happen to exist right now (turret_l/turret_m/bonus_l_weapons); a
    future DLC adding e.g. turret_s would need this SELECT updated too.
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
                ships_base.production_method AS production_method,
                ships_base.s_docks AS s_docks,
                ships_base.m_docks AS m_docks,
                ships_base.s_ship_storage AS s_ship_storage,
                ships_base.m_ship_storage AS m_ship_storage,
                ships_base.hull AS hull,
                ships_base.crew AS crew,
                ships_base.traveldrivestability AS traveldrivestability,
                ships_base.weapon_heat_modifier AS weapon_heat_modifier,
                ships_base.shield_capacity_modifier AS shield_capacity_modifier,
                ships_base.shield_rechargerate_modifier AS shield_rechargerate_modifier,
                ships_base.shield_rechargedelay_modifier AS shield_rechargedelay_modifier,
                ships_base.missile_capacity AS missile_capacity,
                ships_base.drone_capacity AS drone_capacity,
                ships_base.cargo_capacity AS cargo_capacity,
                ships_base.cargo_type AS cargo_type,
                ships_base.shields AS shields,
                ships_base.shields_bonus_m AS shields_bonus_m,
                ships_base.engines AS engines,
                ships_base.weapons AS weapons,
                ships_base.bonus_l_weapons AS bonus_l_weapons,
                ships_base.missile_launchers AS missile_launchers,
                ships_base.turret_l AS turret_l,
                ships_base.turret_m AS turret_m,
                ships_base.price_min AS price_min,
                ships_base.price_avg AS price_avg,
                ships_base.price_max AS price_max,
                ships_base.production_time AS production_time,
                flight_model.jerk_angular_value AS jerk_angular_value,
                flight_model.jerk_forward_accel AS jerk_forward_accel,
                flight_model.jerk_forward_boost_accel AS jerk_forward_boost_accel,
                flight_model.jerk_forward_boost_ratio AS jerk_forward_boost_ratio,
                flight_model.jerk_forward_decel AS jerk_forward_decel,
                flight_model.jerk_forward_ratio AS jerk_forward_ratio,
                flight_model.jerk_forward_travel_accel AS jerk_forward_travel_accel,
                flight_model.jerk_forward_travel_decel AS jerk_forward_travel_decel,
                flight_model.jerk_forward_travel_ratio AS jerk_forward_travel_ratio,
                flight_model.jerk_strafe_value AS jerk_strafe_value,
                flight_model.physics_accfactors_forward AS physics_accfactors_forward,
                flight_model.physics_accfactors_horizontal AS physics_accfactors_horizontal,
                flight_model.physics_accfactors_reverse AS physics_accfactors_reverse,
                flight_model.physics_accfactors_vertical AS physics_accfactors_vertical,
                flight_model.physics_drag_forward AS physics_drag_forward,
                flight_model.physics_drag_horizontal AS physics_drag_horizontal,
                flight_model.physics_drag_pitch AS physics_drag_pitch,
                flight_model.physics_drag_reverse AS physics_drag_reverse,
                flight_model.physics_drag_roll AS physics_drag_roll,
                flight_model.physics_drag_vertical AS physics_drag_vertical,
                flight_model.physics_drag_yaw AS physics_drag_yaw,
                flight_model.physics_inertia_pitch AS physics_inertia_pitch,
                flight_model.physics_inertia_roll AS physics_inertia_roll,
                flight_model.physics_inertia_yaw AS physics_inertia_yaw,
                flight_model.physics_mass AS physics_mass,
                flight_model.steeringcurve AS steeringcurve
            FROM ships_base
            LEFT JOIN localized_strings
                ON localized_strings.ware_id = ships_base.ware_id AND localized_strings.lang_id = ?
            LEFT JOIN flight_model
                ON flight_model.ware_id = ships_base.ware_id
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


# Backs the Component Analyzer's "Economy Wares" component type -- unlike
# GET /api/wares above (a flat union across every PRICE_WARE_TABLES table,
# used by the price-override picker), this is economy_wares_base alone:
# real production-chain materials (raw resources, refined goods, station
# wares), each with its own real volume/transport cargo stats (see that
# table's own schema comment in ships_tables.sql) -- not the meaningless
# flat volume=1 placeholder every other ware kind carries.
@app.get("/api/economy_wares")
def list_economy_wares(lang: str = "en") -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                economy_wares_base.ware_id AS ware_id,
                COALESCE(localized_strings.text, economy_wares_base.name) AS name,
                economy_wares_base.price_min AS price_min,
                economy_wares_base.price_avg AS price_avg,
                economy_wares_base.price_max AS price_max,
                economy_wares_base.volume AS volume,
                economy_wares_base.transport AS transport,
                economy_wares_base.leaf_ware AS leaf_ware
            FROM economy_wares_base
            LEFT JOIN localized_strings
                ON localized_strings.ware_id = economy_wares_base.ware_id AND localized_strings.lang_id = ?
            ORDER BY name
            """,
            (lang,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


@app.get("/api/missiles")
def list_missiles(lang: str = "en") -> list[dict]:
    conn = get_connection()
    try:
        # Every missiles_base stat column except its own raw "name" (the
        # COALESCE below overrides that one with the localized text) --
        # backs the Component Analyzer's missile stat catalog (app.js's
        # MISSILE_STAT_DEFINITIONS). Listed explicitly rather than
        # missiles_base.* -- unlike engines_base/shields_base/weapons_base/
        # turrets_base/thrusters_base, missiles_base has its own "name"
        # column, so a blind .* would collide with the aliased one below.
        rows = conn.execute(
            """
            SELECT
                missiles_base.ware_id AS ware_id,
                COALESCE(localized_strings.text, missiles_base.name) AS name,
                missiles_base.macro AS macro,
                missiles_base.price_min AS price_min,
                missiles_base.price_avg AS price_avg,
                missiles_base.price_max AS price_max,
                missiles_base.ammunition_value AS ammunition_value,
                missiles_base.ammunition_reload AS ammunition_reload,
                missiles_base.missile_amount AS missile_amount,
                missiles_base.missile_barrelamount AS missile_barrelamount,
                missiles_base.missile_lifetime AS missile_lifetime,
                missiles_base.missile_range AS missile_range,
                missiles_base.missile_guided AS missile_guided,
                missiles_base.explosiondamage_value AS explosiondamage_value,
                missiles_base.explosiondamage_shielddisruption AS explosiondamage_shielddisruption,
                missiles_base.reload_time AS reload_time,
                missiles_base.hull AS hull,
                missiles_base.weapon_system AS weapon_system,
                missiles_base.countermeasure_resilience AS countermeasure_resilience,
                missiles_base.physics_mass AS physics_mass,
                missiles_base.lock_time AS lock_time,
                missiles_base.lock_range AS lock_range,
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


# weapon_system_id -> real display name (e.g. "torpedo" -> "Torpedos") for
# every real value missiles_base.weapon_system actually takes -- see
# generate_ships_table.py's parse_missile_weapon_systems()/
# MISSILE_WEAPON_SYSTEM_NAME_REF. Powers the Component Analyzer's missile
# "Weapon System" filter group (app.js). "lang" works exactly like GET
# /api/ship_types' own.
@app.get("/api/missile_weapon_systems")
def list_missile_weapon_systems(lang: str = "en") -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                missile_weapon_systems.weapon_system_id AS weapon_system_id,
                COALESCE(localized_strings.text, missile_weapon_systems.weapon_system_name) AS weapon_system_name
            FROM missile_weapon_systems
            LEFT JOIN localized_strings
                ON localized_strings.ware_id = missile_weapon_systems.weapon_system_id AND localized_strings.lang_id = ?
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
        #
        # Every drones_base stat column except its own raw "name" (the
        # COALESCE below overrides that one with the localized text) --
        # backs the Component Analyzer's drone stat catalog (app.js's
        # DRONE_STAT_DEFINITIONS). Listed explicitly rather than
        # drones_base.* -- like missiles_base, drones_base has its own
        # "name" column, so a blind .* would collide with the aliased one.
        rows = conn.execute(
            """
            SELECT
                drones_base.ware_id AS ware_id,
                COALESCE(localized_strings.text, drones_base.name) AS name,
                drones_base.macro AS macro,
                drones_base.price_min AS price_min,
                drones_base.price_avg AS price_avg,
                drones_base.price_max AS price_max,
                drones_base.ship_type AS ship_type,
                drones_base.purpose AS purpose,
                drones_base.hull AS hull,
                drones_base.physics_mass AS physics_mass
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
        # Every deployables_base stat column except its own raw "name" (the
        # COALESCE below overrides that one with the localized text) --
        # backs the Component Analyzer's deployable stat catalog (app.js's
        # DEPLOYABLE_STAT_DEFINITIONS). Listed explicitly rather than
        # deployables_base.* -- like missiles_base/drones_base,
        # deployables_base has its own "name" column, so a blind .* would
        # collide with the aliased one below.
        rows = conn.execute(
            """
            SELECT
                deployables_base.ware_id AS ware_id,
                COALESCE(localized_strings.text, deployables_base.name) AS name,
                deployables_base.deployable_type AS deployable_type,
                deployables_base.price_min AS price_min,
                deployables_base.price_avg AS price_avg,
                deployables_base.price_max AS price_max,
                deployables_base.hull AS hull,
                deployables_base.radar_range AS radar_range,
                deployables_base.explosion_strength AS explosion_strength,
                deployables_base.explosion_damage AS explosion_damage,
                deployables_base.trigger_oncollision AS trigger_oncollision,
                deployables_base.physics_mass AS physics_mass
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
        # countermeasures_base has no stat column beyond price (see its own
        # schema in ships_tables.sql) -- price_min/avg/max back the
        # Component Analyzer's countermeasure stat catalog (app.js's
        # COUNTERMEASURE_STAT_DEFINITIONS), economy group only.
        rows = conn.execute(
            """
            SELECT
                countermeasures_base.ware_id AS ware_id,
                COALESCE(localized_strings.text, countermeasures_base.name) AS name,
                countermeasures_base.price_min AS price_min,
                countermeasures_base.price_avg AS price_avg,
                countermeasures_base.price_max AS price_max
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
        # crew_base has no stat column beyond price either (see
        # countermeasures_base's own comment just above) -- backs the
        # Component Analyzer's crew stat catalog (app.js's
        # CREW_STAT_DEFINITIONS), economy group only.
        rows = conn.execute(
            """
            SELECT
                crew_base.ware_id AS ware_id,
                COALESCE(localized_strings.text, crew_base.name) AS name,
                crew_base.price_min AS price_min,
                crew_base.price_avg AS price_avg,
                crew_base.price_max AS price_max
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


# Component Analyzer's "Select Components" picker -- a flat, ship-agnostic
# list of every real ware of one equipment type, unlike GET
# /api/ships/{id}/groups' per-slot options (query_ship_groups(), scoped to
# one ship's own hardpoints). "weapon" vs "missile_launcher" are both
# backed by weapons_base (see query_ship_components.py's own
# COMPONENT_TYPE_TABLES, which this mirrors) and split by
# equipment_wares_base.missile_launcher, exactly like query_ship_groups()
# splits them for its own per-ship "weapons"/"missile_launchers" buckets.
COMPONENT_LIST_SPECS = {
    "engine": {"table": "engines_base", "extra_where": None},
    "shield": {"table": "shields_base", "extra_where": None},
    "turret": {"table": "turrets_base", "extra_where": None},
    "thruster": {"table": "thrusters_base", "extra_where": None},
    "weapon": {"table": "weapons_base", "extra_where": "equipment_wares_base.missile_launcher = 0"},
    "missile_launcher": {"table": "weapons_base", "extra_where": "equipment_wares_base.missile_launcher = 1"},
}


@app.get("/api/components/{component_type}")
def list_components(component_type: str, lang: str = "en") -> list[dict]:
    conn = get_connection()
    try:
        if component_type == "software":
            # software_base has no equipment_wares_base parent row (see
            # that table's own docstring in ships_tables.sql) -- name/price
            # live directly on it.
            rows = conn.execute(
                """
                SELECT
                    software_base.ware_id AS ware_id,
                    COALESCE(localized_strings.text, software_base.name) AS name,
                    software_base.category AS category,
                    software_base.mk AS mk,
                    software_base.price_min AS price_min,
                    software_base.price_avg AS price_avg,
                    software_base.price_max AS price_max
                FROM software_base
                LEFT JOIN localized_strings
                    ON localized_strings.ware_id = software_base.ware_id AND localized_strings.lang_id = ?
                ORDER BY name
                """,
                (lang,),
            ).fetchall()
            return [dict(row) for row in rows]

        spec = COMPONENT_LIST_SPECS.get(component_type)
        if spec is None:
            raise HTTPException(status_code=404, detail=f"Unknown component type '{component_type}'")

        where_clause = f"WHERE {spec['extra_where']}" if spec["extra_where"] else ""
        # weapons_base/turrets_base only -- LEFT JOIN (not JOIN) since not
        # every weapon/turret's own bullet_class resolves to a real bullets_base
        # row: 8 values point to a missile macro instead (dumbfire/torpedo-
        # style "weapons" -- see bullets_base's own schema comment in
        # ships_tables.sql), already covered by missiles_base, not this join.
        # bullets_base.* rather than an explicit column list, same reasoning
        # as {spec["table"]}.* below -- its own bullet_class column is a
        # harmless duplicate of {spec["table"]}.bullet_class (identical
        # value when the join hits, absent when it doesn't).
        needs_bullets_join = spec["table"] in ("weapons_base", "turrets_base")
        bullets_select = ", bullets_base.*" if needs_bullets_join else ""
        bullets_join = (
            f"LEFT JOIN bullets_base ON bullets_base.bullet_class = {spec['table']}.bullet_class"
            if needs_bullets_join
            else ""
        )
        # {spec["table"]}.* -- every type-specific stat column (mk/hull/size/
        # compatibility plus whichever of bullet_class/heat_*/rotation_*/
        # weapon_angle/ammunition_*/boost_*/travel_*/thrust_*/recharge_*/
        # thruster_class that type's own table has) -- backs the Component
        # Analyzer's per-type stat catalogs (app.js's ENGINE_STAT_DEFINITIONS/
        # SHIELD_STAT_DEFINITIONS/WEAPON_STAT_DEFINITIONS/TURRET_STAT_DEFINITIONS/
        # THRUSTER_STAT_DEFINITIONS). No column-name collision with the
        # explicitly-aliased ones below -- none of these five tables has its
        # own "name"/"owners"/"production_method"/"price_*" column (those
        # only live on equipment_wares_base, joined in separately).
        rows = conn.execute(
            f"""
            SELECT
                {spec["table"]}.*{bullets_select},
                COALESCE(localized_strings.text, equipment_wares_base.name) AS name,
                equipment_wares_base.owners AS owners,
                equipment_wares_base.production_method AS production_method,
                equipment_wares_base.price_min AS price_min,
                equipment_wares_base.price_avg AS price_avg,
                equipment_wares_base.price_max AS price_max
            FROM {spec["table"]}
            JOIN equipment_wares_base ON equipment_wares_base.ware_id = {spec["table"]}.ware_id
            LEFT JOIN localized_strings
                ON localized_strings.ware_id = {spec["table"]}.ware_id AND localized_strings.lang_id = ?
            {bullets_join}
            {where_clause}
            ORDER BY name
            """,
            (lang,),
        ).fetchall()
        components = [dict(row) for row in rows]

        # Real design race(s) -- same maker_races table/shape GET /api/ships
        # merges in for ship.maker_races (see that endpoint's own comment).
        # Not every component type has one (thrusters/missiles/software/
        # deployables carry no makerrace concept in the game data at all --
        # see load_maker_races()'s own docstring in query_ship_components.py),
        # so components of those types simply end up with an empty list.
        maker_race_rows = conn.execute(
            "SELECT ware_id, race_id FROM maker_races ORDER BY ware_id, ordinal"
        ).fetchall()
        maker_races_by_ware_id: dict[str, list[str]] = {}
        for row in maker_race_rows:
            maker_races_by_ware_id.setdefault(row["ware_id"], []).append(row["race_id"])
        for component in components:
            component["maker_races"] = maker_races_by_ware_id.get(component["ware_id"], [])

        return components
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


# cargo_type_id -> real display name (e.g. "liquid" -> "Liquid") for every
# distinct cargo-type token actually present across ships_base.cargo_type
# (cargo_types table -- see generate_ships_table.py's parse_cargo_types()/
# CARGO_TYPE_NAME_REF). Powers the ship builder's cargo capacity summary
# line -- a ship's own cargo_type can hold more than one space-separated
# token (e.g. "container solid"), so a caller splits it and looks up each
# token here. "lang" works exactly like GET /api/purposes' own.
@app.get("/api/cargo_types")
def list_cargo_types(lang: str = "en") -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                cargo_types.cargo_type_id AS cargo_type_id,
                COALESCE(localized_strings.text, cargo_types.cargo_type_name) AS cargo_type_name
            FROM cargo_types
            LEFT JOIN localized_strings
                ON localized_strings.ware_id = cargo_types.cargo_type_id AND localized_strings.lang_id = ?
            ORDER BY cargo_type_name
            """,
            (lang,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# "?lang=de" works the same way as GET /api/ship_types' own, with one
# known gap: the handful of compatibility tags that are really race ids
# under the hood ("khaak" -- see parse_compatibility_types()'s own
# docstring for why "boron"/"khaak" resolve through the races table rather
# than duplicating COMPATIBILITY_NAME_REF) only ever show their English
# race_name here, never a real per-language one, since that resolution
# happens once, in English, at generate time -- compatibility_types itself
# carries no {page,id} ref for these to give localized_strings anything to
# resolve. Real per-language race names already exist in
# localized_race_names; revisit by joining against that table too if this
# gap ever actually matters (today it's one real token, "khaak").
@app.get("/api/compatibility_types")
def list_compatibility_types(lang: str = "en") -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                compatibility_types.compatibility_type_id AS compatibility_type_id,
                COALESCE(localized_strings.text, compatibility_types.compatibility_type_name) AS compatibility_type_name
            FROM compatibility_types
            LEFT JOIN localized_strings
                ON localized_strings.ware_id = compatibility_types.compatibility_type_id AND localized_strings.lang_id = ?
            ORDER BY compatibility_type_name
            """,
            (lang,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# "?lang=de" works the same way as GET /api/compatibility_types' own, with
# two wrinkles. First: a bare tag (dumbfire/guided/torpedo) gets its
# localized_strings row the normal way (a real name_ref, resolved by
# parse_localized_strings()), but a size-prefixed compound tag (e.g.
# "largedumbfire") gets its own row from a dedicated composer,
# parse_ammunition_compatibility_localized_strings() -- see that function's
# own docstring in generate_ships_table.py for why (no single {page,id}
# ref exists for the whole compound phrase, only for its two pieces).
# Second: the join condition prepends "ammunition_compatibility_type_" to
# this table's own id before comparing against localized_strings.ware_id
# -- a real collision, "torpedo" is also missile_weapon_systems' own real
# id (see parse_ammunition_compatibility_types()'s own docstring), so this
# table's own passenger key needs namespacing to avoid silently inheriting
# missile_weapon_systems' own (differently-worded, e.g. plural "Torpedos")
# translation instead. Either way COALESCE still falls back to the base
# English name for a hull-lock tag (e.g. "ship_ter_l_flagship_01"), which
# never has any real ref at all.
@app.get("/api/ammunition_compatibility_types")
def list_ammunition_compatibility_types(lang: str = "en") -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                ammunition_compatibility_types.ammunition_compatibility_type_id AS ammunition_compatibility_type_id,
                COALESCE(localized_strings.text, ammunition_compatibility_types.ammunition_compatibility_type_name)
                    AS ammunition_compatibility_type_name
            FROM ammunition_compatibility_types
            LEFT JOIN localized_strings
                ON localized_strings.ware_id = 'ammunition_compatibility_type_' ||
                    ammunition_compatibility_types.ammunition_compatibility_type_id
                    AND localized_strings.lang_id = ?
            ORDER BY ammunition_compatibility_type_name
            """,
            (lang,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# "?lang=de" works the same way as GET /api/ship_types' own -- see
# parse_thruster_classes()/THRUSTER_CLASS_NAME_REF's own docstrings in
# generate_ships_table.py for where the two real refs (page 20107) come
# from.
@app.get("/api/thruster_classes")
def list_thruster_classes(lang: str = "en") -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                thruster_classes.thruster_class_id AS thruster_class_id,
                COALESCE(localized_strings.text, thruster_classes.thruster_class_name) AS thruster_class_name
            FROM thruster_classes
            LEFT JOIN localized_strings
                ON localized_strings.ware_id = thruster_classes.thruster_class_id AND localized_strings.lang_id = ?
            ORDER BY thruster_class_name
            """,
            (lang,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# "?lang=de" works the same way as GET /api/ship_types' own, with one
# wrinkle: the join condition prepends "deployable_type_" to this table's
# own id before comparing against localized_strings.ware_id -- see
# parse_deployable_types()'s own docstring in generate_ships_table.py for
# why (a real collision: "mine" is both a deployable_type and a purpose
# id, and the shared localized_strings keyspace needs this table's own
# passenger key namespaced to avoid silently inheriting the *purpose*'s
# own translation).
@app.get("/api/deployable_types")
def list_deployable_types(lang: str = "en") -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                deployable_types.deployable_type_id AS deployable_type_id,
                COALESCE(localized_strings.text, deployable_types.deployable_type_name) AS deployable_type_name
            FROM deployable_types
            LEFT JOIN localized_strings
                ON localized_strings.ware_id = 'deployable_type_' || deployable_types.deployable_type_id
                    AND localized_strings.lang_id = ?
            ORDER BY deployable_type_name
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


# One row per Component Analyzer stat-set tab the user chose to export --
# the frontend has already resolved every cell to a plain string
# (formatStatValue(), the same formatting the on-screen table itself uses)
# before this ever reaches component_export.py, which has no opinion on
# what the data means (see that module's own docstring).
class ComponentAnalyzerExportSheet(BaseModel):
    table_name: str
    tab_name: str
    headers: list[str]
    rows: list[list[str]]


class ComponentAnalyzerExportRequest(BaseModel):
    format: Literal["csv", "xlsx"]
    sheets: list[ComponentAnalyzerExportSheet]


# The Component Analyzer's own "Export" modal's csv/xlsx paths (its json
# path needs no server round trip at all -- see app.js's own export click
# handler) -- see component_export.py's own docstring for the CSV-vs-XLSX
# file/zip shape.
@app.post("/api/export_component_analyzer")
def export_component_analyzer(request: ComponentAnalyzerExportRequest) -> Response:
    sheets = [sheet.model_dump() for sheet in request.sheets]
    if request.format == "csv":
        content = build_csv_zip(sheets)
        filename = "component_analyzer_export_csv.zip"
    else:
        content = build_xlsx_zip(sheets)
        filename = "component_analyzer_export_xlsx.zip"
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
