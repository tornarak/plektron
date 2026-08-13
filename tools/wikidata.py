#!/usr/bin/env python3
"""Propose Wikidata identities for unlocated entities, and derive `geo:` from
the ones a human has adopted.

**Why this is two verbs and not one.** The expensive, error-prone half of
locating a place is deciding *which* place it is; the coordinate that follows is
arithmetic. Collapsing the two would produce exactly the failure this project is
organised against — a coordinate that looks measured and is actually a search
engine's first result. So `propose` reports candidates and writes nothing, a
human writes the `link: wikidata:Q…` they believe, and `fill` derives the point
from that link alone. The authored fact is the *identity*; the coordinate is
re-derivable from it and fails rather than goes stale, which is the same
argument `#gt` and `#mz` rest on in the TEI.

**Geometry is the second witness, and it is why `propose` is worth running at
all.** Natural Earth's `King I.` is King Island, *Tasmania* — 144 E, 40 S — and
a name match alone adopts it without a murmur. Every candidate coordinate here
is tested against the shapes `data/geo/` already holds: is it in the edition's
window, is it inside the shape of the entity's own `within:` parent, and which
store shapes contain it at all. A candidate that lands inside the peninsula its
entry already claims it is on has been confirmed by something other than its
spelling.

**It never gates and it never adopts.** `propose` prints; `fill` needs
`--commit`, and will not overwrite an existing `geo:` without `--replace` — a
point a human read off a chart outranks one a query returned, and silently
replacing the first with the second is how provenance is lost.

**`fill` over an already-located entry is an audit, not a no-op.** It fetches
and compares anyway, reporting the kilometres between the entry's point and
Wikidata's. Thirty-odd points in this store came off Operational Navigation
Charts and had never been checked against anything; the chart and Wikidata share
no ancestor, so 0.5 km apart on Anadyr is a real corroboration and a hundred
would be a real finding. Rows are marked `+` would write, `~` would replace,
`=` compared only.

Wikidata is a live external source, so this is a `tools/` script and not a
harness verb: the harness is offline and deterministic over what is committed,
which is the same split `build_geo.py` sits on.

    tools/wikidata.py propose --unlocated          73 entries, one query, 3 s
    tools/wikidata.py propose place:cape-navarin   small runs also prefix-search
    tools/wikidata.py fill --all                   audit + what would be written
    tools/wikidata.py fill --all --commit
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness import geo  # noqa: E402
from harness.entities import load  # noqa: E402

API = "https://www.wikidata.org/w/api.php"

#: Wikimedia asks every client to identify itself: the project and its purpose,
#: no personal contact — that is the user's to add if they want to be reachable.
UA = "machine-press/0.1 (Bogoras, The Chukchee: annotated digital edition)"

GEO_CLASSES = ("place", "land", "water", "river")

#: Words in a Wikidata description that agree with an entity's class.
#:
#: **The four-class split is what makes this possible, and it is the second
#: disambiguator after geometry.** Searching `Хатырка` returns the village and
#: the river, both real, both in the window, both inside the same shapes — no
#: coordinate test can separate them because they are in the same place. The
#: class can: `river:vatirkan` wants the one described as a river and
#: `place:ilpi` wants the settlement, and those are two different entries in
#: this store precisely because Bogoras uses the name for both. Same for Karaga,
#: Gizhiga, Anadyr, Kolyuchin — the double-duty names this edition is full of.
#:
#: A miss is not a rejection. Descriptions are free text written by strangers,
#: so an unmatched candidate is ranked below a matched one and still printed.
CLASS_WORDS = {
    "place": ("settlement", "village", "town", "city", "locality", "cape",
              "fort", "populated place", "human settlement", "headland"),
    "land": ("island", "peninsula", "range", "mountain", "upland", "plateau",
             "region", "district", "lowland", "hill", "archipelago", "massif"),
    "water": ("bay", "sea", "gulf", "strait", "sound", "lake", "ocean",
              "lagoon", "inlet", "fjord"),
    "river": ("river", "stream", "tributary", "creek", "watercourse"),
}

#: **An unauthenticated sweep gets 429'd**, and a 429 would otherwise surface as
#: an entry reading "no candidate carries a coordinate" — a throttle rendered as
#: a finding, which is the worst way for this tool in particular to fail. So the
#: retry is on the session and `respect_retry_after_header` lets the server set
#: the pace rather than a constant here guessing at it. `maxlag` is Wikimedia's
#: own convention on the other side of the same courtesy: it asks the API to
#: refuse rather than queue when the replicas are behind.
#: The pause is the *first* half of that and the retry is the fallback: getting
#: throttled and recovering costs more wall clock than not getting throttled, and
#: a sweep of this store is a few hundred calls either way.
_RETRY = Retry(total=5, backoff_factor=1.5,
               status_forcelist=(429, 500, 502, 503, 504),
               allowed_methods=("GET",), respect_retry_after_header=True)
PAUSE = 0.25

SESSION = requests.Session()
SESSION.headers["User-Agent"] = UA
SESSION.mount("https://", HTTPAdapter(max_retries=_RETRY))


def _get(params: dict) -> dict:
    r = SESSION.get(API, params={**params, "format": "json", "maxlag": "5"},
                    timeout=30)
    r.raise_for_status()
    time.sleep(PAUSE)
    got = r.json()
    if "error" in got:
        raise RuntimeError(got["error"].get("info", got["error"]))
    return got


SPARQL = "https://query.wikidata.org/sparql"

#: Every name in the sweep, asked in one query instead of one call each.
#:
#: **The per-name search API cannot do a sweep of this store.** It is right for a
#: handful of entries and it is what `--terms` still drives; asked three hundred
#: times it takes a hard `429` — immediate, with no `Retry-After`, so the retry
#: falls back to its own backoff and each entry costs forty seconds. That is not
#: a throttle to tune around, it is the wrong shape of request: three hundred
#: round trips to ask seventy-three questions.
#:
#: A `VALUES` block is the right shape. One query, every name at once, matched
#: against labels *and* aliases in any language — which is what makes the store's
#: own Russian aliases work as identifications, `Хатырка` and `Тилечики` finding
#: what `Vatɪˊrkan` and `Tɪˊḷḷɪran` never will. Only items with a `P625` come
#: back, since an item with no coordinate cannot answer the question being asked.
#:
#: **Exact match, and that is the trade.** `wbsearchentities` does prefixes, so
#: it finds `Тиличики` from `Тилечик`; this does not. The sweep is for coverage
#: and the per-name path stays for the ones it misses — which are reported as
#: misses, not as absences.
_SPARQL_Q = """
SELECT ?item ?name ?coord ?desc ?article WHERE {
  VALUES ?name { %s }
  ?item rdfs:label|skos:altLabel ?name .
  ?item wdt:P625 ?coord .
  OPTIONAL { ?item schema:description ?desc FILTER(LANG(?desc) = "en") }
  OPTIONAL {
    ?article schema:about ?item ;
             schema:isPartOf <https://en.wikipedia.org/> .
  }
}
"""


def sparql_names(names: list[str]) -> dict[str, list[dict]]:
    """`{searched name: [candidate, …]}` for every name at once.

    Rows carry the same keys `entities()` returns, so the two are
    interchangeable downstream — the sweep uses this and a single lookup uses
    that, and nothing after them knows which it got.
    """
    if not names:
        return {}
    values = " ".join(f'"{n}"@{lg}' for n, lg in
                      {(n, "ru" if any("Ѐ" <= c <= "ӿ" for c in n) else "en")
                       for n in names})
    r = SESSION.get(SPARQL, params={"query": _SPARQL_Q % values},
                    headers={"Accept": "application/sparql-results+json"},
                    timeout=120)
    r.raise_for_status()
    out: dict[str, list[dict]] = {}
    for b in r.json()["results"]["bindings"]:
        lat, lon = _wkt(b["coord"]["value"])
        if lat is None:
            continue
        qid = b["item"]["value"].rsplit("/", 1)[-1]
        name = b["name"]["value"]
        row = {"qid": qid, "label": name,
               "desc": b.get("desc", {}).get("value", ""),
               "geo": (lat, lon),
               "enwiki": (b.get("article", {}).get("value", "")
                          .rsplit("/", 1)[-1].replace("_", " "))}
        bucket = out.setdefault(name, [])
        if not any(x["qid"] == qid for x in bucket):
            bucket.append(row)
    return out


def _wkt(v: str):
    """`Point(lon lat)` → `(lat, lon)`. Anything else is not a coordinate."""
    if not v.startswith("Point("):
        return None, None
    try:
        lon, lat = v[6:].rstrip(")").split()
        return float(lat), float(lon)
    except ValueError:
        return None, None


def search(term: str, lang: str = "en", limit: int = 6) -> list[str]:
    """QIDs matching `term`, best first. Names only — no coordinates yet."""
    try:
        r = _get({"action": "wbsearchentities", "search": term,
                  "language": lang, "uselang": lang, "type": "item",
                  "limit": limit})
    except Exception as e:                                # noqa: BLE001
        print(f"  ! search {term!r} ({lang}): {e}", file=sys.stderr)
        return []
    return [h["id"] for h in r.get("search", [])]


def entities(qids: list[str]) -> dict:
    """Label, description, coordinate and en-wiki title for each QID.

    Batched fifty at a time, which is the API's own limit — one call per entity
    name would be several hundred round trips for this store.
    """
    out: dict[str, dict] = {}
    for i in range(0, len(qids), 50):
        chunk = qids[i:i + 50]
        try:
            r = _get({"action": "wbgetentities", "ids": "|".join(chunk),
                      "props": "labels|descriptions|claims|sitelinks",
                      "languages": "en|ru", "sitefilter": "enwiki"})
        except Exception as e:                            # noqa: BLE001
            print(f"  ! fetch {chunk[0]}…: {e}", file=sys.stderr)
            continue
        for qid, ent in (r.get("entities") or {}).items():
            if "missing" in ent:
                continue
            coord = None
            for c in (ent.get("claims") or {}).get("P625", []):
                v = (c.get("mainsnak") or {}).get("datavalue", {}).get("value")
                if v:
                    coord = (v["latitude"], v["longitude"])
                    break
            labels, descs = ent.get("labels") or {}, ent.get("descriptions") or {}
            out[qid] = {
                "qid": qid,
                "label": (labels.get("en") or labels.get("ru") or {}).get("value", ""),
                "desc": (descs.get("en") or descs.get("ru") or {}).get("value", ""),
                "geo": coord,
                "enwiki": ((ent.get("sitelinks") or {})
                           .get("enwiki") or {}).get("title", ""),
            }
    return out


# ------------------------------------------------------------------ geometry


#: Mean Earth radius. A sphere is right to well under a kilometre at this
#: latitude, and the question here is "same village or not", not geodesy.
EARTH_KM = 6371.0


def _own_mark(cls: str, km: float) -> str:
    """How to read a gap between the entry's `geo:` and a candidate's.

    **It is a finding for a `place:` and noise for anything else.** A point
    entity *is* its coordinate, so two sources 0.5 km apart on Anadyr corroborate
    each other and two sources 100 km apart cannot both be the village. A
    `land:`, `water:` or `river:` point is a nominal centre — somebody's idea of
    the middle of a peninsula — and the first run of this check reported the
    Chukchi Peninsula as 45.2 km out, which says nothing at all about either
    source. Same number, opposite meaning, so the row says which.
    """
    return (f"{km} km from the entry's own point" if cls == "place"
            else f"{km} km from the entry's nominal centre (not a finding)")


def _km(a, b) -> float:
    """Great-circle kilometres between two `(lat, lon)` pairs.

    Haversine on the raw longitudes, which needs no antimeridian handling: the
    difference enters only as `sin(dlon/2)²`, so 179.9 against −179.9 is the
    0.2° apart that it is and not 359.8.
    """
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * EARTH_KM * math.asin(min(1.0, math.sqrt(h)))


def _parent_shape(ident: str, store: dict) -> str:
    """The nearest ancestor's `area:` — what a candidate should fall inside.

    Walks up rather than reading `within:` once, because the immediate parent is
    very often shapeless: a village's parent is Chukotka, which no source draws,
    and its grandparent is Northeast Siberia, which none draws either. Stopping
    at the first `within:` would report "no parent shape" for most of the store
    and throw away the check.
    """
    seen, at = set(), store.get(ident, {}).get("within", "")
    while at and at not in seen:
        seen.add(at)
        rec = store.get(at)
        if rec is None:
            return ""
        if rec.get("area"):
            return rec["area"]
        at = rec.get("within", "")
    return ""


def _tests(pt, store: dict, root: Path, ident: str, idx: dict,
           docs: dict) -> dict:
    """What the store's geometry says about one candidate coordinate.

    Four answers, deliberately kept apart. `in_window` is the coarse filter
    that would have caught King Island, Tasmania on its own. `parent` is the
    strong one — the entity's own authored `within:` chain, confirmed or
    contradicted by a source that has never seen it. `inside` is the open
    question, "what does this point fall in at all", which is the useful answer
    where the entry has no parent yet and the one that can suggest a `within:`.

    **`own_km` is the sharpest of the four and applies only where the entry is
    already located.** Thirty-odd points in this store were read off Operational
    Navigation Charts by a human (`place:achchen` says so in its gloss), and
    until now nothing had ever checked them against a second source. Two points
    for the same village agreeing to within a kilometre is a real corroboration
    — the chart and Wikidata share no ancestor — and a hundred-kilometre gap
    says one of them is a different place, which is precisely the finding no
    amount of re-reading the same chart could produce. It is why `propose` and
    `fill` are worth pointing at *located* entities and not only at the gaps.

    **Kilometres, not degrees**, unlike every other distance in this codebase.
    Those measure a point against a polygon, where degrees are the polygon's own
    units; this measures two points, and a degree of longitude at 65°N is 47 km
    against a degree of latitude's 111. Reporting one number for both would make
    an east-west disagreement read as less than half the error it is.
    """
    lat, lon = pt
    slon = geo._shifted(lon, idx)
    w, s, e, n = idx["window"]
    own = (store.get(ident) or {}).get("geo")
    got = {"in_window": bool(s <= lat <= n and w <= slon <= e),
           "parent": "", "parent_out": None, "inside": [],
           "own_km": round(_km(own, pt), 1) if own else None}

    def doc(i):
        if i not in docs:
            docs[i] = geo.shape(i, root)
        return docs[i]

    area = _parent_shape(ident, store)
    if area:
        d = doc(area)
        if d:
            got["parent"] = area
            if geo.in_shape((slon, lat), d):
                got["parent_out"] = 0.0
            else:
                got["parent_out"] = round(geo.distance_to((slon, lat), d), 3)

    for i, row in sorted(idx["shapes"].items()):
        # **The parent is not listed again here.** It has its own mark, which
        # says more — `in region:chukchi-peninsula` is an answer about the
        # entry's authored `within:`, where `inside region:chukchi-peninsula` is
        # an answer about the store at large. Printing both produced
        # "in X; inside X" on every candidate that satisfied the strong test,
        # i.e. exactly on the good ones.
        if i == area or row.get("kind") == "base":
            continue
        b = row.get("bounds")
        if b and not (b[0] - 0.2 <= slon <= b[2] + 0.2
                      and b[1] - 0.2 <= lat <= b[3] + 0.2):
            continue
        d = doc(i)
        if d and geo.in_shape((slon, lat), d):
            got["inside"].append(i)
    return got


# ------------------------------------------------------------------- actions


def _terms(rec: dict) -> list[tuple[str, str]]:
    """`(term, language)` to search on, canonical first.

    Both scripts, because the Russian alias is very often the *only* modern
    identification the store holds — `Тилечики` finds Тиличики where `Tɪˊḷḷɪran`
    finds nothing at all. Tier-1 forms are searched too and are expected to miss;
    they cost one call and a miss is information.
    """
    out = [(rec["canonical"], "en")]
    for a in rec["aliases"]:
        lang = "ru" if any("Ѐ" <= c <= "ӿ" for c in a["form"]) else "en"
        out.append((a["form"], lang))
    seen, uniq = set(), []
    for t, lg in out:
        if t and t not in seen:
            seen.add(t)
            uniq.append((t, lg))
    return uniq


def run_propose(a) -> int:
    root = Path(a.root)
    store = load(root)
    idx = geo.index(root)
    docs: dict = {}

    if a.unlocated:
        idents = sorted(i for i, r in store.items()
                        if r["class"] in GEO_CLASSES
                        and not (r["geo"] or r["area"] or r["frame"]))
    else:
        idents = list(a.idents)
    if not idents:
        print("nothing to propose for", file=sys.stderr)
        return 2

    # **Two lookups, and which ones ran is printed.** SPARQL asks every name in
    # one query and matches labels and aliases *exactly*; the per-name API does
    # prefixes, which is how "Kolyuchin" reaches "Kolyuchin Island" and
    # "Тилечик" reaches "Тиличики". Neither subsumes the other. But the API
    # costs a round trip per name and takes a hard 429 somewhere past a hundred,
    # so it runs only for a run small enough to afford it — and the header says
    # so, because an entry with no candidates means something different under
    # each, and a silence that does not say which question was asked is the
    # thing this whole tool exists to avoid.
    wanted = {i: _terms(store[i])[:a.terms] for i in idents if i in store}
    use_api = len(idents) <= a.api_limit
    print(f"# {len(idents)} entit(ies), against the window "
          f"{' '.join(f'{v:g}' for v in idx['window'])}")
    print("# lookup: SPARQL exact label/alias match"
          + (" + per-name prefix search" if use_api else
             f" only — over {a.api_limit} entries the prefix search is "
             f"rate-limited; name them explicitly for that"))
    try:
        pool = sparql_names([t for ts in wanted.values() for t, _lg in ts])
    except Exception as e:                                    # noqa: BLE001
        print(f"  ! SPARQL: {e}", file=sys.stderr)
        pool = {}
    print()

    for ident in idents:
        rec = store.get(ident)
        if rec is None:
            print(f"{ident}\n  ! no such entity\n")
            continue
        rows = {}
        for term, _lang in wanted.get(ident, []):
            for r in pool.get(term, []):
                rows.setdefault(r["qid"], r)
        if use_api:
            qids = [q for term, lang in wanted.get(ident, [])
                    for q in search(term, lang) if q not in rows]
            rows.update(entities(qids))

        print(f"{ident} — {rec['canonical']}"
              + (f"   within: {rec['within']}" if rec["within"] else ""))
        cands = [(r, _tests(r["geo"], store, root, ident, idx, docs))
                 for r in rows.values() if r["geo"]]
        if not cands:
            print("  (no candidate carries a coordinate)\n")
            continue
        # In-window first, then agreeing with the entity's class, then nearest
        # to the parent the entry already claims, then whatever the store
        # contains it in. The ordering *is* the finding: eleven King Islands
        # with the Alaskan one buried sixth is the same list as ten rejects and
        # one survivor, and only one of the two is readable.
        words = CLASS_WORDS.get(rec["class"], ())
        for r, t in cands:
            blob = f"{r['desc']} {r['label']}".lower()
            t["class_match"] = any(w in blob for w in words)
        # Where the entry is already located, its own point outranks everything
        # below it: two sources naming the same coordinate is a stronger answer
        # than any description or containment test, and the nearest candidate is
        # the one being corroborated.
        cands.sort(key=lambda rt: (not rt[1]["in_window"],
                                   rt[1]["own_km"] if rt[1]["own_km"] is not None
                                   else 0,
                                   not rt[1]["class_match"],
                                   rt[1]["parent_out"] if rt[1]["parent"] else 9e9,
                                   -len(rt[1]["inside"])))
        # Everything in the window, or — where nothing is — the best single row,
        # so an entry with no plausible candidate still shows what it did find
        # rather than a silence indistinguishable from "no results".
        shown = ([rt for rt in cands if rt[1]["in_window"]] or cands[:1]
                 if not a.all_candidates else cands)
        hidden = len(cands) - len(shown)
        for r, t in shown:
            lat, lon = r["geo"]
            marks = []
            if not t["in_window"]:
                marks.append("OUTSIDE WINDOW")
            if t["own_km"] is not None:
                marks.append(_own_mark(rec["class"], t["own_km"]))
            marks.append(f"reads as {rec['class']}:" if t["class_match"]
                         else f"NOT described as a {rec['class']}:")
            if t["parent"]:
                marks.append("in " + t["parent"] if t["parent_out"] == 0
                             else f"{t['parent_out']}° from {t['parent']}")
            if t["inside"]:
                marks.append("inside " + " ".join(t["inside"]))
            print(f"  {r['qid']:10} {lat:>9.4f} {lon:>10.4f}  {r['label'][:34]:34}"
                  f"  {r['desc'][:44]}")
            print(f"  {'':10} {'':>9} {'':>10}  {'; '.join(marks) or '—'}")
            # **The QID line prints whether or not there is an article.** It is
            # the one `fill` reads; a bare Wikidata item with a coordinate and no
            # Wikipedia page is an ordinary and useful result, and printing the
            # pair only when both exist quietly hid Cape Navarin.
            wp = (f"link: wikipedia:{r['enwiki'].replace(' ', '_')}  "
                  if r["enwiki"] else "")
            print(f"  {'':10} {wp}link: wikidata:{r['qid']}")
        if hidden:
            print(f"  {'':10} ({hidden} further candidate(s) outside the "
                  f"window, hidden — --all-candidates shows them)")
        print()
    print("report only — nothing was written. Author the `link:` lines you "
          "believe, then `tools/wikidata.py fill --all --commit`.")
    return 0


def run_fill(a) -> int:
    """`geo:` derived from an authored `link: wikidata:Q…`, and from nothing else."""
    from harness.cli._entity import _set_field

    root = Path(a.root)
    store = load(root)
    idents = (sorted(i for i, r in store.items() if r["class"] in GEO_CLASSES)
              if a.all else list(a.idents))

    todo = []
    for ident in idents:
        rec = store.get(ident)
        if rec is None:
            print(f"{ident}: no such entity", file=sys.stderr)
            continue
        qid = next((v.partition(":")[2] for v in rec["links"]
                    if v.startswith("wikidata:")), "")
        if not qid:
            continue
        # **An entry that already has a point is fetched anyway.** It used to be
        # skipped with one line, which threw away the most valuable thing here:
        # thirty-odd points in this store came off a chart, and comparing them
        # against a source with no common ancestor is a second witness on work
        # that has never had one. Whether it *writes* is still gated by
        # `--replace`; the comparison is free and always reported.
        todo.append((ident, rec, qid))

    if not todo:
        print("nothing to fill")
        return 0

    rows = entities([q for _i, _r, q in todo])
    idx = geo.index(root)
    docs: dict = {}
    wrote = held = 0
    for ident, rec, qid in todo:
        got = rows.get(qid)
        if not got or not got["geo"]:
            print(f"{ident:30} {qid:10} no P625 coordinate — left alone")
            continue
        lat, lon = got["geo"]
        t = _tests(got["geo"], store, root, ident, idx, docs)
        note = []
        if not t["in_window"]:
            note.append("OUTSIDE WINDOW")
        if t["own_km"] is not None:
            note.append(_own_mark(rec["class"], t["own_km"]))
        if t["parent"]:
            note.append("in " + t["parent"] if t["parent_out"] == 0
                        else f"{t['parent_out']}° from {t['parent']}")
        # A located entry is a *comparison*, not a pending write, and the row
        # says which it is — otherwise a clean audit line reads as a fill that
        # `--commit` is about to make.
        act = ("=" if rec["geo"] and not a.replace
               else "~" if rec["geo"] else "+")
        print(f"{act} {ident:30} {qid:10} {lat:>9.4f} {lon:>10.4f}  "
              f"{'; '.join(note) or '—'}")
        if rec["geo"] and not a.replace:
            held += 1
            continue
        if a.commit:
            p = Path(rec["path"])
            text = _set_field(p.read_text(encoding="utf-8"), "geo",
                              f"{lat:g} {lon:g}")
            from harness.entities import parse
            parse(text, where=str(p))
            p.write_text(text, encoding="utf-8")
            wrote += 1

    print("\n+ would be written   ~ would replace an existing point   "
          "= compared only")
    print(f"{held} already located and left alone (--replace overwrites)"
          if held else "")
    print(f"{wrote} written" if a.commit else "report only; --commit writes")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=".", help="repo root (default .)")
    sub = ap.add_subparsers(dest="action", required=True)

    p = sub.add_parser("propose", help="candidate identities, tested against "
                                       "the shapes the store already holds")
    p.add_argument("idents", nargs="*")
    p.add_argument("--unlocated", action="store_true",
                   help="every geographical entry with no geo:, area: or frame:")
    p.add_argument("--terms", type=int, default=4,
                   help="how many of an entry's names to search (default 4)")
    p.add_argument("--api-limit", type=int, default=12,
                   help="up to this many entities, the per-name prefix search "
                        "runs as well as the one SPARQL query (default 12). "
                        "Above it only SPARQL does: the prefix search is a "
                        "round trip per name and takes a hard 429 on a sweep")
    p.add_argument("--all-candidates", action="store_true",
                   help="show the ones outside the edition's window too. They "
                        "are hidden by default because a common English name "
                        "returns a dozen of them and the rejects are the noise")
    p.set_defaults(fn=run_propose)

    p = sub.add_parser("fill", help="geo: from an authored link: wikidata:Q…")
    p.add_argument("idents", nargs="*")
    p.add_argument("--all", action="store_true")
    p.add_argument("--replace", action="store_true",
                   help="overwrite an existing geo:. A point a human read off a "
                        "chart outranks one a query returned")
    p.add_argument("--commit", action="store_true")
    p.set_defaults(fn=run_fill)

    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
