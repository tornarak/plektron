"""A gate must be legible to the actor it gates, so it says its exit code out loud.

A groundtruth-reader is refused shell operators — no `; echo $?`, no chaining, no
redirection — and the refusal is right: one plain command at a time is what makes
that surface auditable. But it left the exit code of the verb a reader is measured
by as the one fact about its own work the reader could not obtain. Measured over
the six-reader batch on `1-064`–`1-069`: every refusal that batch was the operator
arm, and the commonest single reach was `proposal check REF; echo "EXIT: $?"` —
four times across three readers, a turn apiece against a budget of eighty.

What is pinned here is the part `$?` could not have carried anyway. `check` exits 0
both when it found nothing and when it found advisories it declines to gate on, and
those are not the same result; the number is identical and the `means` line is not.
So the tests assert the *distinction*, not merely that a row appears — a verdict
that said "exit: 0" and stopped would satisfy a laxer test and teach a reader
nothing it did not already have.
"""

import json

import pytest

# A defect: `resolved` names a codepoint the text does not contain. Chosen because
# it is unambiguously the reader's to fix, which is what makes it gating.
DEFECT = {"3": {"text": "sometimes called Čiñeiˊ-ñew here",
                "resolved": "Čiñeiˊ-ñew = C+U+030C, i, U+0333 COMBINING DOUBLE "
                            "LOW LINE"}}
# An advisory and nothing else: a bare Tier-1 `g` on a dot-prone suffix, with the
# `resolved` field present so the notation arm stays quiet and the advisory is
# alone. Real — this is `1-064` line 39 as its reader keyed it, before the
# adjudicator put the dot back.
ADVISORY = {"39": {
    "text": "More uncommon is taˊɪrgɪn, a peculiar disease",
    "resolved": "taˊɪrgɪn = t, a, U+02CA MODIFIER LETTER ACUTE ACCENT, "
                "U+026A LATIN LETTER SMALL CAPITAL I, r, g, "
                "U+026A LATIN LETTER SMALL CAPITAL I, n",
}}
CLEAN = {"7": {"text": "an ordinary English line"}}


def run(tmp_path, capsys, lines):
    """One page through `main`, returning (exit code, the verdict section)."""
    from harness.cli import main

    d = tmp_path / "review" / "1-064"
    d.mkdir(parents=True)
    (d / "proposal.json").write_text(json.dumps({"lines": lines}),
                                     encoding="utf-8")
    code = main(["--root", str(tmp_path), "proposal", "check", "1-064",
                 "--json"])
    return code, json.loads(capsys.readouterr().out)["verdict"]


def test_the_verdict_row_reports_the_code_the_process_exits_with(tmp_path,
                                                                 capsys):
    """The whole point: the row and `$?` must not be able to disagree.

    They are computed once and returned, rather than printed and then recomputed,
    so this pins the wiring rather than an arithmetic coincidence.
    """
    code, v = run(tmp_path, capsys, DEFECT)
    assert code == 1 and v["exit"] == 1


def test_a_defect_gates_and_the_verdict_says_it_is_the_readers_to_fix(tmp_path,
                                                                      capsys):
    code, v = run(tmp_path, capsys, DEFECT)
    assert code == 1
    assert "1 gating issue" in v["means"] and "again" in v["means"]


def test_clean_and_advisory_only_share_an_exit_code_and_not_a_verdict(tmp_path,
                                                                      capsys):
    """The distinction `$?` cannot carry, and the reason this verb prints prose.

    Both exit 0. A reader that read the number alone could not tell "nothing
    found" from "found something and declined to gate on it" — and the second is
    the case where there is work to do, in the line's `note`.
    """
    clean_code, clean = run(tmp_path, capsys, CLEAN)
    assert clean_code == 0 and "clean" in clean["means"]


def test_an_advisory_alone_exits_zero_and_says_why(tmp_path, capsys):
    code, v = run(tmp_path, capsys, ADVISORY)
    assert code == 0
    assert "no defects" in v["means"]
    # Named as measurement rather than as a fault, because the rule that keeps it
    # from gating is that a gate must be satisfiable by the actor it gates, and a
    # rare-but-correct form cannot be made common.
    assert "measurement" in v["means"] and "note" in v["means"]
    assert "clean" not in v["means"]


@pytest.mark.parametrize("lines,expect", [(CLEAN, 0), (ADVISORY, 0),
                                          (DEFECT, 1)])
def test_the_verdict_is_the_last_section_whatever_it_says(tmp_path, capsys,
                                                          lines, expect):
    """A summary printed before what it summarises is not a summary.

    Asserted for every branch, since the emit happens on one path but the `means`
    is chosen on three, and a future edit could easily move one of them.
    """
    from harness.cli import main

    d = tmp_path / "review" / "1-064"
    d.mkdir(parents=True)
    (d / "proposal.json").write_text(json.dumps({"lines": lines}),
                                     encoding="utf-8")
    assert main(["--root", str(tmp_path), "proposal", "check", "1-064",
                 "--json"]) == expect
    assert list(json.loads(capsys.readouterr().out))[-1] == "verdict"


def test_normalize_distinguishes_nothing_to_do_from_work_it_would_do(tmp_path,
                                                                     capsys):
    """`corpus normalize` was the other verb the readers reached for `$?` on.

    Its two exit-0 cases are the same pair as `check`'s: an empty scan, and a
    scan whose findings do not block but which `--commit` would still rewrite.
    """
    from harness.cli import main

    assert main(["--root", str(tmp_path), "corpus", "normalize", "--all",
                 "--json"]) == 0
    v = json.loads(capsys.readouterr().out)["verdict"]
    assert v["exit"] == 0 and "clean" in v["means"]
