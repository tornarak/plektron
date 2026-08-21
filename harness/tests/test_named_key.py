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

import unicodedata
from pathlib import Path

import pytest

from harness.proposal_check import (
    _KEY_MARK,
    _NOTE_KEY,
    ADVISORY,
    _named_key_issues,
    could_name_key,
)


def nfd(s: str) -> str:
    """**Every literal in this file goes through here.** The corpus is NFD
    (`keying_spec.md` §1) and an editor composes `ê` to one codepoint, so a
    literal asserted in NFC is asserted about a string the project never holds —
    and `form in text` is exactly the comparison that fails silently on it."""
    return unicodedata.normalize("NFD", s)


def _bucket(key: str, form: str, refs: list[str]) -> dict:
    """One bucket in `lookup.index`'s full shape.

    Complete rather than minimal, and that is load-bearing: `expand` reads only
    `form`, so a thin stub passed every test here until the `search` fallback
    started running on the refusal path and died on `count`. A fixture that
    happens to satisfy the code path under test is not a fixture for the module.
    """
    entry = {"form": nfd(form), "count": len(refs) * 2,
             "refs": refs, "lines": []}
    return {"forms": {key: entry}, "refs": refs}


#: Two keyed forms, passed as `lex` so no test here needs a corpus on disk.
#: `Čêpaˊt` is `3-142`'s, reachable by the query `Cepa't` but not as a key.
LEX = {
    "by_key": {"taka'lhi_n": "b1", "C^e^pa't": "b2"},
    "buckets": {"b1": _bucket("taka'lhi_n", "takaˊlhɪn",
                              ["3-003", "3-006", "3-007"]),
                "b2": _bucket("C^e^pa't", "Čêpaˊt", ["3-106", "3-107"])},
    "unkeyable": {},
}

HIT = "note names"


def _issues(text: str, note: str, as_typed: str = "") -> list[dict]:
    text = nfd(text)
    rec = {"text": text, "note": nfd(note)}
    if as_typed:
        rec["as_typed"] = nfd(as_typed)
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


class TestANoteMayNameTheQueryNotTheKey:
    """`3-142`: "lexicon lookup 'Cepa't' returned no key" beside five hand-typed
    `Čêpaˊt` — a query that does return the key, `C^e^pa't`.

    `expand` needs the key itself, so the first pass is blind to a note that
    quotes what the reader typed at the tool rather than what the tool printed
    back. `search` reduces both sides and lands on it. Only a single usable row
    counts: two rows mean the corpus offers a choice, and picking one would make
    this arm the thing that settles a spelling.
    """

    def _issues(self, text, note):
        text = nfd(text)
        return _named_key_issues("5", {"text": text, "note": nfd(note)}, text,
                                 Path("."), LEX)

    def test_the_query_spelling_still_finds_it(self):
        out = self._issues(
            "Čêpaˊt lost a few animals",
            "lexicon lookup 'Cepa't' returned no key.")
        assert len(out) == 1

    def test_it_names_what_the_note_wrote_and_the_key_both(self):
        """Reporting only the key would have this arm misquote the proposal — the
        very failure it exists to report."""
        out = self._issues(
            "Čêpaˊt lost a few animals",
            "lexicon lookup 'Cepa't' returned no key.")
        assert "C^e^pa't" in out[0]["issue"]
        assert "Cepa" in out[0]["issue"]
        assert "reaches the key" in out[0]["issue"]

    def test_a_query_whose_form_the_line_lacks_is_silent(self):
        """The disagreement case survives the widening: the reader read its own
        page, and the ratified form is not what the line holds."""
        assert self._issues("Cepat lost a few animals",
                            "lexicon lookup 'Cepa't' returned no key.") == []


class TestTheCorpusIsWalkedOncePerRun:
    """`expand` and `index` build the corpus index when not given one, and the
    walk is 2.4s at 645 pages. Three callers used to trigger it per *line* or per
    *page*; all three now take an index from the caller above them.

    The worst was `_handle_issues`, which calls `expand` for every line carrying
    `as_typed` — so the verb was slowest on the pages using handles properly, the
    thing the contract asks for. `3-143`'s nine handles cost 26 seconds.

    These assert the plumbing rather than a duration: a timing test would be
    flaky, and what actually regresses is someone dropping the `idx=` argument.
    """

    def _count_builds(self, monkeypatch) -> list:
        """Every real call to `lookup.index`, however reached."""
        import harness.lookup as lookup

        builds: list[int] = []

        def counted(root, exclude=None):
            builds.append(1)
            return LEX

        monkeypatch.setattr(lookup, "index", counted)
        return builds

    def test_five_lines_carrying_handles_walk_once(self, monkeypatch):
        """The regression that mattered. Drop the `idx=` from `_handle_issues`'
        `expand` call and this counts five walks instead of one."""
        from harness.proposal_check import _handle_issues, _lexicon_loader

        builds = self._count_builds(monkeypatch)
        loader = _lexicon_loader(Path("."), ())
        for _ in range(5):
            _handle_issues("2", {"as_typed": "the noun {taka'lhi_n}"},
                           nfd("the noun takaˊlhɪn"), Path("."), loader)
        assert builds == [1], f"walked {len(builds)} times for five lines"

    def test_a_loader_nobody_uses_never_walks(self, monkeypatch):
        from harness.proposal_check import _lexicon_loader

        builds = self._count_builds(monkeypatch)
        _lexicon_loader(Path("."), ())
        assert builds == []
