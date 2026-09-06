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

## [0.6.0] - 2026-09-06 - Production

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
