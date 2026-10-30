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
import os
import re
import unicodedata
from collections.abc import Callable
from pathlib import Path

from lxml import etree

from . import corrections as _corr
from .atomic import tmp_for
from .detectors import (
    DOT_ABOVE_G,
    LOOKALIKES,
    bears_inventory,
    inventory_glyphs,
    unlicensed_marks,
)

# Aliased: this module already exposes a `corrections` verb (proposal->decision
# character diffs), which is a different subject entirely.
from .layout import stem_for
from .lines import alto_for_lines, page_lines, raster_path
from .lookup import HANDLE
from .parallel import ptrack
from .paths import crops_dir, decisions_path, html_path, page_dirs, proposal_path
from .proposal_check import NOTE_CLASSES
from .refs import norm_ref
from .usage import since_stamp

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
    if bears_inventory(claude):
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
    against neither (`keying_spec.md` section 1, and the collation skill's CATMuS notes).

    **This is a floor and must be labelled as one wherever it is shown.** Four
    inventory members are unmarked ASCII — `c` for English *sh*, plain `s`, `j`, `x`
    — so a line of pure Tier-1 in those letters produces no glyph here at all. An
    unflagged line is "nothing detected", never "no notation present", and a UI that
    lets the two read alike would turn the flag into an invitation to skip lines.

    **A mark on an orthographic base is not one of them**, which is why this goes
    through `detectors.inventory_glyphs` rather than testing `INVENTORY_CHARS`
    directly. `й` is `и` + U+0306 and `ü` is `u` + U+0308, both inventory members
    under NFD, so a line of pre-reform Russian or a German title was flagged as
    carrying notation and sent the reviewer looking for a Chukchee form that was
    never there — `3-149`'s `служилый` / `приказный` were reported exactly so.
    The floor above is about what this *misses*; this is about what it invents.
    """
    return "".join(dict.fromkeys(inventory_glyphs(text)))


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


def page_spans(ref: str, root: Path, store: str) -> list[dict]:
    """Every differing span on one page, one flat record each."""
    ref = norm_ref(ref)
    prop = load_proposal(ref, root)
    out = []
    for rec in page_lines(alto_for_lines(ref, root, store), root, ref=ref):
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


# The notation keyboard, as a toggled mode. Off by default, so the English
# apostrophe and quotes stay typeable in prose. That is why this is a mode and
# not a remap.
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
# The ASCII row earns its place despite being typeable: U+002D is the connector
# hyphen and U+0021 increased articulation (2.1). They look like ordinary
# punctuation and are not, and clicking them works even with the mode on. U+0027
# is deliberately absent: it has no use inside a Tier-1 span (2.1, §3) — the p.
# 10 key's spirant and pause marks have never been seen in the corpus — so a
# raised comma-shaped mark is the stress key, U+02CA, in the modifiers row.
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
    ("ascii, special function", ["-", "!"]),
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
    # a lookalike trap for stress U+02CA (validate.py's LOOKALIKE_GREPS,
    # "U+2019 traps U+02CA") — never something to type there.
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
                   stamp: str | None = None, withdraw: bool = False) -> dict:
    """Write adjudicated lines, recording for each whether it differs from the proposal.

    **An empty `lines` replaces the page's whole adjudication with nothing**, and
    `withdraw` is how that is said. This is the same guard `corrections.save_lines`
    carries and it belongs here more, not less: `.prev` is one save deep, and
    while the journal below survives anything, an empty save appends a record of
    *nothing changed* — so the journal preserves the fact of the truncation and
    none of what it took. A payload that arrives `{}` because a key was dropped,
    a ref was mistyped or a probe was careless is indistinguishable from a human
    clearing every line, which nobody has ever wanted to do.

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
    if not lines and before and not withdraw:
        raise ValueError(
            f"{ref}: refusing to replace {len(before)} adjudicated line(s) with "
            f"nothing. An empty save is what a dropped key or a mistyped ref "
            f"looks like by the time it arrives here, and it is not a ruling "
            f"anybody makes — clearing a page line by line is. If it is really "
            f"meant, say so: `withdraw=True`. `.prev` holds one save, and the "
            f"journal would record the truncation without recording what it took.")
    out = {}
    for k, v in lines.items():
        idx = int(k)
        text = _nfd(v if isinstance(v, str) else v.get("text", ""))
        proposed = _nfd(prop[idx]["text"]) if idx in prop else None
        out[str(idx)] = {"text": text, "edited": proposed is not None
                         and text != proposed}
        # The adjudicator's own note, and **stored only when it says something**.
        # An empty `note` on every line would be the same noise in the file that a
        # textarea on every line is on screen, and it would make "this line was
        # remarked on" unfindable by the only means anyone has — the key existing.
        # Distinct from the proposal's `note`, which is the reader's: these two
        # live in different files precisely so a human ruling is never mistaken
        # for the model's account of what it did.
        note = _nfd("" if isinstance(v, str) else (v.get("note") or "")).strip()
        if note:
            out[str(idx)]["note"] = note
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
    tmp = tmp_for(p)
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


# Longer than this on either side of an opcode and the change is a rewrite rather
# than a character slip, so it is reported by size instead of by content. Without
# the cap a whole-line retype mints a row nothing else will ever match, and the
# table stops being a frequency ranking and becomes a list of one-offs — the same
# failure `zones check`'s adjacent-band merge exists to prevent, where 38 rows for
# one missing region buried the finding.
_CORRECTION_MAX_RUN = 12


def _describe(old: str, new: str) -> str:
    if len(old) >= _CORRECTION_MAX_RUN or len(new) >= _CORRECTION_MAX_RUN:
        return f"<{len(old)}ch> -> <{len(new)}ch>"
    return f"{old!r} -> {new!r}"


def corrections(root: Path = Path("."), refs: list[str] | None = None,
                since: str | None = None, tick: Callable | None = None) -> dict:
    """Character-level proposal->decision corrections, aggregated across pages.

    What the adjudicator changed is the only record of what readers actually get
    wrong, and until now it was computed per page (`restore`'s `edits`) and thrown
    away with the process. It lives here rather than in `proposal_check` because
    it reads *both* files, and only this module owns both.

    Opcodes come from `difflib` over **NFD** text, so a dropped combining mark
    ranks as an insert of the mark itself rather than as a replacement of its host
    word. That is what makes the ranking legible at all: 37 dropped dots-below
    across eight pages collapse to one row, where a word-level diff would scatter
    them over 37 rows nothing could ever match.

    **Scopable, and that is not a convenience.** The store spans this project's
    own history: pages keyed before a rule existed carry error classes that rule
    has since made impossible, so a bare aggregate reads as a live error profile
    when it is partly archaeology. The leading class is 117 straight apostrophes
    across exactly two pages, keyed before a bare apostrophe became its own
    unconditional error (`detectors.apostrophe_flags`); it cannot recur in that
    form. Scoped to 2026-07-31 the only recurring class left is `i` -> `ɪ`, four
    times on three pages. `since` filters on `decision.json`'s own `saved_at`.

    **A structural undercount, stated rather than fixed.** A coordinator repair via
    `proposal_check.set_field`/`replace_in_field` overwrites `proposal.json` in
    place, so a reader error corrected *before* adjudication leaves no
    proposal->decision diff at all — `2-033`'s four bare `g` went exactly that way
    and are invisible here. This measures what reached the adjudicator, never what
    the reader first wrote, and the earlier the loop catches a slip the less of it
    appears. That is the intended direction of travel, not a defect to repair.
    """
    want = {norm_ref(r) for r in refs} if refs else None
    # Resolved once, and it accepts `5m`/`2h`/`1d` as well as a date. Comparison
    # below is lexicographic against `saved_at`, so a duration passed raw would
    # sort *after* every stamp and silently exclude every page — an empty report
    # at exit 0, which is the shape of a right answer. `since_stamp` raises on
    # anything it cannot read rather than filtering with it.
    since = since_stamp(since, tz=None) if since is not None else None
    counts: dict[str, int] = {}
    pages: dict[str, set[str]] = {}
    stamps: dict[str, list[str]] = {}
    by_page: list[dict] = []
    skipped_unstamped: list[str] = []
    # The work-list is every review directory, so the bar counts directories
    # rather than the pages that turn out to hold both files — the denominator a
    # caller can know before the sweep starts, which is the rule `predict_all`
    # set and every other instrumented sweep here follows.
    for d in ptrack(page_dirs(root), tick):
        ref = norm_ref(d.name)
        if want is not None and ref not in want:
            continue
        p, dc = d / "proposal.json", d / "decision.json"
        if not (p.exists() and dc.exists()):
            continue
        doc = json.loads(dc.read_text(encoding="utf-8"))
        saved_at = doc.get("saved_at") or ""
        if since is not None:
            # An unstamped page is *excluded and counted*, never silently dropped:
            # dropped, it is indistinguishable from a page with nothing to report,
            # which is the blank-vs-`?` rule `_ink_cache.json` states for the zone
            # editor's page list — a missing verdict must not draw in the same
            # column as a clean one.
            if not saved_at:
                skipped_unstamped.append(ref)
                continue
            if saved_at < since:
                continue
        prop = json.loads(p.read_text(encoding="utf-8")).get("lines", {})
        dec = doc.get("lines", {})
        here: dict[str, int] = {}
        changed = 0
        for idx, rec in dec.items():
            before = _nfd((prop.get(idx) or {}).get("text", ""))
            after = _nfd(rec.get("text", ""))
            if before == after:
                continue
            changed += 1
            sm = difflib.SequenceMatcher(None, before, after, autojunk=False)
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag == "equal":
                    continue
                key = _describe(before[i1:i2], after[j1:j2])
                here[key] = here.get(key, 0) + 1
        for key, n in here.items():
            counts[key] = counts.get(key, 0) + n
            pages.setdefault(key, set()).add(ref)
            if saved_at:
                stamps.setdefault(key, []).append(saved_at)
        top = max(here.items(), key=lambda kv: (kv[1], kv[0])) if here else ("", 0)
        by_page.append({"ref": ref, "saved_at": saved_at, "lines": len(dec),
                        "changed": changed, "top_change": top[0], "top_count": top[1]})
    changes = []
    for key, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        seen = sorted(stamps.get(key, []))
        changes.append({"change": key, "count": n,
                        # Space-joined, never a nested list: TOON collapses a record
                        # list to a header plus rows only while every cell is scalar
                        # (`emit.py`), and one list-valued cell degrades the whole
                        # table to the verbose form.
                        "pages": " ".join(sorted(pages[key])),
                        "first_seen": seen[0] if seen else "",
                        "last_seen": seen[-1] if seen else ""})
    return {"pages_read": len(by_page),
            "lines": sum(r["lines"] for r in by_page),
            "changed": sum(r["changed"] for r in by_page),
            "skipped_unstamped": " ".join(skipped_unstamped),
            "changes": changes, "by_page": by_page}


def restore_skip(ref: str, root: Path = Path("."), force: bool = False) -> str:
    """Why this page should not be restored in a sweep, or `""` to go ahead.

    One rule in one place, `predict_skip`'s shape and its reasoning: the callers
    are `--all` and the multi-ref loop, and a CLI that decided for itself would
    be a second copy of this, drifting from it the moment either changed.

    **The mtime test is what lets a sweep run at all.** `restore` refuses a target
    already holding text unless `force`, which is right for a named page — every
    page in `gt/ocr/` holds text now, so overwriting one is a deliberate act. Over
    a whole store that guard would refuse everything, so the sweep asks a sharper
    question instead: *is this decision newer than the ground truth it produced?*
    If it is not, the page has already been restored since it was adjudicated and
    there is nothing to write. If it is, the adjudication is the human's own
    latest act on that page and the sweep restores it — passing `force` on its
    behalf, which is the same intent the flag carries, established by the
    timestamps rather than by typing it.

    `force` here means the other thing `--all --force` means: ignore the mtime
    test and restore every page that has a decision at all.

    Deliberately **not** an `mtime >` on the *proposal*: a proposal is a reading,
    not an adjudication, and re-authoring one does not license a write.
    """
    dec = decisions_path(ref, root)
    if not dec.exists():
        return "no decisions"
    if force:
        return ""
    target = root / "gt" / "ocr" / f"{stem_for(ref, root)}.xml"
    if target.exists() and target.stat().st_mtime >= dec.stat().st_mtime:
        return "ground truth is already newer than the decision"
    return ""


def restore(ref: str, root: Path, store: str,
            force: bool = False, commit: bool = False) -> dict:
    """Write adjudicated text into `gt/ocr/chukchi-<ref>.xml`, keeping the geometry.

    The ALTO in `store` is the skeleton: every line has exactly one `String`
    whose box mirrors the `TextLine`'s, so this only sets `@CONTENT`; nothing
    structural moves.

    **Two modes, and the returned `mode` field says which one ran.** They differ
    only in whether the geometry source and the write target are the same file,
    which is now a question of which store the caller named:

      * `restoration` — `store` is `mz/ocr/`, and `gt/ocr/` is being filled in
        from the prediction's skeleton. This is the ordinary case at the stage the
        verb runs: a page reaches adjudication with a machine reading and no
        ground truth, and this is the act that creates it.
      * `revision` — `store` is `gt/ocr/`: re-adjudicating a finished page reads
        its own geometry and writes its own text back. `--store gt` is how a
        caller says so, and `force` is required besides.

    Revision is *safe* rather than merely tolerated, and it is worth saying why,
    because "reads the file it writes" is normally a bug. `etree.parse` builds the
    whole tree in memory before anything is written; the write goes to a `.tmp`
    sibling; and the post-write verification below re-reads `src`, which the
    `tmp.replace(target)` has not yet touched. So the source is never observed
    half-written. The `mode` field exists because the operation is nonetheless a
    different act in the two cases — one reconstructs, the other edits in place —
    and a caller that cannot tell them apart cannot report honestly on either.

    Writes `gt/ocr/` by name, and reads the store it was given by name. It used to
    read through the `ocr/` view, under which the source could *silently* be the
    target — the mode had to be discovered by resolving symlinks. With every read
    naming its store, the mode is a fact the caller stated.

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
                         f"(harness ocr review {ref})")

    src = alto_for_lines(ref, root, store)
    tree = etree.parse(str(src))
    lines = list(tree.iter("{*}TextLine"))

    # **The merged view is the index space, so a correction is not a hole.** A
    # line a human drew in `ocr edit` lives in `gt/lines/`, is appended after the
    # ALTO's last index by `page_lines`, and is adjudicated in the browser like any
    # other line — so it has a decision, and that decision has to land somewhere.
    # `ref` is passed explicitly here and on the verification below: `tmp` is
    # `chukchi-PP-NNN.xml.tmp`, whose stem parses as no ref, and a fold that
    # applied to one side and not the other would surface as this function
    # reporting that its own write had lost lines.
    recs = page_lines(src, root, ref=ref)
    corrected = [r for r in recs if r["src"] == "corr"]

    missing = [i for i in range(len(recs)) if i not in dec]
    if missing:
        raise ValueError(f"{ref}: {len(missing)} of {len(recs)} lines have no "
                         f"decision (indices {missing[:12]}…); refusing a partial "
                         "restore — ground truth with holes is worse than none")
    # **The converse, and it was unguarded.** A decision keyed to an index the
    # page does not have is text with no box: the write loop below iterates the
    # ALTO's lines and the correction join tests `id in index_of`, so such a key
    # was dropped in silence — adjudicated text that reached no store. It used to
    # be `proposal check`'s finding, at the reader, whose remedy it never was
    # ("that is upstream human action and not yours to correct"). The join is
    # here, so both halves of it refuse here.
    orphans = sorted(i for i in dec if not 0 <= i < len(recs))
    if orphans:
        raise ValueError(
            f"{ref}: decisions {orphans[:12]} name no line — the page holds "
            f"{len(recs)} (indices 0–{len(recs) - 1}, corrections included). "
            "A reading with no box to land in is not a reading; if it is printed "
            "matter the segmenter missed, give the band a box in `harness ocr edit` "
            "and adjudicate it there, otherwise drop the key")

    bad = [f"line {i}: {h['mark']} on {h['base']} (licensed on "
           f"{h['licensed_on']}) in {h['context']!r}"
           for i in sorted(dec) for h in unlicensed_marks(dec[i]["text"])]
    if bad:
        raise ValueError(
            f"{ref}: {len(bad)} unlicensed mark(s) in the adjudicated text; "
            "refusing to write. These are sequences the notation does not contain "
            "(keying spec 2.6), not readings to weigh, so re-key them in "
            f"harness ocr review {ref}:\n  " + "\n  ".join(bad))

    target = root / "gt" / "ocr" / f"{stem_for(ref, root)}.xml"
    # The same file under the name it was given is `revision`; any other source is
    # a `restoration` from a separate store. A name test suffices now that no
    # symlink view can make two names one file.
    mode = "revision" if src == target else "restoration"
    if target.exists() and not force:
        existing = sum(len(s.get("CONTENT") or "")
                       for s in etree.parse(str(target)).getroot().iter("{*}String"))
        # The fragment counts too: a corrected line's adjudicated text lives there
        # and nowhere else, so a guard that only looked at `gt/ocr/` would wave
        # through the overwrite of the one reading with no second copy.
        existing += sum(len(r["text"]) for r in _corr.load_lines(ref, root))
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

    # **Text goes to the store its line came from**, which is what keeps `restore`
    # the only writer of ground-truth *text* now that a line can live in two
    # places. The join is by `corr_` id rather than by position: the fragment is
    # ordered by geometry and a human may have nudged a box since, where the id was
    # minted once and travels with it.
    frag = _corr.load_lines(ref, root)
    index_of = {r["line_id"]: r["index"] for r in corrected}
    boxes = [dict(b, text=_nfd(dec[index_of[b["id"]]]["text"]))
             for b in frag if b["id"] in index_of]

    # Always written to a scratch path and verified from there — `commit` only
    # gates the final `tmp.replace(target)` below, so dry-run and real-write share
    # one code path rather than a preview implementation drifting from the real one.
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = tmp_for(target)
    tree.write(str(tmp), xml_declaration=True, encoding="UTF-8", standalone=None)

    # Verify against the source rather than trusting the write: geometry identical,
    # text exactly what was adjudicated.
    a = page_lines(src, root, ref=ref)
    b = page_lines(tmp, root, ref=ref)
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
    # Only the ALTO's own lines are verifiable from `tmp`: a correction's text is
    # written to the fragment, and both sides of this comparison fold the fragment
    # as it still stands on disk. The corrected lines are verified after their
    # write, below, by reading the store back.
    wrong = [y["index"] for y in b if y["src"] == "alto"
             and y["text"] != _nfd(dec[y["index"]]["text"])]
    # `edits` names what changed, not just how many lines did — "edited_by_human: 2"
    # used to be the whole answer, and finding out *what* meant hand-rolling a
    # proposal-vs-decision diff script each time. `load_proposal` can be missing a
    # line decisions has (a line added after the proposal was authored, in theory),
    # so `.get` rather than assuming symmetry.
    prop = load_proposal(ref, root)

    # **Computed against the proposal, not read off the decision's `edited` flag.**
    # The flag is the review server's own bookkeeping, written when a box changes
    # under a human's hands; the proposal is the record the diff is *defined*
    # against. Where the two can disagree, the derived one has to win, and they can:
    # a decision revised through `proposal replace --path` — which is how a ruling
    # about a whole class of lines gets applied across pages — changes `text` and
    # leaves the flag false, so the page reported `edited_by_human: 0` while
    # carrying three corrections. `edits` is the error profile this pass exists to
    # produce, so a silent zero there is worse than a wrong glyph.
    #
    # It also fixes the other direction, which nobody had noticed: a line the
    # adjudicator retyped identically carried the flag and appeared as an edit
    # whose two sides were the same string.
    def _changed(i, v) -> bool:
        if i not in prop:
            return True          # arrived from somewhere the proposal has no line for
        return _nfd(prop[i]["text"]) != _nfd(v["text"])

    edits = [{"line": i, "proposal": prop[i]["text"] if i in prop else "(gone from proposal)",
             "decision": v["text"]}
            for i, v in sorted(dec.items()) if _changed(i, v)]
    # Reported separately, and **not** folded into `edits`, because a note is not
    # an edit and the commonest note is on a line whose text nobody changed —
    # `2-036`'s speck was ruled "ink smudge" and left empty, so it is invisible to
    # any list keyed on `edited`. That was the whole defect: the adjudicator's
    # ruling lived in decision.json and appeared in no report about the page.
    # Its own table rather than a column on `edits` keeps one key set per table
    # (a ragged list degrades to the verbose nested form — see emit.py) and keeps
    # `edited_by_human` meaning what it has always meant.
    notes = [{"line": i, "note": v["note"]}
             for i, v in sorted(dec.items()) if v.get("note")]

    if not commit:
        tmp.unlink()
        return {"path": str(target), "source": str(src), "mode": mode,
                "lines": len(recs), "corrections": len(boxes),
                "chars": sum(len(_nfd(v["text"])) for v in dec.values()),
                "geometry_drift": drift, "text_mismatch": wrong,
                "edited_by_human": len(edits), "edits": edits,
                "noted": len(notes), "notes": notes, "commit": False}
    tmp.replace(target)
    # The fragment second, and verified by reading it back rather than trusting the
    # write — the same rule the ALTO side follows above. `save_lines` rebuilds the
    # file from these boxes, so it must be handed every correction on the page and
    # not only the ones whose text changed.
    if boxes:
        _corr.save_lines(ref, boxes, root)
        after = {b["id"]: b["text"] for b in _corr.load_lines(ref, root)}
        wrong += [i for cid, i in sorted(index_of.items(), key=lambda kv: kv[1])
                  if after.get(cid) != _nfd(dec[i]["text"])]
    return {"path": str(target), "source": str(src), "mode": mode,
            "lines": len(recs), "corrections": len(boxes),
            "chars": sum(len(_nfd(v["text"])) for v in dec.values()),
            "geometry_drift": drift, "text_mismatch": wrong,
            "edited_by_human": len(edits), "edits": edits,
            "noted": len(notes), "notes": notes, "commit": True}


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def _edit_jump_inner(idxs: list[int]) -> str:
    """The 'Edited lines' jump-list body, for the initial server render. `save()`'s
    JS rebuilds the same markup client-side after each save, so the list stays
    current without a reload.

    Held to `review.js`'s `rebuildEditJump` by
    `test_review_session.test_the_edit_jump_markup_is_the_same_on_both_sides`.
    This used to say "keep the two in sync if this format changes" and rest on
    somebody doing so; a divergence is silent by construction, since both sides
    look right alone and the list only stops matching itself across a save.
    """
    if not idxs:
        return "<b>Edited lines:</b> none yet"
    return "<b>Edited lines:</b> " + " ".join(f"<a href='#l{i}'>{i}</a>" for i in idxs)


# **Brill first, because this is a Brill book.** The Memoirs are set in the house
# face the Brill typeface was drawn from, so a reviewer scanning the crop against
# the entry is comparing two renderings of one design rather than translating
# between two — which is the whole ergonomic question here, the crop and the box
# sitting one above the other. It carries the entire inventory, laryngeals and
# dots-below included, and is free from the publisher.
#
# DejaVu Serif stays as the fallback and keeps its old argument: its single-storey
# `g` has a short descender, so a U+0323 under the bowl stays legible where a
# tighter face crowds it. That is the one thing Brill is worse at, and it is worth
# knowing when a dot is the question — which is why the face is now a knob and not
# a constant.
#
# **No webfont, deliberately.** These are locally installed, and a CSS reference to
# a remote font can silently substitute a face that lacks a glyph, which is the
# same class of failure as a terminal showing a box: the text looks fine and is
# not what it says.
DEFAULT_FONT = "Brill"
_FALLBACK = "'DejaVu Serif', 'Charis SIL', 'Noto Sans', sans-serif"

# **24px, set by looking at it.** The entry text is what a reviewer reads for an
# hour, against a crop of type printed at 300 dpi, and Brill runs small for its em
# — so the size that was comfortable in a UI serif is not the size that is
# comfortable here. This is the value the steppers arrived at in use, not a
# default carried over from a face nobody is reading in any more.
DEFAULT_FONT_SIZE = 24
DEFAULT_BOX_LINES = 1


def font_stack(font: str | None = None) -> str:
    """The CSS stack: the chosen face, then the standing fallbacks.

    Prepended rather than replacing, so a name that is not installed degrades to a
    readable page instead of the browser's default serif — a font that silently
    did not load is exactly the failure this view cannot afford.
    """
    name = (font or DEFAULT_FONT).strip()
    # **Confined to what a CSS family name can hold**, because the result is
    # interpolated into a `<style>` block and marked safe there — it has to be,
    # since the quotes a stack needs would otherwise be escaped into `&#39;` and
    # the whole declaration silently ignored, leaving the reviewer comparing a
    # Brill crop against the browser's default serif with nothing to say so.
    # Sanitising here rather than escaping there is the narrower fix: a family
    # name has no legitimate use for `<`, `;` or a newline.
    name = re.sub(r"[^\w \-'\"]", "", name).strip()
    if not name:
        return _FALLBACK
    quoted = name if name.startswith(("'", '"')) else f"'{name}'"
    # A face already in the fallbacks is promoted, not repeated: CSS ignores the
    # duplicate, but a stack naming one family twice reads as a bug to whoever
    # next opens the page source.
    rest = [f for f in _FALLBACK.split(", ") if f.strip("'\"") != quoted.strip("'\"")]
    return ", ".join([quoted, *rest])


def _palette() -> list[dict]:
    """The insertion palette, shared by every page that offers one.

    Factored when the issue list became a second such page: the two pages differ
    in what they show *about* a line, and not at all in what a keyboard can put
    into one, so a second copy would have been a second inventory to keep true.
    """
    binding = {g: k for k, g in KBD_GLYPHS.items()}
    binding.update({m: k for k, m in KBD_MARKS.items()})
    palette = []
    for label, glyphs in PALETTE:
        keys = []
        for g in glyphs:
            combining = len(g) == 1 and unicodedata.category(g) == "Mn"
            keys.append({
                "glyph": g, "key": binding.get(g, ""),
                "combining": combining,
                "shown": ("◌" + g) if combining else g,
                "tip": codepoints(g) + (" — attaches to the character before "
                                        "the caret" if combining else ""),
            })
        # `glyphs`, not `keys`: Jinja resolves `grp.keys` to the dict *method*
        # before it looks for the key, so the palette group would silently
        # iterate a bound method. Same trap as `row.items` in the entity card —
        # named around rather than worked around, because the next person adding
        # a group would hit it too.
        palette.append({"label": label, "glyphs": keys})
    return palette


def page_context(ref: str, root: Path,
                 store: str, crops: Path | None = None,
                 queue: list[dict] | None = None,
                 scan_href: str | None = None,
                 crop_base: str = "crops",
                 font: str | None = None, font_size: int | None = None,
                 box_lines: int | None = None) -> dict:
    """Everything one ref's review page needs, as data.

    `queue` is the session's other pages — `[{"ref", "done"}, …]` in the order the
    reviewer asked for them — and it only ever adds a nav strip and changes what
    the Done button says. A one-page session passes `None` and gets neither: a
    nav bar over a queue of one is furniture that says "there is somewhere else
    to be" when there is not. The queue is a frame around this, never a mode
    inside it.

    Everything below the strip is about one ref, because a review *is* one page
    at a time and pretending otherwise is how a reviewer keys 1-073's text into
    1-151's fields (see the session-restore guard). Pages are reached by
    navigation, never merged into one document.

    **The unit is the line, not the span.** An earlier version grouped by
    substitution class on the grounds that glyphs are 3.3% of characters, but that
    measures the wrong cost: the expensive act is re-orienting to a different line,
    not reading the characters in a line you already have open. Since 44% of lines
    need some attention, those lines get opened regardless, and once open the rest
    of the line is nearly free. Span-grouping also scattered one line's corrections
    across the queue, so their sum could not be seen.

    **Every line is listed**, including the ones CATMuS agrees with: agreement
    about ASCII is weak evidence and it has no vote on a glyph whatsoever, so
    agreement only sets emphasis.

    **`crop_base` is why the crops are no longer base64.** They are files on disk
    under `review/<ref>/crops/`, and they were inlined into a `<style>` block —
    311 KB on 1-021, re-sent uncached on every navigation — because the old
    handler had exactly one image route and no way to *address* one. Served, it
    is a URL; written by `--html`, it is the relative path from the page to the
    directory beside it, which works straight off the filesystem.
    """
    from PIL import Image

    from .lines import write_line_crops
    ref = norm_ref(ref)
    crops = crops or crops_dir(ref, root)
    recs = {r["index"]: r for r in write_line_crops(ref, crops, root, store)}
    # Reading order, not index order. `recs` is keyed by `index` because that is the
    # identity the client submits and `save_decisions` stores under; but iterating
    # `sorted(recs)` would walk the *segmenter's* order, which is not reading order on
    # 18 of the 20 restored pages — a running head lands mid-sequence, a folio last.
    order = sorted(recs, key=lambda i: recs[i]["y_rank"])
    prop = load_proposal(ref, root)
    saved = load_decisions(ref, root)
    spans = page_spans(ref, root, store)
    summ = summary(spans, len(recs))

    # Computed over the text on screen — saved edits included — not over the
    # proposal alone, so a glyph the reviewer has just typed flags its line at once.
    t1 = {idx: tier1_glyphs(_nfd((saved.get(idx) or prop[idx])["text"]))
          for idx in order if idx in prop}
    t1 = {k: v for k, v in t1.items() if v}

    # Default is the on-disk relative path, computed rather than spelled, so the
    # `--html` file works opened straight off the filesystem; the server overrides
    # it with a route, since a browser will not follow file:// from an http origin.
    if scan_href is None:
        scan_href = os.path.relpath(raster_path(ref, root),
                                    html_path(ref, root).parent)

    edited_now = [idx for idx in order if idx in prop and idx in saved
                  and _nfd(saved[idx]["text"]) != _nfd(prop[idx]["text"])]

    differing = {s["index"] for s in spans}
    lines = []
    for idx in order:
        rec = recs[idx]
        # A line in the ALTO with no proposal entry used to be skipped in silence,
        # which is the same class of defect as a hole in ground truth: the queue
        # rendered as complete while a line was unreachable. It happens for real —
        # a line recovered in `ocr edit` has geometry before it has any reading.
        # Render it empty and say so.
        mine = prop.get(idx) or {"text": ""}
        proposed = _nfd(mine["text"])
        # Saved work wins on reload, so a session can be resumed. The proposal is
        # still what `edited` is measured against, server-side.
        full = _nfd(saved[idx]["text"]) if idx in saved else proposed
        agree = idx not in differing
        glyphs = t1.get(idx, "")
        # An unclassed note still counts as noted — the undimming is the reader's
        # to earn by writing anything at all, and the class only decides which
        # badge it wears.
        nclass = (mine.get("class") or "note") if mine.get("note") else ""
        if nclass not in NOTE_CLASSES:
            nclass = "note" if nclass else ""
        # **Derived, never asserted.** A line whose glyphs came out of ratified
        # ground truth rather than off this raster is a claim about provenance, and
        # the reader making the claim is the last party who should get to decide
        # whether it shows.
        typed = mine.get("as_typed", "")
        path = Path(rec["crop"])
        # `.size` reads the header only, so this is a stat rather than a decode.
        w, ht = Image.open(path).size
        # Full column width. Never upscaled past 1:1 — a magnified bitonal crop
        # invents smoothness, and the reviewer should see the raster it is.
        scale = min(1.0, 1040 / w)
        lines.append({
            "idx": idx,
            "cls": ("ln" + (" agree" if agree else "") + (" t1" if glyphs else "")
                    + (" noted" if nclass or typed else "")),
            "line_id": rec["line_id"], "glyphs": glyphs, "typed": typed,
            "typed_html": HANDLE.sub(lambda m: f"<b>{_esc(m.group(0))}</b>",
                                     _esc(typed)) if typed else "",
            "has_proposal": idx in prop,
            # Off `src` rather than off the id's spelling: a recovered line is one
            # the merge added from `gt/lines/`, a fact the record already carries.
            "recovered": rec.get("src") == "corr",
            "agree": agree, "edited": full != proposed,
            "crop": f"{crop_base}/{path.name}",
            "w": round(w * scale), "h": round(ht * scale),
            "full": full, "proposed": proposed,
            "marks": codepoints("".join(
                dict.fromkeys(c for c in full if ord(c) > 127))),
            "catmus": rec["text"], "note": mine.get("note", ""), "nclass": nclass,
            "extra": [(k, mine[k]) for k in ("resolved", "corrected")
                      if mine.get(k)],
            "hnote": (saved.get(idx) or {}).get("note", ""),
        })

    palette = _palette()

    # Is there another page waiting after this one? Only pages *other* than this
    # one count: re-opening a page already marked done and pressing Done again
    # must not claim there is somewhere to go when this was the last of them.
    pending = [q["ref"] for q in (queue or [])
               if q["ref"] != ref and not q["done"]]
    return {
        "ref": ref, "summ": summ, "t1": t1, "lines": lines, "palette": palette,
        "queue": queue or [], "done_n": sum(1 for q in (queue or []) if q["done"]),
        "scan_href": scan_href,
        "edit_jump": _edit_jump_inner(edited_now),
        "done_label": f"Done → next ({len(pending)} left)" if pending else "Done",
        "done_title": ("save, mark this page adjudicated, and open the next one"
                       if pending else "save if needed, then stop the server"),
        "type": {"font": font_stack(font),
                 "size": int(font_size or DEFAULT_FONT_SIZE),
                 "box_lines": max(1, int(box_lines or DEFAULT_BOX_LINES))},
        "kbd_glyphs": KBD_GLYPHS, "kbd_marks": KBD_MARKS,
    }



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


# ---------------------------------------------------------------------------
# Issue lists: a worklist of individual lines, across pages, on one document.
#
# **This is the one place the "one page at a time" rule is deliberately broken,
# and the guards below are the price.** `page_context` says why the rule exists:
# a field belonging to a page other than the one the reviewer thinks they are
# keying is this pass's oldest and worst failure, and the incident behind it was
# Firefox restoring textarea values *by position* after a crash. Naming the ref
# in the payload — the `Save.ref` guard — does not catch that, because a
# positional refill lands in fields whose server-rendered labels never moved.
#
# So a distributed page carries two guards a single-ref page does not need:
#
#   * **all-or-nothing, and the unit is the ruling.** Every listed line must
#     arrive carrying a note. The text is pre-filled and most lines will not need
#     it changed — "that's fine" is the commonest outcome of looking — so a page
#     that demanded a text edit per field would be asking for the wrong thing.
#     What a flagged line owes is a verdict, and a flag with no verdict is the
#     open question this mode exists to close.
#   * **prior-text.** Each field carries the text the server sent for it, and a
#     save whose prior no longer matches the store is refused. A positional
#     refill changes the priors, which is exactly the signal the incident had no
#     way to produce.
#
# And it patches only: a ref with no `decision.json` is refused, because merging
# a few edited lines over a proposal would ratify every *unlisted* line as
# accepted-unread. That is `docs/decisions.md`'s "an empty list meant delete
# everything" in a new costume — the payload says a little and the write would
# mean a lot.
# ---------------------------------------------------------------------------

ISSUE = re.compile(r"^(?P<ref>\d+-\d+)\s*:\s*(?P<index>\d+)\s+(?P<issue>\S.*)$")


def parse_issues(text: str) -> list[dict]:
    """`PP-NNN:LINE  what is wrong with it`, one per line.

    Blank lines and `#` comments are skipped, so a list can be pasted with the
    heading a person wrote it under. The issue text is **required**: a worklist
    entry that does not say what to look at is a line number, and the reviewer
    already had those.

    Refused on a duplicate `ref:line`, because two entries for one field would
    render two boxes writing to the same place, and the second would silently win.
    """
    items: list[dict] = []
    seen: set[tuple[str, int]] = set()
    for n, raw in enumerate(text.splitlines(), start=1):
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        m = ISSUE.match(s)
        if not m:
            raise ValueError(
                f"line {n}: {raw.strip()!r} is not `PP-NNN:LINE issue text` — "
                f"a ref, a colon, the line index, then what to look at")
        ref, idx = norm_ref(m["ref"]), int(m["index"])
        if (ref, idx) in seen:
            raise ValueError(f"line {n}: {ref}:{idx} is listed twice — "
                             f"one entry per line, or the second overwrites the first")
        seen.add((ref, idx))
        items.append({"ref": ref, "index": idx, "issue": m["issue"].strip()})
    if not items:
        raise ValueError("no issues in the list — expected `PP-NNN:LINE issue text`")
    return items


def _text_now(idx: int, prop: dict, saved: dict) -> str:
    """What the store holds for a line: the adjudicated text where there is one,
    the proposal otherwise. The same precedence the single-ref page uses, and the
    value the prior-text guard is taken against."""
    if idx in saved:
        return _nfd(saved[idx]["text"])
    return _nfd(prop[idx]["text"]) if idx in prop else ""


def issues_context(items: list[dict], root: Path,
                   store: str, crop_base: str = "crops",
                   font: str | None = None, font_size: int | None = None,
                   box_lines: int | None = None) -> dict:
    """One document: every listed line, each with a context line either side.

    The context lines are read-only and are there for the questions a crop cannot
    answer alone — whether a wrap took a hyphen, whether a quote opened on the
    line above. They are **neighbours in reading order**, not in index order:
    `write_line_crops` gives the segmenter's order, and on most restored pages
    that puts a running head mid-sequence.

    A listed line the store has no record of is rendered as a refusal rather than
    an empty box, and it is reported before the socket is bound — see the CLI.
    """
    from PIL import Image

    from .lines import write_line_crops

    blocks, missing = [], []
    cache: dict[str, tuple] = {}
    for it in items:
        ref = it["ref"]
        if ref not in cache:
            recs = {r["index"]: r
                    for r in write_line_crops(ref, crops_dir(ref, root),
                                              root, store)}
            order = sorted(recs, key=lambda i: recs[i]["y_rank"])
            cache[ref] = (recs, order, load_proposal(ref, root),
                          load_decisions(ref, root))
        recs, order, prop, saved = cache[ref]
        idx = it["index"]
        if idx not in recs:
            missing.append(f"{ref}:{idx}")
            continue
        at = order.index(idx)
        rec = recs[idx]
        path = Path(rec["crop"])
        w, ht = Image.open(path).size
        scale = min(1.0, 1040 / w)
        text = _text_now(idx, prop, saved)
        blocks.append({
            "ref": ref, "idx": idx, "issue": it["issue"],
            "field": f"{ref}:{idx}",
            "before": ({"idx": order[at - 1],
                        "text": _text_now(order[at - 1], prop, saved)}
                       if at > 0 else None),
            "after": ({"idx": order[at + 1],
                       "text": _text_now(order[at + 1], prop, saved)}
                      if at + 1 < len(order) else None),
            "text": text,
            # The value the save is checked against. Rendered into the field so a
            # refill that moves text between boxes moves the *text* and not this.
            "prior": text,
            "crop": f"{crop_base}/{ref}/{path.name}",
            "w": round(w * scale), "h": round(ht * scale),
            "note": (prop.get(idx) or {}).get("note", ""),
            # The badge the single-page view has shown since notes gained classes.
            # Absent here until the caption pass needed the same head, which is
            # the ordinary way a shared template's two callers drift: the field
            # existed in the store and only one renderer asked for it.
            "nclass": (prop.get(idx) or {}).get("class", ""),
            "hnote": (saved.get(idx) or {}).get("note", ""),
            "marks": codepoints("".join(
                dict.fromkeys(c for c in text if ord(c) > 127))),
        })
    return {"blocks": blocks, "missing": missing, "palette": _palette(),
            "kbd_glyphs": KBD_GLYPHS, "kbd_marks": KBD_MARKS,
            "refs": list(dict.fromkeys(b["ref"] for b in blocks)),
            "count": len(blocks),
            "font": font or DEFAULT_FONT,
            "font_size": font_size or DEFAULT_FONT_SIZE,
            "box_lines": box_lines or DEFAULT_BOX_LINES}


def patch_decisions(edits: list[dict], root: Path = Path("."),
                    stamp: str | None = None) -> list[dict]:
    """Overlay edited lines onto existing adjudications, one write per ref.

    `edits` is `[{"ref", "index", "text", "prior", "note"}, …]` and must be
    **complete** against the list the page was built from; the caller checks that,
    because only the caller knows what was listed. Everything here is the store's
    half:

    * a ref with no `decision.json` is refused — this patches adjudications, it
      does not make them;
    * a line whose `prior` no longer matches the store is refused, naming both, so
      a stale tab or a positionally-refilled form fails loudly instead of writing;
    * the write goes through `save_decisions` with the ref's **whole** line set, so
      `restore`'s "refuses on any missing line" stays true and `edited` is still
      computed against the proposal rather than against what the page believed.

    Nothing is written until every ref has passed, so a bad entry on the second
    page cannot leave the first already patched.
    """
    by_ref: dict[str, list[dict]] = {}
    for e in edits:
        by_ref.setdefault(norm_ref(e["ref"]), []).append(e)

    planned = []
    for ref, group in by_ref.items():
        saved = load_decisions(ref, root)
        if not saved:
            raise ValueError(
                f"{ref} has no decision.json — an issue list patches an "
                f"adjudicated page and cannot make one. Saving here would write "
                f"the proposal's text for every line nobody listed, which reads "
                f"downstream as a human having accepted them. Adjudicate the page "
                f"first: `harness ocr review {ref}`.")
        prop = load_proposal(ref, root)
        lines = {str(i): {"text": _nfd(v["text"]),
                          **({"note": v["note"]} if v.get("note") else {})}
                 for i, v in saved.items()}
        for e in group:
            idx = int(e["index"])
            if idx not in saved:
                raise ValueError(
                    f"{ref}:{idx} is not in that page's decision — "
                    f"it holds {len(saved)} line(s)")
            have, prior = _nfd(saved[idx]["text"]), _nfd(e.get("prior", ""))
            if have != prior:
                raise ValueError(
                    f"{ref}:{idx} changed under this page since it was built. "
                    f"The store holds {have!r}; the form was filled against "
                    f"{prior!r}. Nothing was written — reload the issue list and "
                    f"redo this line, rather than overwriting a save you have "
                    f"not seen.")
            note = _nfd(e.get("note", "")).strip()
            if not note:
                raise ValueError(
                    f"{ref}:{idx} arrived with no note. A flagged line owes a "
                    f"ruling — including 'looked, it is fine', which is a finding "
                    f"and not a non-answer. Nothing was written.")
            # The adjudicator's note **replaces** rather than appends: this page
            # exists to answer a specific flag, and a note that accreted every
            # pass's remark would stop being the answer to the current one.
            lines[str(idx)] = {"text": _nfd(e.get("text", "")), "note": note}
        planned.append((ref, lines, prop))

    out = []
    for ref, lines, _prop in planned:
        out.append(save_decisions(ref, lines, root, stamp=stamp))
    return out
