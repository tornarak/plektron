"""`ocr corrections` — what readers get wrong, aggregated across adjudicated pages.

It lives in `review.py` and in the `ocr` group rather than under `proposal`
because it reads **both** `proposal.json` and `decision.json`, and only that
module owns both — `proposal_check` knows the proposal half alone.

Two properties carry the design and both are pinned here.

**Opcodes run over NFD text**, so a dropped combining mark ranks as an insert of
the mark itself rather than as a replacement of its host word. That is what makes
the ranking legible at all: 37 dropped dots-below over eight pages collapse to one
row, where a word-level diff would have scattered them across 37 unmatchable ones.

**`--since` is not a convenience.** The store spans the project's own history, and
its leading class is 117 straight apostrophes on two pages keyed before a bare
apostrophe became its own unconditional error — a class that cannot recur in that
form. An unscoped run therefore reads as a live error profile when it is partly
archaeology. A page carrying no `saved_at` is excluded *and named*, never dropped:
dropped, it would be indistinguishable from a page with nothing to report, which
is the blank-vs-`?` rule `_ink_cache.json` states for the zone editor's page list.
"""
from __future__ import annotations

import json
import unicodedata

from harness.review import corrections

DOT_BELOW = "̣"


def _page(root, ref, proposal, decision, saved_at="2026-08-01T00:00:00-0400"):
    d = root / "review" / ref
    d.mkdir(parents=True, exist_ok=True)
    (d / "proposal.json").write_text(json.dumps(
        {"lines": {k: {"text": v} for k, v in proposal.items()}},
        ensure_ascii=False), encoding="utf-8")
    doc = {"ref": ref, "lines": {k: {"text": v, "edited": proposal.get(k) != v}
                                 for k, v in decision.items()}}
    if saved_at is not None:
        doc["saved_at"] = saved_at
    (d / "decision.json").write_text(json.dumps(doc, ensure_ascii=False),
                                     encoding="utf-8")
    return d


def _row(rep, change):
    return next((c for c in rep["changes"] if c["change"] == change), None)


def test_a_dropped_dot_below_is_an_insert_of_the_mark(tmp_path):
    """The whole reason the diff is character-level and NFD.

    `g` -> `g̣` is an *insertion of U+0323*, not a replacement of `g̣ɪnuˊn`. Word-level
    or NFC-level, the same defect on two different stems would be two rows and
    neither would ever reach the top of a frequency table.
    """
    _page(tmp_path, "1-001",
          {"0": "vaˊɪrgɪt", "1": "gɪnuˊn"},
          {"0": "vaˊɪrg̣ɪt", "1": "g̣ɪnuˊn"})
    rep = corrections(tmp_path)
    row = _row(rep, f"'' -> {DOT_BELOW!r}")
    assert row is not None, [c["change"] for c in rep["changes"]]
    assert row["count"] == 2
    assert row["pages"] == "1-001"


def test_a_whole_line_rewrite_collapses_to_a_size(tmp_path):
    """A retype must not mint a row nothing else can ever match.

    Uncapped, every rewritten line becomes its own unique `change` string and the
    table degrades from a frequency ranking into a list of one-offs — the same
    failure `zones check`'s adjacent-band merge exists to prevent, where 38 rows
    for one missing region buried the finding.
    """
    _page(tmp_path, "1-001",
          {"0": "Eččaiˊ . . . . . . . . . . ."},
          {"0": "ᴇččaiˊ"})
    rep = corrections(tmp_path)
    assert any(c["change"].startswith("<") and "ch> -> <" in c["change"]
               for c in rep["changes"]), [c["change"] for c in rep["changes"]]


def test_an_unchanged_page_reports_zero_and_still_appears(tmp_path):
    """`by_page` is a census of pages read, not a list of pages with findings."""
    _page(tmp_path, "1-001", {"0": "abc"}, {"0": "abc"})
    rep = corrections(tmp_path)
    assert rep["pages_read"] == 1
    assert rep["changed"] == 0
    assert rep["by_page"][0]["top_change"] == ""


def test_since_excludes_an_earlier_page(tmp_path):
    _page(tmp_path, "1-001", {"0": "a'b"}, {"0": "aˊb"},
          saved_at="2026-07-30T00:00:00-0400")
    _page(tmp_path, "1-002", {"0": "gɪ"}, {"0": "g̣ɪ"},
          saved_at="2026-08-02T00:00:00-0400")
    rep = corrections(tmp_path, since="2026-07-31")
    assert rep["pages_read"] == 1
    assert [c["pages"] for c in rep["changes"]] == ["1-002"]


def test_an_unstamped_page_under_since_is_named_not_dropped(tmp_path):
    """Excluded silently, it would read as a page with nothing to report.

    The two states must not draw in the same column — see the module docstring.
    """
    _page(tmp_path, "1-001", {"0": "gɪ"}, {"0": "g̣ɪ"}, saved_at=None)
    rep = corrections(tmp_path, since="2026-07-31")
    assert rep["pages_read"] == 0
    assert rep["skipped_unstamped"] == "1-001"


def test_no_since_reads_an_unstamped_page_normally(tmp_path):
    """The exclusion belongs to `--since`, not to the verb."""
    _page(tmp_path, "1-001", {"0": "gɪ"}, {"0": "g̣ɪ"}, saved_at=None)
    rep = corrections(tmp_path)
    assert rep["pages_read"] == 1
    assert rep["skipped_unstamped"] == ""


def test_refs_scopes_the_walk(tmp_path):
    _page(tmp_path, "1-001", {"0": "gɪ"}, {"0": "g̣ɪ"})
    _page(tmp_path, "1-002", {"0": "gɪ"}, {"0": "g̣ɪ"})
    assert corrections(tmp_path, refs=["1-002"])["pages_read"] == 1


def test_a_page_without_a_decision_is_not_read(tmp_path):
    """2-030 is the live instance: adjudicated by an earlier route, no proposal."""
    d = tmp_path / "review" / "1-001"
    d.mkdir(parents=True)
    (d / "proposal.json").write_text('{"lines": {"0": {"text": "x"}}}',
                                     encoding="utf-8")
    assert corrections(tmp_path)["pages_read"] == 0


def test_every_cell_is_scalar_so_the_toon_table_stays_tabular(tmp_path):
    """`pages` is space-joined, the `suggest_native_forms` precedent.

    One list-valued cell degrades the whole record list from a header plus rows
    to the verbose nested form (`harness/emit.py`), which is the encoding this
    project chose TOON to avoid.
    """
    _page(tmp_path, "1-001", {"0": "gɪ"}, {"0": "g̣ɪ"})
    _page(tmp_path, "1-002", {"0": "gɪ"}, {"0": "g̣ɪ"})
    rep = corrections(tmp_path)
    for table in ("changes", "by_page"):
        for rec in rep[table]:
            for v in rec.values():
                assert isinstance(v, (str, int)), (table, rec)
    assert _row(rep, f"'' -> {DOT_BELOW!r}")["pages"] == "1-001 1-002"


def test_precomposed_input_is_normalized_before_diffing(tmp_path):
    """A proposal keyed NFC and a decision keyed NFD are not a correction.

    Without the normalize this reports a spurious replacement on every page whose
    two files happened to be written by different tools — and `set_field` writes
    NFD while a hand-authored proposal may not.
    """
    nfc = unicodedata.normalize("NFC", "ä")
    nfd = unicodedata.normalize("NFD", "ä")
    assert nfc != nfd
    _page(tmp_path, "1-001", {"0": nfc}, {"0": nfd})
    assert corrections(tmp_path)["changed"] == 0
