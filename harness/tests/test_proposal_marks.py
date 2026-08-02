"""`proposal marks` — the character-distribution check, and the traps in it.

Four things here are load-bearing and each failed silently at least once while
being written, which is why they are pinned rather than trusted:

**Bare-site subtraction.** `g̣` is `g` + U+0323, so every dotted `g` also contains
a bare one. Counting the confusable naively counted the whole axis: `g-dot` read
48.4% against the corpus's true 93.9%, which put it above `rare_max_pct` and
switched off the `rare` arm for the one contrast it was written for. A wrong
number inside a plausible range, disabling a check, with nothing to say so.

**The fold's case behaviour, in both directions.** Collapsing case must suppress
`äˊmmê`/`Äˊmmê` and must not suppress `I`/`ɪ`. It works only because U+026A has no
case mapping, which is a property of Unicode rather than of this code, so it is
asserted directly.

**Leave-one-out.** After `restore` a page's ground truth is the adjudicated
descendant of its own proposal, so a prior containing the page under test compares
a proposal against its own output — the two-witnesses-that-are-one failure the
verbatim firewall, `review`'s span diff and `zones score`'s `unseen` row have each
produced in turn. Exclusion is unconditional, not conditional on presence: the
conditional form is the same rule with a step where it can be forgotten.

**Types, not tokens.** `2-036`'s 10% `ɪ`-share is one word four times. Per-token
counting turns lexical repetition into a distributional claim.
"""
from __future__ import annotations

import json
import unicodedata

import pytest

from harness.marks import (
    MarksConfigError,
    fold,
    is_medial,
    load_config,
    marks,
    sites,
)

DOT = "̣"          # U+0323 combining dot below
G_DOT = "g" + DOT
CFG = {
    "contrasts": [
        {"name": "g-dot", "expected": G_DOT, "confusable": "g",
         "position": "any", "spec": "5.1"},
        {"name": "smallcap-i", "expected": "ɪ", "confusable": "i",
         "position": "any", "spec": "5.2"},
        {"name": "smallcap-I", "expected": "ɪ", "confusable": "I",
         "position": "initial", "spec": "5.2"},
    ],
    "rare_max_pct": 10.0,
    "min_types": 5,
}


def nfd(s):
    return unicodedata.normalize("NFD", s)


def _config(root, cfg=None):
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "data" / "marks_config.json").write_text(
        json.dumps(cfg or CFG, ensure_ascii=False), encoding="utf-8")


def _proposal(root, ref, lines, name="proposal"):
    d = root / "review" / ref
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.json").write_text(
        json.dumps({"lines": {str(i): {"text": nfd(t)} for i, t in enumerate(lines)}},
                   ensure_ascii=False), encoding="utf-8")


def _gt(root, ref, lines):
    """A ground-truth ALTO carrying one String per line — what feeds the prior."""
    d = root / "gt" / "ocr"
    d.mkdir(parents=True, exist_ok=True)
    body = "".join(
        f'<TextLine ID="l{i}"><String CONTENT="{nfd(t)}"/></TextLine>'
        for i, t in enumerate(lines))
    (d / f"chukchi-{ref}.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<alto xmlns="http://www.loc.gov/standards/alto/ns-v4#"><Layout><Page>'
        f"<PrintSpace><TextBlock ID=\"b1\">{body}</TextBlock></PrintSpace>"
        "</Page></Layout></alto>", encoding="utf-8")


# --- the bare-site subtraction ------------------------------------------------

def test_a_dotted_g_is_not_also_a_bare_g():
    """The trap that disabled the `rare` arm. See the module docstring."""
    c = CFG["contrasts"][0]
    exp, bare = sites(nfd("vaˊɪrg̣ɪt"), c)
    assert len(exp) == 1
    assert bare == []


def test_a_bare_g_is_counted_bare():
    exp, bare = sites(nfd("vaˊɪrgɪt"), CFG["contrasts"][0])
    assert exp == []
    assert len(bare) == 1


def test_disjoint_contrasts_are_unaffected_by_the_subtraction():
    """`ɪ`/`i` share no prefix, so nothing is covered and both sides count."""
    exp, bare = sites(nfd("miluteˊmkɪn"), CFG["contrasts"][1])
    assert len(exp) == 1 and len(bare) == 1


# --- position -----------------------------------------------------------------

def test_the_position_predicate_agrees_with_medial_caps():
    """`is_medial` generalises `detectors.MEDIAL_CAPS` to the small caps.

    Over every ASCII A/E/I/L position in `gt/ocr/` the two never disagree; this
    pins the shape on the cases that matter, so a future edit to either cannot
    drift them apart unnoticed. A hyphen is not a letter, so an element-initial
    capital in a compound reads as initial — which MEDIAL_CAPS's own lookbehind
    class, carrying no hyphen, already decided.
    """
    from harness.detectors import MEDIAL_CAPS

    for tok in ("Iluˊkälin", "ᵉIᵋñɪt-qeˊñu", "Eleˊ-yiˊᵋlhɪn", "ČêˊLo-maˊᵋqɪm"):
        t = nfd(tok)
        mine = {i for i, ch in enumerate(t) if ch in "AEIL" and is_medial(t, i)}
        assert mine == {m.start() for m in MEDIAL_CAPS.finditer(t)}, tok


def test_an_initial_scoped_contrast_ignores_a_medial_confusable():
    c = CFG["contrasts"][2]          # smallcap-I, position: initial
    assert sites(nfd("ČêˊLo"), {**c, "confusable": "L"})[1] == []


def test_an_initial_scoped_contrast_counts_a_word_initial_confusable(tmp_path):
    """`Iᵋplɪˊlɪ` — the census's two `I`->`ɪ` corrections, both word-initial.

    Word-medial uppercase belongs to MEDIAL_CAPS, whose claim is sharper; this
    arm exists for the position MEDIAL_CAPS is blind to by construction.
    """
    assert len(sites(nfd("Iᵋplɪˊlɪ"), CFG["contrasts"][2])[1]) == 1


# --- the fold -----------------------------------------------------------------

def test_smallcap_i_has_no_case_mapping():
    """The Unicode property the whole suppression rests on."""
    assert "I".casefold() == "i"
    assert "ɪ".casefold() == "ɪ"
    assert "Ä".casefold() == "ä".casefold()


def test_the_fold_buckets_the_two_spellings_together():
    cs = CFG["contrasts"]
    assert fold(nfd("neˊlyiᵋ"), cs) == fold(nfd("neˊlyɪᵋ"), cs)
    assert fold(nfd("Iᵋplɪˊlɪ"), cs) == fold(nfd("ɪᵋplɪˊlɪ"), cs)


def _conflict_folds(tmp_path, batch_lines, gt_lines=()):
    _config(tmp_path)
    _proposal(tmp_path, "1-001", batch_lines)
    if gt_lines:
        _gt(tmp_path, "1-002", gt_lines)
    return {c["fold"] for c in marks(["1-001"], tmp_path)["conflict"]}


def test_conflict_fires_on_two_spellings_of_one_word(tmp_path):
    assert _conflict_folds(tmp_path, ["neˊlyiᵋ neˊlyɪᵋ"])


def test_conflict_fires_on_uppercase_against_smallcap(tmp_path):
    """The case the fold must NOT suppress."""
    assert _conflict_folds(tmp_path, ["Iᵋplɪˊlɪ ɪᵋplɪˊlɪ"])


def test_conflict_is_silent_on_a_capitalization_only_pair(tmp_path):
    """4 of the store's 7 multi-spelling folds are this, and legitimately so."""
    assert _conflict_folds(tmp_path, ["äˊmmê Äˊmmê"]) == set()


def test_conflict_sees_the_store_as_a_second_witness(tmp_path):
    """`2-040` live: the proposal keys `vaˊɪrgɪt`, `2-033`'s gt has `vaˊɪrg̣ɪt`."""
    _config(tmp_path)
    _proposal(tmp_path, "1-001", ["vaˊɪrgɪt"])
    _gt(tmp_path, "1-002", ["vaˊɪrg̣ɪt"])
    hits = marks(["1-001"], tmp_path)["conflict"]
    assert len(hits) == 1
    assert hits[0]["in_batch"] is False
    assert hits[0]["store_forms"] == unicodedata.normalize("NFC", nfd("vaˊɪrg̣ɪt"))


def test_conflict_ignores_a_store_only_disagreement(tmp_path):
    """The store's 3 standing `i`/`ɪ` inconsistencies are not this batch's news.

    Reporting them on every run would bury the batch's own finding — the same
    reason `zones check` merges adjacent ink bands rather than emitting 38 rows
    for one missing region. They are a hand-repair worklist, not a verb's output.
    """
    _config(tmp_path)
    _proposal(tmp_path, "1-001", ["qeˊñu"])
    _gt(tmp_path, "1-002", ["neˊlyiᵋ neˊlyɪᵋ"])
    assert marks(["1-001"], tmp_path)["conflict"] == []


# --- the prior ----------------------------------------------------------------

def test_the_prior_excludes_the_page_under_test(tmp_path):
    """Leave-one-out, and it must hold when the page IS in the store.

    That is the live case: a revision re-reads a page whose gt is the adjudicated
    descendant of this very proposal. Were it included, the proposal would be
    compared against its own output and the two witnesses would be one file.
    """
    _config(tmp_path)
    _proposal(tmp_path, "1-001", ["vaˊɪrgɪt"])
    _gt(tmp_path, "1-001", ["vaˊɪrgɪt"] * 20)     # the page's own gt
    _gt(tmp_path, "1-002", ["vaˊɪrg̣ɪt"] * 20)
    rows = [r for r in marks(["1-001"], tmp_path)["ratio"] if r["contrast"] == "g-dot"]
    # 1-002 alone: every `g` dotted. Had 1-001's own gt counted, the prior would
    # be dragged to ~50% and the page would look ordinary.
    assert {r["prior_pct"] for r in rows} == {100.0}
    assert marks(["1-001"], tmp_path)["prior_pages"] == 1


def test_an_empty_store_leaves_every_arm_silent_rather_than_confident(tmp_path):
    _config(tmp_path)
    _proposal(tmp_path, "1-001", ["vaˊɪrgɪt"])
    rep = marks(["1-001"], tmp_path)
    assert rep["rare"] == [] and rep["conflict"] == []
    assert {r["outside"] for r in rep["ratio"]} == {"?"}


# --- rare ---------------------------------------------------------------------

def test_rare_groups_a_repeated_slip_into_one_weighted_row(tmp_path):
    """A keyer repeats a mistake along the page; four hits is one finding of four.

    Four rows would read as four independent signals, which is the opposite of
    what the concentration in the corrections census actually shows.
    """
    _config(tmp_path)
    _proposal(tmp_path, "1-001", ["vaˊɪrgɪt", "vaˊɪrgɪt", "x", "vaˊɪrgɪt vaˊɪrgɪt"])
    _gt(tmp_path, "1-002", ["vaˊɪrg̣ɪt"] * 20)
    rare = marks(["1-001"], tmp_path)["rare"]
    assert len(rare) == 1
    assert rare[0]["count"] == 4
    assert rare[0]["lines"] == "0 1 3 3"


def test_rare_is_silent_when_the_confusable_is_not_corpus_rare(tmp_path):
    """Which contrasts this arm reaches is derived from the prior, not declared.

    Plain `i` sits around a third of its axis, so `smallcap-i` can never qualify
    — and does not need to: `ratio` and `conflict` carry that contrast.
    """
    _config(tmp_path)
    _proposal(tmp_path, "1-001", ["miluteˊmkin"])
    _gt(tmp_path, "1-002", ["miluteˊmkɪn", "tiˊntin"] * 10)
    assert marks(["1-001"], tmp_path)["rare"] == []


def test_rare_max_is_overridable(tmp_path):
    _config(tmp_path)
    _proposal(tmp_path, "1-001", ["miluteˊmkin"])
    _gt(tmp_path, "1-002", ["miluteˊmkɪn", "tiˊntin"] * 10)
    assert marks(["1-001"], tmp_path, rare_max=99.0)["rare"]


# --- ratio --------------------------------------------------------------------

def _ratio(rep, scope, contrast):
    return next(r for r in rep["ratio"]
                if r["scope"] == scope and r["contrast"] == contrast)


def test_ratio_counts_types_not_tokens(tmp_path):
    """`2-036`'s 10% `ɪ`-share is `Pehiˊttin` x4. Repetition is not evidence.

    Stated as the property rather than as a number: repeating the one plain-`i`
    form four times must not move the share at all. Counted per token it drops
    from 75% to 43%, which is the whole false signal the type count removes.
    """
    _gt(tmp_path, "1-002", ["ɪnpɪ"] * 20)
    _config(tmp_path)
    shares = []
    for n in (1, 4):
        _proposal(tmp_path, "1-001", ["Pehiˊttin"] * n + ["ɪˊčve tuˊmg̣ɪt ᴇnmɪ"])
        row = _ratio(marks(["1-001"], tmp_path, min_types=1), "1-001", "smallcap-i")
        shares.append(row["expected_pct"])
        assert row["types"] == 4
    assert shares[0] == shares[1] == 75.0


def test_a_single_ref_gets_no_pooled_row(tmp_path):
    """`ALL` over one ref would restate that ref's own row under another name.

    "Batch" here means only the refs the caller passed; nothing about the scope is
    inferred from, or scaled to, a single one.
    """
    _config(tmp_path)
    _proposal(tmp_path, "1-001", ["qeˊñu"])
    assert not [r for r in marks(["1-001"], tmp_path)["ratio"]
                if r["scope"] == "ALL"]


def test_a_single_ref_reports_its_rows_however_thin(tmp_path):
    """A silently empty table is indistinguishable from a clean one.

    With no pooled row to fall back on, dropping a thin ref's rows would leave the
    verb saying nothing at all about the page it was pointed at.
    """
    _config(tmp_path)
    _proposal(tmp_path, "1-001", ["ɪˊčve"])
    _gt(tmp_path, "1-002", ["ɪnpɪ"] * 20)
    row = _ratio(marks(["1-001"], tmp_path), "1-001", "smallcap-i")
    assert row["types"] < CFG["min_types"]
    assert row["outside"] == "?"


def test_several_refs_pool_and_drop_the_thin_ones(tmp_path):
    """The coordinator's case: one page is a poor sample, the returned jobs are not."""
    _config(tmp_path)
    _proposal(tmp_path, "1-001", ["ɪˊčve"])                       # thin
    _proposal(tmp_path, "1-003", ["ɪnpɪ ɪˊlhɪn tiˊntin miluˊti Leˊutti"])
    _gt(tmp_path, "1-002", ["ɪnpɪ", "tiˊntin"] * 10)
    _gt(tmp_path, "1-004", ["ɪˊlhɪn", "miluˊti"] * 10)
    rep = marks(["1-001", "1-003"], tmp_path)
    scopes = {r["scope"] for r in rep["ratio"] if r["contrast"] == "smallcap-i"}
    assert scopes == {"1-003", "ALL"}
    assert _ratio(rep, "ALL", "smallcap-i")["types"] == 6


def test_min_types_is_overridable(tmp_path):
    _config(tmp_path)
    _proposal(tmp_path, "1-001", ["ɪˊčve"])
    _gt(tmp_path, "1-002", ["ɪnpɪ", "tiˊntin"] * 10)
    _gt(tmp_path, "1-003", ["ɪnpɪ", "ɪˊlhɪn"] * 10)
    rep = marks(["1-001"], tmp_path, min_types=1)
    assert _ratio(rep, "1-001", "smallcap-i")["outside"] != "?"


def test_a_band_of_one_sample_is_no_band(tmp_path):
    """A range over a single page states nothing, and must not read as a verdict."""
    _config(tmp_path)
    _proposal(tmp_path, "1-001", ["miluteˊmkin"])
    _gt(tmp_path, "1-002", ["ɪnpɪ", "tiˊntin"] * 10)
    row = _ratio(marks(["1-001"], tmp_path, min_types=1), "1-001", "smallcap-i")
    assert row["band_n"] == 1
    assert row["outside"] == "?"


def test_the_band_does_not_move_with_how_many_refs_were_passed(tmp_path):
    """It is a property of the ground truth, not of the caller's argument list.

    A band that widened or narrowed with the number of refs would make the same
    page's verdict depend on what it happened to be run alongside.
    """
    _config(tmp_path)
    for ref in ("1-001", "1-003"):
        _proposal(tmp_path, ref, ["ɪnpɪ ɪˊlhɪn tiˊntin miluˊti Leˊutti"])
    for i, forms in enumerate(("ɪnpɪ ɪˊlhɪn ɪˊčve ɪrgɪn ɪˊttɪ",
                               "tiˊntin miluˊti Leˊutti ruˊltin Pehiˊtti") * 3):
        _gt(tmp_path, f"2-{i:03d}", [forms])
    one = _ratio(marks(["1-001"], tmp_path), "1-001", "smallcap-i")
    two = _ratio(marks(["1-001", "1-003"], tmp_path), "1-001", "smallcap-i")
    assert (one["gt_min_pct"], one["gt_max_pct"], one["band_n"]) == \
           (two["gt_min_pct"], two["gt_max_pct"], two["band_n"])


def test_a_shared_lean_shows_up_in_the_pooled_row(tmp_path):
    """The systemic case, which is the reason the pooled row exists.

    Every job leaning the same way is the prompt or the keying spec, not a reader
    — and no per-page row states it, since each page alone may sit inside the
    per-page band while the pool does not.
    """
    _config(tmp_path)
    for ref in ("1-001", "1-003", "1-005"):
        _proposal(tmp_path, ref, ["tiˊntin miluˊti Leˊutti ruˊltin Pehiˊtti"])
    for i in range(6):
        _gt(tmp_path, f"2-{i:03d}", ["ɪnpɪ ɪˊlhɪn ɪˊčve ɪrgɪn ɪˊttɪ"])
    row = _ratio(marks(["1-001", "1-003", "1-005"], tmp_path), "ALL", "smallcap-i")
    assert row["expected_pct"] == 0.0
    assert row["prior_pct"] == 100.0
    assert row["outside"] == "low"


# --- pages, and the ASCII-degraded reading ------------------------------------

def test_a_page_with_no_tier1_tokens_reports_a_row_of_zero(tmp_path):
    """The failure every arm is blind to: a reading degraded all the way to ASCII.

    Every table would be empty and the batch would look clean, so the sample size
    is reported per ref whether or not anything was found. `types: 0` beside a page
    whose zones promise Tier-1 content is itself the finding.
    """
    _config(tmp_path)
    _proposal(tmp_path, "1-001", ["the wife's sister is on the same lake shore"])
    rep = marks(["1-001"], tmp_path)
    assert rep["pages"] == [{"ref": "1-001", "source": "review/1-001/proposal.json",
                             "tokens": 0, "types": 0}]
    assert rep["rare"] == [] and rep["conflict"] == []


def test_decisions_reads_the_other_file(tmp_path):
    """The pair of runs brackets the adjudication — `2-040`'s whole story."""
    _config(tmp_path)
    _proposal(tmp_path, "1-001", ["vaˊɪrgɪt"])
    _proposal(tmp_path, "1-001", ["vaˊɪrg̣ɪt"], name="decision")
    _gt(tmp_path, "1-002", ["vaˊɪrg̣ɪt"] * 20)
    assert marks(["1-001"], tmp_path)["rare"]
    assert marks(["1-001"], tmp_path, decisions=True)["rare"] == []


def test_a_missing_source_refuses_naming_the_path(tmp_path):
    """`2-030` live: adjudicated by an earlier route, no proposal at all."""
    _config(tmp_path)
    with pytest.raises(FileNotFoundError, match="review/1-001/proposal.json"):
        marks(["1-001"], tmp_path)


# --- the config ---------------------------------------------------------------

def test_a_missing_config_raises(tmp_path):
    with pytest.raises(MarksConfigError, match="no marks config"):
        load_config(tmp_path)


@pytest.mark.parametrize("mutate,match", [
    (lambda c: c.__setitem__("contrasts", []), "non-empty list"),
    (lambda c: c["contrasts"][0].pop("position"), "missing 'position'"),
    (lambda c: c["contrasts"][0].__setitem__("position", "final"), "'any' or 'initial'"),
    (lambda c: c["contrasts"][0].__setitem__("expected", "ġ"), "not NFD"),
    (lambda c: c["contrasts"][0].__setitem__("confusable", "gh"), "one character"),
    (lambda c: c.__setitem__("min_types", 0), "positive int"),
    (lambda c: c.__setitem__("rare_max_pct", -1.0), "positive float"),
])
def test_a_malformed_config_raises_rather_than_defaulting(tmp_path, mutate, match):
    """A contrast dropped for a bad field would make its arm report nothing —
    indistinguishable from a clean batch, which is the whole failure mode here."""
    cfg = json.loads(json.dumps(CFG))
    mutate(cfg)
    _config(tmp_path, cfg)
    with pytest.raises(MarksConfigError, match=match):
        load_config(tmp_path)


def test_the_shipped_config_loads_and_is_nfd():
    """The real file, not a fixture — a precomposed entry would match nothing."""
    from pathlib import Path

    cfg = load_config(Path("."))
    assert [c["name"] for c in cfg["contrasts"]][:2] == ["g-dot", "caron-c"]
    assert cfg["contrasts"][0]["expected"] == G_DOT


# --- folded into `proposal check` ---------------------------------------------

def test_check_gates_on_a_rare_form(tmp_path):
    """The reader's own gate, so a slip is caught before the report is written."""
    from harness.proposal_check import check

    _config(tmp_path)
    _proposal(tmp_path, "1-001", ["vaˊɪrgɪt"])
    _gt(tmp_path, "1-002", ["vaˊɪrg̣ɪt"] * 20)
    issues = check(tmp_path / "review/1-001/proposal.json", "1-001", tmp_path)
    assert [i for i in issues if i["issue"].startswith("rare form")]


def test_check_without_a_ref_skips_the_corpus_arms(tmp_path):
    """Leave-one-out cannot be applied to a page that has not said which it is."""
    from harness.proposal_check import check

    _config(tmp_path)
    _proposal(tmp_path, "1-001", ["vaˊɪrgɪt"])
    _gt(tmp_path, "1-002", ["vaˊɪrg̣ɪt"] * 20)
    assert not [i for i in check(tmp_path / "review/1-001/proposal.json")
                if i["issue"].startswith("rare form")]


def test_check_leaves_the_suffix_witness_alone(tmp_path):
    """Overlap is wanted, not deduplicated.

    A bare `-gɪn` produces both a `suffix_mark_flags` hit and a rare-form issue on
    the same line. They reach one defect from different directions — a measured
    shape and a corpus share — and this project asks for a second witness wherever
    one is cheap. Suppressing either buys a shorter report with a blind spot.
    """
    from harness.proposal_check import check

    _config(tmp_path)
    _proposal(tmp_path, "1-001", ["vaˊɪrgɪn"])
    _gt(tmp_path, "1-002", ["vaˊɪrg̣ɪn"] * 20)
    issues = check(tmp_path / "review/1-001/proposal.json", "1-001", tmp_path)
    on_line_0 = [i["issue"] for i in issues if i["line"] == "0"]
    assert any(i.startswith("rare form") for i in on_line_0)
    assert any(i.startswith("bare suffix") for i in on_line_0)


def test_check_reports_a_repeated_form_once_naming_the_other_lines(tmp_path):
    """An issue record addresses a line; the finding is about a page.

    One row per occurrence would report a keyer's single habit as several
    independent faults — the same reasoning as `rare`'s grouping.
    """
    from harness.proposal_check import check

    _config(tmp_path)
    _proposal(tmp_path, "1-001", ["vaˊɪrgɪt", "x", "vaˊɪrgɪt"])
    _gt(tmp_path, "1-002", ["vaˊɪrg̣ɪt"] * 20)
    rare = [i for i in check(tmp_path / "review/1-001/proposal.json", "1-001",
                             tmp_path) if i["issue"].startswith("rare form")]
    assert len(rare) == 1
    assert rare[0]["line"] == "0"
    assert "lines 2" in rare[0]["detail"]


def test_check_survives_a_clone_with_no_marks_config(tmp_path):
    """The checks that need no corpus must still run where the config is absent."""
    from harness.proposal_check import check

    _proposal(tmp_path, "1-001", ["a'b"])
    assert check(tmp_path / "review/1-001/proposal.json", "1-001", tmp_path)


def test_every_cell_is_scalar_so_the_toon_tables_stay_tabular(tmp_path):
    _config(tmp_path)
    _proposal(tmp_path, "1-001", ["vaˊɪrgɪt neˊlyiᵋ neˊlyɪᵋ"])
    _gt(tmp_path, "1-002", ["vaˊɪrg̣ɪt"] * 20)
    rep = marks(["1-001"], tmp_path)
    for table in ("pages", "rare", "conflict", "ratio"):
        assert rep[table], table
        for rec in rep[table]:
            for v in rec.values():
                assert isinstance(v, (str, int, float, bool)), (table, rec)
