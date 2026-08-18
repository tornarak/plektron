"""The corpus lookup, and the handle that keeps it honest.

A reader may consult ratified ground truth for a recurring native form. That is a
crossing of the rule against deriving a convention from a neighbouring page, and it
is survivable only because of what the handle records: `CLAUDE.md` says a comparison
whose witnesses may be one witness must say so, and a reader that quietly copies a
corpus spelling has collapsed two witnesses into one. `as_typed` is the field that
says so; everything here is the machinery that keeps it truthful.

The live fixture throughout is `Čeˊwɪn` (1-042 L34) / `Čeˊwin` (1-052 L7) — one word
the book sets two ways, exempted in `data/marks_exempt.json` because it is a real
disagreement rather than a keying slip. 1-042's reader flagged it instead of
harmonizing to the older page. Every refusal below exists so the tooling cannot undo
that judgement.
"""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path

import pytest

from harness.detectors import INVENTORY_CHARS, native_corpus
from harness.lookup import (
    _case_rank,
    _raise_case,
    bare,
    expand,
    index,
    resolve,
    search,
)
from harness.marks import HANDLE_MARKERS, handle_key
from harness.proposal_check import check, fix, set_field, set_fields

REPO = Path(__file__).resolve().parent.parent.parent


def nfd(s: str) -> str:
    """**Every literal in this file goes through here**, and the first run of these
    tests is why: an editor composed `č` to U+010D while the store holds `c`+U+030C,
    and five assertions failed against strings that render identically. The corpus
    is NFD corpus-wide (`keying_spec.md` §1); a test asserting in NFC is asserting
    about a string the project does not contain."""
    return unicodedata.normalize("NFD", s)

# Every one attested in `gt/ocr/`; none constructed. `Notaˊs˙qa-vaˊɪrg̣ɪn` carries
# five marker classes and a hyphen at once and is the single best case in the store.
WORKED = {
    "Aiˊwan": "Ai'wan",
    "Kuluˊči": "Kulu'c^i",
    "Kavraˊlɪt": "Kavra'li_t",
    "Nɵˊɵkalɪt": "No_'o_kali_t",
    "taˊɪrg̣ɪn": "ta'i_rg.i_n",
    "Ilh-ɪᵋplɪˊlᴇ": "Ilh-i_e^pli_'le_",
    "Veᵋñ": "Vee^n~",
    "Telqäˊp": "Telqa:'p",
    "Notaˊs˙qa-vaˊɪrg̣ɪn": "Nota's.qa-va'i_rg.i_n",
    "Buks˙unda": "Buks.unda",
}


@pytest.mark.parametrize("form,key", sorted(WORKED.items()))
def test_the_key_marks_every_non_ascii_character(form, key):
    assert handle_key(nfd(form)) == key


def test_the_key_reads_back_as_no_word():
    """The point of the markers, stated as a test.

    A plain-ASCII key would spell `Kavraˊlɪt` as `kavralit` and teach an `i` that is
    not there — to a reader who will key it from memory on a later page, and against
    the corpus's largest correction family. Every form carrying a mark must yield a
    key carrying a marker.
    """
    marked = [nfd(f) for f in WORKED if any(not c.isascii() for c in nfd(f))]
    assert marked
    for f in marked:
        assert any(c in "'_^.~:)=" for c in handle_key(f)), f


def test_case_survives_because_lowercasing_collided():
    """`Aiˊwan` and `aiˊwan` are both attested, and 11 pairs like them.

    Case is legible at any zoom, unlike the dot-below this key exists to stop
    asserting, so the reader types what it sees and the collision disappears.
    """
    assert handle_key(nfd("Aiˊwan")) != handle_key(nfd("aiˊwan"))


def test_an_unmapped_character_raises_rather_than_being_dropped():
    """Silence here is how a new inventory glyph starts producing readable keys."""
    with pytest.raises(ValueError, match="U\\+0301"):
        handle_key(nfd("réduites"))


def test_the_marker_table_reaches_every_inventory_member():
    """Totality against `detectors.INVENTORY_CHARS`, which is the definition."""
    missing = sorted(c for c in INVENTORY_CHARS if c not in HANDLE_MARKERS)
    assert not missing, f"inventory members with no marker: {missing!r}"


def test_no_two_attested_forms_share_a_key():
    """Corpus-wide, over every form in `gt/ocr/`. A collision is fixed by splitting
    the offending marker against the real instance, never by picking a side."""
    keys: dict[str, set[str]] = {}
    for _, tok in native_corpus(REPO):
        try:
            keys.setdefault(handle_key(tok), set()).add(tok)
        except ValueError:
            continue
    assert not {k: sorted(v) for k, v in keys.items() if len(v) > 1}


def test_the_conflict_is_ambiguous_and_survives_the_floor():
    """**The floor must never be able to hide a conflict.**

    `Čeˊwɪn` and `Čeˊwin` have one page each, so a floor counted *per form* would
    delete the corpus's only genuine ambiguity from the lookup instead of refusing
    it. Counted per fold the word has two pages, clears the default, and is refused
    on the ground that matters.
    """
    rows = search(["cewin"], REPO)["matches"]
    forms = sorted(r["form"] for r in rows)
    assert forms == [nfd("Čeˊwin"), nfd("Čeˊwɪn")]
    assert all(r["ambiguous"] and not r["key"] for r in rows)


def test_the_precise_key_is_refused_too():
    """The trap the bucket/key split exists to close.

    Marking distinguishes, so the two spellings have *different* keys — a refusal
    resting on key equality would let a reader name one side of a live conflict by
    spelling it exactly. The refusal is on the fold.
    """
    assert handle_key(nfd("Čeˊwɪn")) != handle_key(nfd("Čeˊwin"))
    for form in (nfd("Čeˊwɪn"), nfd("Čeˊwin")):
        got, why = resolve(handle_key(form), REPO)
        assert got is None
        assert "more than one way" in why


class TestCaseLadder:
    """A handle may be written lowercase, capitalized or uppercase, and an
    attestation in one case enables that case and every case above it.

    The book sets one word three ways by position — `keˊlet` in the body, `Keˊlet`
    opening a sentence, `KEˊLET` as a run-in heading — and all three are now in
    `gt/ocr/`. See `harness/lookup.py`'s `_resolve_cased`.
    """

    def test_a_lowercase_attestation_enables_all_three(self):
        for handle, want in (("{ke'let}", "keˊlet"),
                             ("{Ke'let}", "Keˊlet"),
                             ("{KE'LET}", "KEˊLET")):
            out, refusals = expand(handle, REPO)
            assert refusals == [] and out == nfd(want)

    def test_the_ladder_never_descends(self):
        """`Kuluˊči` is capitalized in the corpus because it is a place. A handle
        that lowered it would edit a ratified identity by a keystroke; the refusal
        names the ratified key so a reader who meant it can key it by hand."""
        out, refusals = expand("{kulu'c^i}", REPO)
        assert out == "{kulu'c^i}"
        assert "never lower it" in refusals[0]

    def test_a_capitalized_attestation_still_climbs(self):
        out, refusals = expand("{KULU'C^I}", REPO)
        assert refusals == [] and out == nfd("KULUˊČI")

    def test_raising_case_never_mints_a_glyph(self):
        """`str.upper()` is not safe over this inventory — `ɪ` U+026A maps to `Ɪ`
        U+0197, which the keying spec does not contain. Nothing here can know what
        the compositor set for a small-cap inside an all-caps heading, so the
        uppercase of such a form is refused rather than approximated."""
        got, why = _raise_case(nfd("vaˊɪrg̣ɪn"), 2)
        assert got is None and "not an ASCII letter" in why
        # ...while the capital, which touches only the ASCII `v`, is fine.
        assert _raise_case(nfd("vaˊɪrg̣ɪn"), 1)[0] == nfd("Vaˊɪrg̣ɪn")

    def test_a_combining_mark_survives_its_base_being_raised(self):
        assert _raise_case(nfd("g̣enɪˊmlinet"), 1)[0] == nfd("G̣enɪˊmlinet")

    def test_the_rank_reader_ignores_caseless_letters(self):
        """`ˊ` U+02CA is a modifier letter and passes `isalpha`, so an `isalpha`
        filter would decide `keˊlet` is not lowercase at all."""
        assert [_case_rank(nfd(s)) for s in ("keˊlet", "Keˊlet", "KEˊLET")] == [0, 1, 2]

    def test_the_lookup_offers_the_keys_the_expander_accepts(self):
        """`resolve` and `search` computed ambiguity separately and drifted the
        moment the corpus held three cases of one word: `lexicon lookup` called all
        three `ambiguous` and offered no key, for a word `expand` resolved happily.
        A reader trusts the lookup, so that gap is a form keyed by hand for nothing.
        """
        rows = [r for r in search(["Ke'let"], REPO)["matches"]
                if r["form"].casefold() == nfd("keˊlet").casefold()]
        assert len(rows) == 3
        assert not any(r["ambiguous"] for r in rows)
        for r in rows:
            assert r["key"], f"{r['form']!r} offered no key"
            assert expand(f"{{{r['key']}}}", REPO) == (r["form"], [])

    def test_case_variants_are_one_spelling_but_marks_still_conflict(self):
        """The ambiguity refusal exists for the book disagreeing about *marks*.
        Folding case must not blunt it: `Čeˊwɪn`/`Čeˊwin` differ by `ɪ` and stay
        refused, which `test_the_precise_key_is_refused_too` also asserts from the
        other side."""
        assert resolve("ke'let", REPO)[0] == nfd("keˊlet")
        assert resolve(handle_key(nfd("Čeˊwɪn")), REPO)[0] is None


class TestQueryReduction:
    """A reader may type the form as the book prints it or as the key spells it.

    The reduction used to run on the haystack only, which is not a fuzzy match but
    a match against a spelling the caller has to guess: `Telqäˊp` has the key
    `Telqa:'p`, and `telqa'p` — what a reader actually typed — found nothing.
    """

    @pytest.mark.parametrize("query", ["telqa'p", "telqap", "Telqäˊp", "Telqa:'p",
                                       "TELQAP", "telqä'p"])
    def test_every_spelling_of_one_form_reaches_it(self, query):
        forms = [r["form"] for r in search([query], REPO)["matches"]]
        assert nfd("Telqäˊp") in forms, f"{query!r} did not reach it"

    def test_the_query_is_decomposed_before_reduction(self):
        """A terminal hands over NFC, where `ä` is one non-ASCII character the ASCII
        test discards whole — reducing `Telqäˊp` to `telqp`. The corpus is NFD."""
        assert bare(unicodedata.normalize("NFC", "Telqäˊp")) == "telqap"
        assert bare(nfd("Telqäˊp")) == "telqap"

    def test_the_reduction_drops_modifier_letters_not_only_marks(self):
        """`ˊ` U+02CA and `ɪ` U+026A pass `isalnum()`, so an `isalnum`-only filter
        would leave the stress mark in and never meet the key's bare form."""
        assert bare(nfd("vaˊɪrg̣ɪn")) == "vargn"
        assert bare("va'i_rg.i_n") == "vairgin"

    def test_a_reduced_query_cannot_match_across_unrelated_forms(self):
        """The reduction is a substring test like every other arm, so it must not
        become a wildcard: an empty reduction matches nothing rather than all."""
        assert bare("'''") == ""
        assert search(["'''"], REPO)["matches"] == []


def test_a_form_the_corpus_barely_attests_gets_no_handle():
    got, why = resolve("Kulu'c^i", REPO, min_pages=99)
    assert got is None and "below the floor" in why
    assert resolve("Kulu'c^i", REPO, min_pages=2)[0] == nfd("Kuluˊči")


def test_context_lines_carry_the_form_in_use():
    """The whole point of the lookup: a form's sense, without opening the page."""
    r = search(["kulu"], REPO)
    assert any(nfd("Kuluˊči Bay") in ln["text"] for ln in r["context"])


def test_an_empty_result_is_not_a_corpus_wide_negative():
    """The floor is stated on every run, because the index cannot see an unmarked
    native token and a reader must not read silence as absence."""
    r = search(["zzzznotaword"], REPO)
    assert r["matches"] == []
    assert "not evidence the corpus lacks the word" in r["floor"]


def test_unkeyable_forms_are_counted_and_not_silently_dropped():
    assert index(REPO)["unkeyable"]
    assert search(["kulu"], REPO)["unkeyable"] > 0


# --- the write path -------------------------------------------------------

def _proposal(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "proposal.json"
    p.write_text(json.dumps({"lines": {"1": {"text": text}}}, ensure_ascii=False,
                            indent=2), encoding="utf-8")
    return p


def test_a_handle_expands_inline_inside_english_prose(tmp_path):
    """Real lines are mixed, so the substitution has to be inline, not whole-field."""
    p = _proposal(tmp_path, "x")
    set_field(p, "1", "text", "The bay of {Kulu'c^i}, they say.", REPO)
    rec = json.loads(p.read_text(encoding="utf-8"))["lines"]["1"]
    assert rec["text"] == nfd("The bay of Kuluˊči, they say.")
    assert rec["as_typed"] == "The bay of {Kulu'c^i}, they say."


# --- the path a reader actually takes -------------------------------------
#
# Measured over one day of 63 readers: 63 whole-file `Write`s of proposal.json
# against 16 `proposal set` calls, every one of those a later edit. So for a year
# the handle lived only on a verb nobody authored with, and it fired zero times —
# four readers looked a form up, were given its key, and retyped the glyphs by
# hand, which is the act it exists to replace and which produced three
# ᴇ U+1D07 → ᴀ U+1D00 slips on one name across three pages that day.
#
# `fix` runs on every page and already writes, so the expansion belongs there too.


def test_fix_expands_a_handle_written_straight_into_the_file(tmp_path):
    """The whole point: a reader that authors with `Write`, per the contract, must
    end up with ratified glyphs and a provenance record — not a literal brace in
    the store."""
    p = _proposal(tmp_path, "The bay of {Kulu'c^i}, they say.")
    fix(p, REPO)
    rec = json.loads(p.read_text(encoding="utf-8"))["lines"]["1"]
    assert rec["text"] == nfd("The bay of Kuluˊči, they say.")
    assert rec["as_typed"] == "The bay of {Kulu'c^i}, they say."


def test_fix_leaves_an_unhandled_line_alone(tmp_path):
    """No `as_typed` on a line that claimed nothing — the badge is derived from the
    field's presence, so writing it empty would badge every hand-read line."""
    p = _proposal(tmp_path, nfd("Kuluˊči read off the page"))
    fix(p, REPO)
    assert "as_typed" not in json.loads(p.read_text(encoding="utf-8"))["lines"]["1"]


def test_fix_refuses_the_whole_page_on_a_bad_handle(tmp_path):
    """Same rule as `set_field`, and it has to be: `fix` writes the file, so a
    half-expanded page here would reach the adjudicator looking finished."""
    p = _proposal(tmp_path, "{C^e'win} is spelled two ways")
    with pytest.raises(ValueError, match="more than one way"):
        fix(p, REPO)
    text = json.loads(p.read_text(encoding="utf-8"))["lines"]["1"]["text"]
    assert text == "{C^e'win} is spelled two ways"


def test_fix_refuses_a_handle_the_floor_declined(tmp_path):
    """**The brace must not be a way around `--min-pages`.**

    The floor now defaults to 1, so a hapax resolves (editor ruling — see
    `lookup.py`'s module docstring): most of this vocabulary is rare, and withholding
    a key only sends a reader to retype the form by hand. What must still hold is
    that the *brace is not a bypass* — whatever floor is in force applies to a handle
    exactly as it applies to the lookup, or the floor holds only for readers who read
    the `why` column, and a form the corpus barely attests enters the store wearing
    `as_typed`, which asserts the corpus supplied it.

    So this pins both halves: the hapax resolves at the default, and the same handle
    is refused the moment the caller raises the floor above what the corpus attests.
    """
    # A store holding the form on exactly one page — the shape the floor exists for,
    # built rather than borrowed so it cannot drift as `gt/ocr/` grows.
    root = tmp_path / "one-page"
    (root / "gt" / "ocr").mkdir(parents=True)
    (root / "data").mkdir()
    (root / "data" / "marks_config.json").write_text(
        (REPO / "data" / "marks_config.json").read_text(encoding="utf-8"),
        encoding="utf-8")
    src = next((REPO / "gt" / "ocr").glob("chukchi-1-051.xml"))
    (root / "gt" / "ocr" / src.name).write_text(src.read_text(encoding="utf-8"),
                                                encoding="utf-8")
    # The premise, not assumed: one page, and at the default that is now enough.
    assert resolve("Nu'nlig.ren", root)[0] == nfd("Nuˊnlig̣ren")
    assert resolve("Nu'nlig.ren", root, min_pages=2)[0] is None

    p = _proposal(root, "The village of {Nu'nlig.ren} stands there.")
    fix(p, root)
    rec = json.loads(p.read_text(encoding="utf-8"))["lines"]["1"]
    assert rec["text"] == f"The village of {nfd('Nuˊnlig̣ren')} stands there."
    assert rec["as_typed"] == "The village of {Nu'nlig.ren} stands there."

    # …and the brace is still not a bypass. `fix` takes no floor of its own, so the
    # one in force is `expand`'s: raise it and the same handle is refused, left in
    # place, and nothing is written. Tested here rather than through `fix` because
    # this is the layer that holds the knob — a floor `fix` could not reach would be
    # a floor the handle path never had.
    out, refusals = expand("The village of {Nu'nlig.ren} stands there.",
                           root, min_pages=2)
    assert out == "The village of {Nu'nlig.ren} stands there."
    assert refusals and "below the floor" in refusals[0]


def test_nothing_half_expands(tmp_path):
    """One bad handle aborts the write. A partly-expanded line records neither what
    was read nor what was meant."""
    p = _proposal(tmp_path, "original")
    with pytest.raises(ValueError, match="more than one way"):
        set_field(p, "1", "text", "{Kulu'c^i} and {C^e'win}", REPO)
    assert json.loads(p.read_text(encoding="utf-8"))["lines"]["1"]["text"] == "original"


def test_a_bulk_write_refuses_whole(tmp_path):
    """`ocr restore`'s rule for multi-ref writes, at line scale: dry-run everything
    before writing anything, so no page is left half-authored."""
    p = _proposal(tmp_path, "original")
    with pytest.raises(ValueError, match="line 2"):
        set_fields(p, {"1": "{Kulu'c^i}", "2": "{C^e'win}"}, "text", REPO)
    assert json.loads(p.read_text(encoding="utf-8"))["lines"]["1"]["text"] == "original"


def test_hand_keying_the_line_withdraws_the_corpus_claim(tmp_path):
    """A provenance record that outlives its provenance is worse than none: the UI
    would badge a hand-read line as a corpus match forever after."""
    p = _proposal(tmp_path, "x")
    set_field(p, "1", "text", "{Kulu'c^i}", REPO)
    assert "as_typed" in json.loads(p.read_text(encoding="utf-8"))["lines"]["1"]
    set_field(p, "1", "text", nfd("Kuluˊči"), REPO)
    assert "as_typed" not in json.loads(p.read_text(encoding="utf-8"))["lines"]["1"]


def test_a_note_is_not_expanded(tmp_path):
    """A note may mention a handle without meaning it."""
    p = _proposal(tmp_path, "x")
    set_field(p, "1", "note", "looks like {Kulu'c^i}", REPO)
    rec = json.loads(p.read_text(encoding="utf-8"))["lines"]["1"]
    assert rec["note"] == "looks like {Kulu'c^i}"
    assert "as_typed" not in rec


def test_a_stray_brace_is_refused(tmp_path):
    """No page keys a brace — 1-359 prints one joining two Russian names and its
    reader put it in a note, which is the treatment. So a brace is a mistyped handle
    or a character that does not belong in a reading."""
    p = _proposal(tmp_path, "x")
    with pytest.raises(ValueError, match="brace"):
        set_field(p, "1", "text", "a {stray brace", REPO)


def test_expand_is_a_round_trip(tmp_path):
    p = _proposal(tmp_path, "x")
    set_field(p, "1", "text", "{Kulu'c^i} and {Kulu'sik}", REPO)
    rec = json.loads(p.read_text(encoding="utf-8"))["lines"]["1"]
    assert expand(rec["as_typed"], REPO)[0] == rec["text"]


# --- the check arms -------------------------------------------------------

def _issues(tmp_path: Path, rec: dict) -> list[str]:
    p = tmp_path / "proposal.json"
    p.write_text(json.dumps({"lines": {"1": rec}}, ensure_ascii=False, indent=2),
                 encoding="utf-8")
    return [i["issue"] for i in check(p, root=REPO)]


def test_check_catches_a_record_that_disagrees_with_its_reading(tmp_path):
    """The one state that must not be reachable: `as_typed` and `text` are each
    supposed to be a record of the same act."""
    got = _issues(tmp_path, {"text": "Something else entirely",
                             "as_typed": "{Kulu'c^i}"})
    assert any("does not expand to text" in i for i in got)


def test_check_catches_a_record_with_no_handle_in_it(tmp_path):
    got = _issues(tmp_path, {"text": "plain", "as_typed": "plain"})
    assert any("carries no handle" in i for i in got)


def test_check_catches_an_unexpanded_brace(tmp_path):
    got = _issues(tmp_path, {"text": "left {Kulu'c^i} in"})
    assert any("brace in the reading" in i for i in got)


def test_a_handled_line_is_not_asked_to_narrate_a_reading_it_did_not_make(tmp_path):
    """`resolved` documents the marks a reader settled at the raster. A handle says
    it settled none of them, so demanding an account of those glyphs would ask for
    an invented one — indistinguishable from a real account, which is worse than
    silence. A hand-keyed remainder still answers for itself."""
    pure = _issues(tmp_path, {"text": nfd("Kuluˊči"), "as_typed": "{Kulu'c^i}"})
    assert not any("no resolved field" in i for i in pure)
    mixed = _issues(tmp_path, {"text": nfd("Kuluˊči and Egaˊč"),
                               "as_typed": nfd("{Kulu'c^i} and Egaˊč")})
    assert any("no resolved field" in i for i in mixed)


def test_an_expansion_is_not_a_correction(tmp_path):
    """**The reason expansion happens on write and not when the page is served.**

    Both put the ratified glyphs in front of the adjudicator. Only this one leaves
    the proposal and the decision comparing like with like: serving `Kuluˊči` over a
    proposal holding `{Kulu'c^i}` would make every handled line differ from what it
    is measured against, so `save_decisions` would flag a human edit nobody made and
    `ocr corrections` — the pass's own error profile, and the evidence keying_spec
    §5's register is built from — would grow a correction class manufactured by the
    tooling. Here the adjudicator ratifies the line without touching it and the
    census stays empty, which is the truth about what happened.
    """
    from harness.review import corrections

    d = tmp_path / "review" / "1-001"
    d.mkdir(parents=True)
    line = {"text": nfd("Kuluˊči"), "as_typed": "{Kulu'c^i}"}
    (d / "proposal.json").write_text(
        json.dumps({"lines": {"1": line}}, ensure_ascii=False), encoding="utf-8")
    (d / "decision.json").write_text(
        json.dumps({"saved_at": "2026-08-06T00:00:00-0400",
                    "lines": {"1": {"text": nfd("Kuluˊči"), "edited": False}}},
                   ensure_ascii=False), encoding="utf-8")
    assert corrections(tmp_path)["changes"] == []


def test_the_corpus_badge_is_derived_and_the_line_never_dims(tmp_path):
    """**Derived from `as_typed`, never asserted by a `class`.**

    The reader making a provenance claim is the last party who should decide
    whether it shows, and the note-class machinery is opt-in by design. A handled
    line also always agrees with the CATMuS draft — a ratified form is what the
    recognizer was closest to — so the dimming that hid the accented `Kuvaˊr` would
    hide exactly these lines unless the badge lifts them out of it.
    """
    from harness.tests.test_reader_surfacing import _rendered

    html = _rendered(tmp_path, {
        "0": {"text": nfd("Kuluˊči"), "as_typed": "{Kulu'c^i}"},
        "1": {"text": "plain english line"},
    })
    import re
    cls = {m.group(2): m.group(1) for m in
           re.finditer(r'<div class="(ln[^"]*)" id="l(\d+)"', html)}
    assert "noted" in cls["0"], "the handled line would dim for agreeing"
    assert "noted" not in cls["1"]
    assert "nb-corpus" in html.split('id="l0"')[1].split('id="l1"')[0]
    assert "as typed:" in html


def test_a_clean_handled_line_gates_nothing(tmp_path):
    p = tmp_path / "proposal.json"
    p.write_text(json.dumps(
        {"lines": {"1": {"text": nfd("Kuluˊči"), "as_typed": "{Kulu'c^i}"}}},
        ensure_ascii=False, indent=2), encoding="utf-8")
    assert not [i for i in check(p, root=REPO) if i["severity"] == "defect"]
