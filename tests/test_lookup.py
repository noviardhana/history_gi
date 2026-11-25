import json

import pytest

ID_FIRST = """export const characters = {
  aino: {
    id: 'aino',
    name: 'Aino',
    rarity: 4,
    stats: { hp: 1 },
  },
  albedo: {
    id: 'albedo',
    name: 'Albedo',
    rarity: 5,
  },
};
"""

NAME_FIRST = """export const weaponList = {
  wolfs_gravestone: {
    name: "Wolf's Gravestone",
    id: 'wolfs_gravestone',
    rarity: 5,
  },
  dull_blade: {
    name: 'Dull Blade',
    id: 'dull_blade',
    rarity: 1,
  },
};
"""

# the second entry has no rarity: it must NOT inherit the one of the entry above it
NO_RARITY = """export const characters = {
  aino: {
    id: 'aino',
    name: 'Aino',
    rarity: 4,
  },
  mystery: {
    id: 'mystery',
    name: 'Mystery',
  },
};
"""


@pytest.fixture(scope="module")
def gi(load_script):
    return load_script("01_fetch_gi_lookup.py")


def test_parse_id_first_layout(gi):
    assert gi.parse_lookup(ID_FIRST) == {"aino": {"name": "Aino", "rarity": 4}, "albedo": {"name": "Albedo", "rarity": 5}}


def test_parse_name_first_layout_with_quotes(gi):
    out = gi.parse_lookup(NAME_FIRST)
    assert out["wolfs_gravestone"] == {"name": "Wolf's Gravestone", "rarity": 5}
    assert out["dull_blade"]["rarity"] == 1


def test_missing_rarity_is_not_taken_from_a_neighbour(gi):
    assert gi.parse_lookup(NO_RARITY)["mystery"] == {"name": "Mystery", "rarity": None}


def test_window_fallback_when_format_is_unknown(gi):
    one_line = "x = [{ id: 'a', name: 'A', rarity: 5 }, { id: 'b', name: 'B', rarity: 4 }]"
    assert gi.parse_lookup(one_line) == {"a": {"name": "A", "rarity": 5}, "b": {"name": "B", "rarity": 4}}


# ---- publish_lookup (validation + atomic write) ----------------------------------
@pytest.fixture(scope="module")
def utils(load_script):
    import lookup_utils
    return lookup_utils


def good(n=60):
    return {str(i): {"name": f"n{i}", "rarity": 4} for i in range(n)}


def test_new_file_is_written(utils, tmp_path):
    path = tmp_path / "l.json"
    assert utils.publish_lookup(path, good(), min_items=50) == "updated"
    assert len(json.loads(path.read_text())) == 60
    assert not list(tmp_path.glob("*.tmp"))


def test_too_small_without_existing_file_fails(utils, tmp_path):
    assert utils.publish_lookup(tmp_path / "l.json", good(10), min_items=50) == "failed"
    assert not (tmp_path / "l.json").exists()


@pytest.mark.parametrize("bad", [
    {**good(), "x": {"name": "x", "rarity": None}},     # no rarity
    {**good(), "x": {"name": None, "rarity": 4}},       # no name
    {**good(), "x": {"name": "x", "rarity": 9}},        # rarity out of range
])
def test_incomplete_download_keeps_the_old_file(utils, tmp_path, bad):
    path = tmp_path / "l.json"
    utils.publish_lookup(path, good(), min_items=50)
    before = path.read_text()
    assert utils.publish_lookup(path, bad, min_items=50) == "kept"
    assert path.read_text() == before


def test_shrunk_download_keeps_the_old_file(utils, tmp_path):
    path = tmp_path / "l.json"
    utils.publish_lookup(path, good(100), min_items=50)
    assert utils.publish_lookup(path, good(60), min_items=50) == "kept"
    assert len(json.loads(path.read_text())) == 100


def test_force_skips_the_checks(utils, tmp_path):
    path = tmp_path / "l.json"
    assert utils.publish_lookup(path, good(5), min_items=50, force=True) == "updated"


def test_finish_exit_codes(utils):
    assert utils.finish({"a": "updated", "b": "kept"}) == 0
    assert utils.finish({"a": "failed"}) == 1
