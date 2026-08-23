"""The figure-caption reading pass: one flat proposal, one flat adjudication.

**Why this is not a second copy of `review.py`.** That module's records are keyed
on an integer line index into one page's ALTO, and its whole shape — a directory
per page, a queue, an agent per page — is sized to forty lines of dense phonetic
type. Captions are not that. Measured over the store:

    captions per page   1 on 151 pages, 2 on 68, 3 on 16, 4 on 15
    printed lines       1: 198   2: 122   3: 54   4+: 21  (one 27-line outlier)
    characters          p50 66, p90 156, max 1164
    any Tier-1 glyph    34 of 395

That is ~26 KB of mostly plain English, two lines at a time. So the unit of work
is the **contact sheet**, not the page, and the store is one pair of files keyed
`<ref>|<zone-suffix>` — the key the caption store files each block under, which is what
lets the two be joined block for block when the comparison runs.

**What is copied from `review.save_decisions`, deliberately and in full**, because
these four are why that function is trustworthy and none of them is about lines:

  * every key's **full text** is stored, not just the edited ones. `restore` builds
    the store from this file alone, so if an unedited caption carried only a flag,
    what reached `gt/fig/` would depend on the proposal still being byte-identical
    — and then correcting a reading would silently change what "unedited" resolved
    to, which is a way to alter ratified text without touching it.
  * `edited` is **computed here**, never trusted from the client. It is the pass's
    primary signal — the fraction of proposed captions a human let stand — and a
    number the thing being measured reports about itself is worthless.
  * **NFD on the way in.** Browsers submit whatever the keyboard produced; the
    corpus is NFD by policy (keying spec section 1).
  * an **empty payload is refused** unless `withdraw=True`, and the reason is
    sharper here than for a page: this is one file for the whole corpus, so an
    empty save is not one page cleared but 395 adjudications replaced with
    nothing.

Durability likewise: temp-then-rename, one `.prev`, and an append-only
`decision.jsonl` recording only what differed. Two saves destroy `.prev`; nothing
destroys the journal.

**The cross-page hazard is the normal case here, not an edge.** `review.py`'s issue
list had to grow an all-or-nothing guard and a prior-text check after a save wrote
a field belonging to a key the reviewer was not looking at. Every save in this
module is cross-page by construction, so `patch` below carries that check from the
first commit rather than after the first incident.
"""
from __future__ import annotations

import json
import time
import unicodedata
from collections.abc import Callable
from pathlib import Path

from .atomic import tmp_for
from .parallel import ptrack
from .paths import CAPTIONS, decisions_path, proposal_path
from .refs import norm_ref

#: Adjudication keywords that may open a caption's note. The first two are
#: terminal — the page was re-examined and the question is closed. The rest mark
#: work outstanding. Copied from `figures.NOTE_KEYWORDS` rather than imported:
#: that copy served the old markdown parser and died with it, and this one
#: is the vocabulary of the store that replaces it. Longest-first so a prefix
#: match cannot shadow a longer keyword.
NOTE_KEYWORDS = (
    "CONFLICT WITH THE LIST OF ILLUSTRATIONS",
    "KEYING REQUIRED",
    "ZONE TOO SMALL",
    "ZONE MISPLACED",
    "VERBATIM",
    "MISPRINT",
)
TERMINAL_KEYWORDS = ("VERBATIM", "MISPRINT")


def _nfd(s: str) -> str:
    """NFD, never NFKC — NFKC rewrites U+1D4B and U+02D9, both inventory glyphs."""
    return unicodedata.normalize("NFD", s)


def _fold(s: str) -> str:
    """NFD, and every printed line stripped of its own leading and trailing space.

    **Indentation is presentational, exactly as the line break beside it is.** A
    caption's printed lines are stored apart so a wrap-hyphen stays recoverable —
    31 of 196 multi-line captions turn on that — and *how far in* a continuation
    line sits carries nothing at all: `2-030`'s gloss list indents its runovers,
    and the indent is the compositor's, not the text's.

    Folded silently on write rather than reported, which is this project's rule
    for a difference a fold can recover: there is no ruling to make about a leading
    space. It is enforced here because here is where browser input becomes stored
    text — the adjudicator types a continuation line in a textarea and indents it
    to match the page, which is the natural thing to do and must not become a fact
    about the corpus.

    It also removes a false positive rather than accommodating one. §2.9's
    multi-space rule scans **raw source**, and `normalize.py` argues it cannot
    touch indentation because "an indented line's leading spaces are preceded by a
    newline, not a non-space character" — true of a file's *structural* indent and
    not of an indent *inside a string value*, where the preceding characters are
    the two-character `\\n` escape. So the store carried a §2.9 hit that
    `--convert` would have mangled rather than fixed.
    """
    return "\n".join(ln.strip() for ln in _nfd(s).split("\n"))


def load_proposal(root: Path = Path(".")) -> dict[str, dict]:
    """`review/captions/proposal.json` -> `{"<ref>|<suffix>": record}`.

    A reading, never truth, and **never seeded from the caption already in `gt/fig/`**. The whole
    purpose of this file is to be a second witness to captions that store already
    holds, and `docs/decisions.md` records what happens when two files that look
    independent turn out to share an ancestor: three invented commas sat in both,
    corroborating each other, and only a fresh raster read separated them.

    Absence raises rather than returning `{}`: unlike a page proposal, of which the
    corpus has hundreds and most legitimately absent, there is exactly one of these
    and its absence means the pass has not been run.
    """
    p = proposal_path(CAPTIONS, root)
    if not p.exists():
        raise ValueError(
            f"no caption proposal at {p}. It is a reading of the contact sheets "
            f"`harness fig sheets` writes, authored in one pass by the "
            f"read-captions skill — never seeded from the store it is compared against, which "
            f"is the witness it exists to be compared against.")
    doc = json.loads(p.read_text(encoding="utf-8"))
    return dict(doc.get("lines", {}))


def proposal_is_blind(root: Path = Path(".")) -> bool | None:
    """Whether the reading session declared it did not open the old store.

    `True`, `False`, or `None` for a file that says nothing — and the three are
    kept apart because they mean different things to `fig witness`. A skill has no
    `PreToolUse` hook behind it, so this is a **declaration and not an
    enforcement**; what it buys is that a comparison run against a contaminated
    read is visibly that, rather than a table that looks the same either way.
    """
    p = proposal_path(CAPTIONS, root)
    if not p.exists():
        return None
    doc = json.loads(p.read_text(encoding="utf-8"))
    v = doc.get("blind")
    return v if isinstance(v, bool) else None


def load_decisions(root: Path = Path(".")) -> dict[str, dict]:
    """Adjudicated captions saved so far. Empty if none — nobody has ruled yet."""
    p = decisions_path(CAPTIONS, root)
    if not p.exists():
        return {}
    doc = json.loads(p.read_text(encoding="utf-8"))
    return dict(doc.get("lines", {}))


def save_decisions(blocks: dict, root: Path = Path("."),
                   stamp: str | None = None, withdraw: bool = False) -> dict:
    """Write adjudicated captions, recording for each whether it differs.

    `blocks` maps `<ref>|<suffix>` to a string or to `{text, note, keyword}`. See
    the module docstring for why each of the four invariants below is here; they
    are `review.save_decisions`' and they are about adjudication, not about lines.
    """
    prop = load_proposal(root)
    before = load_decisions(root)
    if not blocks and before and not withdraw:
        raise ValueError(
            f"refusing to replace {len(before)} adjudicated caption(s) with "
            f"nothing. This is one file for the whole corpus, so an empty save is "
            f"not one page cleared — it is every ruling in the pass. A dropped key "
            f"or a careless probe looks exactly like this by the time it arrives "
            f"here. If it is really meant: `withdraw=True`.")

    stamp = stamp or time.strftime("%Y-%m-%dT%H:%M:%S%z")
    out: dict[str, dict] = {}
    for key, v in blocks.items():
        text = _fold(v if isinstance(v, str) else v.get("text", ""))
        proposed = _fold(prop[key]["text"]) if key in prop else None
        rec = {"text": text,
               "edited": proposed is not None and text != proposed}
        # Stored only when it says something, `review.save_decisions`' rule: an
        # empty note on all 395 would make "this caption was remarked on"
        # unfindable by the only means anyone has, the key existing. This is the
        # adjudicator's note and the home the old `@note` line
        # moves to — distinct from the proposal's note, which is the reader's.
        note = _nfd("" if isinstance(v, str) else (v.get("note") or "")).strip()
        if note:
            rec["note"] = note
        kw = "" if isinstance(v, str) else (v.get("keyword") or "")
        if kw:
            if kw not in NOTE_KEYWORDS:
                raise ValueError(
                    f"{key}: {kw!r} is not an adjudication keyword. The closed set "
                    f"is {', '.join(NOTE_KEYWORDS)} — a free-text ruling belongs in "
                    f"`note`, where nothing downstream will try to read it as a "
                    f"verdict.")
            rec["keyword"] = kw
        out[key] = rec

    changed = sorted(k for k, v in out.items()
                     if k in before and before[k]["text"] != v["text"])
    doc = {"proposal": proposal_path(CAPTIONS).as_posix(),
           "saved_at": stamp, "lines": out}

    p = decisions_path(CAPTIONS, root)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        p.with_suffix(".json.prev").write_bytes(p.read_bytes())
    tmp = tmp_for(p)
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)

    with p.with_suffix(".jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"saved_at": stamp, "changed": changed,
                             "edited": {k: v["text"] for k, v in out.items()
                                        if v["edited"]}},
                            ensure_ascii=False) + "\n")

    edited = sorted(k for k, v in out.items() if v["edited"])
    return {"path": str(p), "blocks": len(out),
            "edited": len(edited), "edited_blocks": edited,
            "changed": len(changed), "changed_blocks": changed}


def witness(root: Path = Path("."), source: dict | None = None) -> dict:
    """Compare the fresh reading against the caption in `gt/fig/`, block for block.

    **Measurement, never a gate.** Two ratified human readings disagreeing is a
    finding and not an error, and nothing here decides which is right — that is a
    human's act in `harness fig review`, against the scan. The store is not
    edited to match, because a store edited toward the thing being compared to it
    stops being a witness.

    Four classes, and the middle one exists because it is not a disagreement about
    the book:

      `agree`        NFD-identical, line breaks included.
      `lines_differ` same text, different printed-line division. The box's
                     height decides where a caption wraps, so this is a fact
                     about the segmentation rather than about the type.
      `differ`       a character differs. The class the exercise exists to find.
      `only_in_*`    a block one side keys and the other does not.

    **The header states whether the reading was blind, and that is the report's
    load-bearing field.** A comparison whose two inputs may be one input has to say
    so (CLAUDE.md); `docs/decisions.md` records the case where `gt/ocr/` and
    the caption text corroborated three invented commas because it
    descended from the same recognizer pass, and only a fresh raster read separated
    them. A run whose reader had the old file open produces a table that looks
    exactly like this one and means nothing, so `blind` travels with the numbers.

    `source` is a `figures.readings()` a caller already holds.
    """
    from .figures import readings

    # **Decisions overlay the reading; they do not replace it.** An adjudication
    # covers only the captions somebody has ruled on, so taking it whole where it
    # exists made the other 330 read as `only_in_readings_md` — the fresh reading
    # apparently losing 330 captions the moment the first ruling was saved. Same
    # precedence `review._text_now` keeps for a line: the ruling where there is
    # one, the reading otherwise.
    ratified = load_decisions(root)
    new = {**load_proposal(root), **ratified}
    old = readings(root) if source is None else source

    rows, counts = [], {"agree": 0, "lines_differ": 0, "differ": 0}
    for key in sorted(set(new) | set(old)):
        if key not in old:
            rows.append({"key": key, "verdict": "only_in_reading",
                         "old": "", "new": new[key]["text"]})
            continue
        if key not in new:
            rows.append({"key": key, "verdict": "only_in_readings_md",
                         "old": old[key]["text"], "new": ""})
            continue
        a, b = _nfd(new[key]["text"]), _nfd(old[key]["lines"] and
                                            "\n".join(old[key]["lines"]) or "")
        if a == b:
            verdict = "agree"
        elif a.replace("\n", " ").split() == b.replace("\n", " ").split():
            verdict = "lines_differ"
        else:
            verdict = "differ"
        counts[verdict] += 1
        if verdict != "agree":
            rows.append({"key": key, "verdict": verdict, "old": b, "new": a})

    return {
        # First, and not buried under the counts: a reader who takes the numbers
        # without this has taken a measurement of nothing.
        "blind": proposal_is_blind(root),
        "adjudicated": bool(ratified),
        "compared": counts["agree"] + counts["lines_differ"] + counts["differ"],
        **counts,
        "only_in_reading": sum(1 for r in rows
                               if r["verdict"] == "only_in_reading"),
        "only_in_readings_md": sum(1 for r in rows
                                   if r["verdict"] == "only_in_readings_md"),
        "rows": rows,
    }


def restore(root: Path = Path("."), refs: list[str] | None = None,
            force: bool = False, commit: bool = False,
            tick: Callable | None = None) -> dict:
    """Write the adjudicated captions into `gt/fig/`. **This is the migration.**

    The store is populated by restoring rulings, not by a script transcribing
    an earlier reading — which is the whole point of the exercise. What lands is
    what a human ratified against the scan, so the text in `gt/fig/` can carry
    `#gt`: machine-shaped output a human confirmed, transcluded from its store and
    re-derived on every run.

    **Four refusals, `review.restore`'s, and each is here for its own reason:**

      * a caption with **no decision and no reading** stops the page. A partial
        restore yields a store with invisible holes, which is worse than an empty
        one — `fig check` can see an absent block but not an absent caption that
        nobody expected.
      * a target that **already holds text**, without `force`. Once this has run,
        every FigDesc carries a caption, so overwriting one is a deliberate act
        and `force` is how a caller says they meant it.
      * an **unlicensed mark** on any adjudicated caption (`detectors.MARK_LICENSE`,
        keying spec §2.6). This catches what a human pass can miss rather than
        what it never saw, and a restore is the last point at which it is cheap.
      * **`commit` gates the write**, `normalize --convert`'s contract: the full
        report comes back either way, so a dry run answers "what would this
        change" without a hand-rolled diff.

    Precedence is the pass's throughout: the ruling where there is one, the
    reading otherwise — so a caption both witnesses already agreed on restores
    from the reading without anyone having had to re-type it.
    """
    
    from lxml import etree

    from .detectors import unlicensed_marks as _um
    from .figures import FIGDESC, alto_for, block_text, fig_refs, zone_suffix, zones
    from .figures import save_caption_text as _write

    text_for = {**load_proposal(root), **load_decisions(root)}
    by_ref: dict[str, dict[str, list[str]]] = {}
    for key, rec in text_for.items():
        ref, _, suffix = key.partition("|")
        by_ref.setdefault(ref, {})[suffix] = _fold(rec["text"]).split("\n")

    wanted = [norm_ref(r) for r in refs] if refs else fig_refs(root)
    rows, marks, holes, occupied = [], [], [], []
    for ref in ptrack(wanted, tick):
        blocks = [b for b in zones(ref, root) if b["label"] == FIGDESC]
        if not blocks:
            continue
        have = by_ref.get(ref, {})
        missing = [zone_suffix(b["id"]) for b in blocks
                   if zone_suffix(b["id"]) not in have]
        if missing:
            holes += [f"{ref}|{s}" for s in missing]
            continue
        tree = etree.parse(str(alto_for(ref, root)))
        held = any(block_text(b) for b in tree.iter("{*}TextBlock"))
        if held and not force:
            occupied.append(ref)
            continue
        for suffix, lines in have.items():
            for m in _um("\n".join(lines)):
                marks.append(f"{ref}|{suffix}: {m}")
        rows.append((ref, {s: have[s] for s in
                           (zone_suffix(b["id"]) for b in blocks)}))

    if holes:
        raise ValueError(
            f"{len(holes)} caption block(s) have neither a ruling nor a reading — "
            f"{', '.join(holes[:6])}{'…' if len(holes) > 6 else ''}. A partial "
            f"restore leaves the store with holes nothing can see; read them "
            f"first with the read-captions skill.")
    if marks:
        raise ValueError(
            f"unlicensed mark(s) on {len(marks)} caption(s): "
            f"{'; '.join(marks[:4])}. A mark on a base its licence does not cover "
            f"is a sequence the notation does not contain, so there is no ruling "
            f"to make — key it, then restore.")

    written = 0
    if commit:
        for ref, payload in rows:
            written += _write(ref, root, payload)["written"]
    return {"pages": len(rows), "captions": sum(len(p) for _, p in rows),
            "skipped_holding_text": len(occupied),
            "occupied": occupied[:8],
            "committed": commit, "written": written,
            "note": "" if commit else "preview only — pass --commit to write"}


def key_for(ref: str, index: int) -> str:
    """`("1-049", 6)` -> `"1-049|006"`.

    **The issue list's key space fits captions exactly, and that is not a
    coincidence to be relied on quietly.** A zone id's last field is three zero-
    padded digits, so a caption's key is a ref and an integer — the same pair
    `review.issues_context`, `review-issues.js` and `/issues/save` already carry
    for a line. That is why this pass needs no second template, no second
    keyboard, no second palette and no second save protocol: the document that
    reviews lines from many pages at once *is* the document that reviews captions
    from many pages at once, and only the block builder and the store differ.
    """
    return f"{norm_ref(ref)}|{int(index):03d}"


def _reader_note(rec: dict) -> str:
    """What the reader said about this caption, as one line.

    **`resolved` rides along with the note rather than sitting in its own row**,
    because on a Tier-1 caption it *is* the substance of the disagreement and not
    a footnote to it. On `1-049|006` the reader wrote "there may be a dot below
    the g; at sheet scale I could not resolve it either way" and resolved it as a
    bare g — which is precisely why the store's dotted `g̣` is the competing
    reading. An adjudicator shown only the two strings would have to rediscover
    that from the raster.

    The `class` does *not* come through here: it is a closed vocabulary and gets a
    coloured badge of its own, the same one the line pass has used since notes had
    classes at all. Folding it into prose would spend a word on what a colour says
    at a glance.
    """
    bits = []
    if rec.get("note"):
        bits.append(rec["note"])
    if rec.get("resolved"):
        bits.append(f"· resolved: {rec['resolved']}")
    return " ".join(bits)


def review_context(root: Path = Path("."), verdict: str = "differ",
                   crop_base: str = "", zoom: int = 2,
                   font: str | None = None, font_size: int | None = None,
                   box_lines: int | None = None) -> dict:
    """The disagreements, in `review.issues_context`'s block shape.

    Same keys, so `review/issues.html` and `review-issues.js` render this
    untouched — including the prior-text guard, which this pass needs from its
    first save rather than after its first incident, every document here being
    cross-page by construction.

    Two fields carry the caption pass's own meaning:

      `issue`   what `data/readings.md` reads. The reviewer is not being asked
                "is this right" in the abstract but "which of these two is the
                page", so the other witness *is* the issue.
      `before`  the same text again, as read-only context beside the box, where
                the line pass puts the previous line. A caption has no previous
                line; it has a second reading.

    Nothing here decides anything, and `text` is the fresh reading rather than the
    old one on purpose: the box opens on the witness that has *not* been ratified,
    so letting it stand is an act and not an omission.
    """
    from .figures import caption_strips
    from .review import (
        DEFAULT_BOX_LINES,
        DEFAULT_FONT,
        DEFAULT_FONT_SIZE,
        KBD_GLYPHS,
        KBD_MARKS,
        _palette,
        codepoints,
    )

    rows = [r for r in witness(root)["rows"]
            if verdict == "all" or r["verdict"] == verdict]
    saved = load_decisions(root)
    # The reading itself, for its notes: `witness` carries only the two strings,
    # and what the reader *said about* a caption is most of what settles it.
    prop = load_proposal(root)

    by_ref: dict[str, list[str]] = {}
    for r in rows:
        by_ref.setdefault(r["key"].partition("|")[0], []).append(r["key"])

    sizes: dict[str, tuple[int, int]] = {}
    for ref, keys in by_ref.items():
        for key, strip, _ in caption_strips(ref, root, pad=0.15):
            if key in keys:
                sizes[key] = (strip.width * zoom, strip.height * zoom)

    blocks = []
    for r in rows:
        ref, _, suffix = r["key"].partition("|")
        text = _nfd((saved.get(r["key"]) or {}).get("text") or r["new"])
        w, h = sizes.get(r["key"], (900, 90))
        scale = min(1.0, 1040 / w)
        blocks.append({
            "ref": ref, "idx": int(suffix), "issue": r["old"],
            "field": f"{ref}:{int(suffix)}",
            "before": {"idx": "gt/fig", "text": r["old"]},
            "after": None,
            "text": text, "prior": text,
            "crop": f"{crop_base}/{r['key']}.png",
            "w": round(w * scale), "h": round(h * scale),
            "note": _reader_note(prop.get(r["key"]) or {}),
            # The closed set `proposal_check.NOTE_CLASSES` holds, rendered as the
            # badge `review.css` already colours for the line pass.
            "nclass": (prop.get(r["key"]) or {}).get("class", ""),
            "hnote": (saved.get(r["key"]) or {}).get("note", ""),
            "marks": codepoints("".join(
                dict.fromkeys(c for c in text if ord(c) > 127))),
        })
    return {"blocks": blocks, "missing": [], "palette": _palette(),
            "kbd_glyphs": KBD_GLYPHS, "kbd_marks": KBD_MARKS,
            "refs": list(dict.fromkeys(b["ref"] for b in blocks)),
            "count": len(blocks),
            "font": font or DEFAULT_FONT,
            "font_size": font_size or DEFAULT_FONT_SIZE,
            "box_lines": box_lines or DEFAULT_BOX_LINES}


def patch(edits: list[dict], root: Path = Path("."),
          stamp: str | None = None) -> dict:
    """Apply a form's worth of edits onto the saved adjudication, or none of them.

    **Two guards, both `review.patch_decisions`', and both load-bearing here for a
    reason that module had to learn.** Every document this pass renders is
    cross-page — one list of captions drawn from all over the book — which is
    exactly the shape that once wrote a field belonging to a key the reviewer was
    not looking at.

      * **All or nothing.** A partial apply leaves the reviewer with no way to know
        which half landed, and the form they are looking at describes a state that
        no longer exists on either side.
      * **Prior text.** Each edit carries the text it was filled against. If the
        store has moved since, nothing is written — because the alternative is
        overwriting a save nobody has seen.
    """
    saved = load_decisions(root)
    for e in edits:
        key = e["key"]
        if key not in saved:
            raise ValueError(
                f"{key} has no saved decision to patch. Adjudicate it in "
                f"`harness fig review` first; a patch edits a ruling and does not "
                f"make one.")
        have, prior = _nfd(saved[key]["text"]), _nfd(e.get("prior", ""))
        if have != prior:
            raise ValueError(
                f"{key} changed under this document since it was built. The store "
                f"holds {have!r}; the form was filled against {prior!r}. Nothing "
                f"was written — reload and redo this caption, rather than "
                f"overwriting a save you have not seen.")
    merged = {k: dict(v) for k, v in saved.items()}
    for e in edits:
        rec = merged[e["key"]]
        rec["text"] = e["text"]
        if "note" in e:
            rec["note"] = e["note"]
        if "keyword" in e:
            rec["keyword"] = e["keyword"]
    return save_decisions(merged, root, stamp)
