"""Zones by rule off a text layer: `harness zones propose`.

The 1900 «Матеріалы» is set formulaically enough that its zones can be derived
from the rows its PDF's own OCR layer carries (`ocr import`, `mz/ocr/`), so no
segmenter is trained on it and none is keyed from scratch (docs/multitext.md,
"Zoning by rule"). This is that rule. Its output is `#mz` with `kind: rule`, and
it reaches `gt/zones/` only when the editor saves the page in `zones edit`.

**Two column measures, kept apart.** The *row column* is measured off the rows'
own left edges and is the reference for everything that is a fact about the rows:
a margin number, the indent, centring, a row too wide to be one line, the gutter
search. The *zone x* is `zones.page_windows`, the ink-anchored window `zones
check` holds every zone to, so the check judges this output by its own standard.
The two differ by the font-metric-to-ink offset, which is unmeasured; the report
gives it and nothing gates on it.

**A line, not a row, is the unit.** The layer sometimes leaves two rows on one
printed line: the running head's `В.` set in another size, a line number, a row
broken in two. Rows whose vertical centres fall within half the smaller height of
each other are one line. Two full lines whose font-metric boxes overlap (a quote
mark or an accent makes a box ~150 px tall against ~100) are not merged, and
where two bands' lines overlap the boundary goes at the midpoint.

**What the rule will not do** is split a row it cannot read as one line, or
invent a zone for ink no row accounts for. The first is reported as `unzoned`; the
second is `zones check`'s uncovered-ink finding.

`derive` is pure, rows and a mask in, bands out, so its tests need no store.
"""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from pathlib import Path

from . import provenance
from . import zones as zmod
from . import zones_config as zc
from .lines import alto_for_lines
from .refs import norm_ref

#: Bumped whenever the derivation changes what it writes. A file records it, so
#: two proposals of one page can be told apart without re-running either.
RULE_VERSION = "5"

#: Page-level reasons a band may be wrong, each named where `derive` meets it.
#: Hints in the reviewer's page block, not a worklist: every page is reviewed, so
#: a page carrying none is not thereby the rule's confident case.
#:   unzoned    a line too wide to be one line ended a band (a speck does not count)
#:   parallel   a parallel block was found by its gutter
#:   continued  a MainZone-Continued below the first body band, not under a
#:              full-width rule (the Section I streams' separator)
#:   fallback   the ink window could not be measured (`propose` adds it)
#:   uncovered  ink no zone covers that looks like a printed line, most often
#:              one the text layer has no row for (`missing_lines`; `propose`)
FLAGS = ("unzoned", "parallel", "continued", "fallback", "uncovered")

STEP = "harness zones propose"
LABEL = "region segmentation by rule, off the text layer"
ID_PREFIX = "rule_"
OCR_STORE = "mz/ocr"
#: The only producer whose rows this rule reads: the PDF's text layer.
TEXT_LAYER_STEP = "harness ocr import"

HEAD = "RunningTitleZone"
P = "MainZone-P"
CONT = "MainZone-Continued"
OTHER = "MainZone-Other"
NOTES = "MarginTextZone-Notes"
QUIRE = "QuireMarksZone"

_ALNUM = re.compile(r"[^\W_]")
_LONE_NUMBER = re.compile(r"^\s*\d+\s*$")
# A margin mark: a token of at most three characters joined to a row that
# overhangs the column on that side. The overhang is the witness, since no word of
# the text reaches past the column; the token is whatever the layer made of the
# mark. Mostly a line number, often misread (`зо` for 30, `5.`, `-70`), and
# otherwise a speck or a bracket the layer joined to the row (`/`, `}`, `L`, `T`).
_LEAD_MARK = re.compile(r"^\s*(\S{1,3})\s+\S")
_TRAIL_MARK = re.compile(r"\S\s+(\S{1,3})\s*$")
_DIGIT = re.compile(r"\d")
# A folio or a signature: arabic, or roman in either script's letters, since the
# layer reads a roman `I` as Cyrillic `І` as often as not.
_FOLIO = re.compile(r"^\s*(\d+|[IVXLCІХ]+)\s*\.?\s*$")


@dataclass
class Line:
    """One printed line: one or more of the layer's rows on the same baseline."""

    idx: list[int]
    x0: int
    y0: int
    x1: int
    y1: int
    text: str
    lead: bool = False          # a margin number before the text
    trail: bool = False         # a margin number after it

    @property
    def h(self) -> int:
        return self.y1 - self.y0

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2


@dataclass
class Derived:
    bands: list[dict] = field(default_factory=list)
    unzoned: list[dict] = field(default_factory=list)
    numbers: int = 0
    gutters: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)


def _rows(recs: list[dict]) -> list[Line]:
    out = []
    for r in recs:
        if r.get("hpos") is None or r.get("width") is None:
            continue
        x, y, w, h = (int(r[k]) for k in ("hpos", "vpos", "width", "height"))
        out.append(Line([int(r["index"])], x, y, x + w, y + h, r.get("text") or ""))
    return sorted(out, key=lambda ln: (ln.y0, ln.x0))


def row_column(recs: list[dict], measure: int, tol: float) -> int | None:
    """The row column's left edge: the median left edge of the page's full rows.

    A full row is one within `tol` of the measure. A row carrying a margin number
    is wider than that on one side or the other, so it never votes, and a page
    with no full row at all has no row column (`None`).
    """
    xs = [int(r["hpos"]) for r in recs
          if r.get("width") is not None and abs(int(r["width"]) - measure) <= tol]
    return int(statistics.median(xs)) if xs else None


def _group(lines: list[Line]) -> list[Line]:
    """Rows on one printed line become one line, their text in x order."""
    out: list[Line] = []
    for ln in lines:
        prev = out[-1] if out else None
        if prev and abs(ln.cy - prev.cy) < min(ln.h, prev.h) / 2:
            parts = sorted([(prev.x0, prev.text), (ln.x0, ln.text)])
            out[-1] = Line(prev.idx + ln.idx, min(prev.x0, ln.x0), min(prev.y0, ln.y0),
                           max(prev.x1, ln.x1), max(prev.y1, ln.y1),
                           " ".join(t for _, t in parts))
        else:
            out.append(ln)
    return out


def _gutter(lines: list[Line], ink, lo: int, hi: int,
            min_px: int) -> tuple[int, int] | None:
    """A white run every line shares between `lo` and `hi`, with ink on both sides
    of it in each line, as `(width, centre x)`; `None` if none is `min_px` wide."""
    import numpy as np

    white = np.ones(hi - lo, dtype=bool)
    for ln in lines:
        white &= ~ink[ln.y0:ln.y1, lo:hi].any(axis=0)
    padded = np.concatenate(([False], white, [False]))
    edges = np.flatnonzero(np.diff(padded.astype(np.int8)))
    for a, b in zip(edges[::2], edges[1::2], strict=True):
        if b - a < min_px:
            continue
        ga, gb = lo + int(a), lo + int(b)
        if all(ink[ln.y0:ln.y1, ln.x0:ga].any() and ink[ln.y0:ln.y1, gb:ln.x1].any()
               for ln in lines):
            return int(b - a), (ga + gb) // 2
    return None


def _rule(ink, y0: int, y1: int, lo: int, hi: int, bridge: int,
          fill: float) -> tuple[int, int]:
    """The longest horizontal ink run in rows `y0..y1` between `lo` and `hi`, as
    `(length, start x)`, breaks of at most `bridge` px closed and at least `fill`
    of it inked. `(0, 0)` if none.

    The bridge is for a rule the scan broke, which the measurement found on
    several footnote rules. It closes the white between letters too, so a long
    word in close bold type bridges into a run as long as a footnote rule
    (`1-179`); the fill is what parts them. A rule is solid but for its breaks,
    and a row of type is white between its letters.
    """
    import numpy as np

    lo, y0 = max(lo, 0), max(y0, 0)
    best = (0, 0)
    for row in ink[y0:max(y0, y1), lo:hi]:
        xs = np.flatnonzero(row)
        if not len(xs):
            continue
        cut = np.flatnonzero(np.diff(xs) > bridge + 1)
        starts = np.concatenate(([xs[0]], xs[cut + 1]))
        ends = np.concatenate((xs[cut], [xs[-1]]))
        for i in np.argsort(starts - ends):          # longest first
            w = int(ends[i] - starts[i] + 1)
            if w <= best[0]:
                break
            if row[starts[i]:ends[i] + 1].mean() >= fill:
                best = (w, lo + int(starts[i]))
                break
    return best


def _band(label: str, lines: list[Line]) -> dict:
    return {"label": label, "y0": min(ln.y0 for ln in lines),
            "y1": max(ln.y1 for ln in lines),
            "rows": sorted(i for ln in lines for i in ln.idx)}


def derive(recs: list[dict], x0: int, measure: int, ink, cfg: dict) -> Derived:
    """One page's bands, top to bottom, from its text-layer rows.

    `x0` is the row column's left edge (`row_column`), `measure` the book's
    column width, `ink` the page's boolean mask in the rows' pixel space, `cfg`
    the loaded zone config. Each line is
    claimed once, in the order below; a later step sees only what is left.
    """
    t = cfg["text_rule"]
    tol = float(cfg["width_tolerance_px"])
    x1 = x0 + measure
    centre = x0 + measure / 2
    out = Derived()

    # Specks first: a row with no letter or digit is a mark the layer read as text
    # (`/`, `.`, `-`), and left in it would cut every gap it sits in.
    rows = []
    for ln in _rows(recs):
        if not _ALNUM.search(ln.text):
            out.unzoned.append({"rows": ln.idx, "text": ln.text, "reason": "speck"})
        elif _LONE_NUMBER.match(ln.text) and (ln.x0 >= x1 - 20 or ln.x1 <= x0 + 20):
            out.numbers += 1          # a line number on a row of its own
        else:
            rows.append(ln)
    lines = _group(rows)

    pad = t["number_pad"]
    for ln in lines:
        lead = _LEAD_MARK.match(ln.text) if ln.x0 < x0 - pad else None
        trail = _TRAIL_MARK.search(ln.text) if ln.x1 > x1 + pad else None
        ln.lead, ln.trail = bool(lead), bool(trail)
        # Counted where the layer kept a digit; a misread number is a mark too,
        # but this count is of the numbers the report can vouch for.
        out.numbers += sum(1 for m in (lead, trail) if m and _DIGIT.search(m.group(1)))

    def eff(ln: Line) -> tuple[int, int]:
        return (x0 if ln.lead else ln.x0, x1 if ln.trail else ln.x1)

    # The running head: the first line, if it sits in the head band.
    head: list[Line] = []
    if lines and lines[0].y0 < t["head_max_y"]:
        head = [lines.pop(0)]
    if head:
        out.bands.append(_band(HEAD, head))

    # Foot matter, walking up from the last line: a signature, a chapter's folio.
    foot: list[Line] = []
    while lines and len(foot) < 2:
        ln = lines[-1]
        a, b = eff(ln)
        if _FOLIO.match(ln.text) and b - a <= t["foot_max_w"] and a >= x0 - pad \
                and b <= x1 + pad:
            foot.insert(0, lines.pop())
        else:
            break

    # Small marks with a letter in them: a stray `A`, a superscript call `1` on a
    # row of its own, a glyph from another script. After the foot, whose
    # signatures are as short; left in, one cuts a gap or becomes a band inside
    # its neighbour's extent.
    small = t["speck_max_px"]
    kept: list[Line] = []
    for ln in lines:
        if len(ln.text.strip()) <= t["speck_max_chars"] and ln.h < small \
                and ln.x1 - ln.x0 < small:
            out.unzoned.append({"rows": ln.idx, "text": ln.text, "reason": "speck"})
        else:
            kept.append(ln)
    lines = kept

    # The printed rule between each two lines, if any: the longest horizontal ink
    # run from the upper line's centre to the lower's, breaks bridged. Centre to
    # centre, because the layer's boxes drift against the ink and can close the
    # white a rule sits in (`1-387`: 10 px between the boxes either side of the
    # footnote rule), and half a line of type never makes a run this long.
    bridge, fill = int(t["rule_bridge_px"]), float(t["rule_fill_min"])
    between = [_rule(ink, int(a.cy), int(b.cy), x0 - pad, x1 + pad, bridge, fill)
               for a, b in zip(lines, lines[1:], strict=False)]

    def footshape(run: tuple[int, int]) -> bool:
        """A footnote rule: a short run from the column's left edge."""
        w, at = run
        at -= x0                       # from the row column's left edge
        return (w >= t["footrule_min_px"] and at <= t["footrule_max_start"]
                and at + w <= t["footrule_max_end"])

    # Segments: runs of lines with no structural gap and no footnote rule inside
    # them. `rules[k]` is the run above segment k.
    segs: list[list[Line]] = []
    rules: list[tuple[int, int]] = []
    for i, ln in enumerate(lines):
        run = between[i - 1] if i else (0, 0)
        if segs and ln.y0 - segs[-1][-1].y1 < t["gap_min_px"] and not footshape(run):
            segs[-1].append(ln)
        else:
            segs.append([ln])
            rules.append(run)

    def footrule(k: int) -> bool:
        return footshape(rules[k])

    # Footnotes: the segment under a footnote rule, and all after it. The rule is
    # the measurement and the only one: what the first line says is not asked
    # (the layer misreads `1)`, and a document a note introduces opens with none,
    # `1-049`), and a footnote block with no rule over it is the reviewer's.
    notes: list[Line] = []
    ruled = next((k for k in range(1, len(segs)) if footrule(k)), None)
    if ruled is not None:
        notes = [ln for s in segs[ruled:] for ln in s]
        del segs[ruled:]

    # What is left, in order, each line tagged with the segment it opens, and the
    # segment openers that sit under a full-width rule: on a Section I page, the
    # rule between the Chukchi and its Russian, each continuing from the page before.
    work: list[tuple[Line, bool]] = [(ln, i == 0) for s in segs for i, ln in enumerate(s)]
    under_stream_rule = {id(s[0]) for k, s in enumerate(segs)
                         if k and rules[k][0] >= t["stream_rule_min_px"]}
    kinds: list[str] = [""] * len(work)

    # Parallel columns: runs of lines sharing a white gutter mid-column.
    lo, hi = int(x0 + measure / 3), int(x0 + 2 * measure / 3)
    n_min = int(t["gutter_min_rows"])
    i = 0
    while i < len(work):
        j = i
        found = None
        while j < len(work) and (j == i or not work[j][1]):
            g = _gutter([ln for ln, _ in work[i:j + 1]], ink, lo, hi, int(t["gutter_min_px"]))
            if g is None:
                break
            found, j = g, j + 1
        # A gutter sits near the column's centre; a river of word spaces that
        # happens to line up over a few rows can sit anywhere (`1-351`, +443 px).
        if found is not None and j - i >= n_min \
                and abs(found[1] - centre) <= t["gutter_max_offset"]:
            for k in range(i, j):
                kinds[k] = "parallel"
            # Width, offset of its centre from the column's, and lines spanned:
            # what the gutter thresholds are calibrated off.
            out.gutters.append(f"{found[0]}@{found[1] - int(centre):+d}x{j - i}")
            i = j
        else:
            i += 1

    # Too wide to be one line, once a margin number is off it.
    for k, (ln, _) in enumerate(work):
        a, b = eff(ln)
        if not kinds[k] and b - a > measure + tol:
            kinds[k] = "unzoned"
            out.unzoned.append({"rows": ln.idx, "text": ln.text,
                                "reason": f"{b - a} px against a {measure} px column"})

    # Headings: short and centred.
    for k, (ln, _) in enumerate(work):
        a, b = eff(ln)
        if not kinds[k] and not (ln.lead or ln.trail) and b - a <= t["heading_max_w"] \
                and abs((a + b) / 2 - centre) <= t["centre_tol"]:
            kinds[k] = "heading"

    # A band starts at an indent and nowhere else in a run. What the text says is
    # not read: a Примѣчанія note's printed opener, a colophon, a title are the
    # reviewer's to judge against the rulings (2026-11-15, rules are measurement).
    flagged: set[str] = set()
    body_seen = False

    def indented(ln: Line) -> bool:
        return not ln.lead and abs(ln.x0 - x0 - t["indent_px"]) <= t["indent_tol"]

    cur: list[Line] = []
    cur_label = ""

    def flush() -> None:
        nonlocal cur, cur_label
        if cur:
            out.bands.append(_band(cur_label, cur))
        cur, cur_label = [], ""

    run: list[Line] = []
    for k, (ln, opens) in enumerate(work):
        kind = kinds[k]
        if kind != "parallel" and run:
            flush()
            out.bands.append(_band(OTHER, run))
            run = []
        if kind == "parallel":
            if not run:
                flush()
            run.append(ln)
            continue
        if kind == "unzoned":
            flush()
            continue
        if kind == "heading":
            flush()
            out.bands.append(_band(OTHER, [ln]))
            continue
        # Fresh: nothing is open, because a gap, a heading, a parallel block or an
        # unzoned line has just closed it.
        fresh = opens or not cur
        if indented(ln):
            flush()
            cur, cur_label = [ln], P
            body_seen = True
        elif fresh:
            flush()
            cur, cur_label = [ln], CONT
            # The first body band may be Continued: the paragraph carried over
            # from the page before. So may one under a stream rule. Any other
            # followed a gap, a heading or an unzoned line, and is worth a look.
            if body_seen and id(ln) not in under_stream_rule:
                flagged.add("continued")
            body_seen = True
        else:
            cur.append(ln)
    flush()
    if run:
        out.bands.append(_band(OTHER, run))

    if notes:
        out.bands.append(_band(NOTES, notes))
    for ln in foot:
        out.bands.append(_band(QUIRE, [ln]))

    out.bands.sort(key=lambda b: b["y0"])
    if any(u["reason"] != "speck" for u in out.unzoned):
        flagged.add("unzoned")
    if out.gutters:
        flagged.add("parallel")
    out.flags = [f for f in FLAGS if f in flagged]
    # Two bands whose lines overlap meet at the midpoint, so no zone overlaps another.
    for a, b in zip(out.bands, out.bands[1:], strict=False):
        if a["y1"] > b["y0"]:
            mid = (a["y1"] + b["y0"]) // 2
            a["y1"], b["y0"] = mid, mid
    # A band under the store's minimum height grows to it, into the white either
    # side and never past a neighbour: a signature set small (`II`, 54 px on
    # `1-029`) is a zone the gate would otherwise refuse for its type size.
    min_h = int(cfg.get("min_zone_h_px", 0))
    for i, b in enumerate(out.bands):
        need = min_h - (b["y1"] - b["y0"])
        if need <= 0:
            continue
        top = out.bands[i - 1]["y1"] if i else 0
        bottom = out.bands[i + 1]["y0"] if i + 1 < len(out.bands) else ink.shape[0]
        up = min(need // 2, b["y0"] - top)
        down = min(need - up, bottom - b["y1"])
        up = min(need - down, b["y0"] - top)
        b["y0"], b["y1"] = b["y0"] - up, b["y1"] + down
    return out


def missing_lines(ref: str, zones: list[dict], root: Path, cfg: dict,
                  windows: list[dict], ink) -> list[dict]:
    """Ink in the column no zone covers that looks like a printed line.

    `zones.uncovered_ink` reports every such band, and most are not lines: the
    leaf's own edge at the foot of the raster, a printed rule between two zones,
    a margin mark. A line the text layer has no row for is what the rule cannot
    zone and the review pass must be shown (`1-092`'s title, `1-226`'s source
    note). So: a band at least `missing_min_h` tall, touching neither end of the
    raster, and holding no run a printed rule makes.
    """
    t = cfg["text_rule"]
    h = ink.shape[0]
    edge = int(t["missing_edge_px"])
    out = []
    for b in zmod.uncovered_ink(ref, zones, root, cfg, windows, ink):
        y0, y1 = int(b["vpos"]), int(b["vpos"]) + int(b["height"])
        if y1 - y0 < t["missing_min_h"] or y0 <= edge or y1 >= h - edge:
            continue
        w, _ = _rule(ink, y0, y1, int(b["hpos"]), int(b["hpos"]) + int(b["width"]),
                     int(t["rule_bridge_px"]), float(t["rule_fill_min"]))
        if w >= t["footrule_min_px"]:
            continue
        out.append({"y0": y0, "y1": y1, "x0": int(b["hpos"]),
                    "x1": int(b["hpos"]) + int(b["width"])})
    return out


# ---------------------------------------------------------------- the store


def skip_reason(ref: str, root: Path, splits: dict, force: bool) -> str:
    """Why this page is not proposed, or `""` to go ahead."""
    if zmod.is_exempt(ref, root, splits):
        return "ruled not a text page"
    if splits.get(ref) not in zmod.TEXT_SPLITS:
        return "not marked train or eval"
    src = alto_for_lines(ref, root, OCR_STORE)
    if not src.exists():
        return "no text layer in mz/ocr"
    p = provenance.read_producer(src)
    if p is None or p.step != TEXT_LAYER_STEP:
        return (f"mz/ocr is not the text layer (written by "
                f"{p.step if p else 'an unrecorded producer'})")
    if not force and zmod.has_zones(ref, root, zmod.MZDIR):
        q = provenance.read_producer(zmod.alto_for(ref, root, zmod.MZDIR))
        return f"mz/zones already holds a file ({q.step if q else 'unrecorded'})"
    return ""


def propose(ref: str, root: Path = Path("."), cfg: dict | None = None,
            commit: bool = False, force: bool = False,
            splits: dict | None = None) -> tuple[dict, list[dict]]:
    """Derive one page's zones; write them to `mz/zones/` under `commit`.

    Returns the page's report row and its unzoned lines.
    """
    from .lines import ink_mask, page_lines

    ref = norm_ref(ref)
    cfg = cfg or zc.load_config(root)
    splits = zmod.load_splits(root) if splits is None else splits
    row = {"ref": ref, "zones": 0, "labels": "", "unzoned": 0, "numbers": 0,
           "offset": None, "gutter": "", "flags": "", "skipped": ""}
    why = skip_reason(ref, root, splits, force)
    if why:
        row["skipped"] = why
        return row, []

    src = alto_for_lines(ref, root, OCR_STORE)
    recs = page_lines(src, root, ref=ref)
    measure = int(zc.part_spec(cfg, ref)["measure"])
    tol = float(cfg["width_tolerance_px"])
    scan = zmod.scan_for(ref, root)
    ink = ink_mask(scan)
    frame = zmod.measure_frame(ref, root, cfg, ink)
    win = frame["columns"][0]
    x0 = row_column(recs, measure, tol)
    if x0 is None:
        row["skipped"] = "no full-width row to measure the column off"
        return row, []

    got = derive(recs, x0, measure, ink, cfg)
    zones = [{"label": b["label"], "x0": win["x0"], "x1": win["x1"],
              "y0": b["y0"], "y1": b["y1"]} for b in got.bands]
    lines_by_idx = {int(r["index"]): r for r in recs}
    unzoned = [{"ref": ref, "index": " ".join(str(i) for i in u["rows"]),
                "text": u["text"] or " ".join(lines_by_idx[i]["text"] or "" for i in u["rows"]),
                "reason": u["reason"]} for u in got.unzoned]
    missing = missing_lines(ref, zones, root, cfg, frame["columns"], ink)
    flags = [f for f in FLAGS
             if f in got.flags or (f == "fallback" and frame.get("source") == "fallback")
             or (f == "uncovered" and missing)]
    row.update(zones=len(zones), labels=" ".join(sorted({z["label"] for z in zones})),
               unzoned=len(unzoned), numbers=got.numbers, offset=x0 - win["x0"],
               gutter=" ".join(got.gutters), flags=",".join(flags))

    if commit:
        producer = provenance.Producer(
            step=STEP, label=LABEL, kind="rule", version=RULE_VERSION,
            inputs={"ocr": f"{OCR_STORE}/{src.name}",
                    "ocr_sha256": provenance.digest(src),
                    "raster": str(scan.relative_to(root)) if scan.is_relative_to(root)
                    else str(scan),
                    # ink, override (an editor's ruling) or fallback.
                    "window": frame.get("source", "fallback"),
                    "unzoned": len(unzoned),
                    # Always present, empty when nothing fired: a file without
                    # the key predates the flags, which `zones queue` refuses.
                    "flags": ",".join(flags),
                    **{f"rule.{k}": cfg["text_rule"][k] for k in zc.TEXT_RULE_KEYS}})
        tree = zmod.build_alto(ref, zones, zmod.raster_size(ref, root),
                               id_prefix=ID_PREFIX, root=root)
        desc = tree.getroot().find(f"{{{zmod.ALTO_NS}}}Description")
        desc.append(provenance.alto_processing(producer))
        dest = zmod.alto_for(ref, root, zmod.MZDIR)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = zmod.tmp_for(dest)
        tree.write(str(tmp), xml_declaration=True, encoding="UTF-8", pretty_print=True)
        tmp.replace(dest)
    return row, unzoned


def propose_many(refs: list[str], root: Path = Path("."), commit: bool = False,
                 force: bool = False, tick=None) -> tuple[list[dict], list[dict]]:
    cfg = zc.load_config(root)
    if "text_rule" not in cfg:
        raise zc.ConfigError(
            f"{zc.config_path(root)} has no text_rule block: this text's zones "
            "were never calibrated to be derived off a text layer")
    splits = zmod.load_splits(root)
    rows, unzoned = [], []
    for ref in refs:
        r, u = propose(ref, root, cfg, commit=commit, force=force, splits=splits)
        rows.append(r)
        unzoned.extend(u)
        if tick:
            tick()
    return rows, unzoned
