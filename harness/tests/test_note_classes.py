"""A reader's note carries a class, and a noted line is never dimmed.

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
    assert NOTE_CLASSES == ("doubt", "semantic", "print", "layout", "artifact")


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


# --- the rendering, which is where the failure actually happened ------------

ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"


def _rendered(root: Path, lines: dict) -> str:
    """One page, rendered. Every proposal line here *agrees* with the ALTO, so
    `.agree` is on all of them and the note is the only thing that can lift it.
    """
    from harness.review import render_queue_html
    from harness.tests.conftest import write_scan
    write_scan(root, "1-048")
    body = "".join(
        f'<TextLine ID="mz_1-048_l{i + 1}" HPOS="700" VPOS="{600 + i * 80}" '
        f'WIDTH="1400" HEIGHT="60" '
        f'BASELINE="700 {655 + i * 80} 2100 {655 + i * 80}">'
        f'<Shape><Polygon POINTS="700 {600 + i * 80} 2100 {660 + i * 80}"/>'
        f'</Shape><String CONTENT="{v["text"]}" HPOS="700" '
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
    quiet = html.split("id='l0'")[0].rsplit("<div class='", 1)[1]
    loud = html.split("id='l1'")[0].rsplit("<div class='", 1)[1]
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
