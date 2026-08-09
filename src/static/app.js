"use strict";

// Currently loaded ship's group data (response of GET /api/ships/{id}/groups).
let currentShip = null;

// ware_id of the ship currently highlighted in #ship-options-list (the
// custom ship-picker listbox -- see renderShipOptions()/applyShipSelection()
// below). Plays the same role a native <select>'s own .value would, but a
// plain <select> can't render an <img> per <option>, which every row here
// needs for its ship-class symbol.
let selectedShipWareId = "";

// Index into `cart` currently being edited, or null when "Add to procurement
// list" will append a new entry instead of replacing an existing one.
let editingIndex = null;

// Cart entries: {shipWareId, shipName, shipIcon, missingRequiredComponents, note,
// loadoutMinimized, count, selections: {group_name: ware_id},
// missileAmounts, droneAmounts, deployableAmounts, countermeasureAmounts: {ware_id: amount},
// crewAmounts: {role: amount} (role: "marine"/"service", see CREW_ROLES --
// not a real ware_id, both roles share one),
// wares_list: [{ware_id, amount}], displayItems: [{label, amount}]}
let cart = [];

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
// the page background. Not applied to <select><option> coloring
// (raceColorForName()/buildMethodColor() alone, used by
// buildGroupRow()/openBuildMethodModal()) since <option> background
// styling doesn't reliably render in native dropdowns anyway.
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

function buildMethodColor(methodName) {
  return factionColor(BUILD_METHOD_TO_FACTION[methodName]);
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
// procurement list's Loadout display, see renderLoadoutCell()). A
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
const typeFilterOptions = document.getElementById("type-filter-options");
const shipOptionsList = document.getElementById("ship-options-list");
const loadShipBtn = document.getElementById("load-ship-btn");
const clearShipBtnTop = document.getElementById("clear-ship-btn-top");
const importLoadoutsBtn = document.getElementById("import-loadouts-btn");
const selectGameLoadoutBtn = document.getElementById("select-game-loadout-btn");
const selectChassisLoadoutBtn = document.getElementById("select-chassis-loadout-btn");
const shipDetail = document.getElementById("ship-detail");
const shipNameEl = document.getElementById("ship-name");
const importedLoadoutWarningsEl = document.getElementById("imported-loadout-warnings");
const shipSummaryEl = document.getElementById("ship-summary");
const groupsContainer = document.getElementById("groups-container");
const ammunitionContainer = document.getElementById("ammunition-container");
const countermeasureContainer = document.getElementById("countermeasure-container");
const droneContainer = document.getElementById("drone-container");
const deployableContainer = document.getElementById("deployable-container");
const crewContainer = document.getElementById("crew-container");
const shipNoteInput = document.getElementById("ship-note-input");
const addToCartBtn = document.getElementById("add-to-cart-btn");
const addToSavedLoadoutsBtn = document.getElementById("add-to-saved-loadouts-btn");
const addToSavedLoadoutsStatus = document.getElementById("add-to-saved-loadouts-status");
const clearShipBtnBottom = document.getElementById("clear-ship-btn-bottom");
const cartBody = document.getElementById("cart-body");
const cartEmptyMsg = document.getElementById("cart-empty-msg");
const analysisFileNameInput = document.getElementById("analysis-file-name-input");
const downloadAnalysisBtn = document.getElementById("download-analysis-btn");
const uploadAnalysisInput = document.getElementById("upload-analysis-input");
const wareCostListSection = document.getElementById("ware-cost-list");
const wareCostListThead = document.getElementById("ware-cost-list-thead");
const wareCostListBody = document.getElementById("ware-cost-list-body");
const saveCartBtn = document.getElementById("save-cart-btn");
const loadCartInput = document.getElementById("load-cart-input");
const cartNameInput = document.getElementById("cart-name-input");
const saveForComparisonBtn = document.getElementById("save-for-comparison-btn");
const saveForComparisonWarning = document.getElementById("save-for-comparison-warning");
const buildMethodModalOverlay = document.getElementById("build-method-modal-overlay");
const buildMethodModalFocusSelect = document.getElementById("build-method-modal-focus-select");
const buildMethodModalFallbackList = document.getElementById("build-method-modal-fallback-list");
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
const importLoadoutsModalOverlay = document.getElementById("import-loadouts-modal-overlay");
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

// The most recently calculated (or loaded) /api/summarize response, exactly
// as rendered by renderWareCostList() -- kept around purely so "Save ware
// cost list…" has something to serialize without needing to re-run the
// calculation.
let lastWareCostList = null;

// The Active column's own build focus -- replaces what used to be a single
// shared "Build focus" text input. Each saved comparison column now has its
// own independent build focus too (savedComparisonColumns[i].buildFocus),
// set via the same small button/modal (see openBuildMethodModal()) shown
// under that column's own name in the Ware Cost List header -- see
// renderWareCostListHead(). null means "no build focus set", same meaning
// the old text box's empty string had.
let activeBuildFocus = null;

// The Active column's own fallback-method order + inclusion list -- same
// per-column shape as activeBuildFocus above (savedComparisonColumns[i]
// .fallbackMethods is the saved-column equivalent). null means "use
// whatever /api/build_methods currently returns" (api.py's own
// DEFAULT_FALLBACK_METHODS) -- sent through to /api/summarize and
// /api/price_summary as-is (both already treat a null fallback_methods as
// "use the server default"), only becoming a concrete array once a column's
// build method modal has actually been saved at least once.
let activeFallbackMethods = null;

// Every real build method, fetched once from GET /api/build_methods (see
// BUILD_METHODS in generate_ships_table.py for how it's curated/ordered) --
// both the options list for the modal's build-focus <select> and the
// starting point for any column whose own fallbackMethods is still null.
let allBuildMethods = [];

// Which column the Build Method modal is currently open for -- one of the
// objects wareCostListColumns() builds ({removable, index, ...}), read by
// the modal's own Save handler to know whether to update activeBuildFocus/
// activeFallbackMethods (removable: false) or a specific saved snapshot
// (removable: true, via index). null while the modal is closed.
let buildMethodModalTarget = null;

// The modal's own working copy of the fallback-method list while open --
// [{name, included}], in display/fallback order -- edited in place by the
// checkbox/reorder controls (see renderBuildMethodModalFallbackList()) and
// only committed to the target column's own fallbackMethods on Save.
let buildMethodModalFallbackOrder = [];

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

// One representative icon per ship_type, for the type filter checkboxes --
// icons are actually keyed by (size, purpose) rather than by ship_type
// alone (see generate_ships_table.py's ships_base.icon docstring), so a
// single type can have ships using more than one icon (e.g. "destroyer" at
// L vs XL). This just takes whichever icon the first ship of that type
// (in allShips' name-sorted order) happens to have -- good enough for a
// filter checkbox's purely illustrative symbol, not meant to be exact.
function typeIconMap() {
  const map = {};
  for (const ship of allShips) {
    if (!(ship.ship_type in map)) map[ship.ship_type] = ship.icon;
  }
  return map;
}

async function loadShips() {
  const response = await fetch("/api/ships");
  allShips = await response.json();
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
  const sizes = [...new Set(allShips.map((ship) => ship.size))].sort();
  const types = [...new Set(allShips.map((ship) => ship.ship_type))].sort();

  // Sizes are stored/filtered on as their raw lowercase abbreviation
  // (ship.size, e.g. "s"/"m"/"l"/"xl" -- same value renderShipSummary()
  // already .toUpperCase()s for display elsewhere) -- formatLabel only
  // changes what's shown next to the checkbox, not the value it filters
  // on, so sizeValues.includes(ship.size) in renderShipOptions() still
  // matches correctly.
  buildCheckboxGroup(sizeFilterOptions, "size-filter", sizes, (value) => value.toUpperCase());
  buildCheckboxGroup(typeFilterOptions, "type-filter", types, (value) => value, typeIconMap());
}

function buildCheckboxGroup(container, name, values, formatLabel = (value) => value, iconLookup = null) {
  container.innerHTML = "";
  for (const value of values) {
    container.appendChild(
      buildCheckboxOption(name, value, formatLabel(value), iconLookup ? iconLookup[value] : null),
    );
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
function renderShipOptions() {
  const sizeValues = checkedValues("size-filter");
  const typeValues = checkedValues("type-filter");

  shipOptionsList.innerHTML = "";

  const filtered = allShips.filter(
    (ship) =>
      (sizeValues.length === 0 || sizeValues.includes(ship.size)) &&
      (typeValues.length === 0 || typeValues.includes(ship.ship_type)),
  );

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
  addToCartBtn.textContent = "Add to procurement list";
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
    addToCartBtn.textContent = "Add to procurement list";
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

function resetFilters() {
  for (const input of document.querySelectorAll('input[name="size-filter"], input[name="type-filter"]')) {
    input.checked = false;
  }
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

// Grouping for the Procurement List's own "Loadout" display (see
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
// can be added to the procurement list. Not enforced anywhere server-side
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
function buildGroupRow(group, { isLinkedShield = false } = {}) {
  const row = document.createElement("div");
  row.className = "group-row";
  row.dataset.groupKey = groupKey(group);
  row.dataset.groupName = group.group_name;
  row.dataset.slotCount = group.slot_count;
  // Read back in addToCartBtn's handler to group the procurement list's
  // own display by component type (see CART_DISPLAY_GROUP_LABELS/
  // renderCart()) -- bonus-M-shield rows are still plain "shield" here
  // (isLinkedShield only changes the *label* above), so they group
  // together with ordinary main shields, same as this app's own picker
  // sections already treat them as one "Shields" category.
  row.dataset.componentType = group.component_type;

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
    marker.title = "Recommended -- leaving this unselected will show a warning in the procurement list";
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
  selectChassisLoadoutBtn.textContent = `Select ${data.name} loadout`;
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

    if (sectionType === "software") {
      const highBtn = document.createElement("button");
      highBtn.type = "button";
      highBtn.className = "software-preset-btn";
      highBtn.textContent = "High Preset";
      highBtn.title = "Select the highest-tier software available in every slot";
      highBtn.addEventListener("click", applyHighSoftwarePreset);
      headingRow.appendChild(highBtn);

      const minBtn = document.createElement("button");
      minBtn.type = "button";
      minBtn.className = "software-preset-btn";
      minBtn.textContent = "Minimum Preset";
      minBtn.title = "Select the lowest-tier software in only the required slots (Flight Assist, Object Scanner, Long Range Scanner)";
      minBtn.addEventListener("click", applyMinimumSoftwarePreset);
      headingRow.appendChild(minBtn);
    }

    section.appendChild(headingRow);

    for (const entries of bundles) {
      const card = document.createElement("div");
      card.className = "group-card";

      const nonShield = entries.filter((g) => g.component_type !== "shield");
      const shields = entries.filter((g) => g.component_type === "shield");
      const isLinked = nonShield.length > 0; // else: a standalone shield-only group_name

      for (const group of nonShield) {
        card.appendChild(buildGroupRow(group));
      }
      for (const group of shields) {
        const row = buildGroupRow(group, { isLinkedShield: isLinked });
        if (isLinked) row.classList.add("bonus-shield-row");
        card.appendChild(row);
      }

      section.appendChild(card);
    }

    groupsContainer.appendChild(section);
  }

  updateSelectedAmmoCapacity();
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

// Every currently-rendered software .group-row, in DOM order.
function softwareGroupRows() {
  return [...groupsContainer.querySelectorAll(".group-row")].filter((row) => row.dataset.componentType === "software");
}

// The raw group data (with its own .options, each carrying "mk") behind a
// .group-row -- the row itself only stores groupKey as a dataset string,
// so this looks it back up in currentShip.groups (the same array
// buildGroupRow() built every row from in the first place).
function groupForRow(row) {
  return currentShip ? (currentShip.groups.find((g) => groupKey(g) === row.dataset.groupKey) ?? null) : null;
}

// "High Preset" button (next to the Software section title): selects the
// highest-mk option in *every* software slot, required or not. mk, not
// name or array order, is the only reliable tier indicator for software
// -- see matching_items()'s software branch in query_ship_components.py
// for why (some categories' names don't follow a "... Mk1"/"Mk2"
// convention at all, e.g. "Basic Scanner" vs "Police Scanner").
function applyHighSoftwarePreset() {
  for (const row of softwareGroupRows()) {
    const group = groupForRow(row);
    if (!group || group.options.length === 0) continue;
    const best = group.options.reduce((a, b) => (b.mk > a.mk ? b : a));
    applySelectionToRow(row, best.ware_id);
  }
}

// "Minimum Preset" button: selects the lowest-mk option in the software
// slots actually marked required (row.dataset.requiredLabel -- Flight
// Assist/Object Scanner/Long Range Scanner, see REQUIRED_SOFTWARE_LABELS),
// and clears every other software slot back to "-- none --" -- a true
// minimum-viable loadout, not just "leave whatever else was picked".
function applyMinimumSoftwarePreset() {
  for (const row of softwareGroupRows()) {
    if (!row.dataset.requiredLabel) {
      applySelectionToRow(row, "");
      continue;
    }
    const group = groupForRow(row);
    if (!group || group.options.length === 0) continue;
    const worst = group.options.reduce((a, b) => (b.mk < a.mk ? b : a));
    applySelectionToRow(row, worst.ware_id);
  }
}

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
  loadShipBtn.disabled = true;
  selectChassisLoadoutBtn.disabled = true;
  shipDetail.classList.add("hidden");
  groupsContainer.innerHTML = "";
  ammunitionContainer.innerHTML = "";
  countermeasureContainer.innerHTML = "";
  droneContainer.innerHTML = "";
  deployableContainer.innerHTML = "";
  crewContainer.innerHTML = "";
  shipNoteInput.value = "";
  addToCartBtn.textContent = "Add to procurement list";
  importedLoadoutWarningsEl.classList.add("hidden");
  addToSavedLoadoutsStatus.classList.add("hidden");
}

// Two copies of the same action (top, next to Load; bottom, next to Add
// to procurement list) so it's reachable without scrolling regardless of
// where the user currently is on a long ship-detail page.
clearShipBtnTop.addEventListener("click", resetShipPicker);
clearShipBtnBottom.addEventListener("click", resetShipPicker);

addToCartBtn.addEventListener("click", () => {
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
    cart[editingIndex] = {
      ...cart[editingIndex],
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
    cart.push({
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
  renderCart();
});

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
// so "Add to Saved Loadouts" can build a comparable selections map without
// duplicating that DOM walk.
function gatherCurrentSelections() {
  const selections = {};
  for (const row of groupsContainer.querySelectorAll(".group-row")) {
    const select = row.querySelector(".group-select");
    if (select.value) selections[row.dataset.groupKey] = select.value;
  }
  return selections;
}

// "Add to Saved Loadouts": snapshots the current ship-builder state into
// the same importedLoadoutsResult working set "Import game loadouts"/
// "Import raw XML loadout" feed (see mergeImportedLoadoutsResult()), so it
// immediately shows up in "Select saved loadout"/"Select <ship> loadout"
// and gets picked up by "Export loadouts" too (server-side synthesized
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

  addToSavedLoadoutsBtn.disabled = true;
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
    addToSavedLoadoutsBtn.disabled = false;
  }
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

// Called after every procurement-list mutation (add/edit, remove, load)
// to keep the cart table in sync -- also triggers runCalculation() at the
// end, so the Ware Cost List/Monetary Cost Analysis stay live without a
// manual Calculate click. The qty +/- and direct-input controls built
// below deliberately skip a full renderCart() (they only need to update
// their own displayed value), so they call runCalculation() themselves
// instead of relying on this.
function renderCart() {
  cartBody.innerHTML = "";
  cartEmptyMsg.classList.toggle("hidden", cart.length > 0);

  cart.forEach((entry, index) => {
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
    tr.appendChild(shipTd);

    const loadoutTd = document.createElement("td");
    loadoutTd.className = "cart-loadout";
    renderLoadoutCell(loadoutTd, entry);
    tr.appendChild(loadoutTd);

    const qtyTd = document.createElement("td");
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
      runCalculation();
    });

    const minusBtn = document.createElement("button");
    minusBtn.type = "button";
    minusBtn.textContent = "-";
    minusBtn.className = "qty-btn";
    // Shift+click zeroes this row out in one step; ctrl+click steps by 10
    // instead of 1. No "fill max" on plus here -- unlike the
    // capacity-pooled pickers above, a procurement list entry's own
    // quantity has no ceiling, so ctrl+click on plus just steps by 10 too.
    minusBtn.addEventListener("click", (event) => {
      entry.count = event.shiftKey ? 0 : Math.max(0, entry.count - (event.ctrlKey ? 10 : 1));
      qtyInput.value = entry.count;
      runCalculation();
    });

    const plusBtn = document.createElement("button");
    plusBtn.type = "button";
    plusBtn.textContent = "+";
    plusBtn.className = "qty-btn";
    plusBtn.addEventListener("click", (event) => {
      entry.count += event.ctrlKey ? 10 : 1;
      qtyInput.value = entry.count;
      runCalculation();
    });

    qtyWrap.appendChild(minusBtn);
    qtyWrap.appendChild(qtyInput);
    qtyWrap.appendChild(plusBtn);
    qtyTd.appendChild(qtyWrap);
    tr.appendChild(qtyTd);

    const actionsTd = document.createElement("td");

    const editBtn = document.createElement("button");
    editBtn.textContent = "Edit";
    editBtn.className = "edit-btn";
    editBtn.addEventListener("click", () => editCartEntry(index));
    actionsTd.appendChild(editBtn);

    const removeBtn = document.createElement("button");
    removeBtn.textContent = "Remove";
    removeBtn.className = "remove-btn";
    removeBtn.addEventListener("click", () => {
      cart.splice(index, 1);
      if (editingIndex === index) resetShipPicker();
      renderCart();
    });
    actionsTd.appendChild(removeBtn);

    tr.appendChild(actionsTd);

    cartBody.appendChild(tr);
  });

  runCalculation();
}

async function editCartEntry(index) {
  const entry = cart[index];
  const response = await fetch(`/api/ships/${encodeURIComponent(entry.shipWareId)}/groups`);
  const data = await response.json();
  if (data.error) {
    alert(`Could not load ship: ${data.error}`);
    return;
  }

  currentShip = data;
  editingIndex = index;
  // Clear filters first -- the ship being edited may not be in the
  // currently filtered option list, in which case setting .value below
  // would silently fail to select it.
  resetFilters();
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
  addToCartBtn.textContent = "Update procurement list";
  importedLoadoutWarningsEl.classList.add("hidden");
  shipDetail.scrollIntoView({ behavior: "smooth", block: "start" });
}

// ---- Import Game Loadouts ----
// Two modals: "Import game loadouts" (reads a player-saved loadouts.xml,
// either by server-side path or an uploaded file, via POST
// /api/import_loadouts) and "Select game loadout" (picks one of the
// successfully-parsed ship loadouts from that import to load into the
// builder, the same way editCartEntry() loads a saved cart entry). See
// import_loadouts.py's own module docstring for the schema being parsed
// and how each field maps onto this app's own cart-entry shape.

// The most recent POST /api/import_loadouts response
// ({ships, failed, total_loadouts, skipped_station_loadouts}), or null
// before any import has run -- populates the "Select game loadout" modal,
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
    if (warningCount > 0) lines.push(`${warningCount} warning(s) across imported ships -- see "Select game loadout".`);
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
}

// Discards the entire imported-loadouts working set (both "Import game
// loadouts" and "Import raw XML loadout" feed into the same
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
    if (warningCount > 0) lines.push(`${warningCount} warning(s) -- see "Select game loadout".`);
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

// Shared by both the "Select game loadout" button (every imported ship)
// and the "Select chassis loadout" button next to the loaded ship's name
// (only loadouts whose shipWareId matches the currently loaded ship) --
// chassisWareId is omitted for the former, passed for the latter.
function openSelectGameLoadoutModal(chassisWareId) {
  if (!importedLoadoutsResult) return;
  const entries = chassisWareId
    ? importedLoadoutsResult.ships.filter((s) => s.shipWareId === chassisWareId)
    : importedLoadoutsResult.ships;

  selectGameLoadoutModalTitle.textContent = chassisWareId ? `Select ${currentShip.name} Loadout` : "Select Saved Loadout";
  selectGameLoadoutList.innerHTML = "";

  if (entries.length === 0) {
    const empty = document.createElement("p");
    empty.textContent = "No imported loadouts for this ship.";
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
// editing an existing cart entry -- "Add to procurement list" will append
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
  resetFilters();
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
  addToCartBtn.textContent = "Add to procurement list";

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

// Bumped on every runCalculation() call and captured as `token` at the
// start of each -- a response is only applied if it's still the latest
// call by the time it arrives, so rapidly changing the procurement list
// (e.g. mashing a qty +/- button) can't let an older, slower response
// clobber a newer one on screen.
let calculationToken = 0;

// The Ware Cost List always fetches both grouping modes at once -- "total"
// (group_by_component_type false) for the "Total Cost Breakdown" tab and
// "component_type" (true) for the "Component Type Cost Breakdown" tab --
// rather than a checkbox controlling which single mode gets requested.
// Switching tabs is then a pure client-side re-render (see
// renderWareCostList()), never a new request.
let activeWareCostListTab = "total";

// Whether the current render has an "Active List" column to compare saved
// columns against -- set once per renderWareCostList() call (it's always
// column 0 when present, since wareCostListColumns() puts it first) and
// read by appendComparisonCell() below, rather than threading a parameter
// through every rendering function in the tier -> method -> [category] ->
// row chain. False whenever the active procurement list is empty (see
// wareCostListColumns()), in which case saved columns render as plain
// values with no diff annotation at all -- there's nothing to be a
// baseline.
let wareCostListHasBaseline = false;

// Resolves to the parsed JSON body, or throws (with the response's own
// error text) on a non-ok response -- lets runCalculation() below fire
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
// price_summary grouping modes for one cart + build focus + fallback-method
// list, returning the exact {total: {...}, component_type: {...}} shape
// lastWareCostList/savedComparisonColumns[i].wareCostList both use.
// fallbackMethods null is passed straight through to the API as-is --
// both /api/summarize and /api/price_summary already treat a null
// fallback_methods as "use the server's own default" (DEFAULT_FALLBACK_
// METHODS), same meaning activeFallbackMethods/snapshot.fallbackMethods
// give it client-side. Shared by runCalculation() (the live Active column,
// re-run automatically on every cart mutation) and
// recomputeSavedColumnBuildConfig() (a saved column, re-run only when that
// column's own build method is explicitly edited) -- the two differ only in
// which cart/build focus/fallback methods they call this with and where
// they store the result.
async function computeWareCostList(cartEntries, buildFocus, fallbackMethods) {
  const wares = cartEntries.map((entry) => ({ count: entry.count, wares_list: entry.wares_list }));
  const summarizeBaseBody = { build_focus: buildFocus, fallback_methods: fallbackMethods, verbose: false, wares };
  const priceBaseBody = { build_focus: buildFocus, fallback_methods: fallbackMethods, wares };

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

// Re-runs the Ware Cost List (see computeWareCostList()) and the Monetary
// Cost Analysis panel for the Active column, from the current procurement
// list and its own activeBuildFocus. Called automatically by every
// procurement-list mutation (see renderCart() and the qty controls within
// it) and by editing the Active column's build focus (see
// renderWareCostListHead()), so everything always reflects the cart's
// current contents without a manual click. Silently hides both panels
// (rather than alerting) when the cart is empty, since this runs
// unattended -- an empty cart is a normal, reachable state (e.g. after
// removing the last entry), not a user error.
async function runCalculation() {
  const token = ++calculationToken;

  if (cart.length === 0) {
    lastWareCostList = null;
    // Still re-rendered (not just hidden outright): any saved comparison
    // columns are unaffected by the active cart being empty and should
    // stay visible -- renderWareCostList() itself decides whether the
    // whole section has anything left to show at all.
    renderWareCostList();
    return;
  }

  let result;
  try {
    result = await computeWareCostList(cart, activeBuildFocus, activeFallbackMethods);
  } catch (err) {
    if (token !== calculationToken) return; // superseded by a newer call
    alert(`Calculation failed: ${err.message}`);
    return;
  }
  if (token !== calculationToken) return; // superseded by a newer call

  lastWareCostList = result;
  renderWareCostList();
}

// Re-runs the Active column's own calculation with a newly edited build
// method (see the Build Method modal's Save handler below). Just a thin
// wrapper around setting the two module-level variables + runCalculation()
// -- factored out mainly so the modal's Save handler doesn't need to know
// which column type it's touching beyond a single if/else.
function recomputeActiveBuildConfig(buildFocus, fallbackMethods) {
  activeBuildFocus = buildFocus;
  activeFallbackMethods = fallbackMethods;
  runCalculation();
}

// Re-runs one saved comparison column's own calculation with a newly edited
// build method, updating its stored buildFocus/fallbackMethods/wareCostList
// in place. Unlike runCalculation() (re-run automatically on every cart
// mutation, guarded by calculationToken against overlapping calls), this
// only ever fires from one deliberate action -- editing that column's own
// build method -- so no race-guarding is needed.
async function recomputeSavedColumnBuildConfig(index, buildFocus, fallbackMethods) {
  const snapshot = savedComparisonColumns[index];
  if (!snapshot) return;

  let result;
  try {
    result = await computeWareCostList(snapshot.cart, buildFocus, fallbackMethods);
  } catch (err) {
    alert(`Calculation failed: ${err.message}`);
    return;
  }

  snapshot.buildFocus = buildFocus;
  snapshot.fallbackMethods = fallbackMethods;
  snapshot.wareCostList = result;
  renderWareCostList();
}

// Opens the Build Method modal for `column` (one of wareCostListColumns()'s
// own entries) -- populates the build-focus <select> from allBuildMethods
// (plus a leading "no build focus" option) and the fallback-methods list
// from column.fallbackMethods, defaulting to allBuildMethods itself (in its
// already-correct order) when that column has never had one set. Every
// method in allBuildMethods is always shown, even ones this column's own
// customized list had unchecked/excluded -- see buildMethodModalFallbackOrder's
// own comment for why order and inclusion are tracked independently.
function openBuildMethodModal(column) {
  buildMethodModalTarget = column;

  buildMethodModalFocusSelect.innerHTML = "";
  const noneOption = document.createElement("option");
  noneOption.value = "";
  noneOption.textContent = "-- none --";
  buildMethodModalFocusSelect.appendChild(noneOption);
  for (const method of allBuildMethods) {
    const opt = document.createElement("option");
    opt.value = method;
    opt.textContent = method;
    const color = buildMethodColor(method);
    if (color) opt.style.color = color;
    buildMethodModalFocusSelect.appendChild(opt);
  }
  buildMethodModalFocusSelect.value = column.buildFocus ?? "";

  const currentOrder = column.fallbackMethods ?? allBuildMethods;
  const includedSet = new Set(currentOrder);
  // Anything in allBuildMethods but not in this column's own saved order
  // (e.g. a method added to the game data after this column's list was
  // last customized) is appended at the end, unchecked -- still editable,
  // never silently dropped.
  const extras = allBuildMethods.filter((m) => !includedSet.has(m));
  buildMethodModalFallbackOrder = [...currentOrder, ...extras].map((name) => ({
    name,
    included: includedSet.has(name),
  }));

  renderBuildMethodModalFallbackList();
  buildMethodModalOverlay.classList.remove("hidden");
}

// Rebuilds the modal's fallback-methods checklist from
// buildMethodModalFallbackOrder -- called on open and after every
// checkbox/reorder edit (the list is small, a handful of rows, so a full
// rebuild per edit is simpler than patching individual rows in place).
function renderBuildMethodModalFallbackList() {
  buildMethodModalFallbackList.innerHTML = "";

  buildMethodModalFallbackOrder.forEach((entry, index) => {
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
    applyFactionTextColor(nameSpan, BUILD_METHOD_TO_FACTION[entry.name]);
    nameSpan.textContent = entry.name;
    label.appendChild(nameSpan);
    row.appendChild(label);

    const upBtn = document.createElement("button");
    upBtn.type = "button";
    upBtn.className = "build-method-reorder-btn";
    upBtn.textContent = "↑";
    upBtn.disabled = index === 0;
    upBtn.addEventListener("click", () => {
      [buildMethodModalFallbackOrder[index - 1], buildMethodModalFallbackOrder[index]] = [
        buildMethodModalFallbackOrder[index],
        buildMethodModalFallbackOrder[index - 1],
      ];
      renderBuildMethodModalFallbackList();
    });
    row.appendChild(upBtn);

    const downBtn = document.createElement("button");
    downBtn.type = "button";
    downBtn.className = "build-method-reorder-btn";
    downBtn.textContent = "↓";
    downBtn.disabled = index === buildMethodModalFallbackOrder.length - 1;
    downBtn.addEventListener("click", () => {
      [buildMethodModalFallbackOrder[index], buildMethodModalFallbackOrder[index + 1]] = [
        buildMethodModalFallbackOrder[index + 1],
        buildMethodModalFallbackOrder[index],
      ];
      renderBuildMethodModalFallbackList();
    });
    row.appendChild(downBtn);

    buildMethodModalFallbackList.appendChild(row);
  });
}

function closeBuildMethodModal() {
  buildMethodModalOverlay.classList.add("hidden");
  buildMethodModalTarget = null;
  buildMethodModalFallbackOrder = [];
}

buildMethodModalCancelBtn.addEventListener("click", closeBuildMethodModal);

buildMethodModalSaveBtn.addEventListener("click", () => {
  if (!buildMethodModalTarget) return;

  const buildFocus = buildMethodModalFocusSelect.value || null;
  const fallbackMethods = buildMethodModalFallbackOrder.filter((entry) => entry.included).map((entry) => entry.name);

  const column = buildMethodModalTarget;
  closeBuildMethodModal();

  if (column.removable) {
    recomputeSavedColumnBuildConfig(column.index, buildFocus, fallbackMethods);
  } else {
    recomputeActiveBuildConfig(buildFocus, fallbackMethods);
  }
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
// response itself. An empty "parts" (an explicit build_focus that turned
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
// (neither the "total"/"component_type" split nor which procurement list a
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
// with its own "Build Focus: ..." button/modal -- see
// renderWareCostListHead()), not separate method sections stacked inside
// one column.
function appendWareCostListTier(tierKey, heading, columns) {
  const totalColumns = columns.length + 1;
  const tierCollapsed = appendCollapsibleHeader(tierKey, heading, "ware-cost-list-tier-title", totalColumns);
  if (tierCollapsed) return;

  const dataByColumn = columns.map((column) => {
    const tierResult = tierResultForColumn(column, tierKey);
    if (!tierResult) return null;
    const methodNames = Object.keys(tierResult.methods);
    return methodNames.length > 0 ? tierResult.methods[methodNames[0]] : null;
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
  // given tab (see runCalculation()/saveForComparisonBtn), so whichever
  // column actually has data decides whether it's grouped -- they never
  // legitimately disagree.
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

// One column per procurement list currently shown in the Ware Cost List --
// the live "Active List" first (tracks the current cart and its most
// recent calculation; omitted entirely while the cart is empty), then one
// per snapshot saved via "Save for comparison", in the order they were
// saved. `removable` is false only for the active column, which can't be
// removed this way (clear the procurement list instead).
function wareCostListColumns() {
  const columns = [];
  if (lastWareCostList) {
    columns.push({
      label: "Active List",
      data: lastWareCostList,
      removable: false,
      buildFocus: activeBuildFocus,
      fallbackMethods: activeFallbackMethods,
    });
  }
  savedComparisonColumns.forEach((snapshot, index) => {
    columns.push({
      label: snapshot.name,
      data: snapshot.wareCostList,
      removable: true,
      index,
      buildFocus: snapshot.buildFocus,
      fallbackMethods: snapshot.fallbackMethods,
    });
  });
  return columns;
}

function removeComparisonColumn(index) {
  savedComparisonColumns.splice(index, 1);
  renderWareCostList();
  updateSaveForComparisonWarning(); // the removed column may have been the one causing it
}

// The two-row <thead>: a "List Name" row naming each column (each with its
// own "Build Focus: ..." button underneath -- see openBuildMethodModal() --
// plus a remove button on every saved one, none on "Active List"), then a
// "Ware"/"Amount" x N column-header row underneath -- except a saved
// column's own "Amount" cell is instead a "Set Active" button (see
// setActiveFromComparisonColumn() above), since that's the more useful
// thing to put there than a repeated, static label. Rebuilt on every
// render since the column count itself can change (adding/removing a
// saved comparison snapshot).
function renderWareCostListHead(columns) {
  wareCostListThead.innerHTML = "";

  const nameRow = document.createElement("tr");
  nameRow.className = "ware-cost-list-name-row";
  const nameLabelTh = document.createElement("th");
  nameLabelTh.textContent = "List Name";
  nameRow.appendChild(nameLabelTh);
  for (const column of columns) {
    const th = document.createElement("th");

    const nameDiv = document.createElement("div");
    nameDiv.append(column.label);
    th.appendChild(nameDiv);

    // Opens the Build Method modal (see openBuildMethodModal()) to edit
    // this column's own build focus + fallback-methods list. The modal's
    // own Save handler decides whether to recalculate the Active column
    // right away (recomputeActiveBuildConfig()) or just this saved
    // snapshot (recomputeSavedColumnBuildConfig()), based on column.removable.
    const buildFocusBtn = document.createElement("button");
    buildFocusBtn.type = "button";
    buildFocusBtn.className = "ware-cost-list-build-focus-btn";
    buildFocusBtn.appendChild(document.createTextNode("Build Focus: "));
    const buildFocusNameSpan = document.createElement("span");
    applyFactionTextColor(buildFocusNameSpan, BUILD_METHOD_TO_FACTION[column.buildFocus]);
    buildFocusNameSpan.textContent = column.buildFocus ?? "none";
    buildFocusBtn.appendChild(buildFocusNameSpan);
    buildFocusBtn.title = "Set this list's build method";
    buildFocusBtn.addEventListener("click", () => openBuildMethodModal(column));
    th.appendChild(buildFocusBtn);

    if (column.removable) {
      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.className = "ware-cost-list-remove-column-btn";
      removeBtn.textContent = "×";
      removeBtn.title = "Remove this saved comparison column";
      removeBtn.addEventListener("click", () => removeComparisonColumn(column.index));
      th.appendChild(removeBtn);
    }
    nameRow.appendChild(th);
  }
  wareCostListThead.appendChild(nameRow);

  const columnHeaderRow = document.createElement("tr");
  const wareTh = document.createElement("th");
  wareTh.textContent = "Ware";
  columnHeaderRow.appendChild(wareTh);
  for (const column of columns) {
    const th = document.createElement("th");
    if (column.removable) {
      const setActiveBtn = document.createElement("button");
      setActiveBtn.type = "button";
      setActiveBtn.className = "ware-cost-list-set-active-btn";
      setActiveBtn.textContent = "Set Active";
      setActiveBtn.addEventListener("click", () => setActiveFromComparisonColumn(column.index));
      th.appendChild(setActiveBtn);
    } else {
      th.textContent = "Amount";
    }
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

  const rawDataByColumn = columns.map((column) => {
    const rawResult = tierResultForColumn(column, "raw_materials_price");
    if (!rawResult) return null;
    const methodNames = Object.keys(rawResult);
    return methodNames.length > 0 ? rawResult[methodNames[0]] : null;
  });
  const productionDataByColumn = columns.map((column) => {
    const productionResult = tierResultForColumn(column, "production_wares_price");
    if (!productionResult) return null;
    const methodNames = Object.keys(productionResult);
    return methodNames.length > 0 ? productionResult[methodNames[0]] : null;
  });

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
// -- across every column currently shown (the active procurement list plus
// any saved comparison snapshots). Reads lastWareCostList/
// savedComparisonColumns/activeWareCostListTab directly rather than taking
// parameters, since it's invoked from several unrelated places (a fresh
// calculation, a tab switch, a collapse toggle, adding or removing a
// comparison column) that all just want "redraw with whatever the current
// state is".
function renderWareCostList() {
  const columns = wareCostListColumns();
  if (columns.length === 0) {
    wareCostListSection.classList.add("hidden");
    return;
  }
  wareCostListSection.classList.remove("hidden");
  wareCostListHasBaseline = !columns[0].removable;

  renderWareCostListHead(columns);
  wareCostListBody.innerHTML = "";

  appendMoneyTier(columns);
  appendWareCostListTier(
    "production_wares",
    "Production Wares (buy what the shipyard directly consumes)",
    columns,
  );
  appendWareCostListTier("raw_materials", "Raw Materials (build everything from scratch)", columns);
}

// --- Ware cost list comparison --------------------------------------------
// Snapshots taken via "Save for comparison" -- each is a fully independent,
// frozen copy of the procurement list (cart) and its computed results
// (lastWareCostList) at the moment it was saved, so that column never
// changes when the active procurement list is edited afterward. Deep-
// copied via a JSON round-trip since both cart and lastWareCostList are
// plain data (no functions/DOM references) -- simpler than a hand-written
// structural clone. Only lives in memory for now (no file save/load, per
// the "Save for comparison" button replacing the old ware-cost-list
// save/load buttons entirely).
let savedComparisonColumns = [];

// Stand-in for a snapshot taken with no procurement list name set --
// stored literally in snapshot.name (rather than leaving it "") so the
// List Name row always has something to display; setActiveFromComparisonColumn()
// below checks for this exact value to know when to restore an *empty*
// cartNameInput instead of this placeholder text.
const UNNAMED_PROCUREMENT_LIST_LABEL = "(unnamed procurement list)";

// Live warning next to "Save for comparison" -- shown whenever the current
// procurement list's name (resolved the same way saveForComparisonBtn's
// handler resolves it) matches an *existing* saved comparison column's
// name, since clicking Save in that state overwrites that column instead
// of adding a new one. Re-checked on every rename (cartNameInput's "input"
// event below) and wherever else the set of saved columns or the active
// name can change: after saving, removing a column, or "Set Active".
function updateSaveForComparisonWarning() {
  const name = cartNameInput.value.trim() || UNNAMED_PROCUREMENT_LIST_LABEL;
  const willOverwrite = savedComparisonColumns.some((snapshot) => snapshot.name === name);
  saveForComparisonWarning.textContent = willOverwrite ? "warning, this will overwrite a saved list." : "";
}
cartNameInput.addEventListener("input", updateSaveForComparisonWarning);

saveForComparisonBtn.addEventListener("click", () => {
  if (!lastWareCostList) {
    alert("No ware cost list to save yet -- add something to the procurement list first.");
    return;
  }

  const name = cartNameInput.value.trim() || UNNAMED_PROCUREMENT_LIST_LABEL;
  const snapshot = {
    name,
    cart: JSON.parse(JSON.stringify(cart)),
    wareCostList: JSON.parse(JSON.stringify(lastWareCostList)),
    buildFocus: activeBuildFocus,
    fallbackMethods: activeFallbackMethods,
  };

  // Same name as an existing saved column -> update it in place (keeping
  // its column position) rather than appending a duplicate -- this is the
  // "list updating" behavior updateSaveForComparisonWarning() above warns
  // about before it happens.
  const existingIndex = savedComparisonColumns.findIndex((existing) => existing.name === name);
  if (existingIndex === -1) {
    savedComparisonColumns.push(snapshot);
  } else {
    savedComparisonColumns[existingIndex] = snapshot;
  }

  renderWareCostList();
  updateSaveForComparisonWarning();
});

// "Set Active" (see renderWareCostListHead()) -- loads a saved comparison
// snapshot's own procurement list back into the active cart, overwriting
// whatever's currently there. Same confirmation and restore behavior as
// Upload procurement list (loadCartInput's handler below): confirms only
// when there's something to actually lose, restores the list name and
// build focus, then lets renderCart() trigger a fresh runCalculation() for
// the newly active list. The snapshot itself is left untouched in
// savedComparisonColumns -- this doesn't consume or remove it, so the
// column it came from is still there to compare against afterward.
function setActiveFromComparisonColumn(index) {
  const snapshot = savedComparisonColumns[index];
  if (!snapshot) return;

  if (cart.length > 0 && !confirm("Loading will replace your current procurement list. Continue?")) {
    return;
  }

  cart = JSON.parse(JSON.stringify(snapshot.cart));
  cartNameInput.value = snapshot.name === UNNAMED_PROCUREMENT_LIST_LABEL ? "" : snapshot.name;
  // Setting .value programmatically doesn't fire an "input" event, so the
  // listener that normally keeps the overwrite warning in sync never runs
  // for this -- update it explicitly (the restored name is now, by
  // definition, this same snapshot's own name, so the warning is expected
  // to come on: saving again would overwrite the column just loaded from).
  updateSaveForComparisonWarning();
  activeBuildFocus = snapshot.buildFocus ?? null;
  activeFallbackMethods = snapshot.fallbackMethods ?? null;

  resetShipPicker();
  renderCart();
}

// --- Analysis download / upload -------------------------------------------
// Unlike "Download procurement list…" (summarize_production.py's CLI input
// shape, for portability outside this app) and "Save for comparison" (an
// in-memory-only snapshot), this captures the *entire* comparison table's
// state -- the active procurement list and every saved comparison column
// -- as one file, so it can be closed and reopened later with nothing lost.
// It intentionally serializes this app's own internal `cart` array shape
// directly (the same {shipWareId, wares_list, selections, ...} entries
// savedComparisonColumns already stores), not the CLI-compatible
// {count, wares_list} shape -- there's no need for CLI portability here,
// and doing so avoids reconstructCartEntry()'s lossy re-derivation
// (ambiguous group matching, etc.) entirely: restoring the active cart is
// just as direct a deep copy as restoring a saved column already is.

downloadAnalysisBtn.addEventListener("click", () => {
  if (cart.length === 0 && savedComparisonColumns.length === 0) {
    alert("Nothing to download -- the procurement list is empty and there are no saved comparison lists.");
    return;
  }

  const cartName = cartNameInput.value.trim();
  const analysis = {
    active: {
      cart_name: cartName || null,
      build_focus: activeBuildFocus,
      fallback_methods: activeFallbackMethods,
      cart: JSON.parse(JSON.stringify(cart)),
    },
    saved_columns: JSON.parse(JSON.stringify(savedComparisonColumns)),
  };

  const blob = new Blob([JSON.stringify(analysis, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  // The dedicated analysis-file-name-input, when set, always wins over the
  // procurement list's own name -- it exists specifically so this
  // download's filename can differ from (and outlive renames of) the
  // active procurement list.
  const fileNameOverride = analysisFileNameInput.value.trim();
  const baseFileName = fileNameOverride || cartName || "x4_analysis";
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

  if (!data.active || !Array.isArray(data.active.cart) || !Array.isArray(data.saved_columns)) {
    alert(
      'This doesn\'t look like a valid analysis file (missing "active.cart"/"saved_columns" arrays).',
    );
    event.target.value = "";
    return;
  }

  if (
    (cart.length > 0 || savedComparisonColumns.length > 0) &&
    !confirm("Loading will replace your current procurement list and all saved comparison lists. Continue?")
  ) {
    event.target.value = "";
    return;
  }

  cart = JSON.parse(JSON.stringify(data.active.cart));
  cartNameInput.value = data.active.cart_name || "";
  activeBuildFocus = data.active.build_focus ?? null;
  activeFallbackMethods = data.active.fallback_methods ?? null;
  savedComparisonColumns = JSON.parse(JSON.stringify(data.saved_columns));

  // Setting .value programmatically doesn't fire an "input" event, so the
  // listener that normally keeps the overwrite warning in sync never runs
  // for this -- update it explicitly.
  updateSaveForComparisonWarning();

  resetShipPicker();
  renderCart(); // triggers a fresh runCalculation() for the restored active list
  event.target.value = ""; // allow re-selecting the same file later
});

// --- Save / load ------------------------------------------------------------
// The saved file is shaped exactly like summarize_production.py's own input
// JSON (build_focus/search_depth/verbose/wares), plus two extra fields this
// UI adds on top -- cart_name, and each wares entry's own note -- which
// summarize_production.py itself ignores (extra keys are fine both for the
// CLI's json.load and for the API's Pydantic model), so the file is still
// also directly usable with the CLI tool.
// search_depth itself has no UI control any more (the Ware Cost List always
// shows both fixed depths -- see RAW_MATERIALS_SEARCH_DEPTH above), so the
// saved value is just that same fixed depth, purely for CLI compatibility.

saveCartBtn.addEventListener("click", () => {
  if (cart.length === 0) {
    alert("Procurement list is empty -- nothing to download.");
    return;
  }

  const cartName = cartNameInput.value.trim();

  const body = {
    cart_name: cartName || null,
    build_focus: activeBuildFocus,
    // Unlike cart_name/note, fallback_methods is a field
    // summarize_production.py's CLI genuinely already reads (see this
    // module's own docstring) -- not an extra/ignored key.
    fallback_methods: activeFallbackMethods,
    search_depth: RAW_MATERIALS_SEARCH_DEPTH,
    verbose: true,
    // note is extra (summarize_production.py's CLI ignores unknown keys,
    // same as cart_name above) -- carried along purely so re-uploading this
    // same file (loadCartInput's handler, via reconstructCartEntry())
    // restores it too. Omitted entirely rather than sent as "" when unset,
    // for a cleaner file.
    wares: cart.map((entry) => ({ count: entry.count, wares_list: entry.wares_list, note: entry.note || undefined })),
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
      shipName: "(unrecognized procurement list entry)",
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
    alert("This doesn't look like a valid procurement list file (missing a \"wares\" array).");
    event.target.value = "";
    return;
  }

  if (cart.length > 0 && !confirm("Loading will replace your current procurement list. Continue?")) {
    event.target.value = "";
    return;
  }

  cartNameInput.value = data.cart_name || "";
  // Setting .value programmatically doesn't fire an "input" event, so the
  // listener that normally keeps the overwrite warning in sync never runs
  // for this -- update it explicitly.
  updateSaveForComparisonWarning();
  activeBuildFocus = data.build_focus ?? null;
  activeFallbackMethods = data.fallback_methods ?? null;
  // A loaded file's own "search_depth"/"group_by_component_type" (if any --
  // old saves, or a CLI input file) are intentionally ignored: there's no
  // UI control for either any more, the Ware Cost List always shows both
  // fixed depths and both grouping modes (as tabs) regardless.

  const newCart = [];
  for (const config of data.wares) {
    newCart.push(await reconstructCartEntry(config));
  }
  cart = newCart;

  resetShipPicker();
  renderCart();
  event.target.value = ""; // allow re-selecting the same file later
});

loadShips();
loadMissiles();
loadDrones();
loadDeployables();
loadCountermeasures();
loadCrew();
loadBuildMethods();
