"""A `note` that names a lexicon key the line then types by hand.

The failure this arm exists for: a reader looks a form up, gets a key, writes the
key into its `note` as corroboration for its own reading — and retypes the word by
hand anyway. It gets the store's agreement without the store's characters, which
is backwards in both directions at once. A handle *supplies characters*; the
contract says in as many words that it "is never how a doubt is settled". Chapter
XX produced eight instances on five pages: `3-088` wrote `Matches lexicon key
{Ai'g.i_nto}` into three notes and typed all three by hand, `3-094` wrote `Cf.
lexicon key taka'lhi_n` beside a hand-typed `takaˊlhɪn`.

**The negative is the load-bearing test here**, and it is `test_a_page_that_reads_
against_the_corpus_is_silent`. A reader whose page disagrees with a ratified form
is doing exactly what the contract asks — key what you see, say in `note` what the
corpus holds — and an arm that scolded it would be pressure to stop looking at the
raster, which is the objection `_handle_issues` records against the general form of
this check. It survives that objection only because it tests the *expansion against
the line* rather than testing whether a key was mentioned: where the page and the
corpus differ, the expansion is not in `text` and nothing fires.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from harness.proposal_check import _KEY_MARK, _NOTE_KEY, ADVISORY, _named_key_issues, could_name_key

#: A stub index in `lookup.index`'s shape, holding one keyed form. Passed as `lex`
#: so no test here needs a corpus on disk.
LEX = {
    "by_key": {"taka'lhi_n": "b1"},
    "buckets": {"b1": {"forms": {"taka'lhi_n": {"form": "takaˊlhɪn"}},
                       "refs": ["3-003", "3-006", "3-007"]}},
    "unkeyable": {},
}

HIT = "note names the key"


def _issues(text: str, note: str, as_typed: str = "") -> list[dict]:
    rec = {"text": text, "note": note}
    if as_typed:
        rec["as_typed"] = as_typed
    return _named_key_issues("2", rec, text, Path("."), LEX)


class TestItFires:
    def test_a_bare_key_beside_a_hand_typed_form(self):
        out = _issues("the noun takaˊlhɪn (“mate”)",
                      "Cf. lexicon key taka'lhi_n -> takaˊlhɪn.")
        assert len(out) == 1
        assert HIT in out[0]["issue"]
        assert out[0]["token"] == "takaˊlhɪn"

    def test_a_brace_in_a_note_is_the_same_finding(self):
        # `3-088`'s shape. A brace does nothing in a note, so one there is a handle
        # the reader wrote down and then declined to use.
        out = _issues("the noun takaˊlhɪn (“mate”)",
                      "Matches lexicon key {taka'lhi_n} -> takaˊlhɪn; confirmed 4x.")
        assert len(out) == 1

    def test_it_advises_and_never_gates(self):
        # A handle is a saving, not a reading: the text is already correct, so a
        # reader cannot make this go away by looking harder at the page.
        out = _issues("takaˊlhɪn", "Cf. lexicon key taka'lhi_n.")
        assert [i["severity"] for i in out] == [ADVISORY]

    def test_a_second_key_on_a_line_that_used_a_first(self):
        # Per-key, not per-line: a page using handles elsewhere gets no amnesty.
        out = _issues("Kɪntaˊ and takaˊlhɪn",
                      "keys {ke'let} and {taka'lhi_n}", as_typed="{ke'let}")
        assert len(out) == 1


class TestItStaysQuiet:
    def test_a_page_that_reads_against_the_corpus_is_silent(self):
        # `3-085`/`3-092`/`3-103`: the reader read its own page, found it differs
        # from the ratified form, kept what it saw and said so. The expansion is
        # absent from `text`, so nothing fires — the whole reason the arm compares
        # the expansion to the line instead of noticing the mention.
        assert _issues("the noun takaˊlhin (“mate”)",
                       "Corpus holds taka'lhi_n -> takaˊlhɪn; this page sets "
                       "plain i. Keyed as read.") == []

    def test_the_handle_was_used(self):
        assert _issues("the noun takaˊlhɪn",
                       "Cf. lexicon key taka'lhi_n.",
                       as_typed="the noun {taka'lhi_n}") == []

    def test_a_note_naming_no_key(self):
        assert _issues("takaˊlhɪn", "dot below g confirmed at 4x.") == []

    def test_a_lookup_that_returned_nothing(self):
        # `3-087`, `3-091`, `3-098`: the commonest note mentioning the lexicon at
        # all says the lookup found nothing. It names no key, so it cannot fire.
        assert _issues("gɪnaˊn", "lexicon lookup returned no match; keyed by "
                                 "hand from the raster.") == []

    @pytest.mark.parametrize("note", ["", None])
    def test_no_note(self, note):
        assert _named_key_issues("2", {"text": "takaˊlhɪn", "note": note},
                                 "takaˊlhɪn", Path("."), LEX) == []


class TestTheTrigger:
    """What makes a note worth building the corpus index for.

    The predicate is a cost gate, so a miss here is silent: the arm never runs and
    nothing says it didn't. That is why the mark test backs the word list up — a
    list of the phrasings one chapter happened to use is a sample, not a rule.
    """

    @pytest.mark.parametrize("note", [
        "Cf. lexicon key taka'lhi_n.",
        "lookup gave taka'lhi_n",          # names neither "key" nor "lexicon"
        "Matches {taka'lhi_n} -> takaˊlhɪn",
        "corpus has taka'lhi_n here",      # no announcing word at all
        "cf. Ai'g.i_nto",                  # dot-below, no word
        "cf. Omre^lqo't",                  # circumflex
        "cf. Telqa:'p",                    # diaeresis
    ])
    def test_it_triggers(self, note):
        assert could_name_key(note)

    @pytest.mark.parametrize("note", [
        "dot below g confirmed at 4x.",
        "the reader's own reading; don't harmonize",   # apostrophes only
        "stray ink speck above the d of would; not keyed",
        "",
    ])
    def test_it_does_not(self, note):
        assert not could_name_key(note)

    def test_the_apostrophe_alone_is_not_a_mark(self):
        # `don't` is a key-shaped token under `_NOTE_KEY` and must not by itself
        # make every English note pay for an index build.
        assert _NOTE_KEY.match("don't")
        assert not _KEY_MARK.search("don't")


class TestTheIndexIsLazy:
    """`index` walks the corpus; most pages must never pay for it."""

    def test_a_note_that_names_nothing_never_loads_it(self):
        calls = []

        def loader():
            calls.append(1)
            return LEX

        assert _named_key_issues("2", {"text": "takaˊlhɪn",
                                       "note": "dot below g confirmed at 4x."},
                                 "takaˊlhɪn", Path("."), loader) == []
        assert calls == []

    def test_a_note_whose_only_token_is_already_a_used_handle(self):
        # Trips the trigger and yields a candidate, but the line used that very
        # handle — so there is nothing to resolve and no reason to walk the corpus.
        calls = []

        def loader():
            calls.append(1)
            return LEX

        assert _named_key_issues("2", {"text": "takaˊlhɪn",
                                       "note": "used key {taka'lhi_n}",
                                       "as_typed": "{taka'lhi_n}"},
                                 "takaˊlhɪn", Path("."), loader) == []
        assert calls == []

    def test_it_loads_once_when_there_is_something_to_resolve(self):
        calls = []

        def loader():
            calls.append(1)
            return LEX

        out = _named_key_issues("2", {"text": "the noun takaˊlhɪn",
                                      "note": "Cf. lexicon key taka'lhi_n."},
                                "the noun takaˊlhɪn", Path("."), loader)
        assert len(out) == 1
        assert calls == [1]
