"""Every repo-relative path a document names must resolve on disk.

This exists because `transcriber_harness.md` was cited from nine places and every
one of them was found by a human reading files. That is how they went stale in the
first place, and it is the third time a fact in this project has been kept in two
places with nothing holding them together — after `RESP_RANKS` against the corpus
header, and the ledger's `boundary` column against a sidecar that never existed.

The project's answer everywhere else is that a checkable rule beats a convention,
and there is precedent for asserting over committed configuration rather than code
(`harness/README.md` on `DERIVED` against `.gitignore`). Prose is not exempt: a
document naming a file that does not exist is a dangling pointer, and a reader who
follows it learns nothing and does not know why.

Deliberately narrow. It checks that named paths **exist**, not that what they say
about each other is true — no test can do the second, and pretending otherwise
would be worse than not testing.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
PROJECT = REPO / "jesup" / "bogoras-chukchi"
WORKSPACE = PROJECT.parent

# Documents whose business is pointing at other files. Not every markdown file in
# the repo: a page of prose that happens to mention a filename is not making a
# claim the reader will follow.
DOCS = [
    "CLAUDE.md",
    "keying_spec.md",
    "harness/README.md",
    ".claude/skills/transcribe-page/SKILL.md",
    ".claude/skills/rebuild-groundtruth/SKILL.md",
    "docs/segmentation.md",
    "docs/pipeline.md",
    "docs/apparatus.md",
    "docs/rasters.md",
    "docs/decisions.md",
    "docs/open-questions.md",
    # Added when this gate was widened. The omissions were not principled — they
    # were the files that happened not to be here — and they included the largest
    # document in the repo and the CLI reference, between them naming ~90 paths
    # that nothing checked. `CLAUDE.md`'s routing table is the list of documents
    # that own something; every entry in it belongs here.
    "docs/edition.md",
    "harness/VERBS.md",
    "concordance.md",
    "README.md",
    ".claude/skills/train-zones/SKILL.md",
    ".claude/skills/train-figures/SKILL.md",
    ".claude/skills/train-ocr/SKILL.md",
    ".claude/skills/read-moll-page/SKILL.md",
    ".claude/skills/rebuild-groundtruth/dispatch.md",
    ".claude/agents/collator.md",
    ".claude/agents/groundtruth-reader.md",
    ".claude/rules/zones.md",
]

# A repo-relative path inside backticks: it must contain a directory separator.
#
# A bare `normalize.py` in prose names the *module*, not a file at the repo root,
# and a bare store name is not a path — matching those would fill
# the exemption list with entries that are not exemptions, which is how a check
# stops meaning anything. What this catches is the form a reader would actually
# follow: a path they could open.
PATH_RE = re.compile(r"`((?:[\w.\-]+/)+[\w.\-]+)`")

# **And a directory, which the pattern above cannot see.** It requires a basename
# after the separator, so `gt/seg/` — a store deleted a year ago and still named
# in three documents — was invisible to this gate for its whole life. The blind
# spot only ever fails one way: writing a *more* specific reference makes the
# check stricter, so the vaguer a stale pointer is the safer it was.
#
# **Two components at least**, and that is the same rule `PATH_RE` applies for
# the same reason. A bare `crops/` or `web/` in prose is a directory *name* used
# relatively — "the crops/ subdirectory" — not something a reader could open from
# the repo root, and matching those brought 25 findings of which 20 were nothing.
# Requiring a separator inside the token brings exactly the 5 that are real.
DIR_RE = re.compile(r"`((?:[\w.\-]+/){2,})`")

#: Suffixes this repo actually stores things under. Used only to tell a file from
#: a code citation: `web/edition.figref_rows` names a module attribute, not a
#: path, and nothing but the suffix distinguishes the two shapes.
KNOWN_SUFFIXES = frozenset(
    ".py .md .json .xml .png .jpg .lst .rng .jsonl .txt .toml .lock .js .html "
    ".css .yaml .yml .sh .csv .tsv .mlmodel .pdf .svg .geojson "
    # **`.safetensors` was missing while `.mlmodel` was here**, so the stock
    # models this project only consumes were checked and the four it trains and
    # installs were not — the ones that actually move. All four resolved when
    # this was added; the gap was that nothing could have said so.
    ".safetensors".split()
)

# Named but deliberately absent, each for a reason a reader should meet rather
# than trip over. Kept explicit so that "not there" and "not there *yet*" are
# different states — the same distinction `boundary` and the zone `exempt` mark
# draw, and for the same reason.
EXPECTED_ABSENT = {
    # Derived stores, regenerable and gitignored.
    "scans/chukchi-PP-NNN.png",
    "gt/fig/chukchi-PP-NNN.xml",
    "ocr/chukchi-PP-NNN.xml",
    "tei/chukchi-PP-NNN.xml",
    "gt/zones/_ink_cache.json",
    # Placeholders in worked examples, not files.
    "review/PP-NNN/proposal.json",
    "review/PP-NNN/decision.json",
    "tei/chukchi-1-100.xml",
    # Not there *yet*, which is the distinction this list exists to draw. The
    # recognizer track is laid out and unrun: `train-ocr` names where a trained
    # model will be installed, and nothing has been trained, so there is nothing
    # to install. Remove this entry with the first run.
    "models/text-rec",
    # The same state one store over: `edition/fig-img/` is declared, documented
    # and empty, because no figure has been retouched yet. It has been dangling
    # here since it was written — under its old name for its whole life, and
    # reported on every run without anybody reading the report, which is what an
    # exemption list is for. Remove this entry with the first touched-up picture.
    "edition/fig-img",
    # And the lexicon, declared and still empty — no notes written yet.
    #
    # **It became visible by being moved, not by breaking**, which is `DIR_RE`'s
    # documented blind spot working exactly as that comment says it does: the
    # store was `lexicon/`, one path segment, and the pattern requires two. It was
    # equally absent then and nothing could report it. Naming it `edition/lexicon/`
    # made the reference specific enough to check — so the entry is here on the
    # first day the gate could see the thing it had always been silent about.
    # Remove it with the first note.
    "edition/lexicon",
    # Written by `ocr queue` and cleared by the next one, so it exists only while
    # a batch is out. A checkout that has it is mid-dispatch, not complete.
    "review/_queue.txt",
    # The caption pass's derived images, `paths.DERIVED` under the `captions`
    # pseudo-ref: built by `fig sheets`/`fig zoom` when the pass runs and removed
    # with it. Absent between passes, which is the ordinary state.
    "review/captions/sheets",
    "review/captions/zoom",
    # Deleted by the rebuild sweep and not yet re-read. Both pages were keyed in
    # eScriptorium, so their ALTO carried that tool's zone vocabulary and their
    # readings predate the current pipeline; `keying_spec.md` still cites them as
    # worked examples, which stays correct — the example is about what the *page*
    # prints, and the page has not changed. Remove these two entries when the
    # rebuild restores them, and the test starts checking them again.
    "gt/ocr/chukchi-2-034.xml",
    "gt/ocr/chukchi-3-119.xml",
    # **Removed on purpose, and named in prose precisely because they were.** A
    # METS manifest is `#mz` — re-derived from its store on every run so that it
    # fails rather than goes stale — and a committed one is a second copy of its
    # store's shape with nothing keeping the two honest. Both proved it:
    # `gt/fig/METS.xml` described a store rewritten under it, and
    # `gt/ocr/METS.xml` outlived that removal to manifest 20 files against a
    # store of 663. `corpus mets STORE --out DIR` builds either on demand.
    #
    # Worth knowing how these arrived here: the `gt/fig` one had been gone for
    # ages without this gate noticing, because the prose said "`gt/fig/`" and
    # `PATH_RE` requires a basename after the separator. Writing the full path
    # is what surfaced it — the gate got stricter because the doc got more
    # specific, which is the direction that blind spot always fails in.
    "gt/fig/METS.xml",
    "gt/ocr/METS.xml",
    # --- surfaced by widening the gate, each a real absence -------------------
    # **The first segmentation attempt, deleted.** `docs/segmentation.md` opens
    # by saying so, and CLAUDE.md and `harness/README.md` refer back to it —
    # correct prose about a store that is gone. It sat unnoticed for this gate's
    # whole life because the docs write it `gt/seg/`, with the trailing slash
    # `PATH_RE` cannot match. `DIR_RE` is what found it.
    "gt/seg",
    # Declared and **not yet trained** — CLAUDE.md says "fig-seg is declared but
    # not yet trained". The distinction this list exists to draw: not there *yet*
    # is a different state from not there, and `train-figures/SKILL.md` is the
    # record of what would fill it.
    "models/fig-seg",
    # Declared, derived, gitignored, and currently empty: no machine figure
    # predictions have been kept. `mz/fig` has no view over it either.
    "mz/fig",
    # **Replaced by the `scans` group and named in prose because they were.**
    # `extract_scans.py` cut the rasters from a PEP 723 script no test could
    # import, and `migrate_to_master.py` was the driver for `harness/migrate.py`;
    # `harness scans extract` and `harness scans swap` are both now, with the
    # arithmetic under test in `test_scans.py`. `docs/decisions.md` carries why
    # the isolation cost more than it bought, `docs/rasters.md` and
    # `harness/README.md` point at what replaced them, and none of those
    # sentences can be written without naming the file that is gone.
    "tools/extract_scans.py",
    "tools/migrate_to_master.py",
    # **A forward reference, and the only kind this list should ever hold.**
    # `harness/scans.py` builds its provenance map in `provenance.py`'s vocabulary
    # rather than inventing a second spelling of it, and says so — but that module
    # landed on main after this branch was cut, so the reference is true of where
    # this is going and not of where it is. **Delete this entry on the merge**, at
    # which point the gate checks it like any other path; if it is still here and
    # `harness/provenance.py` exists, the entry is the stale thing.
    "harness/provenance.py",
    # Derived raster farms, gitignored like every other. Not to be confused with
    # `scans/w-figs-blotted/`, which exists and is a different farm: `farms.py`
    # declares FIGS_BLOT (the segmenter's training rasters, figures painted
    # white) and LINE_BLOT (`ocr blot`'s pink-and-blue output for a human)
    # separately, and `lines_ui.BLOT_CACHE` adds the editor's per-session copy.
    "scans/w-blotted",
    "scans/w-blotted-edit",
    # Named relative to the web root rather than the repo: the file is really at
    # `harness/web/static/js/edition.js`, and `docs/edition.md` is describing the
    # served tree, where that *is* its path.
    "static/js/edition.js",
    # Prose, not a path: "a `ref/key` written into the page" means one or the
    # other. Indistinguishable by pattern from `gt/seg` — two lowercase words
    # around a slash — which is why it is exempted rather than filtered.
    "ref/key",
}


def named_paths(doc: str) -> set[str]:
    text = (REPO / doc).read_text(encoding="utf-8")
    toks = ({m.group(1) for m in PATH_RE.finditer(text)}
            | {m.group(1).rstrip("/") for m in DIR_RE.finditer(text)})
    return {t for t in toks if _looks_like_a_path(t)}


def _looks_like_a_path(tok: str) -> bool:
    """Not every slash is a separator, and the false positives are instructive.

    The AMNH accession numbers are set as fractions (`70/7867`); the pre-reform
    Russian genitive endings are written `-аго/-яго`; and a repository URL
    (`gitlab.com/scripta/escriptorium`) is a path to somewhere else. Each would
    otherwise land in the exemption list, where it would read as a file this repo
    is missing.

    The four below were found by widening the gate, and each is a *class* rather
    than an instance — the exemption list is for things that are paths and are
    absent, and filling it with things that were never paths is how a check stops
    meaning anything. Where a class could not be drawn honestly the token is
    exempted instead, with its reason.
    """
    if not any("a" <= c.lower() <= "z" for c in tok):
        return False  # a fraction, or Cyrillic
    if "." in tok.split("/", 1)[0]:
        return False  # a domain, not a directory
    parts = tok.split("/")
    # A CLI metavariable: `DIR/METS.xml` is the shape of a written path, with the
    # directory left for the caller to name. Every metavar in VERBS.md is spelled
    # this way — DIR, STORE, REF, QUERY, FARM — so the convention carries it.
    if any(re.fullmatch(r"[A-Z][A-Z0-9_]*", p) for p in parts):
        return False
    # A ratio set as a fraction with a word on top: `chars/4`, an estimate of
    # tokens. The all-numeric side is what distinguishes it from `part/2`.
    if parts[-1].isdigit():
        return False
    # An element path, not a file path: `Shape/Polygon` is where a coordinate
    # lives inside ALTO. Nothing in this repo is a directory of CamelCase names.
    if all(re.fullmatch(r"[A-Z][a-zA-Z]*", p) for p in parts):
        return False
    # A code citation: `web/edition.figref_rows` names a module attribute the
    # way this repo cites code everywhere. A real file's last component either
    # carries a suffix the repo stores things under, or none at all.
    if "." in parts[-1] and not any(parts[-1].endswith(s) for s in KNOWN_SUFFIXES):
        return False
    return True


@pytest.mark.parametrize("doc", DOCS)
def test_the_document_itself_exists(doc):
    assert (REPO / doc).exists(), f"{doc} is in DOCS but not on disk"


@pytest.mark.parametrize("doc", DOCS)
def test_every_path_it_names_resolves(doc):
    missing = sorted(
        p
        for p in named_paths(doc)
        if p not in EXPECTED_ABSENT and "PP-NNN" not in p and not (REPO / p).exists() and not (PROJECT / p).exists() and not (WORKSPACE / p).exists()
    )
    assert not missing, (
        f"{doc} names paths that do not exist: {missing}. Either the file moved "
        "and the reference did not, or it never existed. If it is deliberately "
        "absent, add it to EXPECTED_ABSENT with a reason."
    )


def test_the_deleted_collation_doc_is_named_nowhere():
    """It was cited from nine places, including a committed TEI artifact. A
    tracked file citing a deleted one is the state this test exists to prevent."""
    offenders = [
        d
        for d in DOCS
        if "transcriber_harness.md" in (REPO / d).read_text(encoding="utf-8")
    ]
    assert not offenders, f"transcriber_harness.md still cited in {offenders}"


def test_the_corpus_header_names_a_real_skill():
    """Not markdown, but the same hazard and the worst instance of it: the header
    is a committed artifact asserting where the output contract is documented, and
    nothing else checks that string."""
    text = (PROJECT / "tei" / "corpus-header.xml").read_text(encoding="utf-8")
    assert "transcriber_harness.md" not in text
    assert ".claude/skills/transcribe-page/SKILL.md" in text
    assert (REPO / ".claude/skills/transcribe-page/SKILL.md").exists()
