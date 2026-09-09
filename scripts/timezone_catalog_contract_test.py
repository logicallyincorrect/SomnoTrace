#!/usr/bin/env python3
"""Contracts for allocation-free native timezone search."""

from pathlib import Path
import hashlib


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "main/timezone_catalog.c").read_text(encoding="utf-8")
HEADER = (ROOT / "main/timezone_catalog.h").read_text(encoding="utf-8")
CMAKE = (ROOT / "main/CMakeLists.txt").read_text(encoding="utf-8")
NOTICES = (ROOT / "THIRD-PARTY-NOTICES.md").read_text(encoding="utf-8")
ZONES = (ROOT / "main/zones.json").read_bytes()

for symbol in (
    "timezone_catalog_search", "timezone_catalog_lookup",
    "timezone_catalog_search_source", "timezone_catalog_lookup_source",
    "utc_offset", "abbreviation", "posix",
):
    assert symbol in HEADER, f"timezone catalog API omits {symbol}"

for forbidden in ("malloc(", "calloc(", "realloc(", "cJSON"):
    assert forbidden not in SOURCE, f"timezone catalog allocates via {forbidden}"

assert "_binary_zones_json_start" in SOURCE
assert "_binary_zones_json_end" in SOURCE
assert "folded" in SOURCE and "character == ' '" in SOURCE
assert "POSIX signs describe what is added to local time to obtain UTC" in SOURCE
expected_hash = "b95662f059d0bf1408962272cb98da4820fa0e20c7582e0aca1d0613e33986ef"
assert hashlib.sha256(ZONES).hexdigest() == expected_hash
assert expected_hash in NOTICES
assert "93447c0ddac304ca6672a5fd905261c7e8905159" in NOTICES
assert "target_add_binary_data(${COMPONENT_LIB} \"zones.json\" TEXT)" in CMAKE
assert "urllib" not in CMAKE and "gen_tz_db" not in CMAKE

print("timezone catalog contract passed")
