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
import unicodedata
from pathlib import Path

from lxml import etree

# Aliased: this module already exposes a `corrections` verb (proposal->decision
# character diffs), which is a different subject entirely.
from . import corrections as _corr
from .context import norm_ref
from .detectors import DOT_ABOVE_G, INVENTORY_CHARS, LOOKALIKES, unlicensed_marks
from .lines import DEFAULT_ALTO_DIR, alto_for_lines, page_lines, raster_path
from .paths import crops_dir, decisions_path, html_path, page_dirs, proposal_path
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
    against neither (`keying_spec.md` section 1, and the collation skill's CATMuS notes).

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
    for rec in page_lines(alto_for_lines(ref, alto_dir, root), root, ref=ref):
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
                since: str | None = None) -> dict:
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
    for d in page_dirs(root):
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
    target = root / "gt" / "ocr" / f"chukchi-{norm_ref(ref)}.xml"
    if target.exists() and target.stat().st_mtime >= dec.stat().st_mtime:
        return "ground truth is already newer than the decision"
    return ""


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
    tmp = target.with_suffix(".xml.tmp")
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
    edits = [{"line": i, "proposal": prop[i]["text"] if i in prop else "(gone from proposal)",
             "decision": v["text"]}
            for i, v in sorted(dec.items()) if v.get("edited")]
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
                # `view` is "" here, not absent: one fixed key set across both
                # branches, since a caller reading the report should not have to
                # know which one produced it to know which keys exist.
                "edited_by_human": len(edits), "edits": edits,
                "noted": len(notes), "notes": notes, "commit": False,
                "view": ""}
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
    # **The promotion is the write plus the relink, and it was only ever half
    # wired.** `recognize.link_one`'s own docstring says so — "promoting a page is a
    # matter of `restore` writing `gt/ocr/` and this relinking, never of moving
    # anything" — and `ocr predict` has always paired the two, relinking each page it
    # writes into `mz/ocr/`. `restore` did not, so a page that had no ground truth
    # came back from a restoration with `gt/ocr/` written and `ocr/` still pointing
    # at the prediction: the view silently one save out of date, and `ocr pages
    # --show-store` reporting a `gt,mz` row that still reads `view: mz`.
    #
    # Relinking here is not a write *through* the view — the rule the store layout
    # exists for — it is a rebuild *of* the view, from the same registry `views
    # build` uses, after the authored write has already landed. It is gated on
    # `commit` because a preview must leave the disk alone, and it is a per-page
    # relink rather than a farm sweep because the page is what changed.
    #
    # Imported here rather than at module scope: there is no cycle (`recognize` does
    # not import this module), but it pulls `zones`, and `restore` should not cost a
    # segmenter import to write a line of text.
    from .recognize import link_one
    view = link_one(ref, root)
    return {"path": str(target), "source": str(src), "mode": mode,
            "lines": len(recs), "corrections": len(boxes),
            "chars": sum(len(_nfd(v["text"])) for v in dec.values()),
            "geometry_drift": drift, "text_mismatch": wrong,
            "edited_by_human": len(edits), "edits": edits,
            "noted": len(notes), "notes": notes, "commit": True,
            "view": view}


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
    if not name:
        return _FALLBACK
    quoted = name if name.startswith(("'", '"')) else f"'{name}'"
    # A face already in the fallbacks is promoted, not repeated: CSS ignores the
    # duplicate, but a stack naming one family twice reads as a bug to whoever
    # next opens the page source.
    rest = [f for f in _FALLBACK.split(", ") if f.strip("'\"") != quoted.strip("'\"")]
    return ", ".join([quoted, *rest])


def render_queue_html(ref: str, alto_dir: str = DEFAULT_ALTO_DIR,
                      root: Path = Path("."), crops: Path | None = None,
                      queue: list[dict] | None = None,
                      scan_href: str | None = None,
                      font: str | None = None, font_size: int | None = None,
                      box_lines: int | None = None) -> str:
    """Self-contained review page for one ref: one entry per line, reading order.

    `queue` is the session's other pages — `[{"ref", "done"}, …]` in the order the
    reviewer asked for them — and it only ever adds a nav strip and changes what
    the Done button says. **A one-page session passes `None` and renders byte-for-
    byte what it always did**, which is the property that keeps the multi-page work
    from being a rewrite of the single-page page: the queue is a frame around this
    function, never a mode inside it.

    The strip is the only thing that knows a session spans pages. Everything below
    it — the line list, the crops, the keyboard, the save payload — is still about
    one ref, because a review *is* one page at a time and pretending otherwise is
    how a reviewer keys 1-073's text into 1-151's fields (see the session-restore
    guard). Pages are reached by navigation, never merged into one document.

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
         # Three knobs, as CSS variables so the in-page steppers can move them
         # without a reload and the server flags only decide where they start.
         # `--fs` is the entry text; `--bl` is how many lines the box holds before
         # it grows, which is a separate want from size — Brill's small eye means
         # a comfortable reading size still leaves a one-line box looking cramped.
         f":root{{--f:{font_stack(font)};"
         f"--fs:{int(font_size or DEFAULT_FONT_SIZE)}px;"
         f"--bl:{max(1, int(box_lines or DEFAULT_BOX_LINES))}}}",
         "body{font:15px var(--f);margin:0;padding:1.5rem;max-width:1100px}",
         "h1{font-size:1.1rem;margin:0 0 .3rem}",
         # The session strip. Deliberately plain and above everything: it is the
         # only thing on the page that is not about the page, and a reviewer who
         # loses track of which ref they are keying is the failure it prevents.
         ".q{margin:0 0 1rem;font:12px ui-monospace,monospace}",
         ".q a,.q span.cur{display:inline-block;padding:.15rem .5rem;margin-right:.3rem;"
         "border:1px solid #ccc;border-radius:3px;text-decoration:none;color:#333}",
         ".q span.cur{background:#333;color:#fff;border-color:#333}",
         # Done is a fact about the file on disk, not about this tab's history —
         # it is recomputed server-side per request, so a reload after a save
         # shows what was actually written rather than what the page remembers.
         ".q a.done{color:#137333;border-color:#b7dfc0;background:#f2fbf5}",
         ".q .qlab{color:#777;margin-right:.5rem}",
         # Sits in the h1 but must not read as part of the count — normal weight,
         # normal size, so the heading still scans as one sentence about the page.
         "a.scan{font-size:.85rem;font-weight:400;margin-left:.6rem;"
         "color:#1a56b8;text-decoration:none;white-space:nowrap}",
         "a.scan:hover{text-decoration:underline}",
         # Machine's account left, human's right. `min-width:0` on the left column
         # is what stops a long catmus line from pushing the note column off the
         # row: a flex item's default `min-width:auto` refuses to shrink below its
         # content, and an overflowing `<div class=ref>` is exactly that case.
         ".meta{display:flex;gap:.75rem;align-items:flex-start;margin-top:.25rem}",
         ".metaL{flex:1 1 auto;min-width:0}",
         # Fixed at ~15 characters of its own 12px type, and it neither grows into
         # the left column nor shrinks under it — a note field that resized with
         # its content would move every line below it as the reviewer typed.
         ".hn{flex:0 0 15ch;font-size:12px}",
         # Quiet until used. A dashed outline reads as "nothing here yet" where a
         # solid button would read as an action the line is waiting on.
         "button.hnb{font:12px var(--f);color:#888;background:none;width:100%;"
         "border:1px dashed #c4c4c4;border-radius:3px;padding:.15rem .3rem;"
         "cursor:pointer}",
         "button.hnb:hover{color:#333;border-color:#888}",
         # Tinted, so an open note is never mistaken for the reading field beside
         # it at a glance down the page.
         "textarea.hnt{font:12px/1.4 var(--f);background:#fffdf0;"
         "border-color:#ded4a4;padding:.15rem .3rem}",
         "textarea.hnt:focus{outline-color:#b59b2e;border-color:#b59b2e}",
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
         ".type{font:12px ui-monospace,monospace;margin:.5rem 0 0;color:#666}",
         "button.tb{font:11px ui-monospace,monospace;border:1px solid #bbb;"
         "background:#fff;border-radius:4px;padding:.1rem .35rem;margin-left:.3rem;"
         "cursor:pointer}",
         ".tv{margin-left:.35rem;color:#888}",
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
         # `min-height` rather than `rows`: the box autogrows past it, so this is a
         # floor and not a size, and a reviewer who wants room to see a wrapped
         # line gets it without the box shrinking back on every keystroke.
         "textarea{font:var(--fs)/1.45 var(--f);width:100%;border:1px solid #bbb;"
         "border-radius:4px;padding:.35rem .5rem;resize:vertical;overflow:hidden;"
         "min-height:calc(var(--bl) * 1.45em + .8rem)}",
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
         "button.tb{background:#1e1e1e;color:#ccc;border-color:#444}"
         ".t1{border-color:#d1a02a;background:linear-gradient(90deg,#2a2211,"
         "transparent 45%)}"
         ".badge{background:#d1a02a;color:#161616}"
         ".t1glyphs{color:#e8c874}"
         ".jump a{color:#e0b552;border-color:#8a6a1e}"
         ".jump.edit a{color:#4fd47a;border-color:#1a7f37}"
         ".editflag{color:#4fd47a}"
         "textarea.justsaved{outline-color:#4fd47a}"
         "button.hnb{color:#8a8a8a;border-color:#3d3d3d}"
         "button.hnb:hover{color:#e6e6e6;border-color:#7a7a7a}"
         "textarea.hnt{background:#221e12;border-color:#5c4f22;color:#f0e6c8}"
         "textarea.hnt:focus{outline-color:#d1a02a;border-color:#d1a02a}"
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

    # The strip, only when there is a session to describe. One page passes `None`
    # and gets nothing — a nav bar over a queue of one is furniture that says
    # "there is somewhere else to be" when there is not.
    if queue and len(queue) > 1:
        cells = ["<span class=qlab>this session:</span>"]
        for q in queue:
            cls = "done" if q["done"] else ""
            if q["ref"] == ref:
                cells.append(f"<span class=cur>{q['ref']}</span>")
            else:
                cells.append(f"<a class='{cls}' href='/p/{q['ref']}'>{q['ref']}</a>")
        done_n = sum(1 for q in queue if q["done"])
        cells.append(f"<span class=qlab>&nbsp;{done_n}/{len(queue)} adjudicated</span>")
        h.append("<div class=q>" + "".join(cells) + "</div>")
    # The whole page, one click away. The crops answer "what does this line set";
    # they cannot answer "what is around it", and a reviewer settling a speck, a
    # dropped line or a heading has to see the sheet. Groping for the file by hand
    # was the alternative, and `scans/` is gitignored and not where the review is.
    #
    # Default is the on-disk relative path, computed rather than spelled, so the
    # `--html` file works opened straight off the filesystem; `serve` overrides it
    # with a route, since a browser will not follow file:// from an http origin.
    if scan_href is None:
        scan_href = os.path.relpath(raster_path(ref, root), html_path(ref, root).parent)
    h += [
         f"<h1>{ref} — {summ['lines']} lines, "
         f"{summ['lines'] - summ['lines_identical']} differing from catmus, "
         f"{len(t1)} carrying notation "
         f"<a class=scan href='{scan_href}' target=_blank rel=noopener>full scan ↗</a>"
         "</h1>",
         "<div class=sum>"
         f"{summ['spans']} differing spans in {summ['classes']} substitution "
         f"classes · {summ['inventory_spans']} touch inventory glyphs · "
         f"{summ['lookalikes_in_proposal']} lookalike traps in the proposal<br>"
         "Every line is listed, in reading order. CATMuS is shown for reference "
         "only: it is a witness to geometry and English, and produced no inventory "
         "glyph anywhere in this book, so on a glyph the image is the sole witness "
         "— and a line the two agree on can still have both of them wrong.</div>"]
    # **Type controls, live.** The flags decide where the page starts; these decide
    # where it ends up, because the right size for a face is a thing you find by
    # looking at it against a crop rather than by predicting it at a command line.
    # Persisted per browser, so the next page and the next session open where this
    # one was left — a setting that has to be re-found every page is not a setting.
    h.append(
        "<div class=type><b>Type:</b> "
        "<button class=tb data-var=fs data-by='-1'>A−</button>"
        "<button class=tb data-var=fs data-by='1'>A+</button>"
        "<span class=tv id=tvfs></span>"
        "<button class=tb data-var=bl data-by='-1'>box −</button>"
        "<button class=tb data-var=bl data-by='1'>box +</button>"
        "<span class=tv id=tvbl></span>"
        "<button class=tb id=treset>reset</button></div>")
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
        # happens for real — a line recovered in `ocr edit` has geometry before it
        # has any reading, which is the whole shape of that pass. Render it empty
        # and say so.
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
                 # Off `src` rather than off the id's spelling: a recovered line
                 # is one the merge added from `gt/lines/`, which is a fact the
                 # record already carries.
                 + (" · recovered line (segmenter missed it)"
                    if rec.get("src") == "corr" else "")
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
        # Everything under the reading is one row: the machine's account of the
        # line on the left, the human's on the right. They are read at different
        # moments — the left while keying, the right when ruling — so stacking
        # them put the one thing the reviewer authors at the bottom of a pile of
        # things they only consult.
        h.append("<div class=meta><div class=metaL>")
        if marks:
            h.append(f"<div class=cp>{_esc(marks)}</div>")
        h.append(f"<div class=ref>catmus: {_esc(rec['text']) or '(empty)'}</div>")
        for key in ("note", "resolved", "corrected"):
            if mine.get(key):
                h.append(f"<div class=note>{key}: {_esc(mine[key])}</div>")
        h.append("</div>")
        # The adjudicator's note, opt-in per line. A textarea on all 45 lines would
        # be 45 empty boxes competing with the 45 that matter, so it starts as a
        # button and becomes a field only when asked for — and a line that already
        # carries one renders open, since a note nobody can see is not a record.
        hnote = (saved.get(idx) or {}).get("note", "")
        h.append("<div class=hn>"
                 f"<button type=button class=hnb data-line='{idx}'"
                 + (" hidden" if hnote else "") + ">+ note</button>"
                 f"<textarea class=hnt data-note='{idx}' rows=1 spellcheck=false "
                 f"autocomplete=off data-text=\"{_esc(hnote)}\""
                 + ("" if hnote else " hidden") + "></textarea></div>")
        h.append("</div>")
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
    # Is there another page waiting after this one? Only pages *other* than this
    # one count: re-opening a page already marked done and pressing Done again
    # must not claim there is somewhere to go when this was the last of them.
    pending = [q["ref"] for q in (queue or [])
               if q["ref"] != ref and not q["done"]]
    dn_label = f"Done → next ({len(pending)} left)" if pending else "Done"
    dn_title = ("save, mark this page adjudicated, and open the next one"
                if pending else "save if needed, then stop the server")
    pal.append("<div id=pctl><div class=pctlrow>"
               "<span><span id=kb>kbd off</span><span id=st>no changes</span></span>"
               # Notation lines are the ones worth walking deliberately, so they get
               # their own traversal rather than only a colour to spot while scrolling.
               f"<span><button id=t1p>&uarr;</button>"
               f"<button id=t1n>&darr; tier-1 ({len(t1)})</button>"
               "<button id=sv>Save</button>"
               # Stops the server from the page, so finishing a review does not
               # leave a process bound to a page that is about to be restored.
               #
               # With a queue, "finish this page" and "finish the session" stop
               # being the same act, and the button says which one it is about to
               # do rather than leaving the reviewer to infer it from how many
               # pages they remember keying. The server still decides — this label
               # is rendered from the same `done` state the strip is, and the POST
               # response is what actually navigates.
               f"<button id=dn title='{_esc(dn_title)}'>{_esc(dn_label)}</button>"
               "</span></div>"
               "<div class=tags>alt-p shows/hides the keyboard panel (overrides "
               "kbd on/off) · ctrl-space toggles kbd · off = plain typing · "
               "alt-j / alt-k walk tier-1 lines</div></div>")
    pal.append("</div>")
    h += pal
    # Autosave on a debounce *and* an explicit button, plus a beforeunload guard.
    # Belt and braces on purpose: the alternative to a save that fires by itself is
    # a reviewer who closes the tab on forty adjudicated lines.
    # `REF` travels in every save and every done. The server could track a "current
    # page" instead, but that is state the browser can contradict — a second tab,
    # a back button, a reload after navigating — and the failure it would produce
    # is one page's adjudicated text written into another page's decision.json.
    # That is the session-restore incident again, so the payload says which page
    # it is about and the server writes where it is told.
    h.append("<script>const GL=" + json.dumps(KBD_GLYPHS, ensure_ascii=False)
             + ",MK=" + json.dumps(KBD_MARKS, ensure_ascii=False)
             + ",REF=" + json.dumps(ref) + ";</script>")
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

// TYPE CONTROLS. The two CSS variables the entry boxes are sized from, moved
// live and remembered per browser. The server flags set the starting values and
// stay the reset target, so `reset` means "back to what this server was started
// with" rather than to a constant compiled in here — otherwise a coordinator who
// passed --font-size would find the button undoing their flag.
const TYPE={fs:{min:11,max:34,unit:'px'},bl:{min:1,max:8,unit:''}};
const typeStart={};
for(const k in TYPE) typeStart[k]=parseFloat(
  getComputedStyle(document.documentElement).getPropertyValue('--'+k));
function typeSet(k,v){
  v=Math.min(TYPE[k].max,Math.max(TYPE[k].min,v));
  document.documentElement.style.setProperty('--'+k,v+TYPE[k].unit);
  const lab=document.getElementById('tv'+k);
  if(lab) lab.textContent=(k==='fs'?v+'px':v+(v===1?' line':' lines'));
  try{localStorage.setItem('review.'+k,v)}catch(e){}
  // Every box was sized against the old metrics, so re-grow them all: a box left
  // at its previous pixel height after a size change is the one thing that would
  // make this look broken.
  for(const t of document.querySelectorAll('textarea')) grow(t);
}
for(const k in TYPE){
  let v=typeStart[k];
  try{const s=localStorage.getItem('review.'+k); if(s!==null) v=parseFloat(s)}catch(e){}
  typeSet(k,v);
}
for(const b of document.querySelectorAll('button.tb[data-var]')){
  b.addEventListener('click',()=>{
    const k=b.dataset.var;
    typeSet(k,parseFloat(getComputedStyle(document.documentElement)
      .getPropertyValue('--'+k))+parseFloat(b.dataset.by));
  });
}
{const r=document.getElementById('treset');
 if(r) r.addEventListener('click',()=>{for(const k in TYPE) typeSet(k,typeStart[k])});}
// `[data-line]` throughout, never a bare `textarea`: the note boxes are textareas
// too, and an unscoped selector would post them as if they were line readings.
function collect(){const o={};
  for(const t of document.querySelectorAll('textarea[data-line]')){
    const n=document.querySelector(`textarea[data-note='${t.dataset.line}']`);
    o[t.dataset.line]={text:t.value,note:n?n.value:''};}
  return o}
// Live edited-flag, kept in sync with typing rather than only with the last save,
// so a line that was reverted back to its proposed text stops claiming "edited"
// before the next save round-trips. `ef{idx}` is the same span the server rendered.
function refreshEditFlag(t){
  const ef=document.getElementById('ef'+t.dataset.line);
  if(ef) ef.style.display=(t.value!==t.dataset.proposed)?'inline':'none';
}
function rebuildEditJump(){
  const idxs=[...document.querySelectorAll('textarea[data-line]')]
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
      body:JSON.stringify({ref:REF,lines:collect()})});
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
  // The server decides what happens next, not the page. It knows which refs are
  // still unadjudicated *on disk*, which is the only account of that fact that
  // survives a reload, a second tab, or a page opened out of order.
  let next=null;
  try{
    const r=await fetch('/done',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({ref:REF})});
    if(r.ok) next=(await r.json()).next;
  }catch(e){}
  dirty=false;
  if(next){ location.href='/p/'+next; return; }
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
// Deliberately unscoped: the note boxes are restored by position too, and a note
// that silently belonged to another page would be worse than a misplaced reading,
// since a note is read as a human's ruling and nothing checks it against the scan.
for(const t of document.querySelectorAll('textarea')){
  const want=t.dataset.text;
  if(t.value!==want) t.value=want;
  grow(t);
  t.addEventListener('focus',()=>{last=t});
  // An empty note is stored as nothing, so an empty *field* is a control asserting
  // a state the file does not have. Emptied and left, it folds back to the button
  // and the line reads exactly as it would after a reload.
  if(t.dataset.note!==undefined) t.addEventListener('blur',()=>{
    if(t.value.trim()) return;
    t.hidden=true;
    const b=document.querySelector(`button.hnb[data-line='${t.dataset.note}']`);
    if(b) b.hidden=false;});
  t.addEventListener('input',()=>{grow(t);dirty=true;st.className='';
    st.textContent='unsaved…';
    // Only a reading has an edited-flag; a note is never "edited from proposed",
    // there being nothing proposed to differ from.
    if(t.dataset.line){refreshEditFlag(t);rebuildEditJump();}
    clearTimeout(timer);timer=setTimeout(save,1200)});
}
// Opt-in notes: the button hands over to the field, and the blur handler above
// hands back whenever the field is left empty, so the two are one control with
// two faces rather than a door that only opens.
for(const b of document.querySelectorAll('button.hnb')){
  b.addEventListener('click',()=>{
    const t=document.querySelector(`textarea[data-note='${b.dataset.line}']`);
    if(!t) return;
    t.hidden=false; b.hidden=true; grow(t); t.focus(); last=t;});
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
  const t=el.querySelector('textarea[data-line]'); if(t){t.focus();last=t}
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


def serve(refs: str | list[str], alto_dir: str = DEFAULT_ALTO_DIR,
          root: Path = Path("."), port: int = 8731, font: str | None = None,
          font_size: int | None = None, box_lines: int | None = None) -> None:
    """Serve a session's reviews at 127.0.0.1 and accept saves.

    Loopback only, and no path routing beyond the endpoints it needs: this holds
    unpublished editorial work and has no business being reachable.

    **One server, several pages, one page at a time.** A batch is normal now that
    the reading half of the pass fans out to one agent per page, and standing a
    server up and tearing it down per page made the human's half the part that
    waited on the machine's. What it is deliberately *not* is one document holding
    several pages: the reviewer sees exactly one ref's lines, reached by
    navigation, because a field belonging to a different page than the one you
    think you are keying is this file's oldest and worst failure.

    **Adjudicated-ness is read off the disk, never held in memory.** A page is done
    when its `decision.json` exists, which is a fact `save_decisions` establishes
    and a reload, a second tab, a back button or a restart cannot contradict. The
    alternative — a set of finished refs in this process — is state the browser can
    disagree with, and the disagreement would express itself as the server writing
    one page's adjudicated text into another page's file.

    Two consequences, both wanted. A session re-run after finishing two of three
    pages opens the third, so the batch resumes rather than restarting. And a page
    that already carried decisions before the session is shown done and is still
    reachable from the strip — visible, not hidden, since "already adjudicated" is
    an answer and silently re-queuing it would discard the earlier one.
    """
    import time

    from . import webui

    queue = [norm_ref(r) for r in ([refs] if isinstance(refs, str) else refs)]
    # Order is the caller's, duplicates dropped: `review 2-045 2-045` is a typo,
    # and a queue that showed the page twice would make "2/3 adjudicated" a lie.
    queue = list(dict.fromkeys(queue))

    def _done(r: str) -> bool:
        return decisions_path(r, root).exists()

    def _state() -> list[dict]:
        return [{"ref": r, "done": _done(r)} for r in queue]

    # Every ref's geometry is resolved before the socket is bound, for the reason
    # `page_refs` parses every ref before any work is done: a store that cannot
    # answer for a page is a fact about the invocation, and the invocation is
    # where it should be reported. It used to surface as a 500 on navigation —
    # the CLI printed the URL and three reassuring `decisions -> …` lines, then
    # the browser got a traceback that only existed on the server's stderr, which
    # in the ordinary backgrounded case is a log nobody is reading. `--store`
    # defaults to `mz` here, so the ordinary way to meet this is a page restored
    # before `ocr predict` existed: name the store that does hold it.
    missing = [(r, alto_for_lines(r, alto_dir, root)) for r in queue]
    missing = [(r, p) for r, p in missing if not p.exists()]
    if missing:
        other = "gt" if "mz" in alto_dir else "mz"
        raise FileNotFoundError(
            "no ALTO in this store for "
            + ", ".join(f"{r} ({p})" for r, p in missing)
            + f" — review reads --store mz by default; try --store {other}, or "
              "`harness ocr predict` to write the prediction.")

    def _next_after(cur: str) -> str | None:
        """The next page still wanting a decision — never `cur` itself.

        Walks the caller's order rather than resuming after `cur`'s position, so a
        page reached out of order from the strip still hands back to the front of
        what is left instead of skipping everything before it.
        """
        return next((r for r in queue if r != cur and not _done(r)), None)

    class Handler(webui.EditorHandler):
        editor = "review"

        def get(self):
            if self.path in ("/", "/index.html"):
                # Bare `/` is "wherever this session is up to": the first page
                # still wanting a decision, falling back to the first page when
                # every one of them already has decisions — a session opened over
                # finished work must still show something rather than 404.
                cur = next((r for r in queue if not _done(r)), queue[0])
            elif self.path.startswith("/scan/"):
                r = self.path[6:]
                if r not in queue:
                    self.send_error(404)
                    return
                self.send_png(raster_path(r, root),
                              f"no raster for {r} — scans/ is derived; "
                              "render it with pdftoppm over pdfs/")
                return
            elif self.path.startswith("/p/"):
                cur = self.path[3:]
                # Only refs this session was asked for. Not a security boundary —
                # it is loopback — but a URL naming a page nobody queued would
                # render a review whose Done button belongs to another session.
                if cur not in queue:
                    self.send_error(404)
                    return
            else:
                self.send_error(404)
                return
            self.send_html(render_queue_html(cur, alto_dir, root, queue=_state(),
                                             scan_href=f"/scan/{cur}", font=font,
                                             font_size=font_size,
                                             box_lines=box_lines))

        def post(self):
            payload = self.body_json()
            if self.path == "/done":
                # The page has finished with *one* ref. Whether that ends the
                # session depends on what is left, and the answer comes from the
                # disk rather than from the page — `save` has already written this
                # page's decisions, so it is done by definition of the file.
                try:
                    cur = norm_ref(payload.get("ref") or queue[0])
                except Exception:
                    cur = queue[0]
                nxt = _next_after(cur) if cur in queue else None
                self.send_json({"next": nxt})
                if nxt:
                    print(f"{cur} adjudicated -> next {nxt}")
                    return
                # Last one. Stop, so nobody has to hunt the process afterwards: a
                # server left bound to a page that has since been restored is how a
                # later save lands on stale text — the rebuild skill warns about
                # exactly that, and telling a human to remember it is a worse fix
                # than a button.
                self.stop_from_page()
                return
            if self.path != "/save":
                self.send_error(404)
                return
            # The page says which ref it is; refuse anything else rather than fall
            # back to a "current page", which is the assumption that would write
            # one page's text into another's file. A raise here is reported to the
            # page as JSON by the shell — never a blank failure.
            cur = norm_ref(payload.get("ref") or "")
            if cur not in queue:
                raise ValueError(
                    f"save names {cur or '(no ref)'}, which is not in this "
                    f"review session ({', '.join(queue)})")
            res = save_decisions(cur, payload.get("lines") or {}, root,
                                 stamp=time.strftime("%Y-%m-%dT%H:%M:%S%z"))
            edited_str = ",".join(map(str, res["edited_lines"])) or "none"
            changed_str = f" · changed this save: {','.join(map(str, res['changed_lines']))}" \
                if res["changed_lines"] else ""
            print(f"saved {res['path']}: {res['edited']}/{res['lines']} edited "
                  f"(lines {edited_str}){changed_str}")
            self.send_json(res)

    url = f"http://127.0.0.1:{port}/"
    banner = [f"review {' '.join(queue)} -> {url}   "
              "(Done button on the page, or ctrl-c)"]
    # Say which pages arrive already adjudicated *before* the reviewer meets a
    # strip full of green. A resumed session is the ordinary case; a page
    # unexpectedly carrying decisions is a question, and it should be asked here
    # rather than discovered by the reviewer wondering what they missed.
    banner += [f"decisions -> {decisions_path(r, root)}"
               f"{'   (already present)' if _done(r) else ''}" for r in queue]
    # The shell's closing line — "done — server stopped from the page" — matters
    # here: the process exiting is the signal that the review is finished and the
    # page is ready to `restore`, so whoever is driving does not have to ask.
    webui.run(Handler, port, url, banner)


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
