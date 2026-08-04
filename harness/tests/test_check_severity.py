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
