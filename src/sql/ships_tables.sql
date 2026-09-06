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
    weapons INTEGER,
    "bonus_l_weapons" INTEGER,
    missile_launchers INTEGER,
    "turret_l" INTEGER,
    "turret_m" INTEGER,
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
