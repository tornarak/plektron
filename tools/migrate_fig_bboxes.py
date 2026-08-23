"""Reduce `gt/fig/` to bounding boxes, re-mint block ids, re-key the readings.

    uv run python tools/migrate_fig_bboxes.py           # report
    uv run python tools/migrate_fig_bboxes.py --commit  # write

A one-off, kept afterwards as the record of what was done — `tools/migrate_coords.py`
is the precedent and the reason for the shape. **The logic is not here.** It lives in
`harness/figures.py` (`migrate_page`, `remap_readings`, `migrate_store`) where the
tests can reach it; this file is the driver and nothing else. A migration whose
correctness argument sits in a script that is run once and never imported is a
migration nobody can check afterwards.

What it does, and why each half needs the other:

`gt/fig/`'s 809 blocks each carry a `Shape/Polygon` beside an `HPOS/VPOS/WIDTH/
HEIGHT` bbox, and 395 of those polygons are skewed quads or 5-to-9-gons that
disagree with their own bbox. Nothing has ever read them: every consumer of this
store goes through `figures.read_blocks`, which takes the bbox. So the reduction
writes down what was already being read, and `migrate_store` refuses outright if any
page's numbers move — that equality is the whole argument, not a hope.

Ids become `fig_PP-NNN_NNN` in geometric order, replacing eScriptorium's
`eSc_textblock_ca04178c`. At the time this ran, the 395 hand-read captions lived in
a markdown file of their own and were keyed by a block id's last field, so the two
files were one fact and moved in one commit; a store whose ids shifted and a
readings file still on the old ones reconciled to nothing. **That file has since
been retired** — the ratified caption now lives on the FigDesc block it keys — so
this script cannot be re-run even in principle, on top of the reasons above.

Gate it on both sides with `uv run harness corpus figures` — 252 / 414 / 395 / 395 /
250 with one known unpaired caption (`2-068`, figs. 239 and 240 stacked under two
side-by-side pictures, a real ambiguity) before and after.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness.figures import migrate_store  # noqa: E402


def main() -> int:
    commit = "--commit" in sys.argv[1:]
    out = migrate_store(Path("."), commit=commit)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    # A refusal is an exit 1: the report says which pages drifted, and a caller
    # that pipes this must not read "nothing written" as "nothing to write".
    return 0 if (out["committed"] or not commit) else 1


if __name__ == "__main__":
    raise SystemExit(main())
