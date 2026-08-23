# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project follows [Semantic Versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`).

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
