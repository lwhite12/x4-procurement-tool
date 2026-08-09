"""Stub tests for src/query_ship_components.py. No implementation yet --
each test documents, via its name and docstring, the behavior it should
confirm once written. All are skipped for now.

See tests/inputs/query_ship_components/ and tests/outputs/query_ship_components/
for hand-verified input/output fixture pairs:
  - barracuda.json: a single S-size ship (Barracuda, resolved by name) --
    covers the weapon/missile_launcher split (34 weapons, 3 dedicated
    missile launchers, matching src/query_ship_components.py's own manual
    verification) and an empty "turrets" list (S ships have none).
  - boron_destroyer.json: a single L-size ship (resolved by ware_id) --
    covers main shield/turret/engine groups and a ship-locked main weapon
    (exactly one compatible option: its own dedicated gun).
  - multi_ship_with_invalid.json: "Heron E" (a transporter with turrets/
    engines/shields but no weapon or missile_launcher hardpoints at all --
    both come back as empty lists, not omitted) plus "Not A Real Ship" --
    covers multi-ship requests and the unresolved-identifier error shape.
"""

import pytest


# --- load_input ---------------------------------------------------------------

def test_load_input_reads_from_file_path():
    pytest.skip("not implemented")


def test_load_input_reads_from_stdin_when_source_is_dash():
    pytest.skip("not implemented")


# --- resolve_ship ---------------------------------------------------------------

def test_resolve_ship_matches_by_ware_id_first():
    """A ware_id and a resolved name could theoretically collide; ware_id
    is checked first since it's the unambiguous key.
    """
    pytest.skip("not implemented")


def test_resolve_ship_falls_back_to_resolved_name():
    """"Barracuda" resolves via ships_base.name when it isn't a ware_id."""
    pytest.skip("not implemented")


def test_resolve_ship_returns_none_when_neither_matches():
    pytest.skip("not implemented")


# --- fetch_groups ---------------------------------------------------------------

def test_fetch_groups_returns_every_group_regardless_of_component_type():
    """All five component_type values (engine/shield/weapon/missile_launcher/
    turret) come back in one query, split into buckets later by the caller.
    """
    pytest.skip("not implemented")


def test_fetch_groups_empty_for_ship_with_no_recorded_groups():
    pytest.skip("not implemented")


# --- matching_items -------------------------------------------------------------

def test_matching_items_filters_by_size_and_compatibility():
    pytest.skip("not implemented")


def test_matching_items_treats_compat_class_as_any_of_comma_separated_tokens():
    """A group class of "advanced,missile" (e.g. a Boron destroyer turret
    mount) matches equipment with compatibility "advanced" OR "missile",
    not just an exact string match against the whole class field.
    """
    pytest.skip("not implemented")


def test_matching_items_returns_empty_list_when_compat_class_is_none():
    """A group with no recorded equipment_compatibility_class contributes
    no matches rather than an unfiltered (potentially misleading, e.g.
    faction-locked) list of every item of that size.
    """
    pytest.skip("not implemented")


def test_matching_items_weapon_excludes_missile_launchers():
    """component_type="weapon" only returns weapons_base rows where
    equipment_wares_base.missile_launcher = 0.
    """
    pytest.skip("not implemented")


def test_matching_items_missile_launcher_only_returns_missile_launchers():
    """component_type="missile_launcher" only returns weapons_base rows
    where equipment_wares_base.missile_launcher = 1, and queries the same
    weapons_base table as "weapon" does -- missile launchers are still
    weapon-type equipment, just a separate ship hardpoint.
    """
    pytest.skip("not implemented")


def test_matching_items_turret_does_not_filter_by_missile_launcher_flag():
    """Unlike weapon/missile_launcher, a "turret" group's matches include
    both combat and missile-capable turret variants -- one physical turret
    mount can take either, so ship_component_groups never splits turrets
    into a separate missile bucket the way it does for weapons.
    """
    pytest.skip("not implemented")


# --- query_ship -------------------------------------------------------------

def test_query_ship_unresolved_identifier_returns_error_shape():
    """{"input": ..., "error": "ship not found"} -- no "name"/"ware_id"/
    "components" keys when resolution fails.
    """
    pytest.skip("not implemented")


def test_query_ship_components_has_all_five_buckets_even_when_empty():
    """A transporter like Heron E has no weapon or missile_launcher
    hardpoints at all -- those buckets must still be present as empty
    lists, not omitted from "components".
    """
    pytest.skip("not implemented")


def test_query_ship_deduplicates_items_across_multiple_groups_of_the_same_type():
    """A ship with more than one turret group (e.g. distinct m and l turret
    mounts) unions their compatible items into one flat "turrets" list,
    deduplicated by ware_id -- an item compatible with more than one group
    appears exactly once.
    """
    pytest.skip("not implemented")


def test_query_ship_components_sorted_by_name():
    pytest.skip("not implemented")


def test_query_ship_barracuda_weapons_excludes_the_three_missile_launchers():
    """Regression check against tests/outputs/query_ship_components/
    barracuda.json: the Barracuda's 3 "weapon" hardpoints (class
    "advanced") resolve to 34 options, and its 1 dedicated
    "missile_launcher" hardpoint resolves to a separate 3 -- never
    combined into one list.
    """
    pytest.skip("not implemented")


def test_query_ship_l_ship_main_weapon_resolves_to_its_own_ship_locked_gun():
    """Regression check against tests/outputs/query_ship_components/
    boron_destroyer.json: an L ship's main "weapon" hardpoint, whose
    compatibility class is a ship-model-specific token rather than a
    generic tier, resolves to exactly one compatible weapon -- its own
    dedicated main gun.
    """
    pytest.skip("not implemented")


# --- main -------------------------------------------------------------

def test_main_outputs_one_entry_per_input_identifier_in_order():
    pytest.skip("not implemented")


def test_main_mixed_valid_and_invalid_identifiers_in_one_request():
    """Regression check against tests/outputs/query_ship_components/
    multi_ship_with_invalid.json: a resolvable ship and an unresolvable one
    in the same "ships" list each get their own correctly-shaped entry.
    """
    pytest.skip("not implemented")
