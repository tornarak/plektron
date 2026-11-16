"""The zone review pass: an agent's verdict on the rule's zones.

`zones propose` writes `mz/zones/` by rule (`#mz`). An agent reviewing that file
writes `review/PP-NNN/zones.json` (`#llm`): **edits against the file, never a
restatement of it**, which is the collation principle — a model never authors
structure a store already holds. The editor opens the rule's bands with the edits
applied (`zones edit`, the `llm` view), and a human save is what writes `gt/zones/`.
Nothing here writes a zone file.

**Edits name band numbers and line indices.** A band is numbered 1… in
`zones.read_zones` order; a line is its `page_lines` index; a line belongs to the
band holding its vertical centre (`lines.line_band`, the rule every reader of a
zone label already uses). So an edit means one thing on every reread, and the
verdict names the **bands' digest** (`bands_digest`), so it goes stale visibly
when the bands it numbers change rather than applying to bands it never saw.

**The digest is of the bands, not the file** (the editor, 2026-11-15). An edit's
meaning depends on each band's label, its y-range and the lines it holds, and on
the lines no band holds — nothing else. The whole file's digest also covered the
zones' x, so moving the column window (the 34 px it sat left of the ink) staled
448 verdicts whose every band was unchanged. A witness to more than its claim is
not stricter; it is a witness to the wrong thing.

**Ops apply in a fixed order and always to the original numbering**: relabel,
then merge, then split, then absorb. Each refers to the bands and lines `zones
bands` printed, never to a band an earlier op made, so no edit's meaning depends
on another's.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import provenance
from . import zones as zmod
from . import zones_config as zc
from .lines import alto_for_lines, line_band, page_lines
from .paths import verdict_path
from .refs import norm_ref

OPS = ("relabel", "merge", "split", "absorb")
#: Each op's fields beyond `op` and `why`. A field outside these is refused: a
#: mistyped key would sit in the file looking like it said something.
FIELDS = {"relabel": ("band", "label"), "merge": ("band",),
          "split": ("line", "label"), "absorb": ("line", "into")}
KEYS = ("ref", "reviewed", "bands", "edits", "notes")
OCR_STORE = "mz/ocr"


class Missing(ValueError):
    """A store the pass reads holds nothing for this page."""


def bands_digest(bands: list[dict], unbanded: list[int]) -> str:
    """sha256 over what a verdict's band numbers mean: each band's label, y-range
    and lines in `read_zones` order, and the lines no band holds."""
    import hashlib
    doc = {"bands": [[b["label"], int(b["y0"]), int(b["y1"]), b["lines"]] for b in bands],
           "unbanded": sorted(int(i) for i in unbanded)}
    blob = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _rel(p: Path, root: Path) -> str:
    r, p = Path(root).resolve(), Path(p).resolve()
    return str(p.relative_to(r)) if p.is_relative_to(r) else str(p)


def baseline(ref: str, root: Path = Path(".")) -> dict:
    """One page's `mz/zones/` file as the agent edits it, read and never re-derived.

    `bands` are numbered from 1 with their line indices; `unbanded` are the lines
    whose centre no band holds. `zones` and `lines` are the raw inputs `apply`
    takes, kept so a caller does not read either file twice.
    """
    ref = norm_ref(ref)
    src = zmod.alto_for(ref, root, zmod.MZDIR)
    if not src.exists():
        raise Missing(f"{ref}: no mz/zones/ file. `harness zones propose {ref} "
                      "--commit` writes one")
    ocr = alto_for_lines(ref, root, OCR_STORE)
    if not ocr.exists():
        raise Missing(f"{ref}: no {OCR_STORE}/ file, so no line can be placed in a "
                      "band. `harness ocr import` writes the text layer")
    zones = zmod.read_zones(ref, root, store=zmod.MZDIR)
    # A line with no box cannot be in a band, and no edit could name it usefully.
    lines = [r for r in page_lines(ocr, root, ref=ref)
             if r.get("vpos") is not None and r.get("height") is not None]
    members: dict[int, list[int]] = {i: [] for i in range(len(zones))}
    unbanded = []
    for r in lines:
        i = line_band(r, zones)
        if i is None:
            unbanded.append(r)
        else:
            members[i].append(int(r["index"]))
    p = provenance.read_producer(src)
    bands = [{"band": i + 1, "label": z["label"], "y0": z["y0"], "y1": z["y1"],
              "lines": " ".join(str(k) for k in members[i])}
             for i, z in enumerate(zones)]
    return {
        "ref": ref,
        "file": _rel(src, root),
        "sha256": provenance.digest(src),
        "bands_sha256": bands_digest(bands, [int(r["index"]) for r in unbanded]),
        "producer": p.step if p else "",
        "version": p.version if p else "",
        # None, not "", where the file predates the flags: "" means none fired.
        "flags": p.inputs.get("flags") if p else None,
        "bands": bands,
        "unbanded": [{"index": int(r["index"]), "y0": r["vpos"],
                      "y1": r["vpos"] + r["height"], "text": r.get("text") or ""}
                     for r in unbanded],
        "zones": zones,
        "lines": lines,
    }


def types_table(cfg: dict) -> list[dict]:
    """The declared types as the agent judges against them: one home, the config."""
    return [{"label": t["label"], "key": t.get("key", ""), "name": t.get("name", ""),
             "description": t.get("description", "")} for t in cfg["types"]]


def load(ref: str, root: Path = Path(".")) -> dict | None:
    """The page's verdict file parsed, or None where there is none.

    Raises `ValueError` on a file that is not JSON: unreadable is a finding, and
    `issues` reports it rather than treating the page as unreviewed.
    """
    p = verdict_path(norm_ref(ref), root)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"{_rel(p, root)} is not JSON: {e}") from None


def _cy(r: dict) -> float:
    return float(r["vpos"]) + float(r["height"]) / 2


def apply(zones: list[dict], lines: list[dict], edits: list[dict]) -> list[dict]:
    """The rule's bands with the edits applied. Pure; `edits` already passed `issues`.

    Every band an edit touched carries `why`, the list of reasons; a band no edit
    touched comes back exactly as it went in.
    """
    out = [dict(z) for z in zones]
    why: list[list[str]] = [[] for _ in zones]
    member: dict[int, int] = {}
    by_idx: dict[int, dict] = {}
    for r in lines:
        by_idx[int(r["index"])] = r
        i = line_band(r, zones)
        if i is not None:
            member[int(r["index"])] = i

    for e in edits:
        if e["op"] == "relabel":
            out[e["band"] - 1]["label"] = e["label"]
            why[e["band"] - 1].append(e["why"])

    merged = {e["band"] - 1: e["why"] for e in edits if e["op"] == "merge"}
    groups: list[list[int]] = []
    for i in range(len(out)):
        if i in merged and groups:
            groups[-1].append(i)
        else:
            groups.append([i])

    splits: dict[int, dict] = {e["line"]: e for e in edits if e["op"] == "split"}
    result: list[tuple[dict, list[str]]] = []
    for g in groups:
        head = dict(out[g[0]])
        head["y1"] = out[g[-1]]["y1"]
        reasons = list(why[g[0]]) + [merged[i] for i in g[1:]]
        mine = sorted((by_idx[k] for k, i in member.items() if i in g), key=_cy)
        cuts = []
        for pos, r in enumerate(mine):
            e = splits.get(int(r["index"]))
            if e is None or pos == 0:
                continue
            prev = mine[pos - 1]
            cut = (int(prev["vpos"]) + int(prev["height"]) + int(r["vpos"])) // 2
            # Between the two centres whatever the boxes do, so each line stays in
            # the band it was split into.
            cut = max(int(_cy(prev)) + 1, min(int(_cy(r)) - 1, cut))
            cuts.append((cut, e))
        if not cuts:
            result.append((head, reasons))
            continue
        top = dict(head, y1=cuts[0][0])
        result.append((top, reasons + [cuts[0][1]["why"]]))
        for k, (cut, e) in enumerate(cuts):
            y1 = cuts[k + 1][0] if k + 1 < len(cuts) else head["y1"]
            piece = dict(head, label=e["label"], y0=cut, y1=y1)
            piece.pop("id", None)
            result.append((piece, [e["why"]]))

    for e in edits:
        if e["op"] != "absorb":
            continue
        r = by_idx[e["line"]]
        cy = _cy(r)
        # A merge across the line has already taken it in: the band that holds it
        # now is the one it was absorbed into, and only the reason is added.
        inside = [i for i, (z, _) in enumerate(result) if z["y0"] <= cy <= z["y1"]]
        if inside:
            result[inside[0]][1].append(e["why"])
            continue
        if e["into"] == "above":
            k = max(i for i, (z, _) in enumerate(result) if z["y1"] < cy)
            result[k][0]["y1"] = max(result[k][0]["y1"], int(r["vpos"]) + int(r["height"]))
        else:
            k = min(i for i, (z, _) in enumerate(result) if z["y0"] > cy)
            result[k][0]["y0"] = min(result[k][0]["y0"], int(r["vpos"]))
        result[k][1].append(e["why"])

    final = []
    for z, reasons in result:
        if reasons:
            z["why"] = reasons
        final.append(z)
    return final


def _edit_errors(v: dict, base: dict, cfg: dict) -> list[dict]:
    """Everything wrong with the verdict before it is applied."""
    errors: list[dict] = []

    def err(rule: str, detail: str):
        errors.append({"rule": rule, "detail": detail})

    for k in sorted(set(v) - set(KEYS)):
        err("unknown-key", f"{k!r} is not a verdict field ({', '.join(KEYS)})")
    if v.get("ref") != base["ref"]:
        err("wrong-ref", f"names {v.get('ref')!r}, but the file is {base['ref']}'s")
    rev = v.get("reviewed") or {}
    if rev.get("file") != base["file"]:
        err("wrong-file", f"reviewed {rev.get('file')!r}, not {base['file']}")
    if "bands_sha256" not in rev:
        err("stale", "names no bands_sha256: it predates the bands digest, and "
                     "`zones verdict --restamp` migrates a verdict that was fresh")
        return errors
    if rev.get("bands_sha256") != base["bands_sha256"]:
        err("stale", f"reviewed bands with digest {str(rev.get('bands_sha256'))[:12]}…; "
                     f"{base['file']}'s are now {base['bands_sha256'][:12]}… — the "
                     "bands changed under the verdict, so its band numbers mean nothing")
        return errors
    n = len(base["zones"])
    if v.get("bands") != n:
        err("band-count", f"says {v.get('bands')!r} bands; the file holds {n}")

    labels = set(zc.types_by_label(cfg))
    member = {}
    for r in base["lines"]:
        i = line_band(r, base["zones"])
        member[int(r["index"])] = i
    openers = set()
    for i in range(n):
        mine = sorted((r for r in base["lines"] if member[int(r["index"])] == i), key=_cy)
        if mine:
            openers.add(int(mine[0]["index"]))

    edits = v.get("edits")
    if not isinstance(edits, list):
        err("edits", "`edits` must be a list, empty where the bands stand")
        edits = []
    relabelled, merged, split_at, absorbed = set(), set(), set(), set()
    for k, e in enumerate(edits, 1):
        at = f"edit {k}"
        if not isinstance(e, dict) or e.get("op") not in OPS:
            err("op", f"{at}: op must be one of {', '.join(OPS)}")
            continue
        op = e["op"]
        want = {"op", "why", *FIELDS[op]}
        for f in sorted(set(e) - want):
            err("field", f"{at} ({op}): {f!r} is not one of its fields")
        for f in sorted(want - set(e)):
            err("field", f"{at} ({op}): {f!r} is missing")
        if not isinstance(e.get("why"), str) or not e["why"].strip():
            err("why", f"{at} ({op}): `why` must say which ruling or type "
                       "description the band contradicts")
        if "band" in FIELDS[op]:
            b = e.get("band")
            if not isinstance(b, int) or isinstance(b, bool) or not 1 <= b <= n:
                err("band-range", f"{at} ({op}): band {b!r} is not 1..{n}")
                continue
        if "line" in FIELDS[op]:
            ln = e.get("line")
            if not isinstance(ln, int) or isinstance(ln, bool) or ln not in member:
                err("line-range", f"{at} ({op}): line {ln!r} is not a line of the page")
                continue
        if "label" in FIELDS[op] and e.get("label") not in labels:
            err("label", f"{at} ({op}): {e.get('label')!r} is not a declared type")
        if op == "relabel":
            b = e["band"]
            if b in relabelled:
                err("conflict", f"{at}: band {b} is relabelled twice")
            relabelled.add(b)
            if e.get("label") == base["zones"][b - 1]["label"]:
                err("no-op", f"{at}: band {b} is already {e['label']}")
        elif op == "merge":
            b = e["band"]
            if b == 1:
                err("conflict", f"{at}: band 1 has no band above to merge into")
            if b in merged:
                err("conflict", f"{at}: band {b} is merged twice")
            merged.add(b)
        elif op == "split":
            ln = e["line"]
            if member[ln] is None:
                err("conflict", f"{at}: line {ln} is in no band; absorb it instead")
            elif ln in openers:
                err("conflict", f"{at}: line {ln} already opens band {member[ln] + 1}")
            if ln in split_at:
                err("conflict", f"{at}: two splits at line {ln}")
            split_at.add(ln)
        elif op == "absorb":
            ln = e["line"]
            if member[ln] is not None:
                err("conflict", f"{at}: line {ln} is in band {member[ln] + 1} already")
            if ln in absorbed:
                err("conflict", f"{at}: line {ln} is absorbed twice")
            absorbed.add(ln)
            into = e.get("into")
            if into not in ("above", "below"):
                err("field", f"{at}: `into` is above or below, not {into!r}")
            else:
                r = next(x for x in base["lines"] if int(x["index"]) == ln)
                side = [z for z in base["zones"]
                        if (z["y1"] < _cy(r) if into == "above" else z["y0"] > _cy(r))]
                if not side:
                    err("conflict", f"{at}: no band {into} line {ln}")
    for b in sorted(relabelled & merged):
        err("conflict", f"band {b} is both relabelled and merged; a merge takes the "
                        "label of the band above, so the relabel would be lost")

    notes = v.get("notes", [])
    if not isinstance(notes, list):
        err("notes", "`notes` must be a list")
        notes = []
    for k, note in enumerate(notes, 1):
        if not isinstance(note, dict) or not str(note.get("text") or "").strip():
            err("notes", f"note {k}: needs a `text`")
            continue
        for f in sorted(set(note) - {"line", "text"}):
            err("notes", f"note {k}: {f!r} is not a note field (line, text)")
        if "line" in note and note["line"] not in member:
            err("notes", f"note {k}: line {note['line']!r} is not a line of the page")
    return errors


def _geometry(ref: str, root: Path, cfg: dict) -> tuple[int, list | None, list, int]:
    from .lines import ink_mask
    measure = zc.window_width(zc.part_spec(cfg, ref))
    over = zc.override_windows(cfg, ref)
    windows = over if over is not None else zmod.page_windows(
        ref, root, cfg, ink_mask(zmod.scan_for(ref, root)))
    _, page_h = zmod.raster_size(ref, root)
    return measure, over, windows, page_h


def issues(ref: str, root: Path = Path("."), cfg: dict | None = None) -> dict:
    """The gate on one page's verdict: `errors` empty is a verdict that may be shown.

    `inherited` are zone errors the rule's own file already carries, which an edit
    did not introduce and the verdict is not failed for; `zones` is the applied
    result, `None` wherever an error stopped it being computed.
    """
    ref = norm_ref(ref)
    cfg = cfg or zc.load_config(root)
    rec = {"ref": ref, "errors": [], "inherited": [], "verdict": None, "zones": None,
           "base": None}
    try:
        v = load(ref, root)
    except ValueError as e:
        rec["errors"].append({"rule": "malformed", "detail": str(e)})
        return rec
    if v is None:
        rec["errors"].append({"rule": "missing",
                              "detail": f"no {_rel(verdict_path(ref, root), root)}"})
        return rec
    if not isinstance(v, dict):
        rec["errors"].append({"rule": "malformed", "detail": "not a JSON object"})
        return rec
    rec["verdict"] = v
    try:
        base = baseline(ref, root)
    except Missing as e:
        rec["errors"].append({"rule": "no-baseline", "detail": str(e)})
        return rec
    rec["base"] = base
    rec["errors"] = _edit_errors(v, base, cfg)
    if rec["errors"]:
        return rec
    got = apply(base["zones"], base["lines"], v.get("edits") or [])
    geo = _geometry(ref, root, cfg)
    before = {(e["rule"], e["detail"]) for e in zmod.zone_list_errors(base["zones"], cfg, *geo)}
    for e in zmod.zone_list_errors(got, cfg, *geo):
        if (e["rule"], e["detail"]) in before:
            rec["inherited"].append(e)
        else:
            rec["errors"].append({"rule": f"applied {e['rule']}", "detail": e["detail"]})
    rec["zones"] = got
    return rec


def applied(ref: str, root: Path = Path("."), cfg: dict | None = None) -> dict:
    """What the editor's `llm` view shows: the applied bands, or why there are none.

    `stale` is reported apart from the other errors because the editor draws it
    apart: a verdict against a file since rewritten is a known state with one
    remedy (review the page again), not a malformed file.
    """
    rec = issues(ref, root, cfg)
    v = rec["verdict"] or {}
    return {"zones": rec["zones"] if not rec["errors"] else None,
            "edits": v.get("edits") or [], "notes": v.get("notes") or [],
            "stale": any(e["rule"] == "stale" for e in rec["errors"]),
            "errors": rec["errors"],
            "present": verdict_path(norm_ref(ref), root).exists()}


def fresh(ref: str, root: Path = Path(".")) -> bool:
    """Whether a verdict exists and names the rule's bands as they now are."""
    try:
        v = load(ref, root)
        base = baseline(ref, root)
    except (ValueError, Missing):
        return False
    if not isinstance(v, dict):
        return False
    return (v.get("reviewed") or {}).get("bands_sha256") == base["bands_sha256"]


def restamp(ref: str, root: Path = Path("."), commit: bool = False) -> str:
    """Migrate one verdict to the bands digest, where it is fresh by the old one.

    Mechanical, and only on its witness: a verdict naming the rule file's current
    whole-file sha256 was checked against exactly these bands, so it is given their
    digest. Anything else is left as it is. Returns what happened.
    """
    ref = norm_ref(ref)
    try:
        v = load(ref, root)
    except ValueError:
        return "unreadable"
    if not isinstance(v, dict):
        return "no verdict"
    rev = v.get("reviewed") or {}
    if "bands_sha256" in rev:
        return "already"
    try:
        base = baseline(ref, root)
    except Missing:
        return "no rule file"
    if rev.get("sha256") != base["sha256"]:
        return "stale"
    if commit:
        v["reviewed"] = {"file": rev.get("file"), "bands_sha256": base["bands_sha256"]}
        p = verdict_path(ref, root)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(v, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8")
        tmp.replace(p)
    return "restamped"
