"""Seam state — what is true at the boundary between two pages.

Everything here is *derived*. The per-page model asserts none of it; it reads a
folio off the image and emits milestones, and this module folds those committed
facts forward. Three seam facts, three producers, one table keyed by PP-NNN ref:

  folio        printed folio, from the committed TEI's <pb n>.
               None = page carries no printed folio (plate, blank, title).
  toc_window   the ToC entries *surrounding* this page's folio, each marked
               open / starts-here — a neighbourhood, not a resolution.
  boundary     whether an element runs across the gap *after* this page, read
               off the committed TEI: the last top-level body element carries
               `@part` of I or M, or carries `@next`. Written by `harness tei seam`
               from the page on the far side of the gap, which is the only one
               holding both witnesses.

               Three states. A mark says "open". Absence of a mark says nothing
               on its own, so it resolves by whether the *next* page is collated:
               if it is, that pass had both witnesses and its silence is the
               `--fresh` verdict ("closed"); if it is not, nothing has been in a
               position to look ("unknown").

The folio is the reason this exists. NNN is a scan index, not a folio, and the
two are not derivable from each other (see context.py); so the only way to know
what folio a scan carries is that someone read it off the page. Once read and
committed, it predicts its successor's folio, and that prediction is what makes
a drifting folio visible instead of silent.

Two neighbourhood lookups live here for the same reason, though neither is a seam
fact: `toc_search` (ToC entries whose title matches a heading read off a page)
and `foreign_terms_nearby` (foreign spans committed on the physically adjacent
pages). Both are recomputed from committed evidence on every call and both are
strictly read-only reference — `foreign_terms_nearby` in particular is for
*seeing* a term keyed two ways, never for harmonizing one to the other.

Why a window rather than a resolved set of open headings: the folio keying it is
itself a prediction, and the fold that marks entries `open` inherits every error
upstream of it. A neighbourhood with marks degrades honestly — a wrong mark next
to visible neighbours is correctable by looking at the page, where a wrong
resolved set is just an answer. Marks inform; they do not decide.
"""
from __future__ import annotations
import json
import re
import unicodedata
from pathlib import Path
from lxml import etree

TEI_NS = "http://www.tei-c.org/ns/1.0"

# Folios either side of the target included in the window. Wide enough that a
# folio off by one or two still lands inside its true neighbourhood.
WINDOW = 4

# Scans either side of the target searched for already-transcribed foreign
# terms. A neighbourhood in *scan* order, not folio order: it is a physical
# proximity question (did the facing page key this word differently?), and the
# folio may not be known for either page.
NEARBY = 5


def _tei_facts(tei_path: Path) -> dict | None:
    """(folio, milestone ids) from one committed TEI page file.

    Returns None if the file doesn't exist or has no <pb> — i.e. the page has
    not been transcribed, which is distinct from a page transcribed as
    unpaginated.
    """
    if not tei_path.exists():
        return None
    try:
        tree = etree.parse(str(tei_path))
    except (etree.XMLSyntaxError, OSError):
        return None
    pb = tree.find(f".//{{{TEI_NS}}}pb")
    if pb is None:
        return None
    n = pb.get("n")
    # The gap *after* this page, read off the page's own last top-level element.
    # Two spellings, because TEI's att.fragmentable covers <p> and <quote> but not
    # <list>/<table>: a fragmentable element left open carries @part of I or M, a
    # non-fragmentable one carries @next at its link. Testing only @part would
    # report a page ending in a run-on list as a clean break — which is exactly
    # what 1-100 is not.
    from .seam import body_elements
    els = body_elements(tree.getroot())
    last = els[-1] if els else None
    open_after = last is not None and (
        last.get("part") in ("I", "M") or last.get("next") is not None)
    return {
        "folio": int(n) if n is not None and n.isdigit() else None,
        "folio_raw": n,
        "marked_open": open_after,
        "milestones": [ms.get("n") for ms in tree.iter(f"{{{TEI_NS}}}milestone")
                       if ms.get("n")],
    }


def _apply_milestones(open_h: dict[int, str], ids: list[str],
                      levels: dict[str, int]) -> dict[int, str]:
    """Fold a page's milestones into the believed-open heading set.

    A heading at level L closes everything deeper than L. Ids absent from the
    ToC are ignored here — the validator is what rejects them.
    """
    out = dict(open_h)
    for mid in ids:
        lvl = levels.get(mid)
        if lvl is None:
            continue
        out[lvl] = mid
        for deeper in [k for k in out if k > lvl]:
            del out[deeper]
    return out


def toc_window(toc: list[dict], folio: int | None, open_ids: list[str],
               span: int = WINDOW) -> list[dict]:
    """ToC entries surrounding `folio`, each marked rather than filtered.

    Membership is the union of two weak signals, neither trusted alone:
      - entries whose page_start falls within `span` folios of the target
      - entries the milestone fold believes open here (`open_ids`)

    A believed-open entry far from the window still appears, because that
    distance is exactly the discrepancy worth seeing. Marks:
      open        the fold believes this heading is open at this page
      starts_here page_start equals the target folio exactly
      distance    page_start - folio, or None when the folio is unknown
    """
    open_set = set(open_ids)
    out = []
    for e in toc:
        ps = e.get("page_start")
        near = folio is not None and ps is not None and abs(ps - folio) <= span
        if not (near or e.get("id") in open_set):
            continue
        out.append({
            "id": e.get("id"),
            "level": e.get("level"),
            "title": e.get("title"),
            "page_start": ps,
            "open": e.get("id") in open_set,
            "starts_here": folio is not None and ps == folio,
            "distance": (ps - folio) if (folio is not None and ps is not None) else None,
        })
    return sorted(out, key=lambda e: (e["page_start"] if e["page_start"] is not None
                                      else 10**9, e["level"] or 0))


def build_ledger(root: Path = Path(".")) -> dict[str, dict]:
    """Fold every committed TEI page into a per-ref seam record.

    Refs are folded in (part, scan index) order; the fold restarts at each part
    boundary, since heading state does not carry across a physical volume.
    """
    from .context import all_scans, parse_ref, stem_for

    toc = load_toc(root)
    levels = {e["id"]: e.get("level", 0) for e in toc if e.get("id")}

    ledger: dict[str, dict] = {}
    open_h: dict[int, str] = {}
    prev_part = None

    for ref in all_scans(root):
        part, _ = parse_ref(ref)
        if part != prev_part:
            open_h = {}
            prev_part = part
        facts = _tei_facts(root / "tei" / f"{stem_for(ref, root)}.xml")
        entry = [open_h[k] for k in sorted(open_h)]
        if facts is not None:
            open_h = _apply_milestones(open_h, facts["milestones"], levels)
        ledger[ref] = {
            "folio": facts["folio"] if facts else None,
            "transcribed": facts is not None,
            "open_in": entry,
            "open_out": [open_h[k] for k in sorted(open_h)],
            "marked_open": bool(facts and facts["marked_open"]),
        }

    # Three states, not two, and the third is the one that matters.
    #
    # A mark says "open". *Absence* of a mark says nothing by itself — it is
    # equally "a human ruled this a clean break" and "nobody has looked", and
    # collapsing those two into "closed" would put a verdict nobody made into the
    # ledger. That is the same defect as a zone page saved with nothing on it,
    # where an empty save erased the difference between having made a judgement
    # and not; see CLAUDE.md on `exempt`.
    #
    # What separates them here is *who could have written it*. A seam is recorded
    # by the page after the gap, and `harness tei seam` refuses unless the predecessor
    # is collated too — so a gap is adjudicable only when **both** its pages exist.
    # Until then nothing has been in a position to look, and the honest answer is
    # "unknown". Once both exist, the pass had both witnesses in front of it and
    # the absence of a mark is its `--fresh` verdict.
    for ref, row in ledger.items():
        nxt = _next_scan(ref, ledger)
        adjudicable = row["transcribed"] and nxt and ledger[nxt]["transcribed"]
        row["boundary"] = (
            "open" if row["marked_open"]
            else "closed" if adjudicable
            else "unknown")
        del row["marked_open"]
    return ledger


def _next_scan(ref: str, ledger: dict) -> str | None:
    """The following scan in the same part. Gaps never cross a part boundary."""
    from .context import parse_ref
    part, idx = parse_ref(ref)
    nxt = f"{part}-{idx + 1:03d}"
    return nxt if nxt in ledger else None


def ledger_rows(root: Path = Path("."), part: int | None = None) -> list[dict]:
    """`build_ledger` flattened to uniform records, `ref` promoted to a field.

    The ledger is a dict keyed by ref because that is what `entry_state` indexes
    into. For emission it has to be a list of records with identical key sets,
    which is the shape the tabular encoder collapses (see emit.py). Sequences of
    strings are joined rather than nested for the same reason: a list-valued
    cell would break the collapse.
    """
    from .context import parse_ref

    rows = []
    for ref, v in build_ledger(root).items():
        if part is not None and parse_ref(ref)[0] != part:
            continue
        rows.append({
            "ref": ref,
            "folio": v["folio"],
            "transcribed": v["transcribed"],
            "open_in": "/".join(v["open_in"]),
            "open_out": "/".join(v["open_out"]),
            "boundary": v["boundary"],
        })
    return rows


def foreign_terms_nearby(ref: str, root: Path = Path("."),
                         span: int = NEARBY) -> list[dict]:
    """Foreign spans already committed on the pages physically around `ref`.

    Recomputed from the committed TEI on every call — there is no persisted
    carried state to go stale, which is the whole point. Scope is the same part
    (heading and orthographic context do not cross a physical volume) and
    `span` scans either side in `all_scans` order.

    This is an error-checking aid, not an input to composition: a term keyed two
    ways on neighbouring pages is worth seeing. It emphatically does not license
    harmonizing one to the other — Tier-1 content is reproduced from *this*
    page's draft, and the firewall check in validate.py enforces that against
    the draft alone.
    """
    from .context import all_scans, parse_ref, stem_for

    part, _ = parse_ref(ref)
    refs = [r for r in all_scans(root) if parse_ref(r)[0] == part]
    if ref not in refs:
        return []
    i = refs.index(ref)
    neighbours = refs[max(0, i - span):i] + refs[i + 1:i + 1 + span]

    seen, out = set(), []
    for nref in neighbours:
        p = root / "tei" / f"{stem_for(nref, root)}.xml"
        if not p.exists():
            continue
        try:
            tree = etree.parse(str(p))
        except (etree.XMLSyntaxError, OSError):
            continue
        # <term> as well as <foreign>. A gloss list's headwords are Tier-1 by the
        # same rule and are worth seeing keyed two ways for the same reason;
        # reading only <foreign> made every term on a neighbouring page invisible
        # here, which is most of what a page like 1-100 contains.
        from .ids import page_glossary
        glosses = {g["term"]: (g["gloss"], g["scope"]) for g in
                   page_glossary(tree.getroot(), nref, root)["pairs"]}
        for el in list(tree.iter(f"{{{TEI_NS}}}foreign")) + \
                  list(tree.iter(f"{{{TEI_NS}}}term")):
            term = " ".join("".join(el.itertext()).split())
            lang = el.get("{http://www.w3.org/XML/1998/namespace}lang") or ""
            # Dedup on the normalized form, emit the term verbatim. Two spellings
            # that differ only by normal form render identically on screen, so
            # keying them as distinct produces a duplicate row whose cause the
            # reader cannot see — which defeats the point of showing a term keyed
            # two ways. A difference that *is* visible still yields two rows.
            key = (unicodedata.normalize("NFD", term), lang)
            if not term or key in seen:
                continue
            seen.add(key)
            # The gloss where the page linked one, plus the frame the gloss list
            # supplies for all its entries — without which "white mixed with
            # brown" says nothing about what is white. Still read-only reference:
            # it says what the neighbour's editor understood the form to mean,
            # which is exactly the context that makes a variant spelling worth a
            # second look — and exactly as unlicensed to copy from as the term.
            #
            # `scope` carries no provenance flag here, deliberately: this record
            # already drops whether the gloss is itself supplied, so marking the frame
            # as authored while the gloss beside it says nothing would be
            # incoherent. `harness lexicon glosses` is the export that keeps both.
            gloss, scope = glosses.get(term, ("", ""))
            out.append({"term": term, "lang": lang, "gloss": gloss,
                        "scope": scope, "ref": nref})
    return out


def entry_state(ref: str, root: Path = Path(".")) -> dict:
    """What page `ref` needs to know about everything before it.

    `expected_folio` is a *prediction*, never an instruction: the last numbered
    predecessor's folio plus the scans since it, and None wherever the chain of
    transcribed pages breaks — an untranscribed predecessor, or the first scan
    of a part. None means "read it off the image and don't guess", which is the
    whole point of it being nullable.
    """
    from .context import all_scans, parse_ref

    part, _ = parse_ref(ref)
    ledger = build_ledger(root)
    refs = [r for r in all_scans(root) if parse_ref(r)[0] == part]
    if ref not in refs:
        raise KeyError(f"{ref} has no scan under {root}")

    i = refs.index(ref)
    prior_ref = refs[i - 1] if i > 0 else None

    expected = None
    prior_folio = None
    basis_ref = None
    if prior_ref is not None and ledger[prior_ref]["transcribed"]:
        prior_folio = ledger[prior_ref]["folio"]
        # Walk back over unpaginated pages to the last numbered one. Everything
        # skipped is transcribed-and-unpaginated by the loop's construction, and
        # a plate carries no folio and so does not advance the printed count —
        # hence +1 from the last numbered page, not +1 per scan. Stop at the
        # first untranscribed page; past that nothing is known.
        j = i - 1
        while j >= 0 and ledger[refs[j]]["transcribed"]:
            if ledger[refs[j]]["folio"] is not None:
                expected = ledger[refs[j]]["folio"] + 1
                basis_ref = refs[j]
                break
            j -= 1

    return {
        "prior_ref": prior_ref,
        "prior_folio": prior_folio,
        # The last *numbered* page the prediction rests on — not necessarily the
        # immediate predecessor, if plates intervene.
        "basis_ref": basis_ref,
        "basis_folio": ledger[basis_ref]["folio"] if basis_ref else None,
        "expected_folio": expected,
        "believed_open": ledger[ref]["open_in"],
        # No `boundary_in`. It said whether the gap before this page was open, and
        # `context`'s `prev_tail` now carries the same fact as `part` on the actual
        # element — read off the same file, one field instead of two. Two names for
        # one fact is the drift shape this project avoids; the ledger's `boundary`
        # column remains, for the gap *after* each page.
    }


def load_toc(root: Path = Path(".")) -> list[dict]:
    p = root / "data/toc.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


_WORD_RE = re.compile(r"[a-z0-9]+")


def _norm_words(s: str) -> set[str]:
    """Word set for mechanical title matching, independent of normal form.

    NFD first, because `[a-z0-9]` treats every non-ASCII codepoint as a separator
    and so a precomposed letter splits where its decomposed twin does not:
    "señor" tokenizes to {se, or} composed but {sen, or} decomposed, and the two
    sets never match. Both sides of every comparison come through here, so folding
    them to one form is enough — NFD rather than NFC because that is the corpus
    form (keying spec section 1), never NFKC, which would rewrite the inventory.

    Combining marks are deliberately left in as separators rather than stripped.
    Stripping them would make matching diacritic-insensitive, i.e. more
    permissive, and this function exists to *check* a heading the model claims to
    have read — a looser match manufactures confirmation, which is the wrong
    direction to err in.
    """
    return set(_WORD_RE.findall(unicodedata.normalize("NFD", s).lower()))


def toc_search(toc: list[dict], query: str, folio: int | None = None,
              span: int = WINDOW) -> list[dict]:
    """ToC entries whose title mechanically matches `query`'s words.

    For use on a heading the model has already read off a page — a check
    against real book-internal apparatus, not a source of a match the model
    invents itself: matching is pure word-set containment (case/punctuation
    folded), nothing fuzzier. A match is any entry whose title's words are a
    subset of the query's words, or vice versa (handles a page heading
    carrying extra furniture, like a leading roman numeral, in either
    direction). If `folio` is given, entries within `span` of it sort first —
    a nearby match is more likely to be the right one — but nothing is
    filtered out by distance; a same-title match anywhere in the book still
    surfaces, since a heading matching two different chapters is exactly the
    kind of thing worth seeing rather than silently resolving.
    """
    q = _norm_words(query)
    if not q:
        return []
    out = []
    for e in toc:
        title = e.get("title") or ""
        t = _norm_words(title)
        if not t or not (t <= q or q <= t):
            continue
        ps = e.get("page_start")
        dist = (ps - folio) if (folio is not None and ps is not None) else None
        out.append({
            "id": e.get("id"), "level": e.get("level"), "title": title,
            "page_start": ps, "distance": dist,
        })
    near = lambda r: r["distance"] is not None and abs(r["distance"]) <= span
    out.sort(key=lambda r: (0 if near(r) else 1,
                            abs(r["distance"]) if r["distance"] is not None else 10**9))
    return out


# `load_boundaries` lived here and read a `boundaries.json` that never existed,
# because the geometry pass that was to write it was never built. Every ledger row
# therefore read `boundary=unknown` — a column that looked like a pending
# measurement and was in fact a dead field. The fact now comes off the committed
# TEI, where `harness tei seam` puts it, which is what "the committed TEI is the
# record" already promised.
