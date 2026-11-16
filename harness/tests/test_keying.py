"""The keying rules compose workspace → text, key by key, and a text's rulings are attested.

`layout.layered` is the prototype chain; `keying.rules` is the one place the
tables are built and checked. The fixtures build a workspace with a text inside
it, because the cases that matter are the ones where a text and its prototype
say different things.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from conftest import JESUP_KEYING, write_project

from harness import keying
from harness.layout import LayerError, layered

BREVE = "̆"


def _ws(tmp_path: Path, text_rules: dict | None = None, ws_rules: dict | None = None) -> Path:
    """A workspace holding the Jesup rules, with one text `t` inside it."""
    ws = tmp_path / "ws"
    (ws / "config").mkdir(parents=True)
    (ws / "workspace.json").write_text('{"title": "fixture"}', encoding="utf-8")
    base = json.loads(JESUP_KEYING.read_text(encoding="utf-8"))
    (ws / "config/keying.json").write_text(json.dumps(ws_rules or base), encoding="utf-8")
    t = write_project(ws / "t")
    (t / "config/keying.json").unlink()      # a text in a workspace inherits by default
    if text_rules is not None:
        (t / "config/keying.json").write_text(json.dumps(text_rules, ensure_ascii=False),
                                              encoding="utf-8")
    return t


def test_a_text_with_no_file_of_its_own_is_its_workspace(tmp_path):
    t = _ws(tmp_path)
    assert keying.rules(t) == keying.workspace_rules(t)
    assert set(keying.rules(t).origin.values()) == {"workspace"}


def test_a_text_adds_one_base_and_inherits_the_rest(tmp_path):
    t = _ws(tmp_path, {"mark_license": {BREVE: {"у": "ў"}},
                       "_why": {f"mark_license.{BREVE}.у": "1-178"}})
    r = keying.rules(t)
    assert r.mark_license[BREVE] == frozenset("uiиИу")
    assert r.origin[("mark_license", BREVE, "у")] == "text"
    assert r.origin[("mark_license", BREVE, "u")] == "workspace"
    assert "у" not in keying.workspace_rules(t).mark_license[BREVE]


def test_a_text_deletes_an_inherited_trap_and_says_why(tmp_path):
    t = _ws(tmp_path, {"lookalike_chars": {"ө": {"_delete": "a letter of this notation"}},
                       "_why": {"lookalike_chars.ө": "1-061 тңэсқан… ө throughout"}})
    r = keying.rules(t)
    assert "ө" not in r.lookalike_chars
    assert r.origin[("lookalike_chars", "ө")] == "text (deleted)"
    assert "ө" in keying.workspace_rules(t).lookalike_chars


def test_a_deletion_without_a_reason_is_refused(tmp_path):
    t = _ws(tmp_path, {"lookalike_chars": {"ө": {"_delete": ""}}})
    with pytest.raises(keying.KeyingError, match="carries its reason"):
        keying.rules(t)


def test_an_override_without_its_attestation_is_refused(tmp_path):
    t = _ws(tmp_path, {"mark_license": {BREVE: {"у": "ў"}}})
    with pytest.raises(keying.KeyingError, match="no `_why`"):
        keying.rules(t)


def test_an_attestation_for_nothing_the_text_sets_is_refused(tmp_path):
    t = _ws(tmp_path, {"_why": {"mark_license.x.y": "stale"}})
    with pytest.raises(keying.KeyingError, match="does not set"):
        keying.rules(t)


def test_a_text_with_no_workspace_is_its_own_base_and_needs_no_attestation(tmp_path):
    # The autouse fixture's text: the Jesup rules in its own config/, no workspace.
    r = keying.rules(tmp_path)
    assert set(r.origin.values()) == {"text"}
    assert r.mark_license[BREVE] == frozenset("uiиИ")


def test_no_rules_anywhere_is_refused_not_defaulted(tmp_path):
    (tmp_path / "config/keying.json").unlink()
    with pytest.raises(keying.KeyingError, match="never against none"):
        keying.rules(tmp_path)


def test_a_workspace_missing_a_table_is_refused(tmp_path):
    base = json.loads(JESUP_KEYING.read_text(encoding="utf-8"))
    del base["tier1_traps"]
    t = _ws(tmp_path, ws_rules=base)
    with pytest.raises(keying.KeyingError, match="tier1_traps"):
        keying.rules(t)


def test_an_orthographic_base_the_mark_is_not_licensed_on_is_refused(tmp_path):
    t = _ws(tmp_path, {"orthographic_bases": {BREVE: {"а": "no"}},
                       "_why": {f"orthographic_bases.{BREVE}.а": "x"}})
    with pytest.raises(keying.KeyingError, match="not licensed on"):
        keying.rules(t)


def test_metadata_is_never_inherited(tmp_path):
    t = _ws(tmp_path, {"_about": "the text's own"})
    merged, _, _ = layered(t, keying.CONFIG)
    assert not any(k.startswith("_") for k in merged)


def test_a_layer_that_is_not_an_object_is_refused(tmp_path):
    t = _ws(tmp_path)
    (t / "config/keying.json").write_text("[]", encoding="utf-8")
    with pytest.raises(LayerError, match="JSON object"):
        layered(t, keying.CONFIG)


def test_a_file_the_workspace_shares_is_judged_by_the_workspace(tmp_path):
    t = _ws(tmp_path, {"mark_license": {BREVE: {"у": "ў"}},
                       "_why": {f"mark_license.{BREVE}.у": "1-178"}})
    shared = t.parent / "edition/entities/person/x.md"
    own = t / "edition/informants.json"
    assert "у" not in keying.rules_for(shared, t).mark_license[BREVE]
    assert "у" in keying.rules_for(own, t).mark_license[BREVE]


JESUP = Path(__file__).resolve().parents[2] / "jesup"


def test_the_chukchee_holds_the_workspace_rules_alone():
    a = keying.rules(JESUP / "bogoras-chukchi")
    assert set(a.origin.values()) == {"workspace"}
    assert a.detectors == keying.DETECTORS - {"footnote_paren_opener"}
    assert a.tier2_scripts == {"Cyrl"}
    assert not a.prose_alphabet


def test_the_1900_books_rulings_are_the_ones_it_attests():
    b = keying.rules(JESUP / "bogoras-materials")
    ruled = {p for p, t in b.origin.items() if t != "workspace"}
    assert ("mark_license", BREVE, "у") in ruled
    for t in ("lookalikes", "tier1_traps", "lookalike_chars", "lookalike_greps"):
        assert "ө" not in getattr(b, t), t          # the barred o is unflagged
    assert b.detectors == {"footnote_paren_opener"} and not b.tier2_scripts
    assert "Cyrl" in b.prose_alphabet


# ------------------------------------------------------------ rule tables


def test_a_text_switches_a_detector_off(tmp_path):
    from harness.detectors import detect_all, medial_cap_positions
    t = _ws(tmp_path, {"detectors": {"word_medial_caps": {"_delete": "no small caps"}},
                       "_why": {"detectors.word_medial_caps": "1-024"}})
    r = keying.rules(t)
    assert not r.on("word_medial_caps") and r.on("dot_above_g")
    assert medial_cap_positions("HɪtoˊLap", r) == []
    types = {f["type"] for f in detect_all(["HɪtoˊLap ġa"], t, lex=set())["tokens"]}
    assert "word_medial_caps" not in types and "dot_above_g" in types


@pytest.mark.parametrize("table,entry", [("detectors", {"medial": "x"}),
                                         ("tier2_scripts", {"Latn": "x"}),
                                         ("prose_alphabet", {"Cyrl": "аб1"})])
def test_a_rule_table_names_only_what_the_code_knows(tmp_path, table, entry):
    key = next(iter(entry))
    t = _ws(tmp_path, {table: entry, "_why": {f"{table}.{key}": "x"}})
    with pytest.raises(keying.KeyingError):
        keying.rules(t)


def test_an_unknown_detector_asked_for_is_a_bug_not_a_no():
    with pytest.raises(KeyError):
        keying.rules(JESUP / "bogoras-chukchi").on("medial")


@pytest.mark.parametrize("token,native", [
    ("Ајңаѝва́т’омъ", True),     # ј ң, and accents
    ("Кутјэ́ўт", True),          # ў is a breve the prose does not discount
    ("мулэмyl", True),           # Latin inside a Cyrillic token
    ("тѵмң-", True),             # ѵ is left out of the prose alphabet on purpose
    ("Tоже", True),              # an OCR slip into Latin is loud, not skipped
    ("Чукотскій", False),        # й is и + an orthographic breve
    ("Лейпцигѣ.", False),
    ("миѳологическаго", False),
])
def test_the_1900_text_judges_a_cyrillic_token_by_its_glyphs(token, native):
    from harness.detectors import bears_inventory, tier2
    b = keying.rules(JESUP / "bogoras-materials")
    nfd = __import__("unicodedata").normalize("NFD", token)
    assert not tier2(nfd, b)
    assert bears_inventory(nfd, b) is native


def test_the_chukchee_still_excludes_cyrillic_whole():
    from harness.detectors import tier2
    a = keying.rules(JESUP / "bogoras-chukchi")
    assert tier2("Ајңанват", a) and not tier2("Aiñanwaˊt", a)


def test_a_book_that_prints_the_apostrophe_calls_a_straight_one_a_slip():
    from harness.detectors import apostrophe_flags
    a = keying.rules(JESUP / "bogoras-chukchi")
    b = keying.rules(JESUP / "bogoras-materials")
    assert [h["kind"] for h in apostrophe_flags("Ајңанват'омъ", b)] == ["prose"]
    assert b.tier1_traps["'"] == "’"
    assert [h["kind"] for h in apostrophe_flags("kaˊle'", a)] == ["unlicensed"]


def test_the_1900_text_folds_its_ruled_sorts_and_the_chukchee_folds_nothing():
    b = keying.rules(JESUP / "bogoras-materials")
    assert b.fold("Ӄаават-ешқан Қ") == "Ӄаават-ешӄан Ӄ"
    assert b.fold("кырңат Ң") == "кырӈат Ӈ"
    assert b.fold("кәңәштумђа") == "кэӈэштумђа"          # ђ is a letter, not a fold
    assert b.fold("ЭӀэнді міӏӄыр") == "Эlэнді міlӄыр"   # the palochka is the tall l
    assert b.fold("лын") == "лын"            # Russian л stays; only the palochka folds
    nfd = __import__("unicodedata").normalize
    # A sequence is taken whole: ď is d + U+030C, and folds to one eth.
    assert b.fold(nfd("NFD", "-ора́wеďат")) == nfd("NFD", "-ора́wеðат")
    # The Latin ä a layer keys becomes Cyrillic а with its diaeresis.
    assert b.fold(nfd("NFD", "аӄälilэткін")) == "аӄӓlilэткін"
    assert b.fold("dа d") == "dа d"            # a bare d is no forked d


def test_a_fold_key_may_not_begin_with_a_mark(tmp_path):
    t = _ws(tmp_path, {"folds": {"̌": "x"}, "_why": {"folds.̌": "x"}})
    with pytest.raises(keying.KeyingError, match="a letter and its marks"):
        keying.rules(t)
    assert keying.rules(JESUP / "bogoras-chukchi").folds == {}


@pytest.mark.parametrize("folds", [{"қ": "ӄӄ"}, {"қ": "қ"}, {"қ": "ӄ", "ӄ": "к"},
                                   {"x": "–"}])
def test_a_fold_is_one_sort_to_another_and_never_a_chain(tmp_path, folds):
    t = _ws(tmp_path, {"folds": folds, "_why": {f"folds.{k}": "x" for k in folds}})
    with pytest.raises(keying.KeyingError, match="folds"):
        keying.rules(t)


def test_normalize_reports_a_fold_and_commit_writes_it(tmp_path):
    from harness.normalize import convert, scan
    t = _ws(tmp_path, {"folds": {"қ": "ӄ"}, "_why": {"folds.қ": "the editor, 2026-11-07"}})
    p = t / "edition" / "toc.json"
    p.parent.mkdir(exist_ok=True)
    p.write_text(json.dumps({"x": "ешқан"}, ensure_ascii=False), encoding="utf-8")
    hits = scan(t)["fold_offenders"]
    assert [(h["path"], h["token"], h["to"]) for h in hits] == \
        [("edition/toc.json", '"ешқан"}', "ӄ")]
    assert convert(t)["changed"][0]["path"] == "edition/toc.json"
    assert json.loads(p.read_text(encoding="utf-8")) == {"x": "ешӄан"}
    assert scan(t)["fold_offenders"] == []


def test_no_module_holds_a_notation_table_as_a_constant():
    """The tables are data; a constant beside them would be a second copy that
    one text's override cannot reach, which is the bypass this layering closes."""
    names = ("INVENTORY_CHARS", "LOOKALIKES", "TIER1_TRAPS", "MARK_LICENSE",
             "ORTHOGRAPHIC_BASES", "LOOKALIKE_CHARS", "LOOKALIKE_SEQS",
             "LOOKALIKE_GREPS", "LOOKALIKE_SEQ_GREPS", "NOTATION_CHARS")
    pat = re.compile(rf"^({'|'.join(names)})\s*[:=]", re.M)
    pkg = Path(__file__).resolve().parents[1]
    hits = [f"{p.relative_to(pkg)}: {m.group(1)}" for p in pkg.rglob("*.py")
            if "tests" not in p.parts for m in pat.finditer(p.read_text(encoding="utf-8"))]
    assert not hits, hits


def test_a_fold_leaves_the_alto_provenance_that_records_it(tmp_path):
    """`ocr import` writes the folds it applied into the ALTO `<Description>`;
    restored to `gt/ocr/`, that record must neither report nor be rewritten."""
    from harness.normalize import convert, scan
    t = _ws(tmp_path, {"folds": {"қ": "ӄ"}, "_why": {"folds.қ": "the editor, 2026-11-07"}})
    p = t / "gt" / "ocr" / "x-1-001.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('<alto xmlns="http://www.loc.gov/standards/alto/ns-v4#">\n'
                 '<Description><Processing><processingStepSettings>in.folds: қ&gt;ӄ'
                 '</processingStepSettings></Processing></Description>\n'
                 '<Layout><String CONTENT="ешқан"/></Layout></alto>\n', encoding="utf-8")
    assert [h["line"] for h in scan(t)["fold_offenders"]] == [3]
    convert(t)
    text = p.read_text(encoding="utf-8")
    assert "in.folds: қ&gt;ӄ" in text and 'CONTENT="ешӄан"' in text
    assert scan(t)["fold_offenders"] == []
