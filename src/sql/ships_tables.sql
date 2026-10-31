DROP TABLE IF EXISTS localized_race_shortnames;
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
DROP TABLE IF EXISTS equipment_mod_stats;
DROP TABLE IF EXISTS equipment_mod_costs;
DROP TABLE IF EXISTS mod_qualities;
DROP TABLE IF EXISTS equipment_mods_base;
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
    prestige INTEGER,
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
    -- radar_range: real on exactly 2 of 255 ships (Hyperion/Sapporo, both
    -- hero/flagship-tier), DEFAULT_RADAR_RANGE (40000) everywhere else --
    -- see load_macro_data()'s own comment, same "absence = a real default"
    -- convention as the hull-wide multipliers above.
    -- region_damage_immune: real on exactly one ship (Erlking) -- a plain
    -- boolean flag, not a percentage (see load_macro_data()'s own comment
    -- for how this reconciles with the equipment-mod system's own
    -- fractional "Hazardous Region Damage Reduction Mod").
    -- countermeasure_capacity/deployable_capacity: no real per-ship game
    -- data exists for either (see COUNTERMEASURE_CAPACITY_BY_SIZE/
    -- DEPLOYABLE_CAPACITY_BY_SIZE's own comment) -- an assumed default by
    -- ship size, moved here from the frontend so the API can return a real
    -- value instead of the client re-deriving it from `size` itself.
    -- radar_cloak: no ship has any inherent stealth capability at all --
    -- a flat constant 1.0 for every ship, existing purely so a radarcloak
    -- mod has a real column to apply its own effect onto.
    -- illegal_cargo_concealed: same situation as radar_cloak but boolean --
    -- no ship has any inherent illegal-ware-concealment capability, always
    -- False, existing purely so a hidecargochance mod has a real column to
    -- apply its own effect onto (same add_ceiling_bool operation as
    -- region_damage_immune -- see equipment_mod_target_mappings.json).
    radar_range INTEGER,
    region_damage_immune BOOLEAN,
    countermeasure_capacity INTEGER,
    deployable_capacity INTEGER,
    radar_cloak REAL,
    illegal_cargo_concealed BOOLEAN,
    size TEXT,
    -- The raw class="..." value this ship's own macro carried (e.g.
    -- "ship_l"), before SHIP_CLASS_TO_SIZE_CODE's mapping to `size` above
    -- -- kept alongside it for the follow-up localization investigation
    -- (see that dict's own docstring), not used by anything else yet.
    ship_class TEXT,
    shields INTEGER,
    engines INTEGER,
    weapons INTEGER,
    "bonus_l_weapons" INTEGER,
    missile_launchers INTEGER,
    "turret_l" INTEGER,
    "turret_m" INTEGER,
    shields_bonus_m INTEGER,
    shield_bonus_groups INTEGER
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

-- A macro this pipeline determined is a compatibility-variant duplicate of
-- another real item -- same display name, makerrace, mk, and every
-- type-specific stat, differing only in `compatibility` (and a resulting
-- hull-value artifact) -- see parse_equipment_component_wares' own
-- docstring for how this is detected (comparing actual stats, not just a
-- macro's own alias="..." attribute) and why both rows still need
-- representing somewhere: a ship with a "standard"-tier slot and one with
-- an "advanced"-tier slot both need to see this as a real option, but
-- turrets_base/engines_base/shields_base/weapons_base only keeps the one
-- canonical row (the one with a real, non-integrated hull value) so the
-- Component Analyzer's own picker shows one row per real item instead of
-- one per compatibility tier. `compatibility` here is the *alias* side's
-- own tag set (the canonical row's own is still on its own turrets_base/
-- etc. row) -- query_ship_components.py's matching_items() (forward, ship
-- group -> compatible equipment) and ships_matching_ware() (reverse,
-- equipment -> compatible ships) both test a canonical ware's own
-- compatibility AND every alias row here targeting it, so neither
-- direction silently drops a real tier's worth of matches.
--
-- Both alias_ware_id and target_ware_id are still real, independently-
-- priced rows in equipment_wares_base -- only the type-specific stats
-- table excludes the alias side. Existing purely so a ware_id sourced from
-- *outside* this app's own picker (a real player-saved ship loadout, see
-- import_loadouts.py) can be resolved back to the still-listed target the
-- game itself treats as equivalent, since the game never actually removed
-- the alias ware -- only this app's own picker does, to avoid showing two
-- indistinguishable options.
CREATE TABLE equipment_ware_aliases (
    alias_ware_id TEXT PRIMARY KEY,
    target_ware_id TEXT NOT NULL,
    equipment_type TEXT NOT NULL,
    compatibility TEXT,
    FOREIGN KEY (alias_ware_id) REFERENCES equipment_wares_base (ware_id),
    FOREIGN KEY (target_ware_id) REFERENCES equipment_wares_base (ware_id)
);

CREATE TABLE turrets_base (
    ware_id TEXT PRIMARY KEY,
    -- Denormalized copy of equipment_wares_base.name (primary_locale's own
    -- text, English by default) for direct queries against this table
    -- alone, no join needed -- same convenience ships_base.name already
    -- offers. api.py's own /api/components/<class 'type'> still prefers the live,
    -- per-viewer i18n name (COALESCE(localized_strings.text,
    -- equipment_wares_base.name)) over this column for the actual app.
    name TEXT,
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
    -- See turrets_base.name's own comment -- same denormalized-copy pattern.
    name TEXT,
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
    -- See turrets_base.name's own comment -- same denormalized-copy pattern.
    name TEXT,
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
    -- See turrets_base.name's own comment -- same denormalized-copy pattern.
    name TEXT,
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
    -- See turrets_base.name's own comment -- same denormalized-copy pattern.
    name TEXT,
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
-- section. Not yet used for any matching/query logic. `thrust_*` come from
-- a real, separate <engine>-class macro this missile's own <connections>
-- points at (never a standalone ware of its own) -- see
-- load_engine_thrust_index()/analyze_missile_macro() in
-- generate_ships_table.py -- NULL for the couple of missiles (heavy
-- torpedoes) with no engine connection at all, a real absence, not a
-- parsing gap. `anomalous_range_multiplier` is hand-measured, not derived
-- from any game file -- see MISSILE_ANOMALOUS_RANGE_MULTIPLIER's own
-- comment in generate_ships_table.py -- a flat correction factor on top
-- of the computed Max Distance stat (app.js), 1.0 (a no-op) for every
-- missile whose formula is already right. `game_value_*` are hand-measured
-- straight from the player's own real in-game Encyclopedia screenshots
-- (see MISSILE_GAME_VALUES' own comment in generate_ships_table.py) --
-- reference ground truth, not a formula's output. NULL (not 0) for the two
-- Barrage missiles, which have no screenshot.
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
    compatibility TEXT,
    thrust_forward REAL,
    thrust_reverse REAL,
    thrust_strafe REAL,
    thrust_pitch REAL,
    thrust_yaw REAL,
    thrust_roll REAL,
    physics_drag_forward REAL,
    physics_drag_reverse REAL,
    physics_drag_horizontal REAL,
    physics_drag_vertical REAL,
    physics_drag_pitch REAL,
    physics_drag_yaw REAL,
    physics_drag_roll REAL,
    physics_inertia_pitch REAL,
    physics_inertia_yaw REAL,
    physics_inertia_roll REAL,
    anomalous_range_multiplier REAL DEFAULT 1,
    game_value_turn_rate REAL,
    game_value_pitch_rate REAL,
    game_value_vertical_strafe REAL,
    game_value_horizontal_strafe REAL
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
-- explosive/AOE bullets (flak etc). charge_time/stick_time/
-- mining_damage_multiplier/surfaceelement_damage_multiplier are each only
-- real on a small minority of bullets (charge beams, sticky/charge Split
-- projectiles, mining lasers, anti-turret bonus-damage bullets
-- respectively) -- NULL everywhere else, same "absence = a real, meaningful
-- NULL" contract as every other optional column here; added specifically
-- so the equipment-mod system's own chargetime/sticktime/mining/
-- surfaceelement weapon mods have a real column to apply their effect onto
-- (see equipment_mod_target_mappings.json).
CREATE TABLE bullets_base (
    bullet_class TEXT PRIMARY KEY,
    damage_value REAL,
    damage_shield REAL,
    damage_hull REAL,
    damage_noshield REAL,
    damage_repair REAL,
    damage_shielddisruption REAL,
    bullet_speed REAL,
    bullet_lifetime REAL,
    bullet_range REAL,
    bullet_amount INTEGER,
    bullet_barrelamount INTEGER,
    charge_time REAL,
    stick_time REAL,
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
    areadamage_lifetime REAL,
    mining_damage_multiplier REAL,
    surfaceelement_damage_multiplier REAL
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

-- The in-game equipment "mod" system (libraries/equipmentmods.xml -- NOT
-- Steam Workshop/user-created mods) -- see
-- parse_equipment_mods()/equipmentmods_files()'s own docstrings above for
-- the full story. One row per real mod (a real wares.xml ware, tag
-- "equipmentmod"; a handful of Timelines mission-specific ones with no
-- real ware are skipped entirely, not represented here at all) PLUS one
-- synthetic row per ship chassis with a non-default <modifiers> block
-- (is_chassis_mod=1 -- see parse_chassis_integrated_mods()'s own
-- docstring). mod_level is quality (1/2/3 = Basic/Advanced/Exceptional)
-- for a real mod; always 0 for a chassis mod (no real mod ever uses 0,
-- so it reads as "not a real, quality-tiered mod" -- a ship either has
-- its own fixed, non-rolled modifiers or it doesn't, no tier concept
-- applies). mod_components is comma-joined -- always a single
-- component_type for a real mod (weapon/engine/ship/shield); a chassis
-- mod is the one case where a mod_id's own rows can span more than one
-- (e.g. "shield,weapon"). additional_stats_count is the mod's own
-- optional <bonus max=""> value (0 if it has no bonus roll at all, always
-- 0 for a chassis mod -- its own numbers are fixed, never rolled) -- how
-- many of equipment_mod_stats' own candidate additional-stat rows for
-- this mod_id actually get chosen/applied, not how many candidates exist
-- (that's just a COUNT(*) ... WHERE is_additional_stat over
-- equipment_mod_stats). ship_icon is that originating ship's own
-- ships_base.icon (e.g. "ship_s_fighter_01") for a chassis mod, so the
-- Modifications Lab can show each one with its real ship's own class
-- symbol -- NULL for every real mod, which has no owning ship at all.
-- price_min/price_avg/price_max are what it actually costs to APPLY this
-- mod via the in-game Modification workshop -- all three always equal
-- (there's no real min/max range, only one flat per-tier price), sourced
-- from MOD_QUALITY_APPLICATION_PRICE (a hardcoded constant, not this
-- mod's own wares.xml <price> tag -- see that constant's own comment for
-- why: that field turned out to be the ware's own market trading price,
-- a real but different number). NULL for every chassis mod, which has no
-- real ware/price at all (see parse_chassis_integrated_mods()'s own "no
-- price" docstring). The materials actually consumed to *craft* one (as
-- opposed to the flat application cost above) are equipment_mod_costs, a
-- separate table below -- a mod's own
-- crafting inputs are "mod part" wares (e.g. "modpart_enginefuelinjector_t1"),
-- a different ware category from the raw/refined materials
-- production_wares' own FK already assumes (economy_wares_base), so they
-- don't fit that existing generic mechanism.
CREATE TABLE equipment_mods_base (
    mod_id TEXT PRIMARY KEY,
    mod_name TEXT,
    mod_level INTEGER,
    mod_components TEXT,
    additional_stats_count INTEGER,
    is_chassis_mod BOOLEAN,
    ship_icon TEXT,
    price_min INTEGER,
    price_avg INTEGER,
    price_max INTEGER
);

-- One row per crafting-material ware (+ amount needed) to produce ONE of a
-- real mod (equipment_mods_base.mod_id) -- read straight off that mod's
-- own <production><primary><ware ware="" amount=""/></primary></production>
-- (see parse_equipment_mods()'s own docstring; every real mod has exactly
-- one production method, confirmed across every wares*.xml file, base
-- game and every DLC). No FK to economy_wares_base -- these "mod part"
-- wares (e.g. "modpart_enginefuelinjector_t1") are their own separate
-- category, not part of PRICE_WARE_TABLES in summarize_production.py at
-- all. ware_name is that resource ware's own English display name,
-- denormalized here the same way equipment_mods_base.mod_name is (GET
-- /api/equipment_mods overrides it per-language via a localized_strings
-- join, same COALESCE pattern as every other mod field) -- these wares
-- are never named anywhere else in this dataset, so this is the only
-- place a real name for one exists at all. No rows at all for a chassis
-- mod (nothing to craft -- it's not a real ware).
CREATE TABLE equipment_mod_costs (
    mod_id TEXT NOT NULL,
    ware_id TEXT NOT NULL,
    ware_name TEXT,
    amount INTEGER NOT NULL,
    PRIMARY KEY (mod_id, ware_id),
    FOREIGN KEY (mod_id) REFERENCES equipment_mods_base (mod_id)
);

-- Every real stat roll a mod in equipment_mods_base can apply -- one row
-- per primary stat (is_additional_stat=0, always guaranteed, chance=1.0)
-- plus one row per candidate secondary/"bonus" stat
-- (is_additional_stat=1) that mod's own optional <bonus> block lists.
-- component_type is which of weapon/engine/ship/shield target_stat
-- belongs to (matches this mod's own equipment_mods_base.mod_components
-- for a real mod -- a chassis mod's own rows are the one case where two
-- rows for the same mod_id carry different component_type values, e.g.
-- "weapon"/"heatgeneration" alongside "shield"/"capacity"). min_value/
-- max_value are that stat's own real roll range for a real mod (a
-- multiplier for most stats, e.g. 1.05-1.2 = "+5% to +20%"; some are
-- sub-1 penalties, e.g. cooling 0.684-0.736 on a damage-focused mod;
-- ship's own "radarcloak"/"regiondamage" use negative values instead --
-- see equipmentmods.xml's own header comment for the "min with no max"
-- caveat this data never actually hits), or a chassis mod's own fixed
-- (never rolled) value repeated as both min_value and max_value -- see
-- parse_chassis_integrated_mods()'s own docstring, including why a
-- chassis's own <weapon heat=""/> becomes target_stat "heatgeneration"
-- here (uninverted), not "heat". chance is that candidate's own <bonus
-- chance=""> (always 1.0 for a primary row -- guaranteed, not rolled for
-- *whether* it applies, only for its own min/max value -- also always
-- 1.0 for a chassis mod's own rows, for the same "always guaranteed"
-- reason). weight is only ever present on some additional-stat rows
-- (used for weighted random selection among candidates when a bonus
-- offers more of them than its own additional_stats_count slots) -- NULL
-- for every primary row, every chassis-mod row, and an additional-stat
-- row with nothing to weigh against (e.g. exactly one candidate for one
-- slot).
CREATE TABLE equipment_mod_stats (
    mod_id TEXT,
    is_additional_stat BOOLEAN,
    component_type TEXT,
    target_stat TEXT,
    min_value REAL,
    max_value REAL,
    chance REAL,
    weight INTEGER,
    PRIMARY KEY (mod_id, is_additional_stat, target_stat),
    FOREIGN KEY (mod_id) REFERENCES equipment_mods_base (mod_id)
);

-- The 3 real in-game equipment-mod quality tiers (Basic/Enhanced/Exceptional,
-- equipment_mods_base.mod_level) with real per-language display names -- see
-- parse_mod_qualities()/MOD_QUALITY_NAME_REF's own docstrings above. Backs the
-- Modifications Lab's own tab labels.
CREATE TABLE mod_qualities (
    mod_level INTEGER PRIMARY KEY,
    mod_quality_name TEXT
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
    "jerk_angular_value" REAL,
    "jerk_forward_accel" REAL,
    "jerk_forward_boost_accel" REAL,
    "jerk_forward_boost_ratio" REAL,
    "jerk_forward_decel" REAL,
    "jerk_forward_ratio" REAL,
    "jerk_forward_travel_accel" REAL,
    "jerk_forward_travel_decel" REAL,
    "jerk_forward_travel_ratio" REAL,
    "jerk_strafe_value" REAL,
    "physics_accfactors_forward" REAL,
    "physics_accfactors_horizontal" REAL,
    "physics_accfactors_reverse" REAL,
    "physics_accfactors_vertical" REAL,
    "physics_drag_forward" REAL,
    "physics_drag_horizontal" REAL,
    "physics_drag_pitch" REAL,
    "physics_drag_reverse" REAL,
    "physics_drag_roll" REAL,
    "physics_drag_vertical" REAL,
    "physics_drag_yaw" REAL,
    "physics_inertia_pitch" REAL,
    "physics_inertia_roll" REAL,
    "physics_inertia_yaw" REAL,
    "physics_mass" REAL,
    steeringcurve TEXT,
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
