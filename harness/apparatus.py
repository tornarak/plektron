"""Page-runs: spans of scans the edition serves as one document, and the locator
that resolves a ref, a folio or a ToC id into a place inside one.

Six scans of List of Illustrations are one printed list, not six documents, and a
reader paging through them a leaf at a time is reading the binding rather than the
book. So the unit the reading view serves is the **run**, and `data/runs.json`
declares which spans are runs.

**The locator and the anchor vocabulary are the load-bearing part, not the three
renderers.** A chapter page is the same object with a derived span — `runs()` will
one day fold in runs computed from `data/toc.json` and the folio index, and nothing
downstream may care which kind it got. That is why `anchor` is one function rather
than an f-string at each call site (`figures.crop_name`'s rule: one function because
several callers must agree exactly), and why every redirect route in `web/edition.py`
goes through `locate` rather than resolving its own key.

**Nothing here interpolates.** A redirect is a resolution, and a guessed one is
indistinguishable from a witnessed one at the URL — so a folio no witness records
refuses and names its neighbours, which on this corpus is the common answer and has
to read as one.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import authorities, figrefs
from .context import all_scans, norm_ref, parse_ref
from .state import _tei_facts, load_toc

RUNS_JSON = "data/runs.json"

#: The closed vocabulary of renderers, and what each kind's store looks like. A run
#: naming a kind that is not here is a gate failure rather than a page that silently
#: falls back to the bare leaf — `figures`' `unknown-exemption` rule, for the same
#: reason: a typo that degrades quietly is a typo nobody finds.
#:
#: **`folio_of_leaf` is the field that has to be declared and cannot be guessed.**
#: All three stores carry a `folio` beside a `ref`, and in only one of them do the
#: two describe the same leaf. An `authorities.json` entry says "this entry was
#: printed on `1-023`, which is folio 3" — the entry *is* the thing on that page. An
#: `loi.json` entry says "this figure appears on folio 17" while its `ref` is the
#: List-of-Illustrations leaf the caption was read from, `1-014`: the folio is about
#: the *subject*, the ref about the *description*, and they are pages apart. Read as
#: a folio witness that places `1-014` at folio 17, and outranking the running
#: titles, it sent every folio in the book to the List of Illustrations.
KINDS = {
    "toc": {"entries": ("entries",), "folio_of_leaf": False},
    "loi": {"entries": ("figures", "plates"), "folio_of_leaf": False},
    "authorities": {"entries": ("authorities",), "folio_of_leaf": True},
    # Every sort is printed on the one leaf the key occupies, so its `folio` is
    # that leaf's — the `authorities` case, not the `loi` one. It is also the
    # only witness there is for folio 10, which is otherwise the single hole
    # between the Authorities run's folio 9 and the body's folio 11.
    "alphabet": {"entries": ("sorts",), "folio_of_leaf": True},
}

#: Anchor kinds. `leaf` is emitted for every ref in a run whether or not the store
#: holds an entry printed on it, because a redirect must always land somewhere.
ANCHOR_KINDS = ("leaf", "folio", "toc")

#: Folio witnesses, strongest first; the rank is the index. Rank *resolves* — the
#: redirect follows the strongest — but it does not silence: a weaker witness
#: contradicting a stronger one is reported by `edition runs`, since that is
#: usually a misread running title and is worth seeing.
WITNESSES = ("tei", "apparatus", "running-title")


def anchor(kind: str, key) -> str:
    """The fragment id for one anchor. `("leaf", "1-015") -> "leaf-1-015"`.

    One function because the template that emits the id and the locator that
    builds the URL pointing at it must agree exactly, and they live in different
    modules. A ref is normalised on the way through, so `1-15` and `1-015` cannot
    mint two anchors for one leaf.
    """
    if kind not in ANCHOR_KINDS:
        raise ValueError(f"{kind!r} is not an anchor kind: {ANCHOR_KINDS}")
    if kind == "leaf":
        key = norm_ref(key)
    return f"{kind}-{key}"


# ------------------------------------------------------------------- the runs


def load_runs(root: Path = Path(".")) -> list[dict]:
    """The declared runs, or none.

    A missing `data/runs.json` is an empty list and not an error: it is a store,
    and "this book declares no runs" is a true statement about a corpus — the
    next book may have no List of Illustrations at all. That is the store rule
    (an absent *farm* refuses, an absent store is a silent empty); `edition runs`
    is where a malformed one is caught.
    """
    p = Path(root) / RUNS_JSON
    if not p.exists():
        return []
    doc = json.loads(p.read_text(encoding="utf-8"))
    return doc if isinstance(doc, list) else doc.get("runs", [])


def runs(root: Path = Path(".")) -> list[dict]:
    """Every run the edition can serve, declared and (later) derived.

    Today this is `load_runs` unchanged. It exists as its own name because chapter
    runs will arrive here, computed rather than written down, and every caller
    downstream is already pointed at the name that will carry both.
    """
    return load_runs(root)


def run_for(ref: str, root: Path = Path(".")) -> dict | None:
    """The run this scan belongs to, if any."""
    ref = norm_ref(ref)
    for r in runs(root):
        if ref in [norm_ref(x) for x in r.get("refs") or []]:
            return r
    return None


def store_for(run: dict, root: Path = Path(".")) -> dict:
    """A run's backing store, normalised to `{"source": …, "entries": [...]}`.

    The three apparatus files keep their entries under three different keys and
    `loi.json` under two at once; `KINDS` is where that is written down, so a
    renderer and the gate read one shape. Entries come out in the file's own
    order, `figures` before `plates`, which is the order the book prints them.
    """
    src = run.get("source")
    if not src:
        return {"source": {}, "entries": []}
    p = Path(root) / src
    if not p.exists():
        return {"source": {}, "entries": []}
    doc = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(doc, list):          # `toc.json`'s bare-list shape
        return {"source": {}, "entries": list(doc)}
    entries: list[dict] = []
    for key in (KINDS.get(run.get("kind")) or {}).get("entries", ()):
        entries.extend(doc.get(key) or [])
    return {"source": doc.get("source") or {}, "entries": entries}


def _authorities(root: Path) -> list[dict]:
    """The works `Authorities Quoted` records, or none.

    **Through the run rather than through `authorities.load`**, which raises on a
    missing file — rightly, since a CLI standing in the wrong directory must not
    read as an empty bibliography. The rules below are a different case: they run
    against whatever stores a tree holds, and a page generated where no
    bibliography exists should carry no citation links rather than fail to build.
    """
    run = next((r for r in runs(root) if r.get("kind") == "authorities"), {})
    return store_for(run, root)["entries"] if run else []


def sigla(root: Path = Path(".")) -> list[dict]:
    """The printed resolution table: `(name, volume, short title)` → work.

    What the List of Authorities Quoted *is*, and the table `citations.cited`
    resolves a footnote against. Read here for `authority_names`' reason — one
    store, one reader — and 52 rows over 34 printed sigla, because a siglum
    printed across several volumes is a row per volume.

    The 34 is not `authority_names`' 47. That set is every name Bogoras cites a
    work under; these are only the names carrying a printed siglum, and the 13
    in the difference are cited without one. The two were conflated here.
    """
    return authorities.sigla(_authorities(root))


def authority_names(root: Path = Path(".")) -> frozenset[str]:
    """The names Bogoras cites other people's work under.

    A cross-reference is only this book's if no authority stands in front of it,
    and `Authorities Quoted` is the store of exactly those names. Three callers
    need the same answer — `tei generate`, which refuses to mark another author's
    plate; `tei validate`, which re-derives that refusal; and the resolver, which
    declines to point a marked one at this book's leaf — so the store is read
    here rather than in each of them. `web/stores.authority_names` wraps this in
    the render cache and is where the keying lives.
    """
    return frozenset(figrefs.authority_names(_authorities(root)))


def entries_for(ref: str, root: Path = Path(".")) -> list[dict]:
    """The apparatus entries recorded as printed on this scan.

    **No fallback.** A leaf shows what the store says was printed on it, and a
    store that does not record a per-entry `ref` renders nothing rather than
    having the whole list attributed to one of its leaves — `edition runs`
    reports that store as unrenderable and says which field is missing. A branch
    this corpus would never exercise is worse than the absence it papers over.
    """
    ref = norm_ref(ref)
    run = run_for(ref, root)
    if run is None:
        return []
    return [e for e in store_for(run, root)["entries"]
            if e.get("ref") and norm_ref(e["ref"]) == ref]


# ------------------------------------------------------------- the folio index


def _as_folio(v) -> int | None:
    """A folio as an integer, or None. Roman front matter and `None` both fail
    here, which is correct: this index is keyed by the arabic folio the ToC's
    `page_start` uses, and a roman leaf is reached by its ref."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    s = str(v).strip()
    return int(s) if s.isdigit() else None


def folio_index(root: Path = Path(".")) -> dict[int, list[dict]]:
    """`{folio: [{"ref", "witness"}, …]}`, strongest witness first.

    Re-derived on every call from three independent witnesses and never persisted,
    which is what makes the two lower ranks admissible at all: they assert nothing
    on their own authority and fail rather than go stale.

      1. `tei`            the committed `<pb n>`. A human collated the page.
      2. `apparatus`      a store's own `ref`/`folio` pair. `authorities.json`
                          alone places folios 3-9 at `1-023`-`1-029`; a human read
                          those off the scan while keying the store.
      3. `running-title`  `context._running_title` over `gt/ocr/`, which lifts the
                          folio out of the head line or the quire marks.
                          Mechanical over adjudicated ground truth.

    Witness 3 is the expensive one — one ALTO parse per keyed page. Callers that
    run inside a server cache it on the store's content stamp (`web/stores.py`);
    the CLI pays it once per invocation.
    """
    from .context import _running_title, all_refs
    from .lines import page_lines

    out: dict[int, list[dict]] = {}
    seen: set[tuple[int, str]] = set()

    def add(folio, ref, witness):
        f = _as_folio(folio)
        if f is None:
            return
        ref = norm_ref(ref)
        if (f, ref) in seen:
            return
        seen.add((f, ref))
        out.setdefault(f, []).append({"ref": ref, "witness": witness})

    # The page's own `<pb n>`, read per file rather than through
    # `state.build_ledger`: the ledger folds heading state over `all_scans`, so it
    # requires the raster farm, and an index of what the corpus says about its own
    # page numbers has no business refusing on a clone with no `scans/`.
    for p in sorted((Path(root) / "tei").glob("chukchi-*.xml")):
        facts = _tei_facts(p)
        if facts is not None:
            add(facts.get("folio"), p.stem.removeprefix("chukchi-"), "tei")

    for run in runs(root):
        if not (KINDS.get(run.get("kind")) or {}).get("folio_of_leaf"):
            continue
        for e in store_for(run, root)["entries"]:
            if e.get("ref"):
                add(e.get("folio"), e["ref"], "apparatus")

    for ref in all_refs(root, "gt/ocr"):
        path = Path(root) / "gt/ocr" / f"chukchi-{norm_ref(ref)}.xml"
        try:
            rt = _running_title(page_lines(path, Path(root), ref=ref), ref, Path(root))
        except Exception:
            # A page whose ALTO will not parse is a page with no witness here.
            # It is `ocr check`'s finding, not this index's, and refusing to
            # build the whole index over one bad file would be the wrong trade.
            continue
        if rt:
            add(rt.get("folio"), ref, "running-title")

    for f in out:
        out[f].sort(key=lambda w: WITNESSES.index(w["witness"]))
    return out


# ---------------------------------------------------------------- the locator


def _page_url(ref: str) -> str:
    return f"/edition/page/{norm_ref(ref)}"


def _place(ref: str, root: Path, witness: str = "") -> dict:
    """Where a scan is served, and under what anchor: inside its run if it has
    one, else as its own page."""
    ref = norm_ref(ref)
    run = run_for(ref, root)
    if run is None:
        return {"url": _page_url(ref), "anchor": "", "ref": ref, "run": "",
                "witness": witness}
    return {"url": f"/edition/run/{run['id']}", "anchor": anchor("leaf", ref),
            "ref": ref, "run": run["id"], "witness": witness}


def locate(root: Path = Path("."), *, ref: str | None = None,
           folio: int | None = None, toc_id: str | None = None,
           index: dict | None = None, span: int = 8) -> dict:
    """Resolve one key to one place, or refuse and say what is nearby.

    Exactly one key. The three shapes it returns are the three honest answers:

        {"url", "anchor", "ref", "run", "witness"}   resolved
        {"candidates": [ … ]}                        two same-rank witnesses
        {"nearest": [ … ]}                           nothing witnesses this key

    `index` is the folio index, passed in by a caller that has one cached; it is
    built here otherwise. `span` bounds how far the `nearest` list reaches.
    """
    given = [k for k, v in (("ref", ref), ("folio", folio), ("toc_id", toc_id))
             if v is not None]
    if len(given) != 1:
        raise ValueError("locate takes exactly one of ref=, folio=, toc_id="
                         f" — got {given or 'none'}")
    root = Path(root)

    if ref is not None:
        return _place(ref, root)

    if toc_id is not None:
        entry = next((e for e in load_toc(root) if e.get("id") == toc_id), None)
        if entry is None:
            return {"nearest": [], "why": f"no ToC entry has id {toc_id!r}"}
        start = _as_folio(entry.get("page_start"))
        if start is None:
            return {"nearest": [],
                    "why": f"ToC entry {toc_id!r} records no page_start"}
        folio = start

    idx = folio_index(root) if index is None else index
    hits = idx.get(folio) or []
    if not hits:
        near = sorted(
            ({"folio": f, **_place(ws[0]["ref"], root, ws[0]["witness"])}
             for f, ws in idx.items() if abs(f - folio) <= span),
            key=lambda r: (abs(r["folio"] - folio), r["folio"]))
        return {"nearest": near, "folio": folio}

    top = [w for w in hits if w["witness"] == hits[0]["witness"]]
    if len(top) > 1:
        return {"candidates": [_place(w["ref"], root, w["witness"]) for w in top],
                "folio": folio}
    place = _place(top[0]["ref"], root, top[0]["witness"])
    if place["run"]:
        place["anchor"] = anchor("folio", folio)
    return place


# -------------------------------------------------------------------- the gate


def check(root: Path = Path(".")) -> dict:
    """`edition runs`' report: one row per run, plus every gate failure.

    Measurement never gates, so the per-leaf entry counts and the folio
    disagreements below `error` are reported whatever they say. What fails is a
    declaration that cannot be true: a run over a page the pipeline still owns, a
    span that contradicts its own store, a kind with no renderer.
    """
    from .zones import LEAF_KINDS, load_splits

    root = Path(root)
    declared = runs(root)
    errors: list[dict] = []
    warnings: list[dict] = []
    rows: list[dict] = []
    leaf_rows: list[dict] = []
    idx = folio_index(root)

    try:
        scans = set(all_scans(root))
    except Exception:
        scans = set()          # a clone with no `scans/`; ref existence unchecked
    splits = load_splits(root)
    exempt = {r for r, s in splits.items() if s in LEAF_KINDS}
    # The leaves whose content this repository holds parsed. A run is a span of
    # these and of nothing else.
    apparatus_leaves = {r for r, s in splits.items() if s == "apparatus"}

    claimed: dict[str, str] = {}
    for run in declared:
        rid = run.get("id") or "?"
        refs = [norm_ref(r) for r in run.get("refs") or []]
        kind = run.get("kind")

        if kind not in KINDS:
            errors.append({"run": rid, "rule": "unknown-kind",
                           "detail": f"{kind!r} is not one of {sorted(KINDS)}"})
        for r in refs:
            if scans and r not in scans:
                errors.append({"run": rid, "rule": "no-such-scan", "detail": r})
            # **`apparatus`, not merely exempt.** A run renders a store this
            # repository holds parsed, so its leaves are the ones a human ruled
            # *apparatus* — the printed Contents, List of Illustrations,
            # Authorities, Alphabet. A plate in a run would render as a list of
            # entries it does not have; the looser test could not say so.
            if r not in apparatus_leaves:
                errors.append({
                    "run": rid, "rule": "not-apparatus", "detail": r,
                    "why": f"a run's leaves must be ruled `apparatus`; {r} is "
                           + (f"ruled `{splits[r]}`" if r in splits
                              else "still the pipeline's")})
            if r in claimed and claimed[r] != rid:
                errors.append({"run": rid, "rule": "overlapping-runs",
                               "detail": f"{r} is also in {claimed[r]}"})
            claimed[r] = rid

        parts = {parse_ref(r)[0] for r in refs}
        idxs = sorted(parse_ref(r)[1] for r in refs)
        if len(parts) > 1 or (idxs and idxs != list(range(idxs[0], idxs[-1] + 1))):
            errors.append({"run": rid, "rule": "discontiguous",
                           "detail": " ".join(refs)})

        store = store_for(run, root)
        src_refs = [norm_ref(r) for r in (store["source"].get("refs") or [])]
        if src_refs and src_refs != refs:
            errors.append({
                "run": rid, "rule": "span-disagreement",
                "detail": f"runs.json {' '.join(refs)} vs "
                          f"{run.get('source')} source.refs {' '.join(src_refs)}"})

        entry_refs = {norm_ref(e["ref"]) for e in store["entries"] if e.get("ref")}
        if not entry_refs and store["entries"]:
            errors.append({
                "run": rid, "rule": "no-entry-provenance",
                "detail": f"{run.get('source')} records no per-entry `ref`, so "
                          "nothing can be attributed to a leaf"})
        elif entry_refs - set(refs):
            errors.append({
                "run": rid, "rule": "span-disagreement",
                "detail": "entries name scans outside the run: "
                          + " ".join(sorted(entry_refs - set(refs)))})

        # **Where the plates are, reported and not gated.** A plate carries no
        # number on its own leaf, so `figures.by_plate` derives it by matching
        # the printed caption against the keyed one; the count is a measurement
        # and belongs beside the run rather than in the error list. What would
        # be wrong is a plate resolving to *two* leaves, and that resolves to
        # none by construction — the page then prints it plain.
        located = ""
        plates = [e for e in store["entries"] if e.get("kind") == "plate"]
        if plates:
            from .figures import by_plate
            located = f"{len(by_plate(plates, root))}/{len(plates)}"

        rows.append({"run": rid, "kind": kind, "title": run.get("title") or "",
                     "span": f"{refs[0]}-{refs[-1]}" if refs else "",
                     "leaves": len(refs), "entries": len(store["entries"]),
                     "plates_located": located})
        for r in refs:
            leaf_rows.append({
                "run": rid, "ref": r,
                "folio": folio_of(r, idx) or "",
                "entries": sum(1 for e in store["entries"]
                               if e.get("ref") and norm_ref(e["ref"]) == r)})

    for f, ws in sorted(idx.items()):
        top = [w for w in ws if w["witness"] == ws[0]["witness"]]
        if len(top) > 1:
            errors.append({
                "run": "", "rule": "folio-collision",
                "detail": f"folio {f}: {', '.join(w['ref'] for w in top)} "
                          f"all claim it as {ws[0]['witness']}"})
        elif len({w["ref"] for w in ws}) > 1:
            warnings.append({
                "run": "", "rule": "folio-disagreement",
                "detail": f"folio {f}: "
                          + ", ".join(f"{w['ref']} ({w['witness']})" for w in ws)})

    # **The other direction, which nothing checked.** `apparatus` says this leaf's
    # content lives parsed in a store rather than in the TEI — and the run is what
    # names *which* store. A leaf ruled `apparatus` that no run covers is therefore
    # a page the edition can say nothing about and will render as a bare scan: the
    # ruling promises a reading nobody supplied. The run half of this pair has been
    # checked since runs existed; only the half where the store is silent was
    # missing, which is the half that fails quietly.
    for r in sorted(apparatus_leaves - claimed.keys(), key=parse_ref):
        errors.append({
            "run": "", "rule": "apparatus-not-in-run", "detail": r,
            "why": "ruled `apparatus`, so its content is supposed to be held "
                   "parsed, but no run in data/runs.json names it and nothing "
                   "says which store that would be"})

    # Every kind counted, whether or not it is one this report has anything else
    # to say about — a census beside the errors, so the vocabulary's shape is
    # visible without a second command. Measurement, never a gate.
    census = {k: sum(1 for s in splits.values() if s == k) for k in LEAF_KINDS}

    editor, leaf_errs = _check_leaves(root, exempt)
    for r in leaf_rows:
        r["editor"] = (editor.get(r["ref"]) or {}).get("file", "")
    return {"runs": rows, "leaves": leaf_rows,
            "editor_leaves": [{"ref": k, **v} for k, v in sorted(editor.items())],
            "leaf_kinds": [{"kind": k, "leaves": n} for k, n in census.items()],
            "errors": errors + leaf_errs, "warnings": warnings,
            "folios": len(idx)}


#: How far an editor's leaf may differ in shape from the scan it replaces. A
#: touch-up is a rescale and a filter; a different aspect ratio is a crop or a
#: stretch, which makes it a different leaf rather than a better one.
ASPECT_TOL = 0.005


def folio_of(ref: str, index: dict) -> int | None:
    """The folio this leaf is recorded at, by whatever names it. None where
    nothing does, which for the front matter is most leaves."""
    ref = norm_ref(ref)
    for folio, ws in index.items():
        if any(w["ref"] == ref for w in ws):
            return folio
    return None


def _check_leaves(root: Path, exempt: set[str]) -> tuple[dict, list]:
    """Every file in `gt/page-img/`, and what is wrong with it.

    The scale is reported whatever it is — measurement never gates, and knowing a
    leaf is served at 2x is worth having. What fails is a file that will never be
    used (the page is not exempt, so `leaf_source` ignores it) or one that is not
    the same leaf.
    """
    from .edition_ui import LEAF_EXTS, PAGE_IMG, scan_for

    rows, errors = {}, []
    d = Path(root) / PAGE_IMG
    for p in sorted(d.glob("chukchi-*")) if d.is_dir() else []:
        if p.suffix not in LEAF_EXTS:
            continue
        ref = norm_ref(p.stem.removeprefix("chukchi-"))
        row = {"file": p.name, "scale": "", "aspect": ""}
        if ref not in exempt:
            errors.append({
                "run": "", "rule": "leaf-not-exempt", "detail": p.name,
                "why": "`leaf_source` serves an editor's leaf only for a page a "
                       "human ruled out of the transcription tracks, so this "
                       "file is ignored rather than quietly honoured. Any leaf "
                       "kind qualifies — what licenses a hand-worked leaf is "
                       "that the page left the tracks, not which sort it is"})
        row.update(_leaf_shape(p, scan_for(ref, Path(root))))
        if row["aspect"] and abs(float(row["aspect"]) - 1.0) > ASPECT_TOL:
            errors.append({
                "run": "", "rule": "leaf-reshaped", "detail": p.name,
                "why": f"aspect {row['aspect']} against the scan's — a crop or a "
                       "stretch is a different leaf, not an enhancement"})
        rows[ref] = row
    return rows, errors


def _leaf_shape(leaf: Path, scan: Path) -> dict:
    """`scale` and `aspect` against the scan, where both are rasters on disk.

    A vector leaf has no pixel size to compare and says so rather than being
    silently passed: `""` here means unmeasured, never measured-and-fine.
    """
    if leaf.suffix == ".svg":
        return {"scale": "vector", "aspect": ""}
    try:
        from PIL import Image

        with Image.open(leaf) as a, Image.open(scan) as b:
            return {"scale": f"{a.size[0] / b.size[0]:.3f}",
                    "aspect": f"{(a.size[0] / a.size[1]) / (b.size[0] / b.size[1]):.4f}"}
    except Exception:
        return {"scale": "", "aspect": ""}
