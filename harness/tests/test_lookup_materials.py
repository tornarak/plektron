"""`lexicon lookup` over a 1900 *Materials*-shaped text: Cyrillic keys, the stem
boundary, and the reading pass's `native` list as a selector."""
from __future__ import annotations

import json
import shutil
import unicodedata
from pathlib import Path

import pytest

from harness import marks
from harness.detectors import native_unmatched
from harness.lookup import index, resolve, search

REPO = Path(__file__).resolve().parents[2]
JESUP = REPO / "jesup"
MATERIALS = JESUP / "bogoras-materials"
ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"
REF = "1-022"


def nfd(s: str) -> str:
    return unicodedata.normalize("NFD", s)


def _alto(lines: list[str]) -> str:
    body = "".join(
        f'<TextLine ID="l{i}" HPOS="700" VPOS="{600 + i * 80}" WIDTH="1400" '
        f'HEIGHT="60" BASELINE="700 {655 + i * 80} 2100 {655 + i * 80}">'
        f'<Shape><Polygon POINTS="700 {600 + i * 80} 2100 {660 + i * 80}"/></Shape>'
        f'<String CONTENT="{t}" HPOS="700" VPOS="{600 + i * 80}" WIDTH="1400" '
        f'HEIGHT="60"/></TextLine>' for i, t in enumerate(lines))
    return (f'<alto xmlns="{ALTO_NS}"><Layout><Page WIDTH="2824" HEIGHT="3897">'
            f'<PrintSpace HPOS="400" VPOS="400" WIDTH="2000" HEIGHT="3000">'
            f'<TextBlock ID="r1">{body}</TextBlock></PrintSpace></Page></Layout></alto>')


LINES = [nfd("сказалъ Ајӈан̀ва́т’омъ, что"),
         nfd("а терк-арм-ора́wеðат пришли"),
         nfd("простая строка безъ формъ")]
NATIVE = {"0": nfd("Ајӈан̀ва́т’омъ"), "1": nfd("терк-арм-ора́wеðат")}


@pytest.fixture
def text(tmp_path):
    """A workspace holding the real Jesup config, and a text holding the real
    *Materials* config with one restored page and its reading."""
    ws = tmp_path / "ws"
    (ws / "config").mkdir(parents=True)
    shutil.copy(JESUP / "workspace.json", ws / "workspace.json")
    for name in ("keying.json", "handle.json", "keyboard.json"):
        shutil.copy(JESUP / "config" / name, ws / "config" / name)
    root = ws / "mat"
    (root / "config").mkdir(parents=True)
    pj = json.loads((MATERIALS / "project.json").read_text(encoding="utf-8"))
    (root / "project.json").write_text(json.dumps(
        {k: pj[k] for k in ("stem", "lang", "prose_stands", "parts")}))
    for name in ("keying.json", "handle.json", "marks.json"):
        shutil.copy(MATERIALS / "config" / name, root / "config" / name)
    gt = root / "gt" / "ocr"
    gt.mkdir(parents=True)
    (gt / f"chukchi-materials-{REF}.xml").write_text(_alto(LINES), encoding="utf-8")
    rv = root / "review" / REF
    rv.mkdir(parents=True)
    (rv / "proposal.json").write_text(json.dumps({"ref": REF, "lines": {
        str(i): {"text": t, **({"native": NATIVE[str(i)]} if str(i) in NATIVE else {})}
        for i, t in enumerate(LINES)}}, ensure_ascii=False), encoding="utf-8")
    return root


def _forms(root):
    idx = index(root)
    return {f["form"]: f["key"] for b in idx["buckets"].values()
            for f in b["forms"].values()}, idx


def test_an_inflected_form_is_indexed_as_its_stem(text):
    forms, _ = _forms(text)
    assert nfd("Ајӈан̀ва́т") in forms
    assert not any("’" in f for f in forms)


def test_an_unmarked_native_form_is_indexed_through_the_reading(text):
    """No glyph test can see a native form spelled in Russian letters; the
    reading's `native` list can."""
    forms, _ = _forms(text)
    assert nfd("терк-арм-ора́wеðат") in forms
    assert nfd("простая") not in forms


def test_a_key_resolves_to_the_exact_ratified_glyphs(text):
    t = marks.handle_table(text)
    key = marks.handle_key(nfd("Ајӈан̀ва́т"), t)
    assert key == "Ajn_1an.va't"
    assert resolve(key, text)[0] == nfd("Ајӈан̀ва́т")


def test_a_key_may_raise_a_cyrillic_forms_case(text):
    """`{T…}` asks for the capital of a form attested lowercase; the injective
    table's case pairs make the Cyrillic capital the same letter."""
    from harness.lookup import expand
    t = marks.handle_table(text)
    key = marks.handle_key(nfd("терк-арм-ора́wеðат"), t)
    out, refused = expand("{" + key[0].upper() + key[1:] + "}", text)
    assert (out, refused) == (nfd("Терк-арм-ора́wеðат"), [])


def test_a_cyrillic_query_reaches_the_form(text):
    rows = search([nfd("Ајӈан")], text)["matches"]
    assert [r["form"] for r in rows] == [nfd("Ајӈан̀ва́т")]


def test_a_listed_form_the_editor_corrected_is_reported_not_indexed(text):
    p = text / "review" / REF / "proposal.json"
    doc = json.loads(p.read_text(encoding="utf-8"))
    doc["lines"]["1"]["native"] = nfd("терк-арм-орáwеðат")   # a different accent
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    assert [u["form"] for u in native_unmatched(text)] == [nfd("терк-арм-орáwеðат")]
    assert search(["terk"], text)["native_unmatched"] == 1


def test_a_ratified_form_is_seen_and_a_slip_is_near(text):
    from harness.lookup import standing_of
    assert standing_of(nfd("Ајӈан̀ва́т’а"), text)["status"] == "seen"
    near = standing_of(nfd("Ајнанват"), text)        # hook and accents lost
    assert near["status"] == "near"
    assert [n["form"] for n in near["near"]] == [nfd("Ајӈан̀ва́т")]
    assert standing_of(nfd("Шамонъ"), text)["status"] == "new"


def test_proposal_check_warns_on_a_near_miss_and_a_listed_form_not_in_text(text):
    """A second page lists a hand-keyed slip of a ratified form, and a form its
    text does not set; both are advisories, and the ratified spelling is silent."""
    from harness.proposal_check import check
    rv = text / "review" / "1-023"
    rv.mkdir(parents=True)
    p = rv / "proposal.json"
    p.write_text(json.dumps({"ref": "1-023", "lines": {
        "0": {"text": nfd("и Ајнанват ушелъ"), "native": nfd("Ајнанват")},
        "1": {"text": nfd("про Ајӈан̀ва́т’а"), "native": nfd("Ајӈан̀ва́т’а")},
        "2": {"text": nfd("ничего"), "native": nfd("Ӄора")}}},
        ensure_ascii=False), encoding="utf-8")
    got = {(i["line"], i["issue"]) for i in check(p, "1-023", text)}
    assert ("0", "native form differs from a ratified spelling") in got
    assert ("2", "native form not in the line's text") in got
    assert not any(line == "1" and "native" in what for line, what in got)


def test_the_review_page_shows_seen_near_and_new_from_other_pages_only(text):
    from harness.review import _native_status
    prop = {0: {"native": nfd("Ајӈан̀ва́т’омъ")}, 1: {"native": nfd("Ајнанват")},
            2: {"native": nfd("Ӄора")}}
    other = _native_status("1-023", prop, text)
    assert [s["status"] for i in (0, 1, 2) for s in other[i]] == ["seen", "near", "new"]
    assert nfd("Ајӈан̀ва́т") in other[1][0]["near"]
    # The page that ratified the form is not told it has seen it.
    own = _native_status(REF, {0: {"native": nfd("Ајӈан̀ва́т’омъ")}}, text)
    assert own[0][0]["status"] == "new"


def test_the_floor_line_says_the_reading_selects(text):
    assert "listed them as native" in search(["x"], text)["floor"]
