"""A first-draft TEI page, built by rule from `gt/zones/` and `gt/ocr/`.

**The collation pass used to author structure a store already held.** A collator
read the raster and a plaintext draft and decided, by eye, where paragraphs began
— on pages whose `gt/zones/` records exactly that, keyed by a human, as
`MainZone-P` (a paragraph opens here) against `MainZone-Continued` (it does not).
Re-deriving an adjudicated fact is the shape this project exists to avoid: the
second derivation can disagree with the first, nothing downstream can tell which
is right, and the disagreement is invisible because both look like prose.

So the rules run first and the model reviews what they wrote. What changes is not
how much a reader does but *what kind* of thing it does — every judgement left
here needs a page in front of it, and none of them is a fact already written down.

**What this can honestly produce, and what it must not.** The store knows where
paragraphs begin, which lines are apparatus, which block is the footnote
apparatus, which is a quotation, and what folio the page prints. It does not know
a heading from a table from a caption — all three land in `MainZone-Other`, whose
`rank: null` says as much — nor where a note anchors in the body, nor what
language a form is in, nor where a figure is discussed. Every one of those leaves
a comment naming itself, and the review contract is the list of comments to clear.

**`mz/tei/` is to `tei/` what `mz/zones/` is to `gt/zones/`**, and the pairing is
the point: the generated file stays on disk, so `harness tei diff` can say what
review changed. The collation pass had no baseline before, which made "did the
collator invent this?" an unanswerable question about every page it produced.

**Two witnesses to a paragraph boundary, and they are kept apart.** The zone
labels are a human's assertion; `zones.paragraph_starts` measures first-line
indents off the blotted raster (96.9% recall over 716 pages) and cuts *within* a
band where one human zone holds two paragraphs. Where the raster is missing the
split degrades to zone boundaries alone and says so in the file — a page with
fewer paragraphs than it should have, marked as such, rather than a silent one.

**The seam witness is not generated.** `<!-- opens: … -->` means what a reader saw
on the raster, and seeding it from the zone label would leave `tei seam` comparing
a value with itself — the one-witness collapse, in the one place the project has
already paid for it twice. The generator writes `<!-- zone-opens: … -->` instead,
which is the *other* witness, and the missing `opens:` is a validate error the
collator clears by looking at the page.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from xml.sax.saxutils import escape

from .context import (
    APPARATUS_ZONES,
    _figures_on_page,
    _running_title,
    norm_ref,
    tier1_terms,
)
from .detectors import join_broken_words
from .entities import auto_forms, load, trigger_index
from .lines import page_lines
from .zones import read_zones, split_at_paragraphs

#: Bumped when the emitted shape changes in a way that makes an older file a
#: different artifact rather than an older copy of the same one. It rides in the
#: stamp, so `tei diff` can say "this baseline predates the current rules" instead
#: of reporting the difference as something review did.
VERSION = 2

GENDIR = "mz/tei"

#: Zone labels that become body prose, and what each becomes. A label absent from
#: here is not prose and is handled by name below; a label absent from *both* is a
#: vocabulary change the generator has not been told about, and it says so rather
#: than guessing which side it belongs on.
PROSE = {"MainZone-P": "p", "MainZone-Continued": "p", "MainZone-Quote": "quote"}
NOTES_ZONE = "MarginTextZone-Notes"
OTHER_ZONE = "MainZone-Other"


def gen_dir(root: Path = Path(".")) -> Path:
    return root / GENDIR


def gen_path(ref: str, root: Path = Path(".")) -> Path:
    return gen_dir(root) / f"chukchi-{norm_ref(ref)}.xml"


def _inputs(ref: str, root: Path) -> tuple[Path, Path]:
    ref = norm_ref(ref)
    return (root / "gt" / "ocr" / f"chukchi-{ref}.xml",
            root / "gt" / "zones" / f"chukchi-{ref}.xml")


def _stamp(ref: str, root: Path) -> str:
    """Version plus a digest of both inputs, so a stale baseline is detectable.

    Without it `tei diff` cannot tell a difference review made from one a
    regeneration made under it, and would report the second as the first — a diff
    whose witness may have moved is exactly the comparison that must say so.
    """
    h = hashlib.sha256()
    for p in _inputs(ref, root):
        h.update(p.read_bytes())
    return f"generated: harness tei generate v{VERSION} inputs={h.hexdigest()[:16]}"


class Unready(Exception):
    """A page the generator will not guess at. Carries the verb that fixes it."""


def _require(ref: str, root: Path) -> None:
    ocr, zones = _inputs(ref, root)
    if not ocr.exists():
        raise Unready(
            f"{ref}: no gt/ocr/ — generation reads adjudicated text only. "
            f"Restore the page first (/rebuild-groundtruth)")
    if not zones.exists():
        raise Unready(
            f"{ref}: no gt/zones/ — the paragraph boundaries are the human zone "
            f"labels, and a prediction is not one. Key the page in `harness zones edit`")


def _bands(ref: str, root: Path) -> tuple[list[dict], str]:
    """The page's zones, cut at measured paragraph openings where that is possible.

    Returns the bands and how the split was reached, because those are two
    different pages: one where the indent detector ran and one where only the
    keyed boundaries are represented. The second is a real degradation — a human
    zone holding three paragraphs stays one `<p>` — and a caller that could not
    tell them apart would publish the short page as if it were the full one.
    """
    zones = read_zones(ref, root)
    try:
        return split_at_paragraphs(zones, ref, root), "raster"
    except Exception:
        # The blotted raster and the scan are both derived and neither is in git,
        # so a fresh clone reaches this. Degrading beats refusing: the zone labels
        # alone still carry every boundary a human keyed, which is most of them.
        return zones, "zones-only"


def _assign(recs: list[dict], bands: list[dict]) -> list[list[dict]]:
    """Bucket lines into bands by the top edge, plus a final bucket for the rest.

    Geometry rather than the ALTO's own `TAGREFS`, because the bands may have been
    cut since `ocr predict` wrote those blocks — a split band exists only in this
    call, so a line could not be carrying its label.

    **The line's vertical centre, not its top edge**, and the difference is a whole
    line every time. A paragraph cut is made at the top of the opening line's *ink*
    (`split_at_paragraphs`), while an ALTO `TextLine` polygon starts above its ink —
    it has to, or it would clip the ascenders. So the opening line's `vpos` sits a
    few pixels *above* the cut drawn for it and every paragraph took one line too
    many from the one below, which read as plausible prose and was off by one on all
    five of `1-021`'s paragraphs. The centre is inside the line's own ink by
    construction and nowhere near either edge, so it cannot land on the wrong side
    of a boundary drawn between lines.

    **`y` alone, and testing `x` too is a bug rather than a tightening.** These
    zones are a *vertical partition of a measured column* — fixed-width bands, by
    construction (`docs/segmentation.md`) — so the band's `x` range carries no
    membership information, and a line whose `hpos` sits a few pixels outside it is
    still that band's line. Requiring both dropped 15 of `1-021`'s lines into the
    outside-zone bucket on the first run: alternating lines of ordinary paragraphs,
    which read as an artwork problem and were an arithmetic one.

    The last bucket is lines inside no band, and they are **kept**. A line outside
    every zone is visible junk and a dropped line is invisible; that asymmetry is
    the same one `ocr predict` settles the same way.
    """
    buckets: list[list[dict]] = [[] for _ in bands] + [[]]
    for r in recs:
        mid = r["vpos"] + r.get("height", 0) // 2
        for i, b in enumerate(bands):
            if b["y0"] <= mid < b["y1"]:
                buckets[i].append(r)
                break
        else:
            buckets[-1].append(r)
    return buckets


def _tier1_spans(rows: list[tuple[int, str]], by_line: dict[int, list[dict]],
                 offsets: list[int]) -> list[tuple[int, int, str]]:
    """Ratified Tier-1 tokens, as spans over the block's joined text.

    The handle is `<foreign index="N"/>` — empty, and carrying no `xml:lang`,
    because **which language a form is in is a judgement and this is a rule**.
    `tier1_terms` is a floor over inventory marks with no language awareness, so it
    catches an ordinary German surname carrying a combining diaeresis exactly as it
    catches a Chukchee form; `Döring` on `1-022` is the standing case. A generator
    that named a language would be inferring one from the shape of a word, which is
    the firewall's failure mode one category over from glyphs.

    So the wrap says only "a ratified token sits here" and the gate refuses a
    lang-less `<foreign>`, which turns every one of them into a question the
    reviewer has to answer: name the language, and `tei expand` writes the adjudicated
    glyphs in; or unwrap, because it was never a foreign form.

    Located per line and then translated to block offsets, rather than searched
    for in the joined block: `tier1_terms` reports which line it found a token
    on, and a token that occurs on two lines would otherwise both times resolve
    to the first.
    """
    spans = []
    for (index, text), base in zip(rows, offsets, strict=True):
        pos = 0
        for t in by_line.get(index, []):
            i = text.find(t["text"], pos)
            if i < 0:
                # The token was found on this line by `tier1_terms` and is not in
                # the joined text — a broken word rejoined onto its neighbour.
                # Skipping is right: `detector_flags` still carries it, so the
                # reviewer is told to read the page rather than handed a handle
                # pointing at half a word.
                continue
            spans.append((base + i, base + i + len(t["text"]),
                          f'<foreign index="{t["index"]}"/>'))
            pos = i + len(t["text"])
    return spans


def _entity_spans(full: str, taken: list[tuple[int, int, str]], ents: dict,
                  autos: dict) -> tuple[list[tuple[int, int, str]], list[dict]]:
    """Trigger hits over the block: the ones a rule may link, and the ones it may not.

    **Matched over the joined block, not per line**, because the printed line
    breaks fall inside the most reliable triggers — `1-021` sets "the Jesup North
    / Pacific Expedition" across two lines — and a matcher that stopped at a line
    end would miss exactly the multi-word forms that are unambiguous enough to
    link.

    A hit overlapping a Tier-1 handle is dropped rather than linked. Linking a
    Tier-1 form is the collator's act, after judging what language it is in;
    a rule that reached inside a handle would be resolving an identity for a
    string whose glyphs it is forbidden even to name.
    """
    from .entities import match

    links, candidates = [], []
    for h in match(full, ents):
        if any(h["start"] < e and s < h["end"] for s, e, _ in taken):
            continue
        owner = autos.get(h["form"])
        if owner:
            links.append((h["start"], h["end"],
                          f'<rs ref="{owner}" resp="#mz">', "</rs>"))
        else:
            candidates.append(h)
    return links, candidates


def _emit(full: str, spans: list, indent: str) -> str:
    """The block's text with its spans marked, printed line breaks preserved.

    **The printed line breaks are kept**, as the hand-collated pages keep them.
    They cost nothing — TEI collapses whitespace in prose — and they are what lets
    a reviewer read the file against the raster a line at a time, which is the
    comparison the whole pass is built on. A span that straddles one keeps it: the
    break is inside the element, where it belongs.
    """
    def wrap(s: str) -> str:
        return escape(s).replace("\n", f"\n{indent}")

    out, pos = [], 0
    for span in sorted(spans):
        start, end, open_ = span[0], span[1], span[2]
        if start < pos:
            continue                          # overlapping; first one wins
        out.append(wrap(full[pos:start]))
        if len(span) > 3:                     # a wrapper: text goes inside it
            out.append(open_ + wrap(full[start:end]) + span[3])
        else:                                 # an empty handle: text goes away
            out.append(open_)
        pos = end
    out.append(wrap(full[pos:]))
    return "".join(out)


def page_blocks(ref: str, root: Path = Path(".")
                ) -> tuple[list[tuple[dict | None, list[tuple[int, str]]]], str]:
    """The page's text in the blocks the rules read it as, plus what the split rested on.

    One entry per band, in order, each `(band, [(line index, joined text), …])`;
    the last entry's band is None and holds the lines inside no zone. Captions
    and empty lines are dropped, and each line's text is the *joined* one, so a
    word broken across two lines is whole on the first of them.

    **A block is the unit a trigger is matched over**, which is why this is one
    function and not two. The generator marks up a block at a time, so a trigger
    straddling a printed line break inside one — "the Jesup North / Pacific
    Expedition" on `1-021` — is found and linked; `tei context` reports the same
    hits to the reviewer, and if it derived its own text differently the table
    and the file would disagree about which questions are still open. They would
    disagree quietly, and in the direction that makes the file look finished.
    """
    ocr, _ = _inputs(ref, root)
    recs = page_lines(ocr, root, ref=ref)
    joined = join_broken_words(recs)
    text_of = {r["index"]: t for r, t in zip(recs, joined, strict=True)}
    bands, split_by = _bands(ref, root)
    buckets = _assign(recs, bands)

    def rows_of(bucket: list[dict]) -> list[tuple[int, str]]:
        out = []
        for r in bucket:
            if r.get("in_figdesc"):
                continue          # the project holds a human reading in readings.md
            text = text_of.get(r["index"], r.get("text") or "")
            if not text.strip():
                continue
            out.append((r["index"], text))
        return out

    out: list[tuple[dict | None, list[tuple[int, str]]]] = [
        (b, rows_of(k)) for b, k in zip(bands, buckets[:-1], strict=True)]
    out.append((None, rows_of(buckets[-1])))
    return out, split_by


def build(ref: str, root: Path = Path(".")) -> tuple[str, dict]:
    """The page's generated TEI, and a report of what the rules could and could not do."""
    ref = norm_ref(ref)
    _require(ref, root)
    ocr, _ = _inputs(ref, root)

    running = _running_title(page_lines(ocr, root, ref=ref), ref, root)
    blocks, split_by = page_blocks(ref, root)
    bands = [b for b, _ in blocks[:-1]]
    buckets = [rows for _, rows in blocks]

    by_line: dict[int, list[dict]] = {}
    for t in tier1_terms(ref, root):
        by_line.setdefault(t["line"], []).append(t)

    store = load(root)
    ents = trigger_index(store)
    autos = auto_forms(ents)
    pending: list[dict] = []          # candidates, to be commented after the block

    def rendered(rows: list[tuple[int, str]], indent: str = "") -> str:
        """One block of lines, marked up whole. Records its candidates in `pending`."""
        if not rows:
            return ""
        texts = [t for _, t in rows]
        offsets, at = [], 0
        for t in texts:
            offsets.append(at)
            at += len(t) + 1                  # +1 for the joining newline
        full = "\n".join(texts)
        spans = _tier1_spans(rows, by_line, offsets)
        links, cands = _entity_spans(full, spans, ents, autos)
        pending.extend(cands)
        return _emit(full, spans + links, indent)

    body: list[str] = []
    rep = {"ref": ref, "folio": None, "folio_from": "", "split_by": split_by,
           "paragraphs": 0, "quotes": 0, "notes": 0, "unresolved": 0,
           "handles": 0, "links": 0, "candidates": 0,
           "outside_zones": 0, "unknown_labels": ""}

    def flush_candidates() -> None:
        """One comment per distinct unlinked trigger, after the block it sits in.

        Every one is a question, in the same shape as every other question the
        generator leaves: the rules found something they are not allowed to
        resolve, and say so where a reader will meet it. Ambiguity is the usual
        reason — "Chukchee" is the people, the language and half a place-name —
        and the entry that is right is the one the sentence decides.
        """
        seen = set()
        for h in pending:
            key = (h["form"], tuple(h["ids"]))
            if key in seen:
                continue
            seen.add(key)
            rep["candidates"] += 1
            # The two reasons a hit is a candidate are different questions, so
            # they are different sentences. Ambiguous: several entities claim the
            # form and only the sentence decides. Uncontested but not automatic:
            # one entity claims it, and its author declared the form unsafe out
            # of context — the book uses it for other things too.
            if len(h["ids"]) > 1:
                say = (f'ambiguous — {escape(" or ".join(h["ids"]))}. Link the '
                       f'one this sentence means, or delete this comment if it '
                       f'means neither')
            else:
                say = (f'{escape(h["ids"][0])}, but the store marks this form '
                       f'`auto: no` — it means other things elsewhere in the '
                       f'book. Link it if the page means this one, or delete '
                       f'this comment')
            body.append(f'      <!-- entity candidate: {escape(h["form"])!r} '
                        f'— {say} -->')
        pending.clear()

    folio = (running or {}).get("folio")
    rep["folio"] = folio
    rep["folio_from"] = (running or {}).get("folio_from") or ""
    if folio is None:
        body.append('      <pb/>')
        body.append('      <!-- generator: no folio parsed from any of '
                    'RunningTitleZone, QuireMarksZone, NumberingZone. Read it off '
                    'the page and write @n, or say in your report that the page '
                    'prints none -->')
    else:
        body.append(f'      <pb n="{escape(str(folio))}"/>')

    # **No `opens:` is written here, deliberately.** It records what a reader saw on
    # the raster; a value derived from the zone label would be the same witness
    # twice. `validate` errors on the absence, which is the correct state — the
    # collator has the page open and the coordinator does not.
    # `buckets[:-1]` pairs with `bands` exactly — the last bucket is the lines
    # inside no band — so this is `strict=True` against the real invariant rather
    # than a waiver that would also accept the two drifting apart.
    first = next((b["label"] for b, k in zip(bands, buckets[:-1], strict=True)
                  if k and b["label"] in PROSE), "")
    if first:
        body.append(f'      <!-- zone-opens: '
                    f'{"continued" if first == "MainZone-Continued" else "fresh"} '
                    f'(from the zone label; the opens: witness above is yours, off '
                    f'the raster) -->')
    if split_by == "zones-only":
        body.append('      <!-- generator: no blotted raster, so paragraphs were '
                    'split at keyed zone boundaries only. A zone holding two '
                    'paragraphs is one <p> here — check the page -->')

    notes: list[str] = []
    unknown: set[str] = set()
    for band, bucket in zip(bands, buckets[:-1], strict=True):
        label = band["label"]
        if label in APPARATUS_ZONES:
            continue              # the printer's text; its folio is in <pb> above
        rows = bucket
        if not rows:
            continue
        if label == NOTES_ZONE:
            notes += rows
            continue
        if label in PROSE:
            tag = PROSE[label]
            if tag == "quote":
                rep["quotes"] += 1
                block = rendered(rows, "        ")
                body.append(f'      <quote>\n        <p>{block}'
                            f'</p>\n      </quote>')
            else:
                rep["paragraphs"] += 1
                body.append(f'      <p>{rendered(rows)}</p>')
        elif label == OTHER_ZONE:
            rep["unresolved"] += 1
            body.append('      <!-- unresolved zone (MainZone-Other): a heading, a '
                        'table, verse, or a caption — the store does not '
                        'distinguish them. Give it its real shape, and if it is a '
                        'heading check toc_window for a milestone -->')
            body.append(f'      <p>{rendered(rows)}</p>')
        else:
            unknown.add(label)
            body.append(f'      <!-- unknown zone label {label!r}: the generator '
                        f'has no rule for it, so its lines are here as prose -->')
            body.append(f'      <p>{rendered(rows)}</p>')
        flush_candidates()

    if notes:
        rep["notes"] = 1
        body.append('      <!-- the footnote apparatus, whole. MarginTextZone-Notes '
                    'is one zone for the page, so these are not split into '
                    'individual notes and none is anchored: which body marker each '
                    'belongs to is a reading. Split them, move each <note> to its '
                    'marker in the prose above, and set @n from the printed '
                    'marker -->')
        body.append(f'      <note place="bottom">{rendered(notes)}</note>')
        flush_candidates()

    if buckets[-1]:
        rep["outside_zones"] = len(buckets[-1])
        rows = buckets[-1]
        if rows:
            body.append(f'      <!-- {len(buckets[-1])} line(s) inside no zone. '
                        f'Usually artwork the segmenter raised a baseline on; '
                        f'occasionally a missing zone. Delete or place them -->')
            body.append(f'      <p>{rendered(rows)}</p>')
            flush_candidates()

    figs = _figures_on_page(ref, root)
    if figs:
        listed = "; ".join(f'{f["n"] or "?"}: {f["caption"][:60]}' for f in figs)
        body.append(f'      <!-- figures printed on this page — {escape(listed)}. '
                    f'Not anchored: a <figure n="N"/> goes where the prose first '
                    f'refers to it, which is a reading -->')
    rep["unknown_labels"] = ",".join(sorted(unknown))
    # Counted off the emitted markup rather than tallied as it is built: what the
    # file actually carries is the thing a reviewer meets, and a counter kept
    # alongside can disagree with it.
    doc_body = "\n".join(body)
    rep["handles"] = doc_body.count("<foreign index=")
    rep["links"] = doc_body.count('resp="#mz"')

    src = f"see corpus teiHeader; page {folio}" if folio is not None \
        else "see corpus teiHeader; folio not parsed"
    doc = (
        '<TEI xmlns="http://www.tei-c.org/ns/1.0">\n'
        f'  <!-- {_stamp(ref, root)} -->\n'
        '  <teiHeader>\n    <fileDesc>\n      <titleStmt>\n'
        '        <title>see corpus teiHeader</title>\n'
        '      </titleStmt>\n      <publicationStmt>\n'
        '        <p>see corpus teiHeader</p>\n'
        '      </publicationStmt>\n      <sourceDesc>\n'
        f'        <p>{escape(src)}</p>\n'
        '      </sourceDesc>\n    </fileDesc>\n  </teiHeader>\n'
        '  <text>\n    <body>\n'
        + "\n".join(body)
        + '\n    </body>\n  </text>\n</TEI>\n')
    return doc, rep


def generate(ref: str, root: Path = Path("."), force: bool = False) -> dict:
    """Build and write one page. Reports `written: False` where a baseline exists.

    **Not gated on `--commit`.** The conventions reserve that for the authored
    stores, and this writes `mz/`, which is derived: same inputs, same bytes, and
    regenerating costs a second. `zones predict` and `ocr predict` write their `mz/`
    stores the same way, and `--force` is the same guard against silently replacing
    one — here because a baseline a collator has already copied is the other half of
    a diff, and moving it under a review in progress makes that diff a lie.
    """
    ref = norm_ref(ref)
    out = gen_path(ref, root)
    if out.exists() and not force:
        return {**skipped(ref), "why": "a baseline exists; --force replaces it"}
    doc, rep = build(ref, root)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8")
    return {**rep, "written": True, "why": ""}


#: The comments the generator writes, by their opening words. Their *survival* in a
#: reviewed page is the measurement `diff` exists for: each one names a judgement
#: the rules could not make, so one still standing is a page not finished being
#: read. Matched on a prefix rather than in full — the bodies carry instructions
#: and will be reworded, and a check that broke when the prose was improved would
#: be a check nobody kept.
GEN_MARKS = ("generated:", "zone-opens:", "unresolved zone",
             "the footnote apparatus", "figures printed on this page",
             "line(s) inside no zone", "unknown zone label",
             "entity candidate")

#: The two that are *supposed* to survive review, and so are not counted as
#: questions left open. The stamp is the baseline's identity, and `zone-opens:` is
#: the second seam witness — `tei seam` reads it against the collator's `opens:`
#: after the batch, so a page that deleted it would have destroyed the comparison.
#: Counting them made a correctly finished page report an unanswered question,
#: which is the kind of standing false positive that teaches a reader to skip a
#: column.
SURVIVING = ("generated:", "zone-opens:")

TEI_NS = "http://www.tei-c.org/ns/1.0"


def _body_text(path: Path) -> str:
    from lxml import etree
    b = etree.parse(str(path)).getroot().find(f".//{{{TEI_NS}}}body")
    return " ".join("".join(b.itertext()).split()) if b is not None else ""


def _counts(path: Path) -> dict:
    """Element counts over the **body**, comments over the whole file.

    Scoped, because `<teiHeader>` carries two boilerplate `<p>`s that both files
    have and neither means — counting them made `1-021` report 9 paragraphs where
    the page sets 7, and a column whose baseline is a constant offset is a column
    read wrong at a glance. The stamp is deliberately outside the body, so comments
    are still gathered from the root.
    """
    from lxml import etree
    root = etree.parse(str(path)).getroot()
    body = root.find(f".//{{{TEI_NS}}}body")
    scope = body if body is not None else root
    n = {t: len(scope.findall(f".//{{{TEI_NS}}}{t}"))
         for t in ("p", "note", "figure", "name", "foreign", "milestone",
                   "quote", "list", "table")}
    comments = [(c.text or "").strip() for c in root.iter(etree.Comment)]
    n["stamp"] = next((c for c in comments if c.startswith("generated:")), "")
    n["gen_comments"] = sum(1 for c in comments
                            if c.startswith(GEN_MARKS) and
                            not c.startswith(SURVIVING))
    n["lang_less"] = len([e for e in scope.findall(f".//{{{TEI_NS}}}foreign")
                          if not e.get("{http://www.w3.org/XML/1998/namespace}lang")])
    return n


def diff(ref: str, root: Path = Path(".")) -> dict:
    """What review changed, per page. Measurement — this never gates.

    **The stamp is compared before anything else**, because a difference means two
    unrelated things and the report has to say which. If `mz/tei/` was regenerated
    after the collator copied it, the rows below are comparing a review against a
    baseline it never saw, and every count is noise. `drifted` says so; without it
    a regeneration would read as work somebody did.

    `gen_comments` is the row that answers "is this page finished". Each generator
    comment names a judgement the rules could not make — an unresolved zone, an
    unanchored note, an unplaced figure — so a reviewed page that still carries one
    has a question outstanding, whatever else changed. `lang_less` is the same
    measurement for the wraps and is also a `validate` error, so a page can only
    reach zero there by a reviewer having disposed of every one.
    """
    ref = norm_ref(ref)
    gen, rev = gen_path(ref, root), root / "tei" / f"chukchi-{ref}.xml"
    row = {"ref": ref, "baseline": gen.exists(), "reviewed": rev.exists(),
           "drifted": False, "text_same": False, "p": "", "note": "",
           "foreign": "", "name": "", "milestone": "", "gen_comments": 0,
           "lang_less": 0, "why": ""}
    if not gen.exists():
        return {**row, "why": "no baseline — `harness tei generate` never ran here"}
    if not rev.exists():
        g = _counts(gen)
        return {**row, "p": str(g["p"]), "gen_comments": g["gen_comments"],
                "lang_less": g["lang_less"], "why": "not collated yet"}

    g, t = _counts(gen), _counts(rev)
    # The live stamp, not the baseline's own: a baseline rebuilt from changed
    # ground truth carries a new digest, so comparing the file against itself would
    # always agree. What matters is whether the copy the reviewer took still
    # matches what the rules produce from today's stores.
    try:
        live = _stamp(ref, root)
    except FileNotFoundError:
        live = ""
    row["drifted"] = bool(live) and t["stamp"] not in ("", live)
    row["text_same"] = _body_text(gen) == _body_text(rev)
    for k in ("p", "note", "foreign", "name", "milestone"):
        row[k] = f"{g[k]}" if g[k] == t[k] else f"{g[k]}->{t[k]}"
    row["gen_comments"] = t["gen_comments"]
    row["lang_less"] = t["lang_less"]
    if row["drifted"]:
        row["why"] = ("baseline regenerated since review — the counts compare "
                      "against a file this page was not reviewed from")
    elif t["gen_comments"]:
        row["why"] = f"{t['gen_comments']} generator comment(s) still unanswered"
    return row


def skipped(ref: str, why: str = "") -> dict:
    """A row for a page nothing was written for, carrying the **whole** key set.

    `emit`'s tabular collapse degrades the entire table to the verbose nested form
    the moment one record's keys differ from its neighbours', so a short row for a
    skip would cost every other page in the sweep its shape. The empties are honest
    here besides: nothing was measured, and a blank is what "not measured" looks
    like beside a page where it was.
    """
    return {"ref": norm_ref(ref), "folio": None, "folio_from": "", "split_by": "",
            "paragraphs": 0, "quotes": 0, "notes": 0, "unresolved": 0,
            "handles": 0, "links": 0, "candidates": 0,
            "outside_zones": 0, "unknown_labels": "",
            "written": False, "why": why}
