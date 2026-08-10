# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project follows [Semantic Versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`).

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
