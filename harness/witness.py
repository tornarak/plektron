"""A second copy of the book, set beside the master line by line.

**The witness is a second scan, not a second reader.** Copy B of the 1900
*Materials* carries a text layer made by the same engine as copy A's, so where the
two agree they may be agreeing on one engine's habit: their agreement lets a line
of Russian prose stand, and never settles a native form (`docs/multitext.md`).
Where they differ, the difference is the cheapest pointer to the place a reader
must look at the scan.

**Pages are paired by their text, never by index.** Copy B is cropped differently
and scanned two of its pages twice, so a fixed offset would silently pair a page
with its neighbour. `pair` scores every copy-B page in a window against each
copy-A page and accepts the best only when it is clear of the runner-up by
`MARGIN`; a page that matches two equally is *named*, and the editor settles it in
the witness's `map` in `project.json`. Nothing here picks between two candidates.

**Lines are aligned by their text, never by index.** The two layers' rows differ in
number (33 against 32 on printed p. 144), so `align` is a monotone alignment over
line similarity, and a line the other copy has no match for is said to have none.
"""
from __future__ import annotations

import difflib
import json
import unicodedata
from collections.abc import Callable
from pathlib import Path

from .layout import witness
from .refs import norm_ref, parse_ref

#: A copy-B page is a copy-A page's reading when their word sequences agree this
#: well (`SequenceMatcher.ratio`)…
PAGE_MIN = 0.5
#: …and the runner-up is at least this far behind. Measured: a true pair scores
#: 0.57–0.93, a neighbour ≤ 0.16, and the doubly scanned pp. 2–3 score 0.71 and
#: 0.77 for one page — the case this margin exists to refuse.
MARGIN = 0.15
#: How far either side of the running offset to look, in pages.
WINDOW = 6
#: A page with fewer words than this carries no text worth pairing (a blank, a
#: plate): it is reported as such rather than paired on noise.
MIN_WORDS = 20
#: Two lines are one line read twice at this similarity or above.
LINE_MIN = 0.6

DATA = "data/witness-{id}.json"


class WitnessError(ValueError):
    """A witness that cannot be paired or read."""


def _nfd(s: str) -> str:
    return unicodedata.normalize("NFD", s.replace(" ", " "))


def _words(page) -> list[str]:
    return _nfd(page.get_text()).split()


def _pdf(root: Path, wid: str) -> Path:
    p = Path(root) / witness(root, wid)["pdf"]
    if not p.exists():
        raise WitnessError(f"witness {wid!r}: {p} does not exist")
    return p


def method() -> dict:
    return {"page_min": PAGE_MIN, "margin": MARGIN, "window": WINDOW,
            "min_words": MIN_WORDS, "score": "difflib.SequenceMatcher.ratio over NFD words"}


def pair(root: Path, wid: str, refs: list[str] | None = None,
         tick: Callable | None = None) -> dict:
    """Copy-A ref → witness page, by text, for every scan of part 1.

    Returns `{map, ruled, ambiguous, unmatched, empty, score}`. `ruled` are the
    editor's pairings from the manifest, which are taken as given and scored for
    the record; `ambiguous` lists the candidates a page could not be told apart
    from, best first, and is what the editor rules on.
    """
    import pymupdf

    from .paths import all_scans
    from .textlayer import master_pdf

    root = Path(root)
    ruled = {norm_ref(k): v for k, v in witness(root, wid).get("map", {}).items()}
    refs = refs or all_scans(root)
    out: dict = {"map": {}, "ruled": {}, "ambiguous": {}, "unmatched": [], "empty": [],
                 "score": {}}
    with pymupdf.open(_pdf(root, wid)) as bdoc:
        bwords: dict[int, list[str]] = {}

        def bw(n: int) -> list[str]:
            if n not in bwords:
                bwords[n] = _words(bdoc[n - 1])
            return bwords[n]

        offset = 0
        docs: dict[Path, object] = {}
        try:
            for i, ref in enumerate(refs, 1):
                if tick:
                    tick(ref, i, len(refs))
                pdf, index = master_pdf(ref, root)
                if pdf not in docs:
                    docs[pdf] = pymupdf.open(pdf)
                aw = _words(docs[pdf][index - 1])
                if ref in ruled:
                    b = ruled[ref]
                    if not 1 <= b <= len(bdoc):
                        raise WitnessError(f"{ref}: ruled to witness page {b}, which "
                                           f"the {len(bdoc)}-page PDF does not have")
                    out["map"][ref] = out["ruled"][ref] = b
                    out["score"][ref] = round(difflib.SequenceMatcher(
                        None, aw, bw(b), autojunk=False).ratio(), 3)
                    offset = b - index
                    continue
                if len(aw) < MIN_WORDS:
                    out["empty"].append(ref)
                    continue
                lo = max(1, index + offset - WINDOW)
                hi = min(len(bdoc), index + offset + WINDOW)
                scored = sorted(((difflib.SequenceMatcher(
                    None, aw, bw(b), autojunk=False).ratio(), b)
                    for b in range(lo, hi + 1)), reverse=True)
                best, b = scored[0]
                if best < PAGE_MIN:
                    out["unmatched"].append(ref)
                    continue
                rivals = [(r, c) for r, c in scored[1:] if r >= best - MARGIN]
                if rivals:
                    out["ambiguous"][ref] = [{"page": c, "score": round(r, 3)}
                                             for r, c in [(best, b), *rivals]]
                    continue
                out["map"][ref] = b
                out["score"][ref] = round(best, 3)
                offset = b - index
        finally:
            for d in docs.values():
                d.close()
    return out


def write(root: Path, wid: str, result: dict) -> Path:
    """The pairing as a receipt in `data/`, with the method that made it."""
    from . import provenance
    from .atomic import tmp_for

    dest = Path(root) / DATA.format(id=wid)
    pdf = _pdf(root, wid)
    doc = {"_method": method(), "_witness": witness(root, wid)["pdf"],
           "_sha256": provenance.digest(pdf), **result}
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = tmp_for(dest)
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                   encoding="utf-8")
    tmp.replace(dest)
    return dest


def page_of(ref: str, root: Path, wid: str) -> int:
    """The witness page paired with `ref`, from the receipt `ocr pair` wrote."""
    ref = norm_ref(ref)
    p = Path(root) / DATA.format(id=wid)
    if not p.exists():
        raise WitnessError(f"no {p.name}: run `harness ocr pair --all` first")
    doc = json.loads(p.read_text(encoding="utf-8"))
    if ref in doc["map"]:
        return doc["map"][ref]
    for why in ("ambiguous", "unmatched", "empty"):
        if ref in doc[why]:
            hint = (" — rule it in the witness's `map` in project.json"
                    if why == "ambiguous" else "")
            raise WitnessError(f"{ref}: {why} in {p.name}{hint}")
    raise WitnessError(f"{ref}: not in {p.name}; re-run `ocr pair`")


def rows(ref: str, root: Path, wid: str) -> list[str]:
    """The witness page's rows, by the importer's own row rule, as NFD text."""
    import pymupdf

    from . import keying
    from .textlayer import fragments
    from .textlayer import rows as build
    fold = keying.rules(root).fold
    with pymupdf.open(_pdf(root, wid)) as doc:
        page = doc[page_of(ref, root, wid) - 1]
        return [fold(_nfd(r["text"])) for r in build(fragments(page))]


def _ratio(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def align(a: list[str], b: list[str], floor: float = LINE_MIN
          ) -> list[tuple[int | None, int | None, float]]:
    """A monotone alignment of two line lists maximising total similarity.

    `(i, j, ratio)` for a matched pair, `(i, None, 0)` for an `a` line with no
    match, `(None, j, 0)` for a `b` line with none, in reading order. A pair below
    `floor` is never made: two different lines are not one line read badly.
    """
    n, m = len(a), len(b)
    r = [[_ratio(a[i], b[j]) for j in range(m)] for i in range(n)]
    best = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            take = r[i][j] + best[i + 1][j + 1] if r[i][j] >= floor else -1.0
            best[i][j] = max(take, best[i + 1][j], best[i][j + 1])
    out, i, j = [], 0, 0
    while i < n and j < m:
        if r[i][j] >= floor and best[i][j] == r[i][j] + best[i + 1][j + 1]:
            out.append((i, j, r[i][j]))
            i, j = i + 1, j + 1
        elif best[i][j] == best[i + 1][j]:
            out.append((i, None, 0.0))
            i += 1
        else:
            out.append((None, j, 0.0))
            j += 1
    out += [(k, None, 0.0) for k in range(i, n)]
    out += [(None, k, 0.0) for k in range(j, m)]
    return out


def _squash(s: str) -> str:
    """A line with its spacing taken out — the layers disagree on space before
    punctuation far more often than on a letter, and a reader keys the print's
    spacing either way (§2.9)."""
    return "".join(s.split())


def compare(ref: str, root: Path, wid: str) -> dict:
    """The master's lines beside the witness's, and the native forms in each.

    Fields per line: `index` (the `page_lines` index `proposal.json` keys on),
    `a`, `b` (`null` where the witness has no match), `agree` — `same` (equal),
    `spacing` (equal but for spaces), `differ`, or `alone` — and `native`, the
    tokens either copy reads as Tier-1 under this text's keying rules.
    `b_only` are witness lines the master has no match for.
    """
    from . import keying
    from .detectors import EDGE_PUNCT, TOKEN, bears_inventory, tier2
    from .lines import page_lines
    from .recognize import MZDIR, alto_for

    ref = norm_ref(ref)
    parse_ref(ref)
    root = Path(root)
    p = alto_for(ref, root, MZDIR)
    if not p.exists():
        raise WitnessError(f"{ref}: no master reading in mz/ocr/ — `ocr import` it")
    recs = [r for r in page_lines(p, root, ref=ref) if r["text"].strip()]
    rules = keying.rules(root)
    a = [rules.fold(_nfd(r["text"])) for r in recs]
    b = rows(ref, root, wid)

    def native(*texts: str) -> list[str]:
        seen: list[str] = []
        for t in texts:
            for m in TOKEN.finditer(t or ""):
                tok = m.group().strip(EDGE_PUNCT)
                if (tok and tok not in seen and not tier2(tok, rules)
                        and bears_inventory(tok, rules)):
                    seen.append(tok)
        return seen

    lines, b_only = [], []
    for i, j, _ in align(a, b):
        if i is None:
            b_only.append({"b": b[j], "native": native(b[j])})
            continue
        bt = b[j] if j is not None else None
        agree = ("alone" if bt is None else "same" if bt == a[i]
                 else "spacing" if _squash(bt) == _squash(a[i]) else "differ")
        lines.append({"index": recs[i]["index"], "a": a[i], "b": bt, "agree": agree,
                      "native": native(a[i], bt or "")})
    counts = {k: sum(1 for x in lines if x["agree"] == k)
              for k in ("same", "spacing", "differ", "alone")}
    return {"ref": ref, "witness_page": page_of(ref, root, wid), **counts,
            "b_only": len(b_only), "lines": lines, "b_lines": b_only}


__all__ = ["DATA", "LINE_MIN", "MARGIN", "PAGE_MIN", "WitnessError", "align",
           "compare", "method", "page_of", "pair", "rows", "write"]
