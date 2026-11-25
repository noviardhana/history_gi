"""Lookup parsing (01_fetch_gi_lookup.parse_lookup) and validation (lookup_utils)."""
import json

import lookup_utils as lu

JS = """
export const characters = {
  hutao: { id: 'hutao', name: 'Hu Tao', rarity: 5, element: 'pyro' },
  amber: {
    name: "Amber",
    id: 'amber',
    rarity: 4,
  },
  xiangling: { id: 'xiangling', rarity: '4', name: 'Xiangling' },
};
"""


def test_parse_basic_entries(gi_fetch):
    out = gi_fetch.parse_lookup(JS)
    assert out["hutao"] == {"name": "Hu Tao", "rarity": 5}
    assert out["amber"] == {"name": "Amber", "rarity": 4}          # double quotes + name before id
    assert out["xiangling"] == {"name": "Xiangling", "rarity": 4}  # quoted rarity


def test_window_never_crosses_into_neighbouring_entry(gi_fetch):
    # 'ghost' has no name/rarity of its own: it must stay None, not borrow Hu Tao's or Amber's
    js = "{ id: 'hutao', name: 'Hu Tao', rarity: 5 },\n{ id: 'ghost' },\n{ name: 'Amber', rarity: 4, id: 'amber' }"
    out = gi_fetch.parse_lookup(js)
    assert out["ghost"] == {"name": None, "rarity": None}
    assert out["hutao"]["rarity"] == 5 and out["amber"]["rarity"] == 4


def test_empty_input(gi_fetch):
    assert gi_fetch.parse_lookup("") == {}


GOOD = {str(i): {"name": f"n{i}", "rarity": 4} for i in range(60)}


def test_problems_in_accepts_good_lookup():
    assert lu.problems_in(GOOD, 50) == []


def test_problems_in_flags_small_shrunk_and_invalid():
    assert lu.problems_in({"1": {"name": "a", "rarity": 5}}, 50)
    assert any("shrunk" in p for p in lu.problems_in(dict(list(GOOD.items())[:30]), 10, previous=GOOD))
    bad = {**GOOD, "x": {"name": "", "rarity": 9}}
    msgs = " ".join(lu.problems_in(bad, 10))
    assert "without a name" in msgs and "valid rarity" in msgs


def test_publish_writes_new_file_atomically(tmp_path):
    p = tmp_path / "l.json"
    assert lu.publish_lookup(p, GOOD, 50) == "updated"
    assert json.loads(p.read_text()) == GOOD
    assert not (tmp_path / "l.json.tmp").exists()


def test_publish_keeps_existing_when_new_is_bad(tmp_path):
    p = tmp_path / "l.json"
    lu.publish_lookup(p, GOOD, 50)
    assert lu.publish_lookup(p, {"1": {"name": "a", "rarity": 5}}, 50) == "kept"
    assert json.loads(p.read_text()) == GOOD


def test_publish_fails_without_fallback_and_force_overrides(tmp_path):
    p = tmp_path / "l.json"
    tiny = {"1": {"name": "a", "rarity": 5}}
    assert lu.publish_lookup(p, tiny, 50) == "failed" and not p.exists()
    assert lu.publish_lookup(p, tiny, 50, force=True) == "updated"


def test_finish_exit_codes():
    assert lu.finish({"a": "updated", "b": "kept"}) == 0
    assert lu.finish({"a": "failed"}) == 1


def test_nested_objects_and_braces_in_strings(gi_fetch):
    js = "{ id: 'a', name: 'Brace } Man', meta: { name: 'inner', rarity: 1 }, rarity: 5 }"
    assert gi_fetch.parse_lookup(js)["a"] == {"name": "Brace } Man", "rarity": 5}
