# User Guide (draft)

Working draft for the User Guide page -- content only, not wired into the site yet. One section
per top-nav tab. Render this locally (VS Code's own Markdown preview, or any Markdown viewer) to
iterate before it gets converted to HTML and i18n'd.

## Fleet Planner

Build out individual ship loadouts and organize them into fleet lists.

### High Level Features

- Pick a ship chassis from a filterable list (Size, Purpose, Type, Race, Vendor, Build Method).
- Equip every slot: engines, thrusters, shields, weapons, turrets, software, missiles/ammunition,
  drones, deployables, countermeasures, and crew.
- High Preset / Minimum Preset buttons auto-fill a loadout with the most/least expensive option in
  each slot.
- Apply equipment and Mods through the Modifications Lab, including copy/paste between
  slots, a real material cost breakdown, and a Roll button.
- Import your own saved game loadouts (`loadouts.xml`) or paste raw loadout XML directly.
- Save a finished loadout, then filter/search your saved loadouts to load one back in later.
- Organize ships into any number of named, independently editable Fleet Lists.
- Download or upload a Fleet List as a file, or generate a share link.

### Ship Builder

Pick a ship from the list on the left, then equip it slot by slot.

- The ship list is filtered by the checkboxes above it (Size, Purpose, Type, Race, Vendor, Build
  Method).
- Once a ship is loaded, every real equipment slot it has shows up as its own section: engines,
  thrusters, shields, weapons, turrets, software, missiles/ammunition, drones, deployables,
  countermeasures, and crew. Only the sections a ship actually has appear.
- Each slot is a dropdown of every compatible option for that exact mount -- size and compatibility
  tier are already filtered for you, so everything shown will fit.
- High Preset fills every slot with its most expensive option; Minimum Preset fills only the
  required slots with the cheapest. Both work ship-wide (next to "Select Loadout") or one section at
  a time.
- Chassis Mods and equipment mods are applied through the Modifications Lab button next to the
  chassis name or each equipped item -- see Component Analyzer's own Modifications Lab section
  below for the full rundown; it works the same way here.
- "Add To Fleet List" saves the current loadout into whichever fleet list is active. "Add To Saved
  Loadouts" saves it to your own loadout library instead (see Loadout Manager below) without adding
  it to a fleet.

### Loadout Manager

Your own library of saved ship loadouts, separate from any one fleet list.

- **Import Game Loadouts** reads your real `loadouts.xml` (either by local file path, if you're
  running this app locally, or by uploading the file) and pulls in every ship loadout it contains.
- **Import Raw XML Loadout** lets you paste a single `<loadout>` element (or a `<loadouts>` block
  with several) directly, for a loadout you don't have the full file for.
- Once you have loadouts imported, **Select Filter Loadout** opens a picker with the same chassis
  filters as the ship list above, plus free-text search by ship name or loadout name, so you can
  find one saved loadout out of a large library quickly.
- **Export Loadouts** downloads everything you've imported/saved as one real `loadouts.xml`, in the
  exact format the game itself uses. You can drop it straight into
  `Documents\Egosoft\X4\<id>\loadouts.xml` and the game will load it. Station module loadouts and any
  loadout this app couldn't parse are carried through untouched too, but you should back up your loadouts
  **Back up your real file first**: this app can't guarantee the result won't break something, and overwriting it can't be
  undone. **Clear Loadouts** empties the library.
- A loadout you load back in from here populates the Ship Builder exactly as it was saved. Edit it
  and re-save under a new name if you want a variant.

### Fleet Lists

A fleet list is a named group of ships, built from the Ship Builder on the left.

- Create any number of fleet lists via the tabs at the top of this section; each one is
  independently named, edited, and deleted.
- These fleet lists are used in the cost analyzer (and in the future, in the fleet trials of the proving
  grounds) as the baseline to compare against. You can compare individual ship costs by using fleet lists
  with only one ship in them.
- Every ship added to the active fleet list shows up as a row with an editable quantity (ctrl-click
  a +/- to step by 10, shift-click to jump to max/0) and an optional note.
- Click a loadout's own expand/collapse arrow to show or hide its full equipment breakdown inline,
  without leaving the list.
- Each fleet list has its own Build Method Priority -- an ordered list of which production method to
  use first for every ware it needs, with each one below it as a fallback. This also drives the Cost
  Analyzer's own cost figures for that fleet.
- Download a fleet list as a file, upload one back in, or use the Share button in the header to
  generate a link someone else can open to load a copy of it (along with any other sections you
  choose to include in that same link).

## Cost Analyzer

Breaks down exactly what a Fleet List costs to build, down to the raw materials.

### High Level Features
- Compare the cost of every Fleet List side by side, in one table.
- Switch between a Total Cost Breakdown and a Component Type Cost Breakdown.
- See Market Purchase Price, Production Wares Price, and Raw Materials Price, each as Min/Average/Max.
- Drill into exactly which wares a build needs and how much of each.
- Override any ware's price to see how that changes every cost figure that depends on it.
- Focus any Fleet List column to compare every other one against it, with colored value/percent diffs.

### Component Type VS Total Cost Breakdowns

Both tabs show the exact same underlying cost data for every fleet list, just organized
differently.

- **Total Cost Breakdown** rolls every ship in a fleet together into one set of numbers.
- **Component Type Cost Breakdown** splits that same total out by component type (Engines, Shields,
  Weapons, and so on), so you can see which category of equipment is actually driving the cost.
- Switching tabs doesn't recalculate anything -- both are ready as soon as a fleet list's cost has
  been computed once.

### Credits, Production Wares, Raw Materials Breakdowns

Three different "how deep do you want to dig" views into the same build, each collapsible:

- **Credit Cost** is the cost in credits. Market Purchase Price (buy from a shipyard), Production
  Wares Price (buy the wares the shipyard consumes), and Raw Materials Price (buy the raw resources),
  each shown as Min/Average/Max.
- **Production Wares** lists exactly which intermediate wares (hull parts, energy cells, and so on)
  a build needs and how much of each, one level down from the finished ship.
- **Raw Materials** goes all the way down to the base resources (ore, silicon, ice, and so on)
  needed to produce everything above, recursively expanded through every recipe in between.
- Expand or collapse any section's header to show or hide its own rows -- useful once a breakdown
  gets long.

### Fleet Comparison and Focus

Every fleet list you've built shows up as its own column, side by side, in every breakdown above.

- Select a fleet list to focus it as the baseline to compare other fleets' costs against. Every other
  column then shows both its own value and a colored difference, both raw and percent change from the baseline.

### Ware Price Overrides

Override what this app assumes a ware costs, for every cost calculation that uses it.

- Click **Set Ware Price Overrides** to open a list of every ware in the database, with its real
  Min/Average/Max price and an editable box to type your own.
- Any override you set applies everywhere that ware's price is used. Every fleet list's cost
  breakdown recalculates to match.
- Once you close the popup, a compact list of every currently active override stays visible so you
  can see (and clear) them without reopening it.

## Component Analyzer

Build side-by-side comparison tables for any equipment category or ware in the game.

### High Level Features
- Compare any of the 12 component types: ship chassis, engines, shields, weapons, turrets,
  thrusters, missiles, software, drones, deployables, countermeasures, and economy wares.
- Build any number of independent tables at once, each with its own component picker and filters.
- Pick exactly which stats show as columns, grouped and searchable.
- Load ready-made comparison tables for common categories with one click (Load Prebuilt Tables).
- Use the Statistics Lab to inspect stats by their source, fundamental data points or derived from fundamental data.
- Author your own custom stats in the Statistics Lab -- formulas built from existing stats, with
  mocked inputs for data a table wouldn't otherwise have access to.
- Inspect the formula behind any stat, `pre-derived` or `derived`.
- Export tables to JSON, CSV, or XLSX, or import one back in.

### Load Prebuilt Tables

The fastest way to get a useful table on screen without building one yourself.

- Click **Load Prebuilt Tables** and pick a category to load a ready-made, fully configured
  comparison table for it -- every relevant component already added, with a sensible set of stats
  already selected.
- This adds a new table alongside whatever you already have open; it never replaces or removes an
  existing one.
- Loading the same prebuilt table more than once is fine -- each load is its own independent table,
  so you end up with duplicates you can then edit differently or remove when you're done with them.

### Component Tables

A table is one side-by-side comparison, you can have as many open at once as you want.

- Every table has an editable title and tab titles. The tabs are for switching between different saved sets of
  columns on the same components selected for this table (more on that under Statistics Lab/stat sets below).
- Each table picks one component type to compare (Ship Chassis, Engines, Shields, Weapons, Turrets,
  Thrusters, Missiles, Software, Drones, Deployables, Countermeasures, or Economy Wares), set once
  through a drop down.
- Add components to a table through its own picker, which has the same filters as everywhere else in
  the app, narrowed to that component type.
- Which stats show as columns is chosen separately per tab (see "Select Stats" on each tab), but
  the components themselves are shared across every tab of the same table, so switching tabs just
  changes which numbers you're looking at for the same row set, not the rows themselves.

### Statistics Lab

The Statistics Lab is a manager for the statistics shown on the website, in the Component Analyzer and
the Proving Grounds. Every stat shown anywhere in this app can be found in the Statistics Lab. It allows
you to view available stats within and shared between component types, when those stats depend on multiple
component types. It allows you to view the source of the stat and an associated formula referencing other
stats, if there is one. It also allows you to create your own custom stats. Below are the tags associated
with different stats and what they mean.

- **Fundamental** -- read straight from the game's own data files defining components, nothing computed.
- **Pre-derived** -- a formula this app ships with, determined by research, investigation, and modeling.
  Examples include weapon DPS, shield totals, and so on.
- **Derived** -- a formula you build yourself, defined using the stat builder using a javascript math
  expression.
- **Mod** -- Dynamic stats whose values change based on inputs from the Modification Lab. These stats are used
  to determine Post Mod pre-derived stats, which apply the modifier to the fundamental stats.
- **Production** -- Production cost stats. These are seperated from the fundamental stats because of how they are
  generated by the data backend. The stats themselves are generated dynamically from the production costs when a new
  ware build method is parsed, so game mods which add new ships, production methods, or wares should dynamically
  generate new stats. 
- Click **Details** next to any stat (fundamental excluded, since there's nothing to show) to see
  exactly what it's made of -- its formula and where every variable in it comes from -- without any
  risk of changing it.
- Click **Clone** to start a new stat from an existing one's formula, or **+ New Stat** to build one
  from scratch: write a formula using math (sums, averages, comparisons) over any other stat, on
  this component type or pulled in from a different one.
- The **Constants** page holds reusable numbers (like the ones this app's own built-in combat-math
  stats are curve-fit against) that a formula can reference the same way it references a stat.
- A stat you create is immediately usable from every table of the same component type, not just the
  one you built it from.
- The same stat is displayed on multiple components, based on which component sources are present in
  the formula for that stat. The user can define the group it appears under for each component.

### Mocked Components and Stats

Some formulas need an input from other component types besides the main component type for that table.
These stats can be resolved through the Mocked Stats and Components manager.

- A mock can be a plain number you type in, or a real component (e.g. "assume this engine is
  installed on a Rattlesnake") whose own real stats get pulled in automatically.
- Stats which require some mocks but have no source for them will display a warning symbol in their
  stat value, which explains the missing stats on mouse over.
- Mocks are configured at one of several scopes, and applied in order from most specific
  to least specific: one row on one tab > one row across every tab > every row on one tab >
  all rows and tabs of a table > or a global mock. The most specific scope with something configured always wins.
- Multiple mocks can be configured on a single scope. The are applied in order until all required stats are
  filled from compatible equipment. Incompatible components are skipped by the mock. All used mocks and skipped 
  mocks are listed by an info pop up next to each stat value in the table.
- Click **Mocked Stats** on a table to see every mock currently affecting it, and which rows (if
  any) are still missing one they need -- a cell missing a mock it needs shows a small warning icon
  you can hover for details.
- "Group mode" lets a mock spread itself across a chassis's own real hardpoint groups instead of
  being treated as one flat count. This is used by stats that need to know about per-group totals, like
  average shield MJ per bonus-shield group.

### Modifications Lab

Apply the game's own equipment mods to a component in this table, to see their effect on
every stat that depends on them.

- Click the Mod Lab button (mod symbol) on a component's own row (or the table-wide one, to set a default for
  every row at once) to open the picker.
- Pick a mod, then roll its value within its real in-game range -- the **Roll** button does this for
  you and keeps a running total of the material cost spent rolling so far.
- Every mod's own real material cost (wares plus credits) is shown before you commit to it.
- Copy a mod from one slot and paste it into another instead of configuring the same roll twice.
- A cell affected by an applied mod is colored by that mod's own quality tier, so you can see at a
  glance which numbers in a table reflect a modded value.
- Mods can also be applied to mocks, and their changed values will also show on the stats table.

### Import and Export

- Export one or more tables to JSON (to re-import later), CSV (one file per tab, zipped), or XLSX
  (one workbook per table, one sheet per tab) -- pick which tables to include when you export.
- Import a previously exported file to bring those tables back, exactly as they were.

## Proving Grounds

Compare real ships and fleets head-to-head on performance, not just cost.

### High Level Features

- Add ships straight from your saved loadouts, from a Fleet List, or build one fresh.
- Edit a ship already in a comparison without removing and re-adding it.
- Pick any ship as a comparison baseline for colored value/percent diffs against every other one.
- Switch between stat sets to compare different groups of stats without rebuilding the table.
- Build custom stat sets using the same stats built in the Component Analyzer.
- Fleet-level (whole-fleet) comparisons are planned but not built yet.

### Ship Trials vs Fleet Trials

- **Ship Trials** compares individual ships against each other, stat by stat -- this is the finished
  half of Proving Grounds, covered by everything below.
- **Fleet Trials** (whole-fleet aggregate comparisons) is still under construction and not usable
  yet -- its tab exists but just shows a placeholder for now. This should show fleet wide stats like burst
  and sustained dps, as well as stat breakdowns along other groups, like ship size or ship type. It should
  use aggregators across existing stats.

### Adding Trials

A Trial is one side-by-side ship comparison, the Proving Grounds equivalent of a Component Analyzer
table.

- Click **+ Add Trial** to create a new one; give it its own title by clicking the title field.
- Add any number of Trials, each completely independent of the others.
- Minimize a Trial to collapse it out of the way without losing it, or remove it entirely with the
  "x" button.

### Define Stats in Stats Tabs

Which stats show as rows is controlled the same way a Component Analyzer table's columns are --
through stat-set tabs, stacked down the left side of a Trial instead of across the top.

- A brand-new Trial starts with 7 stat sets already filled in -- Core Stats, Basic Flight, Advanced
  Flight, Shields, Weapons, Turrets, and Storage and Support -- the same layout as the "Load
  Prebuilt Tables" band's own Large Ship Chassis table, so there's something useful to look at
  immediately, with nothing to configure first.
- Click **Select Stats** on any stat set to change what it shows, or **+** to add another stat set
  tab entirely (e.g. one for combat stats, another for economy stats) and switch between them.
- Every stat available in the Component Analyzer's own Ship Chassis catalog -- fundamental,
  pre-derived, and anything you've built yourself in the Statistics Lab -- can be added to a Trial's
  own stat sets the same way.

### Add Ships to Trials

Three ways to add a ship to a Trial, each from its own button:

- **Add Loadout Ship** picks from your saved loadout library (Loadout Manager), with the same
  filters and search as everywhere else that list shows up.
- **Add Fleet List Ship** picks one of your fleet lists, then one specific ship from it -- read-only,
  it never changes the fleet list itself.
- **Add Builder Ship** opens a blank Ship Builder right inside the Trial, for building a ship from
  scratch without needing to add it to a fleet list first.
- Once a ship is in a Trial, click **Edit** on its column to open the same Ship Builder and change
  its loadout in place -- an "Edited" badge appears once it's been changed from how it was
  originally added, so you can tell at a glance which columns have drifted.

### Comparison Baseline

Click a ship's own column header to set it as the baseline every other column is compared against.

- Every other column then shows a colored (green for more, red for less) raw and percent difference
  against the baseline column, for every numeric stat in the Trial.
- Click the same column's header again to clear the baseline back to plain values; click a different
  column's header to switch the baseline to it instead.
- The baseline column keeps its own place in the table -- setting or clearing one never reorders the
  columns.
