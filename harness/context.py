"""Assemble the per-page input contract for the collation pass.

Everything here is deterministic. The model consumes this; it never re-derives it.
Repo layout assumed:  scans/chukchi-PP-NNN.png   gt/fig/chukchi-PP-NNN.xml
                      ocr/chukchi-PP-NNN.xml     tei/chukchi-PP-NNN.xml
                      data/toc.json              data/readings.md
                      data/lexicon_extra.txt

PAGE REFS. A page is identified by its **PP-NNN** ref — part, and scan index
within that part — and by nothing else. NNN is a scan index, *not* a printed
folio: part 1 runs 001-362, part 2 001-268, part 3 001-202, while the printed
folio runs continuously 1-732 across the volume with plates and front matter
unpaginated. Neither is derivable from the other, so nothing here tries. A bare
integer is not a page identifier anywhere in this harness; where a folio is
needed it comes from state.py, which knows it only because a transcribed page
recorded one.
"""
from __future__ import annotations

import unicodedata
from pathlib import Path

from .detectors import detect_all, join_broken_words
from .refs import (
    _FOLIO_RE,
    APPARATUS_ZONES,
    FOLIO_ZONES,
    _folio_in,
    _window_folio,
    figure_number,
    norm_ref,
    stem_for,
)
from .state import entry_state, foreign_terms_nearby, load_toc, toc_window

ALTO_STRING = ".//{*}TextLine"


def _lines_from_alto(path: Path) -> list[str]:
    """ALTO -> plaintext lines, in **reading order**, empties dropped.

    Order comes from `lines.page_lines` rather than a second walk of the tree.
    This reader produces `catmus_draft`, and `_ocr_lines` beside it in the same
    page context is built from `page_lines` directly: if one were in segmenter
    order and the other in reading order, the two halves of a single contract
    would disagree silently, which is worse than either order alone. Deriving
    both from one banded source makes that impossible by construction instead of
    by two implementations agreeing.

    `lines.py`'s module docstring used to say this reader was "deliberately left
    alone: changing it would move `catmus_draft`, and with it the firewall's
    substring test and every detector line number." Half of that is spent -- the
    verbatim-substring test is gone (see the comment at its old site in
    `validate.validate`). The live half stands: `catmus_draft` and
    `detector_flags` must agree *with each other*, and they still do, because
    `build_context` derives both from this one call.

    Empty lines are still dropped, so position *i* here is **not** the *i*-th
    `TextLine`. That used to be the whole of a detector flag's addressing, and is
    no longer: `build_context` passes this reader's line indices to `detect_all`,
    so a flag names the ALTO identity and the position is not published at all.

    Imported locally: `lines` imports `norm_ref` from this module, so a
    module-level import here would be circular.
    """
    from .lines import page_lines
    return [rec["text"] for rec in page_lines(path) if rec["text"].strip()]




def _running_title(recs: list[dict], ref: str, root: Path) -> dict | None:
    """The page's own statement of what page it is.

    `{text, folio, folio_from, bracketed, lines}`, or null where the page carries
    none of the three zones a folio can print in — a plate, a blank, a page nobody
    has segmented.

    **The folio is looked for in `FOLIO_ZONES` order, and `folio_from` says which
    one answered.** That order is confidence, not frequency: the head line of an
    ordinary page first; then the bracketed number at the foot of a chapter
    opening; then the old vocabulary's dedicated zone, last because it names a
    store's spelling rather than a place on the page.

    **`text` is the running title and only ever that** — the head line with any
    folio token taken out of it. It is `""` on a page that has no running title,
    which a chapter opening does not: `1-151` has no head at all and still yields a
    folio, from the quire marks. So `text` and `folio` are independent, and neither
    being empty says anything about the other.

    Where nothing parses, `folio` is null and the lines are still in `text` — the
    caller has what the page holds and reads the number itself, the same "null
    means go and look" contract `expected_folio` keeps.

    This is also where the running title *goes*. `build_context` drops all three
    zones from `catmus_draft` as the printer's text; promoting them here means the
    information is restructured rather than discarded, and the folio in particular
    is the part the project needs — `<pb n>` is where page numbering enters the
    corpus.

    Two lines in the head is the ordinary case, not one: the title and the number
    sit on one printed line with a wide gap and the segmenter splits them.
    """
    by_zone = {z: [r for r in recs if r.get("zone") == z] for z in FOLIO_ZONES}
    if not any(by_zone.values()):
        # A store whose blocks carry no label at all: fall back to the zone store's
        # bands and take the lines inside them geometrically.
        for z in FOLIO_ZONES:
            by_zone[z] = _lines_in_zone(recs, ref, root, z)
    if not any(by_zone.values()):
        return None

    folio = bracketed = None
    source = ""
    for z in FOLIO_ZONES:
        hit = _folio_in(by_zone[z])
        if hit:
            folio, bracketed = hit
            source = z
            break

    head = sorted(by_zone["RunningTitleZone"], key=lambda r: r.get("hpos") or 0)
    text = " ".join(t for t in ((r["text"] or "").strip() for r in head)
                    if t and not _FOLIO_RE.match(t))
    return {"text": text, "folio": folio, "folio_from": source or None,
            "bracketed": bracketed, "lines": sum(len(v) for v in by_zone.values())}


def _lines_in_zone(recs: list[dict], ref: str, root: Path,
                   label: str) -> list[dict]:
    """Lines whose vertical midpoint falls in a zone of this label.

    Geometry rather than a label on the block, for the store whose blocks carry
    none. Reads `zones/` — the view, so a human-keyed page answers from
    `gt/zones/` and a machine-keyed one from `mz/zones/`, which is what the view
    is for. Silent `[]` when the page has no zones: absence of a segmentation is
    not an error here, it is the ordinary state of a page nobody has reached.
    """
    try:
        from .zones import VIEWDIR, read_zones
        bands = [(z["y0"], z["y1"]) for z in read_zones(ref, root, store=VIEWDIR)
                 if z["label"] == label]
    except Exception:
        return []
    if not bands:
        return []
    out = []
    for r in recs:
        v, h = r.get("vpos"), r.get("height")
        if v is None or h is None:
            continue
        mid = v + h / 2
        if any(y0 <= mid <= y1 for y0, y1 in bands):
            out.append(r)
    return out




def _figures_on_page(ref: str, root: Path = Path(".")) -> list[dict]:
    """The figures the book prints on this page: its own number, and the caption.

    **`n` is the book's identity, not the store's.** The pass anchors
    `<figure n="87"/>` at the textual reference it is already reading in English
    prose, and the build joins that number to the zones through
    `data/readings.md`. Nothing about geometry reaches the model, which is the
    whole point: **placing a figure is not the collator's competence**. Its
    competence is finding where the prose says "(Fig. 87, a)".

    That is a correction of two earlier shapes, and both failed the same way.
    The payload used to carry raw `zone_id`s — an opaque string a model cannot
    check, with the `GraphicZone`/FigDesc pairing left to it, which on `1-151`
    produced a correct anchor plus a permanent known-false orphan comment about
    the caption zone. Then it carried a page-local ordinal over pictures, which
    is worse than it looks: **the zone count is not the figure count in either
    direction**. `1-207` sets fig. 87 *a, b, c* in two boxes, `a` and `b`
    sharing one; several boxes routinely tile one irregularly-shaped figure. An
    ordinal over boxes would have told the model "2 figures" on a page the book
    calls one figure with three parts — the pairing problem again, one level
    down, and unanswerable from geometry because the evidence is prose inside
    the caption.

    So the number does the work. It is unique across text-figures 1–302,
    corroborated by `data/loi.json`, and `validate` checks the pass's `n`
    against the numbers printed in *this* page's captions — a real second
    witness, and the one thing that catches a figure anchored on the wrong page.

    `n` is null where the caption prints no number, and where a figure has no
    caption at all (`3-006`, `3-007`). Neither is an error and neither is the
    pass's business: an uncaptioned zone has no textual reference either, so
    there is nothing to anchor, and the build places it by page. Plates restart
    numbering per plate and are full-page artwork with no body text, so they
    reach this list and are never referenced from it.

    `caption` comes from **`data/readings.md`**, not from the ALTO. `gt/fig/`
    carries no `TextLine` — the lines were stripped, because the exported line
    segmentation dropped whole printed lines. Reading `String/@CONTENT` here used
    to be the source, and after the strip it returned `""` for every zone on
    every page: the model was handed figures with no captions and nothing said
    so.
    """
    from .figures import paired
    out, seen = [], set()
    for f in paired(ref, root)["figures"]:
        # One record per *printed figure*, so the pictures sharing fig. 253's
        # caption are one row and not two. Deduped on the caption itself rather
        # than on the number, since an uncaptioned zone has neither.
        if f["caption"] and f["caption"] in seen:
            continue
        seen.add(f["caption"])
        out.append({"n": figure_number(f["caption"]), "caption": f["caption"]})
    return out




def _figure_line_warnings(recs: list[dict], ref: str,
                          root: Path = Path(".")) -> list[dict]:
    """Lines the segmenter ran across a figure boundary, and lines inside artwork.

    Two segmenter failures the collation pass has to be told about rather than
    left to infer:

      * `straddles_caption` — one `TextLine` spanning the end of a wrapped caption
        and the start of body text. The caption's own reading is attached, so the
        model can see which half is already accounted for.
      * `inside_graphic` — a line wholly inside a plain `GraphicZone`. Usually the
        zone is simply drawn too large: `3-006`'s `CONSANGUINITY.` is a real
        section heading sitting inside caption-less artwork. Reported, never
        suppressed — the alternative deletes headings.

    **The split is geometric, and only geometric.** A page's ALTO carries one
    `String` per `TextLine` with no word- or glyph-level boxes (and `restore`
    requires exactly one), so the pixel boundary between caption and body cannot be
    mapped to a character offset in the line's text. `caption_side` and `body_side`
    are therefore the two *boxes*; the text is handed over whole and the division
    is left to the reader, who can see the page. Splitting the string at a
    proportional index would be a fabricated position — the shape of guess this
    project exists to refuse.

    Empty on all 20 restored pages: no real straddle occurs in the pilot set, so
    this ships exercised only by fixture. Threshold and shape want revisiting the
    first time a genuine one turns up.
    """
    # Read straight from the store rather than from `_figures_on_page`, which no
    # longer carries geometry or the caption zones at all — this is the internal
    # join the model's payload was never the right place for.
    from .figures import readings_for, zone_suffix, zones
    by_zone = {z["id"]: z for z in zones(ref, root)}
    try:
        texts = readings_for(ref, root)
    except (ValueError, OSError):
        texts = {}
    out = []
    for r in recs:
        zid = r.get("figdesc_straddle")
        if zid:
            z = by_zone.get(zid, {})
            cut = z.get("vpos")
            out.append({
                "kind": "straddles_caption", "index": r["index"],
                "line_id": r["line_id"], "zone_id": zid,
                "caption_side": f"{r['hpos']},{r['vpos']},{r['width']},"
                                f"{max(0, (cut or r['vpos']) - r['vpos'])}",
                "body_side": f"{r['hpos']},{cut},{r['width']},"
                             f"{max(0, r['vpos'] + r['height'] - (cut or r['vpos']))}",
                "caption": ((texts.get(zone_suffix(zid)) or {})
                            .get("text") or "")[:200],
            })
        elif r.get("in_graphic"):
            out.append({
                "kind": "inside_graphic", "index": r["index"],
                "line_id": r["line_id"], "zone_id": r["in_graphic"],
                "caption_side": "", "body_side": "", "caption": "",
            })
    return out


def _ocr_lines(ocr_path: Path, root: Path = Path("."),
               ref: str | None = None) -> list[dict]:
    """OCR lines with their ALTO ids, for optional @facs citation on a Tier-1 span.

    Deliberately not `catmus_draft`: that reader (`_lines_from_alto`) drops
    empty lines and discards `@ID`, so its indices don't join back to a real
    ALTO line. This calls the ID-preserving reader instead, and only the
    fields the model can usefully cite — no geometry; it never sees pixels
    here, only proposes a pointer a human later resolves with `harness ocr zoom`.

    Reads the same `ocr/{stem}.xml` the draft already reads — not a second
    ALTO store — since a facs pointer must resolve in the ALTO the model
    actually saw.

    **`APPARATUS_ZONES` are omitted here as well as from the draft**, and for a
    sharper reason than there. The draft excludes them because they are the
    printer's text; this list excludes them because **nothing in the TEI can ever
    point at one**. `@facs` cites the line a Tier-1 span was read from, and a
    running head, a folio and a signature line are not in the body at all — so
    every one of them in this list is a pointer target that would be a mistake to
    use, offered to a pass that is choosing among them.

    A caption line stays, and the difference is worth keeping straight: a caption
    is excluded from the *draft* only, because the project already has a human
    reading of it in `data/readings.md` and showing the model two witnesses of
    different rank invites it to reconcile them. It remains citable, so it remains
    here.

    Omitting records cannot disturb the rest: `index` is an identity assigned by
    ALTO document order, never a position in this list.

    **`line_id` was removed, and `index` is what `@facs` cites.** The ALTO `@ID`
    was a currency nothing in the harness accepts: the skill told the pass to
    write `facs="#eSc_line_e5fa4af8"` and then promised the payoff was
    `harness ocr zoom REF --only <index>`, which are two different keys, so acting
    on a citation meant translating it back by hand first. `detector_flags` moved
    off a draft position and onto `index` for exactly this reason; this was the
    last field left pointing somewhere else. Neither form resolves as a TEI URI
    today — there is no `<facsimile>` in the corpus — so nothing conformant was
    given up, and `index` is the one a human and a tool can both act on.
    """
    from .lines import page_lines  # local: lines.py imports context at module
                                    # level, so this avoids a cycle.
    return [{"index": r["index"], "text": r["text"]}
            for r in page_lines(ocr_path, root, ref=ref)
            if r["zone"] not in APPARATUS_ZONES]


def tier1_terms(ref: str, root: Path = Path("."), keys: bool = True,
                idx: dict | None = None) -> list[dict]:
    """Tier-1 tokens a human has already keyed on this page, with a local handle.

    **Copying is a fresh error surface bolted onto a solved problem.** Where
    `gt/ocr/` holds the page, every mark on it has been adjudicated at the
    raster; a collation pass that retypes `ɪᵋplɪˊlᴇ` character by character can
    drop a U+0323 or read `ɪ` as `i` — §5's two residual classes — and nothing
    downstream disagrees, because the form is unfalsifiable by construction. So
    the pass names the token by `index` and `harness tei expand` writes the
    ratified string in. The model's judgement is *which* token; the glyphs are
    never its to originate.

    **`gt/` only, and never `mz/` or the view.** CATMuS reads 0% of the
    inventory, so a list built from a prediction would be a list of garbled
    forms offered to be copied verbatim — the failure this exists to prevent,
    inverted. A page with no ground truth gets no list at all, which is a true
    statement about the page rather than an empty one: the pass then reads the
    raster itself and flags what it wrote.

    **What counts as Tier-1 here is `NON_ENGLISH_HITS`** — an inventory glyph or
    a straight apostrophe — and not `INVENTORY_CHARS` alone, which omits U+0027
    despite a comment in `detectors` saying otherwise. That matters because
    a straight apostrophe inside a form is a mistyped stress mark (§2.1), so it
    marks a Tier-1 token as surely as an inventory glyph does.

    **The list is a floor and cannot be otherwise.** An unmarked ASCII inventory
    member (`c` for English *sh*, plain `s`, `j`, `x`) is undetectable, so a form
    made only of those gets no handle and has to be typed. That costs little and
    the reason is structural rather than lucky: what makes a token undetectable
    is having no marks, and what makes a token dangerous to retype is having
    marks. The blind spot and the risk are near-complementary.

    **One token per handle.** A multi-token Tier-1 span would need a range, and
    the corpus has none — all 30 spans in committed TEI are single tokens. Built
    for the attested case, in the habit of `_figure_line_warnings`; a range is
    cheap to add against a real instance and guesswork before one.

    `line` is the ALTO line index, the same identity `ocr_lines` and
    `detector_flags` carry, so a term resolves with `harness ocr zoom REF --only
    <line> --store gt` like everything else.

    **`keys=False` omits the `key` column, and omits the corpus walk that builds
    it.** Measured at 1.57s a call — `lookup.index` reads every keyed page twice
    — against ~10ms for everything else here, so the key column *is* the cost of
    this function. Three of its four callers never read the column: `validate`
    takes `text`, `expand` takes `index` and `text`, `generate` takes `line`.
    Only `build_context` needs it, because the collator prompt prints it.

    The column is **absent** rather than empty under `keys=False`, and the
    difference is the usual one here: `key: ""` is a claim — no key resolves back
    to this form, which `_with_keys` decides one form at a time — while a missing
    field is the absence of a claim, and a consumer that wants one gets a
    `KeyError` rather than a false negative.

    `idx` is a prebuilt `lookup.index`, for a caller looping over pages; it
    changes nothing about the answer.
    """
    from .detectors import EDGE_PUNCT, INVENTORY_CHARS, TOKEN, cyrillic
    from .lines import page_lines

    path = root / "gt" / "ocr" / f"chukchi-{norm_ref(ref)}.xml"
    if not path.exists():
        return []
    recs = page_lines(path, root, ref=ref)
    # **A half of a broken word is not a form, and must not be offered as one.**
    # `1-101` prints `Torwaˊwaq` as `(Tor-` / `waˊwaq)`, so this list held
    # `waˊwaq` — a whole token on its line, ratified, and *half the word*. A pass
    # naming it writes a truncated form that `tei expand` fills and stamps `#gt`,
    # and every guard passes: it really is a token in this page's ground truth.
    # Same boundary the whole-token check protects at one end (`Qeˊñ` ⊂ `Qeˊñu`),
    # broken at the other by the compositor's measure.
    #
    # The test is survival of the join: a token is offered only if it is still a
    # whole token after `join_broken_words`. The rejoined form itself is *not*
    # offered in its place — `Tor-waˊwaq` is a string no line holds, and whether
    # that hyphen is the word's or the printer's is exactly the ambiguity
    # `5be1853` preserved rather than decided. So a broken form gets no handle and
    # arrives instead as a `detector_flags` row on the joined text, which is the
    # correct answer: read the page. (`1-101`'s editor did, and left a comment.)
    survives = [{m.group().strip(EDGE_PUNCT)
                 for m in TOKEN.finditer(unicodedata.normalize("NFD", t))}
                for t in join_broken_words(recs)]
    out = []
    for rec, whole in zip(recs, survives, strict=True):
        if rec["zone"] in APPARATUS_ZONES:
            continue
        text = unicodedata.normalize("NFD", rec.get("text") or "")
        for m in TOKEN.finditer(text):
            tok = m.group().strip(EDGE_PUNCT)
            # `cyrillic` is `native_corpus`'s exclusion, shared rather than
            # restated. Pre-1918 Russian sets `й`, which is и + U+0306 under
            # NFD, and U+0306 is an inventory member — so `Чукотскій` on 1-031
            # trips this selection exactly as a Chukchee form does. The two arms
            # disagreed until the reading view made it visible: the generator
            # wrapped the word as a Tier-1 handle while every frequency table
            # excluded it, and the page then offered a link to a lexicon that
            # correctly held nothing. Russian is Tier-2; the ASCII policy does
            # not reach it and no Cyrillic string is evidence about Bogoras's
            # notation.
            if (tok and tok in whole and not cyrillic(tok)
                    and any(c in INVENTORY_CHARS or c == "'" for c in tok)):
                out.append({"index": len(out) + 1, "line": rec["index"],
                            "text": tok})
    return _with_keys(out, root, idx) if keys else out


def _with_keys(rows: list[dict], root: Path,
               idx: dict | None = None) -> list[dict]:
    """Add the lexicon handle to each term, where one resolves back to it.

    **`index` addresses this page and `key` addresses the corpus**, and the
    second is what makes a form typeable anywhere else. `tei expand` takes the
    index and writes the ratified string into *this* page; `{key}` is what
    `entity alias` and `proposal set` expand, so a collator proposing an entity
    for a Tier-1 toponym can name the form without keying a single glyph of it.
    Without this the key was reachable only by running `lexicon lookup` against
    a form the reader would have had to type first, which is the copying this
    whole list exists to avoid.

    **A key is printed only where it resolves back to the very form beside it.**
    `handle_key` is a spelling and `resolve` is a promise: a bucket the book
    spells two ways refuses, and a precise key pointing into a contested bucket
    is refused with it. Emitting a key that will not expand would hand a reader
    a handle that fails at the far end, which is worse than an empty cell — the
    empty cell says "type this one", and the store's own §5 says which forms
    those are.

    **`min_pages=1`, and the difference from `tei expand` is the point.** That
    floor — "one page is a neighbour, not a corpus" — guards writing a
    barely-attested form *into* a page. Naming a form is a different act: a
    toponym printed once is still that toponym, and 1-359 is a gazetteer where
    nearly every form is a hapax. At the default floor this column came back
    empty for fifteen of twenty terms on the one page it was asked for. The
    ambiguity refusal is untouched and is the one that matters, since it is the
    book disagreeing with itself rather than the corpus being small.

    The index is built once for the page and passed down; `lookup.index` walks
    the whole ground-truth corpus and is not cached. A tree with no lexicon
    config is a tree where no key exists, so every cell is empty and nothing
    raises: `tier1_terms` still answers its own question.

    **`idx` lets a caller looping over pages build it once instead of once a
    page.** Measured at 1.57s a build, against ~10ms for the rest of
    `tier1_terms`, so a corpus-wide `tei validate` was spending essentially all
    of its time here. Not a module cache — `harness/README.md` holds that a cache
    is a property of a server and the CLI reads a store once and exits — but the
    same `idx=` parameter `lookup.resolve`, `search` and `expand` already take,
    extended one layer inward rather than invented.

    **That last sentence is the whole licence, and the guard used to be wider
    than it.** `except Exception` also swallowed a corpus that would not read —
    so "there is no config here" and "the index failed to build" reached a
    collating model as the same empty column, and the model has no way to ask.
    Narrowed to the config error the sentence is about; anything else is a fault
    about the corpus and travels.
    """
    if not rows:
        return rows
    from .lookup import index, resolve
    from .marks import MarksConfigError, handle_key

    try:
        idx = index(root) if idx is None else idx
    except MarksConfigError:
        return [{**r, "key": ""} for r in rows]
    out = []
    for r in rows:
        key = ""
        try:
            cand = handle_key(r["text"])
        except ValueError:
            cand = ""
        if cand:
            form, _why = resolve(cand, root, min_pages=1, idx=idx)
            if form == r["text"]:
                key = cand
        out.append({**r, "key": key})
    return out


def entity_hits(ref: str, root: Path = Path("."),
                store: dict | None = None) -> list[dict]:
    """Every entity-alias hit on this page, linked or not.

    `store` is an `entities.load` a caller already holds. Without it this globs
    and parses all 461 entity files — **29ms**, against ~3ms for everything else
    here — once per page, which a corpus-wide run pays per page twice over
    (`validate` loads it again for the same reason). `alias_index` and
    `auto_forms` stay derived here: 0.3ms and 0.1ms, so passing them too would be
    three parameters buying nothing over one.

    **The same matcher the generator ran**, over the same joined text, so the
    rows and the page agree by construction rather than by two implementations
    happening to. `linked` is the generator's own bar — one ratified entity
    claims the form and its author marked it `auto: yes` — so a row with
    `linked: false` is a question standing open in the file, and the two counts
    are the same count.

    `ids` is every entity claiming the form. Where there are several the string
    is ambiguous by construction and only the sentence decides; where there is
    one and `linked` is still false, its author declared the form unsafe out of
    context. Both are the reader's to settle and neither is the tool's.
    """
    from .entities import alias_index, auto_forms, load, match
    from .generate import page_blocks

    path = root / "gt" / "ocr" / f"chukchi-{norm_ref(ref)}.xml"
    if not path.exists():
        return []
    store = load(root) if store is None else store
    idx = alias_index(store)
    if not idx:
        return []
    autos = auto_forms(idx)
    blocks = page_blocks(ref, root)
    out = []
    for band, rows in blocks:
        if band is not None and band["label"] in APPARATUS_ZONES:
            continue
        if not rows:
            continue
        # Joined exactly as the generator joins it, and the hit's offset resolved
        # back to the line it *starts* on — a cross-line match belongs to its
        # first line, which is where a reader looking for it will be.
        starts, at = [], 0
        for _, t in rows:
            starts.append(at)
            at += len(t) + 1
        full = "\n".join(t for _, t in rows)
        for h in match(full, idx):
            line = next(ln for (ln, _), s in zip(reversed(rows),
                                                 reversed(starts), strict=True)
                        if s <= h["start"])
            out.append({"line": line, "form": h["form"],
                        "as_printed": " ".join(h["text"].split()),
                        "ids": " ".join(h["ids"]),
                        # The generator's own bar, re-derived: a hyphenated
                        # spelling is never linked by rule, so it must not show
                        # as linked here either or the table and the file
                        # disagree about which questions are open.
                        "linked": (not h["hyphenated"]
                                   and autos.get(h["form"]) is not None),
                        "status": h["status"] or "(several claim it)"})
    out.sort(key=lambda r: (r["line"], r["form"]))
    return out


def build_context(ref: str, root: Path = Path("."),
                  idx: dict | None = None,
                  store: dict | None = None) -> dict:
    """The whole per-page input contract for the collation pass, as one dict.

    Everything a model needs to produce this page's TEI and nothing it would have
    to re-derive: the ref and stem, the seam state folded forward from committed
    TEI, a ToC neighbourhood, the figure zones with their captions, the OCR line
    ids a Tier-1 span may cite in `@facs`, and the detector flags. Deterministic
    and precomputed by design — a pass that re-derived any of this could disagree
    with the validator that checks it.

    Imported locally, not at module scope: `figures` imports `norm_ref` from here,
    so a top-level import would close a cycle. Three other call sites in this
    package do the same for the same reason.

    `idx` is a prebuilt `lookup.index`, passed straight to `tier1_terms` — this
    is the one caller of it that wants the `key` column, and so the one that pays
    the corpus walk. A caller looping over pages should build it once.

    `store` is the same arrangement for the entity store, passed to
    `entity_hits`: 29ms of glob-and-parse over 461 files, which `validate` then
    repeats for its own read of the same store. Both are reads of a fixed input
    hoisted out of a loop, and neither moves a judgement — every verdict is still
    computed per page from the page's own content.
    """
    from .generate import GENDIR
    from .seam import tail as seam_tail
    ref = norm_ref(ref)
    stem = stem_for(ref, root)
    ocr = root / "ocr" / f"{stem}.xml"
    if not ocr.exists():
        raise FileNotFoundError(f"no {ocr} — {ref} has no OCR yet")

    state = entry_state(ref, root)
    # **`kept` outlived the draft it was built for.** It used to feed
    # `catmus_draft`; what still needs it is `detector_flags`, which fires over the
    # same filtered, joined text and must go on doing so — a flag on a running head
    # or a caption is a flag on text that will never be in the body.
    #
    # The filtering stays here rather than moving into `_lines_from_alto` because
    # that reader is shared with `detectors.suggest_lexicon` and the corpus
    # frequency tables. Excluding caption lines there would silently move published
    # numbers: `2-030`'s caption alone carries 10 of the corpus's 109 U+0323 marks —
    # 9.2% of them, from 2.0% of its characters — and keying_spec section 5.1 cites
    # those tables for the "~90% of g's carry the dot" prior. Same reader, two
    # consumers, and only one of them wants the exclusion.
    from .lines import page_lines
    recs = page_lines(ocr, root)
    # A caption is text the project already has a *human* reading of
    # (`data/readings.md`, all 395), and it reaches the model below as
    # `figures_on_page[].text`. Leaving the line segment in the draft too would
    # hand the model the same caption twice, from two witnesses of different rank,
    # and invite it to reconcile them. Marked lines are excluded from the draft
    # only — they stay in `gt/ocr/`, in the review queue, and in `ocr_lines`, the
    # last because that is what a `@facs` pointer resolves against.
    # The running head with its folio, and the printer's signature line at the foot
    # of a gathering: the printer's text, not the author's, and now identifiable
    # because `ocr predict` writes the zones in as the ALTO's regions. Excluded on
    # the same terms as a caption — from the draft only. They stay in the store, in
    # `ocr_lines`, and one field away in `harness ocr lines PP-NNN`.
    #
    # **Excluded here and not in `ocr predict`**, because the running head shares
    # its zone with the printed folio, and the folio is where page numbering enters
    # the project (`<pb n>`). Dropping it at write time would take the OCR's only
    # record of it and cost a re-run of the page to get back.
    #
    # An unlabelled block is *kept*: `gt/ocr/` and `gt/seg/` label none, so treating
    # blank as apparatus would empty the draft for every ground-truth page.
    kept = [r for r in recs
            if r["text"].strip() and not r["in_figdesc"]
            and r["zone"] not in APPARATUS_ZONES]
    # **The flags read the joined text; the draft does not.** `join_broken_words`
    # rejoins a word the compositor broke across a printed line, and both `lexicon`
    # arms have read through it since 2026-08-03 — but this arm builds its own
    # draft and so was never included, which is why the collation payload went on
    # reporting `Chuk`/`chee`, `Penin`/`sula`, `direc`/`tions` as words no
    # dictionary knows. About a quarter of the residual flags on a ground-truth
    # page were the printer's measure running out.
    #
    # The draft itself must stay line-per-line: the model reads the raster beside
    # it, and a draft that silently reflowed would stop being checkable against
    # the page. So the two diverge here deliberately, which is safe only because
    # `index` is carried alongside rather than being a position in either list.
    #
    # Emptied lines are dropped **with their index**, exactly as `suggest_lexicon`
    # drops them: a line whose only token moved up now has no text of its own, and
    # the token is cited at the line it starts on. Dropping the pair also keeps
    # `_balance` seeing one paragraph per page — an empty line is a paragraph break
    # there, so leaving the holes in would split a page at every rejoined word and
    # invent unbalanced-paren complaints across the seams.
    joined = [(t, str(r["index"]))
              for t, r in zip(join_broken_words(kept), kept, strict=True)
              if t.strip()]
    detected = detect_all([t for t, _ in joined], root,
                          indices=[i for _, i in joined])
    figures = _figures_on_page(ref, root)
    # A term this page has already adjudicated at the raster does not also need
    # flagging, and flagging it is worse than redundant: `tier1_terms` gives the
    # pass a handle that writes the ratified glyphs, and a flag on the same token
    # invites it to read the form instead — the one thing the handle exists to
    # stop. So the flags become *what is left*: the Tier-1 material on this page
    # with no ratified reading behind it, which on an `mz/`-backed page is all of
    # it and on a ground-truth page is the floor's residue (an unmarked ASCII
    # inventory member gets no handle and still wants a human).
    #
    # Suppressed on the pair, never on the token alone: `index` is the ALTO line,
    # so the same form occurring on a line the ground truth does not cover stays
    # flagged. Comparable only because both sides now cut `EDGE_PUNCT` once, at
    # the tokenizer — while `detect_all` published `"mêˊmêl),"` no equality test
    # here could have matched anything.
    # `t["line"]`, not `t["index"]` — the latter is the handle `tei expand`
    # resolves, and these two numberings share neither meaning nor range.
    terms = tier1_terms(ref, root, idx=idx)
    ratified = {(str(t["line"]), t["text"]) for t in terms}
    detected["tokens"] = [f for f in detected["tokens"]
                          if (f["index"], f["token"]) not in ratified]

    running = _running_title(recs, ref, root)
    window_folio, window_witness = _window_folio(state["expected_folio"], running)

    return {
        # **The validator's two fields, and not the model's.** `validate` builds its
        # own context and reads exactly these back — `root` for the full ToC id set
        # (300-odd ids nobody would put in a prompt) and `page_ref` to re-read
        # `tier1_terms` from the store rather than from this dict, which is what
        # keeps the provenance check a second witness instead of the same one twice.
        # They stay because something reads them; they are named here because
        # nothing in the pass should.
        "page_ref": ref,
        "root": str(root),
        "page_image": str(root / "scans" / f"{stem}.png"),
        # The generated page under review. **This replaces `catmus_draft`**, which
        # was the pass's input while it authored TEI from plaintext, and which had a
        # whole section of the contract defending against it: what arrived under a
        # machine label was usually restored human ground truth, so the pass could
        # not see the rank of its own input and was told at length not to guess.
        # `tei queue` now refuses a page without `gt/ocr/`, so there is one rank and
        # `page_state` had nothing left to report either. A lower-ranked second copy
        # of the page's text, sitting beside the file being reviewed, would be the
        # two-witnesses-that-are-one hazard pointed the wrong way.
        "generated": str(root / GENDIR / f"{stem}.xml"),
        # Folio is a prediction from the preceding transcribed page, or null.
        # Null is not a defect: it means read it off the image and don't guess.
        "expected_folio": state["expected_folio"],
        "folio_basis": {"prior_ref": state["prior_ref"],
                        "basis_ref": state["basis_ref"],
                        "basis_folio": state["basis_folio"]},
        # What the page itself says it is, off its running title — the second
        # witness to `expected_folio` above, which is a prediction from the
        # preceding page and knows nothing about this one. Cheap, independent, and
        # the two disagreeing is the signal.
        "running_title": running,
        # A neighbourhood with marks, not a resolution. `open` is what the
        # milestone fold believes; it informs, it does not decide.
        "toc_window": toc_window(load_toc(root), window_folio,
                                 state["believed_open"]),
        # WHICH folio centred the window above, because an empty one has two very
        # different causes and the pass would otherwise have to guess which.
        "toc_window_folio": {"folio": window_folio, "witness": window_witness},
        # The end of the previous page's committed TEI, so the pass can see
        # whether this page opens mid-element instead of inferring it. Null when
        # the predecessor is not collated — then the seam is genuinely unknown and
        # `harness tei seam` will refuse it too. About 70% of text pages open
        # mid-paragraph (measured over the keyed zone corpus), so this is the
        # common case, not an edge one.
        "prev_tail": seam_tail(ref, root),
        "figures_on_page": figures,
        # Segmenter faults where a line meets a figure: a line running from a
        # wrapped caption into body text, or a line sitting inside artwork. Both
        # are reported rather than acted on — see `_figure_line_warnings`.
        "figure_line_warnings": _figure_line_warnings(recs, ref, root),
        "ocr_lines": _ocr_lines(ocr, root, ref),
        # Tier-1 tokens already adjudicated at the raster, named by a page-local
        # handle so the pass never retypes one. Empty on a page with no ground
        # truth, which is 802 of 832 — there the pass reads and flags instead.
        "tier1_terms": terms,
        # Foreign spans already committed on the physically neighbouring pages,
        # recomputed from the TEI each call. For cross-checking a term keyed two
        # ways — never a source to copy from; this page's draft is the only
        # source for this page's Tier-1 content.
        "foreign_terms_nearby": foreign_terms_nearby(ref, root),
        # Every alias hit on this page, whether the generator linked it or not
        # — `linked` says which. An aid to judgement and never an input to
        # composition, in the same disposition `foreign_terms_nearby` keeps: the
        # rows say what the store claims about a string, and whether the claim
        # is true *here* is what the reader is for. The unlinked ones are the
        # interesting half, and each already carries a comment in the generated
        # page; this is the same set gathered into one table, so a reader can see
        # at a glance that one form recurs eight times rather than meeting it
        # eight separate times.
        "entity_hits": entity_hits(ref, root, store),
        # Two tables, not one: token-level hits and paragraph-level balance
        # complaints are different record shapes and are kept apart so each
        # stays uniform.
        "detector_flags": detected["tokens"],
        "balance_flags": detected["balance"],
        # `stem` and `output_path` are gone with `page_state` and `catmus_draft`.
        # They were justified as redundancy — the ref arrives in the page block, and
        # naming the file again could only help — but preventing a write to the
        # wrong path is the guard hook's job, mechanically, and a prompt variable
        # cannot do it at all. What redundancy actually bought was a second place
        # for a path to be right or wrong.
    }
