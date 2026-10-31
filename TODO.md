# X4 Fleet Planner — Future Ideas / Backlog

Large ideas not yet scheduled. Pick one up whenever; check items off as they land.

## 1. Import and export of ship builds from game files - DONE

## 2. Integration with Roguey's site to populate builds
- [ ] **On hold** -- Roguey's own `get_ship.js` opens with "please do not copy this code without permission." Revisit once this app is public and a credit/reference link to roguey.co.uk can be added near the feature (or site-wide); worth directly asking Roguey for permission at that point too.
- [x] Export-XML reading -- already works today. Roguey's "Export loadout" button produces a real `<loadout>` element structurally close enough to a real save (same macro/path/software/ammunition/crew shape, just missing `version`/`revision` attributes) that it already imports cleanly through this app's own `import_loadouts.py` with no changes needed. Verified 2026-08-09 against a hand-made "ares_test" loadout.
- [ ] Share-link (read + generate) -- full analysis done 2026-08-09, written up here so it doesn't need re-deriving:
  - **URL shape**: `roguey.co.uk/x4/ships/<ship_macro>/w=<weapon_code>&t=<turret_code>&tg=<tg_code>&s=<subsystem_code>` (no `?` -- these are literal path segments, not a real query string).
  - Each code is a concatenation of 2-digit zero-padded `<select>.selectedIndex` values -- **not ware ids**. `w` = one pair per weapon slot, in slot order. `t` = one pair per turret slot. `tg` = two pairs per turret-group (turret index, then shield index). `s` = always exactly 3 pairs, fixed order: engine, thruster, shield.
  - The index is relative to a *per-slot filtered dropdown list*, built client-side by `populate_equipment()` in `/x4/ships/js/get_ship.js` (unminified, public) by iterating a cache object's own key order and applying that slot's own rules: size match; Boron-exclusive on L/XL hulls only; Xenon/Kha'ak-exclusive; a hardcoded Hyperion special case; missile-launcher-slot matching. Reproducing a link therefore means replicating that exact filter, in that exact order, per slot -- not just looking up a ware id.
  - Reference data lives in separate public cache files loaded on every ship page: `/x4/weapons/cache/x4_weapons.js`, `.../x4_turrets.js`, `/x4/shields/cache/x4_shields.js`, `/x4/wares/cache/x4_wares.js`, `/x4/engines/cache/x4_engines.js`, `/x4/thrusters/cache/x4_thrusters.js` -- plain JS object literals, one entry per ware, in the exact order `populate_equipment()` iterates them.
  - Per-ship slot metadata (`size`/`compatibility`/`mlauncher` for every weapon/turret/turretgroup/shield/engine slot, plus `ship_id`) is embedded directly in that ship's own page HTML as an inline `ship_data = {...}` `<script>` block -- server-rendered per ship, not fetched separately.
  - **Confirmed fragile**: spot-checked the "ares_test" example against the live cache -- weapon slot indices 13/29 decoded to the wrong ware (a consistent +1 offset from what the exported loadout XML actually has). Root cause: the test loadout's `<patches>` list DLC version "800", but `get_ship.js`'s own changelog says "20/6/2026 - Updated for v9.0 stuff" -- the live cache reflects a newer weapon roster than whatever was live when the link was generated, and nothing in the link itself records which cache snapshot to decode against. Any reader/generator we build carries the same exposure: correct only against whichever cache snapshot is live *at the moment of use*, with no way to detect drift after the fact.
  - **Planned approach** (once unblocked): (1) fetch the target ship's Roguey page and parse its embedded `ship_data` for per-slot size/compatibility/mlauncher; (2) fetch Roguey's own reference-data cache files for the exact iteration order -- both are public static assets already served to every visitor, nothing gated or scraped past what a browser already loads; (3) reimplement `populate_equipment()`'s filter independently, in our own code against our own data model, rather than copying their JS/cache files verbatim -- interoperable without copying; (4) to generate a link: map each of our own selected ware_ids to its computed index in the replicated per-slot filtered list, zero-pad, assemble the URL; (5) to read a link: reverse that -- parse the codes, look up each index in the same replicated filtered list.

## 3. Ship compare UI cleanup - DONE
- [x] Build methods lister and defaults -- each comparison column has its own build focus (dropdown) and its own editable, reorderable fallback-methods list, via a real modal under the column name; defaults to the backend's curated, ordered BUILD_METHODS list
- [x] Comparing prices between different build methods
- [x] Re-running the comparison updater

## 4. Procurement list / builder cleanup - DONE
- [x] Shift-click to max/min/fill remaining
- [x] "Minimize loadout" option in the procurement list
- [x] Optional notes list, shown under the ship type name in the list
- [x] Duplicate-looking entries in equipment dropdowns -- root cause confirmed: real, distinct ware_ids marked as `alias="..."` of another ware right in the macro XML (a redundant model variant, `<hull integrated="1"/>` instead of a real hull value). generate_ships_table.py's parse_equipment_component_wares excludes a macro carrying that attribute only when its (size, compatibility) exactly matches its alias target's -- a first pass that excluded on `alias=` alone was too aggressive and wrongly dropped genuinely-different tiers sharing a name (e.g. it removed the Paranid Blast Mortar Turret, `turret_par_m_shotgun_01_mk1` at `advanced` compat, because it's marked as an alias of the `standard`-compat `_02_mk1` version -- caught when the Hydra lost access to it). The compat-aware two-pass fix restores those, resolving all known player-faction collisions. Two remain: Kha'ak and Xenon M shields (`shield_kha_m_standard_01/02_mk1`, `shield_xen_m_standard_01/02_mk1`) -- neither macro carries the `alias=` marker at all (a different, unmarked duplicate shape), but both are hostile-only factions so this is unlikely to ever surface in the picker for a real player-ownable ship. Low priority.
- [x] Add remaining buildable items from ship parts: crew, countermeasures
- [x] Investigate and fix compatibility groups — currently a singular tag, should match the real tag set. Root cause: the old model collapsed each equipment mount down to one hand-picked "tier" token (standard/advanced/mining/...) via a curated priority list, so any slot gated by a tag outside that list (e.g. L/XL "spinal" main guns locked to their own hull, tagged like `arg_destroyer_01`/`ter_destroyer_01`) resolved to no compatibility at all and showed zero available weapons — this hid every race's destroyer main gun and several XL battleships' main guns entirely. Fixed by replacing the single-token model with full tag-set subset matching: both a ship connection and an equipment mount now store their *complete* remaining tag set (after stripping type/size/bookkeeping tokens), and an equipment item is a valid option only when its own tag set is a subset of the ship connection's tag set (the ship's slot may offer more than the equipment needs, but the equipment can't need something the slot doesn't offer). Verified against real cases: Behemoth/other race destroyers' main guns now correctly show their one dedicated gun, Boron's destroyer (which uses a plain `advanced` tag, no hull lock) still shows its one advanced-tier gun, the Split XL battleship's `standard`+hull-lock combo main gun correctly shows all 4 ordinary standard L weapons, and mining ships' weapon mounts still correctly accept both mining lasers and ordinary combat weapons (the case most at risk of regressing under a naive full-subset rule). Duplicate-dropdown collision count and the Hydra/Blast Mortar fix (see above) both re-verified unaffected. Follow-up bug this surfaced: Xenon shields were showing up as equippable on ordinary player destroyers -- turned out to be a real, pre-existing gap (not caused by the subset-matching change): roughly half of all Xenon/Kha'ak equipment has a mount connection tagged just `standard`, with no faction-exclusivity tag at all, so it physically passes the same mount-compatibility check as ordinary equipment. That's a separate axis from mount compatibility (who's allowed to own/buy it, not whether it fits), so query_ship_components.py's matching_items() now also excludes any equipment built by a hostile-only faction (Xenon, Kha'ak) unless the ship being queried is itself that faction (a few appear in the ship picker for comparison purposes). Derived from each ware's own ware_id naming convention rather than its owners/makerrace column, since that column is sometimes simply missing on the game's own data (e.g. shield_xen_m_standard_02_mk1 has no makerrace attribute at all). Verified: no Xenon/Kha'ak equipment leaks into a 15-ship random sample of player-faction ships, and Xenon ships still see their own faction's equipment.
- [x] High/Minimum Preset buttons (2026-08-10) -- originally software-only (High Preset picked the highest-`mk` option per slot, Minimum Preset the lowest-`mk` option in required slots only, clearing the rest); generalized to every dropdown-based section (Engine, Thruster, Weapon, Missile Launcher, Shield, Turret, Software), ranked by `price_avg` instead of `mk` so the same logic applies uniformly everywhere. "Required slot" reused the existing `requiredGroupLabel()`/`*`-marker mechanism (Engine, Thruster, the 3 required software items) rather than inventing a new concept. Also added ship-wide High Preset/Minimum Preset buttons next to "Select loadout", which just run every section's own preset in turn. Deliberately does *not* cover Ammunition/Drones/Deployables/Countermeasures/Crew -- those are quantity/counter-based (many units per slot), not a single per-slot pick, so "highest/lowest price" doesn't translate the same way; would need its own design if wanted.

## 5. Copyright/attribution notice
- [x] Footer notice crediting Egosoft -- added 2026-08-09. Egosoft's official Fan Content Policy (egosoft.com/community/fanpolicy_en.php) requires, for non-commercial fan websites/tools: (1) a specific disclaimer text displayed visibly, and (2) attribution + a direct link to the game's official Steam/GOG product page. Both now live in `index.html`'s `#site-footer`, styled in `style.css`. This project fits the policy's Section 3 "Fan Websites & Screenshots" bucket ("screenshots, artwork, information, and data from our games on non-commercial fan websites is permitted, provided you clearly attribute... and include a direct link" -- exactly what's now in place), the same bucket Roguey's own site operates under.
- [ ] Two narrower, non-blocking items surfaced while researching the above, worth a second look eventually (not urgent -- neither stopped the footer from shipping):
  - The extracted ship-icon PNGs (`data/images/ships/symbols/`, converted from the game's own DDS textures) are the one piece of this project's data that's a literal "texture" rather than numeric/textual ware data -- the policy's Section 4 (aimed at standalone fan *games* built from ripped models/textures/audio/code, not really this kind of tool) bans that category by name, though Section 3's broader "screenshots, artwork... from our games" language for fan websites plausibly covers it too, and displaying game icons is extremely common practice across X4 fan sites/wikis without apparent pushback.
  - The app's own name uses "X4" directly ("X4 Procurement Planner"). Section 4 says using "X", a game title, or Egosoft logos in an app's branding "requires prior written consent," but immediately carves out "descriptive references to the X-Universe... where they do not imply official licensing or sponsorship" -- which this plausibly is, especially with the disclaimer now visible. Roguey's own site is branded `roguey.co.uk/x4/...` the same way.
  - Neither is a copy-and-paste question -- if it matters later (e.g. before a more public launch), the cleanest path is asking Egosoft directly, per the "prior written consent" language.

## 6. Language support from different language files

## 7. Underlying data explorer and SQL query runner

## 8. Support for different mods from game files
- [ ] Since this app generates the entire database including production wares and the front end from the game files, it might be possible to add support for mods like SWI, VRO, XR Ship pack, etc. out of the box. Then a user could clone the repo, set any custom mods list they prefer on their system, and generate the sql database and local explorer UI which they can run on their own machine.
  - Start with a mod which only adds ships without adding classes or other new features that would probably require additional handling. My guess off hand is that XR Ship Pack is a good candidate, I believe it is only intended to add new ships from the previous games so it should just be a big ship list without feature changes.
- [ ] Installer with DB manager for multiple install support? This would be used to allow different DLC sets, including mods. In a perfect world you could open the installer, view various "installs" which have different configurations. For example, one for base game with DLCs, one for SWI, one for VRO, one for XR Ship Pack, etc. Obviously this would require ensuring the game file reader / database generator / aggregator and front end can dynamically support whatever changes those mods incorporate. This is a huge amount of work, so the installer is a low priority.

## 8. Additional information page
- [x] Bug reports (on github)
- [x] GitHub source link
- [ ] Installation instructions with links to required tools (e.g. XRCatTool)

## 9. Additional analysis ideas (brainstormed 2026-08-10, not yet designed/built)

### Production wares deep dive / Raw resources deep dive tabs -- supersedes the single "Materials analysis section" idea below
- [ ] Refined 2026-08-10: instead of one generic ware-level section, two separate tabs mirroring the existing Total Cost Breakdown's own tier split (Credit Cost / Production Wares / Raw Materials -- see `appendWareCostListTier()` in app.js) -- **Production wares deep dive** and **Raw resources deep dive**.
- [ ] Top-level grouping in each tab = one dynamically generated section per ware (not per component-type/tier the way the existing breakdown tabs group), covering every distinct production ware / raw material involved. **Open question**: scoped to the current procurement list (cart-scoped, matching how the existing Ware Cost List tabs work today) or database-wide regardless of cart (matching how the original "Materials analysis section" idea just below was framed as "independent of the procurement list")? These are different features -- worth deciding explicitly before building either.
- [ ] Per-ware section stats:
  1. Total ware amount cost -- total credits spent on this ware given however much of it the current build/list actually requires.
  2. Ratio of ship cost per ware -- what share of the overall ship/procurement-list cost this one ware accounts for.
- [ ] Color these numbers using the same dynamic price-coloring convention X4's own UI uses when setting trade prices (a gradient across a ware's own min/avg/max range) -- exact color mapping needs confirming against the actual in-game UI before implementing, not just assumed.
- [ ] The timing-stat ideas below (produced value/hour, cost/hour, profit/hour, cargo throughput) fit naturally as additional per-ware stats within the **Production wares deep dive** tab specifically, since they depend on a recipe/production_time existing for that ware -- raw materials generally don't have one.

### Materials analysis section -- ware-level, independent of the procurement list (original framing, see refinement above)
- [ ] New top-level section/tab, separate from the procurement-list-focused tabs (Total Cost Breakdown / Component Type Cost Breakdown) -- ranks/inspects wares purely on their own economic stats, with no ship or cart involved.
- [ ] Value per cargo space -- `price_avg / unit cargo volume`, to rank goods by trade value per cargo hold slot (a hauler's "best cargo to run" question). **Blocked on a data gap**: no per-ware cargo volume is currently extracted anywhere in generate_ships_table.py / stored on economy_wares_base -- would need a new column sourced from wares.xml's own volume attribute before this stat is computable at all.
- [ ] Cost/value transformation (margin) -- input cost (`Σ input.amount × input.price_avg`, summed over a ware's recipe in production_wares) vs its own market price -- flags which wares are worth producing vs buying outright.
- [ ] Produced value/hour -- `produced_amount × price_avg / production_time` -- throughput-adjusted, not just per-unit margin.
- [ ] Other timing stats worth considering alongside produced value/hour:
  - Cost incurred per hour -- `Σ input.amount × input.price_avg / production_time` -- the "spend rate" to run this production step, useful paired with value/hour.
  - Profit per hour -- (produced value/hour) − (cost incurred/hour) -- combines margin and throughput into a single ranking number; probably the best single "efficiency" stat, since plain margin % ignores speed and plain value/hour ignores input cost.
  - Cargo throughput -- output cargo volume produced per hour (`produced_amount × unit volume / production_time`) -- ties the cargo-space idea into the timing stats, a hauler-oriented view ("how much cargo moves through this chain per hour") rather than a pure-credits view. Same volume-data dependency as the value/cargo-space stat above.
  - Time to fill one cargo hold -- given a hold size, `hold_size / (produced_amount / production_time)` -- a more concrete/intuitive number than a raw hourly rate.

### Total production time -- procurement-list-based
- [ ] Recursively sum production_time through the same expansion loop summarize() already uses for cost (aggregate_target_wares / fetch_all_production_rows), producing a "total production time" per procurement list configuration -- comparable across different fleet builds, the time equivalent of the existing Total Cost Breakdown.
- [ ] Would land as a new top-level section under Total Cost Breakdown (parallel to the existing cost breakdown), not a replacement for it.
- [ ] Open design question to settle before building: is this an additive sum across every recipe step in the recursive tree (`production_time × number of production runs at that step`), mirroring how cost is already summed regardless of real-world parallelism -- i.e. "total machine-hours to build this from raw materials with exactly one of each module" -- or an attempt at true wall-clock/critical-path time (which would need to model how many production modules run simultaneously)? These two interpretations produce very different numbers.
- [ ] Flagged by the user as "not necessarily a useful stat, but an interesting one" -- lower priority than the Materials analysis section above.

## 10. Persist browser state across refresh - DONE
- [x] Implemented 2026-08-22 via `localStorage`, not literal cookies -- no server round-trip needed for this (it's all client-side already), and localStorage avoids cookies' per-request overhead and small (~4KB) size cap, which the imported-loadouts working set in particular could exceed. Saved: procurement list + its name, saved comparison columns, the Active column's build focus/fallback methods, configured price overrides, the imported-loadouts working set, and the Size/Purpose/Type filter selections. Deliberately NOT saved: the ship currently mid-edit in the builder (currentShip/missileAmounts/etc.) -- treated as an unsaved draft, same as already happens today if you clear the picker without adding it to the list. Hooked into a handful of existing render choke points (`renderShipOptions()`, `renderCart()`, `renderWareCostList()`, `updateLoadoutManagerBtnStates()`) rather than threaded through every individual mutation -- see `saveState()`'s own comment in app.js. Guarded by a `stateReady` flag so the initial pre-restore render (inside `loadShips()`) can't clobber a real saved session with empty defaults before restoration runs.

## 11. Ware price override tool (brainstormed 2026-08-10)
- [ ] Cross-cutting feature -- affects section 9's new Materials analysis tabs above as well as the existing Total Cost Breakdown / Component Type Cost Breakdown tabs, since it changes the price every cost calculation uses, not just one section's display.
- [ ] Clickable button opens a popup listing every economy ware, with its price_min/price_avg/price_max, and an editable override-price input box per row.
- [ ] Backend groundwork already exists: the price-summary request model (`api.py`, `PriceSummaryRequest` around line 303) already accepts an optional `price_overrides: dict[str, float]`, already threaded through `summarize_prices()`/`summarize_prices_by_category()` inside `/api/price_summary`. This is primarily a frontend feature -- building the popup table UI and wiring its state into the existing request payload -- not new backend plumbing.
- [ ] When the popup is closed, show a small persistent list of currently active overrides somewhere in the UI (visible without reopening the popup), with a way to clear individual overrides from that compact view too.
- [ ] Color the typed number in the override input box using whatever color convention X4's own map/trade UI uses for prices (cheap vs expensive, likely a gradient similar to what's already noted for section 9's per-ware stats above) -- needs research into the actual in-game colors/thresholds first, not yet started.

## 12. Clean up the AI generated code
- [ ] Have some self respect

## 13. User-based state management / recall feature (brainstormed 2026-08-23)
- [ ] Surfaced while scoping a fleet/loadout share-link feature (see the UUID-backed-server-storage
  option under that discussion) -- if there's eventually a user login, the server could store and
  serve saved data configurations per user rather than just anonymous one-off share links.
- [ ] Would naturally generalize beyond just share links to other things worth persisting/recalling:
  ship loadout sets, saved fleets for comparison, ware price override presets, etc.
- [ ] Framed as one general "state manager" feature encompassing all these different kinds of
  user-persisted data/configs, rather than a bespoke mechanism per data type.

## 14. Path to 1.0 (brainstormed 2026-10-27)
Recorded as-is for an audit tomorrow -- given how much landed this session (the whole Statistics
Lab/mock engine rework, the S/M/L/XL prebuilt ships tables + "Load Prebuilt Tables" band, the
group-mode/group_sum shield and weapon-size-split fixes), some of these may turn out to be already
partially or fully done; don't assume any item below is untouched without checking first. Not yet
started on any of them. First version actually called `1.0` -- `VERSION`/`CHANGELOG.md` are still on
`0.6.0` as of this writing, no `1.0` tag exists anywhere yet.
- [x] Confirm Mod Lab modifications applied to a *mock* component actually propagate into derived
  damage/flight stats, and that the affected cells get the same mod-tier color highlight a real
  row's modified cell gets. DONE (2026-10-28): found two real gaps, both fixed --
  (1) thrusters never had `_modifier_mod`/`_post_mod` siblings for `thrust_pitch`/`thrust_yaw`/
  `thrust_roll`/`thrust_strafe` at all (confirmed live: yaw/pitch/roll rate and strafe speed/
  acceleration now correctly reflect an applied "engine"-category mod, e.g. Twister/Rotation
  Thrust Mod); (2) a mod applied to a MOCKED cross-component entry (e.g. a Chassis mock inside an
  Engine table) already changed the computed value but never colored the cell -- added
  `crossComponentMockModHighlight()`, which walks the mock-resolution trace and takes the highest
  mod tier across every contributing source (same-row AND cross-component mocks), per the
  "highest tier wins on conflict" spec. Verified live both ways, no regression to the existing
  same-component-type highlight.
- [x] Prebuilt tables for Engines, Thrusters, Shields, Weapons, Missiles, Turrets, Economy Wares.
  DONE (2026-10-27/28): all 7 categories uploaded and wired into the "Load Prebuilt Tables" band
  (Weapons/Turrets/Thrusters as S/M/L/XL dropdowns, Missiles/Economy Wares as plain one-table
  buttons since they're not size-tiered). Small Turrets specifically still has no uploaded table.
- [x] i18n solution for the prebuilt tables' own *content* (table/tab titles baked into each
  uploaded JSON payload). DONE (2026-10-27): `src/prebuilt_table_titles.py`, a curated
  key->locale translation table the backend applies on the fly (`GET /api/share/
  component_analyzer_tables/<uuid>?lang=<code>`) only for the band's own known table keys -- a
  real user's own shared table is never touched. Covers every title/tab string found across all
  25 currently-uploaded prebuilt tables.
- [x] Proving Grounds: direct ship/fleet performance comparisons pulled straight from a user's real
  Fleet Planner loadouts (not just mocked chassis). DONE for Ship Trials (2026-10-28): page
  scaffold (nav tab/icon, Ship Trials/Fleet Trials toggle built as two buttons inside the page's
  own `<legend>`), a `shipTrials` array of independently-titled Trials (mirrors
  `componentAnalyzerTables`' own add/remove/minimize/rename list), a transposed table per Trial
  (ships as columns with chassis icon + name header, stats as rows, a vertical stat-set tab stack
  switching which rows show), "+ Add Ship" sourced from `importedLoadoutsResult.ships` (the Loadout
  Manager's saved loadouts) with each ship's own `shipMocks` auto-built from its real
  `selections`/`missileAmounts`/etc., keyed by a per-column `instanceId` (not `ware_id`) so two
  different loadouts of the same hull render as independent columns -- verified live against real
  loadout screenshots, exact match. Found and fixed two real formula gaps along the way (now fixed
  for all of Component Analyzer too, not just Ship Trials): `hull_damage_per_shot`/
  `shield_damage_per_shot`'s missile-mock fallback used to misfire for a pure area-damage bullet
  (PAR M Blast Mortar/Flak family -- real `areadamage_value`, no missile involved at all); the
  ship-blended `sustained_dps_ship_contribution` didn't yet handle a weapon with no heat generation
  (now contributes `burst_dps` straight to the ship total, unthrottled, same as the per-weapon
  stat already did). Fleet Trials is still just the "Under Construction" placeholder -- explicitly
  deferred, see item 16 below. Mod Lab support for a Trial's own ships is NOT yet built -- also
  item 16.
- [ ] Once all of the above lands: commit, write up a full CHANGELOG entry summarizing everything
  since the last Production tag, bump VERSION, deploy, and draft a Reddit update post for the
  community covering the whole batch of changes.

## 15. Post-1.0: Mod Support Era (brainstormed 2026-10-28)
Explicitly scoped as AFTER the 1.0 milestone ships, not before -- recorded now purely so the idea
isn't lost. Next major push once 1.0 is out:
- [ ] Mod support itself (extraction pipeline, data model, and UI all currently assume the base
  game + official DLCs only -- extending this to arbitrary installed workshop mods is its own
  substantial effort, not yet scoped in detail).
- [ ] Dynamic prebuilt-table population: today every "Load Prebuilt Tables" band table
  (`scripts/upload_prebuilt_tables.py`, `src/prebuilt_table_titles.py`) is a hand-built,
  hand-uploaded snapshot -- a modded ship/component someone's game adds has no way to show up in
  one of these tables at all. Eventually these should be generated/refreshed dynamically (new
  components AND their mocks) so an unfamiliar ship from some installed mod set still gets
  surfaced the moment "Load Prebuilt Tables" is clicked, not just the base-game catalog this
  session's batch covered. Depends on mod support existing first.
- [ ] Expanded documentation for running/building this app locally against a modded install (today's
  docs assume a vanilla Steam base-game + DLC install; see `src/extract_game_data.py`'s own
  `GAME_ROOT` and catalog-discovery logic).
- [ ] Collect and build for a handful of popular community mod sets, surfaced on the live site
  itself (not just "bring your own game files and run locally") -- exact mechanism (which mod
  sets, how they're kept in sync with mod updates, whether this needs its own separate deployed
  instance per mod set or a single switchable one) not yet designed.

## 16. Proving Grounds / Ship Trials -- Next Session (brainstormed 2026-10-28)
Prioritized as discussed, NOT started on any of it yet -- recorded purely to pick up from
tomorrow. Fleet Trials itself stays out of this list entirely -- user call: it can wait, possibly
pushed to after the 1.0 milestone rather than built alongside the rest of this.

1. [x] **Static asset cache-busting.** DONE 2026-10-30: added a second `@app.middleware("http")`
   in `src/api.py` (`no_cache_static_responses`, right below the existing `/api/...` one) that sets
   `Cache-Control: no-cache` on every response from the `"/"` `StaticFiles` mount (`index.html`,
   `app.js`, `style.css`, `i18n/*.json`, `vendor/*.js`) -- `no-cache` forces a conditional GET every
   load rather than letting the browser trust heuristic freshness, but `StaticFiles` already sets
   `etag`/`last-modified`, so an unchanged file still comes back as a cheap `304` (verified live via
   `curl` with `If-None-Match`). Deliberately excludes the separate `/images/...` mount (ship symbol
   PNGs, keyed by ware_id, effectively immutable) so that normal long-lived caching is undisturbed
   there. Went with headers over a version/hash query-param scheme since it needed no build-time
   tooling or version-bumping discipline and directly closes the exact failure mode hit this session.
2. [ ] **Mod Lab support for a Ship Trial's own ships.** SUPERSEDES this item's own original plan
   (user call, 2026-10-30): no separate new mod page/modal after all -- instead, the real Ship
   Builder/editor (see item 6's own DONE note just below, which built the reuse mechanism this
   depends on) already shows every equipped group for a ship, and that's where a mod gets applied
   too: select a mod for a group, it applies to the whole set of items in that group, matching how
   mods actually work in the real game. Still not started -- this item is now "add a mod picker to
   each group row inside that same Ship Builder view", not a new page.

3. [x] **Ship Trials comparison styling.** DONE 2026-10-30 -- see items 20/21 above for the full
   writeup (user-selectable baseline column, Cost Analyzer-style colored value/percent diffs, the
   Fleet Planner's own selection-box icon overlay, and the matching independent-focus treatment
   ported onto the Cost Analyzer itself).
4. [x] **"Add Ship" source: Fleet Lists.** DONE 2026-10-30. "Add Fleet List Ship" opens
   `#ship-trial-fleet-ship-modal-overlay` (`openShipTrialAddFleetShipModal()` in app.js), a two-step
   picker: step 1 is a VERTICAL list of the user's own real `fleets`, reusing `buildFleetTabShipIcon()`/
   `SELECTION_BOX_CORNER_CLASSES` directly (both already standalone, no `setActiveFleet()` involved)
   so the ship-symbol/active-box look matches the real horizontal fleet tabs exactly -- deliberately
   NOT `buildFleetTabButton()` itself, since that hardcodes `setActiveFleet()` on click (a real
   app-state write this read-only picker must never trigger) plus its own delete "x"/Build Method
   Priority line, neither wanted here. Step 2 shows that one fleet's own ships (icon/name/note, same
   look as the real cart-table rows) with an explicit Select button per row (user call, not a
   whole-row click like the other two "Add Ship" pickers). `cartEntryToLoadout()` converts the
   clicked cart entry into the same loadout shape `addShipToTrial()` already expects for a saved
   loadout, reading `entry` only -- nothing on it is ever written to, so the source fleet's own cart
   is provably untouched (verified live via Playwright: fleet still has its original 2 ships after
   adding one to a Trial). "Back to Fleets" returns to step 1 to pick a different fleet.
5. [x] **"Add Ship" source: build your own.** DONE 2026-10-30 as "Add Builder Ship"
   (`openShipTrialBuilderModalForNewShip()` in app.js). The "biggest unknown" this item used to flag
   -- whether the Ship Builder flow can work meaningfully inside a modal over the Proving Grounds
   page -- turned out to extend naturally from item 6's own relocation trick below: instead of
   relocating just `#ship-detail`, `openShipTrialBuilderModal()` et al. now relocate the WHOLE
   `#picker-section` (chassis filters, Loadout Manager, the ship list, Load/Clear/Select Filter
   Loadout, AND `#ship-detail`, its own last child) into the modal, then back out again on close --
   `#page-fleet-planner`'s `display: grid` layout is undisturbed by this since the page itself stays
   hidden the whole time. "Add Builder Ship" opens that same modal blank (`resetShipPicker()`) so the
   user picks/Loads a fresh chassis right there; "Edit" still opens it pre-populated as before. Either
   way, the reused `Add To Fleet List` button (top AND bottom copies) is now relabeled "Add to
   Trial"/"Update Trial" and saves into the Trial instead, via a new `gatherCurrentShipLoadoutData()`
   extracted from `addSelectedShipToCart()` (shared validation/gathering logic, same capacity checks)
   feeding `saveShipTrialBuilderChanges()` -- see item 6's own entry for the add-vs-update split.
6. [x] **Edit a Trial ship's own loadout.** DONE 2026-10-30 (Phase 1 "populate only" done earlier the
   same day, Phase 2 "save back" done right after, together with item 5 above since they share the
   same modal/button). Each ship column has an "Edit" button (`.ship-trial-edit-ship-btn` in
   `buildShipTrialBody()`) that opens `#ship-trial-builder-modal-overlay` pre-populated via
   `loadImportedGameLoadout(component.loadout)` (`addShipToTrial()` snapshots the adding loadout onto
   `component.loadout` for exactly this -- `shipMocks` alone loses each group's own group_name, so it
   can't reconstruct the groups view; a pre-existing Trial ship from before this snapshot existed gets
   a disabled Edit button with an explanatory tooltip instead of erroring). The modal's own reused
   `Add To Fleet List` button is relabeled "Update Trial" for this case (vs. "Add to Trial" for a
   fresh add, see item 5) -- decided from `shipTrialBuilderContext.instanceId` directly, not from
   whichever label text the call site passed in, since `loadImportedGameLoadout()` always passes the
   "Add" wording even here. Clicking it calls `updateShipInTrial()` (updates that same
   `component.instanceId`'s own `loadout`/`name`/`icon`/`shipMocks` in place, same column position --
   confirmed NOT a duplicate column via Playwright) instead of `addShipToTrial()`. Opening/closing the
   modal has zero lasting effect on the Fleet Planner page underneath either way:
   `closeShipTrialBuilderModal()` snapshots+restores `currentShip`/`editingIndex`/all the amount
   globals/the note field/the Add-button's own label/live group `<select>` values first (verified live
   via Playwright with a DIFFERENT ship already loaded in the Fleet Planner builder beforehand --
   untouched after). Also added as part of this: an editable loadout-name field
   (`renderShipLoadoutNameField()`) right under the ship's own name/icon, pencil-icon-edit style like
   elsewhere in the app, reading/writing the same `shipNoteInput` value the "Loadout Name" field
   further down the page already did (both stay in sync) -- "Add to Trial"/"Update Trial"/"Add To
   Saved Loadouts" all save under whatever name is set there. Mod picker (item 2 above): DONE
   2026-10-31, see that item's own entry. Marking a Trial column "edited": also DONE 2026-10-31 --
   `addShipToTrial()` now snapshots a never-touched-again `component.originalLoadout` alongside the
   live `component.loadout`, and `updateShipInTrial()` recomputes `component.edited` on every save by
   comparing the two via a new `loadoutEquipmentSignature()` (an order-independent deep-equal over
   just the fields that actually mean something -- name/shipWareId/selections/amount maps/
   appliedMods -- deliberately excluding shipName/shipIcon, pure shipWareId lookups, and warnings/
   rawXml, which `saveShipTrialBuilderChanges()` always resets regardless of whether anything real
   changed, so including them would mark every single Update Trial as "edited" even on a true no-op
   save). Shows as an amber "Edited" badge in the column header, tooltip explaining why -- verified
   live via Playwright for both directions: a genuine no-op Update Trial stays unmarked, a real change
   (tested via the top editable loadout name) shows the badge and stays stable across further re-saves
   of the same content. A component saved before this existed (no `originalLoadout` yet) gets it
   lazily backfilled from whatever it currently is on its first save going forward, rather than
   guessing at a baseline that was never recorded.
7. [x] **Statistics Lab: read-only "Details" mode.** DONE 2026-10-30, renamed from "View" to
   "Details" and extended to the Select Stats picker the same day (user call). A new "Details"
   button next to Clone (and Edit, for a user-created stat) on every Browse row whose `def.formula`
   exists -- skipped only for a "fundamental" stat (reads a raw database column directly, see
   `statDef()`'s own comment, so there's genuinely nothing to show). Shown for EVERY other kind, not
   just "derived" -- unlike Edit, Details is never destructive, so there's no reason to withhold it
   from the app-authored, locked "pre-derived"/"mod" stats that previously had no way to inspect
   their own formula short of Clone (which pollutes the custom stat list with a new copy just to
   peek). Opens a new fifth Stat Lab sub-view (`showStatLabView("inspect")`, alongside browse/
   builder/mocks/constants) mirroring the Builder's own Formula/Variables layout, but with plain
   read-only text instead of any input/select/textarea -- verified 0 editable form elements present
   in that view. New `describeFormulaVariableTarget(ref)` renders a readable {aggregation,
   componentType, stat, limit} tuple for every one of the 5 real `ref.type`s
   resolveFormulaVariable()/resolveAggregateVariable() can produce (`stat_ref`/`mock_ref` share one
   description, same as the Builder's own indistinguishable-at-authoring-time treatment;
   `aggregate_ref` adds the aggregation kind plus its limit; `mod_modifier_ref` and `constant_ref`
   get their own honest descriptions since neither has a real {componentType, statId} pair at all)
   -- including `group_sum`/`group_average`, two aggregations the Builder UI itself can never
   produce (Shield MJ/Rate/Delay's own app-authored formulas only) but which Details still needs to
   label correctly. Verified live against three real formulas covering every ref type: Avg Equipped
   Cost (13 `stat_ref` chassis-slot-count variables + 11 `aggregate_ref` sums, one per sub-type,
   each showing its own limit variable by name), a Shield "mod" stat (`mod_modifier_ref`, showing
   "Mod Lab Modifier" / `Current modifier on "recharge_max"`), and the Sustained DPS mechanism-R
   stat (two `constant_ref` variables, correctly resolving each curated constant's own real label).
   `openStatLabInspect(def, componentType)` is fully self-contained (sets `statLabComponentType`,
   populates the type select, unhides `#stat-lab-modal-overlay` itself) rather than assuming the
   Stat Lab modal is already open -- this is what lets the SAME function also back a second "Details"
   button added to the Select Stats picker's own `renderStatSelectGroupsPanel()` (one per stat row
   with a formula, next to its info icon), which opens the Stat Lab modal stacked visually on top of
   the still-open Select Stats modal (later DOM markup already renders on top, same precedent the
   existing "Statistics Lab" cross-modal button inside Select Stats already relied on -- no z-index
   changes needed) -- confirmed via screenshot, and confirmed Select Stats itself stays open
   underneath rather than closing. No edit affordance was added to the Select Stats row itself, per
   explicit instruction -- that picker is for choosing which stats a table shows, not authoring them.
   Confirmed live in the real rendered Browse list too: 121 chassis rows, 57 carrying a real Details
   button (every one with a formula) vs. 121 Clone buttons (every row); the Select Stats modal's own
   chassis catalog shows the same 57-button count. Close returns cleanly to Browse. Long-tail
   follow-up (explicitly not this pass, still true): render the formula as a properly typeset math
   expression instead of the raw `math.js` expression string.
8. [x] **Loadout/ship picker filtering.** DONE 2026-10-30 -- see items 18/19 below for the full
   writeup (chassis filter panel via `buildChassisFilterPanel()`, widened modals so it renders 3
   boxes per row, plus free-text chassis-name/loadout-name search, all in both the Ship Trials
   "Add Ship" modal and the Fleet Planner's own `openSelectGameLoadoutModal`).
9. [ ] **(Long-tail, research only) In-browser 3D ship model viewer.** A button to view/rotate a
   ship's real in-game model. Researched live (2026-10-28), not guessed: confirmed real, pulling a
   real ship's own raw asset folder via the existing XRCatTool pipeline -- a ship is NOT one mesh,
   it's dozens of separate `.xmf`/`.jcs` pieces (hull, cockpit glass, doors, exhaust FX, decals, each
   with LOD/collision/hull variants) in Egosoft's own proprietary binary format, assembled via a
   scene XML (confirmed on the Irukandji: ~80 files, each tens-to-low-hundreds of KB). No direct
   browser-readable format exists in the game files themselves. A real conversion path does exist
   though, not improvised: Egosoft's own official "Blender Mod Tools" extension (and a community
   Nexus Mods importer with extra features, e.g. reading connection XML for weapon/turret/engine
   mount points) imports `.xmf`/`.xac` into Blender, which can then natively export glTF/GLB --
   i.e. the realistic pipeline is X4 raw mesh -> Blender (via that plugin) -> glTF/GLB, not a
   one-step converter. Once in glTF, in-browser viewing itself is a solved, cheap problem
   (`<model-viewer>` or three.js, both lightweight, both handle rotate/zoom for free). The real
   cost is the OFFLINE Blender-based batch conversion step (likely scriptable headless via
   `blender --background --python ...`) -- a genuinely different kind of tooling than this
   project's existing pure-Python/XRCatTool pipeline, multiplied across every ship (and weapons/
   turrets too, if wanted). Next step if picked up: a research/prototype spike -- run the real
   Blender pipeline on just ONE ship end-to-end, see how painful it actually is and how big the
   resulting `.glb` ends up, before committing to it as a real feature. Sources: [Egosoft Forum --
   How To Export Models, Re-Import (Blender)](https://forum.egosoft.com/viewtopic.php?p=4774324),
   [Egosoft Forum -- Significant update to X4 Modding Tools
   released](https://forum.egosoft.com/viewtopic.php?p=5201955), [Egosoft Wiki -- Modding
   Support](https://wiki.egosoft.com/X4%20Foundations%20Wiki/Modding%20Support), [NexusMods -- X4
   Foundations mesh importer](https://www.nexusmods.com/x4foundations/mods/2170).

## 17. Avg/Min/Max Equipped Cost (user call, 2026-11-01) -- DONE
- [x] A new pre-derived "economy" stat, **chassis-only** (same as `shield_total_mj`/
  `ship_sustained_damage_total` -- the slot/capacity counts it caps against only exist as a concept
  when a real chassis is in view): the sum of `price_avg`/`price_min`/`price_max` across every
  REALLY-equipped component, across all 11 equippable sub-types at once (engine, thruster, shield,
  weapon, turret, missile, drone, deployable, countermeasure, crew, software). First version summed
  every mocked entry with no cap at all -- user call (2026-11-01) caught this as wrong with a
  concrete example: a Hydra (4 real main weapon slots) with 20 M weapons mocked onto it for
  comparison purposes must only count 4, not 20, the same way `shield_total_mj` already caps to a
  real slot count rather than trusting the mock list as-is. Reworked so each sub-type sums capped to
  whichever real chassis column represents its own slot/capacity count: `engines`/`shields` (plain),
  weapon as TWO pools (`weapons` main + `bonus_l_weapons`, same split `ship_sustained_damage_total`
  already uses -- missile launcher mocks share the main weapon pool, no separate cap exists to split
  them into), turret as TWO pools (`turret_l` + `turret_m`, no prior precedent, built fresh),
  missile/drone/deployable/countermeasure capped to their own CAPACITY stat (a real unit budget,
  which the mock-budget machinery already consumes correctly per-entry via each mock's own `count`),
  crew capped to `crew`. Two exceptions, both explicit user calls: thruster is capped to a literal
  `1` (every real ship has exactly 1 thruster slot, and no chassis column represents that the way
  `engines` does -- required a new "plain number, not a named variable" case for `limit`, see
  `aggregateLimitValue()`), and software is left UNCAPPED (confirmed no software mod category exists
  at all -- `MOD_LAB_COMPONENT_TYPE_MAP` has no "software" entry -- so there's no "many options to
  compare" use case, and a real ship's own software mocks already come straight from its real,
  already-bounded loadout selections). Needed two small engine additions: `resolveAggregateVariable()`
  gained `treatMissingAsZero` (sum/average with zero resolved values returns 0 instead of reporting
  missing and nulling the whole expression -- without it, a ship with no countermeasures equipped
  would null out the ENTIRE stat, not just that one sub-type's own zero), and `limit` can now be a
  plain number as well as a named-variable string (for thruster's literal 1) -- both threaded through
  `crossComponentFormula()`. A known, accepted trade-off inherited from `shield_total_mj`'s own
  existing "pre-existing simplification": bonus shields share the same mock pool as main shields with
  no way to tell them apart, so they're undercounted the same way `shield_total_mj` already
  undercounts bonus shield MJ -- not a new gap, same one shield_total_mj already has. Verified live:
  Hydra with 20 mocked M weapons correctly caps to exactly 4 slots' worth of cost (confirmed the
  Hydra's own real `weapons` column is 4, matching the user's own example exactly; Dragon's own real
  `weapons` column independently confirmed as 6, also matching); a real, never-over-mocked Asgard
  loadout shows no missing-mock warnings and a lower total than the old uncapped version, entirely
  accounted for by its ~12 bonus shields no longer double-counted past its own 4 main shield slots.
- [x] **Bug found and fixed along the way, affecting every cross-component Ship Trial stat, not
  just this one:** `restorePersistedState()` used to `return` immediately on a null `state` (a
  brand-new session with nothing in localStorage yet), which skipped its own tail-end
  `componentListCache` warming (`collectMockRelevantComponentTypes()` + `fetchComponentList()` for
  each type any registered formula's `aggregate_ref`/`mock_ref` touches) ENTIRELY for that session.
  Since `statSourceForComponentType()` reads straight from that cache with no fallback, a first-time
  user who went straight to Proving Grounds (no prior Component Analyzer/Ship Builder visit to warm
  it as a side effect -- "Add Loadout Ship"/"Add Fleet List Ship" don't need one) would see
  Sustained Weapon Damage, Shield (MJ)/Recharge Rate/Delay, and now Equipped Cost all silently
  wrong or missing on their very first Ship Trial, until they happened to open some unrelated
  picker elsewhere. Fixed by normalizing `state` to `{}` instead of returning early -- every
  individual restore step below already null-checks its own piece of `state` safely, so the only
  behavior change is that the warming (and the final `renderComponentAnalyzerTables()`/
  `renderShipTrials()` calls) now always run. Verified live: a completely fresh Playwright browser
  context now shows `componentListCache` populated (weapon: 101, engine: 150, shield: 85, etc.)
  immediately after the first page load, with no prior navigation.

## 18. Ship Builder capacity mods live-update + auto-downgrade (user call, 2026-10-30) -- DONE
- [x] Chassis Mod slots that raise missile/drone/deployable/countermeasure capacity now live-update
  the Ship Builder's own capacity numbers immediately on Confirm, instead of only showing the
  chassis's unmodded base value. New `shipLiveCapacity(baseKey, postModKey)` resolves the real
  `*_post_mod` formula (`missile_capacity_post_mod`/`drone_capacity_post_mod`/
  `deployable_capacity_post_mod`/`countermeasure_capacity_post_mod` -- all already existed in
  `CHASSIS_STAT_DEFINITIONS` from the Base/Modifier/Post Mod work, just never wired into the Ship
  Builder itself) against the chassis's own row from `statSourceForComponentType("chassis")` --
  needed because `currentShip` nests these under `.summary` (base only) while the formula engine
  expects the flat shape `allShips`-style rows have. `totalMissileCapacity()`/`totalDroneCapacity()`/
  `totalDeployableCapacity()`/`totalCountermeasureCapacity()` all call this now instead of reading
  `currentShip.summary.xxx_capacity` directly. Crew deliberately excluded -- no
  `crew_capacity_post_mod` exists (crew has no real mod support in the game data).
- [x] Second half of the same request: maxed-out selected counts now auto-downgrade when the mod
  that boosted their capacity is weakened or removed, instead of silently sitting over the new, lower
  limit. New `clampAmountsToCapacity(amounts, capacity)` trims an amounts map down to fit (deleting
  zeroed-out entries), and `reclampCapacityLimitedAmounts()` runs it across all 4 amount maps and
  unconditionally re-renders all 4 sections (needed either direction: `renderDroneSection()`/
  `renderDeployableSection()`/`renderCountermeasureSection()` each hide themselves and wipe their own
  amounts at capacity <= 0, so a capacity *increase* off of 0 needs the same full re-render to even
  reappear, not just an increase). Wired into `refreshShipModLabButtons()`, the existing hook already
  called after every mod Confirm across all 6 Ship Builder mod slots -- a cheap no-op whenever
  irrelevant. Verified live end-to-end on a real Asp (3 base + 20 from its equipped S Dumbfire
  Launcher = 23 missile capacity): maxed missile ammo to 23, applied the real "Bandolier (Missile
  Capacity Mod)" at its max roll (+4) -- capacity live-updated to 27; maxed ammo up to the new 27;
  removed the mod -- capacity correctly dropped back to 23 AND the selected ammo amount auto-clamped
  down to 23 in the same step, through the real render pipeline (not just the isolated clamp
  function). Drone/deployable/countermeasure capacity resolution confirmed error-free on the same
  ship. No new i18n strings -- the clamp is silent (same "no toast" precedent as the qty steppers'
  own existing capacity clamping), matching how over-capacity entry is already prevented elsewhere
  in the Ship Builder.

## 19. Loadout list filtering (user call, 2026-10-30) -- DONE
- [x] Both places that list saved/imported loadouts for picking now get the exact same
  Size/Purpose/Type/Race/Vendor/Build Method chassis filter panel as the main Ship Builder's own
  `#ship-filters` -- a collapsible "Filters" button + panel, built fresh via the already-existing
  `buildChassisFilterPanel(container, onChange)` helper (previously only used by the Component
  Analyzer's "Select Components" and Stat Lab's mock-component pickers), scoped to its own
  independent checkbox root via `shipPassesCurrentFilters(ship, root)` so it never shares state
  with `#ship-filters` or any other modal's own copy.
  - Ship Trials "Add Loadout Ship" modal (`openShipTrialAddShipModal`/new
    `renderShipTrialAddShipList`): previously a completely flat, unfiltered list of every imported
    loadout -- now filtered live by its own panel.
  - The main Ship Builder's "Select Filter Loadout" modal (`openSelectGameLoadoutModal`/new
    `renderSelectGameLoadoutList`): previously filtered *silently* by whatever happened to already
    be checked in the main page's own `#ship-filters` (no visible panel of its own, so it was easy
    to forget why some loadouts weren't showing) -- now has the same visible, independent,
    toggleable panel as every other picker in the app, for consistency (an explicit, in-modal "every
    opening starts with nothing checked" panel, not an invisible inherited one). The filter panel is
    hidden entirely in this modal's other mode -- the ship-specific "Select `<Ship>` Loadout" button
    next to the loaded ship's name, already narrowed to one chassis, where a chassis filter would be
    a no-op (unchanged from before).
  - Along the way, fixed three pre-existing, never-localized hardcoded English strings in
    `openSelectGameLoadoutModal` ("No imported loadouts match the current filters.", "No imported
    loadouts for this ship.", "`${count} warning(s)`") -- all now real i18n keys, translated across
    all 15 locales alongside the new "Filters"/"no results" strings this feature itself needed.
  - Verified live: checking only the "S" size filter in the Ship Trials "Add Ship" modal narrowed a
    2-entry list (one S, one L/XL) down to exactly the S one; the "Select Filter Loadout" modal's
    filter panel is confirmed hidden in ship-specific mode and shown in generic mode, with the same
    narrowing behavior; full key-parity re-verified across all 15 locale files (934 keys each, no
    missing/extra) and no console/page errors on load.
  - Follow-up (same day): both modals widened from the shared `.modal`'s own default
    `min(420px, 90vw)` to `min(820px, 90vw)` so the filter panel renders 3 boxes per row, matching
    the main Ship Builder's own look -- the on-paper exact total (3 x 246px `.filter-group` boxes +
    2 x 1.25rem gaps = 778px) measurably still wrapped the 3rd box down onto its own row (same
    unresolved "off by more than rounding" overhead `.filter-group`'s own width comment already
    documents), so 820px was chosen as a confirmed-working conservative buffer above it. Verified
    live: both modals now render Size/Purpose/Type and Race/Vendor/Build Method as two full rows of
    3, not 2+1.
  - Follow-up (same day): added two free-text filters above the checkbox panel in both modals --
    ship chassis name and loadout name, AND-combined with each other and with the checkbox filters
    (all three narrow the same list together). Each modal keeps its own pair of inputs/state, reset
    to empty on every open; wired via a plain `.oninput =` assignment (not `addEventListener`) since
    the handler closes over that one open's own `trial`/mode and must not stack across repeated
    opens, same reasoning as the filter panel's own fresh rebuild on every open. Verified live:
    searching "asp" in the chassis field on a 2-entry list (Asp/Hydra loadouts) narrowed to just the
    Asp one; clearing it and searching "beta" in the loadout-name field narrowed to just that
    differently-named entry; same behavior confirmed in the "Select Filter Loadout" modal. Full
    15-locale key parity re-verified (936 keys each) and no console/page errors.

## 20. Proving Grounds: user-selectable comparison baseline (user call, 2026-10-30) -- DONE
- [x] A Ship Trial can now compare every column's stat numbers against ONE column the user picks,
  instead of always being plain, undiffed values -- clicking a column's own header (its new
  `.ship-trial-column-select-area`, wrapping just the icon/name/edited-badge, kept separate from the
  Edit/Remove buttons below it so those keep working unchanged) calls `setShipTrialBaseline(trial,
  instanceId)`, which sets `trial.baselineInstanceId` (new field on `makeShipTrial()`, cleared
  automatically by `removeShipFromTrial()` if the removed ship happened to be the baseline). A new
  "Clear Comparison Baseline" button sits next to "Select Stats" and is the only way back to no
  baseline (clicking a header is idempotent, not a toggle). Deliberately does NOT reorder
  `trial.components` the way the Ware Cost List's own "column 0 is always the baseline" convention
  does (`wareCostListColumns()`) -- explicit user call: the baseline column stays exactly where it
  already was.
- [x] The baseline column's own icon gets the exact same 4-corner "selection box" overlay the Fleet
  Planner's active fleet tab already shows (`SELECTION_BOX_CORNER_CLASSES`/`selection_box_corner.png`)
  -- new `buildShipTrialColumnIcon(icon, isBaseline)` reuses that same corner-bracket decoration and
  CSS classes verbatim, but keeps the Trial's own plain, untinted icon (`buildIconImg()`) rather than
  switching to the Fleet tab's own green-tinted "player_location" icon variant -- only the corner
  overlay itself was asked for, not that function's whole color scheme.
- [x] Every stat cell now gets the same "(raw diff, percent diff)" annotation, in the same green/red/
  default coloring, as the Ware Cost List's own `appendComparisonCell()` -- new
  `appendStatComparisonDiff(statTd, def, value, baselineValue)` reuses its exact `.ware-cost-list-diff`/
  `-up`/`-down`/`-none` classes and diff math (so it looks identical, per the user's own request),
  layered onto the cell `renderStatCellValue()` already filled in (value text, missing-mock warning
  icon, mock-trace "e" icon) rather than replacing the whole cell the way Ware Cost List's own
  function does -- Ship Trial cells need to keep those icons, which the Ware Cost List's own ware rows
  never had. Silently skipped for a non-numeric stat (booleans, compatibility tags, race codes, ...) --
  diffing those has no real meaning. The baseline value for each row is resolved once (not once per
  cell) against the SAME stat def/active stat set every other column in that row already uses.
- [x] Verified live end-to-end: a 3-ship Trial (Asp/Hydra/Dragon) with Mass + Hull selected showed 0
  diff spans before any baseline was set; clicking the Hydra column's header set it as baseline
  (confirmed via `trial.baselineInstanceId`) and immediately showed correct diffs on the other two
  columns only (e.g. Hull: Asp `-3800, -45.2%` in red, Dragon `+12600, +150.0%` in green, both
  measured against Hydra's own real 8400 hull) with column order unchanged (`Asp, Hydra, Dragon`
  before and after); "Clear Comparison Baseline" correctly removed every diff span and reset the
  baseline to null. Screenshot-confirmed the corner-bracket overlay renders cleanly around the
  baseline icon, matching the Fleet Planner's own look. No console/page errors; full 15-locale key
  parity re-verified (946 keys each).
- [x] Follow-up (same day, user call): row heights no longer shrink/grow when a baseline is set,
  cleared, or switched to a different column. `appendStatComparisonDiff()` is now called
  unconditionally for every numeric stat cell (not just non-baseline cells while a baseline is
  active) -- when there's no real diff to show (no baseline at all, or this IS the baseline column),
  it still appends a `.ware-cost-list-diff-placeholder` span (`visibility: hidden`, same `" "`
  single line) instead of appending nothing, so every numeric row always reserves exactly the same
  line height regardless of baseline state. A non-numeric stat row (booleans, compatibility tags,
  ...) still gets nothing at all either way -- it never had a diff line to reserve in the first
  place, so its own height was already stable across baseline toggles before this fix; only numeric
  rows needed it. Verified live: a 3-row Trial (Mass/Hull numeric, Size non-numeric) measured
  identical per-row heights (49.1875px/49.1875px/33.1875px) with no baseline, with a baseline set,
  and immediately after clearing it again -- confirmed via real `getBoundingClientRect()` reads, not
  just visual inspection.
- [x] Follow-up (same day, user call): removed the "Clear Comparison Baseline" button entirely --
  clicking the column that's already the baseline now clears it instead (`setShipTrialBaseline(trial,
  isCurrentBaseline ? null : component.instanceId)`), a real toggle rather than the previous
  idempotent "always sets" behavior. A different column still just sets itself as the new baseline,
  same as before. The select area's own tooltip switches between "Set this ship as the comparison
  baseline..." and "This ship is the comparison baseline -- click to clear it" depending on which
  state that column is currently in. Verified live: clicking a column sets it (baseline id + 4 corner
  brackets + real diffs appear), clicking that SAME column again clears it (id back to null, 0
  corner brackets, every diff span gone, row heights unaffected per the fix above), and clicking a
  DIFFERENT column while one is already set just switches the baseline cleanly. Full 15-locale key
  parity re-verified (945 keys each, down by exactly 1 from the removed button's own key) and no
  console/page errors.

## 21. Cost Analyzer: independent comparison focus, no reordering (user call, 2026-10-30) -- DONE
- [x] Ported Ship Trials' own comparison-baseline design (items 20 above) onto the Ware Cost List --
  clarified with the user first (AskUserQuestion): the Cost Analyzer's comparison baseline used to
  just BE "whichever fleet is active" (`activeFleetIndex`, the same pointer cart edits/build method
  editing/everywhere else in the app reads), which is also why `wareCostListColumns()` used to sort
  that fleet into column 0 every render. The chosen design makes it a fully independent concept
  instead -- new `wareCostListFocusedFleetIndex` (null = no focus), completely decoupled from
  `activeFleetIndex`, persisted the same way (`saveState()`/`restorePersistedState()`, with the same
  defensive index clamp `activeFleetIndex` already got, except null -- not 0 -- is the valid
  "nothing saved" default).
- [x] `wareCostListColumns()` no longer reorders at all -- plain `fleets.map(...)`, natural order,
  regardless of which fleet (if any) is active or focused. `appendWarePartRows()`/`appendPriceRows()`
  read `partsByColumn[wareCostListFocusedFleetIndex]`/`index !== wareCostListFocusedFleetIndex`
  instead of the old hardcoded `[0]`/`index !== 0`, since a column's position and its fleet index are
  now always the same number.
- [x] Each column header gets its own new "Focus"/"Focused" button (`renderWareCostListHead()`),
  entirely separate from the existing `buildFleetTabButton()` control above it (still the Fleet
  Planner's own click-to-`setActiveFleet()` tab, completely untouched -- same shared component, same
  blue-fill/corner-bracket look, used unchanged in the real Fleet Planner tab bar too). Clicking a
  different column's Focus button sets it; clicking the ALREADY-focused column's own button clears it
  back to null -- no separate "Clear" control, same toggle pattern as item 20's Ship Trials fix. The
  focused column's `<th>` also gets a distinct `.ware-cost-list-focused-column` highlight (background
  tint + bright accent underline) -- deliberately a different visual language from the active fleet's
  own blue-fill/corner-bracket, confirmed via screenshot, so the two concepts never look like the same
  thing even when they happen to coincide on the same column.
- [x] `appendComparisonCell()` now always appends a `.ware-cost-list-diff`/`-placeholder` line (same
  fix as Ship Trials' own `appendStatComparisonDiff()`) instead of only when `showDiff` is true --
  every Ware Cost List row is inherently numeric (unlike Ship Trials' mixed stat rows), so this
  applies unconditionally to every cell now, keeping row heights stable whether a column is focused,
  unfocused, or switched to a different one.
- [x] `deleteFleet()` now adjusts `wareCostListFocusedFleetIndex` the same way it already adjusted
  `activeFleetIndex` (decrement if the deleted fleet was before it) -- except deleting the focused
  fleet itself clears focus to null rather than reassigning it to a survivor, same "clear, don't
  guess a new target" reasoning as Ship Trials' own `removeShipFromTrial()`.
- [x] Verified live end-to-end with 3 real fleets (Asp/Hydra/Dragon carts, real `/api/summarize` +
  `/api/price_summary` data): columns stayed in natural order (Fleet A, B, C) both before and after
  focusing, even with Fleet B set as the ACTIVE fleet the whole time; focusing Fleet A left
  `activeFleetIndex` completely unchanged (still B) while correctly diffing B and C against A (e.g.
  `+1,104,806 Cr, +509.2%`) in green; row heights measured identical across no-focus/focused/cleared
  states; clicking the same column again cleared every diff; clicking a different column switched
  cleanly. Fleet-deletion index adjustment verified directly: deleting a fleet BEFORE the focused one
  correctly decremented the stored index (still pointing at the right fleet, confirmed by name);
  deleting the focused fleet itself correctly cleared focus to null. Full 15-locale key parity
  re-verified (949 keys each) and no console/page errors.

## 22. Tomorrow's list (user call, 2026-10-30)
Not necessarily in priority order. Recorded as the session wrap-up list -- check item 14's "Path to
1.0" audit framing again once picked back up, since several of these interact with it.

1. [ ] **(Long-tail, research only) In-browser 3D ship model viewer.** Still just research, not a
   build task -- see item 16's own entry 9 above for the full writeup (confirmed-real but
   Blender-pipeline-dependent conversion path, no browser-native format in the game files
   themselves). Don't start building against this until a research/prototype spike on one ship is
   actually run.
2. [ ] **Fleet Trials.** Still explicitly parked -- the "Under Construction" placeholder tab stays as
   is. Confirmed again today: possibly post-1.0 rather than picked up alongside the rest of Proving
   Grounds. See item 16's own intro line and issue #16's own comment history for the standing
   rationale.
3. [ ] **New "Information"/terminology page.** Not yet designed -- a page (possibly its own new top-
   nav tab, possibly a modal/overlay reachable from the header) explaining this app's own
   vocabulary and how to actually use it: what a "mock" is and why the Stat Lab needs one, what
   "pre-derived"/"derived"/"fundamental" stat tags mean, what a comparison baseline/focus column
   does, what a Chassis Mod vs. an equipment mod is, the Component Analyzer vs. Proving Grounds vs.
   Cost Analyzer distinction, and anything else a first-time visitor would otherwise have to guess
   at from context. Aimed at new users, not at the existing About page's own changelog/attribution
   content -- a separate concern, not a replacement for it. Scope/placement/exact content list not
   yet decided.
4. [x] **Commit, push, and update tracking issues.** DONE 2026-10-30 -- see the commit itself and
   GitHub issues #26/#16 for the full "what's done, what's left" writeup; not duplicated here.
5. [x] **Reddit update post prep.** DONE 2026-10-30 -- bullet points + screenshot suggestions given
   directly in chat per the user's own request (they're writing the actual post themselves), not
   saved to a file.
