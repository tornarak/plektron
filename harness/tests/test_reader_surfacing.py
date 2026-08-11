"""Two ways a reader's page reaches the adjudicator's eye: the note, and the diff.

Both halves here exist because the adjudicator was the only thing catching
something, and was catching it by reading every line at full attention.

The failure this closes is `1-099`'s. The review UI de-emphasises a line whose
text matches the CATMuS draft (`.agree`, opacity .62) and exempts a Tier-1 line
from that dimming (`.t1.agree`), because agreement about characters is no
evidence at all about a glyph. `Kuvár` carried `a` + U+0301 — a combining acute
in none of `detectors`' tables — so it raised no Tier-1 badge, matched the draft,
and dimmed. The one line on the page that wanted a ruling was styled exactly like
the forty-four that did not, and the adjudicator's eye did what the styling asked.

So the undimming is earned by the *note*, not by the detector: a reader writing a
note is saying it looked and is not certain, which is the opposite of agreement,
and no table has to know about the character for that to work. The class is the
second half — five colours the adjudicator can learn and then skip on sight,
rather than one undifferentiated amber paragraph per line.
"""
from __future__ import annotations

import json
from pathlib import Path

from harness.proposal_check import ADVISORY, DEFECT, NOTE_CLASSES, check


def _proposal(tmp_path: Path, ref: str, lines: dict) -> Path:
    d = tmp_path / "review" / ref
    d.mkdir(parents=True, exist_ok=True)
    p = d / "proposal.json"
    p.write_text(json.dumps({"lines": lines}), encoding="utf-8")
    return p


def _issues(tmp_path: Path, lines: dict) -> list[dict]:
    # No `ref`, so the corpus arms stay out of it — this file is about the note
    # fields alone, and leave-one-out needs a page identity anyway.
    return check(_proposal(tmp_path, "1-048", lines))


def test_the_vocabulary_is_closed():
    """Five classes, and the set is the contract two modules share — the review
    UI colours off it and `check` refuses off it, so a sixth added in one place
    and not the other is a badge nobody styled."""
    assert NOTE_CLASSES == ("doubt", "semantic", "print", "draft", "layout",
                            "artifact")


def test_an_unknown_class_is_a_defect(tmp_path):
    """Satisfiable by the reader — it typed the word — so it gates."""
    out = _issues(tmp_path, {"1": {"text": "the herd", "note": "speck",
                                   "class": "uncertain"}})
    hit = [i for i in out if "unknown note class" in i["issue"]]
    assert len(hit) == 1
    assert hit[0]["severity"] == DEFECT
    # The message has to carry the vocabulary: a reader that guessed the word
    # once will guess again, and the guard blocks it from reading the reference.
    assert all(c in hit[0]["detail"] for c in NOTE_CLASSES)


def test_a_class_with_no_note_is_a_defect(tmp_path):
    """A badge with nothing behind it costs the adjudicator a stop and pays
    nothing back — worse than silence, because it renders undimmed."""
    out = _issues(tmp_path, {"1": {"text": "the herd", "class": "doubt"}})
    hit = [i for i in out if "no note" in i["issue"]]
    assert len(hit) == 1
    assert hit[0]["severity"] == DEFECT


def test_a_note_with_no_class_is_only_an_advisory(tmp_path):
    """Plainly satisfiable, and still not a gate.

    The class decides which badge the note wears; the undimming that actually
    fixes the `Kuvár` failure happens without it. Gating here would price an
    observation the reader cannot confidently classify at the cost of the note
    itself, and a reader that resolves that by staying silent has been made
    worse by the check.
    """
    out = _issues(tmp_path, {"1": {"text": "the herd", "note": "ink speck"}})
    hit = [i for i in out if "no class" in i["issue"]]
    assert len(hit) == 1
    assert hit[0]["severity"] == ADVISORY
    assert not [i for i in out if i["severity"] == DEFECT]


def test_a_classed_note_raises_nothing(tmp_path):
    for cls in NOTE_CLASSES:
        out = _issues(tmp_path, {"1": {"text": "the herd", "note": "x",
                                       "class": cls}})
        assert not [i for i in out if "class" in i["issue"]], cls


# --- the invented line-final comma -----------------------------------------
#
# Eleven instances across 93 proposals — 1-038 L19, 1-058 L25, 1-079 L21, 1-092
# L18, 1-099 L29, 1-103 L4, 1-104 L33, 1-107 L3, 1-109 L35, 1-110 L3 and L24 —
# none on the page and none in the draft, and every one caught by a human. The
# detector reproduces all eleven and fires on nothing else in the corpus.

ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"


def _rendered(root: Path, lines: dict, draft: dict | None = None) -> str:
    """One page, rendered. By default every proposal line *agrees* with the ALTO,
    so `.agree` is on all of them and the note is the only thing that can lift it.

    `draft` overrides what the ALTO says, which is what the terminal-punctuation
    arm needs: its whole subject is the two disagreeing.
    """
    draft = draft or {}
    from harness.review import page_context
    from harness.web import templates

    def render_queue_html(ref, alto_dir, root, **kw):
        # The renderer returns a context now and the markup is a template, so a
        # test that wants the page goes through the same two steps the server
        # does. One renderer, so the served page and `--html` cannot drift.
        ctx = page_context(ref, alto_dir, root, **kw)
        return templates.get_template("review/page.html").render(
            **ctx, base="/review", static="/static", request=None)

    from harness.tests.conftest import write_scan
    write_scan(root, "1-048")
    body = "".join(
        f'<TextLine ID="mz_1-048_l{i + 1}" HPOS="700" VPOS="{600 + i * 80}" '
        f'WIDTH="1400" HEIGHT="60" '
        f'BASELINE="700 {655 + i * 80} 2100 {655 + i * 80}">'
        f'<Shape><Polygon POINTS="700 {600 + i * 80} 2100 {660 + i * 80}"/>'
        f'</Shape><String CONTENT="{draft.get(str(i), v["text"])}" HPOS="700" '
        f'VPOS="{600 + i * 80}" WIDTH="1400" HEIGHT="60"/></TextLine>'
        for i, v in sorted(((int(k), v) for k, v in lines.items())))
    p = root / "mz" / "ocr" / "chukchi-1-048.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f'<alto xmlns="{ALTO_NS}"><Layout><Page WIDTH="2824" HEIGHT="3897">'
        '<PrintSpace HPOS="400" VPOS="400" WIDTH="2000" HEIGHT="3000">'
        f'<TextBlock ID="mz_1-048_r1" TAGREFS="T1">{body}</TextBlock>'
        "</PrintSpace></Page></Layout>"
        '<Tags><OtherTag ID="T1" TYPE="type" LABEL="MainZone-P"/></Tags></alto>',
        encoding="utf-8")
    _proposal(root, "1-048", lines)
    return render_queue_html("1-048", "mz/ocr", root)


def test_an_agreeing_line_dims_and_a_noted_one_does_not(tmp_path):
    """The regression itself, in one assertion pair.

    Both lines match the draft exactly. Without the note they are the same line
    as far as the styling is concerned, and that sameness is what cost `1-099`.
    """
    html = _rendered(tmp_path, {
        "0": {"text": "the herd was large"},
        "1": {"text": "the herd was large", "note": "acute on this vowel",
              "class": "doubt"},
    })
    quiet = html.split('id="l0"')[0].rsplit('<div class="', 1)[1]
    loud = html.split('id="l1"')[0].rsplit('<div class="', 1)[1]
    assert "agree" in quiet and "noted" not in quiet
    assert "agree" in loud and "noted" in loud


def test_the_badge_names_the_class(tmp_path):
    html = _rendered(tmp_path, {"0": {"text": "a", "note": "reads oddly",
                                      "class": "semantic"}})
    assert "nb-semantic" in html and ">SEMANTIC<" in html


def test_an_unclassed_note_still_lifts_the_dimming(tmp_path):
    """The undimming is the load-bearing half and must not wait on a taxonomy —
    every note written before the vocabulary existed still has to surface."""
    html = _rendered(tmp_path, {"0": {"text": "a", "note": "ink speck"}})
    assert "noted" in html.split("id='l0'")[0].rsplit("<div class='", 1)[1]
    assert "nb-note" in html


def test_an_unknown_class_renders_neutral_rather_than_vanishing(tmp_path):
    """`check` refuses it; the UI must not also swallow it. A note lost between
    a rejected class and an unstyled badge is the one outcome worse than both."""
    html = _rendered(tmp_path, {"0": {"text": "a", "note": "something",
                                      "class": "uncertain"}})
    assert "nb-note" in html and "something" in html
    assert "nb-uncertain" not in html


def _check_with(root: Path, lines: dict, draft: dict | None = None) -> list[dict]:
    """Rendered fixture, checked with a `ref` so the draft arms run at all.

    Without the `ocr/` view there is no ALTO to resolve, the arm returns early,
    and every assertion about it passes for the wrong reason.
    """
    _rendered(root, lines, draft=draft)
    # `check` resolves the draft through `ocr/`, the way a reader's page does —
    # the reading pass sees mz through it until a restore repoints it.
    view = root / "ocr"
    view.mkdir(exist_ok=True)
    link = view / "chukchi-1-048.xml"
    if not link.exists():
        link.symlink_to(root / "mz" / "ocr" / "chukchi-1-048.xml")
    return check(root / "review" / "1-048" / "proposal.json", "1-048", root)


def _checked(root: Path, lines: dict) -> list[dict]:
    """The real shape: the recognizer read the line and stopped where the type
    stopped, and the reader's value carries one mark more."""
    return _check_with(root, lines,
                       {k: v["text"].rstrip(",.;:") for k, v in lines.items()})


def _terminal(out: list[dict]) -> list[dict]:
    return [i for i in out if "line ends" in i["issue"]]


def test_a_comma_the_draft_does_not_have_is_a_defect(tmp_path):
    """The whole class, reduced: the draft is the witness, and it disagrees."""
    hit = _terminal(_checked(tmp_path, {"0": {"text": "afraid of anything unusual,"}}))
    assert len(hit) == 1
    assert hit[0]["severity"] == DEFECT
    assert hit[0]["token"] == ","


def test_a_line_matching_its_draft_raises_nothing(tmp_path):
    assert not _terminal(_checked(tmp_path, {"0": {"text": "afraid of anything unusual"}}))


def test_punctuation_the_draft_also_has_raises_nothing(tmp_path):
    """A sentence really ending in a full stop is the ordinary case and must be
    silent, or the check is noise on every paragraph."""
    assert not _terminal(_check_with(tmp_path, {"0": {"text": "the herd was large."}}))


def test_a_rekeyed_line_is_not_this_finding(tmp_path):
    """`restore`-worthy corrections must stay possible. If the body changed too,
    the reader rewrote the line — which it is entitled to do, and about which this
    detector has no opinion. Only a body identical but for the mark qualifies."""
    assert not _terminal(_check_with(
        tmp_path, {"0": {"text": "afraid of nothing at all,"}},
        {"0": "afraid of anything unusual"}))


def test_a_noted_line_drops_to_advisory(tmp_path):
    """A reader that looked and found the comma genuinely printed must not be
    stuck against a gate it cannot pass — the note is how it says so."""
    hit = _terminal(_checked(tmp_path, {
        "0": {"text": "afraid of anything unusual,",
              "note": "comma confirmed at 4x, @100"}}))
    assert len(hit) == 1
    assert hit[0]["severity"] == ADVISORY


def test_a_closing_bracket_is_not_sentence_punctuation(tmp_path):
    """Structural marks span line breaks as a matter of course; questioning one
    would fire on every wrapped gloss on a vocabulary page."""
    assert not _terminal(_check_with(tmp_path, {"0": {"text": "the herd was large)"}},
                                     {"0": "the herd was large"}))
