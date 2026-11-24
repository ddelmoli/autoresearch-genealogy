#!/usr/bin/env python3
"""person_store.sex: the GEDCOM 7 SEX meta key, read case-insensitively, written with
set_meta_key, and an unrecognised value read as absent (SEX_GRAMMAR reports it)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import person_store as ps

line = "- meta: {id: P-ABCDEF, generation: 9, fs: XXXX-XXX}"
assert ps.sex(line) is None
w = ps.set_meta_key(line, "sex", "F")
assert ps.sex(w) == "F" and "sex: F" in w, w
assert ps.sex(ps.set_meta_key(w, "sex", "M")) == "M"           # replaced, not duplicated
assert ps.set_meta_key(w, "sex", "M").count("sex:") == 1
assert ps.sex("- meta: {id: P-ABCDEF, sex: u}") == "U"
assert ps.sex("- meta: {id: P-ABCDEF, sex: male}") is None
assert ps.raw_sex_value("- meta: {id: P-ABCDEF, sex: male}") == "MALE"
print("sex field: read, write, grammar ok")
