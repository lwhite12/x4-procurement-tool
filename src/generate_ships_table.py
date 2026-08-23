"""Build the `ships_base`, `production_wares`, `ship_component_groups`,
`flight_model`, `economy_wares_base`, `equipment_wares_base`,
`turrets_base`/`engines_base`/`shields_base`/`weapons_base`/`thrusters_base`,
`software_base`, `missiles_base`/`deployables_base`/`drones_base`, and
`countermeasures_base`/`crew_base` SQL tables + CSVs from the X4 game data
XML files.

Reads:
  - data/names/0001-l044.xml     (English page/id -> string lookup table)
  - data/libraries/wares*.xml    (base game wares.xml plus each expansion's
                                   wares_<suffix>.xml; ships are wares
                                   tagged "ship", economy wares are wares
                                   tagged "economy", equipment wares are
                                   wares tagged "equipment" plus one of
                                   "engine"/"shield"/"weapon"/"turret"/
                                   "thruster", software candidates are wares
                                   tagged "equipment" plus "software",
                                   missiles are wares tagged "equipment" plus
                                   "missile", deployables are wares tagged
                                   "equipment" plus one of "satellite"/
                                   "resourceprobe"/"mine", drones are wares
                                   tagged "equipment" plus "drone",
                                   countermeasures are wares tagged
                                   "equipment" plus "countermeasure", and the
                                   single "crew" ware has no tags at all so
                                   it's matched by id directly)
  - data/ships/size_*_macros/*.xml     (each ship's macro: component ref,
                                   ship type/hull/crew/travel drive/missile
                                   capacity, the full flight model --
                                   jerk/physics/steeringcurve -- and its
                                   <software> compatibility list)
  - data/ships/size_*_components/*.xml (each ship's component/model
                                   definition, analyzed for engine/shield/
                                   weapon/turret connection slots)
  - data/<type>s/<type>_*_macros/*.xml     (<type> in engine/shield/weapon/
                                   turret: each ware's identification/mk +
                                   type-specific stats -- boost/travel/
                                   thrust for engines, recharge for
                                   shields, bullet/heat/rotation for
                                   weapons, bullet/rotation for turrets)
  - data/<type>s/<type>_*_components/*.xml (each ware's mount size +
                                   compatibility class)
  - data/missiles/macros/*.xml         (each missile's identification +
                                   ammunition/missile/explosiondamage/
                                   reload/hull/weapon/countermeasure/
                                   physics/lock stats, all self-contained
                                   on the macro -- no separate component
                                   file to look up)
  - data/deployables/{satellites,probes,mines,lasertowers,navbeacons}/*.xml
                                   (each deployable's identification +
                                   hull/radar/explosioneffect/
                                   explosiondamage/trigger/physics stats,
                                   also self-contained on the macro)

Writes:
  - src/sql/ships_tables.sql          (CREATE TABLE schema for all 17 tables)
  - src/csv/ships_base.csv            (one row per ship ware)
  - src/csv/production_wares.csv      (one row per ware needed by a ship's,
                                        economy ware's, equipment ware's,
                                        missile's, or deployable's
                                        production -- shared by all five,
                                        see "Economy wares"/"Equipment
                                        wares" below)
  - src/csv/ship_component_groups.csv (one row per named engine/turret/
                                        thruster/software group)
  - src/csv/flight_model.csv          (one row per ship: jerk/physics
                                        attributes + serialized steering
                                        curve, all from the macro alone)
  - src/csv/economy_wares_base.csv    (one row per economy ware)
  - src/csv/equipment_wares_base.csv  (one row per engine/shield/weapon/
                                        turret/thruster ware)
  - src/csv/turrets_base.csv          (one row per turret ware, see
                                        "Turrets" below)
  - src/csv/engines_base.csv          (one row per engine ware)
  - src/csv/shields_base.csv          (one row per shield ware)
  - src/csv/weapons_base.csv          (one row per weapon ware)
  - src/csv/thrusters_base.csv        (one row per thruster ware, see
                                        "Thrusters" below)
  - src/csv/software_base.csv         (one row per software ware actually
                                        reachable from some ship, see
                                        "Software" below)
  - src/csv/missiles_base.csv         (one row per missile ware, see
                                        "Missiles and deployables" below)
  - src/csv/deployables_base.csv      (one row per satellite/resource
                                        probe/mine ware)
  - src/csv/drones_base.csv           (one row per drone ware, see
                                        "Drones" below)
  - src/csv/countermeasures_base.csv  (one row per countermeasure ware --
                                        just "Flares" in the base game, see
                                        "Countermeasures and crew" below)
  - src/csv/crew_base.csv             (one row: the single "crew" ware, see
                                        "Countermeasures and crew" below)
  - data/x4.db                        (SQLite database rebuilt from the
                                        schema + CSVs above on every run)

The old ware id (e.g. "ship_arg_l_destroyer_01_a") is preserved as `ware_id`,
but the resolved display name is used as ships_base's primary key,
eliminating the {page,id} indirection used by the game's i18n system. The
production method is stored as a resolved name too: a ware's
<production method="..."/> attribute (e.g. "default") is just an internal
id, not the actual method name -- the real name lives behind that block's
own name="{page,id}" reference (e.g. "Universal", "Xenon"), which must be
decoded the same way ship names are.

Component slot analysis
------------------------
A ware's <component ref="..."/> (stored as `macro`) points to a *macro* file
(data/ships/size_X_macros/<macro>.xml), which itself has its own
<component ref="..."/> pointing to the *component* file
(data/ships/size_X_components/<component>.xml) that actually defines the
ship's hardpoints as <connection tags="..." group="..."/> entries. Most connections
aren't equipment slots at all (cockpit, lights, cosmetic model attachment
points); the ones that are carry one of "engine"/"shield"/"weapon"/"turret"
plus a size token ("small"/"medium"/"large"/"extralarge") in their tags.

On S/M ships, engine/weapon/turret connections have no "group" attribute --
each is independent. On L/XL ships, engines and turrets are clustered into
named groups (e.g. group="group_engines", group="front_up_mid"), a turret
group can contain more than one turret, and each group gets its own
dedicated medium shields (tagged "shield medium", sharing the same group
name) on top of the ship's own main "shield large" slots.

A ship's own main engines/shields/weapons are always sized to match its own
size class (an S ship's engines/shields/weapon are always "small", an L
ship's are always "large", etc.) -- there's exactly one meaningful count for
each, so ships_base stores them as flat "engines"/"shields"/"weapons"
columns rather than one column per size, with the ship's own size class in
a "size" column. The one exception is bonus medium shields on L/XL ships
(see above), which are never the ship's own main shield size, so they get
their own "shields_bonus_m" column. Turrets don't follow the "matches ship
size" rule at all -- a single L-class ship can carry both large and medium
turrets simultaneously -- so turret slot counts stay one dynamic
"turret_<size>" column per size actually observed (currently "turret_l" and
"turret_m"). ship_component_groups gets one row per (group_name,
component_type) pair, recording its size, how many slots it holds, and the
"equipment_compatibility_class" -- the connection's own full tag set, minus
just the type/size tokens (e.g. "advanced,combat,missile" or
"arg_destroyer_01"). This isn't filtered down to a fixed known vocabulary
(there is no such fixed vocabulary -- some ships gate a slot with a unique
per-hull tag instead of a generic tier, see "Turrets/engines/shields/
weapons" below) -- both size and this tag set can differ between two
groups of the same type and size on the same ship, so they're tracked per
group, not per (type, size). group_name alone is not unique per ship: a
dedicated medium shield protecting a specific engine/turret group shares
that group's own raw group_name (see parse_component_slots' docstring),
distinguished only by component_type = "shield" -- a caller joins on
(ship_id, group_name) to find a group's dedicated shields.

Missiles
--------
A ship's missile ammo capacity (<properties><storage missile="207"/> in its
macro) is stored as ships_base.missile_capacity. Separately, in the
component file, a <connection tags="weapon missile ..."/> is a dedicated
missile launcher rather than a gun mount, so classify_connection reclassifies
it to component_type "missile_launcher" (turrets tagged "missile" stay
turrets -- that's just their compatibility class, not a type change). Like
engines, missile launchers always combine into a single "missile_launcher"
group rather than one row per slot, and their total count (summed across
all sizes, same as engines) is stored in ships_base.missile_launchers.

The same <storage> element can carry up to two more attributes:
"deployable", confirmed always 0 on every ship that has it at all (dead/
unused data, not a real capacity, so it's not captured), and "unit", which
*is* real and varies sensibly with each ship's logistics role (builders/
resuppliers ~100-250, carriers ~20, plain fighters 0/absent) -- captured as
ships_base.drone_capacity, how many drones that ship can carry/deploy. See
"Drones" below for the drone wares themselves.

A fourth attribute, "countermeasure", is never a real per-ship number
either -- but unlike "deployable" it isn't simply dead: it's explicitly set
to "0" only on ships that categorically can't use flares at all (drones,
Kha'ak hulls, and a few other non-player-flyable ships, alongside their own
missile="0"/unit="0"), and is entirely absent (not defaulted to 0) on every
normal player-flyable ship. That means the game applies some other,
hardcoded-in-the-engine default flare capacity for those ships that isn't
recoverable from this XML data at all -- so it's still not captured as a
ships_base column. See "Countermeasures and crew" below for how the
frontend handles this instead (an assumed default by ship size, the same
shape as its existing deployable-capacity assumption).

Ship stats and flight model
----------------------------
ships_base.ship_type/hull/crew/traveldrivestability come straight from the
macro's <ship type="..."/>, <hull max="..."/>, <people capacity="..."/>, and
<traveldrivestability maxvalue="..."/> elements. The last one is absent on
some ships (S-class ships in particular); unlike hull/crew/ship_type it
defaults to 0 rather than being left null when missing.

ships_base.purpose is the macro's <purpose primary="..."/> -- an AI role
classification (e.g. "fight"/"trade"/"mine"/"build"/"auxiliary"/"racing"/
"salvage"/"dismantling"), the same element analyze_drone_macro() already
reads into drones_base.purpose for drones. Independent of ship_type: a
ship_type like "scout" or "heavyfighter" is a hull *class*, purpose is
what it's *for* -- e.g. multiple ship_types can share purpose "fight".

ships_base.icon is the macro's <identification icon="..."/> -- a small
ship-class symbol name (e.g. "ship_s_fighter_01"), one per size+purpose
combo rather than unique per ship (many different ships of the same
size/role share one icon). The actual image is not part of wares.xml/the
macro at all -- it's a separate gzip-compressed DDS texture in the game's
own catalogs (assets/textures/ui/shipicon/<icon>.gz), pulled out by
extract_game_data.py's "ship_icons" extraction job and converted to a
web-displayable PNG by generate_ship_icons.py; see that script's own
docstring for the full path (data/images/ships/symbols/<icon>.png).

flight_model is a separate table, one row per ship (keyed by ware_id, same
as ships_base), built purely from the macro's <jerk> and <physics> blocks --
no wares.xml or component-file data involved. Both blocks have a fixed set
of child elements (jerk: forward/forward_boost/forward_travel/strafe/
angular; physics: inertia/drag/accfactors) but not every child or attribute
is present on every ship (e.g. <accfactors> is sometimes missing entirely,
and when present its attributes vary), so columns are named
"jerk_<child>_<attr>"/"physics_<child>_<attr>" (plus "physics_mass" for the
attribute directly on <physics>) and discovered dynamically the same way
turret/bonus-weapon columns are, rather than hardcoded. <steeringcurve> is a
variable-length list of <point position="" value=""/> entries (5 to 7+
points depending on the ship), which doesn't fit fixed columns at all, so
it's serialized into a single "position:value,position:value,..." text
column instead of a further normalized table.

Expansion ships
---------------
Each expansion's wares_<suffix>.xml is a <diff> patch, not a standalone
<wares> list: new ship (and other ware) definitions live inside an
<add sel="/wares"> block, alongside separate <add sel="/wares/ware[@id='...']">
blocks that patch *existing* wares (mostly adding extra owner factions to
base-game ships for that expansion). Only the wholesale-new ware entries are
picked up here -- the per-ware patches are not applied, so an existing ship's
`owners` list may be incomplete with respect to what an expansion adds to it.

Economy wares
-------------
economy_wares_base covers every ware tagged "economy" (raw resources like
ore/silicon/energycells, refined goods, hightech/shiptech components, food,
pharmaceuticals), plus wares tagged "processed" (raw salvage materials like
rawscrap/rawkhaakscrap that feed economy recipes but carry no "economy" tag
of their own and have no production recipe -- only obtainable by salvaging)
across the same wares*.xml files as ships. `leaf_ware` is True when none of
the ware's production blocks have a non-empty <primary> ware list (i.e. it
has no upstream inputs -- it's a true leaf of the production tree) -- e.g.
energycells (made from sunlight) and rawscrap/rawkhaakscrap (no production
block at all, salvage-only) are True, while engineparts (built from
antimattercells/energycells/refinedmetals) is False.

Unlike ships, an economy ware routinely has *multiple* <production> blocks
-- e.g. engineparts has a "default" recipe and a separate "teladi" recipe
using teladianium instead of refinedmetals -- and all of them, not just the
first, are expanded into production_wares. This is also why
production_wares' primary key includes production_method as well as ware:
two different recipes for the same ware can both need "energycells", which
would otherwise collide on the old (production_ware_id, ware) key.
production_wares is genuinely shared between ships and economy wares now --
a row's production_ware_id can be either a ships_base.ware_id or an
economy_wares_base.ware_id, which is also why it no longer has a FOREIGN KEY
on that column (SQLite can't express "references one of two tables").

Equipment wares
----------------
equipment_wares_base covers mountable ship equipment: wares tagged
"equipment" plus one of "engine"/"shield"/"weapon"/"turret" (that second tag
becomes `equipment_type`). Missile launchers aren't their own category in
the game data -- a weapon or turret additionally tagged "missilelauncher"
is one, recorded as the `missile_launcher` boolean rather than a separate
type. Same production/price parsing as economy wares (multiple methods
kept, all expanded into production_wares, production_ware_id now
potentially a ships_base/economy_wares_base/equipment_wares_base id).

This intentionally does NOT parse an equipment ware's own component/
hardpoint slots (unlike a ship, a standalone piece of equipment doesn't
have its own ship_component_groups-style breakdown) or its combat stats
(damage, range, etc., which live in a different file entirely) -- just
what it costs and what it takes to build.

Turrets/engines/shields/weapons
-------------------------------
turrets_base/engines_base/shields_base/weapons_base are the one exception
to the "no combat stats" rule above: each parses data/<type>s/
<type>_<size>_macros/*.xml and <type>_<size>_components/*.xml (see
extract_game_data.py's equipment_macro_jobs/equipment_component_jobs)
directly, independent of wares.xml, via the shared
parse_equipment_component_wares(equip_type, ...) helper. `ware_id` is
recovered from the macro's own `name` attribute (always "<ware_id>_macro"),
`macro` is that raw macro name, `owners` is the macro's <identification
makerrace="..."/> (a single race, unlike ships_base.owners' comma-joined
faction list), and `mk`/`hull` plus type-specific stats (bullet/rotation
for turrets; boost/travel/thrust for engines; recharge for shields;
bullet/heat/rotation/weapon_angle for weapons) come straight off the
macro's <properties>. `size`/`compatibility` instead come from the
*component* file the macro's <component ref="..."/> points to: the one
<connection tags="<type> <size> <compatibility...> ..."/> among its many
connections (e.g. "turret medium standard" or "engine large advanced")
identifies the mount size and what tags a ship connection must carry to
accept it -- see parse_equipment_mount for exactly how that's resolved.
`compatibility` is stored as the connection's *complete* remaining tag set
(comma-joined, sorted) after stripping the type/size tokens and pure
bookkeeping tokens, not a single collapsed "tier" value -- see
query_ship_components.matching_items()'s docstring for why matching needs
the full set (some slots are gated by more than one tag at once, e.g. a
mining ship's weapon mount accepting either "advanced" or "mining" gear,
and some -- see below -- carry no generic tier tag at all).

Not every macro under data/<type>s/ is a real, purchasable ware: some are
legacy "_01_mk1" macros kept only as an alias="..._02_mk1_macro" backward-
compat redirect for old savegames (no <hull max="..."/>, since they're
never actually equipped), some are _scenario/_story mission-only variants,
and a few are just unused dev leftovers with no matching ware at all. Each
<type>s_base table is filtered down (via filter_to_real_equipment_wares) to
ware_ids that actually exist in equipment_wares_base, so it only contains
real, mountable equipment. Many L/XL weapons are a specific ship hull's
fixed main battery rather than generic swappable equipment -- their
`compatibility` is a unique per-hull identifier (e.g. "arg_destroyer_01")
instead of a generic tier, which in practice means exactly one weapon ware
resolves as an option for that hull's main gun mount. That's a real,
accurate reflection of the game data (most races' L destroyers and several
XL battleships hard-lock their spinal mount to one dedicated weapon; a few,
like the Boron L destroyer and Split XL battleship, use an ordinary/
combined tier tag instead and so offer more than one option) -- see
query_ship_components.matching_items()'s docstring for how this is matched.

The "_01_mk1 alias" pattern above turned out to have a second shape too,
confirmed for several M-size shields and turrets: a macro can carry its
own alias="..." attribute *and still have a completely real, independently
priced wares.xml entry of its own* -- e.g. shield_bor_m_standard_01_mk1
and shield_bor_m_standard_02_mk1 are both fully real, both purchasable,
both the same name/stats/price/compatibility class, and the only reason
they're not both genuinely useful separate choices is that one of them
(the aliased one, identifiable by <hull integrated="1"/> instead of a real
<hull max="..."/>) is the game's own designated redundant copy of the
other. The "restricted to wares.xml" filtering above doesn't catch this
shape at all, since both ware_ids are equally real there -- so
parse_equipment_component_wares checks each macro's own alias="..."
attribute directly, but -- caught by hand-testing after an earlier version
of this shipped a real regression (the Hydra lost access to Paranid Blast
Mortar Turrets) -- the attribute's presence alone isn't sufficient: some
alias pairs are two genuinely different compatibility tiers of the same-
named item (turret_par_m_shotgun_01_mk1 is "advanced", its alias target
turret_par_m_shotgun_02_mk1 is "standard" -- both are real, needed,
separately-mountable turrets, not duplicates at all). Only a pair whose
size *and* compatibility class both match is treated as a true redundant
duplicate and excluded; see parse_equipment_component_wares's own
docstring for the exact (necessarily two-pass, since it needs every
macro's mount already resolved) logic.

A handful of macros (observed for engines/weapons/turrets, never for a real
ware) use <macro ref="..."/> to inherit properties from another macro and
override only some of them; that inheritance chain isn't resolved, so an
affected macro's un-overridden fields come out null. Every currently
existing case is on an already-filtered-out orphan macro, so this doesn't
affect any real row today -- if a future DLC adds a real ware using this
pattern, its null columns will flag the gap.

Thrusters
---------
Unlike engines/shields/weapons/turrets, thrusters have no data/thrusters/
macro or component directory at all -- the game doesn't model a thruster as
a physical <connection> hardpoint on the ship's component file, and no
per-ware macro file exists in the extracted data either. Every ship simply
gets exactly one thruster slot sized to match its own hull, so:

  - ship_component_groups gets one synthesized "thruster" group per ship
    (component_type "thruster", slot_count 1, size = the ship's own size
    class), added directly in analyze_ship_components() rather than
    discovered via parse_component_slots -- there's no XML connection to
    find one in.
  - thrusters_base is parsed straight from wares.xml by
    parse_thruster_wares(), not from a macro walk: `size`, `thruster_class`
    ("allround" or "combat" -- a player playstyle choice, not a tier lock),
    and `mk` are all recovered from the ware_id itself (e.g.
    "thruster_gen_m_combat_01_mk2"), since there's no <properties>/mount
    connection to read them from. Thrusters carry no faction/tier lock in
    the game data at all (no <owner> elements, no compatibility tag), so
    `compatibility` is set to the constant "universal" on both the
    ship_component_groups group and every thrusters_base row -- this isn't
    a real game concept, just a shared sentinel so the existing
    (size, compatibility_class) matching in query_ship_components.py's
    matching_items() keeps working unmodified for this type too.

Software
--------
Software (dock/flight assist/scanner/target/trade computer upgrades) has no
mount, size, or compatibility-class concept at all -- unlike every other
equipment type, whether a ship can use a given software ware isn't derived
from any generic matching rule, it's determined purely by an explicit
per-ship list: each ship macro's <properties><software> block enumerates
the exact ware_ids that ship accepts (flagged default="1" for its stock
loadout or compatible="1" for a purchasable upgrade -- both are treated as
equally valid options here; the distinction isn't currently modeled beyond
that). 254 of 255 ships have this block; the one exception (the unbuildable
Khaak XL Battleship) simply has no software groups.

  - load_macro_data() reads the raw <software ware="..."/> list alongside
    the ship's other <properties> children. analyze_ship_components() then
    groups those ware_ids by category -- the "<category>" in a ware_id like
    "software_scannerlongrangemk2" -- and synthesizes one
    ship_component_groups row per category actually listed for that ship
    (group_name "software_<category>", component_type "software", slot_count
    1, size the SOFTWARE_SIZE sentinel "any" since size genuinely doesn't
    apply). `equipment_compatibility_class` is repurposed here to hold the
    comma-joined list of that ship's specific compatible ware_ids for the
    category (e.g. "software_scannerlongrangemk1,software_scannerlongrangemk2")
    instead of a shared tier token -- query_ship_components.py's
    matching_items() branches on component_type "software" to match against
    this list directly (by ware_id) rather than the (size, compatibility)
    query used for every other type.
  - Docking computer is a confirmed exception to "the ship's own list is
    authoritative": "software_dockmk1" is never listed by any ship's macro
    at all, yet is equippable in-game wherever mk2 is (hand-verified
    in-game against the Raptor) -- docking computers apparently aren't
    actually gated per-ship the way scanners are, just not modeled that
    way in the XML. So after the per-ship loop, main() unconditionally
    expands every ship's "software_dock" group (if it has one) to *every*
    known dock ware, not just whatever its own macro happened to list.
    This is deliberately dock-specific, not a general "lower mk is always
    available" rule -- the Raptor is a live counterexample for scanners:
    its macro lists only "software_scannerlongrangemk2" (no mk1), and mk1
    is genuinely NOT equippable on it in-game, so scanner tiers stay
    exactly as declared.
  - software_base is parsed broadly first (parse_software_wares: every
    wares.xml entry tagged "equipment" plus "software", the same two-tag
    shape as other equipment types -- 10 candidates), then filtered down in
    main() to only ware_ids actually referenced by at least one ship's
    <software> block, after the dock expansion above folds "software_dockmk1"
    into that reachable set (9 of the 10 candidates survive -- only
    "software_scannerobjectmk3" is a real ware no ship ever lists and no
    special case covers, so it's dropped), the same "parse broad, filter to
    real" shape as filter_to_real_equipment_wares uses against
    equipment_wares_base, just filtered against ship-reachability instead
    since software doesn't have an equipment_wares_base parent row -- see
    below. Several other software_* wares in wares.xml (economymk1,
    scannerminingmk1/2, targetmk2, trademk2/3, hackerspacesuitmk1,
    oxygenspacesuitmk1) don't even carry "equipment"+"software" tags
    together and are never candidates in the first place -- the personal-
    upgrade/spacesuit ones aren't ship equipment at all, and the rest have
    no evidence in this dataset of ever being ship-mountable (not modeled,
    rather than guessed).
  - category and mk come from the ware_id itself (e.g.
    "software_scannerobjectmk2" -> category "scannerobject", mk 2), via
    SOFTWARE_WARE_RE -- same reasoning as thrusters: most software wares
    point at a shared "software_dummy_macro" placeholder with no real
    stats, and the handful of scanner wares that instead reference a
    "scanner_gen_..._macro" don't have one anywhere in the extracted data
    either, so there's nothing to gain from a macro walk. name/price come
    straight off the wares.xml entry -- like missiles_base/deployables_base
    (not thrusters_base), software_base has no equipment_wares_base parent
    row, since "software" doesn't fit that table's engine/shield/weapon/
    turret/thruster vocabulary.

Missiles and deployables
-------------------------
missiles_base and deployables_base cover ammo (missile) and standalone
launched objects (satellite/resource probe/mine/laser tower/nav beacon) --
ware categories that don't fit engine/shield/weapon/turret's mold, so
unlike those four they have no equipment_wares_base parent row: name/
macro/price live directly on each table, populated by parse_missile_wares/
parse_deployable_wares from wares.xml. `missiles_base` requires the
"equipment" tag alongside "missile", which naturally excludes ~15 legacy
"deprecated"-tagged missile wares left over from an old naming scheme
(they carry no "equipment" tag at all, so no separate deprecated check is
needed).
`deployables_base.deployable_type` (satellite/resourceprobe/mine/
lasertower/navbeacon) comes from whichever of those five tags a ware
carries, mirroring `equipment_wares_base.equipment_type`. Laser towers
(ship_gen_s_lasertower_01_a, ship_gen_xs_lasertower_01_a) and the nav
beacon (waypointmarker_01) are exactly as generic/race-neutral as the
other three types -- there's only ever one of each ware, no per-race
variants -- despite their macro/component filenames ("eq_arg_satellite_
01_macro" etc. included) sometimes carrying a leftover race-code prefix
from whichever internal art team originally authored the asset. Naming
convention alone is not a reliable race signal here; wares.xml's own tags
are (see race_from_ware_id() in query_ship_components.py for the one
place this app does derive race from a ware_id's naming convention, and
why that's a different, load-bearing use case: distinguishing Xenon/
Kha'ak-only equipment, not this).

Both are self-contained: a missile or deployable's own macro <properties>
has everything (no separate component file with a mount-tag size/
compatibility to resolve, unlike turrets/engines/shields/weapons) --
analyze_missile_macro/analyze_deployable_macro read it directly by looking
up the ware's own `macro` field (from wares.xml's <component ref="..."/>)
in data/missiles/macros/ or the matching data/deployables/<type>/ folder.
Most deployables_base stat columns only apply to one deployable_type (e.g.
radar_range/explosion_strength are satellite-only, explosion_damage/
trigger_oncollision are mine-only) and are null for the others -- that's
expected, not a gap. The nav beacon is its own small wrinkle: its
<explosiondamage> element carries the value under a "max" attribute
instead of every other deployable_type's "value" -- analyze_deployable_macro
checks both.

Laser towers are the one deployable_type extracted from ship-macro
territory (assets/units/size_s|xs/macros/) rather than a dedicated
standalone-equipment catalog folder -- see extract_game_data.py's
deployable_jobs() docstring for why the XS variant needed its own
extraction job despite SHIP_SIZES excluding "xs" entirely.

Missiles DO have a compatibility concept after all -- it just isn't a
separate mount/component file the way turrets/engines/shields/weapons
have one. A missile's own <missile tags="..."/> (not the sibling
<ammunition value="X" reload="Y"/> element, a same-named but unrelated
per-shot-ammo/reload stat already captured as ammunition_value/
ammunition_reload) carries a single token pairing size and type -- e.g.
"mediumdumbfire", "largetorpedo" -- captured as missiles_base.compatibility.
A missile-capable turret_base/weapons_base row carries the matching
concept the other way around: its own macro's <ammunition tags="..."/>
(again, a same-named-but-different element -- this one on the launcher,
not the missile) lists the *set* of tokens it accepts (e.g.
"dumbfire,mediumdumbfire"), captured as ammunition_tags, plus <storage
capacity="N"/> (how many missiles it holds) as ammunition_capacity. Both
are None for a non-missile-capable turret/weapon, which has neither
element at all. A missile is compatible with a launcher when the
missile's own compatibility token is a member of that launcher's
ammunition_tags set -- this was spot-checked across every dumbfire/guided
turret that survived filter_to_real_equipment_wares and held consistently.
query_ship_components.py's matching_items() now uses this directly (a
"software"-style special case keyed on component_type == "software"'s
sibling, not the generic (size, compatibility) path every other type
uses), surfaced in the UI's own Ammunition section.

Drones
------
Drone wares (fighting/mining/building/cargo/repair drones, plus a handful
of faction police drones) are structurally near-identical to a real ship's
own macro -- same macro class ("ship_s"), a <software> compatibility
block, <hull>, <physics>, even a <ship type="..."/> (always "smalldrone")
-- but are tagged "drone" instead of "ship" in wares.xml, so
parse_ship_wares (which requires the "ship" tag) never picks them up.
They also don't fit ship_component_groups' model even if they did: a
drone's equipment is a single fixed <loadouts><loadout id="default"> (one
specific engine/weapon/thruster macro baked in), not swappable
<connection>-tagged hardpoints -- there's nothing for parse_component_slots
to find. So drones_base is its own self-contained table instead (no
equipment_wares_base or ships_base row), built the same "parse broad from
wares.xml, then read the macro when one exists" shape as
missiles_base/deployables_base.

parse_drone_wares finds every ware tagged "drone" plus "equipment" in
wares.xml (11 total: arg/par/tel police drones, plus generic fighting/
mining-liquid/mining-solid/building/cargo/repair drones) -- all of them
real, standalone-purchasable wares in their own right (unlike software,
nothing here needs filtering against ship-reachability). Only 3 of the 11
(the "gen"-faction fighting/mining drones, all size "s") actually have a
macro file present in this extracted dataset; the other 8 (the "xs"-sized
generic drones and all 5 police drones) are referenced but the macro file
itself doesn't exist anywhere in data/, the same situation as software's
"software_dummy_macro"/scanner placeholders -- analyze_drone_macro's
stat columns (ship_type, purpose, hull, physics_mass) are simply null for
those 8, not a parsing gap. `purpose` (<purpose primary="..."/>, e.g.
"fight"/"mine") is a more useful role classification than `ship_type`
(which is "smalldrone" for every drone alike) and is captured for that
reason.

Countermeasures and crew
-------------------------
Two more standalone, self-contained-ware tables, each the smallest of the
"parse broad from wares.xml" family here -- neither needs a macro lookup at
all, just the wares.xml <ware> entry itself.

countermeasures_base: parse_countermeasure_wares finds every ware tagged
"equipment" plus "countermeasure" -- exactly one in the base game,
"countermeasure_flares_01" ("Flares"), with a real production recipe
(advancedcomposites + energycells). As covered above, there is no per-ship
flare *capacity* anywhere in the game data (ships_base has no matching
column) -- the frontend assumes a fixed default by ship size instead
(COUNTERMEASURE_CAPACITY_BY_SIZE in app.js), the same shape as its existing
DEPLOYABLE_CAPACITY_BY_SIZE assumption.

crew_base: parse_crew_ware finds the single ware id="crew" ("Crew") --
unlike everything else in this module it carries no tags at all in
wares.xml, so it's matched directly by id rather than by tag, and it has no
<production> block (bought outright, not manufactured, so it's always a
leaf in production_wares). X4 has no separate "marine" ware: a marine is
just crew assigned that combat role aboard ship, so this single ware covers
both. The capacity it fills is ships_base.crew, already captured from the
macro's own <people capacity="..."/> (see "Ship stats and flight model"
above) -- nothing new needed there, only the ware itself was missing.

crew_base.name is hardcoded to "Crew" rather than resolved through the
name-reference table like every other ware in this module -- the ware's own
name="{20208,10401}" reference resolves to "Crewman(male)" (page 20208 is a
table of gendered per-NPC display strings, and Egosoft's own wares.xml just
points this ware's name at the "male" variant instead of a proper generic
name). See the crew_wares loop in main() for the full explanation.
"""

import csv
import re
import sqlite3
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
LANG_FILE = DATA / "names" / "0001-l044.xml"
WARES_DIR = DATA / "libraries"
SQL_OUT = ROOT / "src" / "sql" / "ships_tables.sql"
SHIPS_CSV_OUT = ROOT / "src" / "csv" / "ships_base.csv"
PRODUCTION_WARES_CSV_OUT = ROOT / "src" / "csv" / "production_wares.csv"
COMPONENT_GROUPS_CSV_OUT = ROOT / "src" / "csv" / "ship_component_groups.csv"
FLIGHT_MODEL_CSV_OUT = ROOT / "src" / "csv" / "flight_model.csv"
ECONOMY_WARES_CSV_OUT = ROOT / "src" / "csv" / "economy_wares_base.csv"
EQUIPMENT_WARES_CSV_OUT = ROOT / "src" / "csv" / "equipment_wares_base.csv"
EQUIPMENT_WARE_ALIASES_CSV_OUT = ROOT / "src" / "csv" / "equipment_ware_aliases.csv"
TURRETS_CSV_OUT = ROOT / "src" / "csv" / "turrets_base.csv"
ENGINES_CSV_OUT = ROOT / "src" / "csv" / "engines_base.csv"
SHIELDS_CSV_OUT = ROOT / "src" / "csv" / "shields_base.csv"
WEAPONS_CSV_OUT = ROOT / "src" / "csv" / "weapons_base.csv"
THRUSTERS_CSV_OUT = ROOT / "src" / "csv" / "thrusters_base.csv"
SOFTWARE_CSV_OUT = ROOT / "src" / "csv" / "software_base.csv"
MISSILES_CSV_OUT = ROOT / "src" / "csv" / "missiles_base.csv"
DEPLOYABLES_CSV_OUT = ROOT / "src" / "csv" / "deployables_base.csv"
DRONES_CSV_OUT = ROOT / "src" / "csv" / "drones_base.csv"
COUNTERMEASURES_CSV_OUT = ROOT / "src" / "csv" / "countermeasures_base.csv"
CREW_CSV_OUT = ROOT / "src" / "csv" / "crew_base.csv"
DB_OUT = DATA / "x4.db"

EQUIPMENT_SIZES = ("s", "m", "l", "xl")
TURRETS_DIR = DATA / "turrets"
TURRET_SIZES = EQUIPMENT_SIZES
TURRET_MACRO_DIRS = {size: TURRETS_DIR / f"turret_{size}_macros" for size in TURRET_SIZES}
TURRET_COMPONENT_DIRS = {size: TURRETS_DIR / f"turret_{size}_components" for size in TURRET_SIZES}
ENGINES_DIR = DATA / "engines"
ENGINE_MACRO_DIRS = {size: ENGINES_DIR / f"engine_{size}_macros" for size in EQUIPMENT_SIZES}
ENGINE_COMPONENT_DIRS = {size: ENGINES_DIR / f"engine_{size}_components" for size in EQUIPMENT_SIZES}
SHIELDS_DIR = DATA / "shields"
SHIELD_MACRO_DIRS = {size: SHIELDS_DIR / f"shield_{size}_macros" for size in EQUIPMENT_SIZES}
SHIELD_COMPONENT_DIRS = {size: SHIELDS_DIR / f"shield_{size}_components" for size in EQUIPMENT_SIZES}
WEAPONS_DIR = DATA / "weapons"
WEAPON_MACRO_DIRS = {size: WEAPONS_DIR / f"weapon_{size}_macros" for size in EQUIPMENT_SIZES}
WEAPON_COMPONENT_DIRS = {size: WEAPONS_DIR / f"weapon_{size}_components" for size in EQUIPMENT_SIZES}
# Thrusters carry no faction/tier lock in the game data (no <owner>, no
# compatibility tag) -- this sentinel stands in for a real compatibility
# class so thrusters_base rows and the synthesized ship_component_groups
# thruster group can still be matched via the same (size, compatibility)
# lookup query_ship_components.py's matching_items() already uses for every
# other equipment type. See the "Thrusters" section of this module's
# docstring.
THRUSTER_COMPATIBILITY = "universal"
THRUSTER_WARE_RE = re.compile(r"^thruster_[a-z]+_(s|m|l|xl)_(allround|combat)_\d+_mk(\d+)$")
# Software has no size/mount concept at all (see the "Software" section of
# this module's docstring) -- this sentinel fills ship_component_groups.size
# (NOT NULL) for software groups, which are matched by explicit ware_id
# membership rather than by size.
SOFTWARE_SIZE = "any"
SOFTWARE_WARE_RE = re.compile(r"^software_([a-z]+)mk(\d+)$")
MISSILES_MACRO_DIR = DATA / "missiles" / "macros"
DEPLOYABLES_DIR = DATA / "deployables"
DEPLOYABLE_MACRO_DIRS = {
    "satellite": DEPLOYABLES_DIR / "satellites",
    "resourceprobe": DEPLOYABLES_DIR / "probes",
    "mine": DEPLOYABLES_DIR / "mines",
    "lasertower": DEPLOYABLES_DIR / "lasertowers",
    "navbeacon": DEPLOYABLES_DIR / "navbeacons",
}

# Insertion order matters a little for readability (parents before children)
# even though SQLite doesn't enforce FKs here by default.
TABLE_CSV_FILES = {
    "ships_base": SHIPS_CSV_OUT,
    "economy_wares_base": ECONOMY_WARES_CSV_OUT,
    "equipment_wares_base": EQUIPMENT_WARES_CSV_OUT,
    "equipment_ware_aliases": EQUIPMENT_WARE_ALIASES_CSV_OUT,
    "turrets_base": TURRETS_CSV_OUT,
    "engines_base": ENGINES_CSV_OUT,
    "shields_base": SHIELDS_CSV_OUT,
    "weapons_base": WEAPONS_CSV_OUT,
    "thrusters_base": THRUSTERS_CSV_OUT,
    "software_base": SOFTWARE_CSV_OUT,
    "missiles_base": MISSILES_CSV_OUT,
    "deployables_base": DEPLOYABLES_CSV_OUT,
    "drones_base": DRONES_CSV_OUT,
    "countermeasures_base": COUNTERMEASURES_CSV_OUT,
    "crew_base": CREW_CSV_OUT,
    "production_wares": PRODUCTION_WARES_CSV_OUT,
    "ship_component_groups": COMPONENT_GROUPS_CSV_OUT,
    "flight_model": FLIGHT_MODEL_CSV_OUT,
}

EQUIPMENT_TYPE_TAGS = ("engine", "shield", "weapon", "turret", "thruster")


def classify_equipment_type(tags: set[str]) -> str | None:
    return next((t for t in EQUIPMENT_TYPE_TAGS if t in tags), None)

SHIP_SIZES = ("s", "m", "l", "xl")
SHIPS_DIR = DATA / "ships"
SIZE_MACRO_DIRS = {size: SHIPS_DIR / f"size_{size}_macros" for size in SHIP_SIZES}
SIZE_COMPONENT_DIRS = {size: SHIPS_DIR / f"size_{size}_components" for size in SHIP_SIZES}

REF_RE = re.compile(r"\{(\d+),\s*(\d+)\}")
FULL_REF_RE = re.compile(r"^\{(\d+),\s*(\d+)\}$")
# Dev-comment prefix, e.g. "(Magnetar \(Gas\) Vanguard){20101,11101} ...".
# Escaped \( \) inside the comment must not be treated as the closing paren.
LEADING_PAREN_RE = re.compile(r"^\((?:\\.|[^()])*\)\s*")
ESCAPED_PAREN_RE = re.compile(r"\\([()])")

# Every real, player-selectable production method (a ware's own
# <production method="..." name="{page,id}"/>) across the whole dataset,
# manually curated from a direct audit of every distinct resolved method
# name against how often each is tagged "noplayerbuild" (an NPC/enemy-only
# recipe variant, never something a player's own factory can build to):
#   Universal 1064/1064 clean, Terran 143/143, Boron 76/76, Teladi 12/12,
#   Argon 7/7, Paranid 7/7, Closed Loop 4/4, Split 2/2 -- all fully player-
#   buildable, kept as-is.
#   Xenon 127/127 noplayerbuild -- the enemy faction's own recipe variant,
#   dropped entirely (never a real choice).
#   Recycling 5/5 noplayerbuild -- kept anyway: unlike Xenon this is a real,
#   player-accessible activity (Scrap Processor stations are player-
#   buildable), the tag just means this exact recipe variant isn't
#   selectable as a factory blueprint.
#   A second, garbled method (2/2 noplayerbuild, "Processing" followed by a
#   giant leaked dev comment -- its own name="{20206,1301}" resolves via a
#   *trailing*, not leading, "(...)" comment, which resolve_text() has no
#   safe way to strip generically: a regex matching an unescaped trailing
#   "(...)" also matches inside strings using ESCAPED_PAREN_RE's own escape
#   convention (e.g. ship names like "Magnetar \(Gas\) Vanguard"), silently
#   corrupting them. Not worth a bigger fix for one ware's cosmetic name --
#   dropped instead, same Scrap-Processor/recycling concept as Recycling
#   above in practice, and only 2 occurrences total.
# Ordered Universal first, Terran second, Recycling last (all explicit
# product requirements), everything else alphabetically between.
BUILD_METHODS = [
    "Universal",
    "Terran",
    "Argon",
    "Boron",
    "Closed Loop",
    "Paranid",
    "Split",
    "Teladi",
    "Recycling",
]

COMPONENT_TYPES = ("engine", "turret", "weapon", "shield")
# Groups that always combine into a single named group rather than one row
# per slot -- this is how the game itself treats them regardless of size.
COMBINED_GROUP_TYPES = ("engine", "missile_launcher")
SIZE_TOKENS = {"small": "s", "medium": "m", "large": "l", "extralarge": "xl"}


def load_language_table(path: Path) -> dict[tuple[str, str], str]:
    """Build a {(page_id, entry_id): raw_text} lookup from a language XML file."""
    tree = ET.parse(path)
    table: dict[tuple[str, str], str] = {}
    for page in tree.getroot().findall("page"):
        page_id = page.get("id")
        for t in page.findall("t"):
            table[(page_id, t.get("id"))] = t.text or ""
    return table


def resolve_text(raw: str, table: dict, depth: int = 0) -> str:
    """Resolve a raw language-table string, recursively substituting any
    embedded {page,id} references and dropping leading '(...)' dev comments
    (e.g. "(Buster Vanguard){20101,10201} {20111,1101}" -> "Buster Vanguard").
    """
    if not raw or depth > 5:
        return raw or ""

    text = LEADING_PAREN_RE.sub("", raw, count=1)

    def _sub(m: re.Match) -> str:
        key = (m.group(1), m.group(2))
        inner = table.get(key)
        return resolve_text(inner, table, depth + 1) if inner is not None else m.group(0)

    text = REF_RE.sub(_sub, text)
    text = ESCAPED_PAREN_RE.sub(r"\1", text)
    return text.strip()


def resolve_ref_attr(attr_value: str | None, table: dict) -> str:
    """Resolve a name="{page,id}" attribute into display text."""
    if not attr_value:
        return ""
    m = FULL_REF_RE.match(attr_value.strip())
    if not m:
        return attr_value
    raw = table.get((m.group(1), m.group(2)))
    return resolve_text(raw, table) if raw is not None else attr_value


def wares_files() -> list[Path]:
    """Base game wares.xml plus every expansion's wares_<suffix>.xml."""
    return sorted(WARES_DIR.glob("wares*.xml"))


def iter_ware_elements(path: Path):
    """Yield <ware> elements from a wares file.

    Base wares.xml has a plain <wares> root with <ware> children. Each
    expansion's wares_<suffix>.xml is a <diff> patch instead: new ware
    definitions live inside <add sel="/wares"> blocks. Patches to existing
    wares (<add sel="/wares/ware[@id='...']">) are intentionally skipped --
    see the "Expansion ships" note in the module docstring.
    """
    root = ET.parse(path).getroot()
    if root.tag == "wares":
        yield from root.findall("ware")
    elif root.tag == "diff":
        for add in root.findall("add"):
            if add.get("sel") == "/wares":
                yield from add.findall("ware")
    else:
        raise ValueError(f"Unexpected root tag '{root.tag}' in {path}")


def parse_ship_wares(paths: list[Path]) -> list[dict]:
    ships = []
    seen_ids: set[str] = set()
    for path in paths:
        for ware in iter_ware_elements(path):
            tags = (ware.get("tags") or "").split()
            if "ship" not in tags:
                continue

            ware_id = ware.get("id")
            if ware_id in seen_ids:
                print(f"WARNING: duplicate ware id '{ware_id}' (in {path.name}), skipping")
                continue
            seen_ids.add(ware_id)

            owners = [o.get("faction") for o in ware.findall("owner")]

            price = ware.find("price")
            macro_el = ware.find("component")

            productions = []
            for prod in ware.findall("production"):
                wares_needed = {}
                primary = prod.find("primary")
                if primary is not None:
                    for w in primary.findall("ware"):
                        wares_needed[w.get("ware")] = int(w.get("amount"))
                productions.append(
                    {
                        "method_name_ref": prod.get("name"),
                        "time": float(prod.get("time")),
                        "produced_amount": int(prod.get("amount")),
                        "wares": wares_needed,
                    }
                )

            ships.append(
                {
                    "ware_id": ware_id,
                    "name_ref": ware.get("name"),
                    "owners": owners,
                    "price_min": price.get("min") if price is not None else None,
                    "price_avg": price.get("average") if price is not None else None,
                    "price_max": price.get("max") if price is not None else None,
                    "macro": macro_el.get("ref") if macro_el is not None else None,
                    "productions": productions,
                }
            )
    return ships


def parse_economy_wares(paths: list[Path]) -> list[dict]:
    """Parse every ware tagged "economy" (raw resources, refined goods,
    hightech/shiptech components, food, pharmaceuticals -- the production
    chain materials, as opposed to ships or equipment), plus wares tagged
    "processed" -- these are raw salvage materials (e.g. rawscrap,
    rawkhaakscrap) that are consumed by economy ware recipes (scrapmetal,
    khaakscrapmetal) but aren't tagged "economy" themselves since they have
    no production recipe of their own; they're only obtainable by salvaging
    in-game. Including them here closes an FK gap where production_wares
    referenced them with no matching base row.

    Unlike ships, an economy ware commonly has *multiple* <production>
    blocks -- e.g. "engineparts" has a "default" recipe using refinedmetals
    and a "teladi" recipe using teladianium instead -- so all of them are
    kept, not just the first.
    """
    wares = []
    seen_ids: set[str] = set()
    for path in paths:
        for ware in iter_ware_elements(path):
            tags = (ware.get("tags") or "").split()
            if "economy" not in tags and "processed" not in tags:
                continue

            ware_id = ware.get("id")
            if ware_id in seen_ids:
                print(f"WARNING: duplicate ware id '{ware_id}' (in {path.name}), skipping")
                continue
            seen_ids.add(ware_id)

            price = ware.find("price")

            productions = []
            for prod in ware.findall("production"):
                wares_needed = {}
                primary = prod.find("primary")
                if primary is not None:
                    for w in primary.findall("ware"):
                        wares_needed[w.get("ware")] = int(w.get("amount"))
                productions.append(
                    {
                        "method_name_ref": prod.get("name"),
                        "produced_amount": int(prod.get("amount")),
                        "wares": wares_needed,
                    }
                )

            wares.append(
                {
                    "ware_id": ware_id,
                    "name_ref": ware.get("name"),
                    "price_min": price.get("min") if price is not None else None,
                    "price_avg": price.get("average") if price is not None else None,
                    "price_max": price.get("max") if price is not None else None,
                    "productions": productions,
                }
            )
    return wares


def parse_equipment_wares(paths: list[Path]) -> list[dict]:
    """Parse every ware tagged "equipment" plus one of "engine"/"shield"/
    "weapon"/"turret" -- mountable ship components, as opposed to economy
    wares (production chain materials) or ships themselves. Missile
    launchers aren't their own tag category: a weapon or turret additionally
    tagged "missilelauncher" is one, recorded as a boolean.

    Same price/production parsing as parse_economy_wares (all production
    blocks kept, not just the first) -- deliberately nothing about the
    ware's own hardpoint slots or combat stats, see the module docstring.
    """
    wares = []
    seen_ids: set[str] = set()
    for path in paths:
        for ware in iter_ware_elements(path):
            tags = set((ware.get("tags") or "").split())
            equipment_type = classify_equipment_type(tags)
            if "equipment" not in tags or equipment_type is None:
                continue

            ware_id = ware.get("id")
            if ware_id in seen_ids:
                print(f"WARNING: duplicate ware id '{ware_id}' (in {path.name}), skipping")
                continue
            seen_ids.add(ware_id)

            price = ware.find("price")

            productions = []
            for prod in ware.findall("production"):
                wares_needed = {}
                primary = prod.find("primary")
                if primary is not None:
                    for w in primary.findall("ware"):
                        wares_needed[w.get("ware")] = int(w.get("amount"))
                productions.append(
                    {
                        "method_name_ref": prod.get("name"),
                        "produced_amount": int(prod.get("amount")),
                        "wares": wares_needed,
                    }
                )

            wares.append(
                {
                    "ware_id": ware_id,
                    "name_ref": ware.get("name"),
                    "equipment_type": equipment_type,
                    "missile_launcher": "missilelauncher" in tags,
                    "price_min": price.get("min") if price is not None else None,
                    "price_avg": price.get("average") if price is not None else None,
                    "price_max": price.get("max") if price is not None else None,
                    "productions": productions,
                }
            )
    return wares


def parse_missile_wares(paths: list[Path]) -> list[dict]:
    """Parse every ware tagged "equipment" plus "missile" -- ammo fired by a
    missile launcher (a weapon/turret ware in equipment_wares_base with
    missile_launcher=True), not the launcher itself. Excludes ~15 legacy
    "deprecated"-tagged missile wares left over from an old naming scheme
    (e.g. "missile_dumbfire_heavy_mk1", superseded by
    "missile_gen_*_dumbfire_*"): they carry no "equipment" tag at all, so
    requiring "equipment" alongside "missile" excludes them without a
    separate deprecated check.

    Same price/production parsing as parse_equipment_wares (all production
    blocks kept, not just the first).
    """
    wares = []
    seen_ids: set[str] = set()
    for path in paths:
        for ware in iter_ware_elements(path):
            tags = (ware.get("tags") or "").split()
            if "equipment" not in tags or "missile" not in tags:
                continue

            ware_id = ware.get("id")
            if ware_id in seen_ids:
                print(f"WARNING: duplicate ware id '{ware_id}' (in {path.name}), skipping")
                continue
            seen_ids.add(ware_id)

            price = ware.find("price")
            component_el = ware.find("component")

            productions = []
            for prod in ware.findall("production"):
                wares_needed = {}
                primary = prod.find("primary")
                if primary is not None:
                    for w in primary.findall("ware"):
                        wares_needed[w.get("ware")] = int(w.get("amount"))
                productions.append(
                    {
                        "method_name_ref": prod.get("name"),
                        "produced_amount": int(prod.get("amount")),
                        "wares": wares_needed,
                    }
                )

            wares.append(
                {
                    "ware_id": ware_id,
                    "name_ref": ware.get("name"),
                    "macro": component_el.get("ref") if component_el is not None else None,
                    "price_min": price.get("min") if price is not None else None,
                    "price_avg": price.get("average") if price is not None else None,
                    "price_max": price.get("max") if price is not None else None,
                    "productions": productions,
                }
            )
    return wares


DEPLOYABLE_TYPE_TAGS = ("satellite", "resourceprobe", "mine", "lasertower", "navbeacon")


def classify_deployable_type(tags: set[str]) -> str | None:
    return next((t for t in DEPLOYABLE_TYPE_TAGS if t in tags), None)


def parse_deployable_wares(paths: list[Path]) -> list[dict]:
    """Parse every ware tagged "equipment" plus one of "satellite"/
    "resourceprobe"/"mine"/"lasertower"/"navbeacon" -- standalone
    deployable objects launched from cargo, as opposed to
    equipment_wares_base's ship-mounted hardpoint equipment (engine/
    shield/weapon/turret).

    Same price/production parsing as parse_equipment_wares.
    """
    wares = []
    seen_ids: set[str] = set()
    for path in paths:
        for ware in iter_ware_elements(path):
            tags = set((ware.get("tags") or "").split())
            deployable_type = classify_deployable_type(tags)
            if "equipment" not in tags or deployable_type is None:
                continue

            ware_id = ware.get("id")
            if ware_id in seen_ids:
                print(f"WARNING: duplicate ware id '{ware_id}' (in {path.name}), skipping")
                continue
            seen_ids.add(ware_id)

            price = ware.find("price")
            component_el = ware.find("component")

            productions = []
            for prod in ware.findall("production"):
                wares_needed = {}
                primary = prod.find("primary")
                if primary is not None:
                    for w in primary.findall("ware"):
                        wares_needed[w.get("ware")] = int(w.get("amount"))
                productions.append(
                    {
                        "method_name_ref": prod.get("name"),
                        "produced_amount": int(prod.get("amount")),
                        "wares": wares_needed,
                    }
                )

            wares.append(
                {
                    "ware_id": ware_id,
                    "name_ref": ware.get("name"),
                    "deployable_type": deployable_type,
                    "macro": component_el.get("ref") if component_el is not None else None,
                    "price_min": price.get("min") if price is not None else None,
                    "price_avg": price.get("average") if price is not None else None,
                    "price_max": price.get("max") if price is not None else None,
                    "productions": productions,
                }
            )
    return wares


def parse_drone_wares(paths: list[Path]) -> list[dict]:
    """Parse every ware tagged "drone" plus "equipment" -- standalone
    launchable drones (fighting/mining/building/cargo/repair, plus a
    handful of faction police drones), as opposed to ships_base (which
    only picks up wares tagged "ship") and equipment_wares_base's ship-
    mounted hardpoint equipment. See the "Drones" section of this module's
    docstring for why these don't fit either of those tables. Unlike
    software_base, every candidate here is a real, standalone-purchasable
    ware in its own right (confirmed via wares.xml), so there's no
    ship-reachability filtering step needed the way software_base has one.

    Same price/production parsing as parse_deployable_wares.
    """
    wares = []
    seen_ids: set[str] = set()
    for path in paths:
        for ware in iter_ware_elements(path):
            tags = set((ware.get("tags") or "").split())
            if "equipment" not in tags or "drone" not in tags:
                continue

            ware_id = ware.get("id")
            if ware_id in seen_ids:
                print(f"WARNING: duplicate ware id '{ware_id}' (in {path.name}), skipping")
                continue
            seen_ids.add(ware_id)

            price = ware.find("price")
            component_el = ware.find("component")

            productions = []
            for prod in ware.findall("production"):
                wares_needed = {}
                primary = prod.find("primary")
                if primary is not None:
                    for w in primary.findall("ware"):
                        wares_needed[w.get("ware")] = int(w.get("amount"))
                productions.append(
                    {
                        "method_name_ref": prod.get("name"),
                        "produced_amount": int(prod.get("amount")),
                        "wares": wares_needed,
                    }
                )

            wares.append(
                {
                    "ware_id": ware_id,
                    "name_ref": ware.get("name"),
                    "macro": component_el.get("ref") if component_el is not None else None,
                    "price_min": price.get("min") if price is not None else None,
                    "price_avg": price.get("average") if price is not None else None,
                    "price_max": price.get("max") if price is not None else None,
                    "productions": productions,
                }
            )
    return wares


def parse_countermeasure_wares(paths: list[Path]) -> list[dict]:
    """Parse every ware tagged "equipment" plus "countermeasure" -- just
    "countermeasure_flares_01" ("Flares") in the base game. See
    "Countermeasures and crew" in this module's docstring for why there's
    no per-ship capacity captured alongside it.

    Same price/production parsing as parse_drone_wares.
    """
    wares = []
    seen_ids: set[str] = set()
    for path in paths:
        for ware in iter_ware_elements(path):
            tags = set((ware.get("tags") or "").split())
            if "equipment" not in tags or "countermeasure" not in tags:
                continue

            ware_id = ware.get("id")
            if ware_id in seen_ids:
                print(f"WARNING: duplicate ware id '{ware_id}' (in {path.name}), skipping")
                continue
            seen_ids.add(ware_id)

            price = ware.find("price")

            productions = []
            for prod in ware.findall("production"):
                wares_needed = {}
                primary = prod.find("primary")
                if primary is not None:
                    for w in primary.findall("ware"):
                        wares_needed[w.get("ware")] = int(w.get("amount"))
                productions.append(
                    {
                        "method_name_ref": prod.get("name"),
                        "produced_amount": int(prod.get("amount")),
                        "wares": wares_needed,
                    }
                )

            wares.append(
                {
                    "ware_id": ware_id,
                    "name_ref": ware.get("name"),
                    "price_min": price.get("min") if price is not None else None,
                    "price_avg": price.get("average") if price is not None else None,
                    "price_max": price.get("max") if price is not None else None,
                    "productions": productions,
                }
            )
    return wares


def parse_crew_ware(paths: list[Path]) -> list[dict]:
    """Find the single ware id="crew" ("Crew") directly by id -- unlike
    every other ware category in this module it carries no tags at all in
    wares.xml, so there's no tag to filter on, and it has no <production>
    block (bought outright, never manufactured). See "Countermeasures and
    crew" in this module's docstring.
    """
    wares = []
    seen_ids: set[str] = set()
    for path in paths:
        for ware in iter_ware_elements(path):
            if ware.get("id") != "crew":
                continue
            if "crew" in seen_ids:
                print(f"WARNING: duplicate ware id 'crew' (in {path.name}), skipping")
                continue
            seen_ids.add("crew")

            price = ware.find("price")
            wares.append(
                {
                    "ware_id": "crew",
                    "name_ref": ware.get("name"),
                    "price_min": price.get("min") if price is not None else None,
                    "price_avg": price.get("average") if price is not None else None,
                    "price_max": price.get("max") if price is not None else None,
                    "productions": [],
                }
            )
    return wares


def parse_thruster_wares(paths: list[Path]) -> list[dict]:
    """Build thrusters_base's rows: one per ware tagged "equipment" plus
    "thruster". Name/price/production live on equipment_wares_base instead
    (parse_equipment_wares already covers the "thruster" tag via
    EQUIPMENT_TYPE_TAGS) -- this only produces the type-specific columns,
    same division of labor as engines_base/shields_base/weapons_base/
    turrets_base vs. equipment_wares_base.

    Unlike those four, thrusters have no macro or component file anywhere
    in the extracted data (data/thrusters/ doesn't exist) -- the game
    doesn't give them their own hardpoint-mount connection to look up
    size/compatibility from, and there's no <properties> block to read
    mk from either. But their ware ids already fully encode the only
    per-ware facts that would otherwise come from a macro: size, class
    ("allround"/"combat" -- a player playstyle choice, not a tier), and mk
    (e.g. "thruster_gen_m_combat_01_mk2") -- so those are recovered
    straight from the ware_id via THRUSTER_WARE_RE instead. `compatibility`
    is always THRUSTER_COMPATIBILITY (see its own comment) since the game
    data has no per-thruster faction/tier lock at all.
    """
    rows = []
    seen_ids: set[str] = set()
    for path in paths:
        for ware in iter_ware_elements(path):
            tags = (ware.get("tags") or "").split()
            if "equipment" not in tags or "thruster" not in tags:
                continue

            ware_id = ware.get("id")
            if ware_id in seen_ids:
                continue  # parse_equipment_wares already warns on this dupe
            seen_ids.add(ware_id)

            match = THRUSTER_WARE_RE.match(ware_id)
            if not match:
                print(f"WARNING: thruster ware id '{ware_id}' doesn't match the expected pattern, skipping")
                continue
            size, thruster_class, mk = match.groups()

            component_el = ware.find("component")
            rows.append(
                {
                    "ware_id": ware_id,
                    "macro": component_el.get("ref") if component_el is not None else None,
                    "mk": int(mk),
                    "thruster_class": thruster_class,
                    "size": size,
                    "compatibility": THRUSTER_COMPATIBILITY,
                }
            )
    return rows


def parse_software_wares(paths: list[Path]) -> list[dict]:
    """Parse every candidate software ware: tagged "equipment" plus
    "software" in wares.xml. This is a broad net (10 wares) -- unlike every
    other equipment type, whether a software ware is actually usable by any
    ship isn't determined by a mount/size/compatibility concept at all
    (there is none), only by whether some ship's own macro <software> block
    actually lists it. main() cross-references this candidate list against
    every ship's macro and filters software_base down to only the wares
    actually reachable that way (see the "Software" section of this
    module's docstring) -- the same two-stage "parse broad, filter to real"
    shape as filter_to_real_equipment_wares, just filtered against
    ship-reachability instead of equipment_wares_base membership.

    Like thrusters, software wares have no macro/component file of their
    own to source additional stats from (most point at a shared
    "software_dummy_macro" placeholder, and the handful that instead
    reference a "scanner_gen_..." macro don't have one anywhere in the
    extracted data either) -- category and mk are recovered from the
    ware_id itself instead (e.g. "software_scannerlongrangemk2"), and
    name/price come straight off the wares.xml entry, the same as
    missiles_base/deployables_base (no equipment_wares_base parent row --
    "software" doesn't fit that table's engine/shield/weapon/turret/
    thruster vocabulary).
    """
    wares = []
    seen_ids: set[str] = set()
    for path in paths:
        for ware in iter_ware_elements(path):
            tags = (ware.get("tags") or "").split()
            if "equipment" not in tags or "software" not in tags:
                continue

            ware_id = ware.get("id")
            if ware_id in seen_ids:
                print(f"WARNING: duplicate ware id '{ware_id}' (in {path.name}), skipping")
                continue
            seen_ids.add(ware_id)

            match = SOFTWARE_WARE_RE.match(ware_id)
            if not match:
                print(f"WARNING: software ware id '{ware_id}' doesn't match the expected pattern, skipping")
                continue
            category, mk = match.groups()

            price = ware.find("price")
            wares.append(
                {
                    "ware_id": ware_id,
                    "name_ref": ware.get("name"),
                    "category": category,
                    "mk": int(mk),
                    "price_min": price.get("min") if price is not None else None,
                    "price_avg": price.get("average") if price is not None else None,
                    "price_max": price.get("max") if price is not None else None,
                }
            )
    return wares


# Tokens that never identify a compatibility requirement -- just mount-
# connection bookkeeping (structural markers, or equipment-only descriptive
# flags like "primary"/"notupgradeable" that never appear on the ship
# connection side either). The equipment type itself ("engine"/"shield"/
# "weapon"/"turret") is stripped per-call in parse_equipment_mount, since
# it's the one structural token that varies.
EQUIPMENT_MOUNT_STRUCTURAL_TOKENS = {
    "component", "hittable", "unhittable", "combat", "primary", "notupgradeable",
}


def parse_equipment_mount(component_path: Path, equip_type: str) -> tuple[str | None, str | None]:
    """Find an equipment component's mount connection -- the one
    <connection tags="..."/> that contains `equip_type` among its many
    connections (most of the rest are cosmetic model/animation parts) --
    and return (size, requirement_tags), e.g. ("m", "standard") or
    ("l", "arg_destroyer_01") or ("m", "advanced,mining").

    `requirement_tags` is every tag on the mount connection *other than*
    the type token, its size token, and pure bookkeeping/descriptive
    tokens (EQUIPMENT_MOUNT_STRUCTURAL_TOKENS) -- comma-joined, sorted for
    a stable/comparable string. This is deliberately the *complete*
    remaining tag set rather than one collapsed "winning" token: a ship
    connection is compatible with this equipment only if every one of
    these tags is also present on the ship's own (much larger, noisier)
    connection tag set -- see query_ship_components.matching_items()'s
    docstring for why the match direction is equipment-subset-of-ship
    rather than the other way, and for the real examples (destroyer main
    guns, mining ship weapon mounts) that motivated this over the old
    single-collapsed-token design.
    """
    tree = ET.parse(component_path)
    for conn in tree.getroot().iter("connection"):
        tokens = (conn.get("tags") or "").split()
        if equip_type not in tokens:
            continue

        size = None
        remaining = set()
        for token in tokens:
            if token == equip_type or token in EQUIPMENT_MOUNT_STRUCTURAL_TOKENS:
                continue
            if token in SIZE_TOKENS:
                size = SIZE_TOKENS[token]
                continue
            remaining.add(token)

        return size, ",".join(sorted(remaining))
    return None, None


def _float_attr(el: ET.Element | None, attr: str) -> float | None:
    if el is None:
        return None
    value = el.get(attr)
    return float(value) if value else None


def parse_equipment_component_wares(
    equip_type: str,
    macro_dirs: dict[str, Path],
    component_dirs: dict[str, Path],
    extract_fields,
) -> tuple[list[dict], dict[str, str]]:
    """Shared engine/shield/weapon/turret parser: walks every macro file
    across all size folders and, for each one, looks up its linked
    component file's mount connection for size/compatibility, then calls
    `extract_fields(properties)` for the type-specific stat columns.
    `ware_id` is recovered from the macro's own `name` attribute, which is
    always "<ware_id>_macro" (verified against wares.xml's
    <component ref="..."/> for each type). Built entirely from
    data/<type>s/ rather than wares.xml.

    A macro carrying its own alias="<other_macro_name>" attribute is
    *sometimes* a redundant "virtual" duplicate of that other ware -- e.g.
    shield_bor_m_standard_01_mk1_macro is an alias of
    shield_bor_m_standard_02_mk1_macro, with the same name, stats, price,
    AND compatibility class, distinguished from the real one only by
    <hull integrated="1"/> (no actual hull value of its own) instead of a
    real <hull max="..."/>. But the alias attribute alone isn't a safe
    exclusion signal by itself -- confirmed by hand (a real regression
    caught via manual testing: the Hydra lost access to Paranid Blast
    Mortar Turrets) that some alias pairs are two genuinely different
    compatibility tiers of the same-named item sharing the alias mechanism
    for some other reason (e.g. turret_par_m_shotgun_01_mk1, "advanced"
    compatibility, is marked as an alias of turret_par_m_shotgun_02_mk1,
    "standard" compatibility -- dropping the "advanced" one the way a
    blanket alias check would breaks any ship whose turret slot actually
    needs that tier). So this only excludes an aliased macro when its own
    (size, compatibility) *exactly matches* its alias target's -- a true
    redundant duplicate -- keeping both when they differ, since then
    they're two distinct, both-needed options that just happen to share a
    display name. This needs every macro's own mount size/compatibility
    already resolved to compare, so it's a second pass over `rows` after
    the main parsing loop below, not a check made inline per-macro.

    Unlike the "no wares.xml entry at all" orphan macros
    filter_to_real_equipment_wares already drops (see its own docstring),
    a true duplicate excluded here DOES have a real, independently-priced
    wares.xml entry -- so equipment_wares_base alone can't tell it apart
    from a genuine ware, and it has to be excluded here instead, at the
    raw-macro level, before it'd otherwise become a second,
    indistinguishable-looking option in the picker. The excluded ware_ids
    are returned alongside the rows (as the second tuple element, now a
    {alias_ware_id: target_ware_id} mapping rather than a bare set) so
    filter_to_real_equipment_wares's own "wares.xml entry with no parsed
    row" check can tell this apart from a genuine parsing gap, and so
    main() can persist the mapping itself into the new
    equipment_ware_aliases table -- a real player-saved ship loadout
    (loadouts.xml, see import_loadouts.py) can still reference an excluded
    alias ware_id directly (the game itself never removed it, only this
    app's own picker treats it as redundant), so anything consuming a
    ware_id from outside this app's own picker needs a way to resolve it
    back to the real, still-listed target ware.

    A few macros (observed for engines/weapons/turrets, never for any real
    ware -- only already-filtered orphan/mission-only ones) use
    <macro ref="..."/> to inherit properties from another macro and only
    override some of them; that inheritance isn't resolved here, so such a
    macro's un-overridden fields come out None. If a future DLC adds a real
    ware using this pattern, its NULL columns will flag the gap.
    """
    rows = []
    alias_of: dict[str, str] = {}
    for size, macro_dir in macro_dirs.items():
        if not macro_dir.exists():
            continue
        for macro_path in sorted(macro_dir.glob("*.xml")):
            macro_el = ET.parse(macro_path).getroot().find("macro")
            if macro_el is None:
                continue
            macro_name = macro_el.get("name")
            ware_id = macro_name.removesuffix("_macro") if macro_name else None

            alias_target = macro_el.get("alias")
            if alias_target:
                alias_of[ware_id] = alias_target.removesuffix("_macro")

            component_el = macro_el.find("component")
            component_ref = component_el.get("ref") if component_el is not None else None

            properties = macro_el.find("properties")
            identification = properties.find("identification") if properties is not None else None
            hull_el = properties.find("hull") if properties is not None else None

            mount_size, compatibility = None, None
            if component_ref:
                component_path = component_dirs[size] / f"{component_ref}.xml"
                if component_path.exists():
                    mount_size, compatibility = parse_equipment_mount(component_path, equip_type)
                else:
                    print(f"WARNING: {equip_type} component file not found for {ware_id} ({component_path})")

            if mount_size and mount_size != size:
                print(
                    f"WARNING: {ware_id}: component mount size '{mount_size}' doesn't match "
                    f"macro folder size '{size}' -- using the component's size"
                )

            row = {
                "ware_id": ware_id,
                "macro": macro_name,
                "owners": identification.get("makerrace") if identification is not None else None,
                "mk": int(identification.get("mk")) if identification is not None and identification.get("mk") else None,
                "hull": int(float(hull_el.get("max"))) if hull_el is not None and hull_el.get("max") else None,
                "size": mount_size or size,
                "compatibility": compatibility,
            }
            row.update(extract_fields(properties))
            rows.append(row)

    rows_by_id = {r["ware_id"]: r for r in rows}
    true_duplicates: dict[str, str] = {}
    for ware_id, target_id in alias_of.items():
        row = rows_by_id.get(ware_id)
        target_row = rows_by_id.get(target_id)
        if row is None or target_row is None:
            continue
        if row["size"] == target_row["size"] and row["compatibility"] == target_row["compatibility"]:
            true_duplicates[ware_id] = target_id

    if true_duplicates:
        print(
            f"  ({len(true_duplicates)} {equip_type} macro(s) excluded as duplicate/alias wares "
            f'(same size+compatibility as their own alias="..." target): {sorted(true_duplicates)})'
        )
    skipped_other_aliases = sorted(set(alias_of) - set(true_duplicates))
    if skipped_other_aliases:
        print(
            f"  ({len(skipped_other_aliases)} {equip_type} macro(s) carry an alias=\"...\" attribute but "
            f"differ in size/compatibility from their target -- kept as distinct, real options: "
            f"{skipped_other_aliases})"
        )

    rows = [r for r in rows if r["ware_id"] not in true_duplicates]
    return rows, true_duplicates


def _ammunition_fields(properties: ET.Element | None) -> dict:
    """Missile-capable turrets/weapons carry an <ammunition tags="..."/>
    element and a <storage capacity="N"/> element; both are absent (None
    here) for every non-missile-capable turret/weapon. `ammunition_tags`
    is the comma-joined, sorted set of missile compatibility tags this
    launcher accepts -- e.g. "dumbfire,mediumdumbfire" -- matched against a
    missile's own single tag (missiles_base.compatibility, e.g.
    "mediumdumbfire") by membership, the same "is this specific token
    among the accepted set" shape used for equipment_compatibility_class
    elsewhere in this pipeline. See the "Missiles" section of this
    module's docstring for how this was discovered/verified. Not yet used
    for any matching/query logic -- this only captures the data.
    `ammunition_capacity` is <storage capacity="N"/> -- how many missiles
    this specific launcher can hold.
    """
    ammunition_el = properties.find("ammunition") if properties is not None else None
    storage_el = properties.find("storage") if properties is not None else None
    tags = (ammunition_el.get("tags") or "").split() if ammunition_el is not None else []
    return {
        "ammunition_tags": ",".join(sorted(tags)) if tags else None,
        "ammunition_capacity": _int_attr(storage_el, "capacity"),
    }


def _turret_fields(properties: ET.Element | None) -> dict:
    bullet_el = properties.find("bullet") if properties is not None else None
    return {
        "bullet_class": bullet_el.get("class") if bullet_el is not None else None,
        "rotation_speed": _float_attr(properties.find("rotationspeed") if properties is not None else None, "max"),
        "rotation_acceleration": _float_attr(
            properties.find("rotationacceleration") if properties is not None else None, "max"
        ),
        **_ammunition_fields(properties),
    }


def _engine_fields(properties: ET.Element | None) -> dict:
    boost = properties.find("boost") if properties is not None else None
    travel = properties.find("travel") if properties is not None else None
    thrust = properties.find("thrust") if properties is not None else None
    return {
        "boost_duration": _float_attr(boost, "duration"),
        "boost_recharge": _float_attr(boost, "recharge"),
        "boost_thrust": _float_attr(boost, "thrust"),
        "boost_acceleration": _float_attr(boost, "acceleration"),
        "boost_attack": _float_attr(boost, "attack"),
        "boost_release": _float_attr(boost, "release"),
        "boost_coast": _float_attr(boost, "coast"),
        "travel_charge": _float_attr(travel, "charge"),
        "travel_thrust": _float_attr(travel, "thrust"),
        "travel_attack": _float_attr(travel, "attack"),
        "travel_release": _float_attr(travel, "release"),
        "thrust_forward": _float_attr(thrust, "forward"),
        "thrust_reverse": _float_attr(thrust, "reverse"),
    }


def _shield_fields(properties: ET.Element | None) -> dict:
    recharge = properties.find("recharge") if properties is not None else None
    return {
        "recharge_max": _float_attr(recharge, "max"),
        "recharge_rate": _float_attr(recharge, "rate"),
        "recharge_delay": _float_attr(recharge, "delay"),
        "recharge_disruptionstability": _float_attr(recharge, "disruptionstability"),
    }


def _weapon_fields(properties: ET.Element | None) -> dict:
    bullet_el = properties.find("bullet") if properties is not None else None
    heat = properties.find("heat") if properties is not None else None
    weapon_el = properties.find("weapon") if properties is not None else None
    return {
        "bullet_class": bullet_el.get("class") if bullet_el is not None else None,
        "heat_overheat": _float_attr(heat, "overheat"),
        "heat_cooldelay": _float_attr(heat, "cooldelay"),
        "heat_coolrate": _float_attr(heat, "coolrate"),
        "heat_reenable": _float_attr(heat, "reenable"),
        "heat_overheatcooldelay": _float_attr(heat, "overheatcooldelay"),
        "rotation_speed": _float_attr(properties.find("rotationspeed") if properties is not None else None, "max"),
        "rotation_acceleration": _float_attr(
            properties.find("rotationacceleration") if properties is not None else None, "max"
        ),
        "weapon_angle": _float_attr(weapon_el, "angle"),
        **_ammunition_fields(properties),
    }


def parse_turrets(macro_dirs: dict[str, Path], component_dirs: dict[str, Path]) -> tuple[list[dict], dict[str, str]]:
    return parse_equipment_component_wares("turret", macro_dirs, component_dirs, _turret_fields)


def parse_engines(macro_dirs: dict[str, Path], component_dirs: dict[str, Path]) -> tuple[list[dict], dict[str, str]]:
    return parse_equipment_component_wares("engine", macro_dirs, component_dirs, _engine_fields)


def parse_shields(macro_dirs: dict[str, Path], component_dirs: dict[str, Path]) -> tuple[list[dict], dict[str, str]]:
    return parse_equipment_component_wares("shield", macro_dirs, component_dirs, _shield_fields)


def parse_weapons(macro_dirs: dict[str, Path], component_dirs: dict[str, Path]) -> tuple[list[dict], dict[str, str]]:
    return parse_equipment_component_wares("weapon", macro_dirs, component_dirs, _weapon_fields)


def _int_attr(el: ET.Element | None, attr: str) -> int | None:
    value = _float_attr(el, attr)
    return int(value) if value is not None else None


MISSILE_STAT_KEYS = [
    "ammunition_value", "ammunition_reload",
    "missile_amount", "missile_barrelamount", "missile_lifetime", "missile_range", "missile_guided",
    "explosiondamage_value", "explosiondamage_shielddisruption",
    "reload_time", "hull", "weapon_system", "countermeasure_resilience", "physics_mass",
    "lock_time", "lock_range", "compatibility",
]
DEPLOYABLE_STAT_KEYS = [
    "hull", "radar_range", "explosion_strength", "explosion_damage", "trigger_oncollision", "physics_mass",
]


def analyze_missile_macro(macro_path: Path) -> dict:
    """Read a missile macro's <properties> -- unlike engine/shield/weapon/
    turret, a missile is self-contained (no separate component file with a
    mount-tag size/compatibility to look up): its own <missile>/
    <explosiondamage>/<physics> elements carry everything.

    `compatibility` is <missile tags="..."/> -- note this is a completely
    different element than the sibling <ammunition value="X" reload="Y"/>
    (already captured as ammunition_value/ammunition_reload above), which
    despite the name collision is this missile's own per-shot ammo count/
    reload, not a compatibility tag. A current (non-deprecated) missile's
    tag is a single token pairing size and type, e.g. "mediumdumbfire" or
    "largetorpedo" -- matched against a launcher's own
    turrets_base/weapons_base.ammunition_tags (a comma-joined *set* of
    these tokens) by membership. The two "flagship" missiles use a ship-
    model lock instead ("ship_ter_l_flagship_01"), the same pattern already
    seen on some L/XL ship-locked weapons. See the "Missiles" section of
    this module's docstring.
    """
    macro_el = ET.parse(macro_path).getroot().find("macro")
    properties = macro_el.find("properties") if macro_el is not None else None

    ammunition = properties.find("ammunition") if properties is not None else None
    missile_el = properties.find("missile") if properties is not None else None
    explosiondamage = properties.find("explosiondamage") if properties is not None else None
    reload_el = properties.find("reload") if properties is not None else None
    hull_el = properties.find("hull") if properties is not None else None
    weapon_el = properties.find("weapon") if properties is not None else None
    countermeasure = properties.find("countermeasure") if properties is not None else None
    physics = properties.find("physics") if properties is not None else None
    lock_el = properties.find("lock") if properties is not None else None

    return {
        "ammunition_value": _int_attr(ammunition, "value"),
        "ammunition_reload": _float_attr(ammunition, "reload"),
        "missile_amount": _int_attr(missile_el, "amount"),
        "missile_barrelamount": _int_attr(missile_el, "barrelamount"),
        "missile_lifetime": _float_attr(missile_el, "lifetime"),
        "missile_range": _float_attr(missile_el, "range"),
        "missile_guided": int(bool(_int_attr(missile_el, "guided"))),
        "explosiondamage_value": _float_attr(explosiondamage, "value"),
        "explosiondamage_shielddisruption": _float_attr(explosiondamage, "shielddisruption"),
        "reload_time": _float_attr(reload_el, "time"),
        "hull": _int_attr(hull_el, "max"),
        "weapon_system": weapon_el.get("system") if weapon_el is not None else None,
        "countermeasure_resilience": _float_attr(countermeasure, "resilience"),
        "physics_mass": _float_attr(physics, "mass"),
        "lock_time": _float_attr(lock_el, "time"),
        "lock_range": _float_attr(lock_el, "range"),
        "compatibility": missile_el.get("tags") if missile_el is not None else None,
    }


def analyze_deployable_macro(macro_path: Path) -> dict:
    """Read a satellite/resource probe/mine/lasertower/navbeacon macro's
    <properties>. Like missiles, deployables are self-contained -- no
    separate component file with a mount-tag to look up.
    """
    macro_el = ET.parse(macro_path).getroot().find("macro")
    properties = macro_el.find("properties") if macro_el is not None else None

    hull_el = properties.find("hull") if properties is not None else None
    radar_el = properties.find("radar") if properties is not None else None
    explosioneffect = properties.find("explosioneffect") if properties is not None else None
    explosiondamage = properties.find("explosiondamage") if properties is not None else None
    trigger_el = properties.find("trigger") if properties is not None else None
    physics = properties.find("physics") if properties is not None else None

    # Every deployable_type spells this "value" except the nav beacon,
    # which uses "max" (<explosiondamage max="50000" /> in the vanilla
    # files) -- checking both keeps that one real, not a missing-tag gap.
    explosion_damage = _float_attr(explosiondamage, "value")
    if explosion_damage is None:
        explosion_damage = _float_attr(explosiondamage, "max")

    return {
        "hull": _int_attr(hull_el, "max"),
        "radar_range": _float_attr(radar_el, "range"),
        "explosion_strength": _float_attr(explosioneffect, "strength"),
        "explosion_damage": explosion_damage,
        "trigger_oncollision": int(bool(_int_attr(trigger_el, "oncollision"))),
        "physics_mass": _float_attr(physics, "mass"),
    }


DRONE_STAT_KEYS = ["ship_type", "purpose", "hull", "physics_mass"]


def analyze_drone_macro(macro_path: Path) -> dict:
    """Read a drone macro's <properties> -- structurally a scaled-down
    ship macro (see the "Drones" section of this module's docstring), so
    this reads the same elements load_macro_data() does for a real ship,
    just the handful actually useful for a drone: its role classification
    (`ship_type` is always "smalldrone" for every drone alike; `purpose`,
    e.g. "fight"/"mine", is the informative one) plus hull/mass. No
    <software>/<jerk>/hardpoint <connections> to read -- a drone's engine/
    weapon/thruster loadout is a single fixed <loadouts> block, not
    swappable equipment.
    """
    macro_el = ET.parse(macro_path).getroot().find("macro")
    properties = macro_el.find("properties") if macro_el is not None else None

    ship_el = properties.find("ship") if properties is not None else None
    purpose_el = properties.find("purpose") if properties is not None else None
    hull_el = properties.find("hull") if properties is not None else None
    physics = properties.find("physics") if properties is not None else None

    return {
        "ship_type": ship_el.get("type") if ship_el is not None else None,
        "purpose": purpose_el.get("primary") if purpose_el is not None else None,
        "hull": _int_attr(hull_el, "max"),
        "physics_mass": _float_attr(physics, "mass"),
    }


def ship_size_code(ware_id: str) -> str | None:
    """Extract the size class from a ware id, e.g. "ship_arg_l_destroyer_01_a" -> "l"."""
    parts = ware_id.split("_")
    if len(parts) < 3 or parts[0] != "ship" or parts[2] not in SIZE_MACRO_DIRS:
        return None
    return parts[2]


def _float_attrs(el, prefix: str) -> dict[str, float]:
    return {f"{prefix}_{attr}": float(value) for attr, value in el.attrib.items()}


def load_macro_data(macro_path: Path) -> dict:
    """Read everything derivable from a ship macro's <properties> block:
    the component ref it points to, ship type, hull, crew, missile ammo
    capacity, travel drive stability, the full flight model (jerk, physics,
    steeringcurve), and the ship's own <software> compatibility list. Any of
    these can be absent for a given ship (e.g. S-class ships have no
    <traveldrivestability>, and <accfactors> attributes vary ship to ship;
    one ship in the whole dataset -- the unbuildable Khaak XL Battleship --
    has no <software> block at all), so callers should treat missing values
    as None/empty rather than assuming a fixed shape.
    """
    tree = ET.parse(macro_path)
    macro_el = tree.getroot().find("macro")
    if macro_el is None:
        return {}

    component_el = macro_el.find("component")
    result: dict = {"component_ref": component_el.get("ref") if component_el is not None else None}

    properties = macro_el.find("properties")
    if properties is None:
        return result

    ship_el = properties.find("ship")
    result["ship_type"] = ship_el.get("type") if ship_el is not None else None

    # AI role classification, e.g. "fight"/"trade"/"mine"/"build"/
    # "auxiliary"/"racing"/"salvage"/"dismantling" -- same element
    # analyze_drone_macro() already reads for drones (see that function's
    # docstring); just never read for real ships until now.
    purpose_el = properties.find("purpose")
    result["purpose"] = purpose_el.get("primary") if purpose_el is not None else None

    # e.g. "ship_s_fighter_01" -- the small ship-class symbol shown in the
    # game's own UI, one per size+purpose combo (not unique per ship: many
    # different fighter-type ships of the same size all share one icon).
    # The actual image (gzip-compressed DDS under
    # assets/textures/ui/shipicon/<icon>.gz in the game's catalogs) is
    # extracted by extract_game_data.py's "ship_icons" job and converted to
    # PNG by generate_ship_icons.py -- see data/images/ships/symbols/.
    identification_el = properties.find("identification")
    result["icon"] = identification_el.get("icon") if identification_el is not None else None

    hull_el = properties.find("hull")
    result["hull"] = int(float(hull_el.get("max"))) if hull_el is not None and hull_el.get("max") else None

    people_el = properties.find("people")
    result["crew"] = int(float(people_el.get("capacity"))) if people_el is not None and people_el.get("capacity") else None

    tds_el = properties.find("traveldrivestability")
    result["traveldrivestability"] = (
        int(float(tds_el.get("maxvalue"))) if tds_el is not None and tds_el.get("maxvalue") else 0
    )

    storage_el = properties.find("storage")
    result["missile_capacity"] = (
        int(float(storage_el.get("missile"))) if storage_el is not None and storage_el.get("missile") else 0
    )
    # <storage> can carry up to four attributes: missile, unit, deployable,
    # countermeasure. "deployable" and "countermeasure" are always 0 on
    # every ship that has them at all (confirmed by inspection -- dead/
    # unused data, not a real capacity), so only "unit" is captured here --
    # it's this ship's drone capacity (how many drones it can carry/deploy),
    # confirmed against ship roles (builders/resuppliers ~100-250,
    # carriers ~20, plain fighters 0/absent).
    result["drone_capacity"] = (
        int(float(storage_el.get("unit"))) if storage_el is not None and storage_el.get("unit") else 0
    )

    software_el = properties.find("software")
    result["software"] = (
        [s.get("ware") for s in software_el.findall("software")] if software_el is not None else []
    )

    jerk_fields: dict[str, float] = {}
    jerk_el = properties.find("jerk")
    if jerk_el is not None:
        for child in jerk_el:
            jerk_fields.update(_float_attrs(child, f"jerk_{child.tag}"))
    result["jerk_fields"] = jerk_fields

    physics_fields: dict[str, float] = {}
    physics_el = properties.find("physics")
    if physics_el is not None:
        if "mass" in physics_el.attrib:
            physics_fields["physics_mass"] = float(physics_el.get("mass"))
        for child in physics_el:
            physics_fields.update(_float_attrs(child, f"physics_{child.tag}"))
    result["physics_fields"] = physics_fields

    steeringcurve = ""
    steeringcurve_el = properties.find("steeringcurve")
    if steeringcurve_el is not None:
        points = sorted(
            (float(p.get("position")), float(p.get("value"))) for p in steeringcurve_el.findall("point")
        )
        steeringcurve = ",".join(f"{pos}:{val}" for pos, val in points)
    result["steeringcurve"] = steeringcurve

    return result


def classify_connection(tags: set[str]) -> tuple[str | None, str | None]:
    comp_type = next((t for t in COMPONENT_TYPES if t in tags), None)
    # A "weapon" connection tagged "missile" is a dedicated missile launcher,
    # not a gun mount -- reclassify it as its own component type. Turrets
    # tagged "missile" stay turrets; that's just their compatibility class.
    if comp_type == "weapon" and "missile" in tags:
        comp_type = "missile_launcher"
    size = next((code for token, code in SIZE_TOKENS.items() if token in tags), None)
    return comp_type, size


def parse_component_slots(path: Path, ship_id: str) -> tuple[dict[tuple[str, str], int], list[dict]]:
    """Parse a ship component file's <connections>.

    Returns (slot_counts, groups):
      - slot_counts: {(component_type, size): count} across the whole ship.
      - groups: one row per (group_name, component_type) pair, each with its
        size, how many slots it holds, its equipment_compatibility_class
        -- the connection's full remaining tag set (comma-joined, sorted),
        not a value drawn from any fixed vocabulary -- and its
        connection_names (comma-joined real <connection name="..."/>
        values, e.g. "con_weapon_01,con_weapon_03"; see
        ship_component_groups' own schema comment for why individual
        connection identity is kept at all despite everything else here
        treating group members as interchangeable). This is per
        *individual* group, not per (component_type, size) -- two same-size turret groups on the
        same ship can carry different classes.

    L/XL ships name most of their engine/turret groups in the XML via a
    "group" attribute, but their main shield and main weapon connections
    often carry no "group" attribute at all -- same as S/M ships, which
    have no such attribute on *any* connection. Either way, a synthetic
    group is created for any connection with no "group" attribute, per the
    game's own convention: engines and missile launchers always combine
    into one shared group ("engine", "missile_launcher"), while
    weapon/turret/shield each get their own group per individual ungrouped
    slot ("weapon_<n>", "turret_<n>", "shield_<n>").

    group_name alone is NOT unique per ship: a dedicated medium shield
    tagged alongside an engine/turret group carries that *same* raw
    "group" attribute value from the XML (kept as-is here, unrenamed --
    ship_component_groups is meant to stay a faithful mirror of the game's
    own group structure, since it may eventually be built directly from
    the XML rather than derived). So group_members (and the resulting
    ship_component_groups table) is keyed by (group_name, component_type)
    together, not group_name alone -- letting a shield entry and its
    sibling engine/turret entry coexist under the identical group_name,
    distinguished only by component_type. A caller that wants "this
    group's dedicated shields" joins on (ship_id, group_name) and filters
    for component_type = "shield".
    """
    tree = ET.parse(path)
    root = tree.getroot()

    slot_counts: dict[tuple[str, str], int] = {}
    group_members: dict[tuple[str, str], dict] = {}
    synth_indices: dict[str, int] = {}

    for conn in root.iter("connection"):
        tags = set((conn.get("tags") or "").split())
        comp_type, comp_size = classify_connection(tags)
        if comp_type is None or comp_size is None:
            continue

        slot_counts[(comp_type, comp_size)] = slot_counts.get((comp_type, comp_size), 0) + 1

        group_name = (conn.get("group") or "").strip()

        if comp_type == "shield":
            if not group_name:
                synth_indices["shield"] = synth_indices.get("shield", 0) + 1
                group_name = f"shield_{synth_indices['shield']}"
            # else: keep the raw group_name as-is -- it's shared with the
            # engine/turret/weapon group this shield protects (see
            # docstring above); (group_name, "shield") is still a distinct
            # key from that sibling's own (group_name, its component_type).
        elif comp_type in COMBINED_GROUP_TYPES:
            if not group_name:
                group_name = comp_type
        else:  # weapon or turret
            if not group_name:
                synth_indices[comp_type] = synth_indices.get(comp_type, 0) + 1
                group_name = f"{comp_type}_{synth_indices[comp_type]}"

        if not group_name:
            continue

        key = (group_name, comp_type)
        # The connection's full tag set minus the type token (any of
        # COMPONENT_TYPES -- not just comp_type, since classify_connection
        # reclassifies a "weapon"-tagged missile launcher to component_type
        # "missile_launcher" while the raw tag itself still reads "weapon")
        # and the size word. No further filtering through a fixed known
        # vocabulary -- see parse_equipment_mount's docstring and
        # query_ship_components.matching_items() for why the full,
        # unfiltered set is what's matched against equipment.
        compat = frozenset(t for t in tags if t not in COMPONENT_TYPES and t not in SIZE_TOKENS)
        entry = group_members.setdefault(key, {"size": comp_size, "compat": set(), "count": 0, "connection_names": []})
        if entry["size"] != comp_size:
            print(f"WARNING: {path.name}: group '{group_name}' ({comp_type}) mixes sizes")
        entry["compat"].add(compat)
        entry["count"] += 1
        # The connection's own real name (e.g. "con_weapon_01") -- every
        # member of a (group_name, comp_type) key is interchangeable for
        # compatibility/cost purposes (that's exactly why they're
        # aggregated into one row instead of tracked individually), so
        # which specific name lines up with which specific equipment
        # choice doesn't matter; this is kept only so a loadout can be
        # exported addressing real connections instead of a synthesized
        # placeholder path (see import_loadouts.py's build_loadout_xml()).
        conn_name = conn.get("name")
        if conn_name:
            entry["connection_names"].append(conn_name)

    groups = []
    for (group_name, comp_type), info in sorted(group_members.items()):
        compat_union = sorted({t for c in info["compat"] for t in c})
        groups.append(
            {
                "group_name": group_name,
                "component_type": comp_type,
                "size": info["size"],
                "slot_count": info["count"],
                "equipment_compatibility_class": ",".join(compat_union),
                "connection_names": ",".join(info["connection_names"]),
            }
        )

    return slot_counts, groups


def analyze_ship_components(ship: dict, size: str | None) -> dict:
    result: dict = {
        "slot_counts": {},
        "groups": [],
        "missile_capacity": 0,
        "drone_capacity": 0,
        "ship_type": None,
        "purpose": None,
        "icon": None,
        "hull": None,
        "crew": None,
        "traveldrivestability": 0,
        "jerk_fields": {},
        "physics_fields": {},
        "steeringcurve": "",
    }

    if size is None:
        print(f"WARNING: couldn't determine size class for {ship['ware_id']}, skipping component analysis")
        return result

    # Thrusters have no <connection> hardpoint in the component file at all
    # (see the "Thrusters" section of this module's docstring) -- every ship
    # just gets exactly one, sized to match its own hull, so it's synthesized
    # here rather than discovered by parse_component_slots below. Added
    # before any of the macro/component lookups below so it's still present
    # even if those fail (it doesn't depend on them).
    result["groups"].append(
        {
            "group_name": "thruster",
            "component_type": "thruster",
            "size": size,
            "slot_count": 1,
            "equipment_compatibility_class": THRUSTER_COMPATIBILITY,
            "connection_names": "",
        }
    )

    if not ship["macro"]:
        print(f"WARNING: no macro ref for {ship['ware_id']}, skipping component analysis")
        return result

    macro_path = SIZE_MACRO_DIRS[size] / f"{ship['macro']}.xml"
    if not macro_path.exists():
        print(f"WARNING: macro file not found for {ship['ware_id']} ({macro_path})")
        return result

    macro_data = load_macro_data(macro_path)
    result["missile_capacity"] = macro_data.get("missile_capacity", 0)
    result["drone_capacity"] = macro_data.get("drone_capacity", 0)
    result["ship_type"] = macro_data.get("ship_type")
    result["purpose"] = macro_data.get("purpose")
    result["icon"] = macro_data.get("icon")
    result["hull"] = macro_data.get("hull")
    result["crew"] = macro_data.get("crew")
    result["traveldrivestability"] = macro_data.get("traveldrivestability", 0)
    result["jerk_fields"] = macro_data.get("jerk_fields", {})
    result["physics_fields"] = macro_data.get("physics_fields", {})
    result["steeringcurve"] = macro_data.get("steeringcurve", "")

    # Software has no <connection> hardpoint or (size, compatibility class)
    # concept at all -- a ship's macro instead lists the exact software
    # ware_ids it can mount directly (see the "Software" section of this
    # module's docstring). Grouped here by category (the ware_id's
    # "software_<category>mk<N>" prefix, e.g. "dock"/"scannerlongrange") --
    # one group per category actually listed for this ship, since a ship
    # only ever lists one or two mk levels of a given category (never more
    # than one category's worth of options mixed together).
    by_category: dict[str, list[str]] = {}
    for ware_id in macro_data.get("software", []):
        match = SOFTWARE_WARE_RE.match(ware_id)
        if not match:
            print(f"WARNING: {ship['ware_id']}: software ware id '{ware_id}' doesn't match the expected pattern, skipping")
            continue
        by_category.setdefault(match.group(1), []).append(ware_id)

    for category, ware_ids in sorted(by_category.items()):
        result["groups"].append(
            {
                "group_name": f"software_{category}",
                "component_type": "software",
                "size": SOFTWARE_SIZE,
                "slot_count": 1,
                "equipment_compatibility_class": ",".join(sorted(ware_ids)),
                "connection_names": "",
            }
        )

    component_ref = macro_data.get("component_ref")
    if not component_ref:
        print(f"WARNING: no component ref in macro for {ship['ware_id']}")
        return result

    component_path = SIZE_COMPONENT_DIRS[size] / f"{component_ref}.xml"
    if not component_path.exists():
        print(f"WARNING: component file not found for {ship['ware_id']} ({component_path})")
        return result

    slot_counts, groups = parse_component_slots(component_path, ship["ware_id"])
    result["slot_counts"] = slot_counts
    result["groups"].extend(groups)
    return result


def summarize_slots(ware_id: str, size: str | None, slot_counts: dict[tuple[str, str], int]) -> dict:
    """Collapse (component_type, size) slot counts into ships_base's flat
    columns: a ship's own engines/shields/weapons always match its own size
    class, so those become single counts; turrets don't, so they stay split
    by size. Two cases exist where a slot legitimately doesn't match the
    ship's own size: bonus medium shields on L/XL ships (shields_bonus_m),
    and off-size weapons like the Asgard's two "large" guns alongside its
    "extralarge" main gun -- those become dynamic bonus_<size>_weapons
    columns, one per off-size actually observed.
    """
    for (comp_type, comp_size), count in slot_counts.items():
        if comp_type == "engine" and comp_size != size:
            print(
                f"WARNING: {ware_id}: engine slot size '{comp_size}' doesn't match "
                f"ship size '{size}' -- included in the flat total anyway"
            )

    engines = sum(count for (t, _), count in slot_counts.items() if t == "engine")
    shields = slot_counts.get(("shield", size), 0) if size else 0
    shields_bonus_m = slot_counts.get(("shield", "m"), 0) if size in ("l", "xl") else 0

    weapons = slot_counts.get(("weapon", size), 0) if size else 0
    weapons_bonus = {sz: count for (t, sz), count in slot_counts.items() if t == "weapon" and sz != size}

    missile_launchers = sum(count for (t, _), count in slot_counts.items() if t == "missile_launcher")

    turrets = {sz: count for (t, sz), count in slot_counts.items() if t == "turret"}

    return {
        "engines": engines,
        "weapons": weapons,
        "weapons_bonus": weapons_bonus,
        "missile_launchers": missile_launchers,
        "shields": shields,
        "shields_bonus_m": shields_bonus_m,
        "turrets": turrets,
    }


def write_sql_schema(
    turret_sizes: list[str],
    bonus_weapon_sizes: list[str],
    jerk_columns: list[str],
    physics_columns: list[str],
    out_path: Path,
) -> None:
    turret_col_defs = ",\n    ".join(f'"turret_{size}" INTEGER' for size in turret_sizes)
    bonus_weapon_col_defs = "".join(f',\n    "bonus_{size}_weapons" INTEGER' for size in bonus_weapon_sizes)
    flight_model_col_defs = "".join(
        f'    "{col}" REAL,\n' for col in jerk_columns + physics_columns
    )
    sql = f"""DROP TABLE IF EXISTS flight_model;
DROP TABLE IF EXISTS ship_component_groups;
DROP TABLE IF EXISTS production_wares;
DROP TABLE IF EXISTS turrets_base;
DROP TABLE IF EXISTS engines_base;
DROP TABLE IF EXISTS shields_base;
DROP TABLE IF EXISTS weapons_base;
DROP TABLE IF EXISTS thrusters_base;
DROP TABLE IF EXISTS software_base;
DROP TABLE IF EXISTS missiles_base;
DROP TABLE IF EXISTS deployables_base;
DROP TABLE IF EXISTS drones_base;
DROP TABLE IF EXISTS countermeasures_base;
DROP TABLE IF EXISTS crew_base;
DROP TABLE IF EXISTS ships_base;
DROP TABLE IF EXISTS economy_wares_base;
DROP TABLE IF EXISTS equipment_ware_aliases;
DROP TABLE IF EXISTS equipment_wares_base;

CREATE TABLE ships_base (
    name TEXT PRIMARY KEY,
    ware_id TEXT NOT NULL UNIQUE,
    owners TEXT,
    price_min INTEGER,
    price_avg INTEGER,
    price_max INTEGER,
    production_time REAL,
    production_method TEXT,
    macro TEXT,
    ship_type TEXT,
    purpose TEXT,
    icon TEXT,
    hull INTEGER,
    crew INTEGER,
    traveldrivestability INTEGER,
    missile_capacity INTEGER,
    drone_capacity INTEGER,
    size TEXT,
    shields INTEGER,
    engines INTEGER,
    weapons INTEGER{bonus_weapon_col_defs},
    missile_launchers INTEGER,
    {turret_col_defs},
    shields_bonus_m INTEGER
);

CREATE TABLE economy_wares_base (
    ware_id TEXT PRIMARY KEY,
    name TEXT,
    price_min INTEGER,
    price_avg INTEGER,
    price_max INTEGER,
    leaf_ware BOOLEAN NOT NULL DEFAULT 0
);

CREATE TABLE equipment_wares_base (
    ware_id TEXT PRIMARY KEY,
    name TEXT,
    equipment_type TEXT NOT NULL,
    missile_launcher BOOLEAN NOT NULL DEFAULT 0,
    price_min INTEGER,
    price_avg INTEGER,
    price_max INTEGER
);

-- A macro carrying its own alias="..." attribute that this pipeline
-- determined is a true redundant duplicate (same size+compatibility as
-- its own target -- see parse_equipment_component_wares' own docstring),
-- and so was excluded from turrets_base/engines_base/shields_base/
-- weapons_base entirely. Both alias_ware_id and target_ware_id are still
-- real, independently-priced rows in equipment_wares_base -- only the
-- type-specific stats table excludes the alias side. Existing purely so
-- a ware_id sourced from *outside* this app's own picker (a real
-- player-saved ship loadout, see import_loadouts.py) can be resolved
-- back to the still-listed target the game itself treats as equivalent,
-- since the game never actually removed the alias ware -- only this
-- app's own picker does, to avoid showing two indistinguishable options.
CREATE TABLE equipment_ware_aliases (
    alias_ware_id TEXT PRIMARY KEY,
    target_ware_id TEXT NOT NULL,
    equipment_type TEXT NOT NULL,
    FOREIGN KEY (alias_ware_id) REFERENCES equipment_wares_base (ware_id),
    FOREIGN KEY (target_ware_id) REFERENCES equipment_wares_base (ware_id)
);

CREATE TABLE turrets_base (
    ware_id TEXT PRIMARY KEY,
    macro TEXT,
    owners TEXT,
    mk INTEGER,
    bullet_class TEXT,
    rotation_speed REAL,
    rotation_acceleration REAL,
    hull INTEGER,
    size TEXT,
    compatibility TEXT,
    -- Missile-capable turrets only (null for every other turret): the
    -- comma-joined set of missile compatibility tags this launcher accepts
    -- (e.g. "dumbfire,mediumdumbfire"), matched against a missile's own
    -- single missiles_base.compatibility token by membership, and how many
    -- missiles it can hold. See the "Missiles and deployables" section of
    -- this module's docstring.
    ammunition_tags TEXT,
    ammunition_capacity INTEGER,
    FOREIGN KEY (ware_id) REFERENCES equipment_wares_base (ware_id)
);

CREATE TABLE engines_base (
    ware_id TEXT PRIMARY KEY,
    macro TEXT,
    owners TEXT,
    mk INTEGER,
    boost_duration REAL,
    boost_recharge REAL,
    boost_thrust REAL,
    boost_acceleration REAL,
    boost_attack REAL,
    boost_release REAL,
    boost_coast REAL,
    travel_charge REAL,
    travel_thrust REAL,
    travel_attack REAL,
    travel_release REAL,
    thrust_forward REAL,
    thrust_reverse REAL,
    hull INTEGER,
    size TEXT,
    compatibility TEXT,
    FOREIGN KEY (ware_id) REFERENCES equipment_wares_base (ware_id)
);

CREATE TABLE shields_base (
    ware_id TEXT PRIMARY KEY,
    macro TEXT,
    owners TEXT,
    mk INTEGER,
    recharge_max REAL,
    recharge_rate REAL,
    recharge_delay REAL,
    recharge_disruptionstability REAL,
    hull INTEGER,
    size TEXT,
    compatibility TEXT,
    FOREIGN KEY (ware_id) REFERENCES equipment_wares_base (ware_id)
);

CREATE TABLE weapons_base (
    ware_id TEXT PRIMARY KEY,
    macro TEXT,
    owners TEXT,
    mk INTEGER,
    bullet_class TEXT,
    heat_overheat REAL,
    heat_cooldelay REAL,
    heat_coolrate REAL,
    heat_reenable REAL,
    heat_overheatcooldelay REAL,
    rotation_speed REAL,
    rotation_acceleration REAL,
    weapon_angle REAL,
    hull INTEGER,
    size TEXT,
    compatibility TEXT,
    -- Missile-launcher weapons only (null for every other weapon) -- see
    -- turrets_base's matching columns / this module's "Missiles and
    -- deployables" docstring section.
    ammunition_tags TEXT,
    ammunition_capacity INTEGER,
    FOREIGN KEY (ware_id) REFERENCES equipment_wares_base (ware_id)
);

-- Unlike turrets/engines/shields/weapons, thrusters have no macro/component
-- file to source mk/size/compatibility from -- all three are recovered from
-- the ware_id itself (see parse_thruster_wares). No owners/hull columns
-- either: no faction lock, no <properties><hull> block to read. thruster_class
-- ("allround"/"combat") is a playstyle choice, not a tier -- both are equally
-- mountable on a given size, unlike compatibility on other equipment types.
CREATE TABLE thrusters_base (
    ware_id TEXT PRIMARY KEY,
    macro TEXT,
    mk INTEGER,
    thruster_class TEXT,
    size TEXT,
    compatibility TEXT,
    FOREIGN KEY (ware_id) REFERENCES equipment_wares_base (ware_id)
);

-- Software has no equipment_wares_base parent row (it doesn't fit that
-- table's engine/shield/weapon/turret/thruster vocabulary) and no macro/
-- component file either -- category/mk come from the ware_id itself (see
-- parse_software_wares), name/price straight off the wares.xml entry.
-- There's no size or compatibility-class concept for software at all: a
-- software ware is only ever compatible with a ship because that ship's
-- own macro explicitly lists it (see ship_component_groups /
-- SOFTWARE_SIZE / the "Software" section of this module's docstring).
-- Rows are filtered down to only wares actually reachable that way, the
-- same "parse broad, filter to real" shape as filter_to_real_equipment_wares.
CREATE TABLE software_base (
    ware_id TEXT PRIMARY KEY,
    name TEXT,
    category TEXT NOT NULL,
    mk INTEGER,
    price_min INTEGER,
    price_avg INTEGER,
    price_max INTEGER
);

-- Unlike turrets/engines/shields/weapons, missiles have no equipment_wares_base
-- parent row (they aren't tagged "engine"/"shield"/"weapon"/"turret") --
-- name/price/macro live directly on this table. `compatibility` (e.g.
-- "mediumdumbfire") is the missile's own launcher-compatibility tag,
-- matched against a launcher's turrets_base/weapons_base.ammunition_tags
-- by membership -- see this module's "Missiles and deployables" docstring
-- section. Not yet used for any matching/query logic.
CREATE TABLE missiles_base (
    ware_id TEXT PRIMARY KEY,
    name TEXT,
    macro TEXT,
    price_min INTEGER,
    price_avg INTEGER,
    price_max INTEGER,
    ammunition_value INTEGER,
    ammunition_reload REAL,
    missile_amount INTEGER,
    missile_barrelamount INTEGER,
    missile_lifetime REAL,
    missile_range REAL,
    missile_guided BOOLEAN,
    explosiondamage_value REAL,
    explosiondamage_shielddisruption REAL,
    reload_time REAL,
    hull INTEGER,
    weapon_system TEXT,
    countermeasure_resilience REAL,
    physics_mass REAL,
    lock_time REAL,
    lock_range REAL,
    compatibility TEXT
);

-- Satellites/resource probes/mines/lasertowers/navbeacon: standalone
-- deployables (launched from cargo, not ship-mounted), also with no
-- equipment_wares_base parent row. deployable_type distinguishes the five;
-- most stat columns only apply to one type (e.g. radar_range is
-- satellite-only) and are null otherwise.
CREATE TABLE deployables_base (
    ware_id TEXT PRIMARY KEY,
    name TEXT,
    deployable_type TEXT NOT NULL,
    macro TEXT,
    price_min INTEGER,
    price_avg INTEGER,
    price_max INTEGER,
    hull INTEGER,
    radar_range REAL,
    explosion_strength REAL,
    explosion_damage REAL,
    trigger_oncollision BOOLEAN,
    physics_mass REAL
);

-- Fighting/mining/building/cargo/repair/police drones: structurally a
-- scaled-down ship (own macro class, hull, physics) but tagged "drone"
-- rather than "ship" in wares.xml, and equipped via one fixed <loadouts>
-- block rather than swappable hardpoints -- doesn't fit ships_base or
-- ship_component_groups, so it's self-contained like missiles_base/
-- deployables_base instead. Only 3 of the 11 rows have a macro file
-- present in the extracted data at all; `ship_type`/`purpose`/`hull`/
-- `physics_mass` are null for the other 8 (not a gap -- see this module's
-- "Drones" docstring section).
CREATE TABLE drones_base (
    ware_id TEXT PRIMARY KEY,
    name TEXT,
    macro TEXT,
    price_min INTEGER,
    price_avg INTEGER,
    price_max INTEGER,
    ship_type TEXT,
    purpose TEXT,
    hull INTEGER,
    physics_mass REAL
);

-- Countermeasures ("Flares" is the only one in the base game) and the
-- single "crew" ware -- both self-contained like missiles_base/
-- drones_base, with no equipment_wares_base parent row. There's no
-- per-ship flare capacity column anywhere (not even here) -- see the
-- "Countermeasures and crew" section of this module's docstring for why;
-- the frontend assumes a fixed default by ship size instead. crew_base's
-- capacity is ships_base.crew (unaffected, already existed).
CREATE TABLE countermeasures_base (
    ware_id TEXT PRIMARY KEY,
    name TEXT,
    price_min INTEGER,
    price_avg INTEGER,
    price_max INTEGER
);

CREATE TABLE crew_base (
    ware_id TEXT PRIMARY KEY,
    name TEXT,
    price_min INTEGER,
    price_avg INTEGER,
    price_max INTEGER
);

-- production_ware_id references ships_base.ware_id, economy_wares_base.ware_id,
-- equipment_wares_base.ware_id, missiles_base.ware_id,
-- deployables_base.ware_id, or countermeasures_base.ware_id (a ship, an
-- economy ware, a piece of equipment, a missile, a deployable, or a
-- countermeasure can all need production inputs) -- SQLite has no
-- either-or foreign key, so it isn't enforced by a FK here. "ware" is always
-- a raw material, so that side is a real FK to economy_wares_base. A ware
-- can have more than one production method (see build_economy_production_rows/
-- build_equipment_production_rows/build_missile_production_rows/
-- build_deployable_production_rows/build_countermeasure_production_rows), so
-- the key includes method. crew_base is never a production_ware_id (the
-- "crew" ware is bought outright, not manufactured -- see "Countermeasures
-- and crew" above).
-- "amount" is how much of "ware" is consumed per cycle; "produced_amount" is
-- the <production amount="..."/> attribute from that same production block
-- (how many units of production_ware_id come out per cycle) -- it's the
-- same value on every input row for a given (production_ware_id,
-- production_method) pair, denormalized onto each row rather than requiring
-- a join back to the parent tables to look it up.
CREATE TABLE production_wares (
    production_ware_id TEXT NOT NULL,
    production_method TEXT,
    ware TEXT NOT NULL,
    amount INTEGER,
    produced_amount INTEGER,
    PRIMARY KEY (production_ware_id, production_method, ware),
    FOREIGN KEY (ware) REFERENCES economy_wares_base (ware_id)
);

-- group_name is NOT unique per ship on its own -- a dedicated medium shield
-- shares its raw XML "group" attribute value with the engine/turret/weapon
-- group it protects (see parse_component_slots' docstring), so the primary
-- key is (ship_id, group_name, component_type). A caller wanting "this
-- group's dedicated shields" joins on (ship_id, group_name) and filters for
-- component_type = 'shield'.
CREATE TABLE ship_component_groups (
    ship_id TEXT NOT NULL,
    group_name TEXT NOT NULL,
    component_type TEXT NOT NULL,
    size TEXT NOT NULL,
    slot_count INTEGER NOT NULL,
    equipment_compatibility_class TEXT,
    -- Comma-separated real <connection name="..."/> values from the ship's
    -- own component XML (e.g. "con_weapon_01,con_weapon_03") -- every
    -- connection sharing a (group_name, component_type) key is
    -- interchangeable for compatibility/cost purposes (that's why they're
    -- aggregated into one row to begin with), so which name lines up with
    -- which equipment choice doesn't matter; kept only so a loadout can be
    -- exported addressing real connections instead of a synthesized
    -- placeholder path (see import_loadouts.py's build_loadout_xml()).
    -- Empty for the two group_names this app synthesizes itself with no
    -- backing <connection> element at all (component_type 'thruster'/
    -- 'software' -- see generate_ships_table.py's "Thrusters"/"Software"
    -- docstring sections).
    connection_names TEXT,
    PRIMARY KEY (ship_id, group_name, component_type),
    FOREIGN KEY (ship_id) REFERENCES ships_base (ware_id)
);

CREATE TABLE flight_model (
    ware_id TEXT PRIMARY KEY,
{flight_model_col_defs}    steeringcurve TEXT,
    FOREIGN KEY (ware_id) REFERENCES ships_base (ware_id)
);
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(sql, encoding="utf-8")


def write_ships_csv(
    ships: list[dict], turret_sizes: list[str], bonus_weapon_sizes: list[str], out_path: Path
) -> None:
    fieldnames = (
        [
            "name",
            "ware_id",
            "owners",
            "price_min",
            "price_avg",
            "price_max",
            "production_time",
            "production_method",
            "macro",
            "ship_type",
            "purpose",
            "icon",
            "hull",
            "crew",
            "traveldrivestability",
            "missile_capacity",
            "drone_capacity",
            "size",
            "shields",
            "engines",
            "weapons",
        ]
        + [f"bonus_{size}_weapons" for size in bonus_weapon_sizes]
        + ["missile_launchers"]
        + [f"turret_{size}" for size in turret_sizes]
        + ["shields_bonus_m"]
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for s in ships:
            primary_prod = s["productions"][0] if s["productions"] else None
            row = {
                "name": s["name"],
                "ware_id": s["ware_id"],
                "owners": ",".join(s["owners"]),
                "price_min": s["price_min"] or "",
                "price_avg": s["price_avg"] or "",
                "price_max": s["price_max"] or "",
                "production_time": primary_prod["time"] if primary_prod else "",
                "production_method": primary_prod["method_name"] if primary_prod else "",
                "macro": s["macro"] or "",
                "ship_type": s["ship_type"] or "",
                "purpose": s["purpose"] or "",
                "icon": s["icon"] or "",
                "hull": s["hull"] if s["hull"] is not None else "",
                "crew": s["crew"] if s["crew"] is not None else "",
                "traveldrivestability": s["traveldrivestability"],
                "missile_capacity": s["missile_capacity"],
                "drone_capacity": s["drone_capacity"],
                "size": s["size"] or "",
                "shields": s["slots"]["shields"],
                "engines": s["slots"]["engines"],
                "weapons": s["slots"]["weapons"],
                "missile_launchers": s["slots"]["missile_launchers"],
                "shields_bonus_m": s["slots"]["shields_bonus_m"],
            }
            for size in bonus_weapon_sizes:
                row[f"bonus_{size}_weapons"] = s["slots"]["weapons_bonus"].get(size, "")
            for size in turret_sizes:
                row[f"turret_{size}"] = s["slots"]["turrets"].get(size, "")
            writer.writerow(row)


def build_ship_production_rows(ships: list[dict]) -> list[dict]:
    """One row per ware in a ship's *first* production block -- ships only
    ever have one in practice (see the multi-production warning in main()).
    """
    rows = []
    for s in ships:
        primary_prod = s["productions"][0] if s["productions"] else None
        if not primary_prod:
            continue
        for ware, amount in sorted(primary_prod["wares"].items()):
            rows.append(
                {
                    "production_ware_id": s["ware_id"],
                    "production_method": primary_prod["method_name"],
                    "ware": ware,
                    "amount": amount,
                    "produced_amount": primary_prod["produced_amount"],
                }
            )
    return rows


def build_economy_production_rows(economy_wares: list[dict]) -> list[dict]:
    """One row per (production method, ware) across *all* of an economy
    ware's production blocks -- unlike ships, these commonly have more than
    one recipe (e.g. a race-specific alternate), and every recipe's inputs
    are recorded, not just the first.
    """
    rows = []
    for w in economy_wares:
        for prod in w["productions"]:
            for ware, amount in sorted(prod["wares"].items()):
                rows.append(
                    {
                        "production_ware_id": w["ware_id"],
                        "production_method": prod["method_name"],
                        "ware": ware,
                        "amount": amount,
                        "produced_amount": prod["produced_amount"],
                    }
                )
    return rows


def build_equipment_production_rows(equipment_wares: list[dict]) -> list[dict]:
    """Same as build_economy_production_rows, for equipment wares."""
    rows = []
    for w in equipment_wares:
        for prod in w["productions"]:
            for ware, amount in sorted(prod["wares"].items()):
                rows.append(
                    {
                        "production_ware_id": w["ware_id"],
                        "production_method": prod["method_name"],
                        "ware": ware,
                        "amount": amount,
                        "produced_amount": prod["produced_amount"],
                    }
                )
    return rows


def build_missile_production_rows(missile_wares: list[dict]) -> list[dict]:
    """Same as build_economy_production_rows, for missile wares."""
    rows = []
    for w in missile_wares:
        for prod in w["productions"]:
            for ware, amount in sorted(prod["wares"].items()):
                rows.append(
                    {
                        "production_ware_id": w["ware_id"],
                        "production_method": prod["method_name"],
                        "ware": ware,
                        "amount": amount,
                        "produced_amount": prod["produced_amount"],
                    }
                )
    return rows


def build_deployable_production_rows(deployable_wares: list[dict]) -> list[dict]:
    """Same as build_economy_production_rows, for deployable wares."""
    rows = []
    for w in deployable_wares:
        for prod in w["productions"]:
            for ware, amount in sorted(prod["wares"].items()):
                rows.append(
                    {
                        "production_ware_id": w["ware_id"],
                        "production_method": prod["method_name"],
                        "ware": ware,
                        "amount": amount,
                        "produced_amount": prod["produced_amount"],
                    }
                )
    return rows


def build_drone_production_rows(drone_wares: list[dict]) -> list[dict]:
    """Same as build_economy_production_rows, for drone wares."""
    rows = []
    for w in drone_wares:
        for prod in w["productions"]:
            for ware, amount in sorted(prod["wares"].items()):
                rows.append(
                    {
                        "production_ware_id": w["ware_id"],
                        "production_method": prod["method_name"],
                        "ware": ware,
                        "amount": amount,
                        "produced_amount": prod["produced_amount"],
                    }
                )
    return rows


def build_countermeasure_production_rows(countermeasure_wares: list[dict]) -> list[dict]:
    """Same as build_economy_production_rows, for countermeasure wares."""
    rows = []
    for w in countermeasure_wares:
        for prod in w["productions"]:
            for ware, amount in sorted(prod["wares"].items()):
                rows.append(
                    {
                        "production_ware_id": w["ware_id"],
                        "production_method": prod["method_name"],
                        "ware": ware,
                        "amount": amount,
                        "produced_amount": prod["produced_amount"],
                    }
                )
    return rows


def write_production_wares_csv(rows: list[dict], out_path: Path) -> int:
    fieldnames = ["production_ware_id", "production_method", "ware", "amount", "produced_amount"]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def write_component_groups_csv(ships: list[dict], out_path: Path) -> int:
    fieldnames = [
        "ship_id",
        "group_name",
        "component_type",
        "size",
        "slot_count",
        "equipment_compatibility_class",
        "connection_names",
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    row_count = 0
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for s in ships:
            for group in s["component_groups"]:
                writer.writerow({"ship_id": s["ware_id"], **group})
                row_count += 1
    return row_count


def write_flight_model_csv(
    ships: list[dict], jerk_columns: list[str], physics_columns: list[str], out_path: Path
) -> int:
    fieldnames = ["ware_id"] + jerk_columns + physics_columns + ["steeringcurve"]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    row_count = 0
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for s in ships:
            row = {"ware_id": s["ware_id"]}
            for col in jerk_columns:
                row[col] = s["jerk_fields"].get(col, "")
            for col in physics_columns:
                row[col] = s["physics_fields"].get(col, "")
            row["steeringcurve"] = s["steeringcurve"]
            writer.writerow(row)
            row_count += 1
    return row_count


def write_economy_wares_csv(economy_wares: list[dict], out_path: Path) -> int:
    fieldnames = ["ware_id", "name", "price_min", "price_avg", "price_max", "leaf_ware"]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for w in economy_wares:
            writer.writerow(
                {
                    "ware_id": w["ware_id"],
                    "name": w["name"],
                    "price_min": w["price_min"] or "",
                    "price_avg": w["price_avg"] or "",
                    "price_max": w["price_max"] or "",
                    "leaf_ware": int(w["leaf_ware"]),
                }
            )
    return len(economy_wares)


def write_equipment_wares_csv(equipment_wares: list[dict], out_path: Path) -> int:
    fieldnames = ["ware_id", "name", "equipment_type", "missile_launcher", "price_min", "price_avg", "price_max"]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for w in equipment_wares:
            writer.writerow(
                {
                    "ware_id": w["ware_id"],
                    "name": w["name"],
                    "equipment_type": w["equipment_type"],
                    "missile_launcher": int(w["missile_launcher"]),
                    "price_min": w["price_min"] or "",
                    "price_avg": w["price_avg"] or "",
                    "price_max": w["price_max"] or "",
                }
            )
    return len(equipment_wares)


def write_equipment_component_csv(rows: list[dict], fieldnames: list[str], out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: (row[name] if row[name] is not None else "") for name in fieldnames})
    return len(rows)


TURRET_FIELDNAMES = [
    "ware_id", "macro", "owners", "mk", "bullet_class",
    "rotation_speed", "rotation_acceleration", "hull", "size", "compatibility",
    "ammunition_tags", "ammunition_capacity",
]
ENGINE_FIELDNAMES = [
    "ware_id", "macro", "owners", "mk",
    "boost_duration", "boost_recharge", "boost_thrust", "boost_acceleration",
    "boost_attack", "boost_release", "boost_coast",
    "travel_charge", "travel_thrust", "travel_attack", "travel_release",
    "thrust_forward", "thrust_reverse",
    "hull", "size", "compatibility",
]
SHIELD_FIELDNAMES = [
    "ware_id", "macro", "owners", "mk",
    "recharge_max", "recharge_rate", "recharge_delay", "recharge_disruptionstability",
    "hull", "size", "compatibility",
]
WEAPON_FIELDNAMES = [
    "ware_id", "macro", "owners", "mk", "bullet_class",
    "heat_overheat", "heat_cooldelay", "heat_coolrate", "heat_reenable", "heat_overheatcooldelay",
    "rotation_speed", "rotation_acceleration", "weapon_angle",
    "hull", "size", "compatibility",
    "ammunition_tags", "ammunition_capacity",
]
THRUSTER_FIELDNAMES = ["ware_id", "macro", "mk", "thruster_class", "size", "compatibility"]
SOFTWARE_FIELDNAMES = ["ware_id", "name", "category", "mk", "price_min", "price_avg", "price_max"]
MISSILE_FIELDNAMES = [
    "ware_id", "name", "macro", "price_min", "price_avg", "price_max",
    "ammunition_value", "ammunition_reload",
    "missile_amount", "missile_barrelamount", "missile_lifetime", "missile_range", "missile_guided",
    "explosiondamage_value", "explosiondamage_shielddisruption",
    "reload_time", "hull", "weapon_system", "countermeasure_resilience", "physics_mass",
    "lock_time", "lock_range", "compatibility",
]
DEPLOYABLE_FIELDNAMES = [
    "ware_id", "name", "deployable_type", "macro", "price_min", "price_avg", "price_max",
    "hull", "radar_range", "explosion_strength", "explosion_damage", "trigger_oncollision", "physics_mass",
]
DRONE_FIELDNAMES = [
    "ware_id", "name", "macro", "price_min", "price_avg", "price_max",
    "ship_type", "purpose", "hull", "physics_mass",
]
COUNTERMEASURE_FIELDNAMES = ["ware_id", "name", "price_min", "price_avg", "price_max"]
CREW_FIELDNAMES = ["ware_id", "name", "price_min", "price_avg", "price_max"]
EQUIPMENT_WARE_ALIASES_FIELDNAMES = ["alias_ware_id", "target_ware_id", "equipment_type"]


def load_database(db_path: Path, schema_path: Path, table_csv_files: dict[str, Path]) -> None:
    """(Re)build the SQLite database from the generated schema + CSVs.

    Only ever touches the tables this pipeline owns -- the schema's own
    DROP TABLE IF EXISTS statements handle clearing old rows, so anything
    else already in a database file at db_path (if it's an existing file
    with unrelated tables) is left alone. Empty CSV fields are inserted as
    real NULL, not the empty string, and SQLite's column type affinity
    handles converting numeric-looking text into INTEGER/REAL on insert.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(schema_path.read_text(encoding="utf-8"))
        for table, csv_path in table_csv_files.items():
            with csv_path.open(newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                columns = next(reader)
                rows = [[value if value != "" else None for value in row] for row in reader]
            col_list = ", ".join(f'"{c}"' for c in columns)
            placeholders = ", ".join("?" for _ in columns)
            conn.executemany(f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders})', rows)
        conn.commit()
    finally:
        conn.close()


def filter_to_real_equipment_wares(
    equip_type: str, equipment_wares: list[dict], rows: list[dict], known_aliases: set[str] = frozenset()
) -> list[dict]:
    """data/<type>s/ contains some macros with no corresponding wares.xml
    ware -- legacy "_01_mk1"-style macros kept only as an
    alias="..._02_mk1_macro" backward-compat redirect for old savegames,
    _scenario/_story mission-only variants, or plain unused dev leftovers.
    None of those are purchasable/mountable by the player, so each
    <type>s_base table is restricted to wares that actually exist in
    equipment_wares_base.

    `known_aliases` (parse_equipment_component_wares's own second return
    value -- see its docstring) covers the *other* alias shape: a macro
    whose alias="..." attribute marks it as a duplicate of another ware,
    but which -- unlike the orphans this function's own `missing` check is
    meant to catch -- still has a real, independently-priced wares.xml
    entry of its own. Without this, every one of those would show up as a
    false-positive "wares.xml entry with no parsed row" WARNING below, even
    though the missing row is entirely intentional (see
    parse_equipment_component_wares).
    """
    real_ids = {w["ware_id"] for w in equipment_wares if w["equipment_type"] == equip_type}
    parsed_ids = {r["ware_id"] for r in rows}
    non_ware = parsed_ids - real_ids
    if non_ware:
        print(
            f"  ({len(non_ware)} parsed {equip_type} macro(s) filtered out as non-ware "
            f"aliases/mission variants: {sorted(non_ware)})"
        )
    filtered = [r for r in rows if r["ware_id"] in real_ids]
    missing = real_ids - {r["ware_id"] for r in filtered} - known_aliases
    if missing:
        print(
            f"WARNING: {len(missing)} {equip_type} ware(s) in wares.xml with no parsed "
            f"{equip_type}s_base row: {sorted(missing)}"
        )
    return filtered


def main() -> None:
    lang_table = load_language_table(LANG_FILE)
    ships = parse_ship_wares(wares_files())
    economy_wares = parse_economy_wares(wares_files())
    equipment_wares = parse_equipment_wares(wares_files())
    turrets, turret_aliases = parse_turrets(TURRET_MACRO_DIRS, TURRET_COMPONENT_DIRS)
    engines, engine_aliases = parse_engines(ENGINE_MACRO_DIRS, ENGINE_COMPONENT_DIRS)
    shields, shield_aliases = parse_shields(SHIELD_MACRO_DIRS, SHIELD_COMPONENT_DIRS)
    weapons, weapon_aliases = parse_weapons(WEAPON_MACRO_DIRS, WEAPON_COMPONENT_DIRS)
    thrusters = parse_thruster_wares(wares_files())
    software_wares = parse_software_wares(wares_files())
    missile_wares = parse_missile_wares(wares_files())
    deployable_wares = parse_deployable_wares(wares_files())
    drone_wares = parse_drone_wares(wares_files())
    countermeasure_wares = parse_countermeasure_wares(wares_files())
    crew_wares = parse_crew_ware(wares_files())

    for s in ships:
        s["name"] = resolve_ref_attr(s["name_ref"], lang_table)
        for prod in s["productions"]:
            prod["method_name"] = resolve_ref_attr(prod["method_name_ref"], lang_table)

    for w in economy_wares:
        w["name"] = resolve_ref_attr(w["name_ref"], lang_table)
        for prod in w["productions"]:
            prod["method_name"] = resolve_ref_attr(prod["method_name_ref"], lang_table)
        w["leaf_ware"] = not any(prod["wares"] for prod in w["productions"])

    for w in equipment_wares:
        w["name"] = resolve_ref_attr(w["name_ref"], lang_table)
        for prod in w["productions"]:
            prod["method_name"] = resolve_ref_attr(prod["method_name_ref"], lang_table)

    for w in software_wares:
        w["name"] = resolve_ref_attr(w["name_ref"], lang_table)

    for w in missile_wares:
        w["name"] = resolve_ref_attr(w["name_ref"], lang_table)
        for prod in w["productions"]:
            prod["method_name"] = resolve_ref_attr(prod["method_name_ref"], lang_table)
        macro_path = MISSILES_MACRO_DIR / f"{w['macro']}.xml" if w["macro"] else None
        if macro_path is not None and macro_path.exists():
            w.update(analyze_missile_macro(macro_path))
        else:
            print(f"WARNING: missile macro file not found for {w['ware_id']} ({macro_path})")
            w.update({key: None for key in MISSILE_STAT_KEYS})

    for w in deployable_wares:
        w["name"] = resolve_ref_attr(w["name_ref"], lang_table)
        for prod in w["productions"]:
            prod["method_name"] = resolve_ref_attr(prod["method_name_ref"], lang_table)
        macro_dir = DEPLOYABLE_MACRO_DIRS.get(w["deployable_type"])
        macro_path = macro_dir / f"{w['macro']}.xml" if macro_dir and w["macro"] else None
        if macro_path is not None and macro_path.exists():
            w.update(analyze_deployable_macro(macro_path))
        else:
            print(f"WARNING: deployable macro file not found for {w['ware_id']} ({macro_path})")
            w.update({key: None for key in DEPLOYABLE_STAT_KEYS})

    for w in drone_wares:
        w["name"] = resolve_ref_attr(w["name_ref"], lang_table)
        for prod in w["productions"]:
            prod["method_name"] = resolve_ref_attr(prod["method_name_ref"], lang_table)
        # Drone macros only ever live under size_s_macros in this dataset
        # (see the "Drones" docstring section) -- 8 of the 11 wares simply
        # have no macro file there (or anywhere) at all, which is expected,
        # not a gap.
        macro_path = SIZE_MACRO_DIRS["s"] / f"{w['macro']}.xml" if w["macro"] else None
        if macro_path is not None and macro_path.exists():
            w.update(analyze_drone_macro(macro_path))
        else:
            w.update({key: None for key in DRONE_STAT_KEYS})

    for w in countermeasure_wares:
        w["name"] = resolve_ref_attr(w["name_ref"], lang_table)
        for prod in w["productions"]:
            prod["method_name"] = resolve_ref_attr(prod["method_name_ref"], lang_table)

    for w in crew_wares:
        # The "crew" ware's own name="{20208,10401}" reference resolves (via
        # the language table's "NPC Types" page) to "Crewman(male)" -- that
        # page is a table of gendered per-NPC display strings (male/female/
        # plural variants for crew/traders/marines/etc.), and Egosoft's own
        # wares.xml just happens to point this ware's name at the "male"
        # entity-type variant rather than a proper generic ware name (there
        # isn't one in the data -- the nearby {20208,20103} "Service
        # crew(plural)" is a *role* label, not this ware's name). Not a
        # parsing bug -- resolve_ref_attr(w["name_ref"], lang_table) really
        # does produce "Crewman(male)" here -- just overridden with a
        # cleaner display name post-resolution.
        w["name"] = "Crew"

    if not crew_wares:
        print("WARNING: no ware with id 'crew' found in wares*.xml -- crew_base will be empty")

    multi_production = [s["ware_id"] for s in ships if len(s["productions"]) > 1]
    if multi_production:
        print(f"WARNING: {len(multi_production)} ship(s) with multiple production blocks (using the first): {multi_production}")

    seen: dict[str, list[str]] = {}
    for s in ships:
        seen.setdefault(s["name"], []).append(s["ware_id"])
    dupes = {name: ids for name, ids in seen.items() if len(ids) > 1}
    if dupes:
        print(f"WARNING: {len(dupes)} duplicate resolved ship name(s): {dupes}")

    economy_seen: dict[str, list[str]] = {}
    for w in economy_wares:
        economy_seen.setdefault(w["name"], []).append(w["ware_id"])
    economy_dupes = {name: ids for name, ids in economy_seen.items() if len(ids) > 1}
    if economy_dupes:
        print(f"WARNING: {len(economy_dupes)} duplicate resolved economy ware name(s): {economy_dupes}")

    equipment_seen: dict[str, list[str]] = {}
    for w in equipment_wares:
        equipment_seen.setdefault(w["name"], []).append(w["ware_id"])
    equipment_dupes = {name: ids for name, ids in equipment_seen.items() if len(ids) > 1}
    if equipment_dupes:
        print(f"WARNING: {len(equipment_dupes)} duplicate resolved equipment ware name(s): {equipment_dupes}")

    missile_seen: dict[str, list[str]] = {}
    for w in missile_wares:
        missile_seen.setdefault(w["name"], []).append(w["ware_id"])
    missile_dupes = {name: ids for name, ids in missile_seen.items() if len(ids) > 1}
    if missile_dupes:
        print(f"WARNING: {len(missile_dupes)} duplicate resolved missile name(s): {missile_dupes}")

    deployable_seen: dict[str, list[str]] = {}
    for w in deployable_wares:
        deployable_seen.setdefault(w["name"], []).append(w["ware_id"])
    deployable_dupes = {name: ids for name, ids in deployable_seen.items() if len(ids) > 1}
    if deployable_dupes:
        print(f"WARNING: {len(deployable_dupes)} duplicate resolved deployable name(s): {deployable_dupes}")

    turrets = filter_to_real_equipment_wares("turret", equipment_wares, turrets, set(turret_aliases))
    engines = filter_to_real_equipment_wares("engine", equipment_wares, engines, set(engine_aliases))
    shields = filter_to_real_equipment_wares("shield", equipment_wares, shields, set(shield_aliases))
    weapons = filter_to_real_equipment_wares("weapon", equipment_wares, weapons, set(weapon_aliases))

    # Persisted so anything working from a real player-saved ship loadout
    # (loadouts.xml, not this app's own picker) can substitute an excluded
    # alias ware_id back to the real, still-listed target ware it's a
    # duplicate of -- see parse_equipment_component_wares' own docstring
    # and import_loadouts.py's resolve_alias().
    equipment_ware_aliases = (
        [{"alias_ware_id": k, "target_ware_id": v, "equipment_type": "turret"} for k, v in turret_aliases.items()]
        + [{"alias_ware_id": k, "target_ware_id": v, "equipment_type": "engine"} for k, v in engine_aliases.items()]
        + [{"alias_ware_id": k, "target_ware_id": v, "equipment_type": "shield"} for k, v in shield_aliases.items()]
        + [{"alias_ware_id": k, "target_ware_id": v, "equipment_type": "weapon"} for k, v in weapon_aliases.items()]
    )
    thrusters = filter_to_real_equipment_wares("thruster", equipment_wares, thrusters)

    turret_sizes: set[str] = set()
    bonus_weapon_sizes: set[str] = set()
    jerk_columns: set[str] = set()
    physics_columns: set[str] = set()
    software_ware_ids_referenced: set[str] = set()
    for s in ships:
        size = ship_size_code(s["ware_id"])
        s["size"] = size
        analysis = analyze_ship_components(s, size)
        s["component_groups"] = analysis["groups"]
        s["missile_capacity"] = analysis["missile_capacity"]
        s["drone_capacity"] = analysis["drone_capacity"]
        s["ship_type"] = analysis["ship_type"]
        s["purpose"] = analysis["purpose"]
        s["icon"] = analysis["icon"]
        s["hull"] = analysis["hull"]
        s["crew"] = analysis["crew"]
        s["traveldrivestability"] = analysis["traveldrivestability"]
        s["jerk_fields"] = analysis["jerk_fields"]
        s["physics_fields"] = analysis["physics_fields"]
        s["steeringcurve"] = analysis["steeringcurve"]
        s["slots"] = summarize_slots(s["ware_id"], size, analysis["slot_counts"])
        turret_sizes.update(s["slots"]["turrets"].keys())
        bonus_weapon_sizes.update(s["slots"]["weapons_bonus"].keys())
        jerk_columns.update(s["jerk_fields"].keys())
        physics_columns.update(s["physics_fields"].keys())
        for group in analysis["groups"]:
            if group["component_type"] == "software" and group["equipment_compatibility_class"]:
                software_ware_ids_referenced.update(group["equipment_compatibility_class"].split(","))
    turret_sizes_sorted = sorted(turret_sizes)
    bonus_weapon_sizes_sorted = sorted(bonus_weapon_sizes)
    jerk_columns_sorted = sorted(jerk_columns)
    physics_columns_sorted = sorted(physics_columns)

    # Docking computer is a confirmed exception to "a ship's own <software>
    # block is authoritative" (see the "Software" section of this module's
    # docstring): "software_dockmk1" is never listed by any ship's macro at
    # all, yet is equippable in-game wherever mk2 is -- apparently docking
    # computers aren't actually gated per-ship the way scanners are, just
    # not modeled that way in this XML data. So every ship's "software_dock"
    # group (if it has one at all) is expanded here to every known dock
    # ware, not just whatever its own macro happened to list.
    dock_ware_ids = sorted(w["ware_id"] for w in software_wares if w["category"] == "dock")
    for s in ships:
        for group in s["component_groups"]:
            if group["component_type"] == "software" and group["group_name"] == "software_dock":
                group["equipment_compatibility_class"] = ",".join(dock_ware_ids)
    software_ware_ids_referenced.update(dock_ware_ids)

    # Unlike filter_to_real_equipment_wares (which filters against
    # equipment_wares_base), software_base is filtered against which
    # ware_ids some ship's own macro actually lists as compatible -- there's
    # no other authoritative source for "is this software real" (see
    # parse_software_wares' docstring).
    software_candidate_ids = {w["ware_id"] for w in software_wares}
    unused_software = software_candidate_ids - software_ware_ids_referenced
    if unused_software:
        print(
            f"  ({len(unused_software)} parsed software ware(s) filtered out -- never referenced by any "
            f"ship's <software> block: {sorted(unused_software)})"
        )
    software_wares = [w for w in software_wares if w["ware_id"] in software_ware_ids_referenced]
    missing_software = software_ware_ids_referenced - software_candidate_ids
    if missing_software:
        print(
            f"WARNING: {len(missing_software)} software ware id(s) referenced by a ship's <software> block "
            f"with no parsed software_base row: {sorted(missing_software)}"
        )

    write_ships_csv(ships, turret_sizes_sorted, bonus_weapon_sizes_sorted, SHIPS_CSV_OUT)
    production_rows = (
        build_ship_production_rows(ships)
        + build_economy_production_rows(economy_wares)
        + build_equipment_production_rows(equipment_wares)
        + build_missile_production_rows(missile_wares)
        + build_deployable_production_rows(deployable_wares)
        + build_drone_production_rows(drone_wares)
        + build_countermeasure_production_rows(countermeasure_wares)
    )
    ware_row_count = write_production_wares_csv(production_rows, PRODUCTION_WARES_CSV_OUT)
    group_row_count = write_component_groups_csv(ships, COMPONENT_GROUPS_CSV_OUT)
    flight_model_row_count = write_flight_model_csv(ships, jerk_columns_sorted, physics_columns_sorted, FLIGHT_MODEL_CSV_OUT)
    economy_row_count = write_economy_wares_csv(economy_wares, ECONOMY_WARES_CSV_OUT)
    equipment_row_count = write_equipment_wares_csv(equipment_wares, EQUIPMENT_WARES_CSV_OUT)
    equipment_ware_aliases_row_count = write_equipment_component_csv(
        equipment_ware_aliases, EQUIPMENT_WARE_ALIASES_FIELDNAMES, EQUIPMENT_WARE_ALIASES_CSV_OUT
    )
    turret_row_count = write_equipment_component_csv(turrets, TURRET_FIELDNAMES, TURRETS_CSV_OUT)
    engine_row_count = write_equipment_component_csv(engines, ENGINE_FIELDNAMES, ENGINES_CSV_OUT)
    shield_row_count = write_equipment_component_csv(shields, SHIELD_FIELDNAMES, SHIELDS_CSV_OUT)
    weapon_row_count = write_equipment_component_csv(weapons, WEAPON_FIELDNAMES, WEAPONS_CSV_OUT)
    thruster_row_count = write_equipment_component_csv(thrusters, THRUSTER_FIELDNAMES, THRUSTERS_CSV_OUT)
    software_row_count = write_equipment_component_csv(software_wares, SOFTWARE_FIELDNAMES, SOFTWARE_CSV_OUT)
    missile_row_count = write_equipment_component_csv(missile_wares, MISSILE_FIELDNAMES, MISSILES_CSV_OUT)
    deployable_row_count = write_equipment_component_csv(deployable_wares, DEPLOYABLE_FIELDNAMES, DEPLOYABLES_CSV_OUT)
    drone_row_count = write_equipment_component_csv(drone_wares, DRONE_FIELDNAMES, DRONES_CSV_OUT)
    countermeasure_row_count = write_equipment_component_csv(
        countermeasure_wares, COUNTERMEASURE_FIELDNAMES, COUNTERMEASURES_CSV_OUT
    )
    crew_row_count = write_equipment_component_csv(crew_wares, CREW_FIELDNAMES, CREW_CSV_OUT)
    write_sql_schema(turret_sizes_sorted, bonus_weapon_sizes_sorted, jerk_columns_sorted, physics_columns_sorted, SQL_OUT)

    print(
        f"Wrote {len(ships)} ships, {len(turret_sizes_sorted)} turret-size columns, "
        f"{len(bonus_weapon_sizes_sorted)} bonus-weapon-size columns, "
        f"{ware_row_count} production_wares rows, {group_row_count} component_groups rows, "
        f"{flight_model_row_count} flight_model rows, {economy_row_count} economy_wares_base rows, "
        f"{equipment_row_count} equipment_wares_base rows, "
        f"{equipment_ware_aliases_row_count} equipment_ware_aliases rows, "
        f"{turret_row_count} turrets_base rows, "
        f"{engine_row_count} engines_base rows, {shield_row_count} shields_base rows, "
        f"{weapon_row_count} weapons_base rows, {thruster_row_count} thrusters_base rows, "
        f"{software_row_count} software_base rows, "
        f"{missile_row_count} missiles_base rows, "
        f"{deployable_row_count} deployables_base rows, "
        f"{drone_row_count} drones_base rows, "
        f"{countermeasure_row_count} countermeasures_base rows, "
        f"{crew_row_count} crew_base rows"
    )
    print(f"  -> {SQL_OUT.relative_to(ROOT)}")
    print(f"  -> {SHIPS_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {PRODUCTION_WARES_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {COMPONENT_GROUPS_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {FLIGHT_MODEL_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {ECONOMY_WARES_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {EQUIPMENT_WARES_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {EQUIPMENT_WARE_ALIASES_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {TURRETS_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {ENGINES_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {SHIELDS_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {WEAPONS_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {THRUSTERS_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {SOFTWARE_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {MISSILES_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {DEPLOYABLES_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {DRONES_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {COUNTERMEASURES_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {CREW_CSV_OUT.relative_to(ROOT)}")

    load_database(DB_OUT, SQL_OUT, TABLE_CSV_FILES)
    print(f"  -> {DB_OUT.relative_to(ROOT)} (rebuilt)")


if __name__ == "__main__":
    main()
