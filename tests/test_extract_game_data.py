"""Stub tests for src/extract_game_data.py. No implementation yet -- each
test documents, via its name and docstring, the behavior it should confirm
once written. All are skipped for now.
"""

import pytest


# --- catalog_files / extension_dirs / game_input_paths -----------------

def test_catalog_files_excludes_signature_catalogs():
    """*_sig.cat files must never be included in the -in list, only real
    numbered/ext_NN.cat catalogs.
    """
    pytest.skip("not implemented")


def test_catalog_files_sorted_in_load_order():
    """01.cat before 02.cat before ... (and ext_01.cat before ext_02.cat),
    since XRCatTool applies later paths' files over earlier ones.
    """
    pytest.skip("not implemented")


def test_extension_dirs_lists_every_installed_extension():
    """Every subfolder of <game_root>/extensions is discovered dynamically
    -- nothing hardcoded, so a newly installed DLC is picked up automatically.
    """
    pytest.skip("not implemented")


def test_game_input_paths_combines_base_and_all_extensions():
    """The full -in catalog list is base game catalogs + every extension's
    catalogs, not just the base game.
    """
    pytest.skip("not implemented")


# --- ship_macro_jobs / ship_component_jobs ------------------------------

def test_ship_macro_jobs_one_job_per_size_class():
    """Exactly one ExtractionJob per size in SHIP_SIZES, each targeting
    assets/units/size_<X>/macros/.
    """
    pytest.skip("not implemented")


def test_ship_component_jobs_include_pattern_excludes_nested_macros_dir():
    """assets/units/size_s/[^/]+\\.xml$ must match a bare component file
    (assets/units/size_s/ship_x.xml) but NOT anything under macros/ or a
    ship's own *_data/ subfolder (extra path segments after size_s/).
    """
    pytest.skip("not implemented")


# --- wares_xml_jobs / extension_suffix ----------------------------------

def test_wares_xml_jobs_base_game_has_no_suffix():
    """The base game's wares.xml job writes to dest_name="wares.xml" (no
    per-extension suffix), using only the base game's own catalogs as
    in_paths (not merged with any extension).
    """
    pytest.skip("not implemented")


def test_wares_xml_jobs_one_job_per_extension_with_own_catalogs_only():
    """Each extension gets its own ExtractionJob whose in_paths is that
    extension's catalogs alone -- never combined with the base game or
    other extensions, since each wares_<suffix>.xml must come from exactly
    one source.
    """
    pytest.skip("not implemented")


def test_extension_suffix_uses_known_mapping():
    """ego_dlc_boron -> "bor", ego_dlc_terran -> "ter", etc., per
    EXTENSION_SUFFIXES.
    """
    pytest.skip("not implemented")


def test_extension_suffix_falls_back_to_stripped_folder_name():
    """An extension not in EXTENSION_SUFFIXES falls back to its folder name
    with the "ego_dlc_" prefix removed, rather than raising.
    """
    pytest.skip("not implemented")


# --- run_job (flattening, dest_name override) ---------------------------

def test_run_job_flattens_nested_catalog_output():
    """XRCatTool always writes matched files nested under their full
    in-catalog path; run_job must copy just the leaf files up into
    job.out_dir flat, discarding the staging directory's structure.
    """
    pytest.skip("not implemented")


def test_run_job_dest_name_renames_single_matched_file():
    """When job.dest_name is set (e.g. the per-extension wares_<suffix>.xml
    jobs), the one matched file is copied under that name instead of its
    original filename.
    """
    pytest.skip("not implemented")


def test_run_job_warns_but_does_not_raise_on_zero_matches():
    """A job whose include_pattern matches nothing (e.g. an extension with
    no new wares) should print a warning and continue, not fail the whole
    run.
    """
    pytest.skip("not implemented")


def test_run_job_raises_on_nonzero_xrcattool_exit_code():
    """A real XRCatTool failure (bad -in path, corrupt catalog, etc.) must
    stop the pipeline, not be silently swallowed like the zero-match case.
    """
    pytest.skip("not implemented")


# --- CLI: --only / --skip / --list-groups -------------------------------

def test_parse_args_only_restricts_to_named_groups():
    pytest.skip("not implemented")


def test_parse_args_skip_excludes_named_groups():
    pytest.skip("not implemented")


def test_parse_args_only_and_skip_combine():
    """--only ships --skip ship_components (say) should run ships jobs
    that aren't also in the skip set.
    """
    pytest.skip("not implemented")


def test_list_groups_does_not_touch_the_filesystem():
    """--list-groups should just print available groups/jobs and exit,
    without requiring XRCatTool.exe or the game install to even exist.
    """
    pytest.skip("not implemented")
