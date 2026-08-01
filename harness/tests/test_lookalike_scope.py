"""The three lookalike tables differ **by scope, deliberately**. Pin that.

There are three tables and they are not copies of one another:

  * `detectors.LOOKALIKES`   — speculative *triage* over OCR lines. A flag, never
                               a gate; "worth a look".
  * `normalize.LOOKALIKE_CHARS` — corpus-wide, whole file, English prose included.
  * `validate.LOOKALIKE_GREPS`  — only inside Tier-1 spans (`xml:lang` in ckt/kpy/ypk).

The curly quotes are the crux, and they are the reason this file exists. English
prose reproduces the print, curly quotes and all (keying_spec §1, ASCII policy
scoped to Tier-1), so a corpus-wide gate that trapped them would fire on thousands
of legitimate characters — and a detector firing on ordinary English buries the
real hits, which is the failure mode the whole triage design is built to avoid.
Inside a Tier-1 span the same characters *are* traps, because there U+0027 is the
spirant and pause mark and a curly quote is what gets typed instead.

So the tables must not be merged, and this was very nearly done: an audit reported
the difference as drift and a consolidation was one step from being carried out.
Merging forces one of two regressions — `normalize` screaming about correct prose,
or `validate` going blind in Tier-1. These tests are the executable form of a rule
that previously existed only as a comment.
"""
from harness.detectors import LOOKALIKES
from harness.normalize import LOOKALIKE_CHARS, LOOKALIKE_SEQS
from harness.validate import FORBIDDEN_PROSE, LOOKALIKE_GREPS, LOOKALIKE_SEQ_GREPS

CURLY = "‘’“”"
# No legitimate use in English prose *or* in the notation, so every table may hold them.
UNIVERSAL = "´ʼʻ‐"


def test_normalize_excludes_curly_quotes():
    """Corpus-wide and whole-file, so it meets English prose, which prints them."""
    for ch in CURLY:
        assert ch not in LOOKALIKE_CHARS, (
            f"{ch!r} (U+{ord(ch):04X}) must stay out of the corpus-wide gate: the "
            "book sets curly quotes and English prose reproduces them")


def test_validate_traps_the_turned_and_raised_comma_in_tier1():
    """Inside Tier-1, U+2018/U+2019 trap U+0027 — the spirant and pause mark."""
    for ch in "‘’":
        assert ch in LOOKALIKE_GREPS


def test_forbidden_prose_excludes_curly_quotes_too():
    """A separate, narrower set — an outright error in prose, not a worklist line."""
    for ch in CURLY:
        assert ch not in FORBIDDEN_PROSE


def test_the_universally_illegitimate_marks_are_trapped_everywhere():
    """Nothing scope-dependent here: these have no reading in either register."""
    for ch in UNIVERSAL:
        assert ch in LOOKALIKE_CHARS
        assert ch in LOOKALIKE_GREPS
        assert ch in FORBIDDEN_PROSE


def test_tables_are_not_the_same_object():
    """A merge would most likely arrive as an alias. Fail loudly if it does."""
    assert LOOKALIKE_CHARS is not LOOKALIKE_GREPS
    assert set(LOOKALIKE_CHARS) != set(LOOKALIKE_GREPS)


def test_triage_table_is_a_bare_set_of_characters():
    """`detectors.LOOKALIKES` carries no messages by design — it produces a flag,
    not a ruling, and a message would imply it had adjudicated something."""
    assert isinstance(LOOKALIKES, set)
    assert all(isinstance(c, str) and len(c) == 1 for c in LOOKALIKES)


def test_dotless_i_is_a_corpus_wide_trap():
    """U+0131 has no legitimate reading anywhere here; the only licensed dotless
    small-cap sort is U+026A (§2.3)."""
    assert "ı" in LOOKALIKE_CHARS
    assert "ɪ" not in LOOKALIKE_CHARS


def test_nbsp_is_trapped_corpus_wide_only():
    """A tokenization hazard in a file, not a glyph confusion inside a span."""
    assert " " in LOOKALIKE_CHARS


def test_sequence_traps_agree_on_the_message():
    """Two spellings of one key — `ġ` precomposed vs `g` + U+0307 — carrying the
    same ruling. The message is the part that must not drift."""
    assert list(LOOKALIKE_SEQS.values()) == list(LOOKALIKE_SEQ_GREPS.values())


def test_dot_above_g_is_the_trap_not_the_glyph():
    """The inventory glyph is `g` + U+0323, dot *below*. Dot above is the lookalike,
    and the naming used to say the opposite."""
    assert all("U+0323" in m for m in LOOKALIKE_SEQS.values())
