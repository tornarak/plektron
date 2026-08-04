"""The subagent prompt is rendered from `dispatch.md`, never transcribed.

Hand-copying the template put five clauses into a prompt an agent actually ran that
existed nowhere in the doc. The doc then described a prompt nobody sent, the run
measured something unwritten, and anyone debugging the result afterwards would have
been reading the wrong text. Same fault as writing a glyph into a note instead of
citing its codepoint — a normative thing reproduced probabilistically, with nothing
to witness the difference.

Two things are worth pinning. The template must stay locatable and fully
substituted, since a stray `{placeholder}` reaching an agent is a literal brace in
an instruction and a `KeyError` is the good outcome. And the refusals must fire,
because they are `dispatch.md`'s four-store survey made mechanical — the check a
coordinator performs by eye and therefore the one that gets skipped.

Fixtures are built in `tmp_path` rather than read off the live corpus, per this
suite's rule, except where a test is explicitly about the repo's own `dispatch.md`.
"""

from pathlib import Path

import pytest

from harness.dispatch import BEGIN, DOC, END, Unready, build, survey, template

REPO = Path(__file__).resolve().parent.parent.parent


def make_page(root: Path, ref="3-063", *, zones=True, mz=True, gt=False,
              figs=False, exempt=False):
    """The smallest tree `survey` reads: four stores and the exempt list."""
    alto = ('<alto xmlns="http://www.loc.gov/standards/alto/ns-v4#"><Layout>'
            '<Page WIDTH="2550" HEIGHT="3525"><PrintSpace>'
            '<TextBlock ID="b1"><TextLine ID="l1" HPOS="10" VPOS="10" '
            'WIDTH="100" HEIGHT="20"><String CONTENT="hi"/></TextLine></TextBlock>'
            '</PrintSpace></Page></Layout></alto>')
    for store, on in (("gt/zones", zones), ("mz/ocr", mz),
                      ("gt/ocr", gt), ("gt/fig", figs)):
        d = root / store
        d.mkdir(parents=True, exist_ok=True)
        if on:
            (d / f"chukchi-{ref}.xml").write_text(alto, encoding="utf-8")
    lst = root / "gt/zones/_exempt.lst"
    lst.write_text(f"chukchi-{ref}.xml\n" if exempt else "", encoding="utf-8")
    doc = root / DOC
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text((REPO / DOC).read_text(encoding="utf-8"), encoding="utf-8")
    return root


def test_the_repo_template_is_locatable_and_nonempty():
    """Against the live doc: the markers are load-bearing and easy to lose."""
    text = (REPO / DOC).read_text(encoding="utf-8")
    assert text.count(BEGIN) == 1 and text.count(END) == 1
    assert text.index(BEGIN) < text.index(END)
    assert len(template(REPO)) > 2000


def test_every_placeholder_the_template_uses_is_supplied(tmp_path):
    """A `{brace}` left in a prompt is a literal brace in an instruction.

    `str.format` raises `KeyError` on an unsupplied name, so this fails loudly if
    someone adds a placeholder to the doc without teaching `build` about it — which
    is the whole point of keeping the prose in the doc.
    """
    rec = build("3-063", make_page(tmp_path))
    assert "{" not in rec["prompt"] and "}" not in rec["prompt"]


def test_the_survey_is_substituted_not_described(tmp_path):
    rec = build("3-063", make_page(tmp_path))
    assert "**3-063**" in rec["prompt"]
    assert "PP-NNN" not in rec["prompt"]
    assert f"{rec['lines']} lines over {rec['blocks']} zones" in rec["prompt"]


def test_the_figure_clause_says_which_situation_the_page_is_in(tmp_path):
    """The two cases say opposite things about what a `gaps` band means.

    Told the wrong one, an agent reads artwork as a dropped line or discounts a
    real one as artwork — so this cannot be left as a word the reader interprets.
    """
    absent = build("3-063", make_page(tmp_path / "a", figs=False))["prompt"]
    present = build("3-063", make_page(tmp_path / "b", figs=True))["prompt"]
    assert "does NOT exist" in absent and "genuine dropped-line candidate" in absent
    assert "are masked out of the detector" in present
    assert "genuine dropped-line candidate" not in present


def test_a_note_lands_in_the_branch_paragraph(tmp_path):
    rec = build("3-063", make_page(tmp_path), note="Sparse page; watch the gaps.")
    assert "does not exist. Sparse page; watch the gaps." in rec["prompt"]


def test_no_note_leaves_no_dangling_space(tmp_path):
    assert "does not exist.\n" in build("3-063", make_page(tmp_path))["prompt"]


@pytest.mark.parametrize("kw,expected", [
    ({"zones": False}, "No zones, no dispatch"),
    ({"exempt": True}, "not a text page"),
    ({"gt": True}, "independent witness"),
    ({"mz": False}, "ocr predict"),
])
def test_a_page_that_is_not_a_candidate_is_refused_with_its_remedy(
        tmp_path, kw, expected):
    """Refusals, not warnings: a prompt is a thing an agent is about to be spent on.

    `gt` present is the sharp one. A reader sent at a keyed page reads the human
    text through every ALTO verb, so its proposal stops being an independent
    witness — and a named range contains such a page sooner or later.
    """
    with pytest.raises(Unready, match=expected):
        build("3-063", make_page(tmp_path, **kw))


def test_survey_reports_all_four_stores(tmp_path):
    s = survey("3-063", make_page(tmp_path, figs=True, gt=True))
    assert (s["zones"], s["figures"], s["gt"], s["mz"]) == (True, True, True, True)
    assert s["ref"] == "3-063"


def test_a_missing_doc_names_itself_rather_than_raising_a_path_error(tmp_path):
    make_page(tmp_path)
    (tmp_path / DOC).unlink()
    with pytest.raises(Unready, match="only source"):
        template(tmp_path)


def test_a_doc_without_markers_says_so(tmp_path):
    """The markers are the locator, so losing them must not fall back to a guess.

    Finding the block by heading instead would silently pick up whatever prose
    followed `## Template`, which is how a doc edit becomes a prompt edit nobody
    intended.
    """
    make_page(tmp_path)
    (tmp_path / DOC).write_text("# no markers here\n", encoding="utf-8")
    with pytest.raises(Unready, match="prompt:begin"):
        template(tmp_path)
