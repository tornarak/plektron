"""`proposal check` gates on defects; advisories report without gating.

The rule this encodes: **a gate must be satisfiable by the actor it gates.** A
defect is a claim that something is wrong and that the reader can put it right.
An advisory is measurement — leave-one-out corpus statistics saying "this shape
is rare, go look" — and a rare-but-correct form cannot be made common. Worse for
the spelling-conflict arm: its second witness is another page, which the firewall
forbids a reader to open, so the one actor who could settle it is the one who is
not allowed to.

Advisories gated anyway until the split, and the damage is what a gate nobody can
pass always does. Eight of the eighteen failing proposals in `review/` failed on
advisories alone; the exit code stopped distinguishing a mistyped combining mark
from a rare surname; and the reading brief had been rewritten to teach readers
that exit 1 is sometimes acceptable — on the one verb whose job is catching
mistyped marks. `measurement never gates` (VERBS.md, Conventions) already said
this; the verb just wasn't obeying it.

What must not regress: an advisory is never made *quieter* by not gating. It
prints, in the same table, carrying its severity. The old behaviour is `--strict`.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.proposal_check import ADVISORY, DEFECT, ISSUE_FIELDS, check, issue

# A line whose only finding is the bare dot-prone suffix: `-gɪn` unmarked, with a
# `resolved` field that correctly names both notation codepoints so the two
# `resolved` arms stay silent. The suffix table keys on ɪ U+026A, not ASCII i —
# with the wrong letter this fixture produces nothing and the test passes vacuously.
ADVISORY_ONLY = {"1": {"text": "Yeˊrgɪn", "resolved": "U+02CA U+026A"}}


def _proposal(tmp_path: Path, ref: str, lines: dict) -> Path:
    d = tmp_path / "review" / ref
    d.mkdir(parents=True)
    p = d / "proposal.json"
    p.write_text(json.dumps({"lines": lines}), encoding="utf-8")
    return p


def test_severity_is_a_field_on_every_record():
    """One record shape whatever detector raised it — a ragged list is not a
    table, and TOON degrades it to the nested form."""
    assert "severity" in ISSUE_FIELDS
    assert set(issue(1, "x")) == set(ISSUE_FIELDS)


def test_the_default_severity_gates():
    """The safe direction: a new detector added without thinking about severity
    fails loudly, rather than landing silently and never firing."""
    assert issue(1, "x")["severity"] == DEFECT


def test_a_mistyped_mark_is_a_defect(tmp_path):
    """`resolved` naming a codepoint the text does not contain — the reader
    typed one of the two, and only they know which."""
    p = _proposal(tmp_path, "1-048",
                  {"1": {"text": "qoraˊɣ", "resolved": "U+0323"}})
    found = check(p)
    assert found, "the fixture stopped producing a mismatch"
    assert all(f["severity"] == DEFECT for f in found), found


def test_a_bare_dot_prone_suffix_is_an_advisory(tmp_path):
    """§5.1's skew says *look*, not *this is wrong* — the shape is legitimately
    bare on some pages, and the reader cannot settle it by fiat."""
    p = _proposal(tmp_path, "1-048", ADVISORY_ONLY)
    sev = {f["severity"] for f in check(p) if "bare suffix" in f["issue"]}
    assert sev == {ADVISORY}, check(p)


@pytest.mark.parametrize("strict,expected", [(False, 0), (True, 1)])
def test_advisories_alone_do_not_gate_unless_strict(tmp_path, capsys, strict,
                                                    expected):
    from harness.tests.test_multi_ref import _run  # the shared CLI harness

    _proposal(tmp_path, "1-048", ADVISORY_ONLY)
    args = ["proposal", "check", "1-048", "--root", str(tmp_path)]
    if strict:
        args.append("--strict")
    code, out, _err = _run(capsys, *args)
    assert code == expected, out
    # Not gating must never mean not reporting: the finding is in the output
    # either way, or this traded a false gate for a blind spot.
    assert "bare suffix" in out
    assert "advisory" in out


# --- a line the store does not have ---------------------------------------

def _alto(tmp_path, ref="1-048", indices=(0, 1)):
    """A store holding exactly the named line indices, under the `ocr/` view."""
    d = tmp_path / "ocr"
    d.mkdir(parents=True, exist_ok=True)
    lines = "".join(
        f'<TextLine ID="l{i}" HPOS="50" VPOS="{100 + i * 60}" WIDTH="500" '
        f'HEIGHT="40"><String CONTENT="x{i}" HPOS="50" VPOS="{100 + i * 60}" '
        f'WIDTH="500" HEIGHT="40"/></TextLine>' for i in indices)
    (d / f"chukchi-{ref}.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<alto xmlns="http://www.loc.gov/standards/alto/ns-v4#"><Layout>'
        '<Page ID="p1" WIDTH="1200" HEIGHT="800"><PrintSpace HPOS="0" VPOS="0" '
        f'WIDTH="1200" HEIGHT="800"><TextBlock ID="b1">{lines}'
        "</TextBlock></PrintSpace></Page></Layout></alto>", encoding="utf-8")
    return tmp_path


def _keyed(tmp_path, keys, ref="1-048"):
    """A proposal that keys exactly `keys`, whatever the store holds.

    Distinct from `_proposal` above, which takes the line records: these tests
    care only about which indices are named.
    """
    p = tmp_path / "review" / ref / "proposal.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(
        {"lines": {k: {"text": f"line {k}"} for k in keys}}), encoding="utf-8")
    return p


def test_a_line_index_the_store_lacks_is_a_defect(tmp_path):
    """`restore` joins on the index, so a key naming no `TextLine` is text with
    no box — the dropped-line case, which belongs in `segmenter_missed`.

    It would otherwise be dropped in silence, which is the whole problem: the
    reading is lost and nothing says a reading was lost.
    """
    root = _alto(tmp_path, indices=(0, 1))
    path = _keyed(tmp_path, ["0", "1", "7"])
    rows = [r for r in check(path, "1-048", root) if "not in the store" in r["issue"]]
    assert [r["line"] for r in rows] == ["7"]
    assert rows[0]["severity"] == DEFECT
    assert "segmenter_missed" in rows[0]["issue"]


def test_every_index_present_reports_nothing(tmp_path):
    """The control — and the one that makes the corpus survey mean something.
    A check that never fires and a corpus with nothing wrong look identical."""
    root = _alto(tmp_path, indices=(0, 1))
    path = _keyed(tmp_path, ["0", "1"])
    assert not [r for r in check(path, "1-048", root)
                if "not in the store" in r["issue"]]


def test_a_page_with_no_alto_is_skipped_not_condemned(tmp_path):
    """Absent is not wrong. Reported, every line of every proposal would fire on
    a fresh clone whose view has not been built."""
    path = _keyed(tmp_path, ["0", "1"])
    (tmp_path / "ocr").mkdir(parents=True, exist_ok=True)
    assert not [r for r in check(path, "1-048", tmp_path)
                if "not in the store" in r["issue"]]


def test_without_a_ref_the_check_is_not_attempted(tmp_path):
    """No ref, no store to resolve — the same rule the corpus-dependent arms
    already follow."""
    root = _alto(tmp_path, indices=(0,))
    path = _keyed(tmp_path, ["0", "9"])
    assert not [r for r in check(path, None, root)
                if "not in the store" in r["issue"]]
