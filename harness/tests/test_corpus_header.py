"""The corpus teiHeader, and the one thing about it that is mechanically checkable.

A page file is a fragment: it defers title, publication and source to the corpus
header by name, declares no `respStmt` of its own, and `validate` deliberately does
not check that its `@resp` resolves locally. That deferral is correct, and it means
**nothing in the per-page gate can notice if the header stops declaring the ranks
the gate enforces**. Two files, one fact, no link — the shape that cost this project
18 pages of transcription when a file's role lived only in its directory name.

So `check_corpus_header` checks the correspondence and not the prose. The tests
below are mostly about the failure directions, since the passing case is the one
that would go on passing anyway.
"""

from __future__ import annotations

from pathlib import Path

from harness.validate import CORPUS_HEADER, RESP_RANKS, check_corpus_header

REPO = Path(__file__).resolve().parent.parent.parent
TEI_NS = "http://www.tei-c.org/ns/1.0"

# Derived, never spelled out. These fixtures held the three ranks literally, so
# adding a fourth (`#gt`) failed four tests that are about licences and root
# elements and have no opinion about how many ranks there are — noise in exactly
# the place a real finding would have to be noticed.
RANK_IDS = tuple(r.lstrip("#") for r in RESP_RANKS)
ALL_RANKS = "".join(f'<respStmt xml:id="{r}"/>' for r in RANK_IDS)


def header(tmp_path: Path, ranks=RANK_IDS, body=None) -> Path:
    stmts = "".join(
        f'<respStmt xml:id="{r}"><resp>{r}</resp><name>x</name></respStmt>'
        for r in ranks
    )
    p = tmp_path / CORPUS_HEADER
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        (
            body
            if body is not None
            else (
                f'<teiHeader xmlns="{TEI_NS}"><fileDesc>'
                f"<titleStmt><title>t</title>{stmts}</titleStmt>"
                f"<publicationStmt><p>p</p></publicationStmt>"
                f"<sourceDesc><p>s</p></sourceDesc>"
                f"</fileDesc></teiHeader>"
            )
        ),
        encoding="utf-8",
    )
    return p


# --------------------------------------------------------- the live header


def test_the_committed_header_passes_its_own_gate():
    assert check_corpus_header(REPO).ok


def test_the_committed_header_declares_every_rank_validate_enforces():
    """The whole point. If someone renames a rank in either file, this fails."""
    rep = check_corpus_header(REPO)
    assert rep.metrics["ranks"] == len(RESP_RANKS)


# --------------------------------------------------------- failure directions


def test_a_missing_header_is_an_error_not_an_absence(tmp_path):
    """It was absent for this project's whole life and everything passed, which is
    exactly why its absence has to be sayable."""
    rep = check_corpus_header(tmp_path)
    assert not rep.ok
    assert "nothing to resolve against" in rep.errors[0]


def test_a_rank_the_gate_knows_but_the_header_omits(tmp_path):
    """Pages may emit '#htr' and it would resolve to nothing on assembly."""
    header(tmp_path, ranks=("ed", "llm"))
    rep = check_corpus_header(tmp_path)
    assert not rep.ok
    assert any("'#htr' is in RESP_RANKS" in e for e in rep.errors)


def test_a_rank_the_header_declares_but_the_gate_rejects(tmp_path):
    """The worse direction: the corpus advertises a rank that `validate` would
    reject on sight, so the header invites output the gate refuses."""
    header(tmp_path, ranks=("ed", "llm", "htr", "reviewer"))
    rep = check_corpus_header(tmp_path)
    assert not rep.ok
    assert any("RESP_RANKS does not know" in e for e in rep.errors)


def test_a_respStmt_with_no_xml_id_is_a_rank_nothing_can_point_at(tmp_path):
    header(
        tmp_path,
        body=(
            f'<teiHeader xmlns="{TEI_NS}"><fileDesc><titleStmt><title>t</title>'
            "<respStmt><resp>anonymous</resp></respStmt>"
            + ALL_RANKS +
            "</titleStmt><publicationStmt><p>p</p></publicationStmt>"
            "<sourceDesc><p>s</p></sourceDesc></fileDesc></teiHeader>"
        ),
    )
    rep = check_corpus_header(tmp_path)
    assert any("carries no xml:id" in e for e in rep.errors)


def test_duplicate_ids_make_resp_ambiguous(tmp_path):
    """lxml refuses a repeated xml:id while parsing, so this surfaces as a parse
    failure rather than reaching the rank comparison. Named separately anyway: two
    ranks answering to one @resp is this gate's own subject, not generic malformed
    XML, and a report saying the latter would send someone looking for a typo."""
    header(tmp_path, ranks=("ed", "ed", "llm", "htr"))
    rep = check_corpus_header(tmp_path)
    assert not rep.ok
    assert any("same xml:id twice" in e for e in rep.errors)


def test_the_deferred_sections_must_exist(tmp_path):
    """Page fragments say "see corpus teiHeader" by name; if the name is not here
    the deferral resolves to nothing."""
    header(
        tmp_path,
        body=(
            f'<teiHeader xmlns="{TEI_NS}"><fileDesc><titleStmt><title>t</title>'
            + ALL_RANKS +
            "</titleStmt></fileDesc></teiHeader>"
        ),
    )
    rep = check_corpus_header(tmp_path)
    assert any("no <publicationStmt>" in e for e in rep.errors)
    assert any("no <sourceDesc>" in e for e in rep.errors)


def test_malformed_xml_is_reported_not_raised(tmp_path):
    header(tmp_path, body="<teiHeader><oops>")
    rep = check_corpus_header(tmp_path)
    assert not rep.ok
    assert "not well-formed" in rep.errors[0]


# --------------------------------------------------------- unsettled, not wrong


def test_the_committed_header_grants_both_licences():
    """The edition is not one work: the transcription of a 1904 book carries no
    fresh right, the apparatus does. Two <licence> elements, and the gate below
    would fail a settled status with neither."""
    from lxml import etree

    doc = etree.parse(str(REPO / CORPUS_HEADER))
    targets = [c.get("target") for c in doc.getroot().iter(f"{{{TEI_NS}}}licence")]
    assert any("publicdomain/zero" in t for t in targets)
    assert any("licenses/by/4.0" in t for t in targets)


def test_a_settled_status_granting_nothing_is_an_error(tmp_path):
    """The one licence state that reads as finished while saying nothing — the
    same shape as an empty zone page, and caught for the same reason."""
    header(
        tmp_path,
        body=(
            f'<teiHeader xmlns="{TEI_NS}"><fileDesc><titleStmt><title>t</title>'
            + ALL_RANKS +
            "</titleStmt><publicationStmt>"
            '<availability status="free"><p>free!</p></availability>'
            "</publicationStmt><sourceDesc><p>s</p></sourceDesc>"
            "</fileDesc></teiHeader>"
        ),
    )
    rep = check_corpus_header(tmp_path)
    assert not rep.ok
    assert any("grants no <licence>" in e for e in rep.errors)


def test_an_unsettled_licence_is_a_worklist_line_not_a_failure(tmp_path):
    """A header that says the licence is undecided is doing its job. What would be
    wrong is a plausible licence nobody chose."""
    header(
        tmp_path,
        body=(
            f'<teiHeader xmlns="{TEI_NS}"><fileDesc><titleStmt><title>t</title>'
            + ALL_RANKS +
            "</titleStmt><publicationStmt>"
            '<availability status="unknown"><p>undecided</p></availability>'
            "</publicationStmt><sourceDesc><p>s</p></sourceDesc>"
            "</fileDesc></teiHeader>"
        ),
    )
    rep = check_corpus_header(tmp_path)
    assert rep.ok
    assert any("licence has not been chosen" in w for w in rep.worklist)
