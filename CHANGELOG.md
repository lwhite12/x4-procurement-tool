# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project follows [Semantic Versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`).

**Production** marks whichever version is currently live at
[x4.fly.dev](https://x4.fly.dev) -- there's always exactly one. **Development** collects
changes already made but not yet deployed there; preview them at
[x4-staging.fly.dev](https://x4-staging.fly.dev) first. When a Development batch actually
ships to production: give it its own version number and today's date, move the Production
tag down from the previous entry onto it, and start a fresh empty Development section above
it.

## [Unreleased] - Development

## [0.7.4] - 2026-11-03 - Production

### Added

- Fleet Lists, Component Analyzer Tables, and Ship Trials loaded from a share link now track where they
  came from: a small "Loaded from share id" note with a reset button appears above the item, letting you
  revert back to exactly what was shared if you've since changed it. Re-opening the same share link while
  an unedited copy is already present no longer creates a duplicate -- it tells you it's already loaded.
  Fleet Lists sharing is now additive (loads as a new fleet alongside what you already have) instead of
  replacing your entire fleet roster.
- Turrets now respond to weapon mods (Damage, Reload Time, Rotation Speed, Beam Length/Speed/Lifetime,
  Charge/Stick Time, Mining/Surface Element Damage) the same way direct weapons do -- previously applying
  one of these to a turret via the Mod Lab had no visible effect on any of its own stats. Turrets still
  don't get heat mods, matching how the game itself works.

### Fixed

- Opening a "Load Prebuilt Tables" link (or any share link) while already on the site triggered a full
  page reload every time -- now applied in-page instantly, with no reload, as long as the app is already
  loaded. A share link opened directly (a fresh tab, a bookmark, a pasted URL) still works exactly as
  before.
- The "Loaded from share id" note and its reset button no longer make the table/trial's own box taller --
  they now sit above it instead of inside it.
- Share links generated from the production site's own default Fly hostname (x4.fly.dev) now correctly
  use the canonical x4-cost-compare.com domain instead.
- A weapon's Reload Time mod never affected its own displayed Rate of Fire (only the raw stat itself) --
  fixed alongside the turret mod work above, since both share the same formula.

## [0.7.3] - 2026-11-03

### Added

- Proving Grounds: Ship Trials can now be shared via the same Share link system as Component
  Analyzer Tables -- a new "Ship Trials" checkbox in the Share modal.

## [0.7.2] - 2026-11-03

### Fixed

- A weapon's "Damage" mod never showed up in Burst/Sustained DPS, in either the Component Analyzer or
  Proving Grounds -- Hull/Shield Damage per Shot (and the area-damage equivalents) read every damage
  component (base, hull bonus, shield bonus, unshielded-hull bonus, area damage, area shield bonus) as
  its raw, unmodded value. All five now correctly scale with an applied Damage mod, the same as the
  mod's own in-game effect.

## [0.7.1] - 2026-11-02

### Fixed

- Statistics Lab: the "Missing Mocks" warning could grow tall enough to push the actual mock-editing
  content below the fold when many tables/stats were missing mocks at once. It now has its own
  minimize button to collapse it down to just the heading.

## [0.7.0] - 2026-11-02

### Added

- **Statistics Lab**: author your own custom stats right inside the Component Analyzer -- formulas
  (sums, averages, counts) built from any existing stat, optionally mixing in stats from other
  component types, with mocked inputs (a literal value, or a real full component to stand in for
  data a table wouldn't otherwise have access to) wherever a formula needs something the table
  itself can't supply. Includes a Constants page for reusable curated numbers, group-mode mocks,
  and a read-only "Details" view for inspecting the formula behind any stat at all -- including the
  app's own built-in ones -- from both the Stat Lab and the stat picker, with no risk of editing it
  by accident.
- Dozens of new built-in stats across every component type, including weapon Burst/Sustained DPS,
  Travel Acceleration, per-group Shield MJ/Recharge Rate/Delay, and a new Avg/Min/Max Equipped Cost
  per ship (sums every actually-equipped component's own price, correctly capped to each slot
  type's real count rather than whatever happens to be mocked).
- **Proving Grounds** (new top-level page): a Ship Trials comparison tool. Add ships straight from
  your saved loadouts, from a Fleet List, or build one fresh in an embedded Ship Builder -- edit any
  Trial ship's loadout later in place, with an "Edited" badge once it's drifted from the original.
  Pick any column as the comparison baseline (click to set it, click that same column again to
  clear it) for colored value/percent-change diffs against every other column, the same comparison
  language the Cost Analyzer already used.
- The Cost Analyzer's own comparison baseline no longer has to be whichever fleet you're actively
  editing -- click "Focus" on any column instead, with the same colored diffs, and fleet columns are
  no longer silently reordered around whichever one that is.
- "Load Prebuilt Tables": one-click, ready-made Component Analyzer comparison tables covering every
  weapon/turret/shield/engine/thruster/missile/economy-ware category, split by size (S/M/L/XL)
  where that matters.
- Both saved-loadout pickers (Ship Trials' own "Add Loadout Ship", and the Fleet Planner's "Select
  Filter Loadout") now have the same Size/Purpose/Type/Race/Vendor/Build Method filters as the main
  ship picker, plus free-text search by ship name or loadout name.
- Modifications Lab: Copy/Paste a mod between slots, a real cost breakdown (wares + credits) for
  every editable mod, and a Roll button with a running cumulative cost.
- Ship Builder: a Chassis Mod that raises missile/drone/deployable/countermeasure capacity now
  updates those limits immediately, and automatically scales back an already-maxed selection if the
  mod is later weakened or removed.
- Static site assets now always revalidate with the server instead of being cached indefinitely, so
  a deployed update is visible without a hard refresh.
- **User Guide** (new top-level page): a full written guide covering every page and feature, with
  real site icons/stat-tag badges injected directly into the text, and a sticky table of contents
  that tracks scroll position as you read.
- New **Production** stat group: per-build-method raw-material costs (e.g. "Universal - Energy
  Cells"), generated directly from the game's own production-ware data rather than hand-maintained,
  shown as whole numbers with their own red "Production" stat tag.
- Proving Grounds: new Trials now start pre-populated with a sensible default stat set instead of an
  empty table.

### Changed

- ~23 existing stats (Max Speed, Shield MJ, turn rates, and more) now correctly read a component's
  modded (Post Mod) value instead of its unmodded base value, so an applied Mod Lab modification
  actually shows up where you'd expect it to.
- Shield (MJ)/Recharge Rate/Recharge Delay are no longer a naive sum across every mounted shield --
  rewritten to match how the game itself actually computes them (the main shield slot alone, plus a
  real per-hardpoint-group average for bonus shields), verified against real in-game loadouts.
- Cost Analyzer: comparing fleets no longer uses a separate "Focus" button -- click a fleet's own
  name/icon in the comparison header to set it as the baseline (click again to clear it), the same
  single interaction everywhere else in the app. This is completely independent of the Fleet
  Planner's own active fleet -- comparing fleets in the Cost Analyzer never changes what the Ship
  Builder is editing.
- Ship picker list: ships are now grouped by chassis -- the same underlying hull model shared across
  races (e.g. every race's destroyer built on the same hull) sorts together -- and sized smallest to
  largest (S, M, L, XL) instead of largest to smallest.
- About page: "Future Plans" is now a short pointer to the GitHub issues page instead of a
  hand-maintained list, since the roadmap had grown too large to keep duplicated in two places.

### Fixed

- A brand-new session with nothing saved yet could show cross-component Proving Grounds/Statistics
  Lab stats as silently wrong or missing on the very first page visited, until an unrelated picker
  happened to be opened elsewhere first.
- A pure area-damage weapon (the Paranid Blast Mortar/Flak family) no longer silently breaks its
  own Hull/Shield Damage per Shot calculation.
- Exporting loadouts back to the game used to silently drop station modules and any ship loadout
  that failed to parse -- both are now preserved in the exported file.
- Some equipment that's a real, distinct item but marked internally as an "alias" of another ware
  (a handful of turrets/shields) could be wrongly treated as incompatible in mocks, the Statistics
  Lab, and Ship Trials. Alias resolution now matches how the rest of the app already looks up wares.
- Proving Grounds: a Trial's stat table could show its "Stats" label column visibly out of alignment
  with its value columns, row by row.
- A weapon with no heat generation at all now correctly contributes its full burst DPS to a ship's
  Sustained DPS total instead of being dropped.

## [0.6.0] - 2026-09-06

### Added

- **New Component Analyzer page**, for building side-by-side comparison tables of any
  component type, independent from the Fleet Planner/ship-builder flow:
  - Stat catalogs for all 12 component types: Chassis, Engines, Shields, Weapons, Turrets,
    Thrusters (including real flight-performance numbers recovered from a
    previously-unscanned game-data path), Software, Drones, Deployables, Countermeasures,
    Crew, and Economy Wares.
  - Any number of independent tables at once, each with its own component-type picker,
    a searchable/filterable component-selection modal (with select-all/none and per-group
    filters), a grouped stat selector (with a per-group All/None button), and its own sort
    column/direction.
  - Editable table/tab names via a dedicated edit button, instead of live-editable text.
  - "View in Component Analyzer" button on the ship builder and every equipment picker,
    opening a new table pre-populated with whatever's currently selected (and closing the
    picker automatically); the new table gets a contextual title like "<chassis> Chassis
    Fleet Planner View".
  - Export to JSON, CSV (a zip of one file per tab), or XLSX (a zip of one workbook per
    table, one sheet per tab), with a per-table selector, plus a matching Import button.
  - A new "Component Analyzer Tables" option in the Share tool, with its own cloud save key.
  - Its own top-nav icon and page, extracted from the game's own "high-tech station" symbol.
- Real, per-language display names (instead of raw internal codes) for ship type, cargo type,
  equipment compatibility class, ammunition compatibility, thruster class, and deployable
  type -- sourced directly from the game's own text.
- Ship builder now shows a ship's special equipment-compatibility requirements (e.g. "Mining",
  "Advanced") both in the chassis summary and next to the weapon/turret slots that need them.
- A half-size Modifications Lab button on every ware in the ware list, scoped to that ware
  only, alongside the existing "apply to all" button.
- A new Fleet Statistics panel.

### Changed

- "Production Wares" component table renamed to "Economy Wares", now backed by its own
  dedicated endpoint instead of the general wares list.
- The Select Components table keeps its All/None header and component-name column frozen
  while scrolling, instead of scrolling them out of view.
- Build method, missile weapon system, and drone purpose stat columns in the Component
  Analyzer now show real display names instead of raw internal codes.
- All of the above additions -- the entire Component Analyzer, the Modifications Lab changes,
  and every new real-name mapping -- are fully translated across all 14 supported languages
  (~255-262 new keys each).

### Fixed

- DLC ship cargo capacities were missing entirely for several expansions (Boron, Split,
  Pirate, Timelines, and both mini-DLCs) -- their storage macros live at a path the
  extraction pipeline never scanned.
- Share links for Component Analyzer tables were silently broken, since the share-request
  type only ever allowed an object payload, not the list-shaped one this section needed.
- Two real cross-table name collisions in the localization data (deployable type "mine" vs.
  ship purpose "mine"; ammunition "torpedo" vs. missile weapon system "torpedo") were causing
  one to silently show the other's translation.

## [0.5.1] - 2026-08-31

### Fixed

- German ship/equipment names using a compound word with an escaped hyphen in the game's own
  text (e.g. "Expeditions\-schiff", "Silizium\-karbid") showed the literal backslash instead
  of a clean hyphen -- affected 24 names across ships/turrets/weapons/wares.

## [0.5.0] - 2026-08-31

### Added

- Full localization of this app's own UI text (buttons, labels, tooltips, confirmation
  dialogs, every modal, the About page) into German, Spanish, French, Italian, Portuguese
  (Brazilian), Czech, Polish, Russian, Ukrainian, Chinese (Simplified), Korean, Japanese,
  Bulgarian, and Turkish -- a language picker in the header switches instantly.
- Game-data localization (ship/ware/equipment names, ship types, build methods, crew roles,
  factions, races, purposes, and each installed DLC's own display name), sourced directly
  from the game's own language files with an automatic fallback to English wherever a
  translation is missing.
- New structured lookup tables (ship types, build methods, crew roles, purposes, races,
  and each ship/equipment's real design race) replacing several places that previously
  guessed at this data from ware-id string prefixes or hardcoded English text.

### Changed

- Ship picker: a ship with more than one real design race now shows one badge per race,
  not just one.
- Equipment picker, Ware Cost List, and Ware Price Override tool now show real localized
  ware/equipment names instead of raw internal ware IDs or English-only names.
- Loadout Manager buttons (Import/Export/Clear) now lay out side by side instead of stacked.

### Fixed

- Hostile-only equipment (Kha'ak/Xenon turrets, shields, etc.) is now excluded from other
  factions' equipment lists using the game's own real per-ware design-race data, instead of
  guessing from the ware_id string -- fixes at least one alias-macro case the guess got wrong.
- About page's "Built From" version table was always showing in English regardless of the
  selected language (a timing bug -- it fetched before the language picker had finished
  initializing).

## [0.4.0] - 2026-08-28

### Added

- About page "Built From" section: this tool's own version alongside the base game's and
  every installed DLC's real version (resolved from the game's own install files, not
  hand-entered).
- Ship picker: every ship now shows one badge per real vendor/owner faction (not just its
  major race), tinted to that faction's actual in-game color -- including minor/story
  factions (Buccaneers, Hatikvah Free League, Scale Plate Pact, etc.), pulled from the game's
  own UI color palette rather than picked by hand. Hovering a badge shows that faction's real
  display name.
- Vendor and Race filter groups in the ship picker, alongside the existing Size/Purpose/Type
  filters -- Vendor filters by any of a ship's real vendor/owner factions (badge + real name),
  Race filters by the ship's own 3-letter design-race code (colored the same as the picker's
  own race label under each ship's name).
- A staging deployment at [x4-staging.fly.dev](https://x4-staging.fly.dev) for previewing
  changes before they go live, plus this changelog's own Production/Development convention
  and `DEPLOY_PROCESS.md` describing the full release process.

### Changed

- Size filter box now matches the fixed height of the Purpose/Type/Vendor/Race boxes, instead
  of shrinking to fit its own shorter list.

## [0.3.1] - 2026-08-26

### Added

- A fleet list's Build Method Priority is now auto-seeded from its first ship's own primary
  build method (e.g. adding an Asgard first defaults the whole list to Terran) -- set once,
  so it stays freely editable afterward and is never re-ordered automatically again.

### Changed

- Build Focus and Fallback Methods merged into a single, reorderable Build Method Priority
  list, used consistently across the UI and API -- the top entry is tried first for every
  ware, with each one below it acting as that ware's own fallback.

### Fixed

- The production-cost pipeline was silently dropping DLC patches to existing wares' build
  methods (e.g. the Terran build method for XL All-Round Thrusters Mk3, needed to build a
  pure-Terran Asgard) -- several hundred DLC recipe patches across every expansion are now
  included.
- Kha'ak/Xenon-only build methods are no longer hidden from price/cost comparisons, so Xenon
  and Kha'ak ships can now be viewed and priced like any other (still not player-buildable or
  pilotable, same as before).

## [0.3.0] - 2026-08-23

### Added

- Share links: generate a link that loads a copy of your Fleet Lists, Ware Price Overrides,
  and/or Ship Loadouts on another browser -- pick which of the three to include, each one
  independently, from the new "Share" button in the header.
- A confirmation warning before downloading Export Loadouts, since overwriting your real
  `loadouts.xml` with the downloaded one isn't guaranteed safe -- recommends backing up your
  loadouts file first.
- A "Future Plans" section on the About page, covering two bigger features on the roadmap:
  user accounts with saved/recallable fleet lists, ship loadouts, and price override presets;
  and support for non-English game language files.

### Changed

- "Add To Fleet List" (top copy) moved up out of the ship builder to sit next to "Add To
  Saved Loadouts", so both are reachable together without scrolling down first.

## [0.2.0] - 2026-08-22

### Added

- Fleet Lists: create, rename, and delete multiple named fleet lists via tabs, each one live
  and directly editable (no more destructive "load" step that overwrote the active list).
  Each tab shows its lead ship's own class icon, tinted and boxed the same way the in-game
  map marks a player-owned/selected object.
- Cost Analysis now recalculates a fleet list's cost only when that list has actually
  changed, instead of on every edit.
- Ware price override tool: a popup listing every ware in the database with its
  min/average/max price and an editable override, plus a persistent summary of active
  overrides.
- Ship "purpose" (AI role classification, e.g. fighter/trader/miner/builder) added to ship
  data.
- Fleet lists, price overrides, imported loadouts, and filter selections now persist across
  page reloads (`localStorage`).
- High/Minimum Preset buttons generalized to every equipment section (ranked by average
  price), plus ship-wide versions and duplicate "Add To Fleet List"/"Add To Saved Loadouts"
  buttons at the top of the ship builder so they're reachable without scrolling.
- GitHub source link and bug-report link added to the About page.

### Changed

- Fleet Planner reorganized into a two-column layout (ship builder on the left, fleet lists
  on the right), with every section's title moved onto its own box outline.
- Cost Analysis's column headers now match the Fleet Lists tab bar exactly (same ship icon,
  color, box, and click-to-switch behavior), with the Build Focus control kept as a
  separately clickable line under each fleet's name.

### Fixed

- Fleet Planner content no longer stayed visible underneath Cost Analysis/About when
  switching tabs.
- Page no longer shifts sideways when switching tabs (scrollbar space is now reserved
  consistently across pages).

## [0.1.0] - 2026-08-10

Initial tracked release.

### Added

- Ship picker with Size/Type filters (grouped by size, then military/civilian/utility
  category, then alphabetically; types spanning multiple sizes are split into separate
  filter entries).
- Per-hardpoint-group equipment loadout builder (weapons, turrets, shields, engines,
  thrusters, software) plus ammunition, drones, deployables, countermeasures, and crew
  sections.
- Procurement list with per-entry, editable quantities (ctrl-click to step by 10,
  shift-click to jump to max).
- Production cost calculator with configurable build focus, fallback build methods, and
  search depth.
- Import of saved game loadouts (`loadouts.xml`, by file upload or by local path when
  running locally) and raw pasted XML loadouts.
- Download/upload of procurement lists and cost analyses as JSON.
- Deployed at [x4.fly.dev](https://x4.fly.dev) and
  [x4-cost-compare.com](https://x4-cost-compare.com) via Fly.io.
