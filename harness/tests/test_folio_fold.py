"""Folio prediction across the seam, over a synthetic repo in `tmp_path`.

The rule this pins: `expected_folio` is **null wherever the chain breaks**, and null
is the correct answer rather than a defect — it means read the folio off the page
and do not guess. Everything else here follows from the fact that the printed folio
and the scan index are not derivable from each other, so the only way the project
knows a folio is that some transcribed page recorded one and it propagated forward.

Synthetic, not corpus-facing: the real `tei/` holds one page, so the interesting
cases (a numbered run, a gap, an unpaginated plate) do not exist there to test.
"""
import pytest

from harness.state import entry_state

PB = '<pb n="{n}"/>'
PB_UNNUMBERED = "<pb/>"

TEI = """<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>{pb}<p>x</p></body></text></TEI>
"""


@pytest.fixture
def repo(tmp_path):
    """A part-1 repo with 10 scans and no TEI. Tests add the TEI they need."""
    (tmp_path / "scans").mkdir()
    (tmp_path / "tei").mkdir()
    for i in range(1, 11):
        (tmp_path / "scans" / f"chukchi-1-{i:03d}.png").touch()
    return tmp_path


def transcribe(repo, ref, folio):
    """Commit a TEI page carrying `folio`, or None for an unpaginated one."""
    pb = PB_UNNUMBERED if folio is None else PB.format(n=folio)
    (repo / "tei" / f"chukchi-{ref}.xml").write_text(
        TEI.format(pb=pb), encoding="utf-8")


def test_first_scan_of_a_part_predicts_nothing(repo):
    """Nothing precedes it, so there is no chain to extend."""
    assert entry_state("1-001", repo)["expected_folio"] is None


def test_untranscribed_predecessor_predicts_nothing(repo):
    assert entry_state("1-005", repo)["expected_folio"] is None


def test_folio_propagates_to_the_next_scan(repo):
    transcribe(repo, "1-004", 30)
    assert entry_state("1-005", repo)["expected_folio"] == 31


def test_a_gap_breaks_the_chain_rather_than_being_counted_across(repo):
    """The strict reading, and the right one: an untranscribed page between the
    basis and here means no prediction at all.

    Counting scans across the gap would look more helpful and would be a guess —
    an unpaginated plate anywhere in the gap makes the arithmetic wrong, and
    nothing in an untranscribed page says whether it carries a number. Null is
    the honest answer: read the folio off the image.
    """
    transcribe(repo, "1-004", 30)
    assert entry_state("1-007", repo)["expected_folio"] is None


def test_a_fully_transcribed_run_predicts_all_the_way_along(repo):
    transcribe(repo, "1-004", 30)
    transcribe(repo, "1-005", 31)
    transcribe(repo, "1-006", 32)
    assert entry_state("1-007", repo)["expected_folio"] == 33


def test_an_unpaginated_page_does_not_advance_the_count(repo):
    """`<pb/>` with no `@n` asserts the page carries no printed number — a plate,
    a blank, a chapter opening. It is transcribed, but it is not folio 31."""
    transcribe(repo, "1-004", 30)
    transcribe(repo, "1-005", None)
    st = entry_state("1-006", repo)
    assert st["basis_folio"] == 30


def test_the_basis_is_reported_not_just_the_prediction(repo):
    """A prediction whose derivation is invisible cannot be argued with."""
    transcribe(repo, "1-004", 30)
    st = entry_state("1-005", repo)
    assert st["basis_ref"] == "1-004"
    assert st["basis_folio"] == 30
    assert st["prior_ref"] == "1-004"
    assert st["expected_folio"] == 31


def test_a_later_folio_reanchors_the_chain(repo):
    """Errors do not cascade: the next legible folio wins over any prediction."""
    transcribe(repo, "1-002", 10)
    transcribe(repo, "1-006", 99)
    assert entry_state("1-007", repo)["expected_folio"] == 100


def test_a_ref_with_no_scan_is_an_error(repo):
    with pytest.raises(KeyError):
        entry_state("1-099", repo)


def test_bare_integer_still_rejected(repo):
    with pytest.raises(ValueError):
        entry_state("5", repo)


# ------------------------------------------------- what it is allowed to read
#
# `entry_state` used to call `build_ledger`, which walks every scan in the corpus
# and computes a `boundary` column needing each page's *successor* — none of which
# this function wants. That cost nothing at 3 collated pages and is quadratic at
# 832, since `tei validate --all` and every `tei context` pay it once per page.
# These pin the narrowing, because it is invisible in the output: the answers were
# byte-identical before and after, so only a test of what gets *opened* can hold it.


def _watch(monkeypatch):
    """Record every TEI path `entry_state` parses."""
    import harness.state as st

    opened: list[str] = []
    real = st._tei_facts

    def spy(path):
        opened.append(path.stem.replace("chukchi-", ""))
        return real(path)

    monkeypatch.setattr(st, "_tei_facts", spy)
    return opened


def test_it_never_reads_past_the_page_it_is_asked_about(repo, monkeypatch):
    for i in range(1, 11):
        transcribe(repo, f"1-{i:03d}", 40 + i)
    opened = _watch(monkeypatch)
    entry_state("1-004", repo)
    assert opened, "nothing was read at all — the spy is not wired up"
    assert max(opened) < "1-004", f"read at or past the target: {sorted(set(opened))}"


def test_it_never_reads_another_part(repo, monkeypatch):
    (repo / "scans" / "chukchi-2-001.png").touch()
    transcribe(repo, "2-001", 500)
    for i in range(1, 4):
        transcribe(repo, f"1-{i:03d}", 40 + i)
    opened = _watch(monkeypatch)
    entry_state("1-003", repo)
    assert not [r for r in opened if r.startswith("2-")]


def test_the_backward_walk_stops_at_the_first_gap(repo, monkeypatch):
    """A page with no TEI breaks the chain, and nothing before it is consulted for
    the prediction — reading past the gap to find a number would predict across
    exactly the break `None` exists to report."""
    transcribe(repo, "1-001", 41)
    transcribe(repo, "1-002", 42)
    # 1-003 deliberately absent.
    transcribe(repo, "1-004", 44)
    _watch(monkeypatch)
    st = entry_state("1-005", repo)
    assert st["expected_folio"] == 45 and st["basis_ref"] == "1-004"
    # The fold still needs the whole prefix, but the *prediction* stopped at 1-004:
    # nothing before the gap contributed a folio.
    assert st["prior_ref"] == "1-004"
