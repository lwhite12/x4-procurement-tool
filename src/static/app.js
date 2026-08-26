"use strict";

// Currently loaded ship's group data (response of GET /api/ships/{id}/groups).
let currentShip = null;

// ware_id of the ship currently highlighted in #ship-options-list (the
// custom ship-picker listbox -- see renderShipOptions()/applyShipSelection()
// below). Plays the same role a native <select>'s own .value would, but a
// plain <select> can't render an <img> per <option>, which every row here
// needs for its ship-class symbol.
let selectedShipWareId = "";

// Index into `activeFleet().cart` currently being edited, or null when "Add
// to fleet list" will append a new entry instead of replacing an existing
// one. Always reset (via resetShipPicker()) whenever the active fleet
// changes, since it's only meaningful relative to whichever fleet's cart was
// open when editCartEntry() was called -- see setActiveFleet()/deleteFleet().
let editingIndex = null;

// One fleet list: {name, cart, buildMethodPriority, wareCostList, dirty}.
// buildMethodPriority is an ordered list of build method names (tried in
// order, first available match wins per ware -- see resolve_method() in
// summarize_production.py) or null to use the server's own default.
// cart entries: {shipWareId, shipName, shipIcon, missingRequiredComponents, note,
// loadoutMinimized, count, selections: {group_name: ware_id},
// missileAmounts, droneAmounts, deployableAmounts, countermeasureAmounts: {ware_id: amount},
// crewAmounts: {role: amount} (role: "marine"/"service", see CREW_ROLES --
// not a real ware_id, both roles share one),
// wares_list: [{ware_id, amount}], displayItems: [{label, amount}]}.
// dirty starts true (nothing computed yet) and is cleared by
// recomputeDirtyFleets() -- see that function for the lazy-recompute design.
function makeFleet(name = "") {
  return { name, cart: [], buildMethodPriority: null, wareCostList: null, dirty: true };
}

// Never empty -- always at least one fleet exists, mirroring the old
// `cart = []` initial state. Replaces the old cart/savedComparisonColumns/
// lastWareCostList/activeBuildFocus/activeFallbackMethods split (see
// UNNAMED_FLEET_LIST_LABEL's old comment block, now removed, for the prior
// "active + saved snapshots" design this superseded).
let fleets = [makeFleet()];

// Which entry in `fleets` is currently being viewed/edited in the Fleet
// Planner and shown as the highlighted tab. Switching this (setActiveFleet())
// is a cheap pointer change, not a copy -- every fleet is always live.
let activeFleetIndex = 0;

function activeFleet() {
  return fleets[activeFleetIndex];
}

// Full, unfiltered ship list fetched once from GET /api/ships.
let allShips = [];

// Full missile catalog fetched once from GET /api/missiles -- filtered
// client-side (see compatibleMissiles()) against whichever launchers are
// currently selected, so swapping a turret/weapon never needs a new fetch.
let allMissiles = [];

// Ammunition picked for the ship currently being configured: ware_id ->
// amount. Reset in resetShipPicker()/on a fresh ship pick, restored from
// the cart entry's own missileAmounts when editing.
let missileAmounts = {};

// Full drone catalog fetched once from GET /api/drones. Unlike missiles,
// no per-launcher compatibility concept -- every drone can fill a ship's
// shared drone_capacity pool, so the list shown never depends on what's
// selected elsewhere in the picker.
let allDrones = [];

// Drones picked for the ship currently being configured: ware_id ->
// amount. Same lifecycle as missileAmounts.
let droneAmounts = {};

// Full deployable catalog fetched once from GET /api/deployables. Same
// "shared pool, no per-selection compatibility" shape as drones.
let allDeployables = [];

// Deployables picked for the ship currently being configured: ware_id ->
// amount. Same lifecycle as missileAmounts/droneAmounts.
let deployableAmounts = {};

// The game data has no per-ship deployable capacity stat anywhere (unlike
// missile_capacity/drone_capacity, both real ships_base columns) -- these
// are assumed defaults by ship size, given explicitly rather than derived.
const DEPLOYABLE_CAPACITY_BY_SIZE = { s: 50, m: 100, l: 250, xl: 450 };

// Full countermeasure catalog fetched once from GET /api/countermeasures --
// just "Flares" in the base game. Same "shared pool, no per-selection
// compatibility" shape as drones/deployables.
let allCountermeasures = [];

// Countermeasures picked for the ship currently being configured: ware_id ->
// amount. Same lifecycle as missileAmounts/droneAmounts/deployableAmounts.
let countermeasureAmounts = {};

// Like DEPLOYABLE_CAPACITY_BY_SIZE: no ship macro anywhere specifies a real
// per-ship flare capacity (only ever an explicit "0" to disable flares on
// drones/Kha'ak/other non-player-flyable hulls -- see the "Countermeasures
// and crew" docstring section in generate_ships_table.py) -- an assumed
// default by ship size instead.
const COUNTERMEASURE_CAPACITY_BY_SIZE = { s: 4, m: 8, l: 20, xl: 40 };

// X4 has no separate "marine"/"service crew" ware -- GET /api/crew always
// returns exactly one real ware (confirmed against the game's own
// wares.xml and every ship's <people capacity="..."/>, which never
// subdivides capacity by role). "Marine"/"Service Crew" are purely an AI
// role assigned to crew already aboard, the same way the game's own saved
// ship loadouts track them (<crew role="marine"/service" exact="N"/>, no
// ware_id at all). The UI still tracks/shows them as two independent rows
// -- allCrew ends up with two *synthetic* entries built from that one real
// ware (see loadCrew()), each keyed by a role id ("marine"/"service")
// instead of a real ware_id; crewWareId separately remembers the one real
// ware_id every row actually shares, needed wherever a row's amount gets
// converted into an actual wares_list contribution (see addToCartBtn's
// handler) since summarize_production.py only knows about the real ware.
const CREW_ROLES = [
  { role: "marine", label: "Marines" },
  { role: "service", label: "Service Crew" },
];
// Maps a cart wares_list item's category override (see addToCartBtn's
// handler) back to the role id it came from -- the only way to tell two
// crew wares_list entries apart on reload, since both share the one real
// crewWareId (see reconstructCartEntry()).
const CREW_CATEGORY_TO_ROLE = { crew_marine: "marine", crew_service: "service" };
let crewWareId = null;

// Full crew catalog -- two synthetic role rows (see CREW_ROLES above),
// built once GET /api/crew resolves. Rendered through the same qty-row
// scaffolding as missiles/drones/deployables/countermeasures.
let allCrew = [];

// Crew picked for the ship currently being configured: role -> amount
// (see CREW_ROLES -- "marine"/"service", not a real ware_id). Same
// lifecycle as missileAmounts/droneAmounts/deployableAmounts/
// countermeasureAmounts. Unlike those, its capacity (totalCrewCapacity())
// is a real ships_base column (query_ship_groups()'s own
// summary.crew_capacity), not an assumed default -- and unlike those,
// both roles draw from that one shared capacity together (see
// totalSelectedCrew(), unchanged: it already just sums every value
// regardless of how many keys exist).
let crewAmounts = {};

// The Ware Cost List always shows two fixed depths side by side rather
// than one user-configurable search_depth -- these mirror the same two
// fixed depths api.py's POST /api/price_summary already uses server-side
// for its "production_wares"/"raw_materials" tiers (see that endpoint's
// docstring), just applied here to the ware *list* instead of a monetary
// total. RAW_MATERIALS_SEARCH_DEPTH matches summarize_production.py's own
// ABSOLUTE_MAX_DEPTH -- large enough that no real production chain in the
// game data bottoms out before it, so this always reaches true leaf wares.
const PRODUCTION_WARES_SEARCH_DEPTH = 1;
const RAW_MATERIALS_SEARCH_DEPTH = 100;

// Faction colors, extracted from the game's own libraries/colors.xml
// (<mapping id="faction_<id>" ref="<color-id>"/> resolved against the
// matching <color id="..." r="" g="" b=""/> entry). Used to tint 3-letter
// race abbreviations wherever they appear (equipment names, ship owners,
// build method labels) so the UI echoes the same faction-color language
// the game itself uses on its map and diplomacy screens. Only factions
// that actually appear as a ship/equipment race prefix or a BUILD_METHODS
// entry are included.
const FACTION_COLORS = {
  argon: "#0069b3",
  boron: "#4db5ff",
  paranid: "#b300b3",
  split: "#b36100",
  teladi: "#b3b300",
  terran: "#99d5ff",
  xenon: "#b30000",
  khaak: "#ff00ff",
  yaki: "#ff4d4d",
  // Not a real in-game faction/color -- "gen"/"pir" ship hulls have no
  // single consistent owning race (see RACE_PREFIX_TO_FACTION below), so
  // there's no libraries/colors.xml entry to draw from. A plain neutral
  // grey exists purely so every ship in the picker still gets a race
  // label with a backing panel (see FACTION_BG_CLASS), not because it
  // represents an actual faction.
  neutral: "#c8c8c8",
};

// Maps the 3-letter race token that prefixes an equipment ware's display
// name (e.g. "PAR" in "PAR M Blast Mortar Turret Mk1") or a ship's own
// ware_id (e.g. "par" in "ship_par_s_heavyfighter_01_a") to a
// FACTION_COLORS key. "atf" (Terran capital-ship/ATF-branded hulls)
// shares Terran's color; "gen"/"pir" (generic/pirate hulls with no
// single consistent owning race -- see ships_base.owners, which for
// these is a mix of minor factions like ownerless/scaleplate/loanshark/
// scavenger rather than one clean race) map to the "neutral" pseudo-
// faction instead of a real one, so every ship still gets a colored,
// paneled race label in the picker -- this key is never matched against
// an equipment ware's own name (no real ware name starts with "GEN "/
// "PIR "), so it only ever takes effect there.
const RACE_PREFIX_TO_FACTION = {
  arg: "argon",
  bor: "boron",
  par: "paranid",
  spl: "split",
  tel: "teladi",
  ter: "terran",
  atf: "terran",
  xen: "xenon",
  kha: "khaak",
  yak: "yaki",
  gen: "neutral",
  pir: "neutral",
};

// Maps a full build-method name (see generate_ships_table.py's
// BUILD_METHODS) to a FACTION_COLORS key -- "Universal"/"Closed Loop"/
// "Recycling" have no associated race and are deliberately absent, so
// they render with no color.
const BUILD_METHOD_TO_FACTION = {
  Argon: "argon",
  Boron: "boron",
  Paranid: "paranid",
  Split: "split",
  Teladi: "teladi",
  Terran: "terran",
  Xenon: "xenon",
};

// Every FACTION_COLORS entry gets a solid backing panel instead of plain
// colored text wherever it's rendered as real DOM text, since none of
// these colors were picked for contrast against this app's own dark
// background (they're lifted straight from the game's own UI, meant for
// its own map/HUD rendering) -- see .faction-bg-silver/.faction-bg-slate
// in style.css: a light "silver" panel behind the darker colors (Argon/
// Paranid/Split/Xenon), a lighter steel-grey "slate" panel behind every
// light color (Boron/Teladi/Terran/Kha'ak/Yaki) -- a light panel there
// would fight with the text color the same way plain dark text does on
// the page background. Not applied to <select><option> coloring (used by
// buildGroupRow() alone) since <option> background styling doesn't
// reliably render in native dropdowns anyway.
const FACTION_BG_CLASS = {
  argon: "faction-bg-silver",
  paranid: "faction-bg-silver",
  split: "faction-bg-silver",
  xenon: "faction-bg-silver",
  boron: "faction-bg-slate",
  teladi: "faction-bg-slate",
  terran: "faction-bg-slate",
  khaak: "faction-bg-slate",
  yaki: "faction-bg-slate",
  neutral: "faction-bg-slate",
};

function factionColor(factionKey) {
  return factionKey ? (FACTION_COLORS[factionKey] ?? null) : null;
}

// Sets `el`'s text color to `factionKey`'s color (a no-op if `factionKey`
// is null/unmapped) and, for FACTION_BG_CLASS entries, adds the matching
// backing-panel class so the harder-to-read faction colors stay legible.
function applyFactionTextColor(el, factionKey) {
  const color = factionColor(factionKey);
  if (!color) return;
  el.style.color = color;
  const bgClass = FACTION_BG_CLASS[factionKey];
  if (bgClass) el.classList.add(bgClass);
}

// Like applyFactionTextColor(), but for a build method name specifically
// (see BUILD_METHOD_TO_FACTION): a race-mapped method (Argon/Boron/.../
// Xenon) gets that faction's usual colored pill, while a race-less one
// (Universal/Closed Loop/Recycling -- deliberately absent from
// BUILD_METHOD_TO_FACTION) still gets a pill, just a plain dark one with
// white text, so every build method reads as a distinct button/row instead
// of the race-less ones rendering as unstyled plain text.
function applyBuildMethodColor(el, methodName) {
  const factionKey = BUILD_METHOD_TO_FACTION[methodName];
  if (factionKey) {
    applyFactionTextColor(el, factionKey);
    return;
  }
  // White "as if it were a race color" -- reuses the exact same slate
  // backing panel every light race color (Boron/Teladi/Terran/Kha'ak/Yaki)
  // already sits on, rather than a bespoke background, so a race-less
  // method looks identical in style to a real one.
  el.style.color = "#ffffff";
  el.classList.add("faction-bg-slate");
}

// Matches a leading race token in an equipment display name, e.g. "PAR"
// in "PAR M Blast Mortar Turret Mk1" -- only equipment names carry this
// convention (missiles/drones/deployables/countermeasures/crew never do).
// Unrecognized 2-4 letter prefixes (e.g. the "XL" in a generic "XL
// All-round Thrusters Mk1") harmlessly fall through to no color, since
// RACE_PREFIX_TO_FACTION simply has no entry for them.
const NAME_RACE_PREFIX_RE = /^([A-Z]{2,4})(\s)/;

function raceFactionForName(name) {
  const match = name.match(NAME_RACE_PREFIX_RE);
  return match ? (RACE_PREFIX_TO_FACTION[match[1].toLowerCase()] ?? null) : null;
}

function raceColorForName(name) {
  return factionColor(raceFactionForName(name));
}

// Splits `name`'s leading race token (if any) into its own colored
// <span>, appended directly to `parent` along with the rest of the name
// as a plain text node -- for names rendered as real DOM text (e.g. the
// fleet list's Loadout display, see renderLoadoutCell()). A
// <select><option> can't render partial-colored text (no nested markup
// support) -- equipment pickers instead tint the *entire* option in its
// race's color via raceColorForName() directly (see buildGroupRow()).
function appendNameWithFactionColor(parent, name) {
  const match = name.match(NAME_RACE_PREFIX_RE);
  const factionKey = match ? raceFactionForName(name) : null;
  if (!factionKey || !FACTION_COLORS[factionKey]) {
    parent.appendChild(document.createTextNode(name));
    return;
  }
  const span = document.createElement("span");
  span.className = "faction-color";
  applyFactionTextColor(span, factionKey);
  span.textContent = match[1];
  parent.appendChild(span);
  parent.appendChild(document.createTextNode(name.slice(match[1].length)));
}

const sizeFilterOptions = document.getElementById("size-filter-options");
const purposeFilterOptions = document.getElementById("purpose-filter-options");
const typeFilterOptions = document.getElementById("type-filter-options");
const shipOptionsList = document.getElementById("ship-options-list");
const loadShipBtn = document.getElementById("load-ship-btn");
const clearShipBtnTop = document.getElementById("clear-ship-btn-top");
const importLoadoutsBtn = document.getElementById("import-loadouts-btn");
const selectGameLoadoutBtn = document.getElementById("select-game-loadout-btn");
const selectChassisLoadoutBtn = document.getElementById("select-chassis-loadout-btn");
const shipHighPresetBtn = document.getElementById("ship-high-preset-btn");
const shipMinimumPresetBtn = document.getElementById("ship-minimum-preset-btn");
const shipDetail = document.getElementById("ship-detail");
const shipNameEl = document.getElementById("ship-name");
const importedLoadoutWarningsEl = document.getElementById("imported-loadout-warnings");
const shipSummaryEl = document.getElementById("ship-summary");
const groupsContainer = document.getElementById("groups-container");
const ammoInfoBoxContainer = document.getElementById("ammo-info-box-container");
const ammunitionContainer = document.getElementById("ammunition-container");
const countermeasureContainer = document.getElementById("countermeasure-container");
const droneContainer = document.getElementById("drone-container");
const deployableContainer = document.getElementById("deployable-container");
const crewContainer = document.getElementById("crew-container");
const shipNoteInput = document.getElementById("ship-note-input");
const addToCartBtn = document.getElementById("add-to-cart-btn");
// Same action as addToCartBtn, next to Select Loadout at the top of the
// builder -- see setAddToCartBtnLabel()/addSelectedShipToCart() below,
// same top/bottom-copy pattern as clearShipBtnTop/clearShipBtnBottom.
const addToCartBtnTop = document.getElementById("add-to-cart-btn-top");

// Keeps both Add To Fleet List buttons (top and bottom copies) in sync --
// every other call site sets the label through this instead of touching
// addToCartBtn/addToCartBtnTop directly, so neither copy can drift out of
// sync with the other (e.g. one still reading "Add To Fleet List" while
// editCartEntry() has switched the other to "Update Fleet List").
function setAddToCartBtnLabel(text) {
  addToCartBtn.textContent = text;
  addToCartBtnTop.textContent = text;
}

const addToSavedLoadoutsBtn = document.getElementById("add-to-saved-loadouts-btn");
// Same action as addToSavedLoadoutsBtn, next to Select Filter Loadout at
// the top of the picker -- see setAddToSavedLoadoutsBtnsDisabled() below,
// same top/bottom-copy pattern as addToCartBtn/addToCartBtnTop.
const addToSavedLoadoutsBtnTop = document.getElementById("add-to-saved-loadouts-btn-top");
const addToSavedLoadoutsStatus = document.getElementById("add-to-saved-loadouts-status");
const clearShipBtnBottom = document.getElementById("clear-ship-btn-bottom");
const cartBody = document.getElementById("cart-body");
const cartEmptyMsg = document.getElementById("cart-empty-msg");
const analysisFileNameInput = document.getElementById("analysis-file-name-input");
const downloadAnalysisBtn = document.getElementById("download-analysis-btn");
const uploadAnalysisInput = document.getElementById("upload-analysis-input");
const headerShareBtn = document.getElementById("header-share-btn");
const shareModalOverlay = document.getElementById("share-modal-overlay");
const shareModalStatus = document.getElementById("share-modal-status");
const shareModalResult = document.getElementById("share-modal-result");
const shareModalResultInput = document.getElementById("share-modal-result-input");
const shareModalCopyBtn = document.getElementById("share-modal-copy-btn");
const shareModalCancelBtn = document.getElementById("share-modal-cancel-btn");
const shareModalGenerateBtn = document.getElementById("share-modal-generate-btn");
const wareCostListSection = document.getElementById("ware-cost-list");
const wareCostListThead = document.getElementById("ware-cost-list-thead");
const wareCostListBody = document.getElementById("ware-cost-list-body");
const saveCartBtn = document.getElementById("save-cart-btn");
const loadCartInput = document.getElementById("load-cart-input");
const cartNameInput = document.getElementById("cart-name-input");
const fleetListTabsEl = document.getElementById("fleet-list-tabs");
const buildMethodModalOverlay = document.getElementById("build-method-modal-overlay");
const buildMethodModalPriorityList = document.getElementById("build-method-modal-priority-list");
const buildMethodModalCancelBtn = document.getElementById("build-method-modal-cancel-btn");
const buildMethodModalSaveBtn = document.getElementById("build-method-modal-save-btn");
const equipmentPickerModalOverlay = document.getElementById("equipment-picker-modal-overlay");
const equipmentPickerModalTitle = document.getElementById("equipment-picker-modal-title");
const equipmentPickerApplyAllCheckbox = document.getElementById("equipment-picker-apply-all-checkbox");
const equipmentPickerModalStatus = document.getElementById("equipment-picker-modal-status");
const equipmentPickerThead = document.getElementById("equipment-picker-thead");
const equipmentPickerTbody = document.getElementById("equipment-picker-tbody");
const equipmentPickerClearBtn = document.getElementById("equipment-picker-clear-btn");
const equipmentPickerCancelBtn = document.getElementById("equipment-picker-cancel-btn");
const priceOverrideBtn = document.getElementById("price-override-btn");
const priceOverrideModalOverlay = document.getElementById("price-override-modal-overlay");
const priceOverrideModalStatus = document.getElementById("price-override-modal-status");
const priceOverrideTbody = document.getElementById("price-override-tbody");
const priceOverrideCloseBtn = document.getElementById("price-override-close-btn");
const priceOverrideSearchInput = document.getElementById("price-override-search-input");
const priceOverrideSummaryList = document.getElementById("price-override-summary-list");
const priceOverrideFilterProductionCheckbox = document.getElementById("price-override-filter-production");
const priceOverrideFilterRawCheckbox = document.getElementById("price-override-filter-raw");
const priceOverrideFilterProcurementCheckbox = document.getElementById("price-override-filter-procurement");
const importLoadoutsModalOverlay = document.getElementById("import-loadouts-modal-overlay");
const importLoadoutsPathSection = document.getElementById("import-loadouts-path-section");
const importLoadoutsPathInput = document.getElementById("import-loadouts-path-input");
const importLoadoutsFileInput = document.getElementById("import-loadouts-file-input");
const importLoadoutsStatus = document.getElementById("import-loadouts-status");
const importLoadoutsCancelBtn = document.getElementById("import-loadouts-cancel-btn");
const importLoadoutsRunBtn = document.getElementById("import-loadouts-run-btn");
const importRawXmlLoadoutBtn = document.getElementById("import-raw-xml-loadout-btn");
const importRawXmlLoadoutModalOverlay = document.getElementById("import-raw-xml-loadout-modal-overlay");
const importRawXmlLoadoutTextarea = document.getElementById("import-raw-xml-loadout-textarea");
const importRawXmlLoadoutStatus = document.getElementById("import-raw-xml-loadout-status");
const importRawXmlLoadoutCancelBtn = document.getElementById("import-raw-xml-loadout-cancel-btn");
const importRawXmlLoadoutConfirmBtn = document.getElementById("import-raw-xml-loadout-confirm-btn");
const exportLoadoutsBtn = document.getElementById("export-loadouts-btn");
const clearLoadoutsBtn = document.getElementById("clear-loadouts-btn");
const selectGameLoadoutModalOverlay = document.getElementById("select-game-loadout-modal-overlay");
const selectGameLoadoutModalTitle = document.getElementById("select-game-loadout-modal-title");
const selectGameLoadoutList = document.getElementById("select-game-loadout-list");
const selectGameLoadoutCancelBtn = document.getElementById("select-game-loadout-cancel-btn");

// lastWareCostList/activeBuildFocus/activeFallbackMethods used to live here
// as module-level globals for "the Active column" specifically -- now every
// fleet (not just one "active" one) carries its own .wareCostList/
// .buildMethodPriority directly (see makeFleet()), read via
// activeFleet().___ wherever the active fleet's own values are needed.

// Every real build method, fetched once from GET /api/build_methods (see
// BUILD_METHODS in generate_ships_table.py for how it's curated/ordered) --
// both the options the modal's priority list offers and the starting point
// for any column whose own buildMethodPriority is still null.
let allBuildMethods = [];

// Which column the Build Method modal is currently open for -- one of the
// objects wareCostListColumns() builds ({fleetIndex, buildMethodPriority,
// ...}), read by the modal's own Save handler to call
// recomputeFleetBuildConfig(column.fleetIndex, ...) on Save. null while the
// modal is closed.
let buildMethodModalTarget = null;

// The modal's own working copy of the priority list while open --
// [{name, included}], in display/priority order -- edited in place by the
// checkbox/reorder controls (see renderBuildMethodModalPriorityList()) and
// only committed to the target column's own buildMethodPriority on Save.
let buildMethodModalPriorityOrder = [];

// A ships_base.icon value (e.g. "ship_s_fighter_01") names a PNG under
// data/images/ships/symbols/ -- see generate_ship_icons.py -- served by
// api.py at this same relative path. Returns null for a ship/type with no
// icon on record, so callers can skip rendering an <img> entirely rather
// than showing a broken-image icon.
function shipIconUrl(icon) {
  return icon ? `/images/ships/symbols/${icon}.png` : null;
}

function buildIconImg(icon, className) {
  const img = document.createElement("img");
  img.src = shipIconUrl(icon);
  img.alt = "";
  img.className = className;
  return img;
}

// Real size progression (ships_base.size), not alphabetical order (which
// would read "l, m, s, xl") -- used for the Size filter's own checkbox
// order (smallest first).
const SIZE_ORDER = ["s", "m", "l", "xl"];

// The ship picker list's own size priority -- deliberately the reverse of
// SIZE_ORDER (largest first, XL at the top) per explicit request, even
// though the Size filter checkboxes themselves stay smallest-first.
const SHIP_LIST_SIZE_ORDER = ["xl", "l", "m", "s"];

// ships_base.ship_type values grouped into the three broad roles X4's own
// ship-class menus conventionally use -- Military (small to large), Civilian
// (small to large), then a small Utility bucket for the ones that don't fit
// either (tug, scavenger, envoy, expeditionary, compactor). Any ship_type
// not listed here (shouldn't happen -- every value currently in ships_base
// is accounted for) falls back to sorting after all three groups rather
// than being silently dropped from the filter.
const SHIP_TYPE_CATEGORY_ORDER = ["military", "civilian", "utility"];
const SHIP_TYPE_CATEGORY = {
  scout: "military",
  fighter: "military",
  heavyfighter: "military",
  gunboat: "military",
  corvette: "military",
  frigate: "military",
  destroyer: "military",
  battleship: "military",
  carrier: "military",
  courier: "civilian",
  transporter: "civilian",
  freighter: "civilian",
  miner: "civilian",
  largeminer: "civilian",
  builder: "civilian",
  resupplier: "civilian",
  tug: "utility",
  scavenger: "utility",
  envoy: "utility",
  expeditionary: "utility",
  compactor: "utility",
};

// Primary: broad role category (SHIP_TYPE_CATEGORY_ORDER). Secondary:
// alphabetical by the ship_type string itself -- shared by the Type
// filter's own checkbox order and, via compareShips() below, the ship
// picker list.
function compareShipTypes(a, b) {
  const categoryDelta =
    SHIP_TYPE_CATEGORY_ORDER.indexOf(SHIP_TYPE_CATEGORY[a] ?? "") - SHIP_TYPE_CATEGORY_ORDER.indexOf(SHIP_TYPE_CATEGORY[b] ?? "");
  return categoryDelta !== 0 ? categoryDelta : a.localeCompare(b);
}

// Ship picker list order: 1) size, largest first (SHIP_LIST_SIZE_ORDER --
// note this is the *opposite* direction from the Size filter's own
// checkbox order), 2) role category and 3) specific ship_type
// alphabetically (both via compareShipTypes), then 4) ship name as the
// final tiebreaker once type itself can't distinguish two ships further.
// Each ship's own real `size` field drives step 1 directly -- see
// buildTypeFilterEntries() below for the Type filter's own, different need
// (a checkbox per *type*, several of which span more than one size).
function compareShips(a, b) {
  const sizeDelta = SHIP_LIST_SIZE_ORDER.indexOf(a.size) - SHIP_LIST_SIZE_ORDER.indexOf(b.size);
  if (sizeDelta !== 0) return sizeDelta;
  const typeDelta = compareShipTypes(a.ship_type, b.ship_type);
  return typeDelta !== 0 ? typeDelta : a.name.localeCompare(b.name);
}

// Checkable entries for the Type filter: {value, label, icon}. Most
// ship_types are a single size, and get one plain checkbox (e.g.
// "Fighter"). Some aren't -- "miner" is 20 M ships plus 6 S ones, "carrier"
// is 11 XL ships plus a single lone L outlier (Guppy), "destroyer" is 16 L
// plus one XL outlier, "heavyfighter" is mostly S with a couple of M,
// "scavenger" is one L and one M. A single "Miner" checkbox spanning both
// sizes gives no way to pick just the S ones (or just the M ones) from the
// Type filter alone -- only by also reaching for the separate Size filter,
// which isn't obvious and easy to forget -- so any type with more than one
// size present is split into one checkbox per (type, size) pair instead,
// e.g. "Miner (S)"/"Miner (M)", each an independently checkable filter
// value (see shipMatchesTypeValue()) rather than a cosmetic label only.
// Sorted the same way as the ship list itself (size largest-first, then
// role category, then alphabetically) -- a split type's two checkboxes
// naturally land in their own respective size groups rather than staying
// adjacent, which is correct: size is still the top sort priority.
function buildTypeFilterEntries() {
  const sizesByType = {};
  for (const ship of allShips) {
    sizesByType[ship.ship_type] ??= new Set();
    sizesByType[ship.ship_type].add(ship.size);
  }

  const entries = [];
  for (const [type, sizesSet] of Object.entries(sizesByType)) {
    const sizes = [...sizesSet];
    if (sizes.length === 1) {
      entries.push({ value: type, label: type, ship_type: type, size: sizes[0] });
    } else {
      for (const size of sizes) {
        entries.push({ value: `${type}:${size}`, label: `${type} (${size.toUpperCase()})`, ship_type: type, size });
      }
    }
  }

  // Icon per entry -- majority vote among exactly that entry's own ships
  // (same "most common wins" reasoning typeIconMap() used before splitting
  // existed, just scoped to the split (type, size) pair now instead of the
  // whole type, since a single (type, size) bucket could still in
  // principle use more than one icon).
  for (const entry of entries) {
    const counts = {};
    for (const ship of allShips) {
      if (ship.ship_type !== entry.ship_type || ship.size !== entry.size) continue;
      counts[ship.icon] = (counts[ship.icon] ?? 0) + 1;
    }
    entry.icon = Object.entries(counts).sort((a, b) => b[1] - a[1])[0][0];
  }

  entries.sort((a, b) => {
    const sizeDelta = SHIP_LIST_SIZE_ORDER.indexOf(a.size) - SHIP_LIST_SIZE_ORDER.indexOf(b.size);
    return sizeDelta !== 0 ? sizeDelta : compareShipTypes(a.ship_type, b.ship_type);
  });

  return entries;
}

// Matches a Type filter checkbox's value against a ship -- either a plain
// ship_type (unsplit types) or "<ship_type>:<size>" (split types, see
// buildTypeFilterEntries()).
function shipMatchesTypeValue(ship, value) {
  const sep = value.indexOf(":");
  if (sep === -1) return ship.ship_type === value;
  return ship.ship_type === value.slice(0, sep) && ship.size === value.slice(sep + 1);
}

async function loadShips() {
  const response = await fetch("/api/ships");
  allShips = (await response.json()).sort(compareShips);
  populateFilterOptions();
  renderShipOptions();
}

async function loadMissiles() {
  const response = await fetch("/api/missiles");
  allMissiles = await response.json();
}

async function loadDrones() {
  const response = await fetch("/api/drones");
  allDrones = await response.json();
}

async function loadDeployables() {
  const response = await fetch("/api/deployables");
  allDeployables = await response.json();
}

async function loadCountermeasures() {
  const response = await fetch("/api/countermeasures");
  allCountermeasures = await response.json();
}

async function loadCrew() {
  const response = await fetch("/api/crew");
  const [crewWare] = await response.json();
  crewWareId = crewWare?.ware_id ?? null;
  allCrew = CREW_ROLES.map(({ role, label }) => ({ ...crewWare, ware_id: role, name: label }));
}

async function loadBuildMethods() {
  const response = await fetch("/api/build_methods");
  allBuildMethods = await response.json();
}

// Fills the size/type filter fieldsets with one checkbox per distinct value
// actually present in allShips, sorted, so the filters never offer a choice
// with zero matches. Multiple checkboxes in the same group can be checked
// at once; none checked means "don't filter on that dimension".
function populateFilterOptions() {
  // Sizes are stored/filtered on as their raw lowercase abbreviation
  // (ship.size, e.g. "s"/"m"/"l"/"xl" -- same value renderShipSummary()
  // already .toUpperCase()s for display elsewhere), matching
  // sizeValues.includes(ship.size) in renderShipOptions().
  const sizeEntries = [...new Set(allShips.map((ship) => ship.size))]
    .sort((a, b) => SIZE_ORDER.indexOf(a) - SIZE_ORDER.indexOf(b))
    .map((size) => ({ value: size, label: size.toUpperCase() }));

  // ship.purpose is a flat, single-valued AI role classification (e.g.
  // "fight"/"trade"/"mine") -- unlike Type, no ship has more than one, so
  // this needs none of buildTypeFilterEntries()'s multi-size splitting.
  const purposeEntries = [...new Set(allShips.map((ship) => ship.purpose))]
    .filter((purpose) => purpose != null)
    .sort((a, b) => a.localeCompare(b))
    .map((purpose) => ({ value: purpose, label: purpose.charAt(0).toUpperCase() + purpose.slice(1) }));

  buildCheckboxGroup(sizeFilterOptions, "size-filter", sizeEntries);
  buildCheckboxGroup(purposeFilterOptions, "purpose-filter", purposeEntries);
  buildCheckboxGroup(typeFilterOptions, "type-filter", buildTypeFilterEntries());
}

function buildCheckboxGroup(container, name, entries) {
  container.innerHTML = "";
  for (const entry of entries) {
    container.appendChild(buildCheckboxOption(name, entry.value, entry.label, entry.icon ?? null));
  }
}

function buildCheckboxOption(name, value, displayLabel, icon = null) {
  const label = document.createElement("label");
  const input = document.createElement("input");
  input.type = "checkbox";
  input.name = name;
  input.value = value;
  input.addEventListener("change", renderShipOptions);
  label.appendChild(input);
  if (icon) label.appendChild(buildIconImg(icon, "type-icon"));
  label.appendChild(document.createTextNode(displayLabel));
  return label;
}

function checkedValues(name) {
  return Array.from(document.querySelectorAll(`input[name="${name}"]:checked`)).map((input) => input.value);
}

// "All"/"None" buttons are static markup (unlike the checkboxes themselves,
// which are (re)built from the API response), so wiring them up once here
// at load time is enough.
for (const btn of document.querySelectorAll(".filter-all-btn")) {
  btn.addEventListener("click", () => {
    for (const input of document.querySelectorAll(`input[name="${btn.dataset.filter}"]`)) {
      input.checked = true;
    }
    renderShipOptions();
  });
}

for (const btn of document.querySelectorAll(".filter-none-btn")) {
  btn.addEventListener("click", () => {
    for (const input of document.querySelectorAll(`input[name="${btn.dataset.filter}"]`)) {
      input.checked = false;
    }
    renderShipOptions();
  });
}

// Rebuilds the ship picker listbox from allShips filtered by the current
// size/type checkbox selections (no checkboxes checked in a group means
// "don't filter on that dimension"). Resets the current selection since it
// may no longer be in the filtered set.
//
// Shared with openSelectGameLoadoutModal(), which applies this same
// predicate (plus compareShips' own ordering) to the saved-loadout list
// when opened generically, so "what ships are currently visible in the
// picker" and "what ships' loadouts show up in Select Filter Loadout"
// never drift apart.
function shipPassesCurrentFilters(ship) {
  const sizeValues = checkedValues("size-filter");
  const purposeValues = checkedValues("purpose-filter");
  const typeValues = checkedValues("type-filter");
  return (
    (sizeValues.length === 0 || sizeValues.includes(ship.size)) &&
    (purposeValues.length === 0 || purposeValues.includes(ship.purpose)) &&
    (typeValues.length === 0 || typeValues.some((value) => shipMatchesTypeValue(ship, value)))
  );
}

function renderShipOptions() {
  shipOptionsList.innerHTML = "";

  const filtered = allShips.filter(shipPassesCurrentFilters);

  if (filtered.length === 0) {
    const empty = document.createElement("div");
    empty.className = "ship-options-empty";
    empty.textContent = "No ships match the current filters.";
    shipOptionsList.appendChild(empty);
  }

  for (const ship of filtered) {
    shipOptionsList.appendChild(buildShipOptionRow(ship));
  }

  selectedShipWareId = "";
  loadShipBtn.disabled = true;
  editingIndex = null;
  setAddToCartBtnLabel("Add To Fleet List");
  saveState();
}

// One clickable row in the ship picker listbox: its class symbol (see
// shipIconUrl()) plus "Name (size, type)", matching what the old <select>'s
// <option> text used to say. Clicking always starts a fresh "add" -- same
// as the native <select>'s own "change" event used to (see
// applyShipSelection() for the shared part also used by editCartEntry(),
// which must NOT reset editingIndex/addToCartBtn's label -- that's why
// that part is factored out separately rather than done here).
// A ship's ware_id always starts with its design race (e.g.
// "ship_par_s_heavyfighter_01_a" -> "PAR") -- unlike ships_base.owners
// (the full, often multi-faction sales list -- a Paranid-designed ship
// is commonly sold through Buccaneers/Holy Order/Trinity too, without
// "paranid" itself necessarily appearing there), this is a single,
// unambiguous per-ship value, so it's used as the picker's "owner
// faction" abbreviation instead of owners.
function shipRaceAbbreviation(wareId) {
  const match = wareId.match(/^ship_([a-z]+)_/);
  return match ? match[1].toUpperCase() : null;
}

function buildShipOptionRow(ship) {
  const row = document.createElement("div");
  row.className = "ship-option-row";
  row.dataset.wareId = ship.ware_id;
  row.setAttribute("role", "option");

  if (ship.icon) row.appendChild(buildIconImg(ship.icon, "ship-icon"));

  const textCol = document.createElement("span");
  textCol.className = "ship-option-text";

  const text = document.createElement("span");
  text.className = "ship-option-name";
  text.textContent = `${ship.name} (${ship.size}, ${ship.ship_type})`;
  textCol.appendChild(text);

  const race = shipRaceAbbreviation(ship.ware_id);
  if (race) {
    const raceLabel = document.createElement("span");
    raceLabel.className = "ship-option-race";
    applyFactionTextColor(raceLabel, RACE_PREFIX_TO_FACTION[race.toLowerCase()]);
    raceLabel.textContent = race;
    textCol.appendChild(raceLabel);
  }

  row.appendChild(textCol);

  row.addEventListener("click", () => {
    applyShipSelection(ship.ware_id);
    editingIndex = null;
    setAddToCartBtnLabel("Add To Fleet List");
  });

  return row;
}

// Highlights `wareId`'s row (if present in the currently rendered list) and
// enables/disables the Load button accordingly -- the part of "selecting a
// ship" shared between a user's click (buildShipOptionRow(), which also
// resets editingIndex) and editCartEntry()'s programmatic restore (which
// must not, since it's what sets editingIndex in the first place).
function applyShipSelection(wareId) {
  selectedShipWareId = wareId;
  for (const row of shipOptionsList.querySelectorAll(".ship-option-row")) {
    row.classList.toggle("selected", row.dataset.wareId === wareId);
  }
  loadShipBtn.disabled = !wareId;
}

loadShipBtn.addEventListener("click", async () => {
  const identifier = selectedShipWareId;
  if (!identifier) return;
  const response = await fetch(`/api/ships/${encodeURIComponent(identifier)}/groups`);
  const data = await response.json();
  if (data.error) {
    alert(`Could not load ship: ${data.error}`);
    return;
  }
  currentShip = data;
  missileAmounts = {}; // a freshly (re)loaded ship always starts with no ammo/countermeasures/drones/deployables/crew picked
  countermeasureAmounts = {};
  droneAmounts = {};
  deployableAmounts = {};
  crewAmounts = {};
  importedLoadoutWarningsEl.classList.add("hidden");
  renderShipDetail(data);
});

const COMPONENT_TYPE_LABELS = {
  engine: "Engines",
  weapon: "Weapons",
  missile_launcher: "Missile Launchers",
  shield: "Shields",
  turret: "Turrets",
  thruster: "Thrusters",
  software: "Software",
};
const COMPONENT_TYPE_ORDER = ["engine", "thruster", "weapon", "missile_launcher", "shield", "turret", "software"];

// Singular form of COMPONENT_TYPE_LABELS, for the equipment picker
// button/modal title ("Select Weapon", not "Select Weapons") -- a
// separate map rather than stripping a trailing "s" since "Software" has
// none to strip.
const COMPONENT_TYPE_SINGULAR_LABELS = {
  engine: "Engine",
  weapon: "Weapon",
  missile_launcher: "Missile Launcher",
  shield: "Shield",
  turret: "Turret",
  thruster: "Thruster",
  software: "Software",
};

// Grouping for the Fleet List's own "Loadout" display (see
// renderCart()) -- a superset of COMPONENT_TYPE_LABELS/_ORDER above (which
// only covers ship_component_groups' component_type values) plus "chassis"
// (the ship hull itself) and the three shared-pool categories that never
// go through a group at all (missile/drone/deployable). "main_shield"/
// "surface_element_shield" split out of the generic "shield"
// component_type (see shieldDisplayCategory() below) the same way
// summarize_production.py's group_by_component_type option already splits
// them for the Ware Cost List, rather than lumping every shield together.
// Anything tagged with a category not listed here (shouldn't normally
// happen) falls back to CART_DISPLAY_FALLBACK_CATEGORY, mirroring the Ware
// Cost List's own "production_wares" catch-all.
const CART_DISPLAY_LABELS = {
  chassis: "Chassis",
  crew_marine: "Marines",
  crew_service: "Service Crew",
  engine: "Engines",
  thruster: "Thrusters",
  weapon: "Weapons",
  missile_launcher: "Missile Launchers",
  main_shield: "Main Shields",
  surface_element_shield: "Surface Element Shields",
  turret: "Turrets",
  software: "Software",
  missile: "Ammunition",
  countermeasure: "Countermeasures",
  drone: "Drones",
  deployable: "Deployables",
  production_wares: "Other",
};
// Matches the ship builder's own on-screen section order exactly (see
// renderShipDetail()/COMPONENT_TYPE_ORDER for the equipment groups, then
// renderAmmunitionSection/renderDroneSection/renderDeployableSection/
// renderCountermeasureSection/renderCrewSection for the shared-pool
// sections after them, in that call order) -- "chassis" prepended (the
// ship itself, picked before any of its equipment) and "production_wares"
// appended (the catch-all "other" bucket, not a real builder section at
// all). Reused as-is by the Ware Cost List's own category ordering (see
// sortCategoriesForDisplay()) so both places agree.
const CART_DISPLAY_ORDER = [
  "chassis",
  "engine",
  "thruster",
  "weapon",
  "missile_launcher",
  "main_shield",
  "surface_element_shield",
  "turret",
  "software",
  "missile",
  "drone",
  "deployable",
  "countermeasure",
  "crew_marine",
  "crew_service",
  "production_wares",
];
const CART_DISPLAY_FALLBACK_CATEGORY = "production_wares";

// Splits the generic "shield" component_type into "main_shield" vs
// "surface_element_shield" for CART_DISPLAY_LABELS/_ORDER -- any other
// component_type passes through unchanged. Shared by addToCartBtn's
// handler (which knows a row is a bonus shield from its own
// "bonus-shield-row" class) and reconstructCartEntry() (which instead
// reads it back off the wares_list item's own "category" override, set
// when it was originally added -- see waresListItem.category below).
function shieldDisplayCategory(componentType, isSurfaceElementShield) {
  if (componentType !== "shield") return componentType;
  return isSurfaceElementShield ? "surface_element_shield" : "main_shield";
}

// group_name alone is NOT unique within data.groups -- a dedicated medium
// shield protecting a specific engine/turret/weapon group shares that
// group's own raw group_name from the game's XML, distinguished only by
// component_type ("shield" vs whatever the sibling is). See
// query_ship_groups()'s docstring in query_ship_components.py. This key is
// what actually identifies one picker uniquely, so it's used for DOM
// dataset identity and for the cart's `selections` map instead of raw
// group_name.
function groupKey(group) {
  return `${group.group_name}::${group.component_type}`;
}

// UI-only requirement: these groups must have a selection before a ship
// can be added to the fleet list. Not enforced anywhere server-side
// (the API will happily calculate a cart missing them) -- purely a picker
// safeguard against forgetting an engine/thruster/core-software choice
// before committing a ship. Engine/thruster are matched by component_type
// (their group_name is always exactly that literal string anyway); software
// slots are matched by group_name, since component_type "software" alone
// doesn't distinguish which category.
const REQUIRED_SOFTWARE_LABELS = {
  software_scannerlongrange: "Long Range Scanner Software",
  software_scannerobject: "Object Scanner Software",
  software_flightassist: "Flight Assist Software",
};

function requiredGroupLabel(group) {
  if (group.component_type === "engine") return "Engine";
  if (group.component_type === "thruster") return "Thruster";
  return REQUIRED_SOFTWARE_LABELS[group.group_name] ?? null;
}

// Which of a ship's recommended groups (per requiredGroupLabel() above)
// have no selection in `selections` -- shared by addToCartBtn's handler
// (which instead reads this straight off the DOM's own
// .group-row[data-required-label] rows, an equivalent but DOM-driven
// computation) and reconstructCartEntry() (which has no DOM to query at
// all, only the raw groups/selections data from a saved file).
function missingRequiredLabels(groups, selections) {
  const missing = [];
  for (const group of groups) {
    const label = requiredGroupLabel(group);
    if (label && !selections[groupKey(group)]) missing.push(label);
  }
  return missing;
}

// Builds one .group-row (label + picker <select>) for a single group. Used
// for both ordinary groups and bonus-M-shield groups -- the latter get a
// friendlier label (their group_name is shared with the group they
// protect, not meant for display on its own) but are otherwise a
// completely ordinary, independently pickable group: same dataset
// attributes, same .group-select class, so all the existing cart-building/
// edit-repopulating code (which just queries every ".group-row" under
// #groups-container) picks them up automatically with no special-casing.
function buildGroupRow(group, { isLinkedShield = false, sectionType } = {}) {
  const row = document.createElement("div");
  row.className = "group-row";
  row.dataset.groupKey = groupKey(group);
  row.dataset.groupName = group.group_name;
  row.dataset.slotCount = group.slot_count;
  // Read back in addToCartBtn's handler to group the fleet list's
  // own display by component type (see CART_DISPLAY_GROUP_LABELS/
  // renderCart()) -- bonus-M-shield rows are still plain "shield" here
  // (isLinkedShield only changes the *label* above), so they group
  // together with ordinary main shields, same as this app's own picker
  // sections already treat them as one "Shields" category.
  row.dataset.componentType = group.component_type;
  // Which *rendered section* (COMPONENT_TYPE_ORDER entry) this row's card
  // lives under -- not always the same as component_type above, since a
  // linked bonus shield's own component_type is "shield" but it's
  // rendered nested inside its parent's section (e.g. "engine"). Used by
  // applyHighPreset()/applyMinimumPreset() to scope a section's preset
  // buttons to exactly the rows visually inside that section.
  if (sectionType) row.dataset.sectionType = sectionType;

  const label = document.createElement("label");
  label.textContent = isLinkedShield
    ? `Bonus M Shield (x${group.slot_count})`
    : `${group.group_name} (${group.component_type}, ${group.size}, x${group.slot_count})`;

  const requiredLabel = requiredGroupLabel(group);
  if (requiredLabel) {
    row.dataset.requiredLabel = requiredLabel;
    const marker = document.createElement("span");
    marker.className = "required-marker";
    marker.textContent = " *";
    marker.title = "Recommended -- leaving this unselected will show a warning in the fleet list";
    label.appendChild(marker);
  }
  row.appendChild(label);

  const select = document.createElement("select");
  select.className = "group-select";
  const noneOption = document.createElement("option");
  noneOption.value = "";
  noneOption.textContent = "-- none --";
  select.appendChild(noneOption);
  for (const option of group.options) {
    const opt = document.createElement("option");
    opt.value = option.ware_id;
    opt.textContent = option.name;
    // <option> can't render partial-colored text (no nested markup
    // support), so the whole option is tinted in its race's color when
    // its name carries a recognized race prefix -- see raceColorForName().
    const raceColor = raceColorForName(option.name);
    if (raceColor) opt.style.color = raceColor;
    // Only set for missile-capable turrets/weapons (null for everything
    // else) -- read back by updateSelectedAmmoCapacity() on every
    // .group-select change to keep the summary panel's running total live.
    if (option.ammunition_capacity != null) {
      opt.dataset.ammoCapacity = option.ammunition_capacity;
    }
    // Comma-joined set of missile compatibility tags this specific
    // launcher accepts (e.g. "dumbfire,mediumdumbfire") -- read back by
    // compatibleMissiles() to decide which missiles the Ammunition section
    // offers, given whatever's currently selected across every launcher.
    if (option.ammunition_tags) {
      opt.dataset.ammoTags = option.ammunition_tags;
    }
    select.appendChild(opt);
  }
  if (group.options.length === 0) {
    select.disabled = true;
    noneOption.textContent = "-- no compatible equipment found --";
  }
  // The <select> stays in the DOM (just hidden) rather than being removed
  // -- every existing piece of cart-building/edit-restore/ammo-capacity
  // logic reads or sets its .value/.options and listens for its "change"
  // event, none of which needs to change now that a button+modal (below)
  // is the actual visible/interactive control. See openEquipmentPickerModal().
  select.classList.add("hidden");
  row.appendChild(select);

  const pickerBtn = document.createElement("button");
  pickerBtn.type = "button";
  pickerBtn.className = "group-select-btn";
  pickerBtn.disabled = group.options.length === 0;
  pickerBtn.addEventListener("click", () => openEquipmentPickerModal(row, group));
  row.appendChild(pickerBtn);
  syncGroupSelectButtonLabel(row);

  return row;
}

// Sets a .group-row's visible picker button to reflect its (hidden)
// .group-select's current value -- called right after building the row
// (nothing selected yet) and anywhere else the select's value changes
// programmatically rather than through the modal's own row click (see
// applyGroupSelections(), the edit-restore path). Not needed after an
// ordinary modal selection -- selectEquipmentPickerOption() calls it
// directly there.
function syncGroupSelectButtonLabel(row) {
  const select = row.querySelector(".group-select");
  const btn = row.querySelector(".group-select-btn");
  if (!select || !btn) return;

  if (!select.value) {
    btn.textContent = select.options[0].textContent; // "-- none --" or "-- no compatible equipment found --"
    btn.classList.add("group-select-btn-empty");
    return;
  }
  btn.classList.remove("group-select-btn-empty");
  const selectedOption = select.options[select.selectedIndex];
  btn.textContent = "";
  appendNameWithFactionColor(btn, selectedOption.textContent);
}

// The .group-row/group data currently open in the equipment picker modal,
// or null -- selectEquipmentPickerOption()/the Clear button need to know
// which row's <select> to update (and, for the "apply to all matching
// slots" checkbox, which group's siblings to consider), and
// closeEquipmentPickerModal() clears both so a stray call after the
// modal's closed is a no-op.
let equipmentPickerModalRow = null;
let equipmentPickerModalGroup = null;

// True when `group` is a dedicated bonus/surface-element shield -- a
// group_name shared with a non-shield sibling group on the same ship
// (see parse_component_slots' docstring in generate_ships_table.py) --
// as opposed to an ordinary standalone main shield slot. Mirrors the
// isLinkedShield distinction buildGroupRow()/renderShipDetail() already
// draw from the DOM structure, recomputed here from raw group data since
// the picker modal only has `currentShip.groups` to work with, not the
// rendered card layout.
function isLinkedShieldGroup(group, allGroups) {
  if (group.component_type !== "shield") return false;
  return allGroups.some((g) => g.group_name === group.group_name && g.component_type !== "shield");
}

// Every *other* group on the ship that the "apply to all matching slots"
// checkbox should also try to update alongside `group` -- same
// component_type and size, and (for shields specifically) the same
// bonus-vs-main status, so a main shield selection never bleeds into a
// bonus M shield slot or vice versa. Deliberately does NOT check whether
// a given ware_id is actually valid for each sibling here -- same-type/
// same-size slots on one ship aren't guaranteed to share the same option
// pool (e.g. a hull-locked "mandatory" mount alongside ordinary ones, or
// a mining ship's mixed-tag turret groups both size M) -- that check
// happens per-sibling in selectEquipmentPickerOption() instead, right
// before applying.
function siblingGroupsForBulkApply(group, allGroups) {
  const groupIsLinkedShield = isLinkedShieldGroup(group, allGroups);
  return allGroups.filter((other) => {
    if (other === group) return false;
    if (other.component_type !== group.component_type || other.size !== group.size) return false;
    if (group.component_type === "shield" && isLinkedShieldGroup(other, allGroups) !== groupIsLinkedShield) return false;
    return true;
  });
}

// Opens the equipment picker modal for one .group-row: fetches each
// option's own level-1 production inputs (POST /api/level1_parts, one
// summarize() call per option server-side -- see that endpoint's own
// docstring for why a single combined call wouldn't work here, each row
// needs its *own* inputs, not a total across every option) and renders a
// table with Name/Min/Avg/Max Price plus one dynamic column per distinct
// input ware across every option in this group. A group with no options
// at all never gets here -- its button is disabled (see buildGroupRow()).
async function openEquipmentPickerModal(row, group) {
  equipmentPickerModalRow = row;
  equipmentPickerModalGroup = group;
  equipmentPickerApplyAllCheckbox.checked = false;
  equipmentPickerModalTitle.textContent = `Select ${COMPONENT_TYPE_SINGULAR_LABELS[group.component_type] ?? "Equipment"}`;
  equipmentPickerThead.innerHTML = "";
  equipmentPickerTbody.innerHTML = "";
  equipmentPickerModalStatus.textContent = "Loading level 1 wares…";
  equipmentPickerModalStatus.classList.remove("hidden");
  equipmentPickerModalOverlay.classList.remove("hidden");

  // Level-1 wares are an enhancement on top of the name/price columns,
  // not something selection depends on -- if the request fails, still
  // render the table (just without those extra columns) rather than
  // leaving the picker unusable.
  let partsData = { parts: {}, part_names: {} };
  try {
    const response = await fetch("/api/level1_parts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ware_ids: group.options.map((option) => option.ware_id) }),
    });
    if (response.ok) partsData = await response.json();
  } catch {
    // fall through with the empty default above
  }

  // The row's own selection could have changed (or the modal could have
  // been closed) while the fetch above was in flight -- only render if
  // this call is still the one the user is looking at.
  if (equipmentPickerModalRow !== row) return;
  equipmentPickerModalStatus.classList.add("hidden");
  renderEquipmentPickerTable(row, group, partsData);
}

function renderEquipmentPickerTable(row, group, partsData) {
  const select = row.querySelector(".group-select");
  const parts = partsData.parts ?? {};
  const partNames = partsData.part_names ?? {};

  // Union of every distinct level-1 input ware across all of this group's
  // options -- each option's own row only fills in the columns that
  // actually apply to it (see the per-row loop below), left blank
  // otherwise. Sorted by display name so column order doesn't depend on
  // dict/object key order.
  const partIds = new Set();
  for (const option of group.options) {
    for (const partId of Object.keys(parts[option.ware_id] ?? {})) partIds.add(partId);
  }
  const sortedPartIds = [...partIds].sort((a, b) => (partNames[a] ?? a).localeCompare(partNames[b] ?? b));

  equipmentPickerThead.innerHTML = "";
  const headRow = document.createElement("tr");
  for (const label of ["Name", "Min Price", "Avg Price", "Max Price", ...sortedPartIds.map((id) => partNames[id] ?? id)]) {
    const th = document.createElement("th");
    th.textContent = label;
    headRow.appendChild(th);
  }
  equipmentPickerThead.appendChild(headRow);

  equipmentPickerTbody.innerHTML = "";

  const clearRow = document.createElement("tr");
  clearRow.className = "equipment-picker-row equipment-picker-clear-row";
  const clearTd = document.createElement("td");
  clearTd.textContent = "-- none --";
  clearTd.colSpan = 4 + sortedPartIds.length;
  clearRow.appendChild(clearTd);
  clearRow.addEventListener("click", () => selectEquipmentPickerOption(""));
  equipmentPickerTbody.appendChild(clearRow);

  for (const option of group.options) {
    const tr = document.createElement("tr");
    tr.className = "equipment-picker-row";
    if (select.value === option.ware_id) tr.classList.add("selected");

    const nameTd = document.createElement("td");
    appendNameWithFactionColor(nameTd, option.name);
    tr.appendChild(nameTd);

    for (const priceField of ["price_min", "price_avg", "price_max"]) {
      const td = document.createElement("td");
      td.textContent = option[priceField] != null ? option[priceField] : "-";
      tr.appendChild(td);
    }

    const optionParts = parts[option.ware_id] ?? {};
    for (const partId of sortedPartIds) {
      const td = document.createElement("td");
      td.textContent = optionParts[partId] != null ? optionParts[partId] : "";
      tr.appendChild(td);
    }

    tr.addEventListener("click", () => selectEquipmentPickerOption(option.ware_id));
    equipmentPickerTbody.appendChild(tr);
  }
}

// Applies a modal row click (or the Clear button, via wareId "") to a
// single .group-row's real <select> -- dispatching "change" rather than
// just setting .value so the existing delegated listener (ammo capacity/
// Ammunition section) fires exactly as it would for a direct user
// selection, then syncs the visible button label.
function applySelectionToRow(row, wareId) {
  const select = row.querySelector(".group-select");
  select.value = wareId;
  select.dispatchEvent(new Event("change", { bubbles: true }));
  syncGroupSelectButtonLabel(row);
}

// Applies a modal row click (or the Clear button, via wareId "") to the
// open group, and -- when the "apply to all matching slots" checkbox is
// checked -- to every sibling slot too (same component_type/size, same
// bonus-vs-main status for shields; see siblingGroupsForBulkApply()).
// Clearing (wareId "") always applies to every sibling, since "-- none --"
// is trivially valid everywhere; a real selection only applies to a
// sibling whose own options actually include it -- confirmed by hand
// against the game data that same-type/same-size slots on one ship don't
// always share the same option pool (e.g. the Teladi Miner's front vs.
// back M turret groups, or a hull-locked weapon mount alongside ordinary
// ones), so this must check per-sibling rather than assume uniformity.
// A sibling this ware isn't valid for is left completely untouched
// (whatever it already had selected, or nothing), not cleared.
function selectEquipmentPickerOption(wareId) {
  if (!equipmentPickerModalRow || !equipmentPickerModalGroup) return;
  applySelectionToRow(equipmentPickerModalRow, wareId);

  if (equipmentPickerApplyAllCheckbox.checked && currentShip) {
    const siblings = siblingGroupsForBulkApply(equipmentPickerModalGroup, currentShip.groups);
    for (const sibling of siblings) {
      if (wareId !== "" && !sibling.options.some((option) => option.ware_id === wareId)) continue;
      const siblingRow = [...groupsContainer.querySelectorAll(".group-row")].find(
        (candidate) => candidate.dataset.groupKey === groupKey(sibling),
      );
      if (siblingRow) applySelectionToRow(siblingRow, wareId);
    }
  }

  closeEquipmentPickerModal();
}

function closeEquipmentPickerModal() {
  equipmentPickerModalGroup = null;
  equipmentPickerModalOverlay.classList.add("hidden");
  equipmentPickerModalRow = null;
}

equipmentPickerClearBtn.addEventListener("click", () => selectEquipmentPickerOption(""));
equipmentPickerCancelBtn.addEventListener("click", closeEquipmentPickerModal);

// GET /api/wares result, cached after the first successful fetch -- every
// ware in the database is a fixed, session-static list (nothing here
// changes while the app is running), so there's no reason to re-fetch it
// on every "Set Ware Price Overrides" click.
let allWaresCache = null;

// ware_id -> override price (a plain number). In-memory only (page refresh
// loses it), but real: sent as computeWareCostList()'s price_overrides on
// every calculation, where api.py substitutes it for that ware's price_min/
// price_avg/price_max alike, across all three Ware Cost List tiers. Still
// missing a compact always-visible list of active overrides once the modal
// is closed -- see TODO.md's "Ware price override tool" entry.
const priceOverrides = {};

async function openPriceOverrideModal() {
  priceOverrideModalOverlay.classList.remove("hidden");
  priceOverrideTbody.innerHTML = "";
  priceOverrideSearchInput.value = "";
  priceOverrideHighlightedRow = null;

  if (allWaresCache) {
    renderPriceOverrideTable(allWaresCache);
    return;
  }

  priceOverrideModalStatus.textContent = "Loading wares…";
  priceOverrideModalStatus.classList.remove("hidden");
  try {
    const response = await fetch("/api/wares");
    allWaresCache = await response.json();
  } catch {
    priceOverrideModalStatus.textContent = "Failed to load wares -- try again.";
    return;
  }
  priceOverrideModalStatus.classList.add("hidden");
  renderPriceOverrideTable(allWaresCache);
}

// Every ware_id appearing anywhere in a fleet list itself (not the
// computed cost breakdown) -- across every fleet in `fleets`, not just the
// active one. Each entry contributes its own ship plus everything in its
// wares_list (equipment, ammo, drones, ...). Backs the "Fleet list wares"
// filter checkbox.
function cartWareIds() {
  const ids = new Set();
  for (const fleet of fleets) {
    for (const entry of fleet.cart) {
      ids.add(entry.shipWareId);
      for (const item of entry.wares_list) ids.add(item.ware_id);
    }
  }
  return ids;
}

// ware_ids from one summarize()-shaped result's flat "parts"
// ({"build_method_priority": [...], "parts": {ware_id: amount}, ...}) --
// a null result (e.g. a fleet with no wareCostList yet) or one whose
// build_method_priority resolved to nothing (no "parts" key at all) just
// contributes nothing.
function wareIdsFromSummarizeResult(result) {
  const ids = new Set();
  if (!result) return ids;
  for (const wareId of Object.keys(result.parts ?? {})) ids.add(wareId);
  return ids;
}

// Every ware_id currently shown in the Ware Cost List's Production Wares
// (tierKey "production_wares") or Raw Materials (tierKey "raw_materials")
// tier -- across every fleet's own column in the table, not just the active
// one. Reads .total (the flat, ungrouped tier) rather than .component_type,
// since which wares appear is identical either way -- component_type only
// changes how they're bucketed for display, not the underlying set.
function wareIdsInWareCostListTier(tierKey) {
  const ids = new Set();
  for (const fleet of fleets) {
    if (!fleet.wareCostList) continue;
    for (const id of wareIdsFromSummarizeResult(fleet.wareCostList.total[tierKey])) ids.add(id);
  }
  return ids;
}

// Unchecked is no filter at all (show everything). Any combination of
// checked boxes is a union, not an intersection -- a ware shows up if it
// matches *any* checked filter. "Production wares"/"Raw resources" match
// the actual per-ware breakdown currently rendered in those Ware Cost
// List tiers (not a static database property); "Fleet list wares"
// matches cart membership instead, an entirely different axis (the
// fleet lists themselves, not their computed cost breakdown) that
// can freely combine with either of the other two.
function filterPriceOverrideWares(wares) {
  const productionChecked = priceOverrideFilterProductionCheckbox.checked;
  const rawChecked = priceOverrideFilterRawCheckbox.checked;
  const procurementChecked = priceOverrideFilterProcurementCheckbox.checked;
  if (!productionChecked && !rawChecked && !procurementChecked) return [...wares];

  const productionIds = productionChecked ? wareIdsInWareCostListTier("production_wares") : null;
  const rawIds = rawChecked ? wareIdsInWareCostListTier("raw_materials") : null;
  const cartIds = procurementChecked ? cartWareIds() : null;

  return wares.filter((ware) => {
    if (productionChecked && productionIds.has(ware.ware_id)) return true;
    if (rawChecked && rawIds.has(ware.ware_id)) return true;
    if (procurementChecked && cartIds.has(ware.ware_id)) return true;
    return false;
  });
}

function renderPriceOverrideTable(wares) {
  priceOverrideTbody.innerHTML = "";
  priceOverrideHighlightedRow = null;
  const sorted = filterPriceOverrideWares(wares).sort((a, b) => (a.name ?? a.ware_id).localeCompare(b.name ?? b.ware_id));

  for (const ware of sorted) {
    const tr = document.createElement("tr");

    // Lowercased once at render time -- handlePriceOverrideSearch() runs
    // on every keystroke, so it just reads this back rather than
    // re-deriving/re-lowercasing the display name on every search.
    tr.dataset.searchName = (ware.name ?? ware.ware_id).toLowerCase();

    const nameTd = document.createElement("td");
    nameTd.textContent = ware.name ?? ware.ware_id;
    tr.appendChild(nameTd);

    for (const priceField of ["price_min", "price_avg", "price_max"]) {
      const td = document.createElement("td");
      td.textContent = ware[priceField] == null ? "—" : formatPriceValue(ware[priceField]);
      tr.appendChild(td);
    }

    const overrideTd = document.createElement("td");
    const overrideInput = document.createElement("input");
    overrideInput.type = "number";
    overrideInput.min = "0";
    overrideInput.step = "any";
    overrideInput.placeholder = "no override";
    overrideInput.className = "price-override-input";
    if (priceOverrides[ware.ware_id] !== undefined) overrideInput.value = priceOverrides[ware.ware_id];
    overrideInput.addEventListener("input", () => {
      if (overrideInput.value === "") {
        delete priceOverrides[ware.ware_id];
      } else {
        priceOverrides[ware.ware_id] = Number(overrideInput.value);
      }
      renderPriceOverrideSummary();
    });
    overrideTd.appendChild(overrideInput);
    tr.appendChild(overrideTd);

    priceOverrideTbody.appendChild(tr);
  }
}

// Ware name for display, falling back to the raw ware_id when
// allWaresCache hasn't been loaded yet (e.g. the summary box renders once
// on page load, before "Set Ware Price Overrides" has ever been opened --
// moot in practice since there can't be any overrides set yet either, but
// keeps this function total rather than assuming the cache exists).
function wareDisplayName(wareId) {
  return allWaresCache?.find((ware) => ware.ware_id === wareId)?.name ?? wareId;
}

// Keeps the "Configured Ware Price Overrides" box (next to the Ware Cost
// List title) in sync with the priceOverrides map -- called on every
// override edit (see the input listener above) and whenever the picker
// modal closes, so it's accurate whether or not that modal has ever been
// opened this session.
function renderPriceOverrideSummary() {
  priceOverrideSummaryList.innerHTML = "";
  const entries = Object.entries(priceOverrides);

  if (entries.length === 0) {
    const empty = document.createElement("span");
    empty.className = "price-override-summary-empty";
    empty.textContent = "None configured.";
    priceOverrideSummaryList.appendChild(empty);
    return;
  }

  entries.sort((a, b) => wareDisplayName(a[0]).localeCompare(wareDisplayName(b[0])));
  for (const [wareId, price] of entries) {
    const row = document.createElement("div");
    row.className = "price-override-summary-entry";

    const name = document.createElement("span");
    name.className = "price-override-summary-name";
    name.textContent = wareDisplayName(wareId);
    row.appendChild(name);

    const value = document.createElement("span");
    value.className = "price-override-summary-value";
    value.textContent = formatPriceValue(price);
    row.appendChild(value);

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "price-override-summary-remove-btn";
    removeBtn.textContent = "×";
    removeBtn.title = `Remove override for ${wareDisplayName(wareId)}`;
    // Deletes straight from priceOverrides -- doesn't need to touch the
    // modal's own table (it re-derives each input's value fresh from
    // priceOverrides every time it's opened, see renderPriceOverrideTable()),
    // so this works whether or not that modal has ever been opened.
    removeBtn.addEventListener("click", () => {
      delete priceOverrides[wareId];
      renderPriceOverrideSummary();
      markAllFleetsDirtyAndRecompute();
    });
    row.appendChild(removeBtn);

    priceOverrideSummaryList.appendChild(row);
  }
}

// Overrides only take effect on the next computeWareCostList() call, and
// affect every fleet's cost (price_overrides is sent with every
// /api/price_summary request regardless of which fleet's wares are being
// priced) -- so a changed override makes every fleet's cached wareCostList
// stale at once, not just the active one. Recomputed immediately here
// (rather than deferred to the next Cost Analysis visit) since this can
// only be reached from *within* the Cost Analysis page in the first place --
// "navigate in" will never fire again while already there.
function markAllFleetsDirtyAndRecompute() {
  for (const fleet of fleets) fleet.dirty = true;
  recomputeDirtyFleets();
}

function closePriceOverrideModal() {
  priceOverrideModalOverlay.classList.add("hidden");
  renderPriceOverrideSummary();
  markAllFleetsDirtyAndRecompute();
}

// The row scrolled to/highlighted by the last search, if any -- cleared
// (and its highlight removed) at the start of every new search so at most
// one row is ever marked, and reset whenever the modal reopens/re-renders
// since a fresh render's rows are entirely new elements.
let priceOverrideHighlightedRow = null;

// Live "jump to" search, run on every keystroke: highlights and scrolls to
// the first row (in the table's current, name-sorted order) whose name
// contains the typed text so far, case-insensitively. Substring match
// rather than prefix-only, so e.g. typing "shield" still finds "M Shield
// Generator" partway through a name. An empty search box just clears any
// existing highlight without picking a new match.
function handlePriceOverrideSearch() {
  if (priceOverrideHighlightedRow) {
    priceOverrideHighlightedRow.classList.remove("price-override-row-highlight");
    priceOverrideHighlightedRow = null;
  }

  const query = priceOverrideSearchInput.value.trim().toLowerCase();
  if (!query) return;

  const match = [...priceOverrideTbody.querySelectorAll("tr")].find((row) => row.dataset.searchName.includes(query));
  if (!match) return;

  match.classList.add("price-override-row-highlight");
  priceOverrideHighlightedRow = match;
  match.scrollIntoView({ block: "center", behavior: "smooth" });
}
priceOverrideSearchInput.addEventListener("input", handlePriceOverrideSearch);

for (const checkbox of [priceOverrideFilterProductionCheckbox, priceOverrideFilterRawCheckbox, priceOverrideFilterProcurementCheckbox]) {
  checkbox.addEventListener("change", () => renderPriceOverrideTable(allWaresCache ?? []));
}

priceOverrideBtn.addEventListener("click", openPriceOverrideModal);
priceOverrideCloseBtn.addEventListener("click", closePriceOverrideModal);

// Which labeled section a group_name's bundle belongs to: the non-shield
// component_type when there is one (so an engine's dedicated bonus shield
// still lands in "Engines", not a separate "Shields" section -- matching
// how it's already rendered nested under that same card), else "shield"
// for a standalone main-shield-only group_name (e.g. shield_1/2/3).
function bundleSectionType(entries) {
  const nonShield = entries.find((g) => g.component_type !== "shield");
  return nonShield ? nonShield.component_type : "shield";
}

function renderShipDetail(data) {
  shipDetail.classList.remove("hidden");
  shipNameEl.innerHTML = "";
  if (data.icon) shipNameEl.appendChild(buildIconImg(data.icon, "ship-icon ship-name-icon"));
  shipNameEl.appendChild(document.createTextNode(data.name));
  updatePlayerLocationMarker(data.icon);
  selectChassisLoadoutBtn.textContent = `Select ${data.name} Loadout`;
  updateSelectChassisLoadoutBtnState();
  addToSavedLoadoutsStatus.classList.add("hidden");
  renderShipSummary(data);

  groupsContainer.innerHTML = "";

  // Group every entry by its (possibly shared) group_name first. A
  // group_name used by more than one component_type means one of them is a
  // dedicated shield protecting the other(s) -- rendered nested inside the
  // same card, right below the protected group's own picker, so the
  // association is visually unambiguous. A group_name used only by
  // shield(s) (e.g. shield_1/2/3) is a normal, standalone main shield slot
  // and renders as an ordinary top-level row.
  const entriesByGroupName = new Map();
  for (const group of data.groups) {
    if (!entriesByGroupName.has(group.group_name)) entriesByGroupName.set(group.group_name, []);
    entriesByGroupName.get(group.group_name).push(group);
  }

  // Bundle each group_name's cards, then bucket those bundles into
  // labeled sections by component type (COMPONENT_TYPE_ORDER/LABELS,
  // already used for the summary panel, doubles as the section list here
  // so both stay in sync). A ship missing a whole category (e.g. no
  // turrets) just doesn't get that section at all.
  const bundlesBySection = new Map();
  for (const entries of entriesByGroupName.values()) {
    const sectionType = bundleSectionType(entries);
    if (!bundlesBySection.has(sectionType)) bundlesBySection.set(sectionType, []);
    bundlesBySection.get(sectionType).push(entries);
  }

  for (const sectionType of COMPONENT_TYPE_ORDER) {
    const bundles = bundlesBySection.get(sectionType);
    if (!bundles) continue;

    const section = document.createElement("div");
    section.className = "picker-section";

    const headingRow = document.createElement("div");
    headingRow.className = "picker-section-heading-row";
    const heading = document.createElement("h4");
    heading.className = "picker-section-title";
    heading.textContent = COMPONENT_TYPE_LABELS[sectionType];
    headingRow.appendChild(heading);

    const highBtn = document.createElement("button");
    highBtn.type = "button";
    highBtn.className = "section-preset-btn";
    highBtn.textContent = "High Preset";
    highBtn.title = "Select the highest average-price item available in every slot in this section";
    highBtn.addEventListener("click", () => applyHighPreset(sectionType));
    headingRow.appendChild(highBtn);

    const minBtn = document.createElement("button");
    minBtn.type = "button";
    minBtn.className = "section-preset-btn";
    minBtn.textContent = "Minimum Preset";
    minBtn.title = "Select the lowest average-price item in this section's required slots (marked *), and clear everything else";
    minBtn.addEventListener("click", () => applyMinimumPreset(sectionType));
    headingRow.appendChild(minBtn);

    section.appendChild(headingRow);

    for (const entries of bundles) {
      const card = document.createElement("div");
      card.className = "group-card";

      const nonShield = entries.filter((g) => g.component_type !== "shield");
      const shields = entries.filter((g) => g.component_type === "shield");
      const isLinked = nonShield.length > 0; // else: a standalone shield-only group_name

      for (const group of nonShield) {
        card.appendChild(buildGroupRow(group, { sectionType }));
      }
      for (const group of shields) {
        const row = buildGroupRow(group, { isLinkedShield: isLinked, sectionType });
        if (isLinked) row.classList.add("bonus-shield-row");
        card.appendChild(row);
      }

      section.appendChild(card);
    }

    groupsContainer.appendChild(section);
  }

  updateSelectedAmmoCapacity();
  renderAmmoInfoBox();
  renderAmmunitionSection();
  renderDroneSection();
  renderDeployableSection();
  renderCountermeasureSection();
  renderCrewSection();
}

// Total missile capacity = the ship's own base missile_capacity (an
// independent contribution -- not derived from any launcher, see
// ships_base.missile_capacity) PLUS ammunition_capacity (per-unit, from a
// missile-capable turret's/weapon's own selected option -- see
// query_ship_components.py's matching_items() docstring) summed across
// every currently-selected group, scaled by that group's own slot_count
// (a group with slot_count 2 mounts two of whatever's selected, so it
// contributes double the capacity). Entirely client-side, no API call
// needed since every option's ammunition_capacity and the ship's own
// missile_capacity already arrived with the initial
// GET /api/ships/{id}/groups response.
function totalMissileCapacity() {
  if (!currentShip) return 0;

  let total = currentShip.summary.missile_capacity ?? 0;
  for (const row of groupsContainer.querySelectorAll(".group-row")) {
    const select = row.querySelector(".group-select");
    const selectedOption = select.options[select.selectedIndex];
    if (selectedOption && selectedOption.dataset.ammoCapacity !== undefined) {
      total += Number(selectedOption.dataset.ammoCapacity) * Number(row.dataset.slotCount);
    }
  }
  return total;
}

// Re-run on every .group-select change (delegated listener below) and
// once right after the picker (re)renders, so it's always in sync with
// whatever's actually selected.
function updateSelectedAmmoCapacity() {
  const line = document.getElementById("selected-ammo-capacity-line");
  if (line) line.textContent = `Total Missile Capacity: ${totalMissileCapacity()}`;
}

function totalSelectedMissiles() {
  return Object.values(missileAmounts).reduce((sum, amount) => sum + amount, 0);
}

// The union of every currently-selected launcher's own ammunition_tags
// (see buildGroupRow()) -- a missile is offered in the Ammunition section
// when its own single compatibility tag is a member of this set.
function acceptedAmmunitionTags() {
  const tags = new Set();
  for (const row of groupsContainer.querySelectorAll(".group-row")) {
    const select = row.querySelector(".group-select");
    const selectedOption = select.options[select.selectedIndex];
    if (selectedOption && selectedOption.dataset.ammoTags) {
      for (const tag of selectedOption.dataset.ammoTags.split(",")) tags.add(tag);
    }
  }
  return tags;
}

function compatibleMissiles() {
  const accepted = acceptedAmmunitionTags();
  return allMissiles.filter((missile) => missile.compatibility && accepted.has(missile.compatibility));
}

// One row: missile name + a qty stepper (+/-, and a directly-typeable
// number input), mirroring the cart's own quantity control. Mutates
// missileAmounts directly and re-derives the running total/comparison on
// every change -- never rebuilds the whole Ammunition section on a qty
// edit (only a launcher swap does that, since only that can change which
// missiles are even compatible).
function buildAmmoRow(missile) {
  const row = document.createElement("div");
  row.className = "ammo-row";

  const label = document.createElement("label");
  label.textContent = missile.name;
  row.appendChild(label);

  const qtyWrap = document.createElement("span");
  qtyWrap.className = "qty-control";

  const qtyInput = document.createElement("input");
  qtyInput.type = "number";
  qtyInput.min = "0";
  qtyInput.className = "qty-input";
  qtyInput.value = missileAmounts[missile.ware_id] ?? 0;

  // Capped at how much room is left in the shared missile-capacity pool --
  // this row's own current amount plus whatever capacity every other row
  // hasn't already claimed -- so typed values, +/- clicks, and shift+plus's
  // "fill remaining" (see plusBtn below) can never push the total over
  // totalMissileCapacity() through this row.
  const setAmount = (value) => {
    const otherTotal = totalSelectedMissiles() - (missileAmounts[missile.ware_id] ?? 0);
    const maxAllowed = Math.max(0, totalMissileCapacity() - otherTotal);
    const amount = Math.min(maxAllowed, Math.max(0, Math.floor(Number(value)) || 0));
    if (amount === 0) {
      delete missileAmounts[missile.ware_id];
    } else {
      missileAmounts[missile.ware_id] = amount;
    }
    qtyInput.value = amount;
    updateAmmoSummary();
  };

  qtyInput.addEventListener("change", () => setAmount(qtyInput.value));

  const minusBtn = document.createElement("button");
  minusBtn.type = "button";
  minusBtn.textContent = "-";
  minusBtn.className = "qty-btn";
  // Shift+click zeroes this row out in one step; ctrl+click steps by 10
  // instead of 1 (still 1 if this row has less than 10 left to give up).
  minusBtn.addEventListener("click", (event) =>
    setAmount(event.shiftKey ? 0 : Number(qtyInput.value) - (event.ctrlKey ? 10 : 1)),
  );

  const plusBtn = document.createElement("button");
  plusBtn.type = "button";
  plusBtn.textContent = "+";
  plusBtn.className = "qty-btn";
  // Shift+click fills this row up to whatever's left in the shared pool --
  // setAmount's own capping above does the actual clamping, Infinity just
  // asks it for "as much as possible". Ctrl+click (without shift) steps by
  // 10 instead of 1.
  plusBtn.addEventListener("click", (event) =>
    setAmount(event.shiftKey ? Infinity : Number(qtyInput.value) + (event.ctrlKey ? 10 : 1)),
  );

  qtyWrap.appendChild(minusBtn);
  qtyWrap.appendChild(qtyInput);
  qtyWrap.appendChild(plusBtn);
  row.appendChild(qtyWrap);

  return row;
}

// Shown above the Ammunition section whenever a ship is loaded, regardless
// of whether that ship actually has any ammunition to show (the counter
// shortcuts apply to every qty counter in the ship builder, not just
// ammunition rows) -- kept in its own container, separate from
// ammunitionContainer, so renderAmmunitionSection()'s early-return for
// "no compatible missiles" can't make it disappear along with the section
// it happens to sit above. Populated once per ship load from
// renderShipDetail(); cleared alongside everything else in
// resetShipPicker().
function renderAmmoInfoBox() {
  ammoInfoBoxContainer.innerHTML = "";

  const box = document.createElement("div");
  box.className = "info-box";
  const icon = document.createElement("span");
  icon.className = "info-box-icon";
  icon.textContent = "i";
  box.appendChild(icon);
  const text = document.createElement("span");
  text.textContent = "Ctrl-click to move counters by 10, Shift-click to move counters by max.";
  box.appendChild(text);

  ammoInfoBoxContainer.appendChild(box);
}

// Rebuilds the Ammunition section from scratch: which missiles are
// compatible can change on every launcher swap, so this re-derives that
// set (dropping any missileAmounts entry that's no longer compatible --
// its count is simply lost, matching "only compatible missiles are
// offered") and rebuilds the row list. The whole section is omitted
// entirely (not even a heading) when nothing is compatible yet, rather
// than showing an empty placeholder. Called after every ship
// (re)render/edit-repopulation and on every .group-select change.
function renderAmmunitionSection() {
  ammunitionContainer.innerHTML = "";
  if (!currentShip) return;

  const missiles = compatibleMissiles();
  const compatibleIds = new Set(missiles.map((missile) => missile.ware_id));
  for (const wareId of Object.keys(missileAmounts)) {
    if (!compatibleIds.has(wareId)) delete missileAmounts[wareId];
  }

  if (missiles.length === 0) return;

  const section = document.createElement("div");
  section.className = "picker-section";

  const heading = document.createElement("h4");
  heading.className = "picker-section-title";
  heading.textContent = "Ammunition";
  section.appendChild(heading);

  const card = document.createElement("div");
  card.className = "group-card";
  for (const missile of missiles) {
    card.appendChild(buildAmmoRow(missile));
  }
  section.appendChild(card);

  const summaryLine = document.createElement("div");
  summaryLine.id = "ammo-summary-line";
  summaryLine.className = "ammo-summary-line";
  section.appendChild(summaryLine);

  ammunitionContainer.appendChild(section);
  updateAmmoSummary();
}

function updateAmmoSummary() {
  const line = document.getElementById("ammo-summary-line");
  if (!line) return;

  const total = totalSelectedMissiles();
  const capacity = totalMissileCapacity();
  line.textContent = `Total Missiles: ${total} / ${capacity}`;
  line.classList.toggle("over-capacity", total > capacity);
}

function totalSelectedDrones() {
  return Object.values(droneAmounts).reduce((sum, amount) => sum + amount, 0);
}

// Unlike missile capacity, this is purely the ship's own base
// drone_capacity (ships_base.drone_capacity, e.g. builders ~100-250,
// carriers ~20) -- no per-launcher contribution to add, since drones
// aren't tied to any equipped weapon/turret the way missiles are.
function totalDroneCapacity() {
  return currentShip ? currentShip.summary.drone_capacity ?? 0 : 0;
}

// One row: drone name + a qty stepper, same control as buildAmmoRow().
function buildDroneRow(drone) {
  const row = document.createElement("div");
  row.className = "ammo-row";

  const label = document.createElement("label");
  label.textContent = drone.name;
  row.appendChild(label);

  const qtyWrap = document.createElement("span");
  qtyWrap.className = "qty-control";

  const qtyInput = document.createElement("input");
  qtyInput.type = "number";
  qtyInput.min = "0";
  qtyInput.className = "qty-input";
  qtyInput.value = droneAmounts[drone.ware_id] ?? 0;

  // Capped at how much room is left in the shared drone-capacity pool --
  // see buildAmmoRow()'s setAmount for the full explanation.
  const setAmount = (value) => {
    const otherTotal = totalSelectedDrones() - (droneAmounts[drone.ware_id] ?? 0);
    const maxAllowed = Math.max(0, totalDroneCapacity() - otherTotal);
    const amount = Math.min(maxAllowed, Math.max(0, Math.floor(Number(value)) || 0));
    if (amount === 0) {
      delete droneAmounts[drone.ware_id];
    } else {
      droneAmounts[drone.ware_id] = amount;
    }
    qtyInput.value = amount;
    updateDroneSummary();
  };

  qtyInput.addEventListener("change", () => setAmount(qtyInput.value));

  const minusBtn = document.createElement("button");
  minusBtn.type = "button";
  minusBtn.textContent = "-";
  minusBtn.className = "qty-btn";
  // Shift+click zeroes this row out in one step; ctrl+click steps by 10
  // instead of 1 (still 1 if this row has less than 10 left to give up).
  minusBtn.addEventListener("click", (event) =>
    setAmount(event.shiftKey ? 0 : Number(qtyInput.value) - (event.ctrlKey ? 10 : 1)),
  );

  const plusBtn = document.createElement("button");
  plusBtn.type = "button";
  plusBtn.textContent = "+";
  plusBtn.className = "qty-btn";
  // Shift+click fills this row up to whatever's left in the shared pool;
  // ctrl+click (without shift) steps by 10 instead of 1.
  plusBtn.addEventListener("click", (event) =>
    setAmount(event.shiftKey ? Infinity : Number(qtyInput.value) + (event.ctrlKey ? 10 : 1)),
  );

  qtyWrap.appendChild(minusBtn);
  qtyWrap.appendChild(qtyInput);
  qtyWrap.appendChild(plusBtn);
  row.appendChild(qtyWrap);

  return row;
}

// Rebuilds the Drones section. Unlike renderAmmunitionSection(), which
// group is compatible never depends on anything else selected in the
// picker (no per-launcher concept for drones), so this is only called
// once per ship (re)render/edit-repopulation -- never on a .group-select
// change. The whole section is omitted entirely (not even a heading) when
// this ship has no drone capacity at all, rather than showing an empty
// placeholder.
function renderDroneSection() {
  droneContainer.innerHTML = "";
  if (!currentShip) return;

  const capacity = totalDroneCapacity();
  if (capacity <= 0) {
    droneAmounts = {};
    return;
  }

  const section = document.createElement("div");
  section.className = "picker-section";

  const heading = document.createElement("h4");
  heading.className = "picker-section-title";
  heading.textContent = "Drones";
  section.appendChild(heading);

  const card = document.createElement("div");
  card.className = "group-card";
  for (const drone of allDrones) {
    card.appendChild(buildDroneRow(drone));
  }
  section.appendChild(card);

  const summaryLine = document.createElement("div");
  summaryLine.id = "drone-summary-line";
  summaryLine.className = "ammo-summary-line";
  section.appendChild(summaryLine);

  droneContainer.appendChild(section);
  updateDroneSummary();
}

function updateDroneSummary() {
  const line = document.getElementById("drone-summary-line");
  if (!line) return;

  const total = totalSelectedDrones();
  const capacity = totalDroneCapacity();
  line.textContent = `Total Drones: ${total} / ${capacity}`;
  line.classList.toggle("over-capacity", total > capacity);
}

function totalSelectedDeployables() {
  return Object.values(deployableAmounts).reduce((sum, amount) => sum + amount, 0);
}

// The game data has no per-ship deployable capacity stat at all (unlike
// missile_capacity/drone_capacity) -- this is an assumed default keyed by
// the ship's own size, not derived from anything in ships_base.
function totalDeployableCapacity() {
  if (!currentShip) return 0;
  return DEPLOYABLE_CAPACITY_BY_SIZE[currentShip.summary.size] ?? 0;
}

// One row: deployable name + a qty stepper, same control as buildAmmoRow()/buildDroneRow().
function buildDeployableRow(deployable) {
  const row = document.createElement("div");
  row.className = "ammo-row";

  const label = document.createElement("label");
  label.textContent = deployable.name;
  row.appendChild(label);

  const qtyWrap = document.createElement("span");
  qtyWrap.className = "qty-control";

  const qtyInput = document.createElement("input");
  qtyInput.type = "number";
  qtyInput.min = "0";
  qtyInput.className = "qty-input";
  qtyInput.value = deployableAmounts[deployable.ware_id] ?? 0;

  // Capped at how much room is left in the shared deployable-capacity pool
  // -- see buildAmmoRow()'s setAmount for the full explanation.
  const setAmount = (value) => {
    const otherTotal = totalSelectedDeployables() - (deployableAmounts[deployable.ware_id] ?? 0);
    const maxAllowed = Math.max(0, totalDeployableCapacity() - otherTotal);
    const amount = Math.min(maxAllowed, Math.max(0, Math.floor(Number(value)) || 0));
    if (amount === 0) {
      delete deployableAmounts[deployable.ware_id];
    } else {
      deployableAmounts[deployable.ware_id] = amount;
    }
    qtyInput.value = amount;
    updateDeployableSummary();
  };

  qtyInput.addEventListener("change", () => setAmount(qtyInput.value));

  const minusBtn = document.createElement("button");
  minusBtn.type = "button";
  minusBtn.textContent = "-";
  minusBtn.className = "qty-btn";
  // Shift+click zeroes this row out in one step; ctrl+click steps by 10
  // instead of 1 (still 1 if this row has less than 10 left to give up).
  minusBtn.addEventListener("click", (event) =>
    setAmount(event.shiftKey ? 0 : Number(qtyInput.value) - (event.ctrlKey ? 10 : 1)),
  );

  const plusBtn = document.createElement("button");
  plusBtn.type = "button";
  plusBtn.textContent = "+";
  plusBtn.className = "qty-btn";
  // Shift+click fills this row up to whatever's left in the shared pool;
  // ctrl+click (without shift) steps by 10 instead of 1.
  plusBtn.addEventListener("click", (event) =>
    setAmount(event.shiftKey ? Infinity : Number(qtyInput.value) + (event.ctrlKey ? 10 : 1)),
  );

  qtyWrap.appendChild(minusBtn);
  qtyWrap.appendChild(qtyInput);
  qtyWrap.appendChild(plusBtn);
  row.appendChild(qtyWrap);

  return row;
}

// Rebuilds the Deployables section -- same shape as renderDroneSection()
// (no per-selection compatibility, only called once per ship (re)render/
// edit-repopulation), hidden entirely when the assumed capacity for this
// ship's size is 0 (shouldn't happen for a real s/m/l/xl ship, but guards
// against an unrecognized/missing size).
function renderDeployableSection() {
  deployableContainer.innerHTML = "";
  if (!currentShip) return;

  const capacity = totalDeployableCapacity();
  if (capacity <= 0) {
    deployableAmounts = {};
    return;
  }

  const section = document.createElement("div");
  section.className = "picker-section";

  const heading = document.createElement("h4");
  heading.className = "picker-section-title";
  heading.textContent = "Deployables";
  section.appendChild(heading);

  const card = document.createElement("div");
  card.className = "group-card";
  for (const deployable of allDeployables) {
    card.appendChild(buildDeployableRow(deployable));
  }
  section.appendChild(card);

  const summaryLine = document.createElement("div");
  summaryLine.id = "deployable-summary-line";
  summaryLine.className = "ammo-summary-line";
  section.appendChild(summaryLine);

  deployableContainer.appendChild(section);
  updateDeployableSummary();
}

function updateDeployableSummary() {
  const line = document.getElementById("deployable-summary-line");
  if (!line) return;

  const total = totalSelectedDeployables();
  const capacity = totalDeployableCapacity();
  line.textContent = `Total Deployables: ${total} / ${capacity}`;
  line.classList.toggle("over-capacity", total > capacity);
}

function totalSelectedCountermeasures() {
  return Object.values(countermeasureAmounts).reduce((sum, amount) => sum + amount, 0);
}

// Same "no real per-ship data, assumed default by size" situation as
// totalDeployableCapacity() -- see COUNTERMEASURE_CAPACITY_BY_SIZE above.
function totalCountermeasureCapacity() {
  if (!currentShip) return 0;
  return COUNTERMEASURE_CAPACITY_BY_SIZE[currentShip.summary.size] ?? 0;
}

// One row: countermeasure name + a qty stepper, same control as buildDeployableRow().
function buildCountermeasureRow(countermeasure) {
  const row = document.createElement("div");
  row.className = "ammo-row";

  const label = document.createElement("label");
  label.textContent = countermeasure.name;
  row.appendChild(label);

  const qtyWrap = document.createElement("span");
  qtyWrap.className = "qty-control";

  const qtyInput = document.createElement("input");
  qtyInput.type = "number";
  qtyInput.min = "0";
  qtyInput.className = "qty-input";
  qtyInput.value = countermeasureAmounts[countermeasure.ware_id] ?? 0;

  // Capped at how much room is left in the shared countermeasure-capacity
  // pool -- see buildAmmoRow()'s setAmount for the full explanation.
  const setAmount = (value) => {
    const otherTotal = totalSelectedCountermeasures() - (countermeasureAmounts[countermeasure.ware_id] ?? 0);
    const maxAllowed = Math.max(0, totalCountermeasureCapacity() - otherTotal);
    const amount = Math.min(maxAllowed, Math.max(0, Math.floor(Number(value)) || 0));
    if (amount === 0) {
      delete countermeasureAmounts[countermeasure.ware_id];
    } else {
      countermeasureAmounts[countermeasure.ware_id] = amount;
    }
    qtyInput.value = amount;
    updateCountermeasureSummary();
  };

  qtyInput.addEventListener("change", () => setAmount(qtyInput.value));

  const minusBtn = document.createElement("button");
  minusBtn.type = "button";
  minusBtn.textContent = "-";
  minusBtn.className = "qty-btn";
  // Shift+click zeroes this row out in one step; ctrl+click steps by 10
  // instead of 1 (still 1 if this row has less than 10 left to give up).
  minusBtn.addEventListener("click", (event) =>
    setAmount(event.shiftKey ? 0 : Number(qtyInput.value) - (event.ctrlKey ? 10 : 1)),
  );

  const plusBtn = document.createElement("button");
  plusBtn.type = "button";
  plusBtn.textContent = "+";
  plusBtn.className = "qty-btn";
  // Shift+click fills this row up to whatever's left in the shared pool;
  // ctrl+click (without shift) steps by 10 instead of 1.
  plusBtn.addEventListener("click", (event) =>
    setAmount(event.shiftKey ? Infinity : Number(qtyInput.value) + (event.ctrlKey ? 10 : 1)),
  );

  qtyWrap.appendChild(minusBtn);
  qtyWrap.appendChild(qtyInput);
  qtyWrap.appendChild(plusBtn);
  row.appendChild(qtyWrap);

  return row;
}

// Rebuilds the Countermeasures section -- same shape as
// renderDeployableSection() (no per-selection compatibility, only called
// once per ship (re)render/edit-repopulation), hidden entirely when the
// assumed capacity for this ship's size is 0.
function renderCountermeasureSection() {
  countermeasureContainer.innerHTML = "";
  if (!currentShip) return;

  const capacity = totalCountermeasureCapacity();
  if (capacity <= 0) {
    countermeasureAmounts = {};
    return;
  }

  const section = document.createElement("div");
  section.className = "picker-section";

  const heading = document.createElement("h4");
  heading.className = "picker-section-title";
  heading.textContent = "Countermeasures";
  section.appendChild(heading);

  const card = document.createElement("div");
  card.className = "group-card";
  for (const countermeasure of allCountermeasures) {
    card.appendChild(buildCountermeasureRow(countermeasure));
  }
  section.appendChild(card);

  const summaryLine = document.createElement("div");
  summaryLine.id = "countermeasure-summary-line";
  summaryLine.className = "ammo-summary-line";
  section.appendChild(summaryLine);

  countermeasureContainer.appendChild(section);
  updateCountermeasureSummary();
}

function updateCountermeasureSummary() {
  const line = document.getElementById("countermeasure-summary-line");
  if (!line) return;

  const total = totalSelectedCountermeasures();
  const capacity = totalCountermeasureCapacity();
  line.textContent = `Total Countermeasures: ${total} / ${capacity}`;
  line.classList.toggle("over-capacity", total > capacity);
}

function totalSelectedCrew() {
  return Object.values(crewAmounts).reduce((sum, amount) => sum + amount, 0);
}

// Unlike totalCountermeasureCapacity()/totalDeployableCapacity(), this is a
// real ships_base column (query_ship_groups()'s own summary.crew_capacity,
// from the macro's <people capacity="..."/>), not an assumed default.
function totalCrewCapacity() {
  return currentShip ? currentShip.summary.crew_capacity ?? 0 : 0;
}

// One row: crew name + a qty stepper, same control as buildDeployableRow().
function buildCrewRow(crew) {
  const row = document.createElement("div");
  row.className = "ammo-row";

  const label = document.createElement("label");
  label.textContent = crew.name;
  row.appendChild(label);

  const qtyWrap = document.createElement("span");
  qtyWrap.className = "qty-control";

  const qtyInput = document.createElement("input");
  qtyInput.type = "number";
  qtyInput.min = "0";
  qtyInput.className = "qty-input";
  qtyInput.value = crewAmounts[crew.ware_id] ?? 0;

  // Capped at how much room is left in the shared crew-capacity pool --
  // see buildAmmoRow()'s setAmount for the full explanation.
  const setAmount = (value) => {
    const otherTotal = totalSelectedCrew() - (crewAmounts[crew.ware_id] ?? 0);
    const maxAllowed = Math.max(0, totalCrewCapacity() - otherTotal);
    const amount = Math.min(maxAllowed, Math.max(0, Math.floor(Number(value)) || 0));
    if (amount === 0) {
      delete crewAmounts[crew.ware_id];
    } else {
      crewAmounts[crew.ware_id] = amount;
    }
    qtyInput.value = amount;
    updateCrewSummary();
  };

  qtyInput.addEventListener("change", () => setAmount(qtyInput.value));

  const minusBtn = document.createElement("button");
  minusBtn.type = "button";
  minusBtn.textContent = "-";
  minusBtn.className = "qty-btn";
  // Shift+click zeroes this row out in one step; ctrl+click steps by 10
  // instead of 1 (still 1 if this row has less than 10 left to give up).
  minusBtn.addEventListener("click", (event) =>
    setAmount(event.shiftKey ? 0 : Number(qtyInput.value) - (event.ctrlKey ? 10 : 1)),
  );

  const plusBtn = document.createElement("button");
  plusBtn.type = "button";
  plusBtn.textContent = "+";
  plusBtn.className = "qty-btn";
  // Shift+click fills this row up to whatever's left in the shared pool;
  // ctrl+click (without shift) steps by 10 instead of 1.
  plusBtn.addEventListener("click", (event) =>
    setAmount(event.shiftKey ? Infinity : Number(qtyInput.value) + (event.ctrlKey ? 10 : 1)),
  );

  qtyWrap.appendChild(minusBtn);
  qtyWrap.appendChild(qtyInput);
  qtyWrap.appendChild(plusBtn);
  row.appendChild(qtyWrap);

  return row;
}

// Rebuilds the Crew section -- same shape as renderDeployableSection(),
// hidden entirely when this ship's crew capacity is 0 (shouldn't normally
// happen for a real crewed ship, but guards against a missing stat).
function renderCrewSection() {
  crewContainer.innerHTML = "";
  if (!currentShip) return;

  const capacity = totalCrewCapacity();
  if (capacity <= 0) {
    crewAmounts = {};
    return;
  }

  const section = document.createElement("div");
  section.className = "picker-section";

  const heading = document.createElement("h4");
  heading.className = "picker-section-title";
  heading.textContent = "Crew";
  section.appendChild(heading);

  const card = document.createElement("div");
  card.className = "group-card";
  for (const crew of allCrew) {
    card.appendChild(buildCrewRow(crew));
  }
  section.appendChild(card);

  const summaryLine = document.createElement("div");
  summaryLine.id = "crew-summary-line";
  summaryLine.className = "ammo-summary-line";
  section.appendChild(summaryLine);

  crewContainer.appendChild(section);
  updateCrewSummary();
}

function updateCrewSummary() {
  const line = document.getElementById("crew-summary-line");
  if (!line) return;

  const total = totalSelectedCrew();
  const capacity = totalCrewCapacity();
  line.textContent = `Total Crew: ${total} / ${capacity}`;
  line.classList.toggle("over-capacity", total > capacity);
}

groupsContainer.addEventListener("change", (event) => {
  if (event.target.classList.contains("group-select")) {
    updateSelectedAmmoCapacity();
    renderAmmunitionSection();
  }
});

// Main/bonus shield counts come straight from ships_base (read-only display
// only, per query_ship_groups()'s docstring). Total equipment slots per
// component type are derived here from data.groups, since that's the only
// place per-hardpoint slot_count actually lives.
function renderShipSummary(data) {
  shipSummaryEl.innerHTML = "";

  const sizeLabel = data.summary.size ? data.summary.size.toUpperCase() : "-";
  const mainShieldsLine = document.createElement("div");
  mainShieldsLine.textContent = `Main Shields (${sizeLabel}): ${data.summary.shields ?? "-"}`;
  shipSummaryEl.appendChild(mainShieldsLine);

  const bonusShieldsLine = document.createElement("div");
  bonusShieldsLine.textContent = `Surface Element Shields (M): ${data.summary.shields_bonus_m ?? "-"}`;
  shipSummaryEl.appendChild(bonusShieldsLine);

  const missileCapacityLine = document.createElement("div");
  missileCapacityLine.textContent = `Missile Capacity: ${data.summary.missile_capacity ?? "-"}`;
  shipSummaryEl.appendChild(missileCapacityLine);

  // Kept up to date by updateSelectedAmmoCapacity() (called on every
  // .group-select change, and once right after this renders) -- looked up
  // fresh each time rather than cached, since this whole panel gets
  // rebuilt (innerHTML = "") on every ship load/edit. Combines the ship's
  // own base missile_capacity (line above -- an independent contribution,
  // not derived from any launcher) with the sum of every currently
  // selected launcher's own ammunition_capacity into one running total.
  const ammoCapacityLine = document.createElement("div");
  ammoCapacityLine.id = "selected-ammo-capacity-line";
  shipSummaryEl.appendChild(ammoCapacityLine);

  const slotTotals = {};
  for (const group of data.groups) {
    slotTotals[group.component_type] = (slotTotals[group.component_type] ?? 0) + group.slot_count;
  }

  const slotsHeader = document.createElement("div");
  slotsHeader.className = "summary-subheader";
  slotsHeader.textContent = "Total equipment slots:";
  shipSummaryEl.appendChild(slotsHeader);

  const slotsList = document.createElement("ul");
  slotsList.className = "summary-slot-list";
  for (const componentType of COMPONENT_TYPE_ORDER) {
    if (!(componentType in slotTotals)) continue;
    const li = document.createElement("li");
    li.textContent = `${COMPONENT_TYPE_LABELS[componentType]}: ${slotTotals[componentType]}`;
    slotsList.appendChild(li);
  }
  shipSummaryEl.appendChild(slotsList);
}

// Every currently-rendered .group-row belonging to one rendered section
// (row.dataset.sectionType, set by buildGroupRow() -- not the same as
// row.dataset.componentType, since a section's cards can include a
// different component_type, e.g. an engine's own linked bonus shield),
// in DOM order.
function groupRowsForSection(sectionType) {
  return [...groupsContainer.querySelectorAll(".group-row")].filter((row) => row.dataset.sectionType === sectionType);
}

// The raw group data (with its own .options, each carrying "price_avg")
// behind a .group-row -- the row itself only stores groupKey as a dataset
// string, so this looks it back up in currentShip.groups (the same array
// buildGroupRow() built every row from in the first place).
function groupForRow(row) {
  return currentShip ? (currentShip.groups.find((g) => groupKey(g) === row.dataset.groupKey) ?? null) : null;
}

// "High Preset" button (next to each section's title): selects the
// highest average-price option in *every* slot of that section, required
// or not.
function applyHighPreset(sectionType) {
  for (const row of groupRowsForSection(sectionType)) {
    const group = groupForRow(row);
    if (!group || group.options.length === 0) continue;
    const best = group.options.reduce((a, b) => ((b.price_avg ?? 0) > (a.price_avg ?? 0) ? b : a));
    applySelectionToRow(row, best.ware_id);
  }
}

// "Minimum Preset" button: selects the lowest average-price option in
// that section's slots actually marked required (row.dataset.requiredLabel
// -- see requiredGroupLabel()), and clears every other slot in the section
// back to "-- none --" -- a true minimum-viable loadout for that section,
// not just "leave whatever else was picked". A section with no required
// slots at all (e.g. Weapons, Turrets) simply clears everything.
function applyMinimumPreset(sectionType) {
  for (const row of groupRowsForSection(sectionType)) {
    if (!row.dataset.requiredLabel) {
      applySelectionToRow(row, "");
      continue;
    }
    const group = groupForRow(row);
    if (!group || group.options.length === 0) continue;
    const worst = group.options.reduce((a, b) => ((b.price_avg ?? 0) < (a.price_avg ?? 0) ? b : a));
    applySelectionToRow(row, worst.ware_id);
  }
}

// Ship-wide High/Minimum Preset buttons, next to "Select loadout" -- just
// runs every section's own applyHighPreset()/applyMinimumPreset() in turn.
// Calling it for a component_type this ship doesn't have (e.g. no
// missile_launcher) is harmless: groupRowsForSection() returns an empty
// list, so that iteration is simply a no-op.
shipHighPresetBtn.addEventListener("click", () => {
  for (const sectionType of COMPONENT_TYPE_ORDER) applyHighPreset(sectionType);
});
shipMinimumPresetBtn.addEventListener("click", () => {
  for (const sectionType of COMPONENT_TYPE_ORDER) applyMinimumPreset(sectionType);
});

function applyGroupSelections(selections) {
  for (const row of groupsContainer.querySelectorAll(".group-row")) {
    const wareId = selections[row.dataset.groupKey];
    if (wareId) {
      row.querySelector(".group-select").value = wareId;
    }
    // Reflects the (possibly just-changed) select value on its visible
    // picker button -- needed even when this row has no saved wareId,
    // since a fresh row otherwise never gets its initial "-- none --"
    // label synced through this path.
    syncGroupSelectButtonLabel(row);
  }
  // Setting .value programmatically doesn't fire a "change" event, so the
  // delegated listener that normally keeps the ammo-capacity line/
  // Ammunition section in sync never runs for these -- recalculate
  // explicitly. (editCartEntry() restores the saved missileAmounts and
  // re-renders the Ammunition section again after this, once the correct
  // launchers are actually selected.)
  updateSelectedAmmoCapacity();
  renderAmmunitionSection();
}

function resetShipPicker() {
  currentShip = null;
  editingIndex = null;
  missileAmounts = {};
  countermeasureAmounts = {};
  droneAmounts = {};
  deployableAmounts = {};
  crewAmounts = {};
  applyShipSelection("");
  updatePlayerLocationMarker(null);
  loadShipBtn.disabled = true;
  selectChassisLoadoutBtn.disabled = true;
  shipDetail.classList.add("hidden");
  groupsContainer.innerHTML = "";
  ammoInfoBoxContainer.innerHTML = "";
  ammunitionContainer.innerHTML = "";
  countermeasureContainer.innerHTML = "";
  droneContainer.innerHTML = "";
  deployableContainer.innerHTML = "";
  crewContainer.innerHTML = "";
  shipNoteInput.value = "";
  setAddToCartBtnLabel("Add To Fleet List");
  importedLoadoutWarningsEl.classList.add("hidden");
  addToSavedLoadoutsStatus.classList.add("hidden");
}

// Two copies of the same action (top, next to Load; bottom, next to Add
// to fleet list) so it's reachable without scrolling regardless of
// where the user currently is on a long ship-detail page.
clearShipBtnTop.addEventListener("click", resetShipPicker);
clearShipBtnBottom.addEventListener("click", resetShipPicker);

// Shared by both Add To Fleet List buttons (top, next to Select Loadout;
// bottom, next to Add To Saved Loadouts/Clear -- see addToCartBtnTop).
function addSelectedShipToCart() {
  if (!currentShip) return;

  // No longer a hard block -- collected here and carried onto the cart
  // entry (see missingRequiredComponents below) so renderCart() can show an
  // orange warning under the ship's name instead of refusing to add it.
  const missingRequired = [];
  for (const row of groupsContainer.querySelectorAll(".group-row[data-required-label]")) {
    const select = row.querySelector(".group-select");
    if (!select.value) missingRequired.push(row.dataset.requiredLabel);
  }

  const selectedMissiles = totalSelectedMissiles();
  const missileCapacity = totalMissileCapacity();
  if (selectedMissiles > missileCapacity) {
    alert(
      `Selected ammunition (${selectedMissiles}) exceeds this ship's total missile capacity (${missileCapacity}). ` +
        "Please reduce the ammunition quantities before adding this ship.",
    );
    return;
  }

  const selectedDrones = totalSelectedDrones();
  const droneCapacity = totalDroneCapacity();
  if (selectedDrones > droneCapacity) {
    alert(
      `Selected drones (${selectedDrones}) exceed this ship's drone capacity (${droneCapacity}). ` +
        "Please reduce the drone quantities before adding this ship.",
    );
    return;
  }

  const selectedDeployables = totalSelectedDeployables();
  const deployableCapacity = totalDeployableCapacity();
  if (selectedDeployables > deployableCapacity) {
    alert(
      `Selected deployables (${selectedDeployables}) exceed this ship's deployable capacity (${deployableCapacity}). ` +
        "Please reduce the deployable quantities before adding this ship.",
    );
    return;
  }

  const selectedCountermeasures = totalSelectedCountermeasures();
  const countermeasureCapacity = totalCountermeasureCapacity();
  if (selectedCountermeasures > countermeasureCapacity) {
    alert(
      `Selected countermeasures (${selectedCountermeasures}) exceed this ship's countermeasure capacity (${countermeasureCapacity}). ` +
        "Please reduce the countermeasure quantities before adding this ship.",
    );
    return;
  }

  const selectedCrew = totalSelectedCrew();
  const crewCapacity = totalCrewCapacity();
  if (selectedCrew > crewCapacity) {
    alert(
      `Selected crew (${selectedCrew}) exceed this ship's crew capacity (${crewCapacity}). ` +
        "Please reduce the crew quantity before adding this ship.",
    );
    return;
  }

  const waresList = [{ ware_id: currentShip.ware_id, amount: 1 }];
  const displayItems = [{ label: currentShip.name, amount: 1, category: "chassis" }];
  const selections = {};

  for (const row of groupsContainer.querySelectorAll(".group-row")) {
    const select = row.querySelector(".group-select");
    if (!select.value) continue;
    const slotCount = Number(row.dataset.slotCount);
    const isSurfaceElementShield = row.classList.contains("bonus-shield-row");
    const waresListItem = { ware_id: select.value, amount: slotCount };
    // A bonus M shield can share the exact same ware_id as an ordinary
    // main shield -- nothing about the ware itself says which role it's
    // playing here, only that this .group-row is a dedicated bonus-shield
    // slot (see buildGroupRow()'s isLinkedShield handling) -- so it's
    // tagged explicitly for summarize_production.py's
    // group_by_component_type option (see its module docstring) rather
    // than left to the DB-driven default, which can't tell the two apart.
    if (isSurfaceElementShield) waresListItem.category = "surface_element_shield";
    waresList.push(waresListItem);
    displayItems.push({
      label: select.options[select.selectedIndex].textContent,
      amount: slotCount,
      category: shieldDisplayCategory(row.dataset.componentType, isSurfaceElementShield),
    });
    selections[row.dataset.groupKey] = select.value;
  }

  for (const [wareId, amount] of Object.entries(missileAmounts)) {
    if (amount <= 0) continue;
    const missile = allMissiles.find((m) => m.ware_id === wareId);
    waresList.push({ ware_id: wareId, amount });
    displayItems.push({ label: missile ? missile.name : wareId, amount, category: "missile" });
  }
  for (const [wareId, amount] of Object.entries(droneAmounts)) {
    if (amount <= 0) continue;
    const drone = allDrones.find((d) => d.ware_id === wareId);
    waresList.push({ ware_id: wareId, amount });
    displayItems.push({ label: drone ? drone.name : wareId, amount, category: "drone" });
  }
  for (const [wareId, amount] of Object.entries(deployableAmounts)) {
    if (amount <= 0) continue;
    const deployable = allDeployables.find((d) => d.ware_id === wareId);
    waresList.push({ ware_id: wareId, amount });
    displayItems.push({ label: deployable ? deployable.name : wareId, amount, category: "deployable" });
  }
  for (const [wareId, amount] of Object.entries(countermeasureAmounts)) {
    if (amount <= 0) continue;
    const countermeasure = allCountermeasures.find((c) => c.ware_id === wareId);
    waresList.push({ ware_id: wareId, amount });
    displayItems.push({ label: countermeasure ? countermeasure.name : wareId, amount, category: "countermeasure" });
  }
  for (const [role, amount] of Object.entries(crewAmounts)) {
    if (amount <= 0) continue;
    const crew = allCrew.find((c) => c.ware_id === role);
    // Both roles share one real ware_id (see CREW_ROLES/crewWareId's own
    // comment) -- the category override is what keeps a Marine and a
    // Service Crew contribution distinguishable everywhere downstream
    // (the Loadout display, the Ware Cost List's by-component-type view,
    // and reconstructCartEntry() on reload), the same mechanism a bonus
    // M shield already uses to stay distinguishable from an ordinary main
    // shield of the same ware_id.
    const category = role === "marine" ? "crew_marine" : "crew_service";
    waresList.push({ ware_id: crewWareId, amount, category });
    displayItems.push({ label: crew ? crew.name : role, amount, category });
  }

  const missileAmountsSnapshot = { ...missileAmounts };
  const droneAmountsSnapshot = { ...droneAmounts };
  const deployableAmountsSnapshot = { ...deployableAmounts };
  const countermeasureAmountsSnapshot = { ...countermeasureAmounts };
  const crewAmountsSnapshot = { ...crewAmounts };

  // Free-text, user-authored reminder of what this configuration is *for*
  // (e.g. "Boron border patrol") -- purely a display annotation, never sent
  // to /api/summarize or /api/price_summary, so there's nothing to validate.
  const note = shipNoteInput.value.trim();

  if (editingIndex !== null) {
    activeFleet().cart[editingIndex] = {
      ...activeFleet().cart[editingIndex],
      shipWareId: currentShip.ware_id,
      shipName: currentShip.name,
      shipIcon: currentShip.icon,
      missingRequiredComponents: missingRequired,
      note,
      selections,
      missileAmounts: missileAmountsSnapshot,
      droneAmounts: droneAmountsSnapshot,
      deployableAmounts: deployableAmountsSnapshot,
      countermeasureAmounts: countermeasureAmountsSnapshot,
      crewAmounts: crewAmountsSnapshot,
      wares_list: waresList,
      displayItems,
    };
  } else {
    // Seeded once, here, rather than kept dynamic: the priority list is
    // meant to be freely hand-edited afterward (see the Build Method modal)
    // without this logic silently re-sorting it back out from under the
    // user on every subsequent add/remove -- so this only ever fires for
    // this fleet's very first ship, and only if its priority hasn't
    // already been explicitly set (e.g. via the modal, before any ship was
    // added). currentShip.production_method is that hull's own primary
    // build method (see query_ship_groups()'s own comment) -- promoted to
    // the front of the normal default order, not a full replacement, since
    // components the ship itself doesn't gate (raw materials, generic
    // equipment) may still need the rest of that order as fallback.
    const isFirstShipInFleet = activeFleet().cart.length === 0;
    if (isFirstShipInFleet && !activeFleet().buildMethodPriority && currentShip.production_method) {
      activeFleet().buildMethodPriority = [
        currentShip.production_method,
        ...allBuildMethods.filter((method) => method !== currentShip.production_method),
      ];
    }
    activeFleet().cart.push({
      shipWareId: currentShip.ware_id,
      shipName: currentShip.name,
      shipIcon: currentShip.icon,
      missingRequiredComponents: missingRequired,
      note,
      count: 1,
      selections,
      missileAmounts: missileAmountsSnapshot,
      droneAmounts: droneAmountsSnapshot,
      deployableAmounts: deployableAmountsSnapshot,
      countermeasureAmounts: countermeasureAmountsSnapshot,
      crewAmounts: crewAmountsSnapshot,
      wares_list: waresList,
      displayItems,
    });
  }

  // Updating an existing entry (editingIndex !== null) still clears the
  // builder afterward, same as before -- there's nothing left to keep
  // tweaking once the edit's been committed back into that cart slot. A
  // fresh add, though, leaves the ship loaded with its current selections
  // so the user can keep adjusting it (or add another copy) without
  // re-picking everything from scratch; one of the Clear buttons (top/
  // bottom, see clearShipBtnTop/Bottom) starts over explicitly.
  if (editingIndex !== null) resetShipPicker();
  activeFleet().dirty = true;
  renderCart();
}

addToCartBtn.addEventListener("click", addSelectedShipToCart);
addToCartBtnTop.addEventListener("click", addSelectedShipToCart);

// Order-independent deep-equal for the plain flat {string: primitive}
// maps this app builds (selections, missileAmounts, droneAmounts, etc.) --
// sorts keys at every level so two objects with the same content built in
// a different insertion order still compare equal.
function stableStringify(value) {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  const keys = Object.keys(value).sort();
  return `{${keys.map((k) => JSON.stringify(k) + ":" + stableStringify(value[k])).join(",")}}`;
}

// Same group-row gathering addToCartBtn's handler does above, factored out
// so "Add To Saved Loadouts" can build a comparable selections map without
// duplicating that DOM walk.
function gatherCurrentSelections() {
  const selections = {};
  for (const row of groupsContainer.querySelectorAll(".group-row")) {
    const select = row.querySelector(".group-select");
    if (select.value) selections[row.dataset.groupKey] = select.value;
  }
  return selections;
}

// "Add To Saved Loadouts": snapshots the current ship-builder state into
// the same importedLoadoutsResult working set "Import Game Loadouts"/
// "Import Raw XML Loadout" feed (see mergeImportedLoadoutsResult()), so it
// immediately shows up in "Select Filter Loadout"/"Select <ship> Loadout"
// and gets picked up by "Export Loadouts" too (server-side synthesized
// rawXml -- see import_loadouts.py's build_loadout_xml()).
async function addToSavedLoadouts() {
  if (!currentShip) return;

  const name = shipNoteInput.value.trim();
  const candidate = {
    shipWareId: currentShip.ware_id,
    selections: gatherCurrentSelections(),
    missileAmounts: { ...missileAmounts },
    droneAmounts: { ...droneAmounts },
    deployableAmounts: { ...deployableAmounts },
    countermeasureAmounts: { ...countermeasureAmounts },
    crewAmounts: { ...crewAmounts },
  };

  // Duplicate check: name first (cheap short-circuit), then every
  // subcomponent besides id -- shipWareId included alongside the fields
  // the user named, since two loadouts for genuinely different ships
  // should never count as "the same loadout" even if their component maps
  // happen to coincide (e.g. both freshly started with nothing picked).
  const isDuplicate = (importedLoadoutsResult?.ships ?? []).some((existing) => {
    if ((existing.name || "") !== name) return false;
    if (existing.shipWareId !== candidate.shipWareId) return false;
    for (const field of ["selections", "missileAmounts", "droneAmounts", "deployableAmounts", "countermeasureAmounts", "crewAmounts"]) {
      if (stableStringify(existing[field]) !== stableStringify(candidate[field])) return false;
    }
    return true;
  });

  if (isDuplicate) {
    showAddToSavedLoadoutsStatus(["Loadout already saved"], true);
    return;
  }

  setAddToSavedLoadoutsBtnsDisabled(true);
  try {
    const response = await fetch("/api/build_saved_loadout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, ...candidate }),
    });
    const entry = await response.json();
    if (entry.error) {
      showAddToSavedLoadoutsStatus([entry.error], true);
      return;
    }

    mergeImportedLoadoutsResult({ ships: [entry], failed: [], total_loadouts: 1, skipped_station_loadouts: 0 });
    showAddToSavedLoadoutsStatus([`Saved as "${entry.name || "(unnamed)"}".`], false);
  } catch (err) {
    showAddToSavedLoadoutsStatus([`Could not save this loadout: ${err.message}`], true);
  } finally {
    setAddToSavedLoadoutsBtnsDisabled(false);
  }
}

// Keeps both Add To Saved Loadouts buttons (top and bottom copies) in
// sync while a save request is in flight -- see setAddToCartBtnLabel()'s
// own comment for why this is worth a shared helper rather than touching
// addToSavedLoadoutsBtn/addToSavedLoadoutsBtnTop directly at each call site.
function setAddToSavedLoadoutsBtnsDisabled(disabled) {
  addToSavedLoadoutsBtn.disabled = disabled;
  addToSavedLoadoutsBtnTop.disabled = disabled;
}

function showAddToSavedLoadoutsStatus(lines, isError) {
  addToSavedLoadoutsStatus.innerHTML = "";
  for (const line of lines) {
    const div = document.createElement("div");
    div.textContent = line;
    addToSavedLoadoutsStatus.appendChild(div);
  }
  addToSavedLoadoutsStatus.classList.remove("hidden");
  addToSavedLoadoutsStatus.classList.toggle("status-error", !!isError);
}

addToSavedLoadoutsBtn.addEventListener("click", addToSavedLoadouts);
addToSavedLoadoutsBtnTop.addEventListener("click", addToSavedLoadouts);

// Renders one cart entry's displayItems into `loadoutTd`, grouped by
// component type (CART_DISPLAY_ORDER/_LABELS) -- one bold, unindented
// category heading per group, then one green, two-space-indented line per
// item underneath it ("Nx Label", matching the in-game ship builder's own
// shopping-list style this is modeled on). A category with no items at
// all is omitted entirely, same "don't show empty sections" convention
// used throughout this app. An item with no category tag (shouldn't
// normally happen -- see addToCartBtn's handler/reconstructCartEntry())
// falls into CART_DISPLAY_FALLBACK_CATEGORY rather than being dropped.
//
// entry.loadoutMinimized (toggled by the small button next to the Chassis
// heading -- always present, since every entry has a "1x <ship name>"
// chassis item) hides every other category, collapsing a long loadout down
// to just the ship itself. Purely a display preference -- re-invoked
// directly by the toggle button's own click handler rather than going
// through a full renderCart() (which would also needlessly re-run
// runCalculation()).
function renderLoadoutCell(loadoutTd, entry) {
  loadoutTd.innerHTML = "";
  const minimized = !!entry.loadoutMinimized;

  const byCategory = new Map();
  for (const item of entry.displayItems) {
    const category = item.category ?? CART_DISPLAY_FALLBACK_CATEGORY;
    if (!byCategory.has(category)) byCategory.set(category, []);
    byCategory.get(category).push(item);
  }

  for (const category of CART_DISPLAY_ORDER) {
    if (minimized && category !== "chassis") continue;

    const items = byCategory.get(category);
    if (!items || items.length === 0) continue;

    const headerRow = document.createElement("div");
    headerRow.className = "cart-loadout-category-row";

    const headerLabel = document.createElement("span");
    headerLabel.className = "cart-loadout-category";
    headerLabel.textContent = CART_DISPLAY_LABELS[category] ?? category;
    headerRow.appendChild(headerLabel);

    if (category === "chassis") {
      const toggleBtn = document.createElement("button");
      toggleBtn.type = "button";
      toggleBtn.className = "cart-loadout-toggle-btn";
      toggleBtn.textContent = minimized ? "+" : "−";
      toggleBtn.title = minimized ? "Show loadout details" : "Hide loadout details";
      toggleBtn.addEventListener("click", () => {
        entry.loadoutMinimized = !minimized;
        renderLoadoutCell(loadoutTd, entry);
      });
      headerRow.appendChild(toggleBtn);
    }

    loadoutTd.appendChild(headerRow);

    for (const item of items) {
      const itemDiv = document.createElement("div");
      itemDiv.className = "cart-loadout-item";
      // Two non-breaking spaces, not plain ones: browsers strip plain
      // leading whitespace at the start of a block box entirely.
      itemDiv.appendChild(document.createTextNode(`  ${item.amount}x `));
      appendNameWithFactionColor(itemDiv, item.label);
      loadoutTd.appendChild(itemDiv);
    }
  }
}

// Called after every fleet-list mutation (add/edit, remove, load) to keep
// the cart table and the fleet-list tab bar in sync. Does NOT trigger any
// recalculation -- cart edits just mark the active fleet dirty (see the qty
// handlers/removeBtn below) and wait for recomputeDirtyFleets(), which only
// actually runs on navigating into Cost Analysis (or immediately, for the
// couple of triggers -- price overrides, build method priority -- only reachable from
// within that page already). See PERSISTED_STATE plan notes / showPage().
function renderCart() {
  // Saved synchronously here so a refresh in the brief gap before the next
  // mutation/render doesn't lose it.
  saveState();
  // Keeps the rename input in sync whenever the active fleet changes out
  // from under it (switch/add/delete) -- setting .value here, not just on
  // its own "input" handler, is what lets a single renderCart() call cover
  // every call site that changes activeFleetIndex.
  cartNameInput.value = activeFleet().name;
  renderFleetListTabs();

  cartBody.innerHTML = "";
  cartEmptyMsg.classList.toggle("hidden", activeFleet().cart.length > 0);

  activeFleet().cart.forEach((entry, index) => {
    const tr = document.createElement("tr");

    const shipTd = document.createElement("td");
    if (entry.shipIcon) shipTd.appendChild(buildIconImg(entry.shipIcon, "ship-icon cart-ship-icon"));
    shipTd.appendChild(document.createTextNode(entry.shipName));
    // User-authored, purely a display annotation -- see the note field's
    // own comment in addToCartBtn's handler.
    if (entry.note) {
      const noteDiv = document.createElement("div");
      noteDiv.className = "cart-ship-note";
      noteDiv.textContent = entry.note;
      shipTd.appendChild(noteDiv);
    }
    // Non-blocking: addToCartBtn's handler/reconstructCartEntry() still let
    // a ship in with these missing (see missingRequiredLabels()) -- this is
    // just a visible reminder, styled like X4's own shipyard "Warnings"
    // banner (orange/amber, not the red/danger used for an actual error).
    if (entry.missingRequiredComponents && entry.missingRequiredComponents.length > 0) {
      const warningDiv = document.createElement("div");
      warningDiv.className = "cart-ship-warning";
      warningDiv.textContent = `⚠ Missing: ${entry.missingRequiredComponents.join(", ")}`;
      shipTd.appendChild(warningDiv);
    }

    // Qty control and Edit/Remove actions live in this same cell, each on
    // their own line below the ship name -- there's no separate Qty/
    // actions column any more.
    const qtyRow = document.createElement("div");
    qtyRow.className = "cart-qty-row";
    const qtyWrap = document.createElement("span");
    qtyWrap.className = "qty-control";

    const qtyInput = document.createElement("input");
    qtyInput.type = "number";
    qtyInput.min = "0";
    qtyInput.value = entry.count;
    qtyInput.className = "qty-input";
    qtyInput.addEventListener("change", () => {
      entry.count = Math.max(0, Number(qtyInput.value) || 0);
      qtyInput.value = entry.count;
      activeFleet().dirty = true;
      saveState();
    });

    const minusBtn = document.createElement("button");
    minusBtn.type = "button";
    minusBtn.textContent = "-";
    minusBtn.className = "qty-btn";
    // Shift+click zeroes this row out in one step; ctrl+click steps by 10
    // instead of 1. No "fill max" on plus here -- unlike the
    // capacity-pooled pickers above, a fleet list entry's own
    // quantity has no ceiling, so ctrl+click on plus just steps by 10 too.
    minusBtn.addEventListener("click", (event) => {
      entry.count = event.shiftKey ? 0 : Math.max(0, entry.count - (event.ctrlKey ? 10 : 1));
      qtyInput.value = entry.count;
      activeFleet().dirty = true;
      saveState();
    });

    const plusBtn = document.createElement("button");
    plusBtn.type = "button";
    plusBtn.textContent = "+";
    plusBtn.className = "qty-btn";
    plusBtn.addEventListener("click", (event) => {
      entry.count += event.ctrlKey ? 10 : 1;
      qtyInput.value = entry.count;
      activeFleet().dirty = true;
      saveState();
    });

    qtyWrap.appendChild(minusBtn);
    qtyWrap.appendChild(qtyInput);
    qtyWrap.appendChild(plusBtn);
    qtyRow.appendChild(qtyWrap);

    // Edit/Remove share this same line as the qty control -- see
    // .cart-qty-row's own CSS for the flex layout that puts them there.
    const editBtn = document.createElement("button");
    editBtn.textContent = "edit";
    editBtn.className = "edit-btn";
    editBtn.addEventListener("click", () => editCartEntry(index));
    qtyRow.appendChild(editBtn);

    const removeBtn = document.createElement("button");
    removeBtn.textContent = "x";
    removeBtn.title = "Remove";
    removeBtn.className = "remove-btn";
    removeBtn.addEventListener("click", () => {
      activeFleet().cart.splice(index, 1);
      activeFleet().dirty = true;
      if (editingIndex === index) resetShipPicker();
      renderCart();
    });
    qtyRow.appendChild(removeBtn);

    shipTd.appendChild(qtyRow);
    tr.appendChild(shipTd);

    const loadoutTd = document.createElement("td");
    loadoutTd.className = "cart-loadout";
    renderLoadoutCell(loadoutTd, entry);
    tr.appendChild(loadoutTd);

    cartBody.appendChild(tr);
  });
}

async function editCartEntry(index) {
  const entry = activeFleet().cart[index];
  const response = await fetch(`/api/ships/${encodeURIComponent(entry.shipWareId)}/groups`);
  const data = await response.json();
  if (data.error) {
    alert(`Could not load ship: ${data.error}`);
    return;
  }

  currentShip = data;
  editingIndex = index;
  // Filters are deliberately left as-is (not reset) -- the ship being
  // edited may not be in the currently filtered picker list, but
  // applyShipSelection() below only touches selectedShipWareId/
  // loadShipBtn.disabled (plain state, not DOM-row-dependent) plus
  // highlighting a matching .ship-option-row *if* one happens to exist;
  // skipping the highlight when the row's filtered out is a harmless
  // cosmetic no-op, not a functional break -- the ship builder itself
  // (renderShipDetail() below) loads correctly regardless.
  renderShipOptions();
  applyShipSelection(entry.shipWareId);
  editingIndex = index; // renderShipOptions() resets this; restore it
  renderShipDetail(data);
  applyGroupSelections(entry.selections);
  // Restored only after the launchers are actually selected above --
  // renderAmmunitionSection() drops any missileAmounts entry that isn't
  // compatible with whatever's currently selected, so restoring it any
  // earlier (while no launcher is selected yet) would wipe it out.
  missileAmounts = { ...(entry.missileAmounts ?? {}) };
  renderAmmunitionSection();
  // Drones/deployables/countermeasures/crew have no such dependency
  // (renderShipDetail() above already drew every section once), but their
  // amounts weren't restored yet at that point, so each needs a second
  // render here too.
  droneAmounts = { ...(entry.droneAmounts ?? {}) };
  renderDroneSection();
  deployableAmounts = { ...(entry.deployableAmounts ?? {}) };
  renderDeployableSection();
  countermeasureAmounts = { ...(entry.countermeasureAmounts ?? {}) };
  renderCountermeasureSection();
  crewAmounts = { ...(entry.crewAmounts ?? {}) };
  renderCrewSection();
  shipNoteInput.value = entry.note ?? "";
  setAddToCartBtnLabel("Update Fleet List");
  importedLoadoutWarningsEl.classList.add("hidden");
  shipDetail.scrollIntoView({ behavior: "smooth", block: "start" });
}

// ---- Import Game Loadouts ----
// Two modals: "Import Game Loadouts" (reads a player-saved loadouts.xml,
// either by server-side path or an uploaded file, via POST
// /api/import_loadouts) and "Select Filter Loadout" (picks one of the
// successfully-parsed ship loadouts from that import to load into the
// builder, the same way editCartEntry() loads a saved cart entry). See
// import_loadouts.py's own module docstring for the schema being parsed
// and how each field maps onto this app's own cart-entry shape.

// The most recent POST /api/import_loadouts response
// ({ships, failed, total_loadouts, skipped_station_loadouts}), or null
// before any import has run -- populates the "Select Filter Loadout" modal,
// see openSelectGameLoadoutModal().
let importedLoadoutsResult = null;

function openImportLoadoutsModal() {
  importLoadoutsPathInput.value = "";
  importLoadoutsFileInput.value = "";
  importLoadoutsStatus.classList.add("hidden");
  importLoadoutsStatus.classList.remove("status-error");
  importLoadoutsModalOverlay.classList.remove("hidden");
}

function closeImportLoadoutsModal() {
  importLoadoutsModalOverlay.classList.add("hidden");
}

function showImportLoadoutsStatus(lines, isError) {
  importLoadoutsStatus.innerHTML = "";
  for (const line of lines) {
    const div = document.createElement("div");
    div.textContent = line;
    importLoadoutsStatus.appendChild(div);
  }
  importLoadoutsStatus.classList.remove("hidden");
  importLoadoutsStatus.classList.toggle("status-error", !!isError);
}

// Reads the file client-side (FileReader) rather than uploading it as
// multipart form data -- the parsed result never needs the raw bytes
// again after this one request, and reusing the same JSON POST body
// shape as the path-based case (just swapping which field is set) keeps
// api.py's endpoint down to one simple branch instead of two request
// formats.
function readFileAsText(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file);
  });
}

async function runImportLoadouts() {
  const path = importLoadoutsPathInput.value.trim();
  const file = importLoadoutsFileInput.files[0];
  if (!path && !file) {
    showImportLoadoutsStatus(["Enter a path or choose a file first."], true);
    return;
  }

  importLoadoutsRunBtn.disabled = true;
  showImportLoadoutsStatus(["Importing…"], false);
  try {
    const body = path ? { path } : { xml_text: await readFileAsText(file) };
    const response = await fetch("/api/import_loadouts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const result = await response.json();
    if (result.error) {
      showImportLoadoutsStatus([result.error], true);
      return;
    }

    mergeImportedLoadoutsResult(result);

    // These counts describe just this run's own result (not the merged,
    // cumulative importedLoadoutsResult) -- see mergeImportedLoadoutsResult().
    const warningCount = result.ships.reduce((sum, s) => sum + s.warnings.length, 0);
    const lines = [
      `Imported ${result.ships.length} ship loadout(s).`,
      `${result.skipped_station_loadouts} station module loadout(s) skipped.`,
    ];
    if (result.failed.length > 0) lines.push(`${result.failed.length} loadout(s) failed to parse.`);
    if (warningCount > 0) lines.push(`${warningCount} warning(s) across imported ships -- see "Select Filter Loadout".`);
    showImportLoadoutsStatus(lines, false);
  } catch (err) {
    showImportLoadoutsStatus([`Import failed: ${err.message}`], true);
  } finally {
    importLoadoutsRunBtn.disabled = false;
  }
}

importLoadoutsBtn.addEventListener("click", openImportLoadoutsModal);
importLoadoutsCancelBtn.addEventListener("click", closeImportLoadoutsModal);
importLoadoutsRunBtn.addEventListener("click", runImportLoadouts);

function openImportRawXmlLoadoutModal() {
  importRawXmlLoadoutTextarea.value = "";
  importRawXmlLoadoutStatus.classList.add("hidden");
  importRawXmlLoadoutStatus.classList.remove("status-error");
  importRawXmlLoadoutModalOverlay.classList.remove("hidden");
}

function closeImportRawXmlLoadoutModal() {
  importRawXmlLoadoutModalOverlay.classList.add("hidden");
}

function showImportRawXmlLoadoutStatus(lines, isError) {
  importRawXmlLoadoutStatus.innerHTML = "";
  for (const line of lines) {
    const div = document.createElement("div");
    div.textContent = line;
    importRawXmlLoadoutStatus.appendChild(div);
  }
  importRawXmlLoadoutStatus.classList.remove("hidden");
  importRawXmlLoadoutStatus.classList.toggle("status-error", !!isError);
}

// Merges a POST /api/import_loadouts response into the existing working
// set instead of replacing it -- shared by both runImportLoadouts()
// (file/path) and runImportRawXmlLoadout() (pasted snippet), so importing
// from either source repeatedly only ever adds ships, never discards
// whatever's already been imported from the other one. See
// clearImportedLoadouts() below for the only way to actually reset it.
function mergeImportedLoadoutsResult(result) {
  if (!importedLoadoutsResult) {
    importedLoadoutsResult = result;
  } else {
    importedLoadoutsResult.ships.push(...result.ships);
    importedLoadoutsResult.failed.push(...result.failed);
    importedLoadoutsResult.total_loadouts += result.total_loadouts;
    importedLoadoutsResult.skipped_station_loadouts += result.skipped_station_loadouts;
  }
  updateLoadoutManagerBtnStates();
}

// Select/Export/Clear all share the same precondition (a non-empty
// importedLoadoutsResult) -- kept in one place so every mutation of it
// (merge or clear) keeps all three, plus the per-chassis button, in sync.
function updateLoadoutManagerBtnStates() {
  const hasLoadouts = !!importedLoadoutsResult && importedLoadoutsResult.ships.length > 0;
  selectGameLoadoutBtn.disabled = !hasLoadouts;
  exportLoadoutsBtn.disabled = !hasLoadouts;
  clearLoadoutsBtn.disabled = !hasLoadouts;
  updateSelectChassisLoadoutBtnState();
  saveState();
}

// Discards the entire imported-loadouts working set (both "Import Game
// Loadouts" and "Import Raw XML Loadout" feed into the same
// importedLoadoutsResult -- there's no way to clear just one source).
// Confirmed first since this can't be undone short of re-importing.
function clearImportedLoadouts() {
  if (!confirm("Are you sure you want to clear all saved loadouts?")) return;
  importedLoadoutsResult = null;
  updateLoadoutManagerBtnStates();
}

// Downloads every currently imported/pasted loadout as one loadouts.xml,
// wrapping each ship entry's own verbatim rawXml (see import_loadouts.py's
// parse_ship_loadout() -- the original <loadout> element, re-serialized
// from the parsed tree) in a fresh <loadouts> root. Client-side only, no
// server round-trip needed since rawXml is already sitting in
// importedLoadoutsResult from whichever import produced it.
function exportLoadouts() {
  if (!importedLoadoutsResult || importedLoadoutsResult.ships.length === 0) return;

  const confirmed = confirm(
    "WARNING: Be careful when overwriting your loadouts file with the downloaded one here. I can not guarantee it " +
      "won't break the game loadouts. Make sure to back up your loadouts file somewhere before you try it, and/or " +
      "copy-paste in any new XML loadouts you want to import in to your game.",
  );
  if (!confirmed) return;

  const body = importedLoadoutsResult.ships.map((s) => s.rawXml).join("\n  ");
  const xml = `<?xml version="1.0" encoding="utf-8"?>\n<loadouts>\n  ${body}\n</loadouts>\n`;

  const blob = new Blob([xml], { type: "application/xml" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "loadouts.xml";
  link.click();
  URL.revokeObjectURL(url);
}

exportLoadoutsBtn.addEventListener("click", exportLoadouts);
clearLoadoutsBtn.addEventListener("click", clearImportedLoadouts);

async function runImportRawXmlLoadout() {
  const xmlText = importRawXmlLoadoutTextarea.value.trim();
  if (!xmlText) {
    showImportRawXmlLoadoutStatus(["Paste a <loadout> or <loadouts> XML snippet first."], true);
    return;
  }

  importRawXmlLoadoutConfirmBtn.disabled = true;
  showImportRawXmlLoadoutStatus(["Importing…"], false);
  try {
    const response = await fetch("/api/import_loadouts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ xml_text: xmlText }),
    });
    const result = await response.json();
    if (result.error) {
      showImportRawXmlLoadoutStatus([result.error], true);
      return;
    }

    mergeImportedLoadoutsResult(result);

    const warningCount = result.ships.reduce((sum, s) => sum + s.warnings.length, 0);
    const lines = [`Added ${result.ships.length} ship loadout(s).`];
    if (result.skipped_station_loadouts > 0) lines.push(`${result.skipped_station_loadouts} station module loadout(s) skipped.`);
    if (result.failed.length > 0) lines.push(`${result.failed.length} loadout(s) failed to parse.`);
    if (warningCount > 0) lines.push(`${warningCount} warning(s) -- see "Select Filter Loadout".`);
    showImportRawXmlLoadoutStatus(lines, false);
  } catch (err) {
    showImportRawXmlLoadoutStatus([`Import failed: ${err.message}`], true);
  } finally {
    importRawXmlLoadoutConfirmBtn.disabled = false;
  }
}

importRawXmlLoadoutBtn.addEventListener("click", openImportRawXmlLoadoutModal);
importRawXmlLoadoutCancelBtn.addEventListener("click", closeImportRawXmlLoadoutModal);
importRawXmlLoadoutConfirmBtn.addEventListener("click", runImportRawXmlLoadout);

// Shared by both the "Select Filter Loadout" button (every imported ship)
// and the "Select chassis loadout" button next to the loaded ship's name
// (only loadouts whose shipWareId matches the currently loaded ship) --
// chassisWareId is omitted for the former, passed for the latter.
function openSelectGameLoadoutModal(chassisWareId) {
  if (!importedLoadoutsResult) return;
  let entries = chassisWareId
    ? importedLoadoutsResult.ships.filter((s) => s.shipWareId === chassisWareId)
    : importedLoadoutsResult.ships;

  // Looked up for every entry regardless of chassisWareId -- used below
  // both for the generic view's filter/sort and (in both views) for each
  // row's own chassis icon, since an imported-loadout entry only carries
  // its shipName as plain text, not the icon symbol allShips already has.
  const shipByWareId = new Map(allShips.map((ship) => [ship.ware_id, ship]));

  // The generic "Select Filter Loadout" button (chassisWareId omitted)
  // applies the exact same Size/Purpose/Type filters and ship-list
  // ordering as the picker above it -- a ship-specific "Select <Ship>
  // Loadout" button (chassisWareId given) is already narrowed to one
  // ship, so filtering/sorting by ship would be a no-op there anyway,
  // and skipping it means an out-of-filter ship's own loadouts still stay
  // reachable from its own button.
  if (!chassisWareId) {
    entries = entries
      .filter((entry) => {
        const ship = shipByWareId.get(entry.shipWareId);
        return ship ? shipPassesCurrentFilters(ship) : true;
      })
      .slice()
      .sort((a, b) => {
        const shipA = shipByWareId.get(a.shipWareId);
        const shipB = shipByWareId.get(b.shipWareId);
        const shipCompare = shipA && shipB ? compareShips(shipA, shipB) : 0;
        return shipCompare !== 0 ? shipCompare : (a.name || "").localeCompare(b.name || "");
      });
  }

  selectGameLoadoutModalTitle.textContent = chassisWareId ? `Select ${currentShip.name} Loadout` : "Select Filter Loadout";
  selectGameLoadoutList.innerHTML = "";

  if (entries.length === 0) {
    const empty = document.createElement("p");
    empty.textContent = chassisWareId
      ? "No imported loadouts for this ship."
      : "No imported loadouts match the current filters.";
    selectGameLoadoutList.appendChild(empty);
  }

  for (const entry of entries) {
    const row = document.createElement("div");
    row.className = "select-game-loadout-row";

    const nameSpan = document.createElement("span");
    nameSpan.className = "select-game-loadout-row-name";
    nameSpan.textContent = entry.name || "(unnamed)";
    row.appendChild(nameSpan);

    // Redundant when already filtered to one chassis, but harmless to
    // leave in -- keeps this row layout identical between both modes.
    const shipSpan = document.createElement("span");
    shipSpan.className = "select-game-loadout-row-ship";
    shipSpan.textContent = entry.shipName;
    row.appendChild(shipSpan);

    const ship = shipByWareId.get(entry.shipWareId);
    if (ship?.icon) row.appendChild(buildIconImg(ship.icon, "ship-icon"));

    if (entry.warnings.length > 0) {
      const warnSpan = document.createElement("span");
      warnSpan.className = "select-game-loadout-row-warning-count";
      warnSpan.textContent = `${entry.warnings.length} warning(s)`;
      row.appendChild(warnSpan);
    }

    row.addEventListener("click", () => loadImportedGameLoadout(entry));
    selectGameLoadoutList.appendChild(row);
  }
  selectGameLoadoutModalOverlay.classList.remove("hidden");
}

function closeSelectGameLoadoutModal() {
  selectGameLoadoutModalOverlay.classList.add("hidden");
}

// Enabled once loadouts have been imported AND at least one of them
// targets the currently loaded ship's exact chassis (ware_id) -- called
// after every import run and every renderShipDetail() (ship load).
function updateSelectChassisLoadoutBtnState() {
  selectChassisLoadoutBtn.disabled =
    !importedLoadoutsResult || !currentShip || !importedLoadoutsResult.ships.some((s) => s.shipWareId === currentShip.ware_id);
}

selectGameLoadoutBtn.addEventListener("click", () => openSelectGameLoadoutModal());
selectChassisLoadoutBtn.addEventListener("click", () => openSelectGameLoadoutModal(currentShip?.ware_id));
selectGameLoadoutCancelBtn.addEventListener("click", closeSelectGameLoadoutModal);

// Loads one parsed loadout (see import_loadouts.py's parse_ship_loadout())
// into the ship builder as a fresh, unsaved configuration -- same restore
// sequence as editCartEntry(), except editingIndex stays null (this isn't
// editing an existing cart entry -- "Add To Fleet List" will append
// a new one) and the loadout's own name seeds the note field instead of a
// saved entry's note.
async function loadImportedGameLoadout(entry) {
  const response = await fetch(`/api/ships/${encodeURIComponent(entry.shipWareId)}/groups`);
  const data = await response.json();
  if (data.error) {
    alert(`Could not load ship: ${data.error}`);
    return;
  }

  currentShip = data;
  editingIndex = null;
  // Filters deliberately left as-is -- see editCartEntry()'s own comment
  // on the identical choice.
  renderShipOptions();
  applyShipSelection(entry.shipWareId);
  renderShipDetail(data);
  applyGroupSelections(entry.selections);
  missileAmounts = { ...entry.missileAmounts };
  renderAmmunitionSection();
  droneAmounts = { ...entry.droneAmounts };
  renderDroneSection();
  deployableAmounts = { ...entry.deployableAmounts };
  renderDeployableSection();
  countermeasureAmounts = { ...entry.countermeasureAmounts };
  renderCountermeasureSection();
  crewAmounts = { ...entry.crewAmounts };
  renderCrewSection();
  shipNoteInput.value = entry.name ?? "";
  setAddToCartBtnLabel("Add To Fleet List");

  importedLoadoutWarningsEl.innerHTML = "";
  if (entry.warnings.length > 0) {
    const heading = document.createElement("strong");
    heading.textContent = `${entry.warnings.length} thing(s) this import couldn't match exactly:`;
    importedLoadoutWarningsEl.appendChild(heading);
    const list = document.createElement("ul");
    for (const warning of entry.warnings) {
      const li = document.createElement("li");
      li.textContent = warning;
      list.appendChild(li);
    }
    importedLoadoutWarningsEl.appendChild(list);
    importedLoadoutWarningsEl.classList.remove("hidden");
  } else {
    importedLoadoutWarningsEl.classList.add("hidden");
  }

  closeSelectGameLoadoutModal();
  shipDetail.scrollIntoView({ behavior: "smooth", block: "start" });
}

// Bumped on every recomputeDirtyFleets() call and captured as `token` at
// the start of each -- a response is only applied if it's still the latest
// call by the time it arrives, so rapid back-to-back triggers (e.g.
// switching straight back into Cost Analysis, or two price-override edits
// in quick succession) can't let an older, slower response clobber a newer
// one on screen.
let calculationToken = 0;

// The Ware Cost List always fetches both grouping modes at once -- "total"
// (group_by_component_type false) for the "Total Cost Breakdown" tab and
// "component_type" (true) for the "Component Type Cost Breakdown" tab --
// rather than a checkbox controlling which single mode gets requested.
// Switching tabs is then a pure client-side re-render (see
// renderWareCostList()), never a new request.
let activeWareCostListTab = "total";

// Whether the current render has a baseline column to compare every other
// fleet against -- set once per renderWareCostList() call and read by
// appendComparisonCell() below, rather than threading a parameter through
// every rendering function in the tier -> method -> [category] -> row
// chain. wareCostListColumns() always sorts the active fleet into column 0,
// and `fleets` is never empty, so this is unconditionally true today -- kept
// as its own flag (rather than inlined) since the diff-rendering functions
// already read it by name.
let wareCostListHasBaseline = true;

// Resolves to the parsed JSON body, or throws (with the response's own
// error text) on a non-ok response -- lets recomputeDirtyFleets() below fire
// every summarize()/price_summary combination via Promise.all and handle
// any one of them failing with a single try/catch, instead of checking
// .ok on each individually.
async function fetchJsonResult(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

function fetchSummarizeResult(searchDepth, groupByComponentType, baseBody) {
  return fetchJsonResult("/api/summarize", {
    ...baseBody,
    search_depth: searchDepth,
    group_by_component_type: groupByComponentType,
  });
}

function fetchPriceSummaryResult(groupByComponentType, baseBody) {
  return fetchJsonResult("/api/price_summary", { ...baseBody, group_by_component_type: groupByComponentType });
}

// Fetches all four summarize() depth x grouping-mode combinations plus both
// price_summary grouping modes for one cart + build method priority list,
// returning the exact {total: {...}, component_type: {...}} shape every
// fleet.wareCostList holds. buildMethodPriority null is passed straight
// through to the API as-is -- both /api/summarize and /api/price_summary
// already treat a null build_method_priority as "use the server's own
// default" (DEFAULT_BUILD_METHOD_PRIORITY), same meaning
// fleet.buildMethodPriority gives it client-side. Shared by
// recomputeDirtyFleets() (called once per dirty fleet) and
// recomputeFleetBuildConfig() (a single fleet, re-run only when that
// fleet's own build method is explicitly edited) -- pure function of its
// two arguments, doesn't know or care which fleet it's for.
async function computeWareCostList(cartEntries, buildMethodPriority) {
  const wares = cartEntries.map((entry) => ({ count: entry.count, wares_list: entry.wares_list }));
  const summarizeBaseBody = { build_method_priority: buildMethodPriority, verbose: false, wares };
  const priceBaseBody = { build_method_priority: buildMethodPriority, wares, price_overrides: priceOverrides };

  const [
    totalRawMaterials,
    totalProductionWares,
    componentTypeRawMaterials,
    componentTypeProductionWares,
    flatPriceSummary,
    groupedPriceSummary,
  ] = await Promise.all([
    fetchSummarizeResult(RAW_MATERIALS_SEARCH_DEPTH, false, summarizeBaseBody),
    fetchSummarizeResult(PRODUCTION_WARES_SEARCH_DEPTH, false, summarizeBaseBody),
    fetchSummarizeResult(RAW_MATERIALS_SEARCH_DEPTH, true, summarizeBaseBody),
    fetchSummarizeResult(PRODUCTION_WARES_SEARCH_DEPTH, true, summarizeBaseBody),
    fetchPriceSummaryResult(false, priceBaseBody),
    fetchPriceSummaryResult(true, priceBaseBody),
  ]);

  return {
    total: {
      raw_materials: totalRawMaterials,
      production_wares: totalProductionWares,
      raw_materials_price: flatPriceSummary.raw_materials,
      production_wares_price: flatPriceSummary.production_wares,
      top_level_price: flatPriceSummary.top_level,
    },
    component_type: {
      raw_materials: componentTypeRawMaterials,
      production_wares: componentTypeProductionWares,
      raw_materials_price: groupedPriceSummary.raw_materials,
      production_wares_price: groupedPriceSummary.production_wares,
      top_level_price: groupedPriceSummary.top_level,
    },
  };
}

// The lazy-recompute core: recomputes computeWareCostList() for every fleet
// whose .dirty is true (cart edits/removals just set that flag -- see
// renderCart() -- rather than calling this directly), clears the flag on
// success, then re-renders the Ware Cost List once. Called from showPage()
// on navigating into Cost Analysis, from bootstrap() when the page loads
// directly into Cost Analysis (e.g. a bookmarked #cost-analysis link), and
// eagerly from the two triggers only reachable from *within* that page
// already -- price overrides (markAllFleetsDirtyAndRecompute()) and a
// fleet's own build method priority (recomputeFleetBuildConfig() below) -- since
// "navigate in" will never fire again while already there.
//
// Promise.allSettled (not Promise.all) closing over fleet objects (not
// indices): one fleet's API failure can't blank out another fleet's fresh
// numbers, and a fleet deleted while its own request is still in flight just
// silently no-ops when that response lands (writing onto a detached object),
// rather than corrupting anything by index.
async function recomputeDirtyFleets() {
  const token = ++calculationToken;
  const dirtyFleets = fleets.filter((fleet) => fleet.dirty);

  await Promise.allSettled(
    dirtyFleets.map(async (fleet) => {
      if (fleet.cart.length === 0) {
        fleet.wareCostList = null;
        fleet.dirty = false;
        return;
      }
      try {
        fleet.wareCostList = await computeWareCostList(fleet.cart, fleet.buildMethodPriority);
        fleet.dirty = false;
      } catch (err) {
        // Left dirty -- retried on the next trigger. fleet.wareCostList
        // keeps whatever it last successfully held (possibly null).
        console.error(`Calculation failed for fleet "${fleet.name}": ${err.message}`);
      }
    }),
  );

  if (token !== calculationToken) return; // superseded by a newer call
  renderWareCostList(); // always -- e.g. a fleet switch with nothing dirty still needs the baseline reorder
}

// Re-runs one fleet's own calculation with a newly edited build method (see
// the Build Method modal's Save handler below), then recomputes it
// immediately -- this only ever fires from one deliberate action (editing
// that fleet's own build method, from within the Cost Analysis page, where
// "navigate in" won't happen again), so there's nothing to defer.
function recomputeFleetBuildConfig(fleetIndex, buildMethodPriority) {
  const fleet = fleets[fleetIndex];
  if (!fleet) return;
  fleet.buildMethodPriority = buildMethodPriority;
  fleet.dirty = true;
  recomputeDirtyFleets();
}

// Opens the Build Method modal for `column` (one of wareCostListColumns()'s
// own entries) -- populates the priority checklist from
// column.buildMethodPriority, defaulting to allBuildMethods itself (in its
// already-correct order) when that column has never had one set. Every
// method in allBuildMethods is always shown, even ones this column's own
// customized list had unchecked/excluded -- see buildMethodModalPriorityOrder's
// own comment for why order and inclusion are tracked independently.
function openBuildMethodModal(column) {
  buildMethodModalTarget = column;

  const currentOrder = column.buildMethodPriority ?? allBuildMethods;
  const includedSet = new Set(currentOrder);
  // Anything in allBuildMethods but not in this column's own saved order
  // (e.g. a method added to the game data after this column's list was
  // last customized) is appended at the end, unchecked -- still editable,
  // never silently dropped.
  const extras = allBuildMethods.filter((m) => !includedSet.has(m));
  buildMethodModalPriorityOrder = [...currentOrder, ...extras].map((name) => ({
    name,
    included: includedSet.has(name),
  }));

  renderBuildMethodModalPriorityList();
  buildMethodModalOverlay.classList.remove("hidden");
}

// Rebuilds the modal's priority checklist from
// buildMethodModalPriorityOrder -- called on open and after every
// checkbox/reorder edit (the list is small, a handful of rows, so a full
// rebuild per edit is simpler than patching individual rows in place).
function renderBuildMethodModalPriorityList() {
  buildMethodModalPriorityList.innerHTML = "";

  buildMethodModalPriorityOrder.forEach((entry, index) => {
    const row = document.createElement("div");
    row.className = "build-method-fallback-row";

    const label = document.createElement("label");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = entry.included;
    checkbox.addEventListener("change", () => {
      entry.included = checkbox.checked;
    });
    label.appendChild(checkbox);
    const nameSpan = document.createElement("span");
    applyBuildMethodColor(nameSpan, entry.name);
    nameSpan.textContent = entry.name;
    label.appendChild(nameSpan);
    row.appendChild(label);

    const upBtn = document.createElement("button");
    upBtn.type = "button";
    upBtn.className = "build-method-reorder-btn";
    upBtn.textContent = "↑";
    upBtn.disabled = index === 0;
    upBtn.addEventListener("click", () => {
      [buildMethodModalPriorityOrder[index - 1], buildMethodModalPriorityOrder[index]] = [
        buildMethodModalPriorityOrder[index],
        buildMethodModalPriorityOrder[index - 1],
      ];
      renderBuildMethodModalPriorityList();
    });
    row.appendChild(upBtn);

    const downBtn = document.createElement("button");
    downBtn.type = "button";
    downBtn.className = "build-method-reorder-btn";
    downBtn.textContent = "↓";
    downBtn.disabled = index === buildMethodModalPriorityOrder.length - 1;
    downBtn.addEventListener("click", () => {
      [buildMethodModalPriorityOrder[index], buildMethodModalPriorityOrder[index + 1]] = [
        buildMethodModalPriorityOrder[index + 1],
        buildMethodModalPriorityOrder[index],
      ];
      renderBuildMethodModalPriorityList();
    });
    row.appendChild(downBtn);

    buildMethodModalPriorityList.appendChild(row);
  });
}

function closeBuildMethodModal() {
  buildMethodModalOverlay.classList.add("hidden");
  buildMethodModalTarget = null;
  buildMethodModalPriorityOrder = [];
}

buildMethodModalCancelBtn.addEventListener("click", closeBuildMethodModal);

buildMethodModalSaveBtn.addEventListener("click", () => {
  if (!buildMethodModalTarget) return;

  const buildMethodPriority = buildMethodModalPriorityOrder.filter((entry) => entry.included).map((entry) => entry.name);

  const column = buildMethodModalTarget;
  closeBuildMethodModal();
  recomputeFleetBuildConfig(column.fleetIndex, buildMethodPriority);
});

// Tab buttons are static markup (not rebuilt per render), so wiring them
// up once here at load time is enough -- matches the filter all/none
// buttons' pattern earlier in this file.
for (const btn of document.querySelectorAll("[data-ware-cost-list-tab]")) {
  btn.addEventListener("click", () => {
    activeWareCostListTab = btn.dataset.wareCostListTab;
    for (const other of document.querySelectorAll("[data-ware-cost-list-tab]")) {
      other.classList.toggle("active", other === btn);
    }
    renderWareCostList();
  });
}

// Display labels for group_by_component_type's category keys (see
// summarize_production.py's module docstring) -- a different, ware-cost-
// list-specific vocabulary from COMPONENT_TYPE_LABELS above (which
// describes picker *groups*, not summarize() output categories). Covers
// every category fetch_ware_categories() can actually produce (same set
// CART_DISPLAY_ORDER enumerates) -- falls back to the raw, lowercase
// category string for anything not listed here, which should never
// normally happen.
const WARE_COST_LIST_CATEGORY_LABELS = {
  chassis: "Chassis",
  engine: "Engines",
  main_shield: "Main Shield",
  surface_element_shield: "Surface Element Shield",
  thruster: "Thrusters",
  turret: "Turrets",
  weapon: "Weapons",
  software: "Software",
  missile: "Missiles",
  drone: "Drones",
  deployable: "Deployables",
  countermeasure: "Countermeasures",
  crew_marine: "Marines",
  crew_service: "Service Crew",
  production_wares: "Production Wares",
};

// Sorts category keys to match the ship builder's own section order
// (CART_DISPLAY_ORDER) instead of alphabetically -- shared by every
// category-grouped section of the Ware Cost List (appendWareCostListTier,
// appendMoneyTopLevelEntry, appendMoneyTier), so "Component Type Cost
// Breakdown" always lists categories top-to-bottom in the same order
// they're actually picked in on the builder. A category not found in
// CART_DISPLAY_ORDER (shouldn't normally happen) sorts after every known
// one, alphabetically among themselves.
function sortCategoriesForDisplay(categoryNames) {
  return [...categoryNames].sort((a, b) => {
    const indexA = CART_DISPLAY_ORDER.indexOf(a);
    const indexB = CART_DISPLAY_ORDER.indexOf(b);
    if (indexA === -1 && indexB === -1) return a.localeCompare(b);
    if (indexA === -1) return 1;
    if (indexB === -1) return -1;
    return indexA - indexB;
  });
}

// True when a method's "parts" is the group_by_component_type shape
// (category -> (ware_id -> amount)) rather than the default flat
// ware_id -> amount map -- distinguished by the type of its own values,
// since summarize_production.py's request flag isn't echoed back in the
// response itself. An empty "parts" (a build_method_priority that turned
// out fully unresolvable) reads as flat either way -- there's nothing to
// render regardless.
function isGroupedParts(parts) {
  const firstValue = Object.values(parts)[0];
  return typeof firstValue === "object" && firstValue !== null;
}

// Rounds away float noise from a subtraction (e.g. 878.85 - 320.14 landing
// on 558.70999999999998) before it's ever displayed -- everything in this
// table is already at most 2 decimal places, so a diff should be too.
function round2(value) {
  return Math.round(value * 100) / 100;
}

// Appends one <td> for a single comparison cell: `value` formatted via
// `formatValue` (a column/row with no reading at all is treated as, and
// displayed as, 0 -- not blank -- since "this build strategy doesn't need
// this ware" and "needs zero of this ware" are the same fact), plus --
// only when `showDiff` is true (this column isn't the baseline itself,
// and the table currently has a baseline at all; see
// wareCostListHasBaseline) -- a trailing "(raw diff, percent diff)"
// annotation against `baselineValue`, the Active List's own value in this
// same row (likewise treated as 0 when absent). Green for an increase,
// red for a decrease, the default text color for no change; the
// percentage alone falls back to "N/A" when the (possibly zero-resolved)
// baseline is exactly 0, since dividing by it isn't meaningful even
// though the raw diff still is.
function appendComparisonCell(tr, value, baselineValue, showDiff, formatValue) {
  const td = document.createElement("td");
  const resolvedValue = value === undefined ? 0 : value;
  td.textContent = formatValue(resolvedValue);

  if (showDiff) {
    const resolvedBaseline = baselineValue === undefined ? 0 : baselineValue;
    const diffSpan = document.createElement("span");
    diffSpan.className = "ware-cost-list-diff";

    const rawDiff = round2(resolvedValue - resolvedBaseline);
    const sign = rawDiff > 0 ? "+" : "";
    const rawText = `${sign}${formatValue(rawDiff)}`;
    const pctText = resolvedBaseline === 0 ? "N/A" : `${sign}${((rawDiff / resolvedBaseline) * 100).toFixed(1)}%`;

    diffSpan.classList.add(
      rawDiff > 0 ? "ware-cost-list-diff-up" : rawDiff < 0 ? "ware-cost-list-diff-down" : "ware-cost-list-diff-none",
    );
    diffSpan.textContent = `(${rawText}, ${pctText})`;
    td.appendChild(diffSpan);
  }

  tr.appendChild(td);
}

// Appends one <tr> per ware across the union of all columns' ware_ids
// (sorted) -- `partsByColumn` is one flat ware_id -> amount map per
// column, in the same order as wareCostListColumns()'s current result,
// with `null` marking a column that doesn't have this tier/method/category
// at all. A column simply missing a given ware (whether its whole parts
// map is null, or it just doesn't happen to need that particular ware)
// displays and diffs as 0 -- see appendComparisonCell() for both that and
// the diff annotation every non-baseline column also gets.
function appendWarePartRows(partsByColumn) {
  const wareIds = new Set();
  for (const parts of partsByColumn) {
    if (parts) for (const wareId of Object.keys(parts)) wareIds.add(wareId);
  }

  for (const wareId of [...wareIds].sort()) {
    const tr = document.createElement("tr");
    const wareTd = document.createElement("td");
    wareTd.textContent = wareId;
    tr.appendChild(wareTd);

    const baselineValue = wareCostListHasBaseline ? partsByColumn[0]?.[wareId] : undefined;

    partsByColumn.forEach((parts, index) => {
      const value = parts ? parts[wareId] : undefined;
      const showDiff = wareCostListHasBaseline && index !== 0;
      appendComparisonCell(tr, value, baselineValue, showDiff, String);
    });

    wareCostListBody.appendChild(tr);
  }
}

// Collapse state for the Ware Cost List's up to 2 nesting layers (tier ->
// category; a 3rd, ware-level layer is planned but intentionally not built
// yet). Declared outside renderWareCostList() so it survives every
// re-render (recalculation, tab switch, adding/removing a comparison
// column) instead of resetting to all-expanded each time. Keys are
// "|"-joined and increasingly specific -- a category's key embeds its tier
// ("raw_materials|engine") -- so collapsing one section never needs to
// know or care about any other. Shared across both tabs *and* every column
// (neither the "total"/"component_type" split nor which fleet list a
// column represents appears in the key), since a tier/category means the
// same thing regardless of which column happens to have data for it.
const collapsedWareCostListSections = new Set();

// Renders one collapsible header row (tier, method, or category), spanning
// every column -- always visible itself, an arrow (▼ expanded / ▶
// collapsed) prefixes `labelHtml`. Clicking anywhere in the row toggles
// `key` in collapsedWareCostListSections and re-renders from cached data
// (a pure client-side redraw, never a new request). Returns whether this
// section is currently collapsed, so the caller can skip rendering its
// children entirely instead of rendering-then-hiding them.
//
// Split into two cells -- a first, single-column label cell plus a second
// cell spanning the rest (`colSpan - 1`) -- rather than one cell spanning
// all `colSpan` columns: a <td> whose own colSpan already covers the
// table's *entire* width doesn't reliably freeze via `position: sticky`
// in browsers (that only works for a genuinely narrower, first-of-several
// cell) -- which is exactly the pattern the ware/price label column
// already uses successfully. Splitting lets the label cell freeze the
// same proven way; the second cell exists purely so the row's background
// still covers every column instead of stopping at the label.
function appendCollapsibleHeader(key, labelHtml, extraClass, colSpan) {
  const isCollapsed = collapsedWareCostListSections.has(key);

  const row = document.createElement("tr");
  const toggle = () => {
    if (collapsedWareCostListSections.has(key)) {
      collapsedWareCostListSections.delete(key);
    } else {
      collapsedWareCostListSections.add(key);
    }
    renderWareCostList();
  };
  row.addEventListener("click", toggle);

  const labelCell = document.createElement("td");
  labelCell.className = `ware-cost-list-collapsible ${extraClass}`;
  labelCell.innerHTML = `<span class="ware-cost-list-arrow">${isCollapsed ? "▶" : "▼"}</span> ${labelHtml}`;
  row.appendChild(labelCell);

  if (colSpan > 1) {
    const fillerCell = document.createElement("td");
    fillerCell.colSpan = colSpan - 1;
    fillerCell.className = `${extraClass} ware-cost-list-collapsible-filler`;
    row.appendChild(fillerCell);
  }

  wareCostListBody.appendChild(row);

  return isCollapsed;
}

// Looks up one column's summarize() result for a given tier
// ("raw_materials"/"production_wares") under the currently active tab --
// null if that column has no data for it at all (shouldn't normally
// happen, but guards against a hand-edited or unexpected snapshot).
function tierResultForColumn(column, tierKey) {
  return column.data?.[activeWareCostListTab]?.[tierKey] ?? null;
}

// A tier heading row (collapsible, spanning every column) followed by its
// ware/category rows -- shared by the raw-materials and production-wares
// tiers below. `tierKey` is also this tier's own collapse-state key (and,
// in turn, its categories' -- see categoryKey below).
//
// summarize_production.py's summarize() now resolves to at most one build
// method per column (see its own module docstring), so there's no more
// per-method row grouping here: each column just contributes its own
// single method's data directly, compared ware-by-ware on the same row
// regardless of which method it happened to resolve to -- comparing
// different build methods now means comparing different *columns* (each
// with its own "Priority: ..." button/modal -- see renderWareCostListHead()),
// not separate method sections stacked inside one column.
function appendWareCostListTier(tierKey, heading, columns) {
  const totalColumns = columns.length + 1;
  const tierCollapsed = appendCollapsibleHeader(tierKey, heading, "ware-cost-list-tier-title", totalColumns);
  if (tierCollapsed) return;

  const dataByColumn = columns.map((column) => {
    const tierResult = tierResultForColumn(column, tierKey);
    return tierResult?.parts ? tierResult : null;
  });

  const sampleData = dataByColumn.find((data) => data != null);
  if (!sampleData) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = totalColumns;
    td.textContent = "No wares required.";
    tr.appendChild(td);
    wareCostListBody.appendChild(tr);
    return;
  }

  // Every column computes group_by_component_type the same way for a
  // given tab (see recomputeDirtyFleets()), so whichever column actually
  // has data decides whether it's grouped -- they never legitimately
  // disagree.
  const grouped = isGroupedParts(sampleData.parts);

  if (grouped) {
    const categoryNames = new Set();
    for (const data of dataByColumn) {
      if (data) for (const category of Object.keys(data.parts)) categoryNames.add(category);
    }

    for (const category of sortCategoriesForDisplay(categoryNames)) {
      const categoryKey = `${tierKey}|${category}`;
      const categoryCollapsed = appendCollapsibleHeader(
        categoryKey,
        WARE_COST_LIST_CATEGORY_LABELS[category] ?? category,
        "ware-cost-list-category-row",
        totalColumns,
      );
      if (categoryCollapsed) continue;
      appendWarePartRows(dataByColumn.map((data) => data?.parts?.[category] ?? null));
    }
  } else {
    appendWarePartRows(dataByColumn.map((data) => data?.parts ?? null));
  }
}

// One column per fleet in `fleets`, active fleet always sorted first (see
// module comment on wareCostListHasBaseline for why: the diff/highlight
// machinery elsewhere hardcodes "column 0 is the baseline", so sorting here
// is simpler than teaching that machinery about activeFleetIndex directly).
function wareCostListColumns() {
  const order = [activeFleetIndex, ...fleets.map((_, i) => i).filter((i) => i !== activeFleetIndex)];
  return order.map((fleetIndex) => ({ data: fleets[fleetIndex].wareCostList, fleetIndex }));
}

// The two-row <thead>: a "List Name" row with one column per fleet, each
// rendered via the exact same buildFleetTabButton() the Fleet Planner's
// own tab bar uses (same ship icon/color/box, same click-to-switch --
// setActiveFleet()), plus its Build Focus line (see openBuildMethodModal())
// since that's otherwise only ever reachable from here; then a plain
// "Ware"/"Amount" x N column-header row underneath -- switching which
// fleet is active is entirely the name row's job now, so this row no
// longer needs its own "Set Active" button. Rebuilt on every render since
// the column count/order can change.
function renderWareCostListHead(columns) {
  wareCostListThead.innerHTML = "";

  const nameRow = document.createElement("tr");
  nameRow.className = "ware-cost-list-name-row";
  const nameLabelTh = document.createElement("th");
  nameLabelTh.textContent = "List Name";
  nameRow.appendChild(nameLabelTh);
  for (const column of columns) {
    const th = document.createElement("th");
    th.appendChild(buildFleetTabButton(fleets[column.fleetIndex], column.fleetIndex, { showBuildPriority: true }));
    nameRow.appendChild(th);
  }
  wareCostListThead.appendChild(nameRow);

  const columnHeaderRow = document.createElement("tr");
  const wareTh = document.createElement("th");
  wareTh.textContent = "Ware";
  columnHeaderRow.appendChild(wareTh);
  for (const column of columns) {
    const th = document.createElement("th");
    th.textContent = "Amount";
    columnHeaderRow.appendChild(th);
  }
  wareCostListThead.appendChild(columnHeaderRow);
}

// Appends one row per price key (Min/Average/Max) across all columns --
// `priceDataByColumn` is one {total_min, total_avg, total_max,
// missing_prices} object per column (or null if that column/category/
// price type doesn't have price data here), in the same order as
// wareCostListColumns()'s current result -- i.e. the price-tier
// counterpart of appendWarePartRows(), with three fixed rows ("as if they
// were wares", per how this feature was asked for) instead of one row per
// ware_id. No label prefix any more -- every caller (Market Purchase
// Price, Production Wares Price, Raw Materials Price) now wraps its own
// call in a collapsible title header of its own (see appendMoneyTier()/
// appendMoneyTopLevelEntry()) that already says what these rows are. A
// column missing price data entirely displays and diffs as 0, same
// convention as a missing ware amount.
const PRICE_COMPARISON_ROWS = [
  { label: "Min Price", key: "total_min" },
  { label: "Average Price", key: "total_avg" },
  { label: "Max Price", key: "total_max" },
];

function formatPriceValue(value) {
  return `${value.toLocaleString()} Cr`;
}

function appendPriceRows(priceDataByColumn) {
  for (const { label, key } of PRICE_COMPARISON_ROWS) {
    const tr = document.createElement("tr");
    const labelTd = document.createElement("td");
    labelTd.textContent = label;
    tr.appendChild(labelTd);

    const baselineValue = wareCostListHasBaseline ? priceDataByColumn[0]?.[key] : undefined;

    priceDataByColumn.forEach((priceData, index) => {
      const value = priceData ? priceData[key] : undefined;
      const showDiff = wareCostListHasBaseline && index !== 0;
      appendComparisonCell(tr, value, baselineValue, showDiff, formatPriceValue);
    });

    wareCostListBody.appendChild(tr);
  }

  // One extra row noting any columns with wares excluded from their own
  // total for lack of price data -- shown once per price type per
  // category (not once per Min/Avg/Max row, which would triple it up), and
  // only when at least one column actually has any.
  if (priceDataByColumn.some((priceData) => priceData && priceData.missing_prices.length > 0)) {
    const tr = document.createElement("tr");
    const labelTd = document.createElement("td");
    labelTd.className = "ware-cost-list-price-missing-label";
    labelTd.textContent = "Missing price data";
    tr.appendChild(labelTd);

    for (const priceData of priceDataByColumn) {
      const valueTd = document.createElement("td");
      valueTd.className = "ware-cost-list-price-missing";
      const missing = priceData?.missing_prices ?? [];
      if (missing.length > 0) {
        valueTd.textContent = missing.join(", ");
        valueTd.title = `${missing.length} ware(s) excluded from this total for lack of price data`;
      } else {
        valueTd.textContent = "—";
      }
      tr.appendChild(valueTd);
    }

    wareCostListBody.appendChild(tr);
  }
}

// The Money tier's "Market Purchase Price" entry -- the top-level (no
// build-method dependency) price data, shown once at the top of the Money
// tier rather than repeated under every method, since it doesn't vary by
// method at all. Collapsible like everything else, with its own stable
// key ("money|top_level") independent of any real method name. Renders
// nothing at all (not even a header) if no column has top-level price
// data, matching the rest of this table's "omit empty sections" pattern.
function appendMoneyTopLevelEntry(columns) {
  const totalColumns = columns.length + 1;
  const topLevelByColumn = columns.map((column) => tierResultForColumn(column, "top_level_price"));
  if (topLevelByColumn.every((data) => data == null)) return;

  const key = "money|top_level";
  const collapsed = appendCollapsibleHeader(key, "Market Purchase Price", "ware-cost-list-method-row", totalColumns);
  if (collapsed) return;

  // Same flat-vs-grouped distinction as everywhere else in this table:
  // "total_min" is never itself a legitimate category name.
  const sample = topLevelByColumn.find((data) => data != null);
  const grouped = sample ? !("total_min" in sample) : false;

  if (grouped) {
    const categoryNames = new Set();
    for (const data of topLevelByColumn) {
      if (data) for (const category of Object.keys(data)) categoryNames.add(category);
    }
    for (const category of sortCategoriesForDisplay(categoryNames)) {
      const categoryKey = `${key}|${category}`;
      const categoryCollapsed = appendCollapsibleHeader(
        categoryKey,
        WARE_COST_LIST_CATEGORY_LABELS[category] ?? category,
        "ware-cost-list-category-row",
        totalColumns,
      );
      if (categoryCollapsed) continue;
      appendPriceRows(topLevelByColumn.map((data) => data?.[category] ?? null));
    }
  } else {
    appendPriceRows(topLevelByColumn);
  }
}

// One price type's own title row (collapsible, same pattern as every
// other section in this table) -- Min/Average/Max rows directly when not
// grouped by category, or one collapsible category sub-header (nested one
// level deeper still -- see .ware-cost-list-category-row) per category
// otherwise, each with its own Min/Average/Max rows underneath. Price type
// is the *outer* grouping and category the *inner* one here -- "what this
// is" before "broken down by component type", matching
// appendWareCostListTier()/appendMoneyTopLevelEntry()'s own nesting.
// Shared by Production Wares Price and Raw Materials Price in
// appendMoneyTier() below. `key` must already be unique within the Money
// tier's own collapse-state namespace (see its caller); `grouped` is
// passed in rather than sniffed from `dataByColumn` itself, since one
// price type can legitimately have no data at all (nothing null to sniff
// a shape from) while the other does -- both always share the same
// grouping mode regardless (one flag per tab, see runCalculation()).
function appendPriceTypeSection(key, label, dataByColumn, grouped, totalColumns) {
  const collapsed = appendCollapsibleHeader(key, label, "ware-cost-list-method-row", totalColumns);
  if (collapsed) return;

  if (!grouped) {
    appendPriceRows(dataByColumn);
    return;
  }

  const categoryNames = new Set();
  for (const data of dataByColumn) {
    if (data) for (const category of Object.keys(data)) categoryNames.add(category);
  }
  for (const category of sortCategoriesForDisplay(categoryNames)) {
    const categoryKey = `${key}|${category}`;
    const categoryCollapsed = appendCollapsibleHeader(
      categoryKey,
      WARE_COST_LIST_CATEGORY_LABELS[category] ?? category,
      "ware-cost-list-category-row",
      totalColumns,
    );
    if (categoryCollapsed) continue;
    appendPriceRows(dataByColumn.map((data) => data?.[category] ?? null));
  }
}

// The unified Money tier: one collapsible section covering all monetary
// information -- Market Purchase Price (top-level, build-method
// independent) first, then Production Wares Price and Raw Materials Price
// for each column's own single resolved build method (see
// summarize_production.py's module docstring -- summarize() resolves to
// at most one method per column now), each its own titled sub-section (see
// appendPriceTypeSection() above, price type outer/category inner) rather
// than a per-build-method row group -- comparing different build methods
// means comparing different *columns* now (each with its own "Build
// Focus: ..." button/modal -- see renderWareCostListHead()), same
// reasoning as appendWareCostListTier(). Replaces what used to be two
// separate price tiers interleaved with the ware tiers, so there are only
// 3 top-level sections in this table now: Money, Production Wares, Raw
// Materials.
function appendMoneyTier(columns) {
  const totalColumns = columns.length + 1;
  const tierCollapsed = appendCollapsibleHeader("money", "Credit Cost", "ware-cost-list-tier-title", totalColumns);
  if (tierCollapsed) return;

  appendMoneyTopLevelEntry(columns);

  const rawDataByColumn = columns.map((column) => tierResultForColumn(column, "raw_materials_price"));
  const productionDataByColumn = columns.map((column) => tierResultForColumn(column, "production_wares_price"));

  if (rawDataByColumn.every((data) => data == null) && productionDataByColumn.every((data) => data == null)) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = totalColumns;
    td.textContent = "No wares required.";
    tr.appendChild(td);
    wareCostListBody.appendChild(tr);
    return;
  }

  const grouped = activeWareCostListTab === "component_type";
  appendPriceTypeSection("money|production", "Production Wares Price", productionDataByColumn, grouped, totalColumns);
  appendPriceTypeSection("money|raw", "Raw Materials Price", rawDataByColumn, grouped, totalColumns);
}

// Money at the top, then the two fixed, always-shown ware depths (see
// RAW_MATERIALS_SEARCH_DEPTH/PRODUCTION_WARES_SEARCH_DEPTH) -- production
// wares (the shallow, "what the shipyard directly consumes" view) first,
// then raw materials (the deepest, "build everything from scratch" view)
// -- one column per fleet in `fleets`. Reads wareCostListColumns()/
// activeWareCostListTab directly rather than taking parameters, since it's
// invoked from several unrelated places (a fresh calculation, a tab switch,
// a collapse toggle, switching/deleting a fleet) that all just want
// "redraw with whatever the current state is".
function renderWareCostList() {
  // renderFleetListTabs() is not called here -- renderCart() already keeps
  // the tab bar in sync on every fleet mutation/switch; calling it again
  // here would just be redundant work on every recompute.
  const columns = wareCostListColumns(); // always >= 1 -- `fleets` is never empty
  wareCostListSection.classList.remove("hidden");

  renderWareCostListHead(columns);
  wareCostListBody.innerHTML = "";

  appendMoneyTier(columns);
  appendWareCostListTier(
    "production_wares",
    "Production Wares (buy what the shipyard directly consumes)",
    columns,
  );
  appendWareCostListTier("raw_materials", "Raw Materials (build everything from scratch)", columns);
  saveState();
}

// --- Fleet lists / tab bar --------------------------------------------
// Display-only fallback for a fleet's tab/column label when its name is
// blank -- never persisted as a real name, just labels the UI.
const DEFAULT_NEW_FLEET_LABEL = "New Fleet";

// Picks "New Fleet", "New Fleet 2", "New Fleet 3", ... -- the first label
// not already used by an existing fleet, so two fleets created back-to-back
// via "+" are always visually distinguishable in the tab bar.
function nextNewFleetName() {
  const existingNames = new Set(fleets.map((fleet) => fleet.name.trim()));
  if (!existingNames.has(DEFAULT_NEW_FLEET_LABEL)) return DEFAULT_NEW_FLEET_LABEL;
  let n = 2;
  while (existingNames.has(`${DEFAULT_NEW_FLEET_LABEL} ${n}`)) n += 1;
  return `${DEFAULT_NEW_FLEET_LABEL} ${n}`;
}

// Switches which fleet is active -- no confirmation, no copying, since
// every fleet is always live and directly editable. resetShipPicker() is
// required here (not optional): editingIndex numerically indexes the
// previously active fleet's cart, and would otherwise silently corrupt an
// unrelated entry in the newly active fleet at the same index.
function setActiveFleet(fleetIndex) {
  if (fleetIndex === activeFleetIndex) return;
  activeFleetIndex = fleetIndex;
  resetShipPicker();
  renderCart();
  renderWareCostList();
}

// Deletes a fleet outright -- real data loss, unlike switching, so this
// keeps a confirm() (same category as clearImportedLoadouts()'s). Reachable
// both from the tab bar and the Ware Cost List's own column header.
function deleteFleet(fleetIndex) {
  if (fleets.length <= 1) return;
  const fleet = fleets[fleetIndex];
  if (!confirm(`Delete fleet list "${fleet.name.trim() || DEFAULT_NEW_FLEET_LABEL}"? This cannot be undone.`)) return;

  fleets.splice(fleetIndex, 1);
  if (fleetIndex === activeFleetIndex) {
    activeFleetIndex = Math.min(fleetIndex, fleets.length - 1);
    resetShipPicker();
  } else if (fleetIndex < activeFleetIndex) {
    activeFleetIndex -= 1;
  }
  renderCart();
  renderWareCostList();
}

cartNameInput.addEventListener("input", () => {
  activeFleet().name = cartNameInput.value;
  renderFleetListTabs();
  saveState();
});

// One bracket per corner around the active tab's ship icon -- see
// buildFleetTabShipIcon(). All 4 corners share one source image
// (selection_box_corner.png, generate_nav_icons.py's crop of just one
// corner of the game's own selection frame) since that source is
// perfectly symmetric under rotation; each corner just rotates it into
// place via its own CSS class.
const SELECTION_BOX_CORNER_CLASSES = [
  "fleet-list-tab-selection-corner top-left",
  "fleet-list-tab-selection-corner top-right",
  "fleet-list-tab-selection-corner bottom-right",
  "fleet-list-tab-selection-corner bottom-left",
];

// A tab's own leading ship icon -- the fleet's first cart entry's ship
// class, tinted the game's own "faction_player" green (see
// generate_nav_icons.py's PLAYER_GREEN/PLAYER_GREEN_HIGHLIGHT), matching
// how the map colors a player-owned icon. The active fleet's tab gets the
// brighter "currently here" tint plus 4 corner brackets (the game's own
// "selected map item" indicator, from widget/bordersquare.gz -- rendered
// in-game as 4 floating corner brackets, not a solid connected outline, so
// that's what's reproduced here too) -- every other tab just gets the
// plain tint, no brackets.
function buildFleetTabShipIcon(icon, isActive) {
  const wrap = document.createElement("span");
  wrap.className = "fleet-list-tab-ship-icon-wrap";

  if (isActive) {
    for (const cornerClass of SELECTION_BOX_CORNER_CLASSES) {
      const corner = document.createElement("img");
      corner.src = "/images/nav_icons/selection_box_corner.png";
      corner.alt = "";
      corner.className = cornerClass;
      wrap.appendChild(corner);
    }
  }

  const img = document.createElement("img");
  img.src = `/images/nav_icons/${isActive ? "player_location" : "fleet_tab"}/${icon}.png`;
  img.alt = "";
  img.className = "fleet-list-tab-ship-icon";
  wrap.appendChild(img);

  return wrap;
}

// One fleet's own tab button -- ship icon (see buildFleetTabShipIcon()),
// name, an optional Build Method Priority line underneath the name (see
// showBuildPriority below), and a delete "×" (unless only one fleet
// remains). Clicking anywhere on the button switches to that fleet via
// setActiveFleet(); the two sub-controls (priority, "×") each stop that
// click from bubbling so they act independently of the tab-switch. Shared
// by both renderFleetListTabs() (the Fleet Planner's own tab bar) and
// renderWareCostListHead() (the Ware Cost List's column headers) so a
// fleet looks and behaves identically -- same icon/color/box/click-to-
// switch -- in both places; the Ware Cost List is the only one of the two
// that needs the priority line, since that's the only place it's
// otherwise ever set (see openBuildMethodModal()).
function buildFleetTabButton(fleet, fleetIndex, { showBuildPriority = false } = {}) {
  const isActive = fleetIndex === activeFleetIndex;
  const tab = document.createElement("button");
  tab.type = "button";
  tab.className = isActive ? "fleet-list-tab-btn active" : "fleet-list-tab-btn";
  tab.addEventListener("click", () => setActiveFleet(fleetIndex));

  const firstShipIcon = fleet.cart[0]?.shipIcon;
  if (firstShipIcon) tab.appendChild(buildFleetTabShipIcon(firstShipIcon, isActive));

  const nameStack = document.createElement("span");
  nameStack.className = "fleet-list-tab-name-stack";
  nameStack.appendChild(document.createTextNode(fleet.name.trim() || DEFAULT_NEW_FLEET_LABEL));

  if (showBuildPriority) {
    // fleet.buildMethodPriority null means "use the server's own default"
    // (DEFAULT_BUILD_METHOD_PRIORITY -- see summarize_production.py), whose
    // own top entry is allBuildMethods[0] -- so this button should always
    // name a real method, never the literal word "default".
    const topPriority = fleet.buildMethodPriority?.[0] ?? allBuildMethods[0];
    const priorityBtn = document.createElement("button");
    priorityBtn.type = "button";
    priorityBtn.className = "ware-cost-list-build-focus-btn";
    priorityBtn.appendChild(document.createTextNode("Priority: "));
    const priorityNameSpan = document.createElement("span");
    applyBuildMethodColor(priorityNameSpan, topPriority);
    priorityNameSpan.textContent = topPriority ?? "default";
    priorityBtn.appendChild(priorityNameSpan);
    priorityBtn.title = "Set this list's build method priority";
    priorityBtn.addEventListener("click", (event) => {
      event.stopPropagation();
      openBuildMethodModal({ fleetIndex, buildMethodPriority: fleet.buildMethodPriority });
    });
    nameStack.appendChild(priorityBtn);
  }
  tab.appendChild(nameStack);

  if (fleets.length > 1) {
    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "fleet-list-tab-remove-btn";
    removeBtn.textContent = "×";
    removeBtn.title = "Delete this fleet list";
    removeBtn.addEventListener("click", (event) => {
      event.stopPropagation();
      deleteFleet(fleetIndex);
    });
    tab.appendChild(removeBtn);
  }

  return tab;
}

// The Fleet Lists section's own tab bar (styled like the top page nav --
// see .fleet-list-tabs/.fleet-list-tab-btn) -- one tab per fleet in
// `fleets`, in order (see buildFleetTabButton()), plus a trailing "+" to
// create a new one.
function renderFleetListTabs() {
  fleetListTabsEl.innerHTML = "";

  fleets.forEach((fleet, index) => {
    fleetListTabsEl.appendChild(buildFleetTabButton(fleet, index));
  });

  const addBtn = document.createElement("button");
  addBtn.type = "button";
  addBtn.className = "fleet-list-tab-add-btn";
  addBtn.textContent = "+";
  addBtn.title = "New fleet list";
  addBtn.addEventListener("click", () => {
    fleets.push(makeFleet(nextNewFleetName()));
    activeFleetIndex = fleets.length - 1;
    resetShipPicker();
    renderCart();
  });
  fleetListTabsEl.appendChild(addBtn);
}

// --- Analysis download / upload -------------------------------------------
// Unlike "Download Fleet List…" below (summarize_production.py's CLI input
// shape, for portability outside this app, one fleet at a time), this
// captures every fleet in `fleets` as one file, so the whole comparison
// table can be closed and reopened later with nothing lost. It
// intentionally serializes this app's own internal `cart` array shape
// directly (the same {shipWareId, wares_list, selections, ...} entries),
// not the CLI-compatible {count, wares_list} shape -- there's no need for
// CLI portability here, and doing so avoids reconstructCartEntry()'s lossy
// re-derivation (ambiguous group matching, etc.) entirely.
//
// Deliberately excludes each fleet's cached wareCostList/dirty -- those are
// a cache, not source of truth -- so every restored fleet comes back
// dirty: true and recomputes fresh the next time Cost Analysis is visited.

// The full multi-fleet snapshot shape shared by Download Analysis, Upload
// Analysis, and the "Fleet Lists" share section (see SHARE_SECTIONS) --
// deliberately excludes each fleet's cached wareCostList/dirty flag (a
// cache, not source of truth), so restoring/sharing a set of fleets always
// recomputes fresh rather than carrying over possibly-stale numbers.
function buildAnalysisPayload() {
  return {
    fleets: fleets.map((fleet) => ({
      name: fleet.name,
      cart: JSON.parse(JSON.stringify(fleet.cart)),
      build_method_priority: fleet.buildMethodPriority,
    })),
    active_fleet_index: activeFleetIndex,
  };
}

// Validates and applies an analysis payload (see buildAnalysisPayload())
// onto `fleets`/`activeFleetIndex`, replacing everything currently there --
// confirms first if there's anything real to lose. Shared by Upload
// Analysis and the "Fleet Lists" share section, so a shared or uploaded set
// of fleets restores identically either way. Returns true if applied,
// false if the payload was invalid or the user declined the confirm.
function applyAnalysisPayload(data) {
  if (!data || !Array.isArray(data.fleets) || data.fleets.some((fleet) => !Array.isArray(fleet.cart))) {
    alert('This doesn\'t look like a valid analysis (missing a "fleets" array of {cart, ...} entries).');
    return false;
  }

  if (
    fleets.some((fleet) => fleet.cart.length > 0) &&
    !confirm("Loading will replace all of your current fleet lists. Continue?")
  ) {
    return false;
  }

  fleets = data.fleets.map((fleet) => ({
    name: fleet.name || "",
    cart: JSON.parse(JSON.stringify(fleet.cart)),
    buildMethodPriority: fleet.build_method_priority ?? null,
    wareCostList: null,
    dirty: true,
  }));
  if (fleets.length === 0) fleets = [makeFleet()];
  activeFleetIndex = Math.min(Math.max(data.active_fleet_index ?? 0, 0), fleets.length - 1);

  resetShipPicker();
  renderCart();
  return true;
}

downloadAnalysisBtn.addEventListener("click", () => {
  if (fleets.every((fleet) => fleet.cart.length === 0)) {
    alert("Nothing to download -- every fleet list is empty.");
    return;
  }

  const analysis = buildAnalysisPayload();
  const blob = new Blob([JSON.stringify(analysis, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  // The dedicated analysis-file-name-input, when set, always wins over the
  // active fleet's own name -- it exists specifically so this
  // download's filename can differ from (and outlive renames of) that fleet.
  const fileNameOverride = analysisFileNameInput.value.trim();
  const baseFileName = fileNameOverride || activeFleet().name.trim() || "x4_analysis";
  link.download = `${baseFileName.replace(/[^a-z0-9_-]+/gi, "_")}.json`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
});

uploadAnalysisInput.addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;

  let data;
  try {
    data = JSON.parse(await file.text());
  } catch (err) {
    alert(`Could not parse file: ${err.message}`);
    event.target.value = "";
    return;
  }

  applyAnalysisPayload(data);
  event.target.value = ""; // allow re-selecting the same file later
});

// --- Share links -------------------------------------------------------------
// Each of these 3 slices of state can be shared independently (a user might
// share fleets but not their price overrides, say) -- see api.py's own
// ShareSection Literal, which this list's `section` values must keep
// matching exactly, and the URL shape (?share_<section>=<uuid>, one per
// included section) applyShareLinksFromUrl() below reads back. `checkbox`
// is looked up once here since every one of these already exists in the
// DOM from page load (unlike the fleet tabs, this isn't rebuilt per render).
const SHARE_SECTIONS = [
  {
    section: "fleets",
    label: "Fleet Lists",
    checkbox: document.getElementById("share-option-fleets"),
    hasContent: () => fleets.some((fleet) => fleet.cart.length > 0),
    buildPayload: buildAnalysisPayload,
    applyPayload: applyAnalysisPayload,
  },
  {
    section: "price_overrides",
    label: "Ware Price Overrides",
    checkbox: document.getElementById("share-option-price_overrides"),
    hasContent: () => Object.keys(priceOverrides).length > 0,
    buildPayload: () => ({ ...priceOverrides }),
    applyPayload: (data) => {
      if (!data || typeof data !== "object") return false;
      if (
        Object.keys(priceOverrides).length > 0 &&
        !confirm("Loading will replace your current ware price overrides. Continue?")
      ) {
        return false;
      }
      for (const key of Object.keys(priceOverrides)) delete priceOverrides[key];
      Object.assign(priceOverrides, data);
      renderPriceOverrideSummary();
      markAllFleetsDirtyAndRecompute();
      return true;
    },
  },
  {
    section: "loadouts",
    label: "Ship Loadouts",
    checkbox: document.getElementById("share-option-loadouts"),
    hasContent: () => !!importedLoadoutsResult && importedLoadoutsResult.ships.length > 0,
    // The saved/imported-loadouts working set is already an additive,
    // never-overwriting concept everywhere else it's touched (Import Game
    // Loadouts, Import Raw XML Loadout, Add To Saved Loadouts all merge via
    // this same function) -- shared loadouts merge the same way, on
    // purpose, rather than introducing a one-off "replace" behavior just
    // for this entry point.
    buildPayload: () => importedLoadoutsResult,
    applyPayload: (data) => {
      if (!data || !Array.isArray(data.ships)) return false;
      mergeImportedLoadoutsResult(data);
      return true;
    },
  },
];

// {section: {hash, uuid}} of the most recently generated share per section
// -- see generateShareLink() below. Persisted (see saveState()) so
// re-sharing unchanged data, even in a later session, still reuses the
// same link instead of writing a redundant duplicate into Tigris every
// time. hash is stableStringify() of that section's own buildPayload()
// result -- order-independent, so key-insertion-order differences alone
// (e.g. price overrides added in a different order) don't count as a
// change.
let shareCache = {};

function showShareModalStatus(lines, isError) {
  shareModalStatus.innerHTML = "";
  for (const line of lines) {
    const div = document.createElement("div");
    div.textContent = line;
    shareModalStatus.appendChild(div);
  }
  shareModalStatus.classList.toggle("hidden", lines.length === 0);
  shareModalStatus.classList.toggle("status-error", !!isError);
}

function openShareModal() {
  for (const entry of SHARE_SECTIONS) {
    const has = entry.hasContent();
    entry.checkbox.checked = has;
    entry.checkbox.disabled = !has;
  }
  shareModalResult.classList.add("hidden");
  showShareModalStatus([], false);
  shareModalOverlay.classList.remove("hidden");
}

async function generateShareLink() {
  const checkedSections = SHARE_SECTIONS.filter((entry) => entry.checkbox.checked);
  if (checkedSections.length === 0) {
    showShareModalStatus(["Check at least one section to share."], true);
    return;
  }

  shareModalGenerateBtn.disabled = true;
  showShareModalStatus(["Generating…"], false);
  try {
    const params = new URLSearchParams();
    for (const entry of checkedSections) {
      const payload = entry.buildPayload();
      const hash = stableStringify(payload);
      const cached = shareCache[entry.section];
      let uuid = cached && cached.hash === hash ? cached.uuid : null;

      if (!uuid) {
        const response = await fetch(`/api/share/${entry.section}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ data: payload }),
        });
        const result = await response.json();
        if (result.error) {
          showShareModalStatus([`Could not share ${entry.label}: ${result.error}`], true);
          return;
        }
        uuid = result.uuid;
        shareCache[entry.section] = { hash, uuid };
        saveState();
      }
      params.set(`share_${entry.section}`, uuid);
    }

    shareModalResultInput.value = `${location.origin}${location.pathname}?${params.toString()}`;
    shareModalResult.classList.remove("hidden");
    showShareModalStatus([], false);
  } catch (err) {
    showShareModalStatus([`Could not generate share link: ${err.message}`], true);
  } finally {
    shareModalGenerateBtn.disabled = false;
  }
}

headerShareBtn.addEventListener("click", openShareModal);
shareModalCancelBtn.addEventListener("click", () => shareModalOverlay.classList.add("hidden"));
shareModalGenerateBtn.addEventListener("click", generateShareLink);

shareModalCopyBtn.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(shareModalResultInput.value);
    showShareModalStatus(["Copied!"], false);
  } catch {
    // Clipboard API unavailable or permission denied (e.g. non-HTTPS,
    // an older browser, or a blocked permission) -- select the text so
    // the user can still copy it manually (Ctrl/Cmd+C).
    shareModalResultInput.select();
    showShareModalStatus(["Couldn't copy automatically -- text is selected, copy it manually."], true);
  }
});

// Reads ?share_<section>=<uuid> query params (see SHARE_SECTIONS/
// generateShareLink() above) and, for each present, fetches and applies
// that section -- called once from bootstrap(), after state has already
// been restored from localStorage, so each section's own applyPayload()
// (which may confirm() before overwriting) is judging against the user's
// real current data, not empty defaults. Strips the params from the URL
// afterward either way (applied, declined, or failed) so reloading the
// page doesn't re-prompt every time.
async function applyShareLinksFromUrl() {
  const params = new URLSearchParams(location.search);
  const present = SHARE_SECTIONS.filter((entry) => params.has(`share_${entry.section}`));
  if (present.length === 0) return;

  let anyApplied = false;
  for (const entry of present) {
    const shareUuid = params.get(`share_${entry.section}`);
    try {
      const response = await fetch(`/api/share/${entry.section}/${shareUuid}`);
      const result = await response.json();
      if (result.error) {
        alert(`Could not load shared ${entry.label}: ${result.error}`);
        continue;
      }
      if (entry.applyPayload(result.data)) anyApplied = true;
    } catch (err) {
      alert(`Could not load shared ${entry.label}: ${err.message}`);
    }
  }

  const url = new URL(location.href);
  for (const entry of present) url.searchParams.delete(`share_${entry.section}`);
  history.replaceState(null, "", url);

  if (anyApplied) saveState();
}

// --- Save / load ------------------------------------------------------------
// The saved file is shaped exactly like summarize_production.py's own input
// JSON (build_method_priority/search_depth/verbose/wares), plus two extra
// fields this UI adds on top -- cart_name, and each wares entry's own note
// -- which summarize_production.py itself ignores (extra keys are fine both
// for the CLI's json.load and for the API's Pydantic model), so the file is
// still also directly usable with the CLI tool.
// search_depth itself has no UI control any more (the Ware Cost List always
// shows both fixed depths -- see RAW_MATERIALS_SEARCH_DEPTH above), so the
// saved value is just that same fixed depth, purely for CLI compatibility.

saveCartBtn.addEventListener("click", () => {
  if (activeFleet().cart.length === 0) {
    alert("Fleet list is empty -- nothing to download.");
    return;
  }

  const cartName = cartNameInput.value.trim();

  const body = {
    cart_name: cartName || null,
    // build_method_priority is a field summarize_production.py's CLI
    // genuinely already reads (see this module's own docstring) -- not an
    // extra/ignored key, unlike cart_name/note.
    build_method_priority: activeFleet().buildMethodPriority,
    search_depth: RAW_MATERIALS_SEARCH_DEPTH,
    verbose: true,
    // note is extra (summarize_production.py's CLI ignores unknown keys,
    // same as cart_name above) -- carried along purely so re-uploading this
    // same file (loadCartInput's handler, via reconstructCartEntry())
    // restores it too. Omitted entirely rather than sent as "" when unset,
    // for a cleaner file.
    wares: activeFleet().cart.map((entry) => ({ count: entry.count, wares_list: entry.wares_list, note: entry.note || undefined })),
  };

  const blob = new Blob([JSON.stringify(body, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = cartName ? `${cartName.replace(/[^a-z0-9_-]+/gi, "_")}.json` : "x4_cart.json";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
});

// Rebuilds one cart entry from a saved {count, wares_list, note} configuration.
// wares_list only has raw {ware_id, amount} pairs -- it doesn't record which
// hardpoint group an equipment choice came from -- so this re-derives that:
// the first wares_list entry that resolves as a real ship (via the groups
// endpoint) is treated as the ship. A missile, drone, deployable,
// countermeasure, or crew ware_id (checked against the already-loaded
// allMissiles/allDrones/allDeployables/allCountermeasures/allCrew catalogs)
// is routed into missileAmounts/droneAmounts/deployableAmounts/
// countermeasureAmounts/crewAmounts rather than group-matching, since none
// of them are part of any group's options at all. Every other entry is matched to
// whichever of that ship's groups both accepts it and expects that exact
// amount (its slot_count). If a ware doesn't match any group or catalog
// (a hand-edited or foreign file), it's still kept in wares_list for
// calculation purposes, just shown with its raw ware_id instead of a
// resolved name, and that configuration's "Edit"
// won't be able to re-populate it into a picker. note (a sibling field of
// wares_list, not part of it) is a plain passthrough -- an older saved file
// without one just leaves it "".
async function reconstructCartEntry(config) {
  const waresList = config.wares_list;
  let shipItem = null;
  let shipData = null;

  for (const item of waresList) {
    const response = await fetch(`/api/ships/${encodeURIComponent(item.ware_id)}/groups`);
    const data = await response.json();
    if (!data.error) {
      shipItem = item;
      shipData = data;
      break;
    }
  }

  if (!shipData) {
    return {
      shipWareId: null,
      shipName: "(unrecognized fleet list entry)",
      shipIcon: null,
      missingRequiredComponents: [],
      note: config.note || "",
      count: config.count ?? 1,
      selections: {},
      missileAmounts: {},
      droneAmounts: {},
      deployableAmounts: {},
      countermeasureAmounts: {},
      crewAmounts: {},
      wares_list: waresList,
      displayItems: waresList.map((item) => ({ label: item.ware_id, amount: item.amount })),
    };
  }

  const selections = {};
  const missileAmountsResult = {};
  const droneAmountsResult = {};
  const deployableAmountsResult = {};
  const countermeasureAmountsResult = {};
  const crewAmountsResult = {};
  const displayItems = [{ label: shipData.name, amount: 1, category: "chassis" }];
  // Keyed by groupKey(), not raw group_name -- group_name alone isn't
  // unique (a dedicated shield shares its group_name with the group it
  // protects), so two entries can legitimately both match slot_count/
  // ware_id against different group_name-sharing groups at once.
  const usedGroupKeys = new Set();

  for (const item of waresList) {
    if (item === shipItem) continue;

    const missile = allMissiles.find((m) => m.ware_id === item.ware_id);
    if (missile) {
      missileAmountsResult[item.ware_id] = (missileAmountsResult[item.ware_id] ?? 0) + item.amount;
      displayItems.push({ label: missile.name, amount: item.amount, category: "missile" });
      continue;
    }

    const drone = allDrones.find((d) => d.ware_id === item.ware_id);
    if (drone) {
      droneAmountsResult[item.ware_id] = (droneAmountsResult[item.ware_id] ?? 0) + item.amount;
      displayItems.push({ label: drone.name, amount: item.amount, category: "drone" });
      continue;
    }

    const deployable = allDeployables.find((d) => d.ware_id === item.ware_id);
    if (deployable) {
      deployableAmountsResult[item.ware_id] = (deployableAmountsResult[item.ware_id] ?? 0) + item.amount;
      displayItems.push({ label: deployable.name, amount: item.amount, category: "deployable" });
      continue;
    }

    const countermeasure = allCountermeasures.find((c) => c.ware_id === item.ware_id);
    if (countermeasure) {
      countermeasureAmountsResult[item.ware_id] = (countermeasureAmountsResult[item.ware_id] ?? 0) + item.amount;
      displayItems.push({ label: countermeasure.name, amount: item.amount, category: "countermeasure" });
      continue;
    }

    // Both crew roles share one real ware_id (see CREW_ROLES/crewWareId's
    // own comment), so unlike missile/drone/deployable/countermeasure
    // above, a ware_id match alone can't tell Marine and Service Crew
    // apart -- only the category override saved alongside this item can
    // (the same mechanism a bonus M shield already relies on below). A
    // pre-existing saved cart with a bare "crew" ware_id and no such
    // category (from before this role split existed) falls through
    // unresolved here -- its cost still counts correctly (wares_list is
    // kept as-is regardless), it just won't re-populate into the crew
    // qty steppers on Edit.
    const role = item.ware_id === crewWareId ? CREW_CATEGORY_TO_ROLE[item.category] : undefined;
    if (role) {
      const crew = allCrew.find((c) => c.ware_id === role);
      crewAmountsResult[role] = (crewAmountsResult[role] ?? 0) + item.amount;
      displayItems.push({ label: crew.name, amount: item.amount, category: item.category });
      continue;
    }

    const matchedGroup = shipData.groups.find(
      (group) =>
        !usedGroupKeys.has(groupKey(group)) &&
        group.slot_count === item.amount &&
        group.options.some((option) => option.ware_id === item.ware_id),
    );

    if (matchedGroup) {
      usedGroupKeys.add(groupKey(matchedGroup));
      selections[groupKey(matchedGroup)] = item.ware_id;
      const option = matchedGroup.options.find((o) => o.ware_id === item.ware_id);
      // Unlike addToCartBtn's handler (which reads bonus-vs-main off the
      // .group-row's own "bonus-shield-row" class), there's no DOM here to
      // read that from during reconstruction -- but the wares_list item
      // itself already carries the same "surface_element_shield" override
      // (see waresListItem.category in addToCartBtn's handler) if it was
      // one when originally added, so that's the source of truth instead.
      displayItems.push({
        label: option.name,
        amount: item.amount,
        category: shieldDisplayCategory(matchedGroup.component_type, item.category === "surface_element_shield"),
      });
    } else {
      displayItems.push({ label: item.ware_id, amount: item.amount });
    }
  }

  return {
    shipWareId: shipData.ware_id,
    shipName: shipData.name,
    shipIcon: shipData.icon,
    missingRequiredComponents: missingRequiredLabels(shipData.groups, selections),
    note: config.note || "",
    count: config.count ?? 1,
    selections,
    missileAmounts: missileAmountsResult,
    droneAmounts: droneAmountsResult,
    deployableAmounts: deployableAmountsResult,
    countermeasureAmounts: countermeasureAmountsResult,
    crewAmounts: crewAmountsResult,
    wares_list: waresList,
    displayItems,
  };
}

loadCartInput.addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;

  let data;
  try {
    data = JSON.parse(await file.text());
  } catch (err) {
    alert(`Could not parse file: ${err.message}`);
    event.target.value = "";
    return;
  }

  if (!Array.isArray(data.wares)) {
    alert("This doesn't look like a valid fleet list file (missing a \"wares\" array).");
    event.target.value = "";
    return;
  }

  const activeName = activeFleet().name.trim() || DEFAULT_NEW_FLEET_LABEL;
  if (
    activeFleet().cart.length > 0 &&
    !confirm(`Loading will replace the active fleet's list ("${activeName}"). Continue?`)
  ) {
    event.target.value = "";
    return;
  }

  activeFleet().name = data.cart_name || "";
  cartNameInput.value = activeFleet().name;
  activeFleet().buildMethodPriority = data.build_method_priority ?? null;
  // A loaded file's own "search_depth"/"group_by_component_type" (if any --
  // old saves, or a CLI input file) are intentionally ignored: there's no
  // UI control for either any more, the Ware Cost List always shows both
  // fixed depths and both grouping modes (as tabs) regardless.

  const newCart = [];
  for (const config of data.wares) {
    newCart.push(await reconstructCartEntry(config));
  }
  activeFleet().cart = newCart;
  activeFleet().dirty = true;

  resetShipPicker();
  renderCart();
  event.target.value = ""; // allow re-selecting the same file later
});

// Hides the "Path to loadouts.xml" input (only meaningful when this
// server and the browser are the same machine) once this app is running
// as a public Fly.io deployment -- see api.py's IS_REMOTE/GET /api/config
// for the actual source of truth this mirrors; the backend independently
// rejects a path-based import in that mode regardless of what this UI
// shows, so a fetch failure here just leaves the (harmless, since the
// backend still blocks it) local-dev default visible rather than erroring.
async function applyRemoteModeUI() {
  try {
    const response = await fetch("/api/config");
    const config = await response.json();
    if (config.remote_mode) importLoadoutsPathSection.classList.add("hidden");
  } catch {
    // leave the path section visible -- see comment above
  }
}

// The nav bar's small "you are here" marker (see generate_nav_icons.py) --
// ship_s_fighter_01 (a small fighter) when no ship is loaded, matching the
// map's own default. Updates to the currently loaded ship's own icon in
// renderShipDetail() (every ship-load path funnels through there --
// Load button, Select Filter/<Ship> Loadout, editing a cart entry -- see
// that function's own callers), and reverts here in resetShipPicker()
// (both Clear buttons, plus every other place that resets the builder).
const DEFAULT_PLAYER_LOCATION_ICON = "ship_s_fighter_01";

function updatePlayerLocationMarker(iconName) {
  const src = `/images/nav_icons/player_location/${iconName || DEFAULT_PLAYER_LOCATION_ICON}.png`;
  for (const img of document.querySelectorAll(".main-nav-player-marker")) {
    img.src = src;
  }
}

// ---- Page navigation (Fleet Planner / Cost Analysis / About) ----
// Client-side only -- switching pages just toggles which #page-<id> div is
// visible, no navigation/reload involved, so fleets/currentShip/
// priceOverrides etc. all stay exactly as they were.
// location.hash still updates so a page is linkable/bookmarkable and the
// browser's own back/forward buttons work.
const PAGE_IDS = ["fleet-planner", "cost-analysis", "about"];

function showPage(pageId) {
  if (!PAGE_IDS.includes(pageId)) pageId = PAGE_IDS[0];
  for (const id of PAGE_IDS) {
    document.getElementById(`page-${id}`).classList.toggle("hidden", id !== pageId);
  }
  for (const btn of document.querySelectorAll(".main-nav-btn")) {
    btn.classList.toggle("active", btn.dataset.page === pageId);
  }
  if (location.hash !== `#${pageId}`) location.hash = pageId;
  // Navigating into Cost Analysis is the main lazy-recompute trigger (see
  // recomputeDirtyFleets()) -- edits made from *within* that page (price
  // overrides, per-fleet build method priority) recompute eagerly instead, since
  // "navigate in" never fires again while already there. Does NOT cover the
  // very first page shown at load -- see bootstrap()'s own trailing check,
  // since this runs before fleets are ever restored from localStorage.
  if (pageId === "cost-analysis") recomputeDirtyFleets();
}

for (const btn of document.querySelectorAll(".main-nav-btn")) {
  btn.addEventListener("click", () => showPage(btn.dataset.page));
}

// Covers both the browser's back/forward buttons and a direct/bookmarked
// link straight to e.g. #cost-analysis.
window.addEventListener("hashchange", () => showPage(location.hash.slice(1)));

showPage(location.hash.slice(1));

// ---- Persisted state (localStorage) ----
// Survives a page reload/browser restart -- everything a user would
// reasonably consider "their data": every fleet in `fleets` (including each
// one's own cached wareCostList/dirty flag -- deliberately NOT stripped, so
// a reload doesn't force every fleet to recompute again the next time Cost
// Analysis is opened, which would defeat the point of the dirty-flag
// design), which one is active, configured price overrides, and the
// imported-loadouts working set (see
// mergeImportedLoadoutsResult()/clearImportedLoadouts()), plus the current
// Size/Purpose/Type filter selections. Deliberately does NOT include the
// ship currently being configured in the builder (currentShip/
// missileAmounts/etc. and friends) -- that's treated as an unsaved draft,
// exactly like it already is if you clear the picker or load a different
// ship without adding the current one to the list.
const PERSISTED_STATE_KEY = "x4-fleet-planner-state";
const PERSISTED_STATE_VERSION = 2;

// loadShips() (see bootstrap() below) calls renderShipOptions() once on
// its own, before there's been any chance to restore a previous session --
// without this guard that call's own saveState() hook would immediately
// overwrite a real saved session with empty defaults, before
// restorePersistedState() ever got to read it. Flipped true right before
// restorePersistedState() runs; every save from then on is real.
let stateReady = false;

// Called from a handful of existing render/state-mutation choke points
// (renderCart() via renderWareCostList(), renderShipOptions(),
// updateLoadoutManagerBtnStates()) rather than threaded through every
// individual mutation -- see each call site's own comment.
function saveState() {
  if (!stateReady) return;

  const state = {
    version: PERSISTED_STATE_VERSION,
    fleets,
    activeFleetIndex,
    priceOverrides,
    importedLoadoutsResult,
    shareCache,
    filters: {
      size: checkedValues("size-filter"),
      purpose: checkedValues("purpose-filter"),
      type: checkedValues("type-filter"),
    },
  };
  try {
    localStorage.setItem(PERSISTED_STATE_KEY, JSON.stringify(state));
  } catch {
    // Storage full/disabled (private browsing, quota exceeded) -- state
    // just doesn't persist this time; nothing else in the app depends on
    // the write actually succeeding.
  }
}

// Returns null on anything unusable (nothing saved yet, corrupt JSON, or
// a version from a future/incompatible build of this app) rather than
// guessing at a partial shape -- restorePersistedState() then just leaves
// every already-initialized default in place.
function loadPersistedState() {
  let raw;
  try {
    raw = localStorage.getItem(PERSISTED_STATE_KEY);
  } catch {
    return null;
  }
  if (!raw) return null;
  try {
    const state = JSON.parse(raw);
    return state && state.version === PERSISTED_STATE_VERSION ? state : null;
  } catch {
    return null;
  }
}

// Called once at startup, after the ship list (and with it the filter
// checkboxes -- see loadShips()) exists to restore filter selections
// into. Re-renders through the same functions saveState() is hooked into,
// so restoring doesn't need its own separate render logic.
function restorePersistedState(state) {
  if (!state) return;

  if (Array.isArray(state.fleets) && state.fleets.length > 0) {
    fleets = state.fleets;
    // Defensive clamp -- guards against a corrupted/hand-edited index
    // rather than trusting it blindly.
    activeFleetIndex = Math.min(Math.max(state.activeFleetIndex ?? 0, 0), fleets.length - 1);
  }
  // priceOverrides is const (mutated in place elsewhere too, e.g. the
  // Configured Ware Price Overrides list's own "x" remove button) --
  // assign onto it rather than rebinding the name.
  if (state.priceOverrides && typeof state.priceOverrides === "object") {
    Object.assign(priceOverrides, state.priceOverrides);
  }
  if (state.importedLoadoutsResult) importedLoadoutsResult = state.importedLoadoutsResult;
  // Purely an optimization (skip re-uploading an unchanged share), so a
  // missing/malformed value here just means the next share regenerates
  // from scratch -- nothing to validate strictly.
  if (state.shareCache && typeof state.shareCache === "object") shareCache = state.shareCache;

  if (state.filters) {
    const filterGroups = {
      "size-filter": state.filters.size,
      "purpose-filter": state.filters.purpose,
      "type-filter": state.filters.type,
    };
    for (const [name, values] of Object.entries(filterGroups)) {
      if (!Array.isArray(values)) continue;
      for (const input of document.querySelectorAll(`input[name="${name}"]`)) {
        input.checked = values.includes(input.value);
      }
    }
  }

  updateLoadoutManagerBtnStates();
  renderShipOptions();
  renderCart();
}

async function bootstrap() {
  await loadShips(); // filter checkboxes (restorePersistedState needs them) live here
  await Promise.all([
    loadMissiles(),
    loadDrones(),
    loadDeployables(),
    loadCountermeasures(),
    loadCrew(),
    loadBuildMethods(),
  ]);
  stateReady = true;
  restorePersistedState(loadPersistedState());
  // Judged against the just-restored real state above, not empty defaults
  // -- see applyShareLinksFromUrl()'s own comment for why this has to come
  // after restorePersistedState(), not before it.
  await applyShareLinksFromUrl();

  // showPage(location.hash.slice(1)) below already ran once, synchronously,
  // before any of the above -- so its own recomputeDirtyFleets() hook (see
  // showPage()) fired, if at all, against the seeded placeholder fleet, not
  // real/restored data. Check the actually-visible page here, after restore
  // completes, and trigger the real recompute directly for a direct/
  // bookmarked load straight into #cost-analysis.
  if (!document.getElementById("page-cost-analysis").classList.contains("hidden")) {
    recomputeDirtyFleets();
  }
}

bootstrap();
applyRemoteModeUI();
