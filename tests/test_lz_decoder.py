"""LZString decoder in 02_preprocess_hsr.py, checked against vectors made by the reference `lzstring` package."""
import json
from pathlib import Path

import pytest

VECTORS = json.loads((Path(__file__).parent / "lz_vectors.json").read_text(encoding="utf-8"))


def decode(hsr, packed: str) -> str:
    return hsr._lz_decompress(len(packed), 16384, lambda i: ord(packed[i]) - 32)


@pytest.mark.parametrize("name", sorted(VECTORS))
def test_reference_vectors(hsr, name):
    assert decode(hsr, VECTORS[name]["packed"]) == VECTORS[name]["plain"]


def test_decode_backup_roundtrip(hsr, tmp_path):
    payload = {"profiles": {"1": {"name": "Default"}}, "data": {"stores": {}}}
    # build a "srs" backup the same way the site does, using the reference vectors' JSON sample
    sample = VECTORS["json"]
    f = tmp_path / "starrailstation-backup_2026-01-01.dat"
    f.write_text("srs" + sample["packed"], encoding="utf-8")
    assert hsr.decode_backup(f) == json.loads(sample["plain"])
    assert payload  # keeps the fixture shape documented


def test_wrong_header_is_rejected(hsr, tmp_path):
    f = tmp_path / "bad.dat"
    f.write_text("xyz" + VECTORS["simple"]["packed"], encoding="utf-8")
    with pytest.raises(ValueError, match="header"):
        hsr.decode_backup(f)


def test_garbage_does_not_pass_silently(hsr, tmp_path):
    """Truncated / corrupt data must raise (ValueError incl. JSON errors) instead of returning wrong data."""
    packed = VECTORS["long"]["packed"]
    f = tmp_path / "cut.dat"
    f.write_text("srs" + packed[: len(packed) // 2], encoding="utf-8")
    with pytest.raises(ValueError):
        hsr.decode_backup(f)
