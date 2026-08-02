"""Span-level review queue: two witnesses, grouped by substitution class.

The eval rebuild needs 18 pages of ground truth back, and the arithmetic of the
page decides the shape of the tool. On the two surviving hand-keyed pages,
inventory glyphs are 3.3% of characters but fall in 43.8% of lines, so
line-at-a-time review means re-reading nearly half the book to fix a thirtieth of
it. Hence spans, not lines.

The second number is why spans are then *grouped*. On `1-074`, my reading and the
CATMuS output differ in 62 places — but those 62 collapse to 26 distinct
substitution classes, and the top six cover 65%. A queue keyed on the instance
asks "is this ' really ˊ?" twelve times; a queue keyed on the class asks once and
shows you the twelve crops.

**Grouping is presentation. The tool decides nothing.** It does not rank the
witnesses, does not mark a class safe, does not suppress a difference, and never
extends a decision to an instance the human did not accept. Every span reaches
the queue; grouping only changes how they are stacked on screen.

Two display mechanisms rather than one, because a capable font does not help if
the terminal is not:

  * every span is rendered with a **codepoint breakdown** — `g̣ro` reads as
    `g, U+0323 DOT BELOW, r, o`. Environment-independent, and the only form that
    cannot silently lose a mark. This is not hypothetical: a missing U+0323 in a
    terminal is exactly how `1-074`'s `Am-g̣roˊkĭ` was first mis-keyed.
  * the browser view stacks the scan crop above the same line rendered in DejaVu
    Serif, whose single-storey `g` leaves clean space under the bowl for a dot
    below. Charis SIL is the closer match to Bogoras's serif letterforms and is
    better for comparing *shapes*, but it crowds that dot against the descender,
    and confirming a mark exists is this tool's job.

CATMuS is a witness to line geometry and to English, and to nothing else. Against
the human-collated `1-151` it produced 13 non-ASCII characters where the human had
41, and not one was an inventory glyph. So a non-ASCII span has exactly one
witness — the image — and is queued unconditionally.
"""
from __future__ import annotations

import difflib
import json
import unicodedata
from pathlib import Path

from lxml import etree

from .context import norm_ref
from .detectors import DOT_ABOVE_G, INVENTORY_CHARS, LOOKALIKES, unlicensed_marks
from .lines import DEFAULT_ALTO_DIR, alto_for_lines, page_lines
from .paths import crops_dir, decisions_path, proposal_path

CONTEXT_CHARS = 24


def _nfd(s: str) -> str:
    return unicodedata.normalize("NFD", s)


def codepoints(s: str) -> str:
    """`g̣ro` -> `g, U+0323 DOT BELOW, r, o`.

    Named marks are spelled out; printable ASCII is shown as itself, because
    `U+0072 LATIN SMALL LETTER R` for every letter buries the one that matters.
    """
    out = []
    for ch in s:
        if ch == " ":
            out.append("SPACE")
        elif ord(ch) < 128 and ch.isprintable():
            out.append(ch)
        else:
            # Full Unicode name, unabbreviated. Trimming the prefix would turn
            # "COMBINING DOT BELOW" into "DOT BELOW" and lose the one word that
            # says the mark attaches to the character before it — which is the
            # whole distinction this function exists to make visible.
            out.append(f"U+{ord(ch):04X} {unicodedata.name(ch, 'UNNAMED')}")
    return ", ".join(out)


def classify(catmus: str, claude: str) -> str:
    """Space-separated class tags for one differing span. Flat, for TOON."""
    tags = []
    both = catmus + claude
    if any(ord(c) > 127 for c in both):
        tags.append("non_ascii")
    else:
        tags.append("ascii_only")
    if any(c in INVENTORY_CHARS for c in claude):
        tags.append("inventory")
    if any(c in LOOKALIKES for c in claude):
        tags.append("lookalike_in_proposal")
    if DOT_ABOVE_G.search(claude):
        tags.append("dot_above_g_in_proposal")
    if not catmus:
        tags.append("insertion")
    elif not claude:
        tags.append("deletion")
    return " ".join(tags)


def tier1_glyphs(text: str) -> str:
    """The distinct inventory glyphs in a line, in order of first appearance.

    Used to flag a line as *probably* carrying transcribed notation, which is the
    line the reviewer's attention is worth most on: a misread English word is
    checkable against a dictionary and a second witness, a misread Chukchee form
    against neither (`keying_spec.md` section 1, and CLAUDE.md's Collation notes).

    **This is a floor and must be labelled as one wherever it is shown.** Four
    inventory members are unmarked ASCII — `c` for English *sh*, plain `s`, `j`, `x`
    — so a line of pure Tier-1 in those letters produces no glyph here at all. An
    unflagged line is "nothing detected", never "no notation present", and a UI that
    lets the two read alike would turn the flag into an invitation to skip lines.
    """
    return "".join(dict.fromkeys(c for c in text if c in INVENTORY_CHARS))


def load_proposal(ref: str, root: Path = Path(".")) -> dict[int, dict]:
    """`review/<ref>/proposal.json` -> `{index: record}`.

    A proposal, never ground truth: no glyph identity in it is adopted. The word is
    in the filename precisely so the distinction cannot be lost to a path, which is
    how 18 pages of real ground truth were lost — it used to be carried by the
    `review/proposals/` directory instead, which said the same thing.
    """
    p = proposal_path(ref, root)
    if not p.exists():
        # The ordinary state of most of the corpus, not a broken install: 812 pages
        # have a prediction and no reading. A bare FileNotFoundError names the path
        # and not the act, which is the wrong error for the commonest case in the
        # pass — so say what is missing and who writes it.
        raise ValueError(
            f"no proposal for {ref} at {p}. A proposal is *your reading of the "
            f"raster*, authored line by line — start with `harness ocr lines "
            f"{ref} --store mz` and the crops, per the rebuild-groundtruth "
            "skill. It is never seeded from the recognizer: that would collapse "
            "the two witnesses the span diff compares, and CATMuS reads 0% of the "
            "transcription inventory.")
    doc = json.loads(p.read_text(encoding="utf-8"))
    return {int(k): v for k, v in doc["lines"].items()}


def line_spans(catmus: str, claude: str) -> list[dict]:
    """Differing spans between two readings of one line, with local context."""
    a, b = _nfd(catmus), _nfd(claude)
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        out.append({
            "catmus": a[i1:i2],
            "claude": b[j1:j2],
            "at": j1,
            "context": b[max(0, j1 - CONTEXT_CHARS):j2 + CONTEXT_CHARS],
            "classes": classify(a[i1:i2], b[j1:j2]),
        })
    return out


def page_spans(ref: str, alto_dir: str = DEFAULT_ALTO_DIR,
               root: Path = Path(".")) -> list[dict]:
    """Every differing span on one page, one flat record each."""
    ref = norm_ref(ref)
    prop = load_proposal(ref, root)
    out = []
    for rec in page_lines(alto_for_lines(ref, alto_dir, root)):
        mine = prop.get(rec["index"])
        if mine is None:
            continue
        for sp in line_spans(rec["text"], mine["text"]):
            out.append({"ref": ref, "index": rec["index"],
                        "line_id": rec["line_id"], **sp})
    return out


def group_spans(spans: list[dict]) -> list[dict]:
    """Collapse spans to substitution classes, most frequent first.

    `instances` is a compact `index:at` list rather than nested records — a nested
    list would de-tabularize the TOON table, and the caller can rejoin against
    `page_spans` on those keys when it wants the full record.
    """
    byclass: dict[tuple[str, str], list[dict]] = {}
    for sp in spans:
        byclass.setdefault((sp["catmus"], sp["claude"]), []).append(sp)
    out = []
    for (catmus, claude), items in byclass.items():
        out.append({
            "n": len(items),
            "catmus": catmus,
            "claude": claude,
            "catmus_cp": codepoints(catmus),
            "claude_cp": codepoints(claude),
            "classes": items[0]["classes"],
            "instances": " ".join(f"{i['index']}:{i['at']}" for i in items),
        })
    out.sort(key=lambda r: (-r["n"], r["claude"]))
    return out


# The notation keyboard, as a toggled mode. Off by default, so U+0027 — which is
# itself the spirant and pause mark (keying spec 2.1), not merely a lookalike for
# U+02CA — stays typeable. That is why this is a mode and not a remap.
#
# The first block is the editor's existing bindings, reproduced key for key so
# muscle memory survives. Note `r`/`R` is deliberately asymmetric (ṛ vs ř) and is
# left as found rather than regularised.
KBD_GLYPHS = {
    "a": "ᴀ", "e": "ᴇ", "i": "ɪ", "c": "č", "g": "g̣", "j": "ǰ",
    "l": "ʟ", "n": "ñ", "r": "ṛ", "R": "ř",
    "'": "ˊ", "<": "ᵋ", ">": "˙", "?": "(??/????)",
    # Atomics the editor's list flagged as having no key.
    "o": "ɵ", ";": "ᵉ",
    # Capitals, likewise unreachable before. Composed, so they are NFD by
    # construction rather than by remembering to normalize.
    "C": "Č", "G": "G̣", "N": "Ñ", "L": "ʟ̣",
}

# Postfix combining marks: they attach to whatever precedes the caret, so one key
# each reaches every marked sort in keying spec 2.2 — ä ë ê ḷ ʟ̣ š ŭ x˙ and both
# length marks — instead of a binding per glyph. This is also exactly the corpus's
# own encoding, so what is typed is what is stored.
KBD_MARKS = {
    ".": "̣", "^": "̂", "~": "̃",
    ":": "̈", '"': "̌", "-": "̄", "=": "̆",
}

# Decomposed at the source, not left to the save to fix. Seven of the literals above
# are precomposed if written naively (č U+010D, ñ U+00F1, ṛ U+1E5B, ř U+0159, ǰ, Č,
# Ñ), so typing them would put precomposed characters on screen and in the palette's
# codepoint tooltips while the entire corpus is NFD. `save_decisions` would still
# normalize the file, which is exactly what makes the discrepancy easy to miss.
KBD_GLYPHS = {k: unicodedata.normalize("NFD", v) for k, v in KBD_GLYPHS.items()}

# The palette is the whole keying-spec inventory, not just what has a binding —
# grouped as the spec groups it so the panel reads as the inventory rather than as a
# pile of characters. Bindings are a shortcut for the frequent ones; the button is
# the guarantee that nothing is unreachable.
#
# The ASCII row earns its place despite being typeable: U+0027 is the spirant *and*
# pause mark, U+002D the connector hyphen, U+0021 increased articulation (2.1). They
# look like ordinary punctuation and are not, and clicking them works even with the
# mode on, which is otherwise the one way to reach U+0027 without toggling.
PALETTE = [
    ("small caps (2.3)", ["ᴀ", "ᴇ", "ɪ", "ʟ", "ʟ̣"]),
    ("modifiers (2.1)", ["ˊ", "ᵋ", "ᵉ", "˙"]),
    ("combining marks", list(KBD_MARKS.values())),
    ("marked sorts (2.2)",
     ["ñ", "č", "š", "ř", "ǰ", "ê", "ë", "ä", "ŭ", "ṛ", "ḷ", "ɵ", "x˙", "g̣"]),
    # Convenience only, and labelled so it cannot be mistaken for inventory: the
    # spec lists no capital rows. G̣ is attested (1-074's G̣ɪthaˊk) and Č occurs in the
    # corpus; Š Ř J̌ are here because a base plus a mark key produces them anyway, not
    # because anything has licensed them.
    ("capitals (composed, not spec rows)", ["Ñ", "Č", "Š", "Ř", "J̌", "G̣"]),
    ("ascii, special function", ["'", "-", "!"]),
    ("catalogue placeholder", ["(??/????)"]),
    # Not Tier-1 notation — English prose reproduces the print, curly quotes
    # included (keying spec section 1). Straight U+0022 has no legitimate
    # reading anywhere in this corpus (normalize.py's quote check), and a bare
    # keyboard makes it the path of least resistance: shift-' is one keystroke,
    # a curly quote is not on any physical key at all. `1-048` and `2-030` —
    # both hand-keyed before this button existed — carry the straight-quote
    # slip throughout, which is the button's whole reason for being here.
    #
    # U+2019 belongs in this row for the identical reason, not in the ASCII
    # row above: it is the *English* possessive/elision apostrophe the book
    # sets ("cliff's end," "don't"), and inside a Tier-1 span it is instead
    # the lookalike trap for the spirant/pause U+0027 (validate.py's
    # LOOKALIKE_GREPS, "U+2019 traps U+0027") — never something to type there.
    # A corpus-wide check turned up several already-restored English glosses
    # ("cliff's end," "man's name," "Kihiˊni' Island") carrying a straight
    # U+0027 where the print sets curly ’, the same slip 1-048/2-030 made
    # with the double-quote pair — this button exists so the fix, and every
    # future gloss, has an easy key to reach for instead of the bare
    # apostrophe already under the fingers.
    ("curly quotes (English prose)", ["“", "”", "’"]),
]
PALETTE = [(label, [unicodedata.normalize("NFD", g) for g in glyphs])
           for label, glyphs in PALETTE]


def load_decisions(ref: str, root: Path = Path(".")) -> dict[int, dict]:
    """Adjudicated lines saved so far, `{index: record}`. Empty if none."""
    p = decisions_path(ref, root)
    if not p.exists():
        return {}
    doc = json.loads(p.read_text(encoding="utf-8"))
    return {int(k): v for k, v in doc.get("lines", {}).items()}


def save_decisions(ref: str, lines: dict, root: Path = Path("."),
                   stamp: str | None = None) -> dict:
    """Write adjudicated lines, recording for each whether it differs from the proposal.

    **Every line's full text is stored, not just the edited ones**, and the apparent
    redundancy against the proposal is the point. `restore` builds ground truth from
    this file alone and refuses on any missing line, so if an unedited line carried
    only a flag, the content of `gt/ocr/` would depend on the proposal still being
    byte-identical — and a proposal is a model's output, rewritten whenever a reading
    is revised. Then correcting a proposal would silently change what the stored
    "unedited" resolved to, which is a way to alter ground truth without touching it.
    `edited` is the derived field here; the text is the substance.

    `edited` is computed here rather than trusted from the client, because it is the
    eval's primary signal — the fraction of proposed lines a human let stand — and a
    number the thing being measured gets to report about itself is worthless.

    NFD on the way in. Browsers submit whatever normal form the keyboard produced,
    and this corpus is NFD by policy (keying spec section 1); an unnormalized save
    would reintroduce exactly the mixed-encoding drift `harness corpus normalize` exists to
    remove.

    Written temp-then-rename so an interrupted save cannot truncate the file, and the
    previous version is kept alongside. Cheap, and this repo has already lost 18 pages
    of transcription once.

    `.prev` is one deep and that is not enough on its own, so every save also appends
    to an **append-only journal**, `decision.jsonl`, recording only the lines that differ
    from the proposal. Two saves in a row destroy `.prev`; nothing destroys the
    journal. This is not hypothetical: Firefox restores textarea values across a
    crash-and-reopen and restores them *by position*, so reopening this page refilled
    `1-073`'s fields with `1-151`'s text, and one keystroke autosaved all 47 lines.
    `.prev` happened to still hold the real pass. A third save would have taken it.

    `changed` is returned so the page can show it, because that incident was invisible
    at every layer that could have caught it — well-formed payload, real transcription,
    plausible counts. A save reporting 38 changed lines after one keystroke is the one
    signal that does not require knowing which page's text it is.
    """
    ref = norm_ref(ref)
    prop = load_proposal(ref, root)
    before = load_decisions(ref, root)
    out = {}
    for k, v in lines.items():
        idx = int(k)
        text = _nfd(v if isinstance(v, str) else v.get("text", ""))
        proposed = _nfd(prop[idx]["text"]) if idx in prop else None
        out[str(idx)] = {"text": text, "edited": proposed is not None
                         and text != proposed}
    changed = sorted(int(k) for k, v in out.items()
                     if int(k) in before and before[int(k)]["text"] != v["text"])
    doc = {"ref": ref,
           # Repo-relative regardless of `root`: the field records which reading was
           # adjudicated, and an absolute path names a machine rather than a file.
           "proposal": proposal_path(ref).as_posix(),
           "saved_at": stamp,
           "lines": out}
    p = decisions_path(ref, root)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        p.with_suffix(".json.prev").write_bytes(p.read_bytes())
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)

    # Appended after the write succeeds, and only the edited lines: a full snapshot per
    # autosave would grow without bound over a session, and the edited set is what a
    # recovery actually needs.
    with p.with_suffix(".jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"saved_at": stamp, "changed": changed,
                             "edited": {k: v["text"] for k, v in out.items()
                                        if v["edited"]}},
                            ensure_ascii=False) + "\n")
    # Counts alone are what "38 lines edited" is: a symptom without a location. Both
    # line-index lists are returned alongside their counts so the terminal print and
    # the page's status line can name the lines, not just tally them.
    edited_lines = sorted(int(k) for k, v in out.items() if v["edited"])
    return {"path": str(p), "lines": len(out),
            "edited": len(edited_lines), "edited_lines": edited_lines,
            "changed": len(changed), "changed_lines": changed}


def restore(ref: str, alto_dir: str = DEFAULT_ALTO_DIR, root: Path = Path("."),
            force: bool = False, commit: bool = False) -> dict:
    """Write adjudicated text into `gt/ocr/chukchi-<ref>.xml`, keeping the geometry.

    The ALTO in `alto_dir` is the skeleton: every line has exactly one `String`
    whose box mirrors the `TextLine`'s, so this only sets `@CONTENT`; nothing
    structural moves.

    **Two modes, and the returned `mode` field says which one ran.** They differ
    only in whether the geometry source and the write target are the same file:

      * `restoration` — the source is some other store, and `gt/ocr/` is being
        filled in from it. This is what the ground-truth rebuild did, page by
        page, when `gt/ocr/` held export shells with no `TextLine` at all.
      * `revision` — the source resolves to the target. Under the default store
        that is the ordinary case now that the rebuild is complete: `ocr/<ref>` is
        a symlink onto `gt/ocr/<ref>`, so re-adjudicating a finished page reads
        its own geometry and writes its own text back.

    Revision is *safe* rather than merely tolerated, and it is worth saying why,
    because "reads the file it writes" is normally a bug. `etree.parse` builds the
    whole tree in memory before anything is written; the write goes to a `.tmp`
    sibling; and the post-write verification below re-reads `src`, which the
    `tmp.replace(target)` has not yet touched. So the source is never observed
    half-written. The `mode` field exists because the operation is nonetheless a
    different act in the two cases — one reconstructs, the other edits in place —
    and a caller that cannot tell them apart cannot report honestly on either.

    Writes `gt/ocr/` by name, never `ocr/`. They are the same inode — `ocr/*.xml`
    are symlinks — and naming the real store is what stops the next reader
    reasoning about the wrong one. Reads are the other way round: see
    `lines.alto_for_lines` on why resolving *through* `ocr/` is fine.

    `commit` gates the actual write, same contract as `normalize`'s `--convert`:
    every check below still runs and the full report — including `edits`, so a
    dry run answers "what would restore change" without needing a hand-rolled
    diff script — comes back either way, but without `commit` nothing on disk
    changes. Ground truth is the one thing in this repo an accidental write has
    already destroyed once (see CLAUDE.md, "The ground-truth loss"); a bare call
    defaulting to write was the wrong default for the same reason `normalize`'s
    was.

    Refuses rather than guesses, in three cases, because the whole point of this
    function is to put back something that was destroyed by a write nobody had to
    confirm:

      * the target already holds text, without `force`. Since the rebuild finished
        every page in `gt/ocr/` holds text, so this is now the guard that separates
        a deliberate `revision` from an accidental overwrite — `force` is how a
        caller says which it meant, and it is required for every revision.
      * any line lacks a decision. A partial restore yields ground truth with
        invisible holes, which is worse than no ground truth.
      * a line does not have exactly one `String`. Unexpected shape, so it stops.
      * any adjudicated line carries a mark on a base its licence does not cover
        (`detectors.MARK_LICENSE`, keying spec §2.6). This one catches what a human
        pass can miss rather than what it never saw: `1-073` prints the same ǰ three
        times, review corrected two and left the third, and the page read as done.
        A restore is the last point at which that is still cheap to fix.
    """
    ref = norm_ref(ref)
    dec = load_decisions(ref, root)
    if not dec:
        raise ValueError(f"no decisions for {ref}: adjudicate it first "
                         f"(harness ocr review {ref} --serve)")

    src = alto_for_lines(ref, alto_dir, root)
    tree = etree.parse(str(src))
    lines = list(tree.iter("{*}TextLine"))

    missing = [i for i in range(len(lines)) if i not in dec]
    if missing:
        raise ValueError(f"{ref}: {len(missing)} of {len(lines)} lines have no "
                         f"decision (indices {missing[:12]}…); refusing a partial "
                         "restore — ground truth with holes is worse than none")

    bad = [f"line {i}: {h['mark']} on {h['base']} (licensed on "
           f"{h['licensed_on']}) in {h['context']!r}"
           for i in sorted(dec) for h in unlicensed_marks(dec[i]["text"])]
    if bad:
        raise ValueError(
            f"{ref}: {len(bad)} unlicensed mark(s) in the adjudicated text; "
            "refusing to write. These are sequences the notation does not contain "
            "(keying spec 2.6), not readings to weigh, so re-key them in "
            f"harness ocr review {ref} --serve:\n  " + "\n  ".join(bad))

    target = root / "gt" / "ocr" / f"chukchi-{ref}.xml"
    # Same real file, reached under two names, is `revision`; anything else is a
    # `restoration` from a separate store. Compared by resolved path rather than by
    # directory name, since `ocr/` reaches `gt/ocr/` by symlink and a name test
    # would call that a restoration.
    mode = ("revision" if target.exists() and src.exists()
            and src.resolve() == target.resolve() else "restoration")
    if target.exists() and not force:
        existing = sum(len(s.get("CONTENT") or "")
                       for s in etree.parse(str(target)).getroot().iter("{*}String"))
        if existing:
            raise ValueError(
                f"{target} already holds {existing} characters of text. Refusing to "
                "overwrite hand-keyed ground truth; pass force=True if that is "
                "genuinely what you want")

    for i, tl in enumerate(lines):
        strings = tl.findall("{*}String")
        if len(strings) != 1:
            raise ValueError(f"{ref} line {i} ({tl.get('ID')}) has {len(strings)} "
                             "String elements, expected exactly 1 — not guessing")
        strings[0].set("CONTENT", _nfd(dec[i]["text"]))

    # Always written to a scratch path and verified from there — `commit` only
    # gates the final `tmp.replace(target)` below, so dry-run and real-write share
    # one code path rather than a preview implementation drifting from the real one.
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".xml.tmp")
    tree.write(str(tmp), xml_declaration=True, encoding="UTF-8", standalone=None)

    # Verify against the source rather than trusting the write: geometry identical,
    # text exactly what was adjudicated.
    a = page_lines(src)
    b = page_lines(tmp)
    # **Length first, and then `strict`.** Bare `zip` stops at the shorter side, so
    # a write that dropped a line would have been verified over the common prefix
    # and reported clean — a check that cannot see the one failure this repo has
    # already paid for twice, sitting inside the function whose whole job is to
    # verify the write. Ruff's B905 found it; the count guard is what gives the
    # failure a message, and `strict=True` is what makes the guard impossible to
    # drift away from.
    if len(a) != len(b):
        raise ValueError(
            f"{ref}: the written page has {len(b)} lines where the source has "
            f"{len(a)} — the write lost or gained lines and was not committed")
    geom = ("line_id", "block_id", "hpos", "vpos", "width", "height",
            "baseline", "points")
    drift = [x["index"] for x, y in zip(a, b, strict=True)
             if any(x[k] != y[k] for k in geom)]
    wrong = [y["index"] for y in b if y["text"] != _nfd(dec[y["index"]]["text"])]
    # `edits` names what changed, not just how many lines did — "edited_by_human: 2"
    # used to be the whole answer, and finding out *what* meant hand-rolling a
    # proposal-vs-decision diff script each time. `load_proposal` can be missing a
    # line decisions has (a line added after the proposal was authored, in theory),
    # so `.get` rather than assuming symmetry.
    prop = load_proposal(ref, root)
    edits = [{"line": i, "proposal": prop[i]["text"] if i in prop else "(gone from proposal)",
             "decision": v["text"]}
            for i, v in sorted(dec.items()) if v.get("edited")]

    if not commit:
        tmp.unlink()
        return {"path": str(target), "source": str(src), "mode": mode,
                "lines": len(lines),
                "chars": sum(len(y["text"]) for y in b),
                "geometry_drift": drift, "text_mismatch": wrong,
                "edited_by_human": len(edits), "edits": edits, "commit": False}
    tmp.replace(target)
    return {"path": str(target), "source": str(src), "mode": mode,
            "lines": len(lines),
            "chars": sum(len(y["text"]) for y in b),
            "geometry_drift": drift, "text_mismatch": wrong,
            "edited_by_human": len(edits), "edits": edits, "commit": True}


def _data_uri(path: Path) -> str:
    import base64
    return ("data:image/png;base64,"
            + base64.b64encode(path.read_bytes()).decode("ascii"))


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def _edit_jump_inner(idxs: list[int]) -> str:
    """The 'Edited lines' jump-list body, for the initial server render. `save()`'s
    JS rebuilds the same markup client-side after each save, so the list stays
    current without a reload — keep the two in sync if this format changes."""
    if not idxs:
        return "<b>Edited lines:</b> none yet"
    return "<b>Edited lines:</b> " + " ".join(f"<a href='#l{i}'>{i}</a>" for i in idxs)


# DejaVu Serif first, deliberately. Its single-storey `g` has a short descender, so
# a U+0323 below the bowl stays legible; Charis SIL matches Bogoras's serif
# letterforms far better and is the right choice for comparing *shapes*, but it
# crowds that dot. Confirming a mark exists is this view's job. No webfont: the
# font is installed locally and a CSS reference cannot silently substitute the way
# a missing glyph in a terminal does.
_FONT_STACK = "'DejaVu Serif', 'Charis SIL', 'Noto Sans', sans-serif"


def render_queue_html(ref: str, alto_dir: str = DEFAULT_ALTO_DIR,
                      root: Path = Path("."), crops: Path | None = None) -> str:
    """Self-contained review page for one ref: one entry per line, reading order.

    **The unit is the line, not the span.** An earlier version grouped by
    substitution class on the grounds that glyphs are 3.3% of characters, but that
    measures the wrong cost: the expensive act is re-orienting to a different line,
    not reading the characters in a line you already have open. Since 44% of lines
    need some attention, those lines get opened regardless, and once open the rest
    of the line is nearly free. Span-grouping also scattered one line's corrections
    across the queue, so their sum could not be seen.

    It organised around the wrong thing besides. The spans are diffs against
    CATMuS, which reads no inventory glyph at all, so a class like `'` -> `ˊ`
    describes the recognizer's failure modes rather than the text. `group_spans`
    survives as *measurement* for the eval, not as the review unit.

    Reading order, not difference-first: consecutive lines carry each other's
    context, and a line the two witnesses agree on can still have both of them
    wrong — CATMuS agreeing about ASCII is weak evidence and it has no vote on a
    glyph whatsoever. So every line is present; agreement only sets emphasis.

    **"Reading order" was a claim this function did not honour** until the ordering
    work: it iterated `sorted(recs)`, i.e. the segmenter's index order, which is
    not reading order on 18 of the 20 restored pages — a running head lands
    mid-sequence, a folio last. It now walks `y_rank`. The consequence on screen is
    that the line labels are *not* consecutive, and that is correct: the label is
    the identity `decision.json` is keyed by, not a position in the queue.
    """
    from .lines import write_line_crops
    ref = norm_ref(ref)
    crops = crops or crops_dir(ref, root)
    recs = {r["index"]: r for r in write_line_crops(ref, crops, alto_dir, root)}
    # Reading order, not index order. `recs` is keyed by `index` because that is the
    # identity the client submits and `save_decisions` stores under; but iterating
    # `sorted(recs)` would walk the *segmenter's* order, which is not reading order on
    # 18 of the 20 restored pages — a running head lands mid-sequence, a folio last.
    # The queue's whole premise is that consecutive lines carry each other's context,
    # so it must walk the page as a reader does. Order here, identity everywhere else.
    order = sorted(recs, key=lambda i: recs[i]["y_rank"])
    prop = load_proposal(ref, root)
    saved = load_decisions(ref, root)
    spans = page_spans(ref, alto_dir, root)
    summ = summary(spans, len(recs))

    h = [f"<title>review {ref}</title>", "<style>",
         f":root{{--f:{_FONT_STACK}}}",
         "body{font:15px var(--f);margin:0;padding:1.5rem;max-width:1100px}",
         "h1{font-size:1.1rem;margin:0 0 .3rem}",
         ".sum{color:#555;font-size:.85rem;margin-bottom:1.4rem}",
         ".ln{border-top:1px solid #ddd;padding:.7rem 0}",
         # Agreement is de-emphasis, never omission: CATMuS agreeing about ASCII is
         # weak evidence, and on a glyph it has no vote at all, so a quiet line is
         # still a line somebody has to look at.
         ".agree{opacity:.62}",
         ".agree:focus-within{opacity:1}",
         # A Tier-1 line is where the reviewer is the only witness there will ever
         # be, so it is marked in three redundant ways — rule, tint, and a badge
         # naming the glyphs — rather than by one colour a reader can scroll past.
         # It also overrides `.agree`: agreement with CATMuS is no evidence at all
         # about a glyph, so a dimmed Tier-1 line would be dimmed for a reason that
         # does not apply to the part of it that matters.
         ".t1{border-left:5px solid #b8860b;padding-left:.7rem;"
         "background:linear-gradient(90deg,#fdf6e3,transparent 45%)}",
         ".t1.agree{opacity:1}",
         ".badge{display:inline-block;font:11px ui-monospace,monospace;"
         "background:#b8860b;color:#fff;border-radius:3px;padding:.05rem .35rem;"
         "margin-right:.4rem;letter-spacing:.04em}",
         ".t1glyphs{font-size:1.05rem;color:#7a4a00;letter-spacing:.12em}",
         ".jump{font:12px ui-monospace,monospace;margin:.5rem 0 0}",
         ".jump a{color:#8a5a00;margin-right:.45rem;text-decoration:none;"
         "border-bottom:1px dotted #b8860b}",
         ".jump.edit a{color:#1a7f37;border-color:#1a7f37}",
         ".editflag{color:#1a7f37}",
         # Transient — added to a just-saved line's own textarea (not just the
         # row) so it is unmissable which field a save just touched, not only a
         # count in the status bar. A thin outline on the row read as too subtle;
         # this is the same idea moved onto the textbox itself and made bolder.
         # Removed by the same timeout that adds it (see `save()`), not by CSS.
         "textarea.justsaved{outline:3px solid #1a7f37;outline-offset:1px}",
         ".floor{color:#8a2b2b;font-size:.8rem;margin-top:.35rem;max-width:80ch}",
         ".cp{font:12px ui-monospace,monospace;color:#036;margin:.2rem 0}",
         ".tags{font:11px ui-monospace,monospace;color:#666}",
         ".ref{font:13px ui-monospace,monospace;color:#777;margin-top:.2rem}",
         ".note{font-size:12px;color:#7a4a00;margin-top:.2rem;max-width:70ch}",
         # Crops are emitted as one CSS rule per line and referenced by class, not
         # inlined per occurrence. Inlining embedded a line's image once per queue
         # entry; on 1-074 that was 676 KB against 209.
         ".crop{border:1px solid #ddd;background-repeat:no-repeat;"
         "background-size:contain;background-color:#fff;margin:.2rem 0}",
         "textarea{font:17px/1.4 var(--f);width:100%;border:1px solid #bbb;"
         "border-radius:4px;padding:.35rem .5rem;resize:vertical;overflow:hidden}",
         "textarea:focus{outline:2px solid #47f;border-color:#47f}",
         # Fixed to the bottom, full width, always visible. It is the reference for
         # what the mode does as much as it is an input device, so hiding it behind a
         # scroll position would defeat both jobs.
         #
         # #pctl and #pgroups stack (column), #pctl on top — not side by side. Side
         # by side, #pctl's status text (the growing "saved · N/M edited (...line
         # numbers...)" list) competed with #pgroups for horizontal space: as that
         # text grew wide it starved #pgroups's width, which made the wrapped key
         # rows pile up vertically instead, and #pal's height (shared by both flex
         # children) grew with them — on a long session the keyboard could end up
         # consuming the whole viewport for a reason that had nothing to do with the
         # keyboard. Stacked, #pctl's width no longer bounds #pgroups's at all.
         "#pal{position:fixed;left:0;right:0;bottom:0;z-index:5;background:#fff;"
         "border-top:1px solid #999;box-shadow:0 -2px 10px #0002;"
         "display:flex;flex-direction:column}",
         "#pgroups{display:flex;flex-wrap:wrap;gap:.35rem .9rem;padding:.5rem .8rem}",
         ".pgrp{display:flex;flex-direction:column;gap:.15rem}",
         ".plabel{font:10px ui-monospace,monospace;color:#888;letter-spacing:.02em}",
         ".pkeys{display:flex;flex-wrap:wrap;gap:.2rem}",
         ".pk{font:inherit;min-width:2.5rem;padding:.15rem .25rem;cursor:pointer;"
         "display:flex;flex-direction:column;align-items:center;line-height:1.1;"
         "background:#fafafa;border:1px solid #bbb;border-radius:4px}",
         ".pk b{font-size:1.15rem;font-weight:500}",
         ".pk span{font:10px ui-monospace,monospace;color:#888;min-height:1em}",
         ".pk.mk{background:#eef3ff}",
         # order:-1 puts this ahead of #pgroups regardless of DOM position (pgroups
         # is emitted first, since the palette-group loop is simplest that way).
         "#pctl{order:-1;display:flex;flex-direction:column;gap:.3rem;"
         "padding:.5rem .8rem;border-bottom:1px solid #ddd;font-size:.85rem}",
         # kb / st / the button group are the three controls worth a glance at
         # once — same row, same box model, so the eye reads them as one strip
         # rather than a badge, a caption and a toolbar stacked by accident.
         ".pctlrow{display:flex;align-items:stretch;justify-content:space-between;"
         "gap:.4rem;width:100%}",
         ".pctlrow>span{display:flex;gap:.4rem}",
         "#kb,#st,#pctl button{font:12px ui-monospace,monospace;border:1px solid #bbb;"
         "border-radius:3px;padding:.25rem .5rem;line-height:1.1}",
         "#st{color:#555;min-width:13ch;text-align:right;border-color:#ddd}",
         "#st.bad{color:#b00;font-weight:600;border-color:#b00}",
         "#kb{color:#777;cursor:pointer;user-select:none}",
         "#kb.on{color:#fff;background:#1a7f37;border-color:#1a7f37;font-weight:700}",
         "#pctl button{cursor:pointer}",
         # The mode has to be unmissable, since with it on every letter key means
         # something else. A badge alone is too easy to lose track of.
         "body.kbdon textarea:focus{outline-color:#1a7f37;border-color:#1a7f37;"
         "background:#f2fbf4}",
         # The glyph grid is only worth the screen space while a line is actually
         # being keyed. Retracted by default; #pgroups reappears (and the page
         # regains its clearance below) on the kbd toggle or the alt-p override —
         # never gone, since #pctl (status, save, the shortcut hint) stays put
         # either way, now as the bar above rather than a sidebar beside it.
         "#pgroups{display:none}", "body.palopen #pgroups{display:flex}",
         "body{padding-bottom:2.6rem}", "body.palopen{padding-bottom:16rem}",
         "@media(prefers-color-scheme:dark){body{background:#161616;color:#e6e6e6}"
         ".ln{border-color:#2f2f2f}.cp{color:#8ec7ff}.ref{color:#8f8f8f}"
         ".note{color:#d9b26a}"
         ".t1{border-color:#d1a02a;background:linear-gradient(90deg,#2a2211,"
         "transparent 45%)}"
         ".badge{background:#d1a02a;color:#161616}"
         ".t1glyphs{color:#e8c874}"
         ".jump a{color:#e0b552;border-color:#8a6a1e}"
         ".jump.edit a{color:#4fd47a;border-color:#1a7f37}"
         ".editflag{color:#4fd47a}"
         "textarea.justsaved{outline-color:#4fd47a}"
         ".floor{color:#e88d8d}"
         "textarea{background:#111;color:#eee;border-color:#444}"
         "#st{color:#bbb;border-color:#444}"
         "#pal{background:#1b1b1b;border-color:#444}"
         "#pctl{border-color:#3a3a3a}"
         "#pctl button{border-color:#555;background:#242424;color:#eee}"
         ".pk{background:#242424;border-color:#484848;color:#eee}"
         ".pk.mk{background:#1b2436}"
         "#kb{color:#aaa;border-color:#555}"
         "body.kbdon textarea:focus{background:#0f1a12}"
         ".crop{filter:invert(1) hue-rotate(180deg)}}",
         "</style>"]

    # One rule per unique line crop, scaled down to fit the column while keeping
    # aspect ratio, so the div reserves the right height before the image paints.
    from PIL import Image
    # Every rendered line needs a rule, not only the differing ones. Deriving this
    # from the span instances left the agreeing lines as empty bordered boxes.
    css = []
    for idx in order:
        rec = recs[idx]
        path = Path(rec["crop"])
        w, ht = Image.open(path).size
        # Full column width. Never upscaled past 1:1 — a magnified bitonal crop
        # invents smoothness, and the reviewer should see the raster it is.
        scale = min(1.0, 1040 / w)
        css.append(f".c{idx}{{background-image:url({_data_uri(path)});"
                   f"width:{round(w * scale)}px;height:{round(ht * scale)}px}}")
    h += ["<style>", "\n".join(css), "</style>"]
    # Computed over the text on screen — saved edits included — not over the
    # proposal alone, so a glyph the reviewer has just typed flags its line at once.
    t1 = {idx: tier1_glyphs(_nfd((saved.get(idx) or prop[idx])["text"]))
          for idx in order if idx in prop}
    t1 = {k: v for k, v in t1.items() if v}

    h += [
         f"<h1>{ref} — {summ['lines']} lines, "
         f"{summ['lines'] - summ['lines_identical']} differing from catmus, "
         f"{len(t1)} carrying notation</h1>",
         "<div class=sum>"
         f"{summ['spans']} differing spans in {summ['classes']} substitution "
         f"classes · {summ['inventory_spans']} touch inventory glyphs · "
         f"{summ['lookalikes_in_proposal']} lookalike traps in the proposal<br>"
         "Every line is listed, in reading order. CATMuS is shown for reference "
         "only: it is a witness to geometry and English, and produced no inventory "
         "glyph anywhere in this book, so on a glyph the image is the sole witness "
         "— and a line the two agree on can still have both of them wrong.</div>"]
    if t1:
        h.append("<div class=jump><b>Tier-1 lines:</b> " + " ".join(
            f"<a href='#l{i}'>{i}</a>" for i in t1) + "</div>")
    # Edited lines get the same jump-list treatment as Tier-1, and for the same
    # reason: "38 lines edited" told a reader nothing about *which* 38 until the
    # session-restore incident forced the question. `editjump` is rewritten by
    # `save()` after every save, so this list never goes stale without a reload.
    edited_now = [idx for idx in order if idx in prop
                 and idx in saved and _nfd(saved[idx]["text"]) != _nfd(prop[idx]["text"])]
    h.append("<div class='jump edit' id=editjump>" + _edit_jump_inner(edited_now)
             + "</div>")
    h.append(
        "<div class=floor>Notation flags are a <b>floor, not a census</b>: four "
        "inventory members are unmarked ASCII (<code>c</code> for English "
        "<i>sh</i>, plain <code>s</code>, <code>j</code>, <code>x</code>), so a "
        "Tier-1 form spelled only in those raises no flag. An unflagged line means "
        "nothing was detected, not that the line is English.</div>")

    differing = {s["index"] for s in spans}
    for idx in order:
        rec = recs[idx]
        mine = prop.get(idx)
        # A line in the ALTO with no proposal entry used to be skipped in silence,
        # which is the same class of defect as a hole in ground truth: the queue
        # rendered as complete while a line was unreachable, the human could never
        # adjudicate it, and `restore` would then refuse the page forever. It
        # happens for real — a line recovered by `--adopt-gap` has geometry before
        # it has any reading. Render it empty and say so.
        if mine is None:
            mine = {"text": ""}
        proposed = _nfd(mine["text"])
        # Saved work wins on reload, so a session can be resumed. The proposal is
        # still what `edited` is measured against, server-side.
        full = _nfd(saved[idx]["text"]) if idx in saved else proposed
        marks = codepoints("".join(dict.fromkeys(c for c in full if ord(c) > 127)))
        agree = idx not in differing
        glyphs = t1.get(idx, "")
        cls = "ln" + (" agree" if agree else "") + (" t1" if glyphs else "")
        h.append(f"<div class='{cls}' id='l{idx}'"
                 + (" data-t1=1" if glyphs else "") + ">")
        h.append("<div class=tags>"
                 + (f"<span class=badge>TIER 1</span>"
                    f"<span class=t1glyphs>{_esc(glyphs)}</span> · "
                    if glyphs else "")
                 + f"line {idx} · {_esc(rec['line_id'])}"
                 + (" · <b>NO PROPOSAL — key from the scan</b>"
                    if idx not in prop else "")
                 + (" · recovered line (segmenter missed it)"
                    if (rec["line_id"] or "").startswith("gap_") else "")
                 + ("" if agree else " · differs from catmus")
                 + f"<span class=editflag id='ef{idx}' "
                   f"style='display:{'inline' if full != proposed else 'none'}'>"
                   " · <b>edited</b></span>" + "</div>")
        h.append(f"<div class='crop c{idx}' role=img "
                 f"aria-label='scan of line {idx}'></div>")
        # The value is carried in `data-text` and assigned by script on load, not
        # written as element content — see SESSION-RESTORE below. `autocomplete=off`
        # asks the browser not to restore it; the JS assignment is what guarantees it.
        # `data-proposed` is what the live edited-flag toggle (on input, and after
        # a save) compares the current value against — the same comparison
        # `save_decisions` makes server-side, just available to the page too.
        h.append(f"<textarea data-line='{idx}' rows=1 spellcheck=false "
                 f"autocomplete=off data-text=\"{_esc(full)}\" "
                 f"data-proposed=\"{_esc(proposed)}\"></textarea>")
        if marks:
            h.append(f"<div class=cp>{_esc(marks)}</div>")
        h.append(f"<div class=ref>catmus: {_esc(rec['text']) or '(empty)'}</div>")
        for key in ("note", "resolved", "corrected"):
            if mine.get(key):
                h.append(f"<div class=note>{key}: {_esc(mine[key])}</div>")
        h.append("</div>")

    # Fixed to the bottom of the viewport, and the save controls live in the same
    # panel: two floating widgets competing for the corner is one too many.
    binding = {g: k for k, g in KBD_GLYPHS.items()}
    binding.update({m: k for k, m in KBD_MARKS.items()})

    pal = ["<div id=pal>", "<div id=pgroups>"]
    for label, glyphs in PALETTE:
        pal.append(f"<div class=pgrp><div class=plabel>{_esc(label)}</div>"
                   "<div class=pkeys>")
        for g in glyphs:
            key = binding.get(g, "")
            combining = len(g) == 1 and unicodedata.category(g) == "Mn"
            shown = ("◌" + g) if combining else g
            tip = codepoints(g) + (
                " — attaches to the character before the caret" if combining else "")
            pal.append(f"<button class='pk{' mk' if combining else ''}' "
                       f"data-ins='{_esc(g)}' title='{_esc(tip)}'>"
                       f"<b>{_esc(shown)}</b>"
                       f"<span>{_esc(key) or '&nbsp;'}</span></button>")
        pal.append("</div></div>")
    pal.append("</div>")
    pal.append("<div id=pctl><div class=pctlrow>"
               "<span><span id=kb>kbd off</span><span id=st>no changes</span></span>"
               # Notation lines are the ones worth walking deliberately, so they get
               # their own traversal rather than only a colour to spot while scrolling.
               f"<span><button id=t1p>&uarr;</button>"
               f"<button id=t1n>&darr; tier-1 ({len(t1)})</button>"
               "<button id=sv>Save</button>"
               # Stops the server from the page, so finishing a review does not
               # leave a process bound to a page that is about to be restored.
               "<button id=dn title='save if needed, then stop the server'>"
               "Done</button></span></div>"
               "<div class=tags>alt-p shows/hides the keyboard panel (overrides "
               "kbd on/off) · ctrl-space toggles kbd · off = plain typing · "
               "alt-j / alt-k walk tier-1 lines</div></div>")
    pal.append("</div>")
    h += pal
    # Autosave on a debounce *and* an explicit button, plus a beforeunload guard.
    # Belt and braces on purpose: the alternative to a save that fires by itself is
    # a reviewer who closes the tab on forty adjudicated lines.
    h.append("<script>const GL=" + json.dumps(KBD_GLYPHS, ensure_ascii=False)
             + ",MK=" + json.dumps(KBD_MARKS, ensure_ascii=False) + ";</script>")
    h.append("""<script>
const st=document.getElementById('st'), sv=document.getElementById('sv');
const dn=document.getElementById('dn');
const kb=document.getElementById('kb');
let kbdOn=false, last=null;
function setKbd(v){kbdOn=v;kb.textContent='kbd '+(v?'ON':'off');
  kb.className=v?'on':'';document.body.classList.toggle('kbdon',v);syncPal()}
function insert(el,s){
  const a=el.selectionStart,b=el.selectionEnd;
  el.setRangeText(s,a,b,'end');
  el.dispatchEvent(new Event('input',{bubbles:true}));
}
// Click-to-insert targets whichever field was last focused, so the palette works
// without stealing the caret.
document.addEventListener('mousedown',e=>{
  if(e.target.closest('#pal')) e.preventDefault();
});
for(const b of document.querySelectorAll('.pk')){
  b.addEventListener('click',()=>{ if(last) insert(last,b.dataset.ins) });
}
kb.addEventListener('click',()=>setKbd(!kbdOn));
// Retract the glyph grid except while it's actually wanted: kbd mode is on, or
// the reviewer pinned it open (alt-p) to browse without keeping a caret in a
// field. Visibility is a pure function of those two toggles — SOLELY the
// shortcuts (ctrl-space, alt-p) — and never of focus. It used to also require
// a focused textarea, on the theory that plain typing in an ordinary English
// line shouldn't pop the grid; in practice that made the panel jump open the
// instant a field was focused whenever kbd mode was already on, which is the
// opposite of "no keyboard until you asked for it", and no different from a
// docked-vs-undocked distinction if a focus event overrides it either way. So
// focus no longer participates at all: turn kbd mode on and the panel is
// open, everywhere, until you turn it off. #pctl (status/save/hint) is
// unaffected — see the CSS.
//
// palOverride is a tri-state, not a bool ORed with kbdOn: null means "follow
// kbdOn", true/false means alt-p has said otherwise and wins regardless of
// kbdOn. The OR version couldn't represent "kbd mode on, panel hidden" at
// all — kbdOn=true forced the OR to true no matter what alt-p did, which is
// exactly the state a reviewer wants when they know the mode they're in and
// don't need the grid on screen to use it. alt-p flips whatever is currently
// showing, so it always does something visible, and the override sticks
// until alt-p is pressed again — toggling kbd mode itself doesn't clear it.
let palOverride=null;
const syncPal=()=>document.body.classList.toggle(
  'palopen', palOverride===null?kbdOn:palOverride);
document.addEventListener('focusin',e=>{
  // The panel occupying 16rem when kbd mode is on can cover the very field
  // just focused, if it was near the bottom of the page. scrollIntoView
  // (nearest, not goT1's center) nudges just enough to clear it without
  // recentering on an ordinary tab/click. Scroll-only now — it no longer
  // toggles the panel itself, since that depends only on kbdOn/palOverride.
  if(e.target.tagName==='TEXTAREA'&&kbdOn){
    e.target.scrollIntoView({block:'nearest',behavior:'smooth'});
  }
});
addEventListener('keydown',e=>{
  if(e.altKey&&!e.ctrlKey&&!e.metaKey&&e.key==='p'){
    e.preventDefault();
    const shown=palOverride===null?kbdOn:palOverride;
    palOverride=!shown;syncPal();
  }
});
addEventListener('keydown',e=>{
  if(e.ctrlKey&&e.code==='Space'){e.preventDefault();setKbd(!kbdOn);return}
  if(!kbdOn||!last||document.activeElement!==last) return;
  if(e.ctrlKey||e.altKey||e.metaKey) return;
  const g=Object.prototype.hasOwnProperty.call(GL,e.key)?GL[e.key]
        :(Object.prototype.hasOwnProperty.call(MK,e.key)?MK[e.key]:null);
  if(g===null) return;
  e.preventDefault(); insert(last,g);
});
let dirty=false, timer=null;
const grow=t=>{t.style.height='auto';t.style.height=t.scrollHeight+'px'};
function collect(){const o={};for(const t of document.querySelectorAll('textarea'))
  o[t.dataset.line]=t.value;return o}
// Live edited-flag, kept in sync with typing rather than only with the last save,
// so a line that was reverted back to its proposed text stops claiming "edited"
// before the next save round-trips. `ef{idx}` is the same span the server rendered.
function refreshEditFlag(t){
  const ef=document.getElementById('ef'+t.dataset.line);
  if(ef) ef.style.display=(t.value!==t.dataset.proposed)?'inline':'none';
}
function rebuildEditJump(){
  const idxs=[...document.querySelectorAll('textarea')]
    .filter(t=>t.value!==t.dataset.proposed)
    .map(t=>parseInt(t.dataset.line,10)).sort((a,b)=>a-b);
  document.getElementById('editjump').innerHTML=idxs.length
    ? '<b>Edited lines:</b> '+idxs.map(i=>`<a href='#l${i}'>${i}</a>`).join(' ')
    : '<b>Edited lines:</b> none yet';
}
async function save(){
  st.textContent='saving…';
  try{
    const r=await fetch('/save',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({lines:collect()})});
    if(!r.ok) throw new Error(await r.text());
    const j=await r.json();
    dirty=false;
    const editedTxt=j.edited_lines.length?` (lines ${j.edited_lines.join(',')})`:'';
    const changedTxt=j.changed_lines.length?` (lines ${j.changed_lines.join(',')})`:'';
    st.textContent=`saved · ${j.edited}/${j.lines} edited${editedTxt} · `+
                   `${j.changed} changed${changedTxt}`;
    // A save that moved many lines at once is the only visible sign of a bulk
    // overwrite — a browser session-restore looks like ordinary work otherwise.
    if(j.changed>3) st.className='bad';
    rebuildEditJump();
    // Flash exactly the textboxes this save touched — the status line names them
    // too, but the field itself changing color is what actually catches the eye,
    // rather than something you have to go read.
    for(const i of j.changed_lines){
      const box=document.querySelector(`textarea[data-line='${i}']`);
      if(!box) continue;
      box.classList.add('justsaved');
      setTimeout(()=>box.classList.remove('justsaved'),2500);
    }
  }catch(e){ st.textContent='SAVE FAILED: '+e.message; st.className='bad'; }
}
// Finish the session from the page. **Always saves**, and refuses to stop if that
// save fails — the server is the only thing holding the decisions, so stopping on
// a failed save would discard them silently.
//
// Unconditional, not gated on `dirty`, and that distinction is the whole point:
// "I changed nothing" is an adjudication, not an absence of one. It means every
// proposed line was read and accepted, and `save_decisions` stores every line's
// full text for exactly that reason. Gating on `dirty` was the first version of
// this button and it silently did nothing on a page reviewed without edits —
// including one whose ALTO had just gained a recovered line, so `decision.json`
// stayed a line short and `restore` would have refused it forever.
async function done(){
  await save();
  if(st.className==='bad'){
    st.textContent='NOT stopping — save failed, your work is still here';
    return;
  }
  try{ await fetch('/done',{method:'POST'}); }catch(e){}
  dirty=false;
  document.body.innerHTML='<div style="font:15px var(--f);padding:2rem">'+
    '<b>Review server stopped.</b><br>Decisions are saved. '+
    'You can close this tab.</div>';
}
// SESSION-RESTORE GUARD. Firefox restores textarea values across a crash-and-reopen,
// and it restores them BY POSITION, so reopening this page after a crash refilled
// 1-073's fields with 1-151's text — then one keystroke made the debounce save all 47
// of them, and the file said 38 lines edited. Nothing in the page or the server could
// tell that from real work: the payload was well-formed and the text was real
// transcription, just of a different page.
//
// So the server-rendered text is authoritative and is assigned here, after any restore
// has happened. `autocomplete=off` alone is advisory; this is not. Values are compared
// before overwriting only to keep `dirty` honest — an assignment is not an edit.
for(const t of document.querySelectorAll('textarea')){
  const want=t.dataset.text;
  if(t.value!==want) t.value=want;
  grow(t);
  t.addEventListener('focus',()=>{last=t});
  t.addEventListener('input',()=>{grow(t);dirty=true;st.className='';
    st.textContent='unsaved…';refreshEditFlag(t);rebuildEditJump();
    clearTimeout(timer);timer=setTimeout(save,1200)});
}
sv.addEventListener('click',save);
dn.addEventListener('click',done);
// Tier-1 traversal. Focuses the field rather than only scrolling: the point of
// arriving at the line is to key it.
const T1=[...document.querySelectorAll('.ln[data-t1]')];
let t1i=-1;
function goT1(d){
  if(!T1.length) return;
  t1i=(t1i+d+T1.length*2)%T1.length;
  const el=T1[t1i];
  el.scrollIntoView({block:'center',behavior:'smooth'});
  const t=el.querySelector('textarea'); if(t){t.focus();last=t}
}
document.getElementById('t1n').addEventListener('click',()=>goT1(1));
document.getElementById('t1p').addEventListener('click',()=>goT1(-1));
addEventListener('keydown',e=>{
  if(!e.altKey||e.ctrlKey||e.metaKey) return;
  if(e.key==='j'){e.preventDefault();goT1(1)}
  else if(e.key==='k'){e.preventDefault();goT1(-1)}
});
addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue=''}});
</script>""")
    return "\n".join(h)


def serve(ref: str, alto_dir: str = DEFAULT_ALTO_DIR, root: Path = Path("."),
          port: int = 8731) -> None:
    """Serve one page's review at 127.0.0.1 and accept saves.

    Loopback only, and no path routing beyond the two endpoints it needs: this
    holds unpublished editorial work and has no business being reachable.
    """
    import json as _json
    import time
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        # Silence the per-request log: one line per save is enough, GETs are noise.
        # Signature matches the base class rather than `*a` — an override that
        # narrows is a real incompatibility even when the body ignores everything.
        def log_message(self, format: str, *args) -> None:
            pass

        def do_GET(self):
            if self.path not in ("/", "/index.html"):
                self.send_error(404)
                return
            body = render_queue_html(ref, alto_dir, root).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if self.path == "/done":
                # The page asks the server to stop, so nobody has to hunt the
                # process afterwards. A server left bound to a page that has since
                # been restored is how a later save lands on stale text — the
                # rebuild skill warns about exactly that, and telling a human to
                # remember it is a worse fix than a button.
                #
                # Shut down from another thread: `shutdown()` blocks until the
                # serve loop exits, and the serve loop is what is running this
                # handler, so calling it inline would deadlock.
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"{}")
                import threading
                threading.Thread(target=srv.shutdown, daemon=True).start()
                return
            if self.path != "/save":
                self.send_error(404)
                return
            try:
                n = int(self.headers.get("Content-Length") or 0)
                payload = _json.loads(self.rfile.read(n) or b"{}")
                res = save_decisions(ref, payload.get("lines") or {}, root,
                                     stamp=time.strftime("%Y-%m-%dT%H:%M:%S%z"))
            except Exception as e:  # report it to the page, never a blank failure
                msg = _json.dumps({"error": str(e)}).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(msg)))
                self.end_headers()
                self.wfile.write(msg)
                return
            edited_str = ",".join(map(str, res["edited_lines"])) or "none"
            changed_str = f" · changed this save: {','.join(map(str, res['changed_lines']))}" \
                if res["changed_lines"] else ""
            print(f"saved {res['path']}: {res['edited']}/{res['lines']} edited "
                  f"(lines {edited_str}){changed_str}")
            body = _json.dumps(res).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"review {norm_ref(ref)} -> {url}   (Done button on the page, or ctrl-c)")
    print(f"decisions -> {decisions_path(ref, root)}")
    import webbrowser
    webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    else:
        # Reached when the page's Done button called `/done`. Printing it matters:
        # the process exiting is the signal that the review is finished and the
        # page is ready to `restore`, so whoever is driving does not have to ask.
        print("done — server stopped from the page")
    finally:
        srv.server_close()


def summary(spans: list[dict], n_lines: int) -> dict:
    """Counts worth having before deciding whether to open the queue at all."""
    lines_with = {s["index"] for s in spans}
    return {
        "lines": n_lines,
        "lines_identical": n_lines - len(lines_with),
        "spans": len(spans),
        "classes": len({(s["catmus"], s["claude"]) for s in spans}),
        "non_ascii_spans": sum(1 for s in spans if "non_ascii" in s["classes"]),
        "inventory_spans": sum(1 for s in spans if "inventory" in s["classes"]),
        "lookalikes_in_proposal": sum(
            1 for s in spans if "lookalike_in_proposal" in s["classes"]),
    }
