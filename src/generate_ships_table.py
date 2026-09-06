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
  - data/ships/<class>_macros/*.xml     (each ship's macro: component ref,
                                   ship type/hull/crew/travel drive/missile
                                   capacity, the full flight model --
                                   jerk/physics/steeringcurve -- and its
                                   <software> compatibility list. <class> is
                                   whatever the macro's own <macro
                                   class="..."/> attribute says (e.g.
                                   "ship_l"), sorted there by extract_game_
                                   data.py's sort_ship_files_by_class() --
                                   see index_ship_files()/
                                   SHIP_CLASS_TO_SIZE_CODE below for how
                                   that maps to ships_base.size)
  - data/ships/<class>_components/*.xml (each ship's component/model
                                   definition, analyzed for engine/shield/
                                   weapon/turret connection slots -- same
                                   <class>_ folder convention as macros
                                   above, from each file's own <component
                                   class="..."/>)
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
  - data/version.dat                   (base game build number, a plain
                                   number with no XML around it)
  - data/extensions/<ext>/content.xml  (one per installed extension --
                                   id/name/version/date attributes on the
                                   root <content> element; extract_game_data
                                   .py's copy_metadata_files() is what puts
                                   these two under data/ in the first place,
                                   since neither lives inside a .cat/.dat
                                   catalog like everything else this module
                                   reads)
  - data/libraries/factions.xml        (base game faction definitions --
                                   id/name="{page,id}"/primaryrace/etc on
                                   each <faction> element)
  - data/libraries/factions_<suffix>.xml  (each extension's own <diff>
                                   patch -- new factions plus relation/
                                   licence tweaks to existing ones; see
                                   factions_files()/parse_factions() below.
                                   Only 5 of 7 extensions ship one)
  - data/names/0001-l<id>.xml          (one per LANGUAGE_FILES entry --
                                   id/page-keyed strings for that language,
                                   base-game-only same as 0001-l044.xml
                                   itself; see parse_localized_strings()
                                   below for the non-English ones)
  - data/libraries/purposes.xml        (base game ship/station purpose
                                   category definitions -- id/name=
                                   "{page,id}" on each <purpose> element,
                                   base-game-only same as colors.xml; see
                                   parse_purposes() below)
  - data/libraries/races.xml           (base game race definitions -- id/
                                   name/shortname="{page,id}" on each
                                   <race> element, base-game-only same as
                                   purposes.xml/colors.xml; see
                                   parse_races() below. A race's own id
                                   (e.g. "argon") is the same value every
                                   ship/turret/engine/shield/weapon's own
                                   makerrace attribute uses directly -- see
                                   "Design race and race/faction
                                   shortcodes" below)

Writes:
  - src/sql/ships_tables.sql          (CREATE TABLE schema for all 30 tables)
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
  - src/csv/source_versions.csv       (one row for the base game plus one
                                        per installed extension -- see
                                        parse_source_versions() below; for
                                        the About page's "built from these
                                        versions" section, not used by any
                                        other part of this pipeline)
  - src/csv/factions.csv              (one row per real faction id, its
                                        display name and shortname (e.g.
                                        "YAK" for Yaki) resolved -- see
                                        parse_factions() below; for the
                                        ship picker's owner-faction icon
                                        tooltips, src/static/app.js, and the
                                        Vendor filter)
  - src/csv/races.csv                 (one row per real race id, its
                                        display name and shortname (e.g.
                                        "ARG" for Argon) resolved -- see
                                        parse_races() below; a race's own id
                                        is the same value maker_races.csv's
                                        race_id column and every ship/
                                        equipment ware's own makerrace
                                        attribute use directly)
  - src/csv/maker_races.csv           (one row per (ware_id, race_id) pair
                                        -- a ship/turret/engine/shield/
                                        weapon's own real design race(s),
                                        read directly from its macro's
                                        makerrace attribute; see "Design
                                        race and race/faction shortcodes"
                                        below)
  - src/csv/localized_shortnames.csv  (one row per (ware_id, lang_id) pair
                                        with a real non-English translation
                                        of a race's or faction's own short
                                        callsign (e.g. "ARG"/"YAK") --
                                        same shape as localized_strings.csv,
                                        kept separate since it's a second,
                                        independently-localizable text field
                                        on the same entities; see "Design
                                        race and race/faction shortcodes"
                                        below)
  - src/csv/purposes.csv              (one row per real purpose id, its
                                        display name resolved -- see
                                        parse_purposes() below; for the
                                        ship picker's Purpose filter labels)
  - src/csv/ship_types.csv            (one row per real ship_type value
                                        actually present in ships_base, its
                                        display name resolved where known --
                                        see parse_ship_types()/
                                        SHIP_TYPE_NAME_REF below; for the
                                        ship picker's Type filter labels)
  - src/csv/build_methods.csv         (one row per real production method
                                        name (BUILD_METHODS) -- see
                                        parse_build_methods()/
                                        collect_build_method_refs() below;
                                        for the Build Method filter, the
                                        Cost Analysis Build Method modal,
                                        and the fleet-tab priority button.
                                        build_method_name doubles as the
                                        real internal key used everywhere
                                        else in this app -- see
                                        collect_build_method_refs()'s own
                                        docstring for why that's
                                        deliberately unchanged here)
  - src/csv/crew_roles.csv            (one row per real crew-role code
                                        (CREW_ROLE_NAME_REF) -- see
                                        parse_crew_roles() below; for the
                                        ship builder's Marines/Service Crew
                                        rows)
  - src/csv/localized_strings.csv     (one row per (ware_id, lang_id) pair
                                        with a real non-English translation
                                        available -- see
                                        parse_localized_strings() below;
                                        game-data localization, separate
                                        from the website's own UI text --
                                        see src/static/i18n.js for that)
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
(data/ships/<class>_macros/<macro>.xml, looked up by name via
index_ship_files() -- see that function's own docstring), which itself has
its own <component ref="..."/> pointing to the *component* file
(data/ships/<class>_components/<component>.xml, same name-based lookup)
that actually defines the ship's hardpoints as
<connection tags="..." group="..."/> entries. Most connections
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

Expansion wares
---------------
Each expansion's wares_<suffix>.xml is a <diff> patch, not a standalone
<wares> list: new ship/equipment/economy-ware definitions live inside an
<add sel="/wares"> block, alongside separate <add sel="/wares/ware[@id='...']">
blocks that patch an *existing* ware (extra owner factions, or -- just as
common -- an entirely new <production> method the base game didn't ship,
e.g. the Terran DLC adding a Terran recipe to a thruster that only had a
Universal one). iter_ware_elements() applies both: every file's own
wholesale-new ware entries are collected first, then every patch is merged
onto its target ware's Element (owners/productions/etc. all inherited from
whichever child elements the patch itself adds) before any of the
type-specific parsers below ever see it.

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
Unlike engines/shields/weapons/turrets, thrusters are not a physical
<connection> hardpoint on the ship's own component file -- the game doesn't
give a ship a mountable "thruster" slot the way it does an engine/shield/
weapon/turret bay. Every ship simply gets exactly one thruster slot sized to
match its own hull, so:

  - ship_component_groups gets one synthesized "thruster" group per ship
    (component_type "thruster", slot_count 1, size = the ship's own size
    class), added directly in analyze_ship_components() rather than
    discovered via parse_component_slots -- there's no XML connection to
    find one in.
  - thrusters_base is parsed straight from wares.xml by
    parse_thruster_wares(), not from a macro walk: `size`, `thruster_class`
    ("allround" or "combat" -- a player playstyle choice, not a tier lock),
    and `mk` are all recovered from the ware_id itself (e.g.
    "thruster_gen_m_combat_01_mk2") rather than from the macro's own
    (redundant) <identification mk="..."/> attribute. Thrusters carry no
    faction/tier lock in the game data at all (no <owner> elements, no
    compatibility tag), so `compatibility` is set to the constant
    "universal" on both the ship_component_groups group and every
    thrusters_base row -- this isn't a real game concept, just a shared
    sentinel so the existing (size, compatibility_class) matching in
    query_ship_components.py's matching_items() keeps working unmodified
    for this type too.
  - Real per-mk RCS thrust stats DO exist, despite the above -- a per-ware
    macro file for each (size, thruster_class, mk) combo, living at
    assets/props/Engines/macros/thruster_*_macro.xml (macro class="engine";
    the game internally treats a ship's RCS thrusters as a kind of engine
    component). Confirmed via a probe of every base+DLC catalog after an
    earlier, narrower search (just data/thrusters/, which genuinely doesn't
    exist) wrongly concluded no macro data existed at all. See
    thruster_macro_jobs() in extract_game_data.py and
    parse_thruster_macros() below for where these get pulled in.

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
deployable_jobs() docstring. That job pulls the file into its own
data/deployables/lasertowers/ folder independently of (and in addition
to) the general ship macro extraction, which -- since generalizing to a
class-discovered scan, see extract_game_data.py's ship_macro_jobs() --
now also picks up the same file into ship_xs_macros/, harmlessly unused
there since no real <ware tags="ship"> ever references it.

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

Design race and race/faction shortcodes
-----------------------------------------
A ship/turret/engine/shield/weapon's own design race (e.g. "who built this")
comes from its macro's <properties><identification makerrace="argon" .../>
attribute -- read directly (see load_macro_data()/
parse_equipment_component_wares()), never inferred from the ware_id's own
naming convention. This replaced an earlier ware_id-prefix-parsing approach
(SHIP_RACE_PREFIX_TO_FACTION/ship_owner_faction(), both removed) once it
became clear makerrace is a real, per-entity, per-mod-respected game
attribute -- unlike a ware_id's shape, which no mod is under any obligation
to follow. makerrace can be multi-valued (space-separated, e.g. "argon
teladi" on ship_gen_m_corvette_01, the Envoy) -- see split_maker_races()/
build_maker_race_rows(), which produce one maker_races row per (ware_id,
race_id) pair rather than collapsing to a single value. Missiles,
deployables, thrusters, and software have no makerrace concept in the base
game at all (confirmed by inspection), so they simply get no maker_races
rows.

Separately, a race's or faction's own short in-game callsign (e.g. "ARG" for
Argon, "YAK" for Yaki) comes from races.xml's/factions*.xml's own
shortname="{page,id}" attribute (parse_races()/parse_factions()) -- purely
a display concern now, not a lookup key (a ship's race is found via
maker_races/makerrace directly, never by matching a shortcode string back
against a ware_id prefix).

Both race_name/race_shortname and faction_name/faction_shortname need two
independently-localizable text fields per entity, but localized_strings'
schema only has room for one text column per (ware_id, lang_id) pair --
solved with one extra table per extra field, all built by the same shared
parse_localized_strings(), just given a different `ref_key` and/or a
different, smaller entity_lists each time: factions' own name stays in the
main shared localized_strings table (alongside ships/wares/purposes, whose
ware_id namespace never collides with a faction id in practice);
faction_shortname gets its own localized_shortnames table
(ref_key="shortname_ref", entity_lists=[factions]). races is deliberately
NOT mixed into either of those -- see the next paragraph -- and instead
gets two more dedicated tables of its own, localized_race_names
(entity_lists=[races]) and localized_race_shortnames
(entity_lists=[races], ref_key="shortname_ref").

Why races needed full isolation rather than just joining factions' tables
the same way: several race ids collide with a same-named faction id (e.g.
"argon" is both a race id and a faction id), and parse_localized_strings()'s
own `seen` dedup keeps only the first (ware_id, lang_id) row it finds
across all lists passed to one call -- so mixing races into factions'
shared keyspace was confirmed, via a live GET /api/races?lang=de test, to
silently return the *faction's* German text for a race (e.g. "Argonische
Föderation", the Argon Federation faction's own name, instead of the
race's own "Argonen"). This was caught by testing an actual API response,
not by inspection -- the bug produced no errors or warnings anywhere in
the pipeline, since every step involved was individually working exactly
as designed; the only sign was the wrong text showing up end to end.

Confirmed empirically: race shortcodes are identical in English and German
(all 8 match byte-for-byte), but faction shortcodes are not -- 9 of 25
differ (e.g. "buccaneers" is "BUC" in English, "KDH" in German). One,
"scavenger", carries a pre-existing data-quality quirk in Egosoft's own
German text: its shortname reference resolves to
"STU(Riptide Rakers RIP = Sturmflut-Streicher STU)" -- a *trailing*, not
leading, dev comment, which resolve_text() has no safe way to strip
generically (see LEADING_PAREN_RE's own comment on why a trailing-paren
strip would corrupt real names that use escaped, backslash-prefixed parens,
e.g. "Magnetar (Gas) Vanguard") --
same class of bug as the "Processing" production method noted above, left
unfixed for the same reason, not something introduced by this pipeline.
"""

import csv
import re
import sqlite3
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
LANG_FILE = DATA / "names" / "0001-l044.xml"

# lang_id -> data/names/<file>.xml, one entry per language the database has
# any localized_strings coverage for (see parse_localized_strings() below).
# "en" is deliberately excluded from that table -- see this module's own
# note on LOCALIZED_STRINGS_FIELDNAMES for why -- but is listed here too so
# every other piece of code that needs "every supported language" (not
# just "every language with its own localized_strings rows") has one
# single place to read it from. Must stay in sync with LANGUAGE_IDS in
# extract_game_data.py (that's the other place a new language needs
# adding -- the actual extraction job).
LANGUAGE_FILES = {
    "en": "0001-l044.xml",
    "de": "0001-l049.xml",
    "es": "0001-l034.xml",
    "fr": "0001-l033.xml",
    "it": "0001-l039.xml",
    "pt": "0001-l055.xml",
    "cs": "0001-l042.xml",
    "pl": "0001-l048.xml",
    "ru": "0001-l007.xml",
    "uk": "0001-l380.xml",
    "zh": "0001-l086.xml",
    "ko": "0001-l082.xml",
    "ja": "0001-l081.xml",
    "bg": "0001-l359.xml",
    "tr": "0001-l090.xml",
}
WARES_DIR = DATA / "libraries"
VERSION_DAT_FILE = DATA / "version.dat"
EXTENSIONS_DIR = DATA / "extensions"
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
BULLETS_CSV_OUT = ROOT / "src" / "csv" / "bullets_base.csv"
DEPLOYABLES_CSV_OUT = ROOT / "src" / "csv" / "deployables_base.csv"
DRONES_CSV_OUT = ROOT / "src" / "csv" / "drones_base.csv"
COUNTERMEASURES_CSV_OUT = ROOT / "src" / "csv" / "countermeasures_base.csv"
CREW_CSV_OUT = ROOT / "src" / "csv" / "crew_base.csv"
SOURCE_VERSIONS_CSV_OUT = ROOT / "src" / "csv" / "source_versions.csv"
FACTIONS_CSV_OUT = ROOT / "src" / "csv" / "factions.csv"
RACES_FILE = WARES_DIR / "races.xml"
RACES_CSV_OUT = ROOT / "src" / "csv" / "races.csv"
PURPOSES_FILE = WARES_DIR / "purposes.xml"
PURPOSES_CSV_OUT = ROOT / "src" / "csv" / "purposes.csv"
SHIP_TYPES_CSV_OUT = ROOT / "src" / "csv" / "ship_types.csv"
CARGO_TYPES_CSV_OUT = ROOT / "src" / "csv" / "cargo_types.csv"
MISSILE_WEAPON_SYSTEMS_CSV_OUT = ROOT / "src" / "csv" / "missile_weapon_systems.csv"
COMPATIBILITY_TYPES_CSV_OUT = ROOT / "src" / "csv" / "compatibility_types.csv"
AMMUNITION_COMPATIBILITY_TYPES_CSV_OUT = ROOT / "src" / "csv" / "ammunition_compatibility_types.csv"
THRUSTER_CLASSES_CSV_OUT = ROOT / "src" / "csv" / "thruster_classes.csv"
DEPLOYABLE_TYPES_CSV_OUT = ROOT / "src" / "csv" / "deployable_types.csv"
BUILD_METHODS_CSV_OUT = ROOT / "src" / "csv" / "build_methods.csv"
CREW_ROLES_CSV_OUT = ROOT / "src" / "csv" / "crew_roles.csv"
MAKER_RACES_CSV_OUT = ROOT / "src" / "csv" / "maker_races.csv"
LOCALIZED_STRINGS_CSV_OUT = ROOT / "src" / "csv" / "localized_strings.csv"
LOCALIZED_SHORTNAMES_CSV_OUT = ROOT / "src" / "csv" / "localized_shortnames.csv"
LOCALIZED_RACE_NAMES_CSV_OUT = ROOT / "src" / "csv" / "localized_race_names.csv"
LOCALIZED_RACE_SHORTNAMES_CSV_OUT = ROOT / "src" / "csv" / "localized_race_shortnames.csv"
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
BULLETS_MACRO_DIR = DATA / "bullets" / "macros"
THRUSTERS_MACRO_DIR = DATA / "thrusters" / "macros"
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
    "bullets_base": BULLETS_CSV_OUT,
    "deployables_base": DEPLOYABLES_CSV_OUT,
    "drones_base": DRONES_CSV_OUT,
    "countermeasures_base": COUNTERMEASURES_CSV_OUT,
    "crew_base": CREW_CSV_OUT,
    "production_wares": PRODUCTION_WARES_CSV_OUT,
    "ship_component_groups": COMPONENT_GROUPS_CSV_OUT,
    "flight_model": FLIGHT_MODEL_CSV_OUT,
    "source_versions": SOURCE_VERSIONS_CSV_OUT,
    "factions": FACTIONS_CSV_OUT,
    "races": RACES_CSV_OUT,
    "purposes": PURPOSES_CSV_OUT,
    "ship_types": SHIP_TYPES_CSV_OUT,
    "cargo_types": CARGO_TYPES_CSV_OUT,
    "missile_weapon_systems": MISSILE_WEAPON_SYSTEMS_CSV_OUT,
    "compatibility_types": COMPATIBILITY_TYPES_CSV_OUT,
    "ammunition_compatibility_types": AMMUNITION_COMPATIBILITY_TYPES_CSV_OUT,
    "thruster_classes": THRUSTER_CLASSES_CSV_OUT,
    "deployable_types": DEPLOYABLE_TYPES_CSV_OUT,
    "build_methods": BUILD_METHODS_CSV_OUT,
    "crew_roles": CREW_ROLES_CSV_OUT,
    "maker_races": MAKER_RACES_CSV_OUT,
    "localized_strings": LOCALIZED_STRINGS_CSV_OUT,
    "localized_shortnames": LOCALIZED_SHORTNAMES_CSV_OUT,
    "localized_race_names": LOCALIZED_RACE_NAMES_CSV_OUT,
    "localized_race_shortnames": LOCALIZED_RACE_SHORTNAMES_CSV_OUT,
}

EQUIPMENT_TYPE_TAGS = ("engine", "shield", "weapon", "turret", "thruster")


def classify_equipment_type(tags: set[str]) -> str | None:
    return next((t for t in EQUIPMENT_TYPE_TAGS if t in tags), None)

SHIPS_DIR = DATA / "ships"
DOCK_MACROS_DIR = SHIPS_DIR / "dock_macros"

# Interim, hand-curated mapping from a ship's own real macro/component
# class="..." attribute (see index_ship_files()) to the short size code
# used throughout this app (ships_base.size, the Size filter, the
# turret_<size>/bonus_<size>_weapons dynamic columns, etc.).
#
# Investigated whether a real in-game localization source exists for the
# S/M/L/XL/XS text itself (plain letters don't necessarily make sense
# translated as-is into every language, e.g. Chinese) and confirmed one
# does: the game's own UI code (ui/addons/ego_detailmonitorhelper/
# helper.lua, ~line 9122) hardcodes exactly this class-to-language-ref
# mapping (class == "ship_xl" -> ReadText(1001, 48), etc., page 1001 ids
# 48-52). But also confirmed -- by resolving those refs in English, German,
# AND Chinese (the game does ship a Chinese language file, t/0001-l086.xml)
# -- that Egosoft's own translators keep these as the literal Latin letters
# "XL"/"L"/"M"/"S"/"XS" in every one of those languages, not translated at
# all. So wiring this through to real per-language text would produce
# byte-identical output to this hardcoded dict today; deliberately not done
# for that reason (no real value from the extra machinery right now), but
# the Lua source above is exactly where to start if that ever needs
# revisiting -- see SHIP_TYPE_NAME_REF below for what doing this properly
# looks like once it's actually worth it for a given lookup.
#
# No general mechanism exists in the base game for handling an unrecognized
# size class either, mods included -- confirmed by inspection (no XML
# registry anywhere; class semantics live only in this same hardcoded Lua
# and in the C++ engine itself, which mods can't touch), so a mod
# introducing a genuinely new size class would need Egosoft's own UI code
# patched too, not just game data. This dict's own `.get(...)` returning
# None (see index_ship_files()'s caller) for anything unrecognized is the
# realistic ceiling here, not a gap to eventually close.
#
# REVISIT when real mod support is built (see GitHub issue #5) --
# specifically confirmed relevant to Star Wars Interworlds, which is known
# to add XXL/XXXL-ish ships beyond this dataset's own xs/s/m/l/xl. Whatever
# class string(s) that mod actually uses show up directly in ships_base.
# ship_class once its data is run through this pipeline (added specifically
# so this would be visible rather than silently guessed at) -- start there.
SHIP_CLASS_TO_SIZE_CODE = {
    "ship_xs": "xs",
    "ship_s": "s",
    "ship_m": "m",
    "ship_l": "l",
    "ship_xl": "xl",
}

# Hand-curated mapping from a ship's own real ships_base.ship_type value
# (e.g. "destroyer") to its real in-game display name's language ref (e.g.
# "Destroyer"/German "Zerstörer"). No XML registry exists for this any more
# than SHIP_CLASS_TO_SIZE_CODE's own size classes do -- found the same way,
# by reading the game's own UI Lua source
# (ui/addons/ego_detailmonitor/menu_map.lua's map-legend table, ~line
# 1560-1600), which is keyed by *icon* (ships_base.icon, e.g.
# "ship_xl_destroyer_01"), not ship_type directly -- cross-referenced
# against every real (ship_type, icon) pair actually present in this
# dataset to build this table, since the two aren't quite 1:1 (a handful of
# ships use a generic/placeholder icon that doesn't appear in that Lua
# table at all, but every real ship_type value's *dominant* icon does).
#
# Confirmed -- unlike SHIP_CLASS_TO_SIZE_CODE's size letters -- these
# genuinely differ by language (checked all 18 unique refs against German:
# 17 of 18 produce real, different text, e.g. "Heavy Fighter" ->
# "Schwerer Jäger"), so this one *is* worth resolving through
# parse_localized_strings() for real per-language text -- see
# parse_ship_types() below. Some of these refs resolve through a nested
# indirection (e.g. {1001,9824} -> {20221,4001}) rather than directly to
# text -- resolve_text()'s existing recursive {page,id} substitution
# already handles that with no extra code needed.
#
# "envoy" (2 unique one-off ships, the Envoy and Cypher) has no entry in
# the Lua legend that led here, but page 20221 itself turned out to be a
# real, complete, well-structured registry once dumped in full -- id/name/
# description triples in tight, regular blocks (xxx1 = name, xxx2 =
# description, incrementing by 10 per category, e.g. 5091/5092 =
# "Expeditionary Ship"/its description, 5101/5102 = "Envoy"/its
# description) -- so "envoy" does have a real entry after all, just one the
# Lua legend itself never surfaces (found by a direct full-page read, not
# via any Lua/icon cross-reference). Correcting course from this dict's own
# earlier claim that no real name existed for it anywhere.
#
# REVISIT when real mod support is built (see GitHub issue #5) -- a mod's
# own new ship_type value has no guaranteed entry on this same page (it's
# base-game content, not an extensible registry), so it'll still fall back
# to parse_ship_types()'s title-cased-code default, gracefully but without
# a real translated name, until this table is hand-extended for it.
SHIP_TYPE_NAME_REF = {
    "battleship": "{1001,9822}",
    "builder": "{1001,9821}",
    "carrier": "{1001,9823}",
    "compactor": "{1001,9826}",
    "corvette": "{1001,9828}",
    "courier": "{1001,9832}",
    "destroyer": "{1001,9824}",
    "envoy": "{20221,5101}",
    "expeditionary": "{20221,5091}",
    "fighter": "{1001,9816}",
    "freighter": "{1001,9819}",
    "frigate": "{1001,9829}",
    "gunboat": "{1001,9830}",
    "heavyfighter": "{1001,9833}",
    "largeminer": "{1001,9818}",
    "miner": "{1001,9818}",
    "resupplier": "{1001,9820}",
    "scavenger": "{1001,9825}",
    "scout": "{1001,9834}",
    "transporter": "{1001,9817}",
    "tug": "{1001,9827}",
}


def parse_ship_types(ships: list[dict], lang_table: dict) -> list[dict]:
    """Every real ship_type value actually present in `ships` (derived from
    the data itself, not a hardcoded enumeration -- so a mod's own new
    ship_type automatically gets a row here, falling back gracefully
    through SHIP_TYPE_NAME_REF's own missing-entry handling below), for the
    ship_types DB table backing the Type filter's real display names
    instead of the raw internal code shown unstyled.

    Display name comes from SHIP_TYPE_NAME_REF when this type has an entry
    there, else a title-cased version of the raw code (same fallback
    parse_factions()/parse_purposes() already use for their own no-real-
    name cases) -- see that dict's own docstring for where the mapped
    entries come from.

    Same "ware_id"/"name_ref" passenger keys as parse_purposes() (see that
    function's own docstring) so this list can be handed to
    parse_localized_strings() the same way, giving ship_type_name its own
    non-English coverage. Safe to share the main shared localized_strings
    keyspace (unlike races -- see that table's own docstring note): no
    ship_type value collides with any race/faction/purpose id in the
    current dataset.
    """
    ship_type_ids = sorted({s["ship_type"] for s in ships if s["ship_type"]})
    rows = []
    for ship_type_id in ship_type_ids:
        name_ref = SHIP_TYPE_NAME_REF.get(ship_type_id)
        ship_type_name = resolve_ref_attr(name_ref, lang_table) if name_ref else ship_type_id.replace("_", " ").title()
        rows.append(
            {
                "ship_type_id": ship_type_id,
                "ship_type_name": ship_type_name,
                "ware_id": ship_type_id,
                "name_ref": name_ref or "",
            }
        )
    return rows


# Equipment mount compatibility tag (engines_base/shields_base/weapons_base/
# turrets_base/thrusters_base/missiles_base.compatibility, and the same
# vocabulary on ship_component_groups.equipment_compatibility_class --
# see parse_equipment_mount()'s own docstring for where this comes from:
# every <connection tags="..."/> token besides the equipment-type token
# itself and pure bookkeeping tokens). Real refs, found via a direct search
# of the English language file for "Mining"/"Advanced" as standalone
# strings: page 20228 is titled "Equipment Compatibility Types" ("Names and
# descriptions of equipment compatibility types"), a complete, tidy
# registry (ids incrementing by 100, same shape as CARGO_TYPE_NAME_REF's
# own page 20205) -- Standard/Missile/Mining/High-Energy/Brane/Boron/Xenon/
# Advanced.
#
# "highpower" is mapped to High-Energy on a strong semantic match (not a
# structural confirmation the way a direct text search gave every other
# entry here) -- no ware/macro file spells out "highpower" alongside a
# {20228,...} ref the way, say, wares.xml's own name="{page,id}" attributes
# do for everything else. REVISIT if a real in-game example ever shows this
# wrong.
#
# "boron" and "khaak" are real, meaningful compatibility tags in the actual
# data (e.g. a Kha'ak-hull-only weapon mount) but deliberately NOT
# duplicated into this dict -- both are also real race ids, and this
# module already has a fully correct, independently-verified name for each
# one in the `races` table (parse_races()). parse_compatibility_types()
# below checks this dict first, then falls back to races' own race_name
# for exactly this reason, rather than risking two separately-maintained
# copies of "Boron"/"Kha'ak" drifting apart. "xenon" appears in both
# page 20228 (as its own compatibility type) and the races table -- kept
# here anyway since both resolve to the identical "Xenon" text either way,
# so there's no actual conflict to worry about.
#
# A great many real compatibility values are neither a page 20228 type nor
# a race id at all -- they're hull-specific hardpoint lock identifiers
# instead (e.g. "arg_destroyer_01", "ship_gen_m_yacht_01", "mandatory") --
# genuinely have no real display name anywhere in the game's own text
# data, so parse_compatibility_types() falls back to a title-cased version
# of the raw tag for these, same spirit as every other _NAME_REF dict's own
# no-real-name fallback.
COMPATIBILITY_NAME_REF = {
    "standard": "{20228,101}",
    "missile": "{20228,201}",
    "mining": "{20228,301}",
    "highpower": "{20228,401}",
    "brane": "{20228,501}",
    "xenon": "{20228,701}",
    "advanced": "{20228,801}",
}


def parse_compatibility_types(
    component_tables: list[list[dict]], ship_component_groups: list[dict], races: list[dict], lang_table: dict
) -> list[dict]:
    """Every distinct compatibility tag actually present across
    `component_tables` (engines/shields/weapons/turrets/thrusters/missiles'
    own already-parsed row lists, each row's own "compatibility" field) and
    `ship_component_groups` (every ship's own flattened component_groups,
    each one's own "equipment_compatibility_class" field -- same
    vocabulary, different key name, see that column's own schema comment).
    Both are comma-joined (parse_equipment_mount()'s own doing for the
    former, see that function's own docstring), so this splits every one
    apart before collecting the distinct set, unlike parse_ship_types()'s
    single-token case.

    Feeding `ship_component_groups` in too (not just component_tables) is
    what actually makes this list complete -- confirmed some real hull-lock
    tags (e.g. "atf_battleship_01") only ever appear on a ship's own
    (deliberately noisier -- see query_ship_components.py's own
    matching_items() docstring) connection tag set, never on any single
    piece of equipment's own already-cleaned compatibility requirement.
    Software-type groups are skipped -- their own
    equipment_compatibility_class is repurposed to hold a raw software
    ware_id list, not real compatibility tags at all (see this module's own
    "Software" docstring section), so including them would just pollute
    this table with meaningless entries.

    Display name resolution, in order: COMPATIBILITY_NAME_REF (the real
    page 20228 registry) -- else a matching race's own real race_name (see
    this dict's own docstring for why "boron"/"khaak" deliberately aren't
    duplicated into COMPATIBILITY_NAME_REF instead) -- else a title-cased
    version of the raw tag (hull-lock identifiers like "arg_destroyer_01"
    have no real name anywhere).

    Same "ware_id"/"name_ref" passenger-key shape as parse_ship_types() so
    this list can be handed to parse_localized_strings() the same way.
    """
    race_names = {race["race_id"]: race["race_name"] for race in races}
    tag_ids: set[str] = set()
    for rows in component_tables:
        for row in rows:
            compatibility = row.get("compatibility")
            if compatibility:
                tag_ids.update(compatibility.split(","))
    for group in ship_component_groups:
        if group.get("component_type") == "software":
            continue
        compatibility = group.get("equipment_compatibility_class")
        if compatibility:
            tag_ids.update(compatibility.split(","))

    rows_out = []
    for tag_id in sorted(tag_ids):
        name_ref = COMPATIBILITY_NAME_REF.get(tag_id)
        if name_ref:
            tag_name = resolve_ref_attr(name_ref, lang_table)
        elif tag_id in race_names:
            tag_name = race_names[tag_id]
        else:
            tag_name = tag_id.replace("_", " ").replace(",", ", ").title()
        rows_out.append(
            {
                "compatibility_type_id": tag_id,
                "compatibility_type_name": tag_name,
                "ware_id": tag_id,
                "name_ref": name_ref or "",
            }
        )
    return rows_out


# Missile/ammunition compatibility tag -- missiles_base.compatibility and
# weapons_base/turrets_base.ammunition_tags all share this one vocabulary:
# a bare launcher-type word ("dumbfire"/"guided"/"torpedo") or that same
# word prefixed with a size ("small"/"medium"/"large"), e.g.
# "largedumbfire" -- a genuinely different vocabulary from
# COMPATIBILITY_NAME_REF's own page 20228 one, despite living on the same
# "compatibility"-shaped columns (missiles_base.compatibility in
# particular used to be run through COMPATIBILITY_NAME_REF too, producing
# ugly unsplit fallbacks like "Largedumbfire" -- this dict is what actually
# fixes that).
#
# The compound phrases page 20105 ("Weapons and Turrets") shows for actual
# launcher items are "Dumbfire Launcher" ({20105,1121}), "Tracking
# Launcher" ({20105,1141}), "Torpedo Launcher" ({20105,1161}) -- not the
# bare type word alone -- but each bare word also exists there as its own
# separate, real, reusable {page,id} entry (confirmed by grepping the raw
# English file for e.g. ">Dumbfire<" as a standalone string, then checking
# it's referenced elsewhere on the same page, e.g. id 4245 "(Dumbfire
# Mk1){20105,4243}" -- a real in-game short name, not a coincidental
# isolated string). "guided" mapping to "Tracking" (not "Guided") is that
# real, confirmed in-game name -- deliberately different from
# MISSILE_WEAPON_SYSTEM_NAME_REF's own "Guided" (page 1040's own, separate
# "Weapon Systems" filter-category text for the same underlying concept:
# two different real in-game labels for the same thing, one for launcher
# item/ammunition names, the other for a filter category).
#
# "Small"/"Medium"/"Large" have no equivalent standalone entry on page
# 20105 itself, but a clean, real, generic size-scale registry exists on
# page 1001 (Interface) -- the same page SHIP_TYPE_NAME_REF's own Lua-UI
# refs live on -- id 2853/2854/2855, sandwiched between "Very Small"/"Very
# Large"/"Huge" siblings, confirmed via a direct search of the English file
# for ">Small<" etc.
AMMUNITION_TYPE_NAME_REF = {
    "dumbfire": "{20105,4243}",
    "guided": "{20105,4283}",
    "torpedo": "{20105,6461}",
}
AMMUNITION_SIZE_NAME_REF = {
    "small": "{1001,2853}",
    "medium": "{1001,2854}",
    "large": "{1001,2855}",
}


def _decompose_ammunition_tag(tag_id: str) -> tuple[str | None, str | None]:
    """Splits a raw ammunition-compatibility tag into its (size_ref,
    type_ref) pair -- size_ref is None for a bare, non-size-prefixed tag
    (e.g. "dumbfire", "guided", "torpedo"); type_ref is None when the
    (possibly size-stripped) remainder isn't a recognized type word at all
    (a hull-lock identifier like "ship_ter_l_flagship_01"). Shared by
    ammunition_compatibility_display_name() (English) and
    parse_ammunition_compatibility_localized_strings() (every other
    language) so both walk the exact same decomposition rule.
    """
    for size_prefix, size_ref in AMMUNITION_SIZE_NAME_REF.items():
        if tag_id.startswith(size_prefix):
            return size_ref, AMMUNITION_TYPE_NAME_REF.get(tag_id[len(size_prefix) :])
    return None, AMMUNITION_TYPE_NAME_REF.get(tag_id)


def ammunition_compatibility_display_name(tag_id: str, lang_table: dict) -> str:
    """"largedumbfire" -> "Large Dumbfire", "guided" -> "Tracking",
    "ship_ter_l_flagship_01" -> "Ship Ter L Flagship 01" (a hull-lock
    identifier -- _decompose_ammunition_tag() found no type_ref at all,
    same graceful title-cased fallback every other compatibility-style
    dict in this module uses).

    strip_trailing_dev_comment() on both pieces: AMMUNITION_SIZE_NAME_REF's
    page 1001 entries are shared with a generic Discount/Commission Level
    scale (Tiny/Very Small/Small/.../Huge), not an equipment-size-specific
    registry, and at least one language's own translation of "small" there
    carries a bundled translator uncertainty note ("Wenig(klein?)" in
    German) -- same class of real Egosoft data-quality quirk
    strip_trailing_dev_comment() already exists to clean up (see its own
    docstring), just discovered here instead of on a CREW_ROLE_NAME_REF/
    SOURCE_VERSION_NAME_REF ref. English carries no such artifact today,
    so this is a no-op for the base name -- applied anyway to stay
    symmetric with the per-language composer below, which needs it for
    real.
    """
    size_ref, type_ref = _decompose_ammunition_tag(tag_id)
    if type_ref is None:
        return tag_id.replace("_", " ").title()
    type_name = strip_trailing_dev_comment(resolve_ref_attr(type_ref, lang_table))
    if size_ref is None:
        return type_name
    size_name = strip_trailing_dev_comment(resolve_ref_attr(size_ref, lang_table))
    return f"{size_name} {type_name}"


def parse_ammunition_compatibility_types(
    missiles: list[dict], weapons: list[dict], turrets: list[dict], lang_table: dict
) -> list[dict]:
    """Every distinct ammunition-compatibility tag actually present across
    missiles' own "compatibility" field and weapons'/turrets' own
    "ammunition_tags" field (both comma-joined -- see this table's own
    schema comment). Display name always comes from
    ammunition_compatibility_display_name() -- see that function's own
    docstring for the resolution rule.

    Same "ware_id"/"name_ref" passenger-key shape as parse_ship_types() so
    this list can be handed to parse_localized_strings() the same way --
    but only carries a real name_ref for a *bare* tag (dumbfire/guided/
    torpedo, straight from AMMUNITION_TYPE_NAME_REF). A size-prefixed
    compound tag (e.g. "largedumbfire") has no single ref of its own to
    give parse_localized_strings() -- its own non-English text instead
    comes from parse_ammunition_compatibility_localized_strings() below,
    which composes it from two independently-resolved refs per language.
    A hull-lock tag (e.g. "ship_ter_l_flagship_01") gets neither -- "" here,
    same as every other never-really-localized fallback in this module.

    The "ware_id" passenger key is "ammunition_compatibility_type_<id>",
    not the bare id: "torpedo" is also missile_weapon_systems' own real id
    (a different, real page-1040 ref, e.g. plural "Torpedos" as a filter-
    category label vs. this table's singular "Torpedo" launcher/ammo name)
    -- without this prefix, parse_localized_strings()'s shared keyspace/
    dedup silently hands whichever list runs first's translation to both,
    hiding the other's real, sometimes genuinely different, text. Both
    GET /api/ammunition_compatibility_types and
    parse_ammunition_compatibility_localized_strings() below use this same
    prefix.
    """
    tag_ids: set[str] = set()
    for missile in missiles:
        compatibility = missile.get("compatibility")
        if compatibility:
            tag_ids.update(compatibility.split(","))
    for rows in (weapons, turrets):
        for row in rows:
            ammunition_tags = row.get("ammunition_tags")
            if ammunition_tags:
                tag_ids.update(ammunition_tags.split(","))

    rows_out = []
    for tag_id in sorted(tag_ids):
        size_ref, type_ref = _decompose_ammunition_tag(tag_id)
        name_ref = type_ref if size_ref is None else ""
        rows_out.append(
            {
                "ammunition_compatibility_type_id": tag_id,
                "ammunition_compatibility_type_name": ammunition_compatibility_display_name(tag_id, lang_table),
                "ware_id": f"ammunition_compatibility_type_{tag_id}",
                "name_ref": name_ref or "",
            }
        )
    return rows_out


def parse_ammunition_compatibility_localized_strings(ammunition_compatibility_types: list[dict]) -> list[dict]:
    """Real non-English text for every size-prefixed compound
    ammunition_compatibility_types row (e.g. "largedumbfire" ->
    German "Groß Ungelenkt", say) -- the one case
    parse_localized_strings() itself can't handle, since a compound tag has
    no single {page,id} ref of its own to resolve (see
    parse_ammunition_compatibility_types()'s own docstring): this composes
    each language's own text from AMMUNITION_SIZE_NAME_REF +
    AMMUNITION_TYPE_NAME_REF independently, joined with a space, mirroring
    how the base English name itself is built in
    ammunition_compatibility_display_name().

    Loads every language file itself (can't reuse parse_localized_strings()'s
    own internal tables -- they're a local variable there, not returned) --
    same LANGUAGE_FILES/load_language_table() pattern, and the same
    "missing entry in this language's own raw table = no translation
    available, skip this (ware_id, lang_id) row entirely" contract
    (checked per-piece here: if either the size word or the type word is
    missing from a given language, no composed row is written for that
    language at all, rather than risk a half-English "Small Ungelenkt").

    A bare tag (dumbfire/guided/torpedo -- real name_ref already set by
    parse_ammunition_compatibility_types(), so parse_localized_strings()
    already covers it) or a hull-lock tag (no type_ref at all) produces no
    rows here.
    """
    lang_tables: dict[str, dict] = {}
    for lang_id, filename in LANGUAGE_FILES.items():
        if lang_id == "en":
            continue
        path = DATA / "names" / filename
        if path.exists():
            lang_tables[lang_id] = load_language_table(path)

    def _lookup(ref: str, table: dict) -> str | None:
        m = FULL_REF_RE.match(ref)
        raw = table.get((m.group(1), m.group(2))) if m else None
        # strip_trailing_dev_comment() -- see
        # ammunition_compatibility_display_name()'s own comment for why
        # (AMMUNITION_SIZE_NAME_REF's "small" entry carries a bundled
        # translator note in at least one language).
        return strip_trailing_dev_comment(resolve_text(raw, table)) if raw is not None else None

    rows = []
    for row in ammunition_compatibility_types:
        tag_id = row["ammunition_compatibility_type_id"]
        size_ref, type_ref = _decompose_ammunition_tag(tag_id)
        if size_ref is None or type_ref is None:
            continue
        for lang_id, table in lang_tables.items():
            size_name = _lookup(size_ref, table)
            type_name = _lookup(type_ref, table)
            if size_name is None or type_name is None:
                continue
            # "ammunition_compatibility_type_" prefix -- see
            # parse_ammunition_compatibility_types()'s own docstring for
            # why (avoids colliding with missile_weapon_systems' own
            # "torpedo" id in the shared localized_strings keyspace).
            rows.append(
                {"ware_id": f"ammunition_compatibility_type_{tag_id}", "lang_id": lang_id, "text": f"{size_name} {type_name}"}
            )
    return rows


# thrusters_base.thruster_class ("allround"/"combat" -- a player playstyle
# choice, not a tier, see THRUSTER_WARE_RE's own comment for where this is
# recovered from). Real refs, found via a direct search of the English
# language file for "All-round"/"Combat" as standalone strings: page 20107
# is the thruster-selection UI's own text page -- id 10003 = "All-round",
# id 1203 = "Combat".
THRUSTER_CLASS_NAME_REF = {
    "allround": "{20107,10003}",
    "combat": "{20107,1203}",
}


def parse_thruster_classes(thrusters: list[dict], lang_table: dict) -> list[dict]:
    """Every distinct thruster_class value actually present in `thrusters`
    (derived from the data, not hardcoded -- same spirit as
    parse_ship_types()), for the thruster_classes DB table backing the
    Component Analyzer's own "Thruster Class" stat column with a real
    display name instead of the raw internal code ("allround"/"combat").

    Same "ware_id"/"name_ref" passenger-key shape as parse_ship_types() so
    this list can be handed to parse_localized_strings() the same way,
    giving thruster_class_name its own non-English coverage.
    """
    thruster_class_ids = sorted({t["thruster_class"] for t in thrusters if t.get("thruster_class")})
    rows = []
    for thruster_class_id in thruster_class_ids:
        name_ref = THRUSTER_CLASS_NAME_REF.get(thruster_class_id)
        thruster_class_name = (
            resolve_ref_attr(name_ref, lang_table) if name_ref else thruster_class_id.replace("_", " ").title()
        )
        rows.append(
            {
                "thruster_class_id": thruster_class_id,
                "thruster_class_name": thruster_class_name,
                "ware_id": thruster_class_id,
                "name_ref": name_ref or "",
            }
        )
    return rows


# deployables_base.deployable_type (satellite/resourceprobe/mine/
# lasertower/navbeacon -- see DEPLOYABLE_TYPE_TAGS/classify_deployable_type()
# below). Real refs, found via a direct search of the English language file
# for "Resource Probe" as a standalone string: page 20201 ("Wares") is a
# huge, non-registry page (mostly production-ware flavor text, same
# "real names live here, but it's not a clean registry" situation as
# AMMUNITION_TYPE_NAME_REF's own page 20105), but the "(*CONSUMABLE
# WARES*)" section (ids 20101-21002) happens to give 4 of these 5 types
# their own clean, standalone real ware name: Mine (20201), Satellite
# (20301), Resource Probe (20701 -- the user's own confirmed example),
# Nav Beacon (20801).
#
# "lasertower" is the exception: page 20201 only has "Laser Tower Mk1"
# (20501)/"Laser Tower Mk2" (20601), both real but tier-specific --
# neither reads right as a generic category label spanning both. A plain
# "Laser Tower" does exist as its own real entry, just on a different page:
# 20221, id 1041 -- the same ship_type registry SHIP_TYPE_NAME_REF already
# treats as authoritative for exactly this kind of generic category name
# (laser towers apparently get their own ship_type entry there too, e.g.
# "An automated weapons platform." as the description).
DEPLOYABLE_TYPE_NAME_REF = {
    "mine": "{20201,20201}",
    "satellite": "{20201,20301}",
    "lasertower": "{20221,1041}",
    "resourceprobe": "{20201,20701}",
    "navbeacon": "{20201,20801}",
}


def parse_deployable_types(deployable_wares: list[dict], lang_table: dict) -> list[dict]:
    """Every distinct deployable_type value actually present in
    `deployable_wares` (derived from the data, not hardcoded -- same spirit
    as parse_ship_types()), for the deployable_types DB table backing the
    Component Analyzer's own "Deployable Type" stat column with a real
    display name instead of the raw internal code ("resourceprobe").

    Same "ware_id"/"name_ref" passenger-key shape as parse_ship_types() so
    this list can be handed to parse_localized_strings() the same way,
    giving deployable_type_name its own non-English coverage -- except the
    "ware_id" passenger key is "deployable_type_<id>", not the bare id:
    "mine" is both a real deployable_type AND a real purpose id (see
    purposes.xml), and parse_localized_strings()'s shared keyspace/dedup
    would otherwise silently hand this table the *purpose*'s own German
    "Bergbau" ("Mining") instead of the deployable weapon's own "Mine" --
    same class of real collision this module already solved once for
    races-vs-factions, just narrow enough here (one token) to fix by
    namespacing this table's own passenger key instead of splitting into a
    whole separate table. GET /api/deployable_types' own query strips the
    same prefix back off when joining.
    """
    deployable_type_ids = sorted({d["deployable_type"] for d in deployable_wares if d.get("deployable_type")})
    rows = []
    for deployable_type_id in deployable_type_ids:
        name_ref = DEPLOYABLE_TYPE_NAME_REF.get(deployable_type_id)
        deployable_type_name = (
            resolve_ref_attr(name_ref, lang_table) if name_ref else deployable_type_id.replace("_", " ").title()
        )
        rows.append(
            {
                "deployable_type_id": deployable_type_id,
                "deployable_type_name": deployable_type_name,
                "ware_id": f"deployable_type_{deployable_type_id}",
                "name_ref": name_ref or "",
            }
        )
    return rows


# Ware cargo transport type (a ship's own cargo hold "tags", e.g.
# "container"/"solid"/"liquid" -- see parse_ship_docks() in this same
# module, and ships_base.cargo_type) -- real refs, found via a direct
# search of the English language file for "Container"/"Liquid"/"Solid" as
# standalone strings: page 20205 is titled "Ware Transport Types" ("Names
# and descriptions of ware cargo transport types"), a complete registry
# matching wares.xml's own `transport="..."` attribute vocabulary exactly
# (container/solid/liquid/passenger/equipment/inventory/software/workunit/
# ship/research, plus "condensate" with no corresponding transport= value
# seen in the current dataset). Every ship's own cargo hold only ever uses
# container/solid/liquid in practice (confirmed against every real
# storage_*_macro's own <cargo tags="..."/>, including the combined
# "container solid" case -- two space-separated tokens from this same
# vocabulary, not a distinct fourth type), but the full registry is mapped
# here anyway, same "derive from real data, don't hand-restrict" spirit as
# SHIP_TYPE_NAME_REF -- a mod adding a ship with a different cargo tag
# would already have a real name to resolve.
CARGO_TYPE_NAME_REF = {
    "container": "{20205,100}",
    "solid": "{20205,200}",
    "liquid": "{20205,300}",
    "passenger": "{20205,400}",
    "equipment": "{20205,500}",
    "inventory": "{20205,600}",
    "software": "{20205,700}",
    "workunit": "{20205,800}",
    "ship": "{20205,900}",
    "research": "{20205,1000}",
    "condensate": "{20205,1100}",
}


def parse_cargo_types(ships: list[dict], economy_wares: list[dict], lang_table: dict) -> list[dict]:
    """Every distinct cargo-type token actually present across `ships`' own
    cargo_type field OR `economy_wares`' own transport field -- derived
    from the data, not hardcoded (same spirit as parse_ship_types()).
    ships_base.cargo_type is a space-separated field holding one or two
    tokens (see CARGO_TYPE_NAME_REF's own docstring for the "container
    solid" case); economy_wares_base.transport is always a single token,
    but real ones ships never use (e.g. "condensate" -- confirmed via page
    20205 "Ware Transport Types") would otherwise never get a row here
    even though CARGO_TYPE_NAME_REF already has a mapping for them. Keyed
    by the individual token, not either field's own combined/raw string,
    so a caller splits (for ships_base.cargo_type) or looks up directly
    (for economy_wares_base.transport, already a single token) and finds
    the same row either way. Same ware_id/name_ref passenger-key shape as
    parse_ship_types() so this list can be handed to
    parse_localized_strings() the same way.
    """
    ship_tokens = {token for s in ships if s["cargo_type"] for token in s["cargo_type"].split()}
    ware_tokens = {token for w in economy_wares if w["transport"] for token in w["transport"].split()}
    cargo_type_ids = sorted(ship_tokens | ware_tokens)
    rows = []
    for cargo_type_id in cargo_type_ids:
        name_ref = CARGO_TYPE_NAME_REF.get(cargo_type_id)
        cargo_type_name = resolve_ref_attr(name_ref, lang_table) if name_ref else cargo_type_id.title()
        rows.append(
            {
                "cargo_type_id": cargo_type_id,
                "cargo_type_name": cargo_type_name,
                "ware_id": cargo_type_id,
                "name_ref": name_ref or "",
            }
        )
    return rows


# Missile "type" (missiles_base.weapon_system -- <weapon system="..."/> on
# the missile's own macro, see analyze_missile_macro()) resolved to a real
# display name. Found the same way CARGO_TYPE_NAME_REF was: a direct search
# of the English language file for "Torpedos" as a standalone string. Page
# 1040 is titled "Weapon Systems" ("Describes the different weapon systems
# available in the game") and covers far more than missiles (Drones/Bombs/
# Standard Weapons/Turrets by range/...), but only 3 of its ids are ever
# actually used as a missiles_base.weapon_system value in the current
# dataset -- the id itself is never referenced anywhere in the structured
# XML (macros/wares/menus), only this hand-picked correspondence between
# the two vocabularies, same "known small enum -> real localization page"
# technique as CREW_ROLE_NAME_REF.
MISSILE_WEAPON_SYSTEM_NAME_REF = {
    "missile_dumbfire": "{1040,7}",
    "missile_guided": "{1040,8}",
    "torpedo": "{1040,9}",
}


def parse_missile_weapon_systems(missiles: list[dict], lang_table: dict) -> list[dict]:
    """Every distinct weapon_system token actually present across
    `missiles`' own weapon_system field (derived from the data, not
    hardcoded -- same spirit as parse_cargo_types()). Same ware_id/name_ref
    passenger-key shape so this list can be handed to
    parse_localized_strings() the same way.
    """
    weapon_system_ids = sorted({m["weapon_system"] for m in missiles if m.get("weapon_system")})
    rows = []
    for weapon_system_id in weapon_system_ids:
        name_ref = MISSILE_WEAPON_SYSTEM_NAME_REF.get(weapon_system_id)
        weapon_system_name = resolve_ref_attr(name_ref, lang_table) if name_ref else weapon_system_id.title()
        rows.append(
            {
                "weapon_system_id": weapon_system_id,
                "weapon_system_name": weapon_system_name,
                "ware_id": weapon_system_id,
                "name_ref": name_ref or "",
            }
        )
    return rows


def index_ship_files(suffix: str) -> dict[str, tuple[str, Path]]:
    """{macro/component name (no .xml) -> (class_value, path)}, built by
    scanning every SHIPS_DIR/<class>_<suffix>/ folder extract_game_data.py's
    sort_ship_files_by_class() sorted real ship files into. Lets a caller
    look up any ship macro or component by name alone, with no need to
    already know (or guess from a ware_id/filename) which class/size it
    belongs to -- that's exactly what the returned class_value answers,
    read from the file's own <macro class="..."/>/<component class="..."/>
    attribute at sort time, not assumed from a folder name.

    Deliberately keyed by the *file's own* discovered class (e.g. "ship_l"),
    not by the mapped short size code -- see SHIP_CLASS_TO_SIZE_CODE, a
    separate, app-side concern this function has no opinion on.
    """
    index: dict[str, tuple[str, Path]] = {}
    for class_dir in sorted(SHIPS_DIR.glob(f"*_{suffix}")):
        class_value = class_dir.name.removesuffix(f"_{suffix}")
        for path in class_dir.glob("*.xml"):
            index[path.stem] = (class_value, path)
    return index

REF_RE = re.compile(r"\{(\d+),\s*(\d+)\}")
FULL_REF_RE = re.compile(r"^\{(\d+),\s*(\d+)\}$")
# Dev-comment prefix, e.g. "(Magnetar \(Gas\) Vanguard){20101,11101} ...".
# Escaped \( \) inside the comment must not be treated as the closing paren.
LEADING_PAREN_RE = re.compile(r"^\((?:\\.|[^()])*\)\s*")
# Also covers escaped hyphens ("\-"), needed for German compound-word
# names (e.g. "Expeditions\-schiff", "Silizium\-karbid") -- the game's own
# text format escapes a literal hyphen the same way it escapes literal
# parens, and both need the same backslash stripped before display.
# Confirmed narrow: only German data has ever used this, 24 ware_ids total.
ESCAPED_CHAR_RE = re.compile(r"\\([()-])")
# Bare trailing "(...)" dev-comment annotation, e.g. "Marines(plural)" ->
# "Marines" -- NOT applied generically by resolve_text() (see that
# function's own docstring/LEADING_PAREN_RE's comment for why a blanket
# trailing-paren strip would corrupt real names using escaped "\(...\)"
# parens, e.g. "Magnetar \(Gas\) Vanguard"). Used narrowly by
# strip_trailing_dev_comment() below, only against small, manually-
# verified value sets -- never arbitrary resolved game text.
TRAILING_PAREN_RE = re.compile(r"\s*\([^()]*\)\s*$")


def strip_trailing_dev_comment(text: str) -> str:
    """Strips one bare trailing "(...)" annotation via TRAILING_PAREN_RE --
    see that constant's own comment for why this isn't something
    resolve_text() does for every resolved string. Confirmed needed for
    CREW_ROLE_NAME_REF's own two refs, whose raw language-table text is
    "Marines(plural)"/"Service crew(plural)" (and the German
    "Marinesoldaten(Plural)") -- a real Egosoft data-quality quirk, not
    something this pipeline introduces.
    """
    return TRAILING_PAREN_RE.sub("", text)

# Every real production method (a ware's own <production method="..."
# name="{page,id}"/>) across the whole dataset, manually curated from a
# direct audit of every distinct resolved method name:
#   Universal 1064/1064 clean, Terran 143/143, Boron 76/76, Teladi 12/12,
#   Argon 7/7, Paranid 7/7, Closed Loop 4/4, Split 2/2 -- all fully player-
#   buildable, kept as-is.
#   Xenon 127/127 tagged "noplayerbuild" (an NPC/enemy-only recipe
#   variant) -- kept anyway, deliberately: this list isn't only used to
#   pick a build focus for a player's *own* factories, it's also how
#   Xenon/Kha'ak ships get priced/compared at all in the Cost Analysis
#   tool, since those ships' own components have no other method to fall
#   back to. "noplayerbuild" is a real in-game distinction (this recipe
#   variant isn't selectable as a factory blueprint) but not a reason to
#   hide the data -- confirmed the tag doesn't even mean "never player-
#   accessible" in general: the Recycling method below carries the same
#   tag, and is produced by a real, player-buildable Scrap Recycler module
#   that references it directly, bypassing the normal factory-blueprint
#   picker entirely.
#   Recycling 5/5 also tagged "noplayerbuild", kept for that reason above.
#   A second, garbled method (2/2 noplayerbuild, "Processing" followed by a
#   giant leaked dev comment -- its own name="{20206,1301}" resolves via a
#   *trailing*, not leading, "(...)" comment, which resolve_text() has no
#   safe way to strip generically: a regex matching an unescaped trailing
#   "(...)" also matches inside strings using ESCAPED_CHAR_RE's own escape
#   convention (e.g. ship names like "Magnetar \(Gas\) Vanguard"), silently
#   corrupting them. Still dropped -- unlike Xenon/Recycling above this
#   isn't a noplayerbuild judgment call, it's a cosmetic text-resolution
#   bug (a real fix would need a way to distinguish "trailing dev comment"
#   from "trailing escaped parenthetical in a real name," not attempted
#   here) -- same Scrap-Processor/recycling concept as Recycling in
#   practice, and only 2 occurrences total, so nothing is lost by dropping
#   it specifically.
# Ordered Universal first, Terran second, Recycling/Xenon last (all
# explicit product requirements), everything else alphabetically between.
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
    "Xenon",
]


def collect_build_method_refs(entity_lists: list[list[dict]]) -> dict[str, str]:
    """{resolved English build method name -> its own name_ref}, built by
    scanning every entity's own `productions` list (each production block
    carries "method_name"/"method_name_ref" -- see the ships/economy_wares/
    equipment_wares/missile_wares/deployable_wares/drone_wares/
    countermeasure_wares resolution loops in main(), which this must run
    after). First ref seen for a given name wins -- same "first definition
    wins" convention parse_factions() already uses -- since every
    production block sharing a method name is expected to point at the
    same underlying {page,id} ref anyway.

    This exists because BUILD_METHODS above is a hand-curated list of
    already-resolved English text with no ref of its own preserved --
    unlike ship_type/purpose/race/faction, a build method's *English name*
    doubles as its real internal id everywhere in this app (ships_base.
    production_method, summarize_production.py's own cost-calc grouping,
    the frontend's build_method_priority payloads, persisted fleet state)
    since the game's own internal, non-English <production method="..."/>
    code is never captured at all -- deliberately not changing that (a much
    bigger, riskier refactor touching calculation logic and persisted user
    state, not just a display label -- see GitHub issue #3 discussion) --
    this only recovers the ref needed to localize the *display* text for
    that same stable English key, see parse_build_methods() below.
    """
    refs: dict[str, str] = {}
    for entities in entity_lists:
        for entity in entities:
            for prod in entity.get("productions", []):
                name = prod.get("method_name")
                ref = prod.get("method_name_ref")
                if name and ref and name not in refs:
                    refs[name] = ref
    return refs


def parse_build_methods(method_name_refs: dict[str, str]) -> list[dict]:
    """One row per BUILD_METHODS entry, for the build_methods DB table
    backing real per-language display text (Build Method filter, Cost
    Analysis's Build Method modal and fleet-tab priority button) while
    every internal use of a build method's name (matching, filtering,
    persisted fleet state) keeps using the plain English string unchanged
    -- see collect_build_method_refs()'s own docstring for why.

    build_method_name doubles as both the table's real primary key and the
    base (English) display value -- unlike ship_type/purpose/race/faction,
    there's no separate internal code to key on here, so unlike those this
    table has no need for a second "_name" column: the base table's own
    "name" *is* build_method_name, and COALESCE(localized_strings.text,
    build_methods.build_method_name) at query time gives the same "fall
    back to English" shape every other localized lookup in this app has.

    A method with no ref recovered (shouldn't happen for any of the 10 real
    BUILD_METHODS entries, all confirmed to come from real <production
    name="{page,id}"/> attributes) still gets a row -- see "ware_id"/
    "name_ref" below -- just with name_ref empty, which
    parse_localized_strings() already treats as "no translation available"
    the same way a missing ref anywhere else does.
    """
    return [
        {
            "build_method_name": name,
            "ware_id": name,
            "name_ref": method_name_refs.get(name, ""),
        }
        for name in BUILD_METHODS
    ]


# X4 has no separate "marine"/"service crew" *ware* -- the single real
# "crew" ware (crew_base) covers both, and a saved loadout's own
# <crew role="marine"/service" exact="N"/> element is how the game tracks
# which role crew already aboard are assigned to (see this module's
# "Countermeasures and crew" docstring section) -- "marine"/"service" here
# are exactly those same two real internal role codes, not app-invented
# ids. Their *display names*, however, aren't attached to any XML data
# this pipeline already reads -- found instead by tracing the game's own
# crew-assignment UI Lua (ui/addons/ego_detailmonitor/menu_map.lua, ~line
# 13108-13109): `{ name = ReadText(20208, 20103), role = "service" }` /
# `{ name = ReadText(20208, 20203), role = "marine" }` -- same "no XML
# registry, but a real Lua-sourced ref" situation as SHIP_TYPE_NAME_REF,
# not app-owned UI text the way it was first (wrongly) treated as (i18next
# was tried here initially -- see the git history of src/static/i18n/
# de.json for the two guessed strings this replaced, one of which,
# "Marinesoldaten", happened to exactly match the real word by coincidence,
# and one, "Wartungspersonal", didn't -- the real one is "Servicemannschaft").
CREW_ROLE_NAME_REF = {
    "marine": "{20208,20203}",
    "service": "{20208,20103}",
}


def parse_crew_roles(lang_table: dict) -> list[dict]:
    """One row per CREW_ROLE_NAME_REF entry, for the crew_roles DB table
    backing real per-language display text for the ship builder's Marines/
    Service Crew rows (see app.js's CREW_ROLES). Unlike build_methods,
    crew_role_id ("marine") is a real internal code genuinely distinct from
    its own display text ("Marines") -- same "id" + resolved "name" shape
    as parse_ship_types()/parse_purposes(), not parse_build_methods()'s
    single-column one.

    Both refs' raw text carries a trailing "(plural)" dev-comment
    resolve_text() doesn't strip (see strip_trailing_dev_comment()'s own
    docstring) -- applied here to the base English name specifically; the
    non-English translation in localized_strings gets the same treatment
    separately, in main(), right after parse_localized_strings() resolves
    it (that function is shared by every entity in this pipeline, so this
    two known values' cleanup can't live inside it).
    """
    rows = []
    for role_id, name_ref in CREW_ROLE_NAME_REF.items():
        rows.append(
            {
                "crew_role_id": role_id,
                "crew_role_name": strip_trailing_dev_comment(resolve_ref_attr(name_ref, lang_table)),
                "ware_id": role_id,
                "name_ref": name_ref,
            }
        )
    return rows


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
    text = ESCAPED_CHAR_RE.sub(r"\1", text)
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


def factions_files() -> list[Path]:
    """Base game factions.xml plus every extension's own
    factions_<suffix>.xml -- see factions_xml_jobs() in
    extract_game_data.py. Only 5 of 7 extensions actually ship one
    (ego_dlc_mini_01/mini_02 don't), so this glob naturally comes up short
    for those two rather than erroring -- same "whichever files actually
    exist" approach as wares_files() above.
    """
    return sorted(WARES_DIR.glob("factions*.xml"))


WARE_PATCH_SEL_RE = re.compile(r"^/wares/ware\[@id='([^']+)'\]$")


def iter_ware_elements(paths: list[Path]):
    """Yield every <ware> element across all of `paths` (base wares.xml plus
    every expansion's wares_<suffix>.xml), patches applied -- one merged
    pass across every file, not per-file, so patch order relative to the
    ware it targets never matters (every file's own new-ware definitions are
    collected first, patches are resolved against that complete set after).

    Base wares.xml has a plain <wares> root with <ware> children. Each
    expansion's wares_<suffix>.xml is a <diff> patch instead, with two
    distinct block shapes:
      - <add sel="/wares"> -- a brand-new ware definition. First file wins
        on a duplicate id (prints the same "duplicate ware id" warning every
        caller used to print itself -- centralized here now that dedup
        happens once for every caller instead of separately per parser).
      - <add sel="/wares/ware[@id='...']"> -- a patch to an *existing* ware
        (new/replacement <production> methods, extra <owner> factions,
        etc.) -- appended onto that ware's own Element in place. Silently
        ignored if the target id was never actually defined by any file
        (e.g. a patch aimed at DLC-gated content this dataset doesn't have
        installed) -- nothing to merge onto, not an error.

    Previously (see git history) the per-ware patch case was skipped
    entirely, on the assumption it "mostly adds extra owner factions to
    base-game ships" -- confirmed wrong: it's also how expansions attach
    new production methods to *existing* wares (e.g. the Terran DLC adding
    a Terran recipe to a thruster that only shipped with a Universal one),
    which was silently dropping real, player-relevant build methods for
    every ware category, not just ships.
    """
    wares_by_id: dict[str, ET.Element] = {}
    patches: list[tuple[str, ET.Element, Path]] = []

    for path in paths:
        root = ET.parse(path).getroot()
        if root.tag == "wares":
            new_ware_elements = root.findall("ware")
        elif root.tag == "diff":
            new_ware_elements = []
            for add in root.findall("add"):
                sel = add.get("sel")
                if sel == "/wares":
                    new_ware_elements.extend(add.findall("ware"))
                elif sel:
                    match = WARE_PATCH_SEL_RE.match(sel)
                    if match:
                        patches.append((match.group(1), add, path))
        else:
            raise ValueError(f"Unexpected root tag '{root.tag}' in {path}")

        for ware in new_ware_elements:
            ware_id = ware.get("id")
            if ware_id in wares_by_id:
                print(f"WARNING: duplicate ware id '{ware_id}' (in {path.name}), skipping")
                continue
            wares_by_id[ware_id] = ware

    for target_id, patch_el, path in patches:
        target = wares_by_id.get(target_id)
        if target is None:
            continue
        for child in patch_el:
            target.append(child)

    return wares_by_id.values()


def parse_ship_wares(paths: list[Path]) -> list[dict]:
    ships = []
    for ware in iter_ware_elements(paths):
        tags = (ware.get("tags") or "").split()
        if "ship" not in tags:
            continue

        ware_id = ware.get("id")

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

    Also carries `volume`/`transport` straight off the <ware> element
    itself -- see this function's own note on those two fields below for
    why they're only parsed here, not for every ware kind.
    """
    wares = []
    for ware in iter_ware_elements(paths):
        tags = (ware.get("tags") or "").split()
        if "economy" not in tags and "processed" not in tags:
            continue

        ware_id = ware.get("id")

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
                # Real per-ware cargo stats -- how much hold space one unit
                # takes (`volume`) and which cargo-hold type it needs
                # (`transport`: "container"/"liquid"/"solid", matching
                # cargo_types.cargo_type_id, plus a handful of "condensate"
                # outliers -- a real fourth value this table doesn't have a
                # row for, left as a raw string rather than forcing a join
                # that would drop them). Only meaningful for these
                # production-chain wares -- every other ware kind in
                # wares.xml also carries a `volume`/`transport` pair, but
                # it's always a flat, meaningless "volume=1,
                # transport=<its own type name>" placeholder (confirmed:
                # ships, equipment, missiles, drones, countermeasures, crew
                # all do this), so this is deliberately not parsed anywhere
                # else.
                "volume": ware.get("volume"),
                "transport": ware.get("transport"),
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

    `owners` is the same real <owner faction="..."/> list ships_base.owners
    already reads for ships (see parse_ship_wares()) -- confirmed present on
    engine/shield/weapon/turret wares too, not a ships-only element. Empty
    for the handful of genuinely faction-agnostic wares (every thruster --
    already known to carry no faction/tier lock at all, see
    THRUSTER_COMPATIBILITY -- plus a few EVA-spacesuit engines/weapons),
    same "no owner data" case ships_base.owners already tolerates.
    """
    wares = []
    for ware in iter_ware_elements(paths):
        tags = set((ware.get("tags") or "").split())
        equipment_type = classify_equipment_type(tags)
        if "equipment" not in tags or equipment_type is None:
            continue

        ware_id = ware.get("id")

        owners = [o.get("faction") for o in ware.findall("owner")]

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
                "owners": owners,
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
    for ware in iter_ware_elements(paths):
        tags = (ware.get("tags") or "").split()
        if "equipment" not in tags or "missile" not in tags:
            continue

        ware_id = ware.get("id")

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
    for ware in iter_ware_elements(paths):
        tags = set((ware.get("tags") or "").split())
        deployable_type = classify_deployable_type(tags)
        if "equipment" not in tags or deployable_type is None:
            continue

        ware_id = ware.get("id")

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
    for ware in iter_ware_elements(paths):
        tags = set((ware.get("tags") or "").split())
        if "equipment" not in tags or "drone" not in tags:
            continue

        ware_id = ware.get("id")

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
    for ware in iter_ware_elements(paths):
        tags = set((ware.get("tags") or "").split())
        if "equipment" not in tags or "countermeasure" not in tags:
            continue

        ware_id = ware.get("id")

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
    for ware in iter_ware_elements(paths):
        if ware.get("id") != "crew":
            continue

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


def parse_thruster_macros(macro_dir: Path) -> dict[str, dict]:
    """Every thruster macro in `macro_dir` (THRUSTERS_MACRO_DIR -- see
    thruster_macro_jobs() in extract_game_data.py), keyed by the macro's own
    `name` attribute -- exactly the string thrusters_base.macro already
    carries. Unlike bullets_base's many-to-one join, this is a clean 1:1
    match (one macro per thrusters_base row, confirmed: 18 macro files, 18
    thrusters_base rows), so parse_thruster_wares() merges these straight
    onto its own rows rather than this living as a separate joined table.

    Real per-mk RCS thrust stats -- `strafe` (lateral/vertical translation
    thrust) plus `pitch`/`yaw`/`roll` (rotation thrust) -- see the
    "Thrusters" section of this module's own docstring for how these were
    found despite thrusters having no hardpoint-mount connection.
    """
    macros = {}
    for macro_path in sorted(macro_dir.glob("*.xml")):
        macro_el = ET.parse(macro_path).getroot().find("macro")
        if macro_el is None:
            continue
        macro_name = macro_el.get("name")
        properties = macro_el.find("properties")
        thrust_el = properties.find("thrust") if properties is not None else None
        macros[macro_name] = {
            "thrust_strafe": _float_attr(thrust_el, "strafe"),
            "thrust_pitch": _float_attr(thrust_el, "pitch"),
            "thrust_yaw": _float_attr(thrust_el, "yaw"),
            "thrust_roll": _float_attr(thrust_el, "roll"),
        }
    return macros


def parse_thruster_wares(paths: list[Path], thruster_macros: dict[str, dict]) -> list[dict]:
    """Build thrusters_base's rows: one per ware tagged "equipment" plus
    "thruster". Name/price/production live on equipment_wares_base instead
    (parse_equipment_wares already covers the "thruster" tag via
    EQUIPMENT_TYPE_TAGS) -- this only produces the type-specific columns,
    same division of labor as engines_base/shields_base/weapons_base/
    turrets_base vs. equipment_wares_base.

    Unlike those four, thrusters have no hardpoint-mount connection to look
    up size/compatibility from, and no <properties> block on the WARE
    itself to read mk from either. But their ware ids already fully encode
    the only per-ware facts that would otherwise come from that connection:
    size, class ("allround"/"combat" -- a player playstyle choice, not a
    tier), and mk (e.g. "thruster_gen_m_combat_01_mk2") -- so those are
    recovered straight from the ware_id via THRUSTER_WARE_RE instead.
    `compatibility` is always THRUSTER_COMPATIBILITY (see its own comment)
    since the game data has no per-thruster faction/tier lock at all.

    `thruster_macros` (parse_thruster_macros()'s own return value) IS a
    real per-ware macro lookup, keyed by `macro` -- see this function's own
    "Thrusters" docstring section for why that's a separate parse step
    rather than folded in here directly.
    """
    rows = []
    for ware in iter_ware_elements(paths):
        tags = (ware.get("tags") or "").split()
        if "equipment" not in tags or "thruster" not in tags:
            continue

        ware_id = ware.get("id")

        match = THRUSTER_WARE_RE.match(ware_id)
        if not match:
            print(f"WARNING: thruster ware id '{ware_id}' doesn't match the expected pattern, skipping")
            continue
        size, thruster_class, mk = match.groups()

        component_el = ware.find("component")
        macro = component_el.get("ref") if component_el is not None else None
        macro_stats = thruster_macros.get(macro, {})
        rows.append(
            {
                "ware_id": ware_id,
                "macro": macro,
                "mk": int(mk),
                "thruster_class": thruster_class,
                "size": size,
                "compatibility": THRUSTER_COMPATIBILITY,
                "thrust_strafe": macro_stats.get("thrust_strafe"),
                "thrust_pitch": macro_stats.get("thrust_pitch"),
                "thrust_yaw": macro_stats.get("thrust_yaw"),
                "thrust_roll": macro_stats.get("thrust_roll"),
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
    for ware in iter_ware_elements(paths):
        tags = (ware.get("tags") or "").split()
        if "equipment" not in tags or "software" not in tags:
            continue

        ware_id = ware.get("id")

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
                # Design race(s), raw and unsplit (e.g. "argon", or rarely
                # "argon teladi") -- a passenger key like "name_ref"
                # elsewhere in this pipeline, consumed by
                # build_maker_race_rows() in main(), never written to this
                # table's own CSV (not in TURRET/ENGINE/SHIELD/
                # WEAPON_FIELDNAMES -- the real per-race data lives in the
                # maker_races join table instead).
                "makerrace": identification.get("makerrace") if identification is not None else None,
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


def parse_bullets(macro_dir: Path) -> list[dict]:
    """Every weapon/turret projectile macro in `macro_dir` (BULLETS_MACRO_DIR --
    see bullet_macro_jobs() in extract_game_data.py), keyed by the macro's own
    `name` attribute -- the exact same string weapons_base.bullet_class/
    turrets_base.bullet_class already carry, confirmed a clean many-to-one
    join (many weapons/turrets legitimately share one bullet macro; every
    weapon/turret has exactly one bullet_class). 8 further bullet_class
    values point to missile macros instead (dumbfire/torpedo-style
    "weapons") and are deliberately not covered here -- those are already
    real rows in missiles_base.

    Unlike missiles/deployables, a bullet isn't itself a ware at all (no
    wares.xml entry, no price, no name) -- it's purely a projectile
    definition referenced BY a ware. So there's no "ware_id"/name_ref/price
    parsing step here the way parse_missile_wares() has -- just the raw
    combat stats, one row per real macro file.

    `damage_value` is the main/base damage; `damage_shield` and
    `damage_hull` are optional additional type-specific bonuses that
    sometimes ride alongside it (e.g. ion weapons: a small `value` plus a
    much larger `shield`-specific bonus) -- never a replacement for
    `damage_value`, confirmed present together on every sampled case.
    `reload_rate` (shots/sec) and `reload_time` (sec/shot) are two
    different, mutually-exclusive attribute names different bullet
    variants use for the same "how often does this fire" concept -- both
    columns exist, only one is ever populated per row. `weapon_system` is
    the same real page-1040 "Weapon Systems" vocabulary already resolved
    for missiles_base (see MISSILE_WEAPON_SYSTEM_NAME_REF) -- e.g.
    "weapon_standard" -- not yet resolved to a display name here.
    """
    rows = []
    seen_bullet_classes: set[str] = set()
    for macro_path in sorted(macro_dir.glob("*.xml")):
        macro_el = ET.parse(macro_path).getroot().find("macro")
        if macro_el is None:
            continue
        bullet_class = macro_el.get("name")
        if bullet_class in seen_bullet_classes:
            # A real (if rare) copy-paste artifact in the game's own files --
            # confirmed once: bullet_ter_turret_s_laser_01_mk1_macro.xml's
            # own <macro name="..."/> says "_m_", not "_s_", colliding with
            # the real M-turret file. Neither weapons_base nor turrets_base
            # actually references either name for that specific case, so
            # this is a genuine dead/unused duplicate, not a real
            # weapon/turret losing its damage data -- same "skip and warn"
            # handling iter_ware_elements() already uses for a duplicate
            # ware id.
            print(f"WARNING: duplicate bullet_class '{bullet_class}' (in {macro_path.name}), skipping")
            continue
        seen_bullet_classes.add(bullet_class)

        properties = macro_el.find("properties")

        bullet_el = properties.find("bullet") if properties is not None else None
        heat_el = properties.find("heat") if properties is not None else None
        reload_el = properties.find("reload") if properties is not None else None
        damage_el = properties.find("damage") if properties is not None else None
        ammunition_el = properties.find("ammunition") if properties is not None else None
        weapon_el = properties.find("weapon") if properties is not None else None
        areadamage_el = properties.find("areadamage") if properties is not None else None

        rows.append(
            {
                "bullet_class": bullet_class,
                "damage_value": _float_attr(damage_el, "value"),
                "damage_shield": _float_attr(damage_el, "shield"),
                "damage_hull": _float_attr(damage_el, "hull"),
                "damage_repair": _float_attr(damage_el, "repair"),
                "damage_shielddisruption": _float_attr(damage_el, "shielddisruption"),
                "bullet_speed": _float_attr(bullet_el, "speed"),
                "bullet_lifetime": _float_attr(bullet_el, "lifetime"),
                "bullet_range": _float_attr(bullet_el, "range"),
                "bullet_amount": _int_attr(bullet_el, "amount"),
                "bullet_barrelamount": _int_attr(bullet_el, "barrelamount"),
                "reload_rate": _float_attr(reload_el, "rate"),
                "reload_time": _float_attr(reload_el, "time"),
                "heat_value": _float_attr(heat_el, "value"),
                "heat_initial": _float_attr(heat_el, "initial"),
                "ammunition_value": _int_attr(ammunition_el, "value"),
                "ammunition_reload": _float_attr(ammunition_el, "reload"),
                "weapon_system": weapon_el.get("system") if weapon_el is not None else None,
                "areadamage_value": _float_attr(areadamage_el, "value"),
                "areadamage_shield": _float_attr(areadamage_el, "shield"),
                "areadamage_shielddisruption": _float_attr(areadamage_el, "shielddisruption"),
                "areadamage_lifetime": _float_attr(areadamage_el, "lifetime"),
            }
        )
    return rows


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


def split_maker_races(raw: str | None) -> list[str]:
    """A macro's identification/@makerrace attribute is a space-separated
    token list, almost always one entry (e.g. "argon") but occasionally
    more than one -- confirmed exactly one real case in the current
    dataset, ship_gen_m_corvette_01 (the Envoy): makerrace="argon teladi".
    Order is preserved (not sorted) so build_maker_race_rows() can record
    which one was listed first via its own "ordinal" column.
    """
    return raw.split() if raw else []


def build_maker_race_rows(entities: list[dict], valid_race_ids: set[str]) -> list[dict]:
    """One row per (ware_id, race_id) pair across every ship/turret/engine/
    shield/weapon whose macro carries a real identification/@makerrace --
    the golden-source replacement for the old ware_id-prefix guess
    (SHIP_RACE_PREFIX_TO_FACTION/ship_owner_faction(), removed). Each
    `entity` dict just needs "ware_id" and "makerrace" (the raw, unsplit
    attribute string -- see split_maker_races()) -- ships carry it via
    analyze_ship_components()'s own "makerrace" key, turrets/engines/
    shields/weapons via parse_equipment_component_wares()'s "makerrace" key.

    A token that doesn't match any real races.xml id is dropped with a
    warning rather than trusted blindly -- this is exactly the kind of
    input this app can't fully control once a mod is generating its own
    makerrace values, so a garbage token degrades to "this entity has one
    fewer recognized race" instead of polluting maker_races with a
    dangling id nothing else in the DB recognizes.

    Missiles, deployables, thrusters, and software have no
    identification/@makerrace at all in the base game (confirmed by
    inspection -- no <properties> block for thrusters/software to begin
    with; missiles/deployables have <identification> but never a
    makerrace attribute on it), so they're not passed in here and simply
    have no maker_races rows -- same as the handful of raceless drone/
    utility ships (see load_macro_data()'s own docstring note).
    """
    rows = []
    for entity in entities:
        for ordinal, race_id in enumerate(split_maker_races(entity.get("makerrace"))):
            if race_id not in valid_race_ids:
                print(
                    f"WARNING: {entity['ware_id']}: makerrace token '{race_id}' doesn't match any "
                    "real race id -- skipped"
                )
                continue
            rows.append({"ware_id": entity["ware_id"], "race_id": race_id, "ordinal": ordinal})
    return rows


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

    # The ship's own real design-race attribute -- e.g. makerrace="argon",
    # or the rare space-separated multi-value case, makerrace="argon
    # teladi" (the Envoy, ship_gen_m_corvette_01) -- golden-source
    # replacement for the old ware_id-prefix guess (see
    # build_maker_race_rows() below for where this is split/validated
    # against real races.xml ids). Raw and unsplit here; None for the
    # handful of ships with no <identification> makerrace attribute at all
    # (confirmed: always drones/utility ships with no real design lineage,
    # e.g. the transdrone/transport drones -- not a parsing gap).
    result["makerrace"] = identification_el.get("makerrace") if identification_el is not None else None

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

    # Hull-wide multipliers applied on top of whatever's actually mounted --
    # confirmed real in-game (not dead data): a <weapon heat="X"/> scales
    # every mounted weapon's own heat generation, <shield capacity="X"
    # rechargerate="X" rechargedelay="X"/> scales every mounted shield's own
    # numbers. Only present on a small minority of ships at all (~8% for
    # weapon heat, ~3% for shield -- confirmed by inspection across every
    # ship macro); absence means an implicit, unmodified 1.0, not "unknown",
    # so every ship gets a real value here, never None.
    modifiers_el = properties.find("modifiers")
    weapon_mod_el = modifiers_el.find("weapon") if modifiers_el is not None else None
    shield_mod_el = modifiers_el.find("shield") if modifiers_el is not None else None
    result["weapon_heat_modifier"] = _float_attr(weapon_mod_el, "heat") or 1.0
    result["shield_capacity_modifier"] = _float_attr(shield_mod_el, "capacity") or 1.0
    result["shield_rechargerate_modifier"] = _float_attr(shield_mod_el, "rechargerate") or 1.0
    result["shield_rechargedelay_modifier"] = _float_attr(shield_mod_el, "rechargedelay") or 1.0

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


# Docksize tag (see dock_macro_jobs() in extract_game_data.py) -> the same
# short size code used throughout this app (ships_base.size, SIZE_TOKENS,
# etc.). A dockingbay-class macro's own <docksize tags="..."/> can carry a
# second, unrelated tag alongside the size one (e.g. "dock_xs spacesuit"
# on dock_gen_xs_ship_01_macro) -- only the "dock_<size>" token is ever
# meaningful here.
DOCK_SIZE_TAG_TO_CODE = {
    "dock_xs": "xs",
    "dock_s": "s",
    "dock_m": "m",
    "dock_l": "l",
    "dock_xl": "xl",
}


def index_dock_macros() -> dict[str, tuple[str, Path]]:
    """{macro name -> (class_value, path)} for every file dock_macro_jobs()
    (extract_game_data.py) extracted -- flat, not sorted into per-class
    subfolders the way index_ship_files() sorts ship macros/components,
    since there's no equivalent convention worth building for only a
    couple hundred files. Includes some station-only dockarea/dockingbay
    entries dock_macro_jobs() couldn't cleanly filter out at extraction
    time -- harmless, parse_ship_docks() below only ever looks up a name a
    real ship's own macro actually references.
    """
    index: dict[str, tuple[str, Path]] = {}
    if not DOCK_MACROS_DIR.exists():
        return index
    for path in DOCK_MACROS_DIR.glob("*.xml"):
        macro_el = ET.parse(path).getroot().find("macro")
        if macro_el is None:
            continue
        name = macro_el.get("name")
        if name:
            index[name] = (macro_el.get("class"), path)
    return index


def _dockingbay_stats(path: Path) -> tuple[str | None, bool, int]:
    """For one dockingbay-class macro: (size_code, is_storage, capacity).

    is_storage is this dock's own <dock storage="1"/> flag -- true means it
    counts toward ship-storage capacity (an internal hangar bay a ship can
    be stored/hidden inside, see shipstorage_gen_* macros), false means it
    counts as one external docking point instead (a visible port another
    ship physically attaches to, see dockingbay_arg_*/dock_gen_* macros).

    capacity is <dock capacity="N"/> when present (every real storage-type
    dock has one), otherwise 1 -- a plain external dock has no capacity
    attribute at all since it's inherently a single slot; each of its
    *connections* (see parse_ship_docks()) is what actually multiplies the
    count, not this attribute.
    """
    macro_el = ET.parse(path).getroot().find("macro")
    properties = macro_el.find("properties") if macro_el is not None else None
    if properties is None:
        return None, False, 0

    docksize_el = properties.find("docksize")
    size_code = None
    if docksize_el is not None:
        for tag in (docksize_el.get("tags") or "").split():
            if tag in DOCK_SIZE_TAG_TO_CODE:
                size_code = DOCK_SIZE_TAG_TO_CODE[tag]
                break

    dock_el = properties.find("dock")
    is_storage = dock_el is not None and dock_el.get("storage") == "1"
    capacity = int(float(dock_el.get("capacity"))) if dock_el is not None and dock_el.get("capacity") else 1
    return size_code, is_storage, capacity


def parse_ship_docks(
    macro_path: Path,
    macro_index: dict[str, tuple[str, Path]],
    dock_index: dict[str, tuple[str, Path]],
) -> dict:
    """Cargo hold capacity/type plus external-dock and ship-storage
    (hangar) capacity, both broken down by size -- read from the ship's
    own top-level macro <connections> (con_storage.../con_dockarea_.../
    con_dock_.../con_shipstorage_...), NOT the per-hardpoint <connections>
    in its *component* file that parse_component_slots() reads -- these
    are two genuinely separate <connections> blocks in two separate files.

    Cargo: resolved via `macro_index` (the same one analyze_ship_components()
    already uses for the ship macro itself) since a ship's own cargo-hold
    macro is class="storage" and already lives in storage_macros/,
    alongside every other real ship-class macro -- no separate index
    needed. At most one per ship (confirmed: every real ship has either
    zero or exactly one storage_* connection, never more).

    Docks/ship-storage: resolved via `dock_index` (see index_dock_macros())
    instead, since dockarea/dockingbay/shipstorage macros live under a
    completely different in-catalog path with no ship-class concept at
    all. A dockarea-class connection target itself carries no size/
    capacity data directly -- it's a thin wrapper around one or more inner
    <connection> entries of its own, each pointing to a real dockingbay-
    class macro (see dock_macro_jobs()'s docstring); a dock_gen_*/
    shipstorage_gen_* connection target is already dockingbay-class
    directly, no unwrapping needed. Every resolved dockingbay-class macro
    is classified by _dockingbay_stats() and folded into `docks`/
    `ship_storage`, keyed by its own real docksize -- never guessed from
    any macro's filename (confirmed necessary: e.g.
    dockarea_arg_xl_builder_01_macro's own inner docks are a mix of M and
    S, despite "xl" in its own name referring to the ship class this dock
    area belongs to, not the size of ship it docks).

    Returns {"cargo_capacity": int, "cargo_type": str, "docks": {size:
    count}, "ship_storage": {size: count}} -- "docks"/"ship_storage" only
    contain keys for sizes actually present on this ship, so callers
    should use .get(size, 0).
    """
    result: dict = {"cargo_capacity": 0, "cargo_type": "", "docks": {}, "ship_storage": {}}

    macro_el = ET.parse(macro_path).getroot().find("macro")
    connections_el = macro_el.find("connections") if macro_el is not None else None
    if connections_el is None:
        return result

    for conn in connections_el.findall("connection"):
        macro_ref_el = conn.find("macro")
        target_name = macro_ref_el.get("ref") if macro_ref_el is not None else None
        if not target_name:
            continue

        cargo_lookup = macro_index.get(target_name)
        if cargo_lookup is not None and cargo_lookup[0] == "storage":
            cargo_properties = ET.parse(cargo_lookup[1]).getroot().find("macro").find("properties")
            cargo_el = cargo_properties.find("cargo") if cargo_properties is not None else None
            if cargo_el is not None:
                result["cargo_capacity"] = int(float(cargo_el.get("max"))) if cargo_el.get("max") else 0
                result["cargo_type"] = cargo_el.get("tags") or ""
            continue

        dock_lookup = dock_index.get(target_name)
        if dock_lookup is None:
            continue
        class_value, path = dock_lookup

        inner_paths: list[Path] = []
        if class_value == "dockarea":
            area_el = ET.parse(path).getroot().find("macro")
            area_connections = area_el.find("connections") if area_el is not None else None
            if area_connections is not None:
                for inner_conn in area_connections.findall("connection"):
                    inner_macro_el = inner_conn.find("macro")
                    inner_name = inner_macro_el.get("ref") if inner_macro_el is not None else None
                    inner_lookup = dock_index.get(inner_name) if inner_name else None
                    if inner_lookup is not None:
                        inner_paths.append(inner_lookup[1])
        elif class_value == "dockingbay":
            inner_paths.append(path)

        for inner_path in inner_paths:
            size_code, is_storage, capacity = _dockingbay_stats(inner_path)
            if size_code is None:
                continue
            bucket = result["ship_storage"] if is_storage else result["docks"]
            bucket[size_code] = bucket.get(size_code, 0) + capacity

    return result


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


def analyze_ship_components(
    ship: dict,
    macro_index: dict[str, tuple[str, Path]],
    component_index: dict[str, tuple[str, Path]],
    dock_index: dict[str, tuple[str, Path]],
) -> dict:
    """Unlike the old ware_id-prefix-guessed `size` this used to take as an
    input parameter, "size"/"ship_class" are now *outputs*: this function
    has to locate and open the ship's own macro before it can know either
    (the macro's own <macro class="..."/> attribute is the real source --
    see SHIP_CLASS_TO_SIZE_CODE) -- so both start out None in `result` and
    only get filled in once that lookup succeeds. macro_index/
    component_index (see index_ship_files()) let that lookup happen by
    macro/component name alone, no assumed size/folder needed to find the
    file in the first place. dock_index (see index_dock_macros()) is the
    equivalent lookup for parse_ship_docks()'s own dockarea/dockingbay/
    shipstorage macro resolution.
    """
    result: dict = {
        "slot_counts": {},
        "groups": [],
        "size": None,
        "ship_class": None,
        "makerrace": None,
        "missile_capacity": 0,
        "drone_capacity": 0,
        "ship_type": None,
        "purpose": None,
        "icon": None,
        "hull": None,
        "crew": None,
        "traveldrivestability": 0,
        "weapon_heat_modifier": 1.0,
        "shield_capacity_modifier": 1.0,
        "shield_rechargerate_modifier": 1.0,
        "shield_rechargedelay_modifier": 1.0,
        "jerk_fields": {},
        "physics_fields": {},
        "steeringcurve": "",
        "cargo_capacity": 0,
        "cargo_type": "",
        "docks": {},
        "ship_storage": {},
    }

    if not ship["macro"]:
        print(f"WARNING: no macro ref for {ship['ware_id']}, skipping component analysis")
        return result

    macro_lookup = macro_index.get(ship["macro"])
    if macro_lookup is None:
        print(f"WARNING: macro file not found for {ship['ware_id']} (looked for '{ship['macro']}' in {SHIPS_DIR})")
        return result
    ship_class, macro_path = macro_lookup
    result["ship_class"] = ship_class

    size = SHIP_CLASS_TO_SIZE_CODE.get(ship_class)
    if size is None:
        print(
            f"WARNING: {ship['ware_id']}: unrecognized ship class '{ship_class}' -- "
            "add it to SHIP_CLASS_TO_SIZE_CODE, skipping component analysis"
        )
        return result
    result["size"] = size

    # Thrusters have no <connection> hardpoint in the component file at all
    # (see the "Thrusters" section of this module's docstring) -- every ship
    # just gets exactly one, sized to match its own hull, so it's synthesized
    # here rather than discovered by parse_component_slots below. Added as
    # soon as `size` itself is known (now only true once the macro lookup
    # above has already succeeded, unlike before) rather than any earlier,
    # since there's no size to synthesize it with otherwise.
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

    dock_data = parse_ship_docks(macro_path, macro_index, dock_index)
    result["cargo_capacity"] = dock_data["cargo_capacity"]
    result["cargo_type"] = dock_data["cargo_type"]
    result["docks"] = dock_data["docks"]
    result["ship_storage"] = dock_data["ship_storage"]

    macro_data = load_macro_data(macro_path)
    result["makerrace"] = macro_data.get("makerrace")
    result["missile_capacity"] = macro_data.get("missile_capacity", 0)
    result["drone_capacity"] = macro_data.get("drone_capacity", 0)
    result["ship_type"] = macro_data.get("ship_type")
    result["purpose"] = macro_data.get("purpose")
    result["icon"] = macro_data.get("icon")
    result["hull"] = macro_data.get("hull")
    result["crew"] = macro_data.get("crew")
    result["traveldrivestability"] = macro_data.get("traveldrivestability", 0)
    result["weapon_heat_modifier"] = macro_data.get("weapon_heat_modifier", 1.0)
    result["shield_capacity_modifier"] = macro_data.get("shield_capacity_modifier", 1.0)
    result["shield_rechargerate_modifier"] = macro_data.get("shield_rechargerate_modifier", 1.0)
    result["shield_rechargedelay_modifier"] = macro_data.get("shield_rechargedelay_modifier", 1.0)
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

    component_lookup = component_index.get(component_ref)
    if component_lookup is None:
        print(f"WARNING: component file not found for {ship['ware_id']} (looked for '{component_ref}' in {SHIPS_DIR})")
        return result
    _component_class, component_path = component_lookup

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
    sql = f"""DROP TABLE IF EXISTS localized_race_shortnames;
DROP TABLE IF EXISTS localized_race_names;
DROP TABLE IF EXISTS localized_shortnames;
DROP TABLE IF EXISTS localized_strings;
DROP TABLE IF EXISTS maker_races;
DROP TABLE IF EXISTS crew_roles;
DROP TABLE IF EXISTS build_methods;
DROP TABLE IF EXISTS ship_types;
DROP TABLE IF EXISTS cargo_types;
DROP TABLE IF EXISTS missile_weapon_systems;
DROP TABLE IF EXISTS compatibility_types;
DROP TABLE IF EXISTS ammunition_compatibility_types;
DROP TABLE IF EXISTS thruster_classes;
DROP TABLE IF EXISTS deployable_types;
DROP TABLE IF EXISTS purposes;
DROP TABLE IF EXISTS races;
DROP TABLE IF EXISTS factions;
DROP TABLE IF EXISTS source_versions;
DROP TABLE IF EXISTS flight_model;
DROP TABLE IF EXISTS ship_component_groups;
DROP TABLE IF EXISTS production_wares;
DROP TABLE IF EXISTS turrets_base;
DROP TABLE IF EXISTS engines_base;
DROP TABLE IF EXISTS shields_base;
DROP TABLE IF EXISTS weapons_base;
DROP TABLE IF EXISTS thrusters_base;
DROP TABLE IF EXISTS software_base;
DROP TABLE IF EXISTS missiles_base;
DROP TABLE IF EXISTS bullets_base;
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
    -- Hull-wide multipliers applied on top of whatever's actually mounted --
    -- confirmed real in-game (not dead data): a ship's own <modifiers>
    -- <weapon heat="X"/> scales every mounted weapon's own heat generation,
    -- <shield capacity="X" rechargerate="X" rechargedelay="X"/> scales every
    -- mounted shield's own numbers. See load_macro_data()'s own docstring.
    -- Only present on a small minority of ships at all -- absence means an
    -- implicit, unmodified 1.0, not "unknown", so every ship gets a real
    -- value here, never NULL.
    weapon_heat_modifier REAL,
    shield_capacity_modifier REAL,
    shield_rechargerate_modifier REAL,
    shield_rechargedelay_modifier REAL,
    missile_capacity INTEGER,
    drone_capacity INTEGER,
    -- Ship's own cargo hold, read from its storage_*_macro's <cargo max=""
    -- tags=""/> (see parse_ship_docks()) -- cargo_type is the raw tags
    -- string (e.g. "container", "liquid", "solid", "container solid"), 0/""
    -- for ships with no cargo hold at all (most combat ships).
    cargo_capacity INTEGER,
    cargo_type TEXT,
    -- External docking points and internal ship-storage (hangar) capacity,
    -- both by docked-ship size -- see parse_ship_docks()'s own docstring
    -- for the real distinction between the two (a dock is a single visible
    -- attach point; ship storage is how many ships of that size an L/XL
    -- ship can carry stored inside it, e.g. a carrier's fighter bay).
    s_docks INTEGER,
    m_docks INTEGER,
    s_ship_storage INTEGER,
    m_ship_storage INTEGER,
    size TEXT,
    -- The raw class="..." value this ship's own macro carried (e.g.
    -- "ship_l"), before SHIP_CLASS_TO_SIZE_CODE's mapping to `size` above
    -- -- kept alongside it for the follow-up localization investigation
    -- (see that dict's own docstring), not used by anything else yet.
    ship_class TEXT,
    shields INTEGER,
    engines INTEGER,
    weapons INTEGER{bonus_weapon_col_defs},
    missile_launchers INTEGER,
    {turret_col_defs},
    shields_bonus_m INTEGER
);

-- volume/transport are real per-ware cargo stats straight off the <ware>
-- element (see parse_economy_wares()'s own docstring): `volume` is how
-- much cargo-hold space one unit takes, `transport` is which hold type it
-- needs -- "container"/"liquid"/"solid" (matching cargo_types.cargo_type_id)
-- plus a handful of real "condensate" outliers cargo_types has no row for,
-- kept as a raw string rather than forced through a join that would drop
-- them. Deliberately not parsed for any other ware kind (ships/equipment/
-- missiles/drones/countermeasures/crew) -- they all carry the same
-- attribute pair in wares.xml too, but it's always a meaningless flat
-- "volume=1, transport=<its own type name>" placeholder there, confirmed
-- by inspection, not a real cargo stat.
CREATE TABLE economy_wares_base (
    ware_id TEXT PRIMARY KEY,
    name TEXT,
    price_min INTEGER,
    price_avg INTEGER,
    price_max INTEGER,
    leaf_ware BOOLEAN NOT NULL DEFAULT 0,
    volume INTEGER,
    transport TEXT
);

CREATE TABLE equipment_wares_base (
    ware_id TEXT PRIMARY KEY,
    name TEXT,
    equipment_type TEXT NOT NULL,
    missile_launcher BOOLEAN NOT NULL DEFAULT 0,
    -- Comma-joined faction ids, same real <owner faction="..."/> element
    -- and same shape as ships_base.owners (see parse_equipment_wares()'s
    -- own docstring) -- empty for the handful of genuinely faction-
    -- agnostic wares (every thruster, plus a few EVA-spacesuit items).
    owners TEXT,
    -- Same real Universal/Terran/Xenon/Boron/Closed Loop vocabulary as
    -- ships_base.production_method (page 20206 "Ware Production Methods"),
    -- taken from this ware's own first <production> block -- genuinely
    -- meaningful for engine/shield/weapon/turret (confirmed real
    -- diversity, not always "Universal"); every thruster's own first
    -- production block is always "Universal" (no real variation), so this
    -- column is present but not offered as a filter for that type -- see
    -- app.js's COMPONENT_FILTER_GROUPS.
    production_method TEXT,
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

-- Unlike turrets/engines/shields/weapons, thrusters have no hardpoint-mount
-- connection to source mk/size/compatibility from -- all three are recovered
-- from the ware_id itself (see parse_thruster_wares). No owners/hull columns
-- either: no faction lock, no <properties><hull> block to read. thruster_class
-- ("allround"/"combat") is a playstyle choice, not a tier -- both are equally
-- mountable on a given size, unlike compatibility on other equipment types.
-- thrust_* IS real per-mk macro data (see parse_thruster_macros() and this
-- module's own "Thrusters" docstring section for how a probe found these
-- macros living alongside the engine ones despite thrusters having no mount
-- connection): strafe is lateral/vertical translation thrust, pitch/yaw/roll
-- are rotation thrust.
CREATE TABLE thrusters_base (
    ware_id TEXT PRIMARY KEY,
    macro TEXT,
    mk INTEGER,
    thruster_class TEXT,
    size TEXT,
    compatibility TEXT,
    thrust_strafe REAL,
    thrust_pitch REAL,
    thrust_yaw REAL,
    thrust_roll REAL,
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

-- Weapon/turret projectile definitions -- what weapons_base.bullet_class/
-- turrets_base.bullet_class actually resolves to (join on bullet_class ==
-- bullet_class), see parse_bullets()' own docstring for the full picture
-- (many-to-one from weapon/turret to bullet, one row here per real bullet
-- macro file, no wares.xml entry/price/name of its own since a bullet
-- isn't a purchasable ware). damage_value is the main/base damage;
-- damage_shield/damage_hull are optional type-specific bonuses that
-- sometimes ride alongside it (never a replacement). reload_rate (shots/
-- sec) and reload_time (sec/shot) are mutually exclusive per row -- two
-- different attribute names the game itself uses for the same concept
-- depending on bullet variant. areadamage_* is only populated for
-- explosive/AOE bullets (flak etc).
CREATE TABLE bullets_base (
    bullet_class TEXT PRIMARY KEY,
    damage_value REAL,
    damage_shield REAL,
    damage_hull REAL,
    damage_repair REAL,
    damage_shielddisruption REAL,
    bullet_speed REAL,
    bullet_lifetime REAL,
    bullet_range REAL,
    bullet_amount INTEGER,
    bullet_barrelamount INTEGER,
    reload_rate REAL,
    reload_time REAL,
    heat_value REAL,
    heat_initial REAL,
    ammunition_value INTEGER,
    ammunition_reload REAL,
    weapon_system TEXT,
    areadamage_value REAL,
    areadamage_shield REAL,
    areadamage_shielddisruption REAL,
    areadamage_lifetime REAL
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

CREATE TABLE source_versions (
    source_id TEXT PRIMARY KEY,
    source_name TEXT,
    source_version TEXT
);

CREATE TABLE factions (
    faction_id TEXT PRIMARY KEY,
    faction_name TEXT,
    faction_shortname TEXT
);

CREATE TABLE races (
    race_id TEXT PRIMARY KEY,
    race_name TEXT,
    race_shortname TEXT
);

CREATE TABLE purposes (
    purpose_id TEXT PRIMARY KEY,
    purpose_name TEXT
);

-- Every real ship_type value actually present in ships_base, with a real
-- display name where one is known -- see parse_ship_types()/
-- SHIP_TYPE_NAME_REF's own docstrings (both above, in this same module).
CREATE TABLE ship_types (
    ship_type_id TEXT PRIMARY KEY,
    ship_type_name TEXT
);

-- Every real cargo-type token actually present across ships_base.cargo_type
-- (space-separated, see that column's own docstring), with a real display
-- name where one is known -- see parse_cargo_types()/CARGO_TYPE_NAME_REF's
-- own docstrings (both above, in this same module).
CREATE TABLE cargo_types (
    cargo_type_id TEXT PRIMARY KEY,
    cargo_type_name TEXT
);

-- Every real weapon_system token actually present across missiles_base.
-- weapon_system, with a real display name where one is known -- see
-- parse_missile_weapon_systems()/MISSILE_WEAPON_SYSTEM_NAME_REF's own
-- docstrings (both above, in this same module).
CREATE TABLE missile_weapon_systems (
    weapon_system_id TEXT PRIMARY KEY,
    weapon_system_name TEXT
);

-- Every real compatibility tag actually present across engines_base/
-- shields_base/weapons_base/turrets_base/thrusters_base/missiles_base.
-- compatibility (each comma-joined, see that column's own docstring),
-- with a real display name where one is known -- see
-- parse_compatibility_types()/COMPATIBILITY_NAME_REF's own docstrings
-- (both above, in this same module).
CREATE TABLE compatibility_types (
    compatibility_type_id TEXT PRIMARY KEY,
    compatibility_type_name TEXT
);

-- Every real ammunition-compatibility tag actually present across
-- missiles_base.compatibility and weapons_base/turrets_base.
-- ammunition_tags (each comma-joined) -- a distinct vocabulary from
-- compatibility_types above despite the similarly-named source columns,
-- see parse_ammunition_compatibility_types()/AMMUNITION_TYPE_NAME_REF's
-- own docstrings (both above, in this same module).
CREATE TABLE ammunition_compatibility_types (
    ammunition_compatibility_type_id TEXT PRIMARY KEY,
    ammunition_compatibility_type_name TEXT
);

-- Every real thruster_class value actually present across thrusters_base.
-- thruster_class ("allround"/"combat" -- a player playstyle choice, not a
-- tier), with a real display name where one is known -- see
-- parse_thruster_classes()/THRUSTER_CLASS_NAME_REF's own docstrings (both
-- above, in this same module).
CREATE TABLE thruster_classes (
    thruster_class_id TEXT PRIMARY KEY,
    thruster_class_name TEXT
);

-- Every real deployable_type value actually present across
-- deployables_base.deployable_type ("satellite"/"resourceprobe"/"mine"/
-- "lasertower"/"navbeacon"), with a real display name where one is known
-- -- see parse_deployable_types()/DEPLOYABLE_TYPE_NAME_REF's own
-- docstrings (both above, in this same module).
CREATE TABLE deployable_types (
    deployable_type_id TEXT PRIMARY KEY,
    deployable_type_name TEXT
);

-- Every real production method (see BUILD_METHODS/parse_build_methods()
-- above). build_method_name is both the primary key and the base English
-- display value -- see parse_build_methods()'s own docstring for why this
-- table has no separate "_name" column the way ship_types/purposes do.
CREATE TABLE build_methods (
    build_method_name TEXT PRIMARY KEY
);

-- The two real internal crew-role codes (see CREW_ROLE_NAME_REF/
-- parse_crew_roles() above) with their own real display name.
CREATE TABLE crew_roles (
    crew_role_id TEXT PRIMARY KEY,
    crew_role_name TEXT
);

-- A ship/turret/engine/shield/weapon's own real design race(s) -- see
-- build_maker_race_rows() and this module's "Design race and race/faction
-- shortcodes" docstring section. Usually one row per ware_id, occasionally
-- more (e.g. ship_gen_m_corvette_01, the Envoy, has both an "argon" and a
-- "teladi" row) -- ordinal preserves the order makerrace listed them in.
CREATE TABLE maker_races (
    ware_id TEXT,
    race_id TEXT,
    ordinal INTEGER,
    PRIMARY KEY (ware_id, race_id),
    FOREIGN KEY (race_id) REFERENCES races (race_id)
);

CREATE TABLE localized_strings (
    ware_id TEXT,
    lang_id TEXT,
    text TEXT,
    PRIMARY KEY (ware_id, lang_id)
);

-- Same shape as localized_strings, but for faction_shortname specifically
-- (e.g. "YAK" for Yaki) rather than a display name -- kept as a separate
-- table since a faction needs two independently-localizable text fields
-- and localized_strings' schema only has room for one text column per
-- (ware_id, lang_id) pair. See this module's "Design race and race/faction
-- shortcodes" docstring section.
CREATE TABLE localized_shortnames (
    ware_id TEXT,
    lang_id TEXT,
    text TEXT,
    PRIMARY KEY (ware_id, lang_id)
);

-- race_name's own non-English coverage, kept in a dedicated table rather
-- than sharing localized_strings with factions/wares/ships -- several race
-- ids collide with a same-named faction id (e.g. "argon" is both), and
-- mixing the two in one shared keyspace was confirmed (via a live query)
-- to silently return the faction's translation for the race. See this
-- module's "Design race and race/faction shortcodes" docstring section.
CREATE TABLE localized_race_names (
    ware_id TEXT,
    lang_id TEXT,
    text TEXT,
    PRIMARY KEY (ware_id, lang_id)
);

-- race_shortname's own non-English coverage -- same isolation reasoning as
-- localized_race_names above, just for the shortcode field instead.
CREATE TABLE localized_race_shortnames (
    ware_id TEXT,
    lang_id TEXT,
    text TEXT,
    PRIMARY KEY (ware_id, lang_id)
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
            "weapon_heat_modifier",
            "shield_capacity_modifier",
            "shield_rechargerate_modifier",
            "shield_rechargedelay_modifier",
            "missile_capacity",
            "drone_capacity",
            "cargo_capacity",
            "cargo_type",
            "s_docks",
            "m_docks",
            "s_ship_storage",
            "m_ship_storage",
            "size",
            "ship_class",
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
                "weapon_heat_modifier": s["weapon_heat_modifier"],
                "shield_capacity_modifier": s["shield_capacity_modifier"],
                "shield_rechargerate_modifier": s["shield_rechargerate_modifier"],
                "shield_rechargedelay_modifier": s["shield_rechargedelay_modifier"],
                "missile_capacity": s["missile_capacity"],
                "drone_capacity": s["drone_capacity"],
                "cargo_capacity": s["cargo_capacity"],
                "cargo_type": s["cargo_type"],
                "s_docks": s["s_docks"],
                "m_docks": s["m_docks"],
                "s_ship_storage": s["s_ship_storage"],
                "m_ship_storage": s["m_ship_storage"],
                "size": s["size"] or "",
                "ship_class": s["ship_class"] or "",
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
    fieldnames = ["ware_id", "name", "price_min", "price_avg", "price_max", "leaf_ware", "volume", "transport"]
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
                    "volume": w["volume"] or "",
                    "transport": w["transport"] or "",
                }
            )
    return len(economy_wares)


def write_equipment_wares_csv(equipment_wares: list[dict], out_path: Path) -> int:
    fieldnames = [
        "ware_id",
        "name",
        "equipment_type",
        "missile_launcher",
        "owners",
        "production_method",
        "price_min",
        "price_avg",
        "price_max",
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for w in equipment_wares:
            # Same "first production block wins" convention write_ships_csv()
            # already uses for ships_base.production_method -- see this
            # module's "Design race and race/faction shortcodes" docstring
            # section and GET /api/components' own comment for why this is
            # real, meaningful data (Universal/Terran/Xenon/Boron/Closed
            # Loop) for engine/shield/weapon/turret, not ware-id parsing.
            primary_prod = w["productions"][0] if w["productions"] else None
            writer.writerow(
                {
                    "ware_id": w["ware_id"],
                    "name": w["name"],
                    "equipment_type": w["equipment_type"],
                    "missile_launcher": int(w["missile_launcher"]),
                    "owners": ",".join(w["owners"]),
                    "production_method": primary_prod["method_name"] if primary_prod else "",
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
    "ware_id", "macro", "mk", "bullet_class",
    "rotation_speed", "rotation_acceleration", "hull", "size", "compatibility",
    "ammunition_tags", "ammunition_capacity",
]
ENGINE_FIELDNAMES = [
    "ware_id", "macro", "mk",
    "boost_duration", "boost_recharge", "boost_thrust", "boost_acceleration",
    "boost_attack", "boost_release", "boost_coast",
    "travel_charge", "travel_thrust", "travel_attack", "travel_release",
    "thrust_forward", "thrust_reverse",
    "hull", "size", "compatibility",
]
SHIELD_FIELDNAMES = [
    "ware_id", "macro", "mk",
    "recharge_max", "recharge_rate", "recharge_delay", "recharge_disruptionstability",
    "hull", "size", "compatibility",
]
WEAPON_FIELDNAMES = [
    "ware_id", "macro", "mk", "bullet_class",
    "heat_overheat", "heat_cooldelay", "heat_coolrate", "heat_reenable", "heat_overheatcooldelay",
    "rotation_speed", "rotation_acceleration", "weapon_angle",
    "hull", "size", "compatibility",
    "ammunition_tags", "ammunition_capacity",
]
THRUSTER_FIELDNAMES = [
    "ware_id", "macro", "mk", "thruster_class", "size", "compatibility",
    "thrust_strafe", "thrust_pitch", "thrust_yaw", "thrust_roll",
]
SOFTWARE_FIELDNAMES = ["ware_id", "name", "category", "mk", "price_min", "price_avg", "price_max"]
MISSILE_FIELDNAMES = [
    "ware_id", "name", "macro", "price_min", "price_avg", "price_max",
    "ammunition_value", "ammunition_reload",
    "missile_amount", "missile_barrelamount", "missile_lifetime", "missile_range", "missile_guided",
    "explosiondamage_value", "explosiondamage_shielddisruption",
    "reload_time", "hull", "weapon_system", "countermeasure_resilience", "physics_mass",
    "lock_time", "lock_range", "compatibility",
]
BULLET_FIELDNAMES = [
    "bullet_class",
    "damage_value", "damage_shield", "damage_hull", "damage_repair", "damage_shielddisruption",
    "bullet_speed", "bullet_lifetime", "bullet_range", "bullet_amount", "bullet_barrelamount",
    "reload_rate", "reload_time",
    "heat_value", "heat_initial",
    "ammunition_value", "ammunition_reload",
    "weapon_system",
    "areadamage_value", "areadamage_shield", "areadamage_shielddisruption", "areadamage_lifetime",
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
SOURCE_VERSIONS_FIELDNAMES = ["source_id", "source_name", "source_version"]
FACTIONS_FIELDNAMES = ["faction_id", "faction_name", "faction_shortname"]
RACES_FIELDNAMES = ["race_id", "race_name", "race_shortname"]
PURPOSES_FIELDNAMES = ["purpose_id", "purpose_name"]
SHIP_TYPE_FIELDNAMES = ["ship_type_id", "ship_type_name"]
CARGO_TYPE_FIELDNAMES = ["cargo_type_id", "cargo_type_name"]
COMPATIBILITY_TYPE_FIELDNAMES = ["compatibility_type_id", "compatibility_type_name"]
AMMUNITION_COMPATIBILITY_TYPE_FIELDNAMES = ["ammunition_compatibility_type_id", "ammunition_compatibility_type_name"]
THRUSTER_CLASS_FIELDNAMES = ["thruster_class_id", "thruster_class_name"]
DEPLOYABLE_TYPE_FIELDNAMES = ["deployable_type_id", "deployable_type_name"]
MISSILE_WEAPON_SYSTEM_FIELDNAMES = ["weapon_system_id", "weapon_system_name"]
BUILD_METHOD_FIELDNAMES = ["build_method_name"]
CREW_ROLE_FIELDNAMES = ["crew_role_id", "crew_role_name"]
MAKER_RACES_FIELDNAMES = ["ware_id", "race_id", "ordinal"]
LOCALIZED_STRINGS_FIELDNAMES = ["ware_id", "lang_id", "text"]


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


def format_egosoft_build_version(raw: str) -> str:
    """Egosoft's own build-number convention is the public version times
    100, zero-padded to always show two decimal places (e.g. base game
    version.dat's "900" -> public "9.00", a hypothetical "750" -> "7.50")
    -- confirmed against the current public release (build 900 = the "9.00
    Empire Update", released 2026-06-10). Falls back to the raw string
    unchanged if it isn't a plain integer, rather than raising -- a
    defensive fallback only, since every real Egosoft version.dat/
    content.xml value seen so far has always been one.
    """
    try:
        return f"{int(raw) / 100:.2f}"
    except ValueError:
        return raw


def parse_factions(paths: list[Path], lang_table: dict) -> list[dict]:
    """Every real <faction id="..." name="{page,id}" .../> across
    factions_files()'s base+extension set, resolved to its display name --
    for the factions DB table backing the ship picker's owner-faction icon
    tooltips (see src/static/app.js) and a planned owner-faction filter.

    Each extension's own factions.xml is a <diff> patch, same convention as
    wares.xml -- but unlike iter_ware_elements() (which has to distinguish
    "new ware" <add sel="/wares"> blocks from "patch an existing ware"
    <add sel="/wares/ware[@id='...']"> blocks), a plain root.iter("faction")
    here is sufficient: every *actual* <faction id=... name=...> definition
    is a real <faction> element regardless of how deeply it's nested inside
    its own <add sel="/factions">, while every other per-extension patch in
    these files (relation/licence tweaks to an *existing* faction, e.g.
    <add sel="/factions/faction[@id='court']/relations">) only ever
    reaches into a faction by its `sel` path string, never by containing an
    actual nested <faction> tag itself -- so this can't accidentally
    mistake one of those for a real definition.

    First definition of a given id wins, across every file in `paths` in
    that list's own order -- covers factions_tim.xml's own guarded re-add
    of "terran" (if="not(//faction[@id='terran'])", to stay valid whether
    or not the Terran DLC is also installed) as a harmless duplicate,
    without needing to parse that guard condition at all.

    Factions with no name attribute at all (currently just "ownerless", a
    hidden placeholder/no-owner faction with no real in-game display
    string) fall back to a title-cased version of their own id.

    Each row also carries "ware_id" (the faction_id, under the name
    parse_localized_strings() actually looks for) and "name_ref" -- not
    real ships_base-style columns, just along for the ride so this same
    list can be passed straight into parse_localized_strings() alongside
    every other entity list in main(), giving factions the exact same
    non-English name coverage (localized_strings table) ships/wares
    already have. FACTIONS_FIELDNAMES doesn't include either key, so
    write_equipment_component_csv() silently ignores them when writing
    factions.csv itself -- same as how every other entity list's own
    "name_ref" never leaks into its own CSV either.

    "faction_shortname" (e.g. "YAK" for Yaki) is resolved from the
    faction's own shortname="{page,id}" attribute the exact same way as
    faction_name -- this row's own base-table value (English, same as
    faction_name). "shortname_ref" is the *unresolved* {page,id} ref,
    carried alongside "name_ref" so main() can pass this same list to
    parse_localized_strings() a second time (with ref_key="shortname_ref")
    to get faction_shortname's own non-English coverage into the separate
    localized_shortnames table -- see this module's "Design race and
    race/faction shortcodes" docstring section for why that's a second
    table rather than a second row per entity in localized_strings. Missing
    for the handful
    of hidden/internal factions with no shortname attribute at all (e.g.
    "ownerless", "civilian", "player") -- callers must treat that as
    legitimately absent, not a parsing bug.
    """
    by_id: dict[str, ET.Element] = {}
    for path in paths:
        root = ET.parse(path).getroot()
        for faction_el in root.iter("faction"):
            faction_id = faction_el.get("id")
            if faction_id and faction_id not in by_id:
                by_id[faction_id] = faction_el

    rows = []
    for faction_id, faction_el in sorted(by_id.items()):
        name_ref = faction_el.get("name")
        faction_name = resolve_ref_attr(name_ref, lang_table) if name_ref else faction_id.replace("_", " ").title()
        shortname_ref = faction_el.get("shortname")
        faction_shortname = resolve_ref_attr(shortname_ref, lang_table) if shortname_ref else None
        rows.append(
            {
                "faction_id": faction_id,
                "faction_name": faction_name,
                "faction_shortname": faction_shortname,
                "ware_id": faction_id,
                "name_ref": name_ref or "",
                "shortname_ref": shortname_ref or "",
            }
        )
    return rows


def parse_races(path: Path, lang_table: dict) -> list[dict]:
    """Every <race id="..." name="{page,id}" shortname="{page,id}" .../> in
    races.xml -- for the races DB table. A race's own id (e.g. "argon") is
    the same value every ship/turret/engine/shield/weapon's own
    identification/@makerrace attribute uses directly (see
    build_maker_race_rows()), so unlike the old ware_id-prefix approach
    this table is no longer a lookup key for *finding* a ship's race --
    only for display (race_name/race_shortname).

    Not every race carries every attribute: "drone" (a hidden placeholder
    race, tags="hidden", with no ships of its own) has no shortname at all
    -- callers must treat a missing race_shortname as legitimately absent,
    not a parsing bug.

    Same "ware_id"/"name_ref"/"shortname_ref" passenger keys as
    parse_factions() (see that function's own docstring), but race_name and
    race_shortname get their own dedicated localized_race_names/
    localized_race_shortnames tables rather than sharing factions' -- see
    this module's "Design race and race/faction shortcodes" docstring
    section for why (races and factions share some ids, e.g. "argon" is
    both, and mixing them into one shared keyspace was confirmed to
    silently return the wrong entity's translation).
    """
    root = ET.parse(path).getroot()
    rows = []
    for race_el in root.findall("race"):
        race_id = race_el.get("id")
        if not race_id:
            continue
        name_ref = race_el.get("name")
        race_name = resolve_ref_attr(name_ref, lang_table) if name_ref else race_id.replace("_", " ").title()
        shortname_ref = race_el.get("shortname")
        race_shortname = resolve_ref_attr(shortname_ref, lang_table) if shortname_ref else None
        rows.append(
            {
                "race_id": race_id,
                "race_name": race_name,
                "race_shortname": race_shortname,
                "ware_id": race_id,
                "name_ref": name_ref or "",
                "shortname_ref": shortname_ref or "",
            }
        )
    return rows


def parse_purposes(path: Path, lang_table: dict) -> list[dict]:
    """Every <purpose id="..." name="{page,id}" .../> in purposes.xml --
    for the purposes DB table backing the ship picker's Purpose filter
    labels with a real display name instead of the raw internal code
    (ships_base.purpose, e.g. "dismantling") capitalized client-side with
    no actual translation behind it.

    Covers every real purpose the game defines (~22, including several
    that only ever apply to stations, e.g. "hack"/"habitation"/"docking"),
    not just the 8 that currently show up in ships_base.purpose -- same
    "store the whole real vocabulary, not just today's subset" choice
    parse_factions() already makes, so a ship whose purpose value changes
    (or a new one a future DLC adds) doesn't need this table touched.

    Same "ware_id"/"name_ref" passenger keys as parse_factions() (see that
    function's own docstring) so this list can be handed to
    parse_localized_strings() the same way -- a purpose isn't a ware
    either, but slots into that shared function identically.
    """
    root = ET.parse(path).getroot()
    rows = []
    for purpose_el in root.findall("purpose"):
        purpose_id = purpose_el.get("id")
        if not purpose_id:
            continue
        name_ref = purpose_el.get("name")
        purpose_name = resolve_ref_attr(name_ref, lang_table) if name_ref else purpose_id.replace("_", " ").title()
        rows.append(
            {
                "purpose_id": purpose_id,
                "purpose_name": purpose_name,
                "ware_id": purpose_id,
                "name_ref": name_ref or "",
            }
        )
    return rows


def parse_localized_strings(entity_lists: list[list[dict]], ref_key: str = "name_ref") -> list[dict]:
    """Non-English text for everything in `entity_lists` (each a parsed
    ships/economy_wares/equipment_wares/software_wares/missile_wares/
    deployable_wares/drone_wares/countermeasure_wares/crew_wares/factions/
    races/purposes list -- anything with its own "ware_id" and `ref_key`
    keys) -- one row per (ware_id, lang_id) pair that actually has a real
    translation, for the localized_strings DB table backing this app's
    game-data localization (separate from the website's own UI text, see
    src/static/i18n.js). parse_factions()/parse_races()/parse_purposes() are
    the callers whose own real primary key isn't actually named "ware_id"
    ("faction_id"/"race_id"/"purpose_id") -- their rows carry a "ware_id"
    key too purely so they slot into this shared function the same way
    every other entity list already does, not because a faction/race/
    purpose is a ware.

    `ref_key` defaults to "name_ref" (every entity's display-name ref) --
    main() also calls this with ref_key="shortname_ref" (against just
    [factions], writing to localized_shortnames) and again against just
    [races] for both name_ref and shortname_ref (writing to
    localized_race_names/localized_race_shortnames) -- same function, same
    resolution logic each time, just a different ref/entity_lists/output
    table. See this module's "Design race and race/faction shortcodes"
    docstring section for why races needed full isolation from factions'
    tables rather than just another ref_key against a shared list.

    "ware_id" values are assumed unique across every list passed in
    together -- true by construction for wares (a real, guaranteed-unique
    ware_id namespace) and, separately, for faction ids (their own
    distinct namespace, checked against no ware_id ever colliding with a
    faction_id in practice), but never verified against each other here.

    Companion-table pattern, but shared across every translatable table
    instead of one companion per table (ships_translations,
    equipment_wares_translations, ...) -- keyed by ware_id rather than by
    the game's own (page_id, entry_id) pair, which was the other option
    considered: ware_id is already the real primary key on every table
    this reads from, so this needs zero schema changes anywhere else to
    join against, at the cost of a little redundancy if two wares somehow
    shared the exact same name string (not a real concern for names, which
    are effectively always unique per ware, unlike e.g. generic UI text
    where the same string commonly repeats across many places).

    English is deliberately excluded -- LANGUAGE_FILES lists it, but it's
    already baked directly into every base table's own "name" column (see
    each parse_*() function's own w["name"] = resolve_ref_attr(...) line),
    so duplicating it here would just be redundant storage. A ware with no
    real translation available in a given language (missing from that
    language's own file entirely -- confirmed here by checking the raw
    (page_id, entry_id) key directly, not by the fragile-in-general
    "did resolve_ref_attr() actually change anything" heuristic) simply
    gets no row for that (ware_id, lang_id) pair at all -- api.py's own
    query is expected to COALESCE a missing row back to the base table's
    English "name" column, exactly the "fall back to English" behavior
    requested. This is also the correct behavior for a future third-party
    mod that ships incomplete or no localization of its own: same missing-
    row-falls-back-to-English path, no special-casing needed, *provided*
    the mod's own text actually lives in the same base-game-relative
    t/0001-l<id>.xml files this reads (confirmed true for every official
    DLC -- see language_jobs() in extract_game_data.py -- but an
    unofficial mod could in principle ship its own separate language file
    instead, which this function has no knowledge of at all; revisit once
    real mod support -- a deferred post-1.0 item -- is actually built and
    it's clear how mods really do this).
    """
    lang_tables: dict[str, dict] = {}
    for lang_id, filename in LANGUAGE_FILES.items():
        if lang_id == "en":
            continue
        path = DATA / "names" / filename
        if path.exists():
            lang_tables[lang_id] = load_language_table(path)

    rows = []
    seen: set[tuple[str, str]] = set()
    for entities in entity_lists:
        for entity in entities:
            ware_id = entity.get("ware_id")
            name_ref = (entity.get(ref_key) or "").strip()
            match = FULL_REF_RE.match(name_ref)
            if not ware_id or not match:
                continue
            page_id, entry_id = match.group(1), match.group(2)
            for lang_id, table in lang_tables.items():
                key = (ware_id, lang_id)
                if key in seen:
                    continue
                raw = table.get((page_id, entry_id))
                if raw is None:
                    continue  # no translation for this entry in this language
                text = resolve_text(raw, table)
                if text:
                    rows.append({"ware_id": ware_id, "lang_id": lang_id, "text": text})
                    seen.add(key)
    return rows


# Extension content id -> {page,id} ref for that DLC's own real display
# name, cross-referenced from data/names/0001-l044.xml page 1021 -- X4's
# own "New Game"/gamestart expansion-selection screen registry. Found by
# grepping the English language file for each DLC's literal content.xml
# "name" attribute value ("Split Vendetta", "Kingdom End", ...): every one
# of them turned out to also have its own real entry on this same page,
# alongside "Requires expansion: <name>" strings one id higher (80-87) that
# aren't used here. Confirmed against German (0001-l049.xml) that real
# translations exist for every entry below (some carry a trailing
# translator-note parenthetical in German only -- e.g. "Wiege der
# Menschheit(Cradle of Humanity)" -- stripped the same way as
# CREW_ROLE_NAME_REF's "(plural)" artifact, see strip_trailing_dev_comment()
# and this function's own caller in main()).
#
# The base game's own row deliberately has no ref here and keeps its
# literal "X4: Foundations" name -- this page's own base-game entry (id 65)
# is just "Foundations" with no "X4:" prefix (this screen's own context
# already establishes that), and the German translator's note on it
# ("Foundations(oder hier: Grundlagen?)") reads as genuinely undecided
# rather than a settled translation, unlike every DLC entry below.
#
# REVISIT when real mod support is built (see GitHub issue #5) -- same
# caveat as SHIP_TYPE_NAME_REF/CREW_ROLE_NAME_REF: a third-party
# extension's content id has no entry here and correctly falls back to its
# own content.xml "name" attribute, unlocalized.
SOURCE_VERSION_NAME_REF = {
    "ego_dlc_split": "{1021,61}",  # Split Vendetta
    "ego_dlc_terran": "{1021,62}",  # Cradle of Humanity
    "ego_dlc_pirate": "{1021,63}",  # Tides of Avarice
    "ego_dlc_boron": "{1021,66}",  # Kingdom End
    "ego_dlc_timelines": "{1021,67}",  # Timelines
    "ego_dlc_mini_01": "{1021,71}",  # Hyperion Pack
    "ego_dlc_mini_02": "{1021,72}",  # Envoy Pack
}


def parse_source_versions() -> list[dict]:
    """Base game build number (data/version.dat, a plain number with no XML
    around it) plus every installed extension's own version (data/
    extensions/<ext>/content.xml's version attribute, name attribute for
    display) -- for the About page's "built from these versions" section.

    Unlike wares.xml, content.xml is a plain file, never a <diff> patch, and
    version.dat isn't XML at all -- both are read directly, no
    iter_ware_elements()/resolve_ref_attr() involved. The base game row
    always comes first; extensions follow in data/extensions' own
    alphabetical (by folder name, e.g. "ego_dlc_boron") order, which isn't
    necessarily install/release order but is at least stable run to run.

    format_egosoft_build_version() above is only ever applied to the base
    game row and to an extension whose own content.xml has
    author="Egosoft GmbH" -- official DLCs are versioned to match the
    current base-game build, not their own independent number, so the same
    public-version formatting is correct for them too. A third-party mod's
    content.xml can carry any version string at all (semantic version, a
    date, anything), so its own author's value is displayed completely
    unformatted -- reformatting it under the same "divide by 100" assumption
    would silently misrepresent it.

    Each row also carries "ware_id" (== source_id) and "name_ref" (see
    SOURCE_VERSION_NAME_REF above) purely so this list can slot into
    parse_localized_strings() the same way every other entity list does --
    same convention as parse_factions()/parse_purposes()' own "ware_id"
    field, not written to the CSV (see SOURCE_VERSIONS_FIELDNAMES).
    """
    rows = [
        {
            "source_id": "base_game",
            "ware_id": "base_game",
            "name_ref": None,
            "source_name": "X4: Foundations",
            "source_version": format_egosoft_build_version(VERSION_DAT_FILE.read_text(encoding="utf-8").strip()),
        }
    ]

    if EXTENSIONS_DIR.exists():
        for ext_dir in sorted(EXTENSIONS_DIR.iterdir()):
            content_xml = ext_dir / "content.xml"
            if not content_xml.exists():
                continue
            content_el = ET.parse(content_xml).getroot()
            source_id = content_el.get("id") or ext_dir.name
            raw_version = content_el.get("version") or ""
            is_egosoft = content_el.get("author") == "Egosoft GmbH"
            rows.append(
                {
                    "source_id": source_id,
                    "ware_id": source_id,
                    "name_ref": SOURCE_VERSION_NAME_REF.get(source_id),
                    "source_name": content_el.get("name") or ext_dir.name,
                    "source_version": format_egosoft_build_version(raw_version) if is_egosoft else raw_version,
                }
            )

    return rows


def main() -> None:
    lang_table = load_language_table(LANG_FILE)
    # Built once, up front -- see index_ship_files()'s own docstring. Feeds
    # both the ship loop below (analyze_ship_components()) and the drone
    # macro lookup further down.
    ship_macro_index = index_ship_files("macros")
    ship_component_index = index_ship_files("components")
    dock_macro_index = index_dock_macros()
    ships = parse_ship_wares(wares_files())
    economy_wares = parse_economy_wares(wares_files())
    equipment_wares = parse_equipment_wares(wares_files())
    turrets, turret_aliases = parse_turrets(TURRET_MACRO_DIRS, TURRET_COMPONENT_DIRS)
    engines, engine_aliases = parse_engines(ENGINE_MACRO_DIRS, ENGINE_COMPONENT_DIRS)
    shields, shield_aliases = parse_shields(SHIELD_MACRO_DIRS, SHIELD_COMPONENT_DIRS)
    weapons, weapon_aliases = parse_weapons(WEAPON_MACRO_DIRS, WEAPON_COMPONENT_DIRS)
    thruster_macros = parse_thruster_macros(THRUSTERS_MACRO_DIR)
    thrusters = parse_thruster_wares(wares_files(), thruster_macros)
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
        # Drone macros only ever turn up under class ship_s in this dataset
        # (see the "Drones" docstring section), but looked up here by name
        # via ship_macro_index rather than assumed -- 8 of the 11 wares
        # simply have no macro file there (or anywhere) at all, which is
        # expected, not a gap.
        macro_lookup = ship_macro_index.get(w["macro"]) if w["macro"] else None
        if macro_lookup is not None:
            _drone_class, macro_path = macro_lookup
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
        analysis = analyze_ship_components(s, ship_macro_index, ship_component_index, dock_macro_index)
        s["size"] = analysis["size"]
        s["ship_class"] = analysis["ship_class"]
        s["makerrace"] = analysis["makerrace"]
        s["component_groups"] = analysis["groups"]
        s["missile_capacity"] = analysis["missile_capacity"]
        s["drone_capacity"] = analysis["drone_capacity"]
        s["ship_type"] = analysis["ship_type"]
        s["purpose"] = analysis["purpose"]
        s["icon"] = analysis["icon"]
        s["hull"] = analysis["hull"]
        s["crew"] = analysis["crew"]
        s["traveldrivestability"] = analysis["traveldrivestability"]
        s["weapon_heat_modifier"] = analysis["weapon_heat_modifier"]
        s["shield_capacity_modifier"] = analysis["shield_capacity_modifier"]
        s["shield_rechargerate_modifier"] = analysis["shield_rechargerate_modifier"]
        s["shield_rechargedelay_modifier"] = analysis["shield_rechargedelay_modifier"]
        s["jerk_fields"] = analysis["jerk_fields"]
        s["physics_fields"] = analysis["physics_fields"]
        s["steeringcurve"] = analysis["steeringcurve"]
        s["cargo_capacity"] = analysis["cargo_capacity"]
        s["cargo_type"] = analysis["cargo_type"]
        s["s_docks"] = analysis["docks"].get("s", 0)
        s["m_docks"] = analysis["docks"].get("m", 0)
        s["s_ship_storage"] = analysis["ship_storage"].get("s", 0)
        s["m_ship_storage"] = analysis["ship_storage"].get("m", 0)
        s["slots"] = summarize_slots(s["ware_id"], s["size"], analysis["slot_counts"])
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
    bullets = parse_bullets(BULLETS_MACRO_DIR)
    bullet_row_count = write_equipment_component_csv(bullets, BULLET_FIELDNAMES, BULLETS_CSV_OUT)
    deployable_row_count = write_equipment_component_csv(deployable_wares, DEPLOYABLE_FIELDNAMES, DEPLOYABLES_CSV_OUT)
    drone_row_count = write_equipment_component_csv(drone_wares, DRONE_FIELDNAMES, DRONES_CSV_OUT)
    countermeasure_row_count = write_equipment_component_csv(
        countermeasure_wares, COUNTERMEASURE_FIELDNAMES, COUNTERMEASURES_CSV_OUT
    )
    crew_row_count = write_equipment_component_csv(crew_wares, CREW_FIELDNAMES, CREW_CSV_OUT)
    source_versions = parse_source_versions()
    source_versions_row_count = write_equipment_component_csv(
        source_versions, SOURCE_VERSIONS_FIELDNAMES, SOURCE_VERSIONS_CSV_OUT
    )
    factions = parse_factions(factions_files(), lang_table)
    factions_row_count = write_equipment_component_csv(factions, FACTIONS_FIELDNAMES, FACTIONS_CSV_OUT)
    races = parse_races(RACES_FILE, lang_table)
    races_row_count = write_equipment_component_csv(races, RACES_FIELDNAMES, RACES_CSV_OUT)
    purposes = parse_purposes(PURPOSES_FILE, lang_table)
    purposes_row_count = write_equipment_component_csv(purposes, PURPOSES_FIELDNAMES, PURPOSES_CSV_OUT)
    ship_types = parse_ship_types(ships, lang_table)
    ship_types_row_count = write_equipment_component_csv(ship_types, SHIP_TYPE_FIELDNAMES, SHIP_TYPES_CSV_OUT)
    cargo_types = parse_cargo_types(ships, economy_wares, lang_table)
    cargo_types_row_count = write_equipment_component_csv(cargo_types, CARGO_TYPE_FIELDNAMES, CARGO_TYPES_CSV_OUT)
    compatibility_types = parse_compatibility_types(
        [engines, shields, weapons, turrets, thrusters, missile_wares],
        [group for s in ships for group in s["component_groups"]],
        races,
        lang_table,
    )
    compatibility_types_row_count = write_equipment_component_csv(
        compatibility_types, COMPATIBILITY_TYPE_FIELDNAMES, COMPATIBILITY_TYPES_CSV_OUT
    )
    ammunition_compatibility_types = parse_ammunition_compatibility_types(missile_wares, weapons, turrets, lang_table)
    ammunition_compatibility_types_row_count = write_equipment_component_csv(
        ammunition_compatibility_types,
        AMMUNITION_COMPATIBILITY_TYPE_FIELDNAMES,
        AMMUNITION_COMPATIBILITY_TYPES_CSV_OUT,
    )
    thruster_classes = parse_thruster_classes(thrusters, lang_table)
    thruster_classes_row_count = write_equipment_component_csv(
        thruster_classes, THRUSTER_CLASS_FIELDNAMES, THRUSTER_CLASSES_CSV_OUT
    )
    deployable_types = parse_deployable_types(deployable_wares, lang_table)
    deployable_types_row_count = write_equipment_component_csv(
        deployable_types, DEPLOYABLE_TYPE_FIELDNAMES, DEPLOYABLE_TYPES_CSV_OUT
    )
    missile_weapon_systems = parse_missile_weapon_systems(missile_wares, lang_table)
    missile_weapon_systems_row_count = write_equipment_component_csv(
        missile_weapon_systems, MISSILE_WEAPON_SYSTEM_FIELDNAMES, MISSILE_WEAPON_SYSTEMS_CSV_OUT
    )
    # Every production-resolution loop above (ships/economy_wares/
    # equipment_wares/missile_wares/deployable_wares/drone_wares/
    # countermeasure_wares) has already run by this point, so every real
    # method_name/method_name_ref pair is available to collect from.
    build_method_refs = collect_build_method_refs(
        [ships, economy_wares, equipment_wares, missile_wares, deployable_wares, drone_wares, countermeasure_wares]
    )
    build_methods = parse_build_methods(build_method_refs)
    build_methods_row_count = write_equipment_component_csv(build_methods, BUILD_METHOD_FIELDNAMES, BUILD_METHODS_CSV_OUT)
    crew_roles = parse_crew_roles(lang_table)
    crew_roles_row_count = write_equipment_component_csv(crew_roles, CREW_ROLE_FIELDNAMES, CREW_ROLES_CSV_OUT)

    # The golden-source design-race data (see build_maker_race_rows()'s own
    # docstring): every ship plus every turret/engine/shield/weapon carries
    # its own identification/@makerrace, already captured onto each row's
    # "makerrace" key by analyze_ship_components()/
    # parse_equipment_component_wares() respectively. valid_race_ids comes
    # from races (just parsed above), so this has to run after that.
    valid_race_ids = {r["race_id"] for r in races}
    maker_races = build_maker_race_rows(
        ships + turrets + engines + shields + weapons, valid_race_ids
    )
    maker_races_row_count = write_equipment_component_csv(maker_races, MAKER_RACES_FIELDNAMES, MAKER_RACES_CSV_OUT)

    # `races` is deliberately NOT in this list -- see the races/factions
    # split below for why.
    localized_strings = parse_localized_strings(
        [
            ships,
            economy_wares,
            equipment_wares,
            software_wares,
            missile_wares,
            deployable_wares,
            drone_wares,
            countermeasure_wares,
            crew_wares,
            factions,
            purposes,
            ship_types,
            cargo_types,
            compatibility_types,
            ammunition_compatibility_types,
            thruster_classes,
            deployable_types,
            missile_weapon_systems,
            build_methods,
            crew_roles,
            source_versions,
        ]
    )
    # See strip_trailing_dev_comment()'s own docstring -- both
    # CREW_ROLE_NAME_REF refs' raw text carries the same trailing
    # "(plural)" dev comment in every language, not just English, so their
    # own localized_strings row(s) need the identical cleanup
    # parse_crew_roles() already applied to the base English name.
    #
    # SOURCE_VERSION_NAME_REF's German entries carry the same class of
    # artifact -- translator notes rather than a dev comment (e.g. "Wiege
    # der Menschheit(Cradle of Humanity)" echoing the English original,
    # "Kingdom End(falls Extension-Name; falls Ort: Königstal)" flagging an
    # unresolved naming question) -- but the fix is identical: strip the
    # trailing parenthetical, keep the real translated text before it.
    for row in localized_strings:
        if row["ware_id"] in CREW_ROLE_NAME_REF or row["ware_id"] in SOURCE_VERSION_NAME_REF:
            row["text"] = strip_trailing_dev_comment(row["text"])
    # A size-prefixed compound ammunition-compatibility tag (e.g.
    # "largedumbfire") has no single name_ref of its own for the loop above
    # to have resolved -- see parse_ammunition_compatibility_localized_strings()'s
    # own docstring for why that one case needs composing from two refs
    # per language instead. Safe to just append: bare tags (dumbfire/
    # guided/torpedo) already got a real row from parse_localized_strings()
    # itself above, and this function only ever emits rows for compound
    # tags, so there's no (ware_id, lang_id) overlap between the two lists.
    localized_strings += parse_ammunition_compatibility_localized_strings(ammunition_compatibility_types)
    localized_strings_row_count = write_equipment_component_csv(
        localized_strings, LOCALIZED_STRINGS_FIELDNAMES, LOCALIZED_STRINGS_CSV_OUT
    )
    # Same shared function, but resolving faction_shortname's own
    # "shortname_ref" instead of "name_ref" -- a faction's short in-game
    # callsign (e.g. "YAK" for Yaki) gets its own non-English coverage
    # here, completely separate from its display name's. See
    # parse_factions() for where shortname_ref comes from, and this
    # module's "Design race and race/faction shortcodes" docstring section
    # for why a second table (not a second row in localized_strings) was
    # the cleanest way to give one entity two independently-localizable
    # text fields.
    localized_shortnames = parse_localized_strings([factions], ref_key="shortname_ref")
    localized_shortnames_row_count = write_equipment_component_csv(
        localized_shortnames, LOCALIZED_STRINGS_FIELDNAMES, LOCALIZED_SHORTNAMES_CSV_OUT
    )

    # races gets its own pair of tables, entirely separate from
    # localized_strings/localized_shortnames above, rather than sharing
    # factions' -- discovered the hard way (a live GET /api/races?lang=de
    # test) that several race ids collide with a same-named faction id
    # (e.g. "argon" is both), and parse_localized_strings()'s own `seen`
    # dedup silently keeps whichever list happens to be processed first on
    # a collision -- so mixing races into factions' shared keyspace was
    # quietly returning the *faction's* German name/shortcode for a race
    # (e.g. "Argonische Föderation" instead of the race's own "Argonen").
    # Isolating races into their own tables sidesteps the collision
    # entirely instead of relying on list ordering + "the values happen to
    # match today" to paper over it.
    localized_race_names = parse_localized_strings([races])
    localized_race_names_row_count = write_equipment_component_csv(
        localized_race_names, LOCALIZED_STRINGS_FIELDNAMES, LOCALIZED_RACE_NAMES_CSV_OUT
    )
    localized_race_shortnames = parse_localized_strings([races], ref_key="shortname_ref")
    localized_race_shortnames_row_count = write_equipment_component_csv(
        localized_race_shortnames, LOCALIZED_STRINGS_FIELDNAMES, LOCALIZED_RACE_SHORTNAMES_CSV_OUT
    )
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
        f"{bullet_row_count} bullets_base rows, "
        f"{deployable_row_count} deployables_base rows, "
        f"{drone_row_count} drones_base rows, "
        f"{countermeasure_row_count} countermeasures_base rows, "
        f"{crew_row_count} crew_base rows, "
        f"{source_versions_row_count} source_versions rows, "
        f"{factions_row_count} factions rows, "
        f"{races_row_count} races rows, "
        f"{purposes_row_count} purposes rows, "
        f"{ship_types_row_count} ship_types rows, "
        f"{cargo_types_row_count} cargo_types rows, "
        f"{compatibility_types_row_count} compatibility_types rows, "
        f"{ammunition_compatibility_types_row_count} ammunition_compatibility_types rows, "
        f"{thruster_classes_row_count} thruster_classes rows, "
        f"{deployable_types_row_count} deployable_types rows, "
        f"{missile_weapon_systems_row_count} missile_weapon_systems rows, "
        f"{build_methods_row_count} build_methods rows, "
        f"{crew_roles_row_count} crew_roles rows, "
        f"{maker_races_row_count} maker_races rows, "
        f"{localized_strings_row_count} localized_strings rows, "
        f"{localized_shortnames_row_count} localized_shortnames rows, "
        f"{localized_race_names_row_count} localized_race_names rows, "
        f"{localized_race_shortnames_row_count} localized_race_shortnames rows"
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
    print(f"  -> {BULLETS_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {DEPLOYABLES_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {DRONES_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {COUNTERMEASURES_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {CREW_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {SOURCE_VERSIONS_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {FACTIONS_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {RACES_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {PURPOSES_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {SHIP_TYPES_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {CARGO_TYPES_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {COMPATIBILITY_TYPES_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {AMMUNITION_COMPATIBILITY_TYPES_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {THRUSTER_CLASSES_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {DEPLOYABLE_TYPES_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {MISSILE_WEAPON_SYSTEMS_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {BUILD_METHODS_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {CREW_ROLES_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {MAKER_RACES_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {LOCALIZED_STRINGS_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {LOCALIZED_SHORTNAMES_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {LOCALIZED_RACE_NAMES_CSV_OUT.relative_to(ROOT)}")
    print(f"  -> {LOCALIZED_RACE_SHORTNAMES_CSV_OUT.relative_to(ROOT)}")

    load_database(DB_OUT, SQL_OUT, TABLE_CSV_FILES)
    print(f"  -> {DB_OUT.relative_to(ROOT)} (rebuilt)")


if __name__ == "__main__":
    main()
