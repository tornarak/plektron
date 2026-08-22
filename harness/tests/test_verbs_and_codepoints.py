"""Two small modules that answer questions mid-pass, and the second parser of `VERBS.md`.

`harness/verbs.py` slices `harness/VERBS.md` so a reader can consult one entry
instead of paying 33,000 tokens for the whole file. It does that with **its own
regex** (`verbs.HEAD`), while `test_cli_surface.py` parses the same headings with
another (`_HEADING`) to gate the CLI against the reference. That is this repo's
named defect shape — two parsers of one file, no page resolving the
correspondence locally — and the first test below is the gate that keeps them
from drifting apart: the index must offer exactly the actions the surface gate
knows about, neither more nor fewer. A verb the index cannot find is a verb whose
documentation is unreachable through the tool that exists to reach it, and
nothing else would report that.

`harness/codepoints.py` names the non-ASCII characters in a line. It exists
because the question it answers — "is this ı U+0131 or ɪ U+026A" — is the one
`keying_spec.md` §2.3 says the small-cap sorts invite getting wrong, and no
amount of magnification separates the two by eye. Its properties worth pinning
are that it discriminates the lookalike pairs at all, that it iterates
**codepoints and not graphemes** (an NFD corpus stores `g̣` as two, and a check
that folded them back into one would be blind to exactly the mark it was asked
about), and that its unnamed-character fallback holds, that being the one branch
whose absence would raise instead of report.
"""
from __future__ import annotations

import pytest

from harness import verbs
from harness.codepoints import non_ascii
from harness.tests.test_cli_surface import _documented

# --- verbs.py, held against the other parser ---------------------------------


def test_the_index_and_the_surface_gate_see_the_same_actions():
    """**The two `VERBS.md` parsers must agree, and nothing else checks it.**

    `test_cli_surface.py` holds the reference against the CLI in both directions,
    so a heading it cannot see is a heading that gates nothing. `verbs.py` reads
    the same headings with a different regex, so a heading *it* cannot see is an
    entry `harness verbs show` will deny exists — and a caller told an action does
    not exist stops looking. Both failures are silent on their own; only the
    comparison is loud.

    Held as set equality rather than one containment, because the interesting
    failures run both ways: `HEAD`'s `[a-z-]+` drops a heading with a capital or a
    digit that `_HEADING`'s `\\w+` keeps, while `HEAD`'s optional second word
    invents a bare-group entry `_HEADING` never yields.
    """
    indexed = set(verbs.lookup("")["actions"])
    gated = {f"{group} {action}" for group, action in _documented()}
    assert indexed == gated, (
        f"the index sees {sorted(indexed - gated)} that the surface gate does not, "
        f"and misses {sorted(gated - indexed)} that it does")


def test_the_empty_query_is_the_whole_list_and_nothing_else():
    """`lookup("")` is the cheapest answer to "what can I run".

    It must carry no body text at all — the point of the empty case is that a
    caller reaching for it first pays for names and not for prose, and a `text`
    that quietly filled up would put the 100 KB file back in the context the
    module was written to keep it out of.
    """
    out = verbs.lookup("")
    assert out["query"] == ""
    assert out["text"] == ""
    assert out["actions"] == sorted(out["actions"])
    assert out["actions"], "no actions parsed out of VERBS.md — the heading form moved"


@pytest.mark.parametrize("blank", ["", "   ", "\t\n"])
def test_whitespace_is_the_empty_query(blank):
    """A shell that passes an empty argument through as a space must not be told
    its command does not exist."""
    assert verbs.lookup(blank)["text"] == ""


def test_a_group_lookup_carries_the_conventions_block():
    """The rules a caller reading one entry is most likely to be missing.

    Report-by-default, `--commit` writes, exit 0/1/2, refs are `PP-NNN`: none of
    them are restated per action, so an entry read in isolation says nothing about
    any of them. Asserted on the substance rather than on the heading, so a
    Conventions block that survived as an empty stub would still fail.
    """
    out = verbs.lookup("ocr")
    assert out["query"] == "ocr"
    assert len(out["actions"]) > 1
    assert all(a.startswith("ocr ") for a in out["actions"])
    assert "## Conventions" in out["text"]
    assert "--commit" in out["text"]
    assert out["actions"] == sorted(out["actions"])
    # Every entry in the group is actually present, not just named.
    for action in out["actions"]:
        assert f"### {action}" in out["text"]


def test_a_single_action_lookup_is_one_entry():
    """One entry, its own heading, and no neighbour's body dragged along — the
    slice boundary is the next heading and an off-by-one there would hand a reader
    a second entry it never asked for."""
    out = verbs.lookup("ocr zoom")
    assert out["actions"] == ["ocr zoom"]
    assert out["text"].startswith("### ocr zoom")
    assert out["text"].count("\n### ") == 0


def test_an_extra_space_in_the_query_still_resolves():
    """`lookup` collapses whitespace before matching, so a query pasted out of a
    wrapped line resolves to the same entry."""
    assert verbs.lookup("  ocr   zoom ")["text"] == verbs.lookup("ocr zoom")["text"]


def test_an_unknown_verb_raises_and_names_the_near_misses():
    """**A silent empty result reads as "no such command" when the truth is a typo.**

    Pinned as the observed behaviour: `lookup` raises `ValueError`, and when the
    query is a substring of real action names it lists them. This is the whole
    reason the function does not simply return `{}` — the caller's next move after
    an empty dict is to give up, and after "did you mean `zones check`" is to type
    it.
    """
    with pytest.raises(ValueError) as exc:
        verbs.lookup("zone")
    msg = str(exc.value)
    assert "zone" in msg
    assert "Did you mean" in msg
    assert "zones check" in msg


def test_an_unrecognizable_verb_points_at_the_list():
    """With no near miss to offer, the error must still say what to do next; an
    error whose only content is that something failed sends the reader back to the
    file the index exists to avoid."""
    with pytest.raises(ValueError) as exc:
        verbs.lookup("xyzzy")
    msg = str(exc.value)
    assert "no argument" in msg
    assert "VERBS.md" in msg


def test_a_missing_reference_fails_loudly(tmp_path):
    """The reference is not optional, and its absence must not read as "no actions".

    An empty index and a missing file are indistinguishable to a caller unless the
    second raises, and the empty one is exactly what a `--root` pointed somewhere
    wrong would produce.
    """
    with pytest.raises(FileNotFoundError) as exc:
        verbs.lookup("", root=tmp_path)
    assert "VERBS.md" in str(exc.value)


def test_entries_slice_at_the_headings(tmp_path):
    """The slicing itself, on a fixture small enough to state the whole expectation.

    Each entry runs from its own heading to the next one and stops there, and the
    prose before the first heading belongs to no entry.
    """
    doc = tmp_path / "harness" / "VERBS.md"
    doc.parent.mkdir(parents=True)
    doc.write_text(
        "# preamble nobody's entry owns\n\n"
        "## Conventions\n\nreport by default, `--commit` writes\n\n"
        "## Groups\n\n"
        "### alpha one\n\nbody of one\n\n"
        "### alpha two\n\nbody of two\n\n"
        "### beta one\n\nbody of three\n",
        encoding="utf-8")
    out = verbs.entries(root=tmp_path)
    assert sorted(out) == ["alpha one", "alpha two", "beta one"]
    assert out["alpha one"] == "### alpha one\n\nbody of one"
    assert "preamble" not in "".join(out.values())
    # Conventions is a `## ` block and stops at the next one, not at the file end.
    conv = verbs.conventions(root=tmp_path)
    assert conv.startswith("## Conventions")
    assert "--commit" in conv
    assert "### alpha one" not in conv


def test_conventions_is_empty_rather_than_wrong_when_absent(tmp_path):
    """A group lookup still works on a reference with no Conventions block; the
    block is prepended, so a missing one must degrade to nothing rather than to
    the rest of the file."""
    doc = tmp_path / "harness" / "VERBS.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("### alpha one\n\nbody\n", encoding="utf-8")
    assert verbs.conventions(root=tmp_path) == ""
    assert verbs.lookup("alpha", root=tmp_path)["text"].strip() == "### alpha one\n\nbody"


def test_a_bare_group_heading_does_not_shadow_its_own_group(tmp_path):
    """**The divergence the two regexes used to permit.**

    `verbs.HEAD` made the second word optional, so `### ocr` on its own parsed as
    an *action* named `ocr` — and because `lookup` tests `q in all_` before it
    tests the group prefix, that entry answered every `lookup("ocr")` with one
    stub instead of the group and its Conventions. `_HEADING` in
    `test_cli_surface.py` requires both words and would never have seen the
    heading, so the surface gate could not have reported it either: the two
    parsers of one file would have disagreed in silence.

    Both words are required now, so a bare heading is simply not an action and
    the group answers as a group.
    """
    doc = tmp_path / "harness" / "VERBS.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("### ocr\n\nthe group blurb\n\n### ocr zoom\n\nbody\n",
                   encoding="utf-8")
    out = verbs.lookup("ocr", root=tmp_path)
    assert out["actions"] == ["ocr zoom"]
    assert "ocr zoom" in out["text"]


def test_a_digit_in_an_action_name_does_not_overwrite_its_sibling(tmp_path):
    """The other half of the same divergence. `HEAD`'s class was `[a-z-]`, so
    `### tei validate2` truncated to `tei validate` and **silently overwrote**
    the real entry in `entries()` — an action dropped from the index with no
    error, while the surface gate read `validate2` and saw nothing wrong. The
    class matches `_HEADING`'s `[\\w-]` now, so the two names stay distinct."""
    doc = tmp_path / "harness" / "VERBS.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("### tei validate\n\nreal body\n\n### tei validate2\n\nother\n",
                   encoding="utf-8")
    assert verbs.lookup("", root=tmp_path)["actions"] == \
        ["tei validate", "tei validate2"]
    assert "real body" in verbs.lookup("tei validate", root=tmp_path)["text"]


# --- codepoints.py -----------------------------------------------------------


def test_the_small_cap_lookalikes_are_told_apart():
    """`ı` U+0131 against `ɪ` U+026A — the pair the module was written for.

    `keying_spec.md` §2.3 puts ɪ in the IPA block precisely because the neighbouring
    "Latin Letter Small Capital" run invites a later "fixing" to a lookalike, and
    §2.6 adds that a dotless i-form under a mark is `ĭ` and never `ɪ̆`. Nothing in
    the letterform decides it; the codepoint does, and this is what prints it.
    """
    dotless = non_ascii("ı")
    smallcap = non_ascii("ɪ")
    assert dotless == [{"char": "ı", "codepoint": "U+0131",
                        "name": "LATIN SMALL LETTER DOTLESS I"}]
    assert smallcap[0]["codepoint"] == "U+026A"
    assert smallcap[0]["name"] != dotless[0]["name"]


def test_the_apostrophe_and_the_stress_mark_are_told_apart():
    """The other pair in the module's docstring, and the one with a policy behind it.

    Inside Tier-1, U+0027 is the only apostrophe — so it is ASCII and correctly
    invisible here, while the stress mark U+02CA that gets typed in its place is
    not. The asymmetry is the finding: a line that looks right and reports one
    record has the wrong character in it.
    """
    assert non_ascii("ke'ti") == []
    marked = non_ascii("keˊti")
    assert [r["codepoint"] for r in marked] == ["U+02CA"]


def test_a_combining_mark_is_its_own_record():
    """**Codepoints, not graphemes** — load-bearing for an NFD corpus.

    `g̣` is stored as `g` + U+0323 and never as a precomposed sort, so the question
    "is the mark below this g a dot or a ring" is a question about the *second*
    codepoint. A grapheme-wise report would fold the two back together and answer
    a question nobody asked, leaving the one that was asked unanswerable. The base
    `g` is ASCII and drops out, which is why a one-glyph string reports one record
    here and the record is the mark.
    """
    out = non_ascii("g̣")
    assert out == [{"char": "̣", "codepoint": "U+0323",
                    "name": "COMBINING DOT BELOW"}]
    # And the ring the reader has to rule out is a different record entirely.
    assert non_ascii("g̥")[0]["name"] == "COMBINING RING BELOW"


def test_a_multi_mark_form_reports_every_mark_in_order():
    """Order is the other half of the NFD question — which mark sits on which base.

    Reported in string order, so the records read left to right against the line
    the caller pasted in.
    """
    out = non_ascii("ʟ̣ă")
    assert [r["codepoint"] for r in out] == ["U+029F", "U+0323", "U+0306"]


def test_ascii_is_dropped_whole():
    """The filter is `ord > 127`, which means the bulk of any English line costs
    nothing to look at — including the two characters Tier-1 reserves, U+0027 and
    U+002D, whose *correct* forms are exactly the ones that should not show up."""
    assert non_ascii("") == []
    assert non_ascii("the well-known 'sacrifice', 1904") == []
    assert non_ascii("\x7f") == []          # DEL, the last ASCII codepoint
    assert non_ascii("\x80")[0]["codepoint"] == "U+0080"


def test_an_unnamed_character_reports_instead_of_raising():
    """The one branch whose absence would turn a report into a traceback.

    `unicodedata.name` raises `ValueError` on a private-use or unassigned
    codepoint, and those are exactly what a mis-keyed or font-mangled paste
    contains — so the character that most needs naming is the one that would kill
    the tool. The fallback keeps the record, with the codepoint still readable,
    which is the part the caller actually needs.
    """
    out = non_ascii("")
    assert out == [{"char": "", "codepoint": "U+E000", "name": "<unnamed>"}]


def test_an_astral_codepoint_is_one_record():
    """Formatted with `04X`, so a codepoint above U+FFFF must widen rather than
    truncate — and Python iterating a `str` yields it as one character, not as a
    surrogate pair."""
    out = non_ascii("\U0001D50A")
    assert len(out) == 1
    assert out[0]["codepoint"] == "U+1D50A"
