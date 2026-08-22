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
`<ref>|<zone-suffix>` — the key `data/readings.md` already uses, which is what
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
from pathlib import Path

from .atomic import tmp_for
from .paths import CAPTIONS, decisions_path, proposal_path

#: Adjudication keywords that may open a caption's note. The first two are
#: terminal — the page was re-examined and the question is closed. The rest mark
#: work outstanding. Copied from `figures.NOTE_KEYWORDS` rather than imported:
#: that copy serves the `data/readings.md` parser and dies with it, and this one
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


def load_proposal(root: Path = Path(".")) -> dict[str, dict]:
    """`review/captions/proposal.json` -> `{"<ref>|<suffix>": record}`.

    A reading, never truth, and **never seeded from `data/readings.md`**. The whole
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
            f"read-captions skill — never seeded from `data/readings.md`, which "
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
        text = _nfd(v if isinstance(v, str) else v.get("text", ""))
        proposed = _nfd(prop[key]["text"]) if key in prop else None
        rec = {"text": text,
               "edited": proposed is not None and text != proposed}
        # Stored only when it says something, `review.save_decisions`' rule: an
        # empty note on all 395 would make "this caption was remarked on"
        # unfindable by the only means anyone has, the key existing. This is the
        # adjudicator's note and the home the `@note` line of `data/readings.md`
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
