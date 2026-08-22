"""The line record's key set is closed, and something checks it at run time.

`lines.py`'s module docstring has always stated the rule: *every record carries
every key, `None` where it does not apply*. Nothing enforced it. The failure it
guards is quiet and total — the TOON encoder collapses a list of records to a
header plus rows only while they are flat and share one key set, so **one ragged
record de-tabularizes the whole table**, and what a collating model receives
silently becomes the verbose nested form. `context.figures_on_page` already emits
that way, for exactly this reason, which is what the rule was learnt from.

**A `TypedDict` cannot close this and is not asked to.** The defect is a runtime
one — the encoder never sees a type — and `ty` is not a gate in this repo. So
`LINE_FIELDS` is the tuple, `LineRec` is the shape a checker can use, and the
test below is what actually holds the invariant. That is `ISSUE_FIELDS`'
arrangement in `proposal_check.py`, copied deliberately rather than reinvented.

The record is assembled in **three** places — `page_lines` writes eleven keys and
stamps `src`, `mark_figure_overlap` adds the three figure keys, `reading_order`
adds `y_rank` — which is the whole reason the tuple earns its keep: no single
site can be read to learn the shape.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from harness.lines import LINE_FIELDS, LineRec, page_lines

REPO = Path(__file__).resolve().parent.parent.parent
ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"


@pytest.fixture(scope="module")
def real_page() -> list[dict]:
    """A page out of `gt/ocr/`, because the invariant is about what the harness
    actually produces and a hand-built fixture would only test the fixture."""
    src = sorted((REPO / "gt" / "ocr").glob("chukchi-*.xml"))
    if not src:
        pytest.skip("gt/ocr/ is empty in this checkout")
    p = src[0]
    return page_lines(p, REPO, ref=p.stem.replace("chukchi-", ""))


def test_the_tuple_and_the_typed_dict_agree():
    """Two spellings of one fact, held together — the defect shape this repo
    keeps finding. `LineRec` is what a checker reads; `LINE_FIELDS` is what the
    runtime test reads, and neither may drift from the other."""
    assert sorted(LineRec.__annotations__) == sorted(LINE_FIELDS)


def test_every_record_carries_every_key(real_page):
    """The invariant itself, over a real page."""
    assert real_page, "the page produced no lines — this test proves nothing"
    for i, rec in enumerate(real_page):
        assert tuple(rec) == LINE_FIELDS, (
            f"line {i} has keys {tuple(rec)}, not LINE_FIELDS. A record that "
            "differs — even by key *order*, since TOON emits a header — turns "
            "the whole table into the nested form silently."
        )


def test_the_key_order_is_the_declared_order(real_page):
    """Order and not just membership. The encoder writes one header for the
    table, so a record whose keys arrive in a different order is a different
    record to it, however equal the sets are."""
    assert list(real_page[0]) == list(LINE_FIELDS)


def test_the_figure_keys_are_present_on_an_ordinary_line(real_page):
    """The specific case the module docstring calls out: `in_figdesc`,
    `in_graphic` and `figdesc_straddle` are stamped `None` on **every** line, not
    only on the ones inside a figure. That stamping is what keeps the set closed,
    and it is the thing a well-meaning simplification would remove."""
    plain = [r for r in real_page if r["in_figdesc"] is None]
    assert plain, "no ordinary lines on this page"
    for rec in plain:
        for k in ("in_figdesc", "in_graphic", "figdesc_straddle"):
            assert k in rec, f"{k} absent on a line outside any figure zone"


def test_every_value_is_a_scalar(real_page):
    """The other half of the encoder rule, from the docstring: a single nested
    dict or list de-tabularizes the table just as a ragged key set does. Geometry
    is flattened to four ints and `baseline`/`points` stay the space-separated
    strings ALTO already uses, rather than becoming lists of pairs."""
    for i, rec in enumerate(real_page):
        for k, v in rec.items():
            assert not isinstance(v, (dict, list, tuple, set)), (
                f"line {i} field {k!r} holds {type(v).__name__}; TOON needs "
                "scalars to keep the table flat"
            )


def test_the_geometry_is_typed_as_optional():
    """Not decoration. ALTO omits `HPOS` on a line the segmenter gave no box, so
    `rec["hpos"] + rec["width"]` is arithmetic on a possible `None` at every site
    that does it — `generate.py` crashed on exactly that shape,
    `r["vpos"] + r.get("height", 0)` with `vpos` absent. Declaring it is what
    lets a checker find those rather than a person guessing which are guarded."""
    def spelled(k: str) -> str:
        # `from __future__ import annotations` makes these ForwardRef objects
        # rather than the strings they are written as.
        a = LineRec.__annotations__[k]
        return getattr(a, "__forward_arg__", a) if not isinstance(a, str) else a

    for k in ("hpos", "vpos", "width", "height"):
        assert spelled(k) == "int | None", (
            f"{k} is no longer optional in LineRec — if ALTO now guarantees it, "
            "the arithmetic sites can drop their guards and this test should say "
            "so; if not, the annotation is wrong."
        )
