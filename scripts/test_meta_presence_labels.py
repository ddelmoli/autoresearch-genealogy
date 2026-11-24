#!/usr/bin/env python3
"""meta_presence_audit: a dated record or organisation LABEL bullet is not a
person entry, while a bullet-form person with no meta block still is. Fixture
vault with placeholder names only."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("AUTORESEARCH_VAULT", tempfile.gettempdir())
import meta_presence_audit as M

TREE = """### Generation 5

**Jane Example** (b. 1801, Somewhereton; d. 1870)
- meta: {id: P-AAAAAA, generation: 5}
- **WWII Draft Registration** (16 OCT 1940, Somewhere County): names him with his birth date.
- **Society of Descendants of Saint Example** (founded 1950, a lineage society)
- **1850 Census Index** (1850, Somewhereton): lists the household.

- **John Example** (b. 1799, Somewhereton; d. 1861)
- **Will Example** (b. 1820; d. 1890)
"""


def main():
    with tempfile.TemporaryDirectory() as d:
        Path(d, "Family_Tree_Fixture.md").write_text(TREE, encoding="utf-8")
        names = sorted(n.strip() for _, n in M.audit(d))
    assert names == ["John Example", "Will Example"], names
    assert M._is_label_bullet("WWII Draft Registration")
    assert not M._is_label_bullet("Will Example")
    print("ok")


if __name__ == "__main__":
    main()
