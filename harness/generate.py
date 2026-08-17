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
`rank: null` says as much — nor what language a form is in, nor where a figure is
discussed. Every one of those leaves a comment naming itself, and the review
contract is the list of comments to clear.

**The line runs between what the printer marked and what a reader must decide**,
and the footnotes are where it moved. Splitting the apparatus at its superscripts
and anchoring each note at the same character in the body are *character
identity* — the compositor set both marks and the recognizer read both — so they
belong on this side of the line, and 241 of the corpus's 250 notes place that way.
The 9 that do not are the cases where the evidence is short: a marker that reads
nowhere in the prose, or reads in two places. Those stay at the foot saying which,
which is what a rule that will not guess looks like when it declines.

**Figures arrive placed, and the placement is final.** The box's position is real
evidence and puts the figure on the right part of the right page; the anchor the
edition wants — where the prose says "(Fig. 87, a)" — is a *link*, written by
`figrefs` at generation and resolved when the page is served. Those are two
different facts and both are now recorded, so the pass no longer asks a reader to
trade one for the other. Note that `context._figures_on_page` withholds geometry
from the *model* deliberately — placing a figure is not the collator's competence
— and this reads it anyway. Not an inconsistency: a rule cannot be talked into
anything by what it sees, so it may use what a model may not.

**`mz/tei/` is to `tei/` what `mz/zones/` is to `gt/zones/`**, and the pairing is
the point: the generated file stays on disk, so `harness tei diff` can say what
review changed. The collation pass had no baseline before, which made "did the
collator invent this?" an unanswerable question about every page it produced.

**The paragraphs are the keyed zones, and this reads no raster at all.**
`zones.paragraph_starts` measures first-line indents off the scan and used to *cut*
a keyed band it read as holding two paragraphs — a measurement adding structure
over a human's assertion, in a file that recorded no difference between the two,
and `1-160` is what that was worth: one speck of dirt in the gutter, 20 paragraphs
the keying never had. Reporting them here instead of cutting failed the same test
one level up. **Every finding that check makes is answered by editing `gt/zones/`**,
so it is a gate on the zone store and lives there, with its rulings in
`gt/zones/_para_exempt.json`; leaving it here gave a ruling nowhere to live and
made the generated page depend on a derived, untracked raster, so a fresh clone
built *different TEI* from identical stores. What is left is the property that was
wanted: a pure function of the tracked stores.

**The seam witness is not generated.** `<!-- opens: … -->` means what a reader saw
on the raster, and seeding it from the zone label would leave `tei seam` comparing
a value with itself — the one-witness collapse, in the one place the project has
already paid for it twice. The generator writes `<!-- zone-opens: … -->` instead,
which is the *other* witness, and the missing `opens:` is a validate error the
collator clears by looking at the page.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from xml.sax.saxutils import escape

from . import apparatus, citations, figrefs
from .context import (
    APPARATUS_ZONES,
    _running_title,
    norm_ref,
    tier1_terms,
)
from .detectors import join_broken_words
from .entities import alias_index, auto_forms, load
from .lines import page_lines
from .zones import read_zones

#: Bumped when the emitted shape changes in a way that makes an older file a
#: different artifact rather than an older copy of the same one. It rides in the
#: stamp, so `tei diff` can say "this baseline predates the current rules" instead
#: of reporting the difference as something review did.
VERSION = 4

GENDIR = "mz/tei"

#: Zone labels that become body prose, and what each becomes. A label absent from
#: here is not prose and is handled by name below; a label absent from *both* is a
#: vocabulary change the generator has not been told about, and it says so rather
#: than guessing which side it belongs on.
PROSE = {"MainZone-P": "p", "MainZone-Continued": "p", "MainZone-Quote": "quote"}
NOTES_ZONE = "MarginTextZone-Notes"
OTHER_ZONE = "MainZone-Other"


#: The printed footnote markers. Superscript digits and nothing else: a census of
#: the generated corpus finds ¹–⁶ and no `*`, `†`, `‡` or `§` anywhere, so a rule
#: written for symbols would be a rule for a book other than this one.
NOTE_MARKERS = "⁰¹²³⁴⁵⁶⁷⁸⁹"

#: `@n` is the digit, not the raised glyph. Three reasons and they agree: the
#: collator contract has always specified an integer, `.noteref` raises and shrinks
#: whatever `@n` holds so a superscript character there is superscripted twice, and
#: the number is what a reader cites. Written out rather than reached through
#: `unicodedata.normalize("NFKC", …)`, which would do it — and which CLAUDE.md
#: forbids outright, because the same call destroys two inventory glyphs.
NOTE_N = {m: str(i) for i, m in enumerate(NOTE_MARKERS)}


def gen_dir(root: Path = Path(".")) -> Path:
    return root / GENDIR


def _split_notes(rows: list[tuple[int, str]]) \
        -> list[tuple[str, list[tuple[int, str]]]]:
    """`MarginTextZone-Notes` cut into the individual notes the printer set.

    **The marker is the printer's, not a guess.** Every note in this book opens
    with its own superscript — 148 of the corpus's 152 note blocks demonstrably
    so — which makes the cut mechanical and auditable: the character is either at
    the head of the line or it is not.

    A block that opens without one becomes a note with **no `@n`** rather than
    being folded into the note after it, because a marker nobody read is a
    question and folding would answer it.

    **Four blocks used to arrive that way and the recognizer was not to blame.**
    `1-075`, `1-091`, `1-203` and `1-243` each end their last body line on a
    broken word — `…the Kolyma west-` — and `join_broken_words` took the first
    token of the next non-empty line, which was the footnote below. The body got
    `Kolyma west-¹` and the note lost the marker off its head, so this function
    was handed a markerless block and said so. Two texts corrupted by one join,
    and the comment it produced sent a reader to look for a recognizer error that
    was not there. The join now refuses to cross a zone.
    """
    out: list[tuple[str, list[tuple[int, str]]]] = []
    for idx, text in rows:
        head = text.lstrip()
        if head and head[0] in NOTE_MARKERS:
            out.append((head[0], []))
        elif not out:
            out.append(("", []))
        out[-1][1].append((idx, text))
    return out


def _figures_with_geometry(ref: str, root: Path) -> list[dict]:
    """The page's figures — number, caption, and where the box sits — top first.

    **`_figures_on_page` deliberately drops geometry and this deliberately keeps
    it**, and the two are not in tension. That function builds the *model's*
    payload, where geometry is withheld on purpose: placing a figure is not the
    collator's competence, and handing it coordinates invites it to place one by
    eye instead of finding the sentence that says "(Fig. 87, a)". This is a rule
    reading a store a human keyed, which is the other half of the same design —
    the generator may use what the model may not, because a rule cannot be
    persuaded by what it sees.

    Deduped on the caption exactly as `_figures_on_page` dedupes, so the two
    pictures sharing fig. 253's caption are one figure here too. The survivor is
    the topmost, `paired` having sorted by position already.

    **That fold is `figures.figure_boxes`' now, and this keeps only the three
    fields the emitter uses.** It was written out here as well, and two copies of
    one rule is the shape this project treats as a defect: nothing held them
    together, so a change to either would have been invisible until a page came
    out wrong. What stays here is the projection, because the geometry that
    function also returns is exactly what a *placement* rule may read and the
    model may not — the asymmetry above, unchanged.
    """
    from .figures import figure_boxes
    return [{"n": f["n"], "caption": f["caption"], "y": f["y"]}
            for f in figure_boxes(ref, root)]


def _mark_notes(body: list[str], rows: list[tuple[int, str]], rendered) \
        -> tuple[int, int, list[tuple[str, str]]]:
    """Mark each printed footnote marker in the prose, and render the notes.

    Returns `(marked, refs, notes)` — how many distinct notes were referenced at
    least once, how many references were marked in all, and the notes themselves
    as `(n attribute, rendered text)` in printed order, for the caller to emit at
    the foot.

    **Nothing moves.** The note stays where the printer set it and the marker
    stays where the printer set *that*; what the rule adds is a `<ref>` over the
    marker, which is the same act as marking a cross-reference and carries the
    same `#mz`. This used to splice the `<note>` into the prose at its marker and
    delete the marker in the process, and three things followed from that one
    decision:

    - **A note could be referenced only once.** `1-147` and `1-226` print one
      note against two markers, and a spliced note has to pick one; the pass
      reported them as ambiguous — "which one anchors it is a reading" — when the
      reading is that both do.
    - **The body lost a character the ground-truth pass had adjudicated.** The
      superscript is inventory (`keying_spec.md` §2.10) and it was replaced by an
      element standing in for it, so the page's text and the page's markup said
      the same thing in two ways and only one of them was the print's.
    - **And downstream had to undo it.** `validate._figref_flat` put the marker
      back before re-scanning a block, character for character, so the string it
      read matched the string the rule had read. That reinsertion goes with this.

    A marker outside a figure's locant run is a reference, which is what §2.10
    settles corpus-wide; `_marker_sites` holds the exclusion. A note whose head
    carries no marker is emitted with no `@n` and a comment, as before — that is
    a question about the page and not about anchoring.
    """
    parts = _split_notes(rows)
    notes: list[tuple[str, str]] = []
    edits: dict[int, list[tuple[int, int, str]]] = {}
    marked = refs = 0
    for marker, note_rows in parts:
        text = rendered(note_rows)
        # The marker comes off the *note's* head, where `@n` records it and the
        # renderer draws it from — it would otherwise be set twice at the foot.
        # It stays in the body, which is the one place the print puts it as part
        # of a sentence. Stripped from the rendered string rather than the row,
        # because the Tier-1 spans are offsets into the row's own text.
        if marker and text.startswith(marker):
            text = text[len(marker):].lstrip()
        if not marker:
            notes.append(("", text))
            continue
        n = NOTE_N[marker]
        notes.append((n, text))
        sites = _marker_sites(body, marker)
        if sites:
            marked += 1
            refs += len(sites)
        for i, at in sites:
            edits.setdefault(i, []).append(
                (at - len(marker), at,
                 f'<ref type="note" n="{n}" resp="#mz">{marker}</ref>'))
    # Back to front within each block, so an earlier edit cannot move a later
    # one's offsets — the same discipline the splice needed, for the same reason.
    for i, per_block in edits.items():
        for start, end, element in sorted(per_block, reverse=True):
            body[i] = body[i][:start] + element + body[i][end:]
    return marked, refs, notes


def _marker_sites(body: list[str], marker: str) -> list[tuple[int, int]]:
    """Where this marker occurs in the prose already emitted: `(block, offset)`,
    the offset being just past the character.

    Comments are skipped, and that is not tidiness — the generator's own comments
    quote page text, so a marker inside one would count as an anchor and the note
    would be spliced into a comment, where it is both invisible and unparseable.

    Figures are skipped for a different reason. A `<figDesc>` is caption text
    transcluded from `data/readings.md`, a store this file does not author; a note
    anchoring inside one would splice this page's apparatus into another store's
    text. **No caption in the corpus carries a superscript today**, so the guard
    catches nothing — it is here because `readings.md` is hand-edited and the
    failure would be silent, not because anything has gone wrong.
    """
    out = []
    for i, block in enumerate(body):
        head = block.lstrip()
        if head.startswith("<!--") or head.startswith("<figure"):
            continue
        skip = _locant_spans(block)
        at = block.find(marker)
        while at != -1:
            if not any(a <= at < b for a, b in skip):
                out.append((i, at + len(marker)))
            at = block.find(marker, at + 1)
    return out


#: A figure reference as this file has just written it. Matched on the emitted
#: markup rather than on the plain text because that is where `_marker_sites`
#: looks: the body strings already carry their `<ref>`s, and a plain-text offset
#: would have moved under every element inserted before it.
_FIG_REF = re.compile(r'<ref type="figure"[^>]*>\d+</ref>')


def _locant_spans(block: str) -> list[tuple[int, int]]:
    """Where this block's figure **sub-part locants** sit: `(start, end)` pairs.

    **A raised numeral after a figure number is not a footnote marker.**
    `1-285` prints `(Fig. 155, d², e¹)`, `(Fig. 155, d³)` and `(Fig. 155, a²,
    c²)`, and every one of those superscripts was counted as a reference to a
    note — four places reading `²` on a page setting one real marker, three
    reading `¹` where there is one, and the pass reported all three notes as
    ambiguous and anchored none of them.

    `keying_spec.md` §2.10 already excludes a locant, and bounds it textually:
    "a lone letter carries the superscript and a close-paren follows". That is
    true of `e¹` and false of `d²` in the same parenthesis, so the rule caught
    the last member of a run and missed every earlier one. Here the bound is
    structural — the run is whatever `figrefs.LOCANTS` consumes after a figure
    reference, which is the same pattern that decided where the reference ended —
    so a comma-separated list is no harder than a single letter.

    Nothing is guessed at. A superscript outside a locant run is a marker, which
    is what §2.10 settles corpus-wide, and this only says where the runs are.
    """
    spans = []
    for m in _FIG_REF.finditer(block):
        tail = figrefs.LOCANTS.match(block, m.end())
        if tail is not None and tail.end() > m.end():
            spans.append((m.end(), tail.end()))
    return spans


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


def _bands(ref: str, root: Path) -> list[dict]:
    """The page's zones as a human keyed them, uncut.

    **The paragraphs are the keyed zones and this module reads no raster.** They
    used to be cut further by `split_at_paragraphs`, which measures first-line
    indents off the scan — a good rule, 96.8% against this store, running in the
    one place it is not needed. `_require` refuses a page without `gt/zones/`, so
    the boundary the measurement exists to recover is never missing here: a human
    drew it, and the store's 561 abutting pairs are what that looks like. What the
    measurement added instead were boundaries the human did not key, on its own
    authority, into a file that records no difference between the two — one speck
    of dirt in `1-160`'s gutter was worth 20 of them.

    Reporting them here instead of cutting was the next wrong answer, and it failed
    the same test one level up. **Every finding the check makes is answered by
    editing `gt/zones/`** — the three real ones it found were fixed there, not in
    any TEI — so it is a gate on the zone store, `harness zones paragraphs` runs
    it, and `gt/zones/_para_exempt.json` records the rulings. Leaving it here left
    a ruling nowhere to live, so the same questions returned on every regeneration;
    and it made the generated page depend on a derived, untracked raster, so a
    fresh clone produced *different TEI* from identical stores.

    What is left is the property that was wanted all along: this module is a pure
    function of the tracked stores.
    """
    return read_zones(ref, root)


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
                 offsets: list[int]) -> list[tuple[int, int, str, str]]:
    """Ratified Tier-1 tokens, as spans over the block's joined text.

    The wrap is `<foreign index="N">Uweˊlen</foreign>` — **the ratified text in
    place**, carrying no `xml:lang`, because which language a form is in is a
    judgement and this is a rule. `tier1_terms` is a floor over inventory marks
    with no language awareness, so it catches an ordinary German surname carrying
    a combining diaeresis exactly as it catches a Chukchee form; `Döring` on
    `1-022` is the standing case. A generator that named a language would be
    inferring one from the shape of a word, which is the firewall's failure mode
    one category over from glyphs.

    So the wrap says only "a ratified token sits here", and the gate refuses a
    lang-less `<foreign>` — which turns every one into a question the reviewer has
    to answer: name the language, or unwrap it because it was never a foreign form.

    **The handle used to be empty**, and that was right when the collation pass
    authored the whole file from a plaintext draft: a model that never typed the
    glyphs could not corrupt them, and `tei expand` filled them in from `gt/ocr/`
    afterwards. That argument died when the generator started writing the file.
    A rule copies these characters exactly as it copies every other character on
    the page, so putting them in costs nothing in fidelity — while leaving them
    out cost the reviewer a lookup from `index="7"` to `tier1_terms[7]` *before it
    could judge the language*, which is a judgement about a word it cannot see.
    `1-032` is what that costs when `tei context` is unavailable: fourteen
    numbered blanks, and a collator that went to the raster to find out what they
    said.

    `@index` stays, and is what `tei expand` verifies the text against before
    stamping `#gt`. Located per line and then translated to block offsets, rather
    than searched for in the joined block: `tier1_terms` reports which line it
    found a token on, and a token occurring on two lines would otherwise resolve
    to the first both times.
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
                          f'<foreign index="{t["index"]}">', "</foreign>"))
            pos = i + len(t["text"])
    return spans


def _cited_owner(h: dict, full: str, sigla: list[dict], store: dict) -> str | None:
    """The work an ambiguous name means where the page *cites* it, or None.

    **The printed citation form is the second witness the alias table has not
    got.** `Nelson` is claimed by `person:nelson` and `source:nelson-1899`, so
    `auto_forms` withholds a link and the generator asks — correctly, since the
    name alone does not say which. A page locator attached to it does:
    `Nelson, pp. 27, 28` is the book, `Nelson. Fig. 22, b, shows a sled` is the
    man, and `citations.cited` refuses the second.

    **It chooses among the store's own claims and never adds one.** The work has
    to be an entity that already claims this form — every siglum in `Authorities
    Quoted` is claimed by its `source:` entry, so this costs nothing and keeps
    the alias table the gate on what a string may name. Two human-keyed tables
    have to agree before anything is written: the printed sigla, and the
    `authority:` on the entry.
    """
    key = citations.cited(h["form"], full[h["end"]:h["end"] + 80], sigla)
    if not key:
        return None
    work = citations.work_of(key, store)
    return work if work and work in h["ids"] else None


def _entity_spans(full: str, taken: list[tuple], ents: dict, autos: dict,
                  sigla: list[dict], store: dict, once: set[str]
                  ) -> tuple[list[tuple], list[tuple], list[dict]]:
    """Trigger hits over the block: the ones a rule may link, and the ones it may not.

    Returns `(tier1, links, candidates)` — the Tier-1 spans back, because a hit
    that coincides with one is expressed by rewriting that span rather than by
    adding a second one beside it.

    **Matched over the joined block, not per line**, because the printed line
    breaks fall inside the most reliable aliases — `1-021` sets "the Jesup North
    / Pacific Expedition" across two lines — and a matcher that stopped at a line
    end would miss exactly the multi-word forms that are unambiguous enough to
    link.

    **A hit that merely overlaps a Tier-1 handle is dropped; one that exactly
    coincides with it is wrapped.** The rule this used to state — that a rule
    linking a Tier-1 form "would be resolving an identity for a string whose
    glyphs it is forbidden even to name" — holds for *reaching inside* a handle
    and not for *enclosing* one:

        <rs ref="place:uelen" resp="#mz"
          ><foreign index="7">Uweˊlen</foreign></rs>

    Each `@resp` is a claim about its own element. The outer says which entity
    this string names, which is the alias table's judgement applied by rule;
    the inner says a ratified token sits here, and still carries no `xml:lang`,
    so the collator's question is untouched and `tei expand` still stamps `#gt`
    on the element that holds the glyphs. `validate`'s rule that `#mz` "is
    confined to `@ref` on `<rs>`, and never carries a glyph" is honoured
    literally: the element carrying `#mz` has no text of its own.

    **An alias that wholly contains a handle encloses it**, on the same argument
    one further step. `water:kolyuchin-bay` carries `Kuluˊči Bay`, which reaches
    over the handle `Kuluˊči` and two ASCII characters more:

        <rs ref="water:kolyuchin-bay" resp="#mz"
          ><foreign index="2">Kuluˊči</foreign> Bay</rs>

    Containment is decidable without an opinion — the handle's *both* ends are
    inside the alias — which is what a partial overlap is not, and it is the
    shape every double-duty toponym in this book takes: a bay, a cape or an
    island named off a village, in English, around the village's own form. The
    extra text is required to be ASCII, so the `#mz` element still carries no
    glyph a rule would be originating; the inner `<foreign>` is untouched and
    keeps its own rank.

    **A partial overlap is still refused, and now says so.** Nothing may pick
    where the form ends. It used to be dropped in silence, which cost the page
    the shorter alias's link too — `match` is non-overlapping, so the longer
    hit had already taken the span — leaving neither a link nor a question.

    **`once` spends its link on the page's first occurrence, and every later one
    goes bare *and silent*.** `once` is a set the caller owns for the length of
    the page — this function marks up one block at a time and the convention is
    per page, not per paragraph — and which hits it admits is
    `entities.rule_links`' decision rather than this function's, so that the
    placer here and the re-deriver in `validate` cannot drift apart. A spent hit
    is skipped whole: not linked, and not recorded as a candidate either, since
    a comment on the fourth `Chukchee` of a page is precisely the interruption
    `once` exists to remove. It is skipped before the straddle test too, so a
    later occurrence that also straddles a handle asks nothing — the question
    was already put where the link is.
    """
    from .entities import match, rule_links

    by_bounds = {(s[0], s[1]): i for i, s in enumerate(taken)}
    tier1 = list(taken)
    links, candidates = [], []
    hits = match(full, ents)
    allowed = {(h["start"], h["end"]) for h in rule_links(hits, autos, once)}
    for h in hits:
        at = by_bounds.get((h["start"], h["end"]))
        owner = None if h["hyphenated"] else autos.get(h["form"])
        if (owner is not None and h["scope"] == "first"
                and (h["start"], h["end"]) not in allowed):
            continue
        if owner is None and not h["hyphenated"]:
            owner = _cited_owner(h, full, sigla, store)
        over = [s for s in taken if h["start"] < s[1] and s[0] < h["end"]]
        if at is None and over:
            held = all(h["start"] <= s[0] and s[1] <= h["end"] for s in over)
            rest = full[h["start"]:h["end"]]
            for s in sorted(over, reverse=True):
                rest = rest[:s[0] - h["start"]] + rest[s[1] - h["start"]:]
            if not (held and rest.isascii()):
                candidates.append(dict(h, straddles=True))
                continue
            if owner:
                links.append((h["start"], h["end"],
                              f'<rs ref="{owner}" resp="#mz">', "</rs>"))
                continue
        if not owner:
            candidates.append(h)
            continue
        if at is None:
            links.append((h["start"], h["end"],
                          f'<rs ref="{owner}" resp="#mz">', "</rs>"))
            continue
        start, end, open_, close = tier1[at]
        tier1[at] = (start, end, f'<rs ref="{owner}" resp="#mz">{open_}',
                     f"{close}</rs>")
    return tier1, links, candidates


def _figref_spans(full: str, names: set[str]) -> list[tuple]:
    """The block's cross-references, marked where a rule may mark them.

    **This is the same class of act as an entity link and is recorded the same
    way.** A rule reads a printed string, applies a table a human keyed, and
    stamps `#mz` on what it wrote; `validate` re-derives every one of them from
    the page's own text on every run, so a mark whose text was edited afterwards
    fails rather than going stale. It used to happen in the renderer instead,
    where the collator could not see it and nothing checked it — the whole reason
    for moving it here.

    **Another author's plate is not marked at all.** Bogoras cites Nelson,
    Murdoch and Sauer by plate number in his footnotes, in the words he uses for
    his own, and `Sauer, Plate XIV` collides with this book's Plate XIV outright.
    Refusing is the safe direction and it belongs here rather than downstream: a
    mark the edition is bound to decline is a question put to the collator that
    the store had already answered.

    `before` is the block up to the reference, which is where the citing name
    stands — `Murdoch, Eskimo Bows, Plate X, Fig. 27` is one footnote, and the
    guard reads 160 characters back.
    """
    out = []
    for span in figrefs.scan(full):
        if figrefs.foreign_citation(full[:span["start"]], names):
            continue
        out.append((span["start"], span["end"],
                    f'<ref{figrefs.mark(span)} resp="#mz">', "</ref>"))
    return out


def _emit(full: str, spans: list, indent: str) -> str:
    """The block's text with its spans marked, printed line breaks preserved.

    **The printed line breaks are kept**, as the hand-collated pages keep them.
    They cost nothing — TEI collapses whitespace in prose — and they are what lets
    a reviewer read the file against the raster a line at a time, which is the
    comparison the whole pass is built on. A span that straddles one keeps it: the
    break is inside the element, where it belongs.

    **Containment nests; anything else is still first-one-wins.** A span wholly
    inside another is rendered inside it, because that is the one relation where
    both can hold at once — an entity reference around a Tier-1 handle. A partial
    overlap stays undecidable and the earlier span keeps the text.
    """
    def wrap(s: str) -> str:
        return escape(s).replace("\n", f"\n{indent}")

    # Outermost first where two spans start together, so the container is the one
    # that claims the text and the contained one renders inside it.
    ordered = sorted(spans, key=lambda s: (s[0], -(s[1] - s[0])))

    def render(items: list, lo: int, hi: int) -> str:
        out, pos, i = [], lo, 0
        while i < len(items):
            span = items[i]
            start, end, open_ = span[0], span[1], span[2]
            if start < pos:                   # overlapping; first one wins
                i += 1
                continue
            out.append(wrap(full[pos:start]))
            held, j = [], i + 1
            while j < len(items) and items[j][0] < end:
                if items[j][1] <= end:
                    held.append(items[j])
                j += 1
            if len(span) > 3:                 # a wrapper: text goes inside it
                out.append(open_ + render(held, start, end) + span[3])
            else:                             # an empty handle: text goes away
                out.append(open_)
            pos, i = end, j
        out.append(wrap(full[pos:hi]))
        return "".join(out)

    return render(ordered, 0, len(full))


def page_blocks(ref: str, root: Path = Path(".")
                ) -> list[tuple[dict | None, list[tuple[int, str]]]]:
    """The page's text in the blocks the rules read it as.

    One entry per band, in order, each `(band, [(line index, joined text), …])`;
    the last entry's band is None and holds the lines inside no zone. Captions
    and empty lines are dropped, and each line's text is the *joined* one, so a
    word broken across two lines is whole on the first of them.

    **A block is the unit an alias is matched over**, which is why this is one
    function and not two. The generator marks up a block at a time, so an alias
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
    bands = _bands(ref, root)
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
    return out


def build(ref: str, root: Path = Path(".")) -> tuple[str, dict]:
    """The page's generated TEI, and a report of what the rules could and could not do."""
    ref = norm_ref(ref)
    _require(ref, root)
    ocr, _ = _inputs(ref, root)

    running = _running_title(page_lines(ocr, root, ref=ref), ref, root)
    blocks = page_blocks(ref, root)
    bands = [b for b, _ in blocks[:-1]]
    buckets = [rows for _, rows in blocks]

    by_line: dict[int, list[dict]] = {}
    for t in tier1_terms(ref, root):
        by_line.setdefault(t["line"], []).append(t)

    store = load(root)
    ents = alias_index(store)
    autos = auto_forms(ents)
    cited = apparatus.authority_names(root)
    # The printed resolution table: `(name, volume, short title)` → work, which is
    # what the List of Authorities Quoted *is*. Loaded once per page, beside the
    # names the figure guard reads out of the same store.
    sigla = apparatus.sigla(root)
    pending: list[dict] = []          # candidates, to be commented after the block
    # **Which `once` forms this page has already spent its link on.** Page-scoped
    # because the convention is, and mutable across `rendered` calls because a
    # block is not the unit. That makes placement order-dependent, which is safe
    # only because `rendered` is called in reading order: the band loop walks the
    # page top to bottom, and the footnotes go through `_mark_notes` afterwards,
    # which is where the print puts them too.
    once: set[str] = set()

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
        spans, links, cands = _entity_spans(full, spans, ents, autos,
                                            sigla, store, once)
        pending.extend(cands)
        return _emit(full, spans + links + _figref_spans(full, cited), indent)

    body: list[str] = []
    # Every key present from the start, `figures` and `notes_anchored` included:
    # they are filled conditionally below, and a page with no notes would
    # otherwise return a row one key short — which collapses the whole sweep's
    # table to the nested form (`skipped`, same argument).
    rep = {"ref": ref, "folio": None, "folio_from": "",
           "paragraphs": 0, "quotes": 0, "notes": 0, "unresolved": 0,
           "handles": 0, "links": 0, "figrefs": 0, "candidates": 0,
           "outside_zones": 0, "unknown_labels": "",
           "figures": 0, "notes_anchored": 0, "noterefs": 0}

    def flush_candidates() -> None:
        """One comment per distinct unlinked alias, after the block it sits in.

        Every one is a question, in the same shape as every other question the
        generator leaves: the rules found something they are not allowed to
        resolve, and say so where a reader will meet it. Ambiguity is the usual
        reason — "Chukchee" is the people, the language and half a place-name —
        and the entry that is right is the one the sentence decides.
        """
        seen = set()
        for h in pending:
            key = (h["form"], h["hyphenated"], h.get("straddles", False),
                   tuple(h["ids"]))
            if key in seen:
                continue
            # Keyed on the page's spelling too, so `Chukchee` and `Chuk-chee` in
            # one block are two questions — they are.
            seen.add(key)
            rep["candidates"] += 1
            # The two reasons a hit is a candidate are different questions, so
            # they are different sentences. Ambiguous: several entities claim the
            # form and only the sentence decides. Uncontested but not automatic:
            # one entity claims it, and its author declared the form unsafe out
            # of context — the book uses it for other things too.
            if h["hyphenated"]:
                say = (f'{escape(h["ids"][0] if len(h["ids"]) == 1 else " or ".join(h["ids"]))}'
                       f', spelt with a hyphen the store does not have — the '
                       f'compositor broke the word across a line and the join '
                       f'keeps its hyphen, since nothing can tell that hyphen '
                       f'from the word\'s own. Read the page: if the break is the '
                       f'printer\'s, link it; if the hyphen is really there, say '
                       f'so and leave it unlinked')
            elif h.get("straddles"):
                say = (f'{escape(h["ids"][0] if len(h["ids"]) == 1 else " or ".join(h["ids"]))}'
                       f', but the form straddles a Tier-1 handle without '
                       f'matching it — no rule may say where the name ends. '
                       f'Link it around the handle if the page means this one, '
                       f'or delete this comment')
            elif len(h["ids"]) > 1:
                say = (f'ambiguous — {escape(" or ".join(h["ids"]))}. Link the '
                       f'one this sentence means, or delete this comment if it '
                       f'means neither')
            elif h["auto"] and h["status"] != "ratified":
                # `auto_forms` withholds a link for three reasons and the reader
                # can act on only one of them at a time. Saying `auto: no` when
                # the author wrote `auto: yes` sends them to edit a field that
                # is already right.
                say = (f'{escape(h["ids"][0])}, whose entry is still '
                       f'`{escape(h["status"])}` — a rule may not link an '
                       f'unaudited entry. Link it if the page means this one; '
                       f'`harness entity ratify {escape(h["ids"][0])}` is what '
                       f'lets the rule do it everywhere else')
            else:
                say = (f'{escape(h["ids"][0])}, but the store marks this form '
                       f'`auto: no` — it means other things elsewhere in the '
                       f'book. Link it if the page means this one, or delete '
                       f'this comment')
            shown = " ".join(h["text"].split()) if h["hyphenated"] else h["form"]
            body.append(f'      <!-- entity candidate: {escape(shown)!r} '
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
    notes: list[str] = []
    unknown: set[str] = set()

    #: Lines of the paragraph currently open across one or more bands.
    para: list[tuple[int, str]] = []

    figs = _figures_with_geometry(ref, root)
    rep["figures"] = len(figs)
    fig_at = 0
    at_y = 0
    #: The foot of the paragraph being accumulated. `at_y` is the top of the
    #: band in hand, which is the next paragraph's start and not this one's end.
    para_y1 = 0

    def emit_figures(before: int | None, at: int | None = None) -> None:
        """Emit the figures whose boxes sit above `before`, or all of them.

        **Placed at a paragraph boundary and never inside one**, which is the
        whole of the compromise here. The box's position is real evidence and it
        puts the figure on the right part of the right page; but a picture the
        text wraps around sits *inside* a paragraph, and splitting the prose at
        it would undo exactly what `MainZone-Continued` records.

        **So a figure the prose ran past goes at the top of that paragraph, not
        after it** — `at` is where the paragraph began, and the lines are spliced
        in there rather than appended. Both ends are a boundary and neither is
        the true anchor, so the question is which is the better draft, and the
        top wins for two reasons. A picture the text wraps around begins level
        with the paragraph's first lines and ends inside it, so the top is the
        nearer edge to where the page actually has it. And a reader meets the
        figure before the prose that discusses it rather than after, which is the
        order the book itself uses whenever the reference is forward-looking.

        **The placement stands, and used to be commented as a draft to move.**
        Every figure carried `<!-- … not where it belongs: anchor it where the
        prose first refers to it -->`, from a pass that placed figures nowhere in
        particular and had no other anchor to offer. It has one now: `figrefs`
        marks every printed "Fig. 87" as `<ref type="figure">` and the edition
        resolves it, so the reference is a link and the figure's position is
        typographic. Against that, moving it cost the one positional fact
        anybody has — and the prose that first names a figure is routinely on
        another page, so the instruction could not be followed where it was
        cited most confidently. 197 comments, one question, and the question was
        already answered elsewhere.
        """
        nonlocal fig_at
        out: list[str] = []
        while fig_at < len(figs) and (before is None or figs[fig_at]["y"] < before):
            f = figs[fig_at]
            fig_at += 1
            n = f["n"]
            if not n:
                # The one figure question left, and it is about the store rather
                # than the page: `1-037`'s caption ends "Fig. 1." and the number
                # never parsed, while `1-254`'s artwork prints none at all. Two
                # pages, and neither is fixable from here — `data/readings.md` is
                # off the collator's surface — so it asks for a report line.
                out.append(
                    '      <!-- figure with no number: data/readings.md parsed '
                    'none from this caption. Say in your report whether the page '
                    'prints one -->')
            attr = f' n="{escape(n)}"' if n else ""
            if f["caption"]:
                out.append(f'      <figure{attr}>\n'
                           f'        <figDesc>{escape(f["caption"])}</figDesc>\n'
                           f'      </figure>')
            else:
                # `3-006` and `3-007`: artwork the book captions nowhere. An empty
                # <figDesc> would assert a caption exists and read as one lost.
                out.append(f'      <figure{attr}/>')
        if not out:
            return
        if at is None:
            body.extend(out)
        else:
            body[at:at] = out

    def close_paragraph() -> None:
        """Emit whatever prose bands have accumulated as one `<p>`.

        **`MainZone-Continued` means "no paragraph opens here", and a `<p>` per
        band said the opposite.** The label is the human's assertion that these
        lines continue what came before, so a run of `P, Continued, Continued` is
        one paragraph and used to leave three, each break landing mid-sentence. The
        zone store held the right answer the whole time and the generator was
        throwing it away, which is the exact shape this module exists to avoid.

        Worth 15 paragraphs over the corpus, no more: 213 of the 228 `Continued`
        bands are the first body band on their page and still open a `<p>` here,
        having nothing above them to join. That is the common case and it is not
        what this fixes.

        Rendering the run whole rather than concatenating rendered bands also puts
        an alias that straddles a band boundary inside one call to `rendered`,
        so it is found and linked like any other — the same reason the block is
        marked up whole rather than line by line.
        """
        if not para:
            return
        rep["paragraphs"] += 1
        # Where this paragraph starts, so a figure it ran past can be spliced in
        # above it. Taken before the `<p>` is appended and before
        # `flush_candidates`, whose comments belong *after* the prose they are
        # about and must not be pushed below the figure.
        top = len(body)
        body.append(f'      <p>{rendered(para)}</p>')
        flush_candidates()
        para.clear()
        # **Against the paragraph's own bottom, not against the band that
        # happened to close it.** `at_y` is the top of whatever came *next*, and
        # for the last paragraph on a page nothing comes next — it is closed
        # after the loop with `at_y` still holding its own first band's y0. A
        # figure inside it then failed this test, fell through to the final
        # `emit_figures(None)`, and was appended at the very foot of the page:
        # `1-157` sets fig. 36 at y 1602 inside a band running 1393–3249 and put
        # it after the paragraph that wraps it. Tracking the bottom fixes the
        # last paragraph and changes nothing for the others, a paragraph's own
        # end being at or above the next one's start.
        emit_figures(para_y1, at=top)

    for band, bucket in zip(bands, buckets[:-1], strict=True):
        label = band["label"]
        at_y = band["y0"]
        if not para:
            emit_figures(at_y)
        if label in APPARATUS_ZONES:
            # The printer's text; its folio is in <pb> above. Deliberately does
            # not close an open paragraph: a running title is *around* the prose,
            # not in it, and a page whose head sits between two body bands must
            # not have its paragraph broken by it.
            continue
        rows = bucket
        if not rows:
            continue
        if label == NOTES_ZONE:
            notes += rows
            continue
        if label in PROSE:
            tag = PROSE[label]
            if tag == "quote":
                close_paragraph()
                rep["quotes"] += 1
                block = rendered(rows, "        ")
                body.append(f'      <quote>\n        <p>{block}'
                            f'</p>\n      </quote>')
            else:
                # **The keyed label, and nothing else, opens a paragraph.** A
                # measured indent used to be able to open one too, by having cut
                # this band in `_bands` — a rule adding structure on top of a
                # human's, which is the thing this module exists not to do. That
                # measurement is a gate on `gt/zones/` now and runs there.
                if label == "MainZone-P":
                    close_paragraph()
                para.extend(rows)
                # The foot of the prose accumulated so far, which is what a
                # figure inside this paragraph has to be measured against.
                para_y1 = band["y1"]
            continue
        close_paragraph()
        if label == OTHER_ZONE:
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

    close_paragraph()
    emit_figures(None)          # anything below the last band of prose

    if notes:
        # **Split at the printed marker, and the marker is marked where it
        # stands.** The zone is one band for the whole page, so the oldest shape
        # was every note in a single unanchored `<note>` — one marker at the foot
        # carrying three notes' text. The shape after that spliced each note into
        # the prose at its marker and deleted the marker; this marks the marker
        # and moves nothing.
        #
        # Both halves are mechanical and neither is a reading. A note begins
        # where the printer set its superscript; a reference is where the same
        # character stands in the prose, excluding a figure's locant run. The
        # compositor put every one of those marks there and the recognizer read
        # them, so what is left for a reviewer is whether the rule read them the
        # same way — which the text still says, because the characters are all
        # still in it.
        #
        # **A marker printed twice is two references to one note**, which is what
        # `1-147` and `1-226` do and what the splice could not express: it had to
        # choose, so it refused and called the page ambiguous instead.
        marked, refs, made = _mark_notes(body, notes, rendered)
        rep["notes"] = len(made)
        rep["notes_anchored"] = marked
        rep["noterefs"] = refs
        for n, text in made:
            if not n:
                body.append(
                    '      <!-- note (no marker): no marker at the head of this '
                    'note. Either the recognizer dropped it, or this is '
                    'foot-text running over from the previous page — which the '
                    'book does once or twice. Read the page: if it is a note, '
                    'set @n from its printed marker; if it is a continuation, '
                    'leave it here with no @n -->')
            body.append(f'      <note{f' n="{n}"' if n else ""} '
                        f'place="bottom">{text}</note>')
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

    rep["unknown_labels"] = ",".join(sorted(unknown))
    # Counted off the emitted markup rather than tallied as it is built: what the
    # file actually carries is the thing a reviewer meets, and a counter kept
    # alongside can disagree with it.
    doc_body = "\n".join(body)
    rep["handles"] = doc_body.count("<foreign index=")
    # Two things now carry `#mz` and they are two different acts, so they are
    # counted apart: `links` is the entity store applied to a name, `figrefs` the
    # printed cross-references marked. Counting the rank alone would have folded
    # them into one number that answers neither question.
    rep["links"] = doc_body.count('<rs ref=')
    rep["figrefs"] = doc_body.count("<ref type=")

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
             # Was "the footnote apparatus", one comment for the whole foot.
             # There is now one per note the generator would not place, and it
             # names which of the two refusals happened.
             "note ",
             # Was "figures printed on this page", a comment standing in for
             # figures that were not emitted at all; then one per figure, telling
             # a reader to move it to the first textual reference. Neither
             # survives: the figure is really there, and `<ref type="figure">`
             # is the anchor that instruction was reaching for. What is left
             # fires on 2 pages, and asks about the caption store.
             "figure with no number",
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
    return {"ref": norm_ref(ref), "folio": None, "folio_from": "",
            "paragraphs": 0, "quotes": 0, "notes": 0, "unresolved": 0,
            "handles": 0, "links": 0, "figrefs": 0, "candidates": 0,
            "outside_zones": 0, "unknown_labels": "",
            "figures": 0, "notes_anchored": 0, "noterefs": 0,
            "written": False, "why": why}
