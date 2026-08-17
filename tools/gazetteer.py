#!/usr/bin/env python3
"""Propose gazetteer identities for unlocated entities, and derive `geo:` from
the ones a human has adopted.

**Two sources, because neither has what the other has.** Wikidata is live, rich
and uneven — it knows Khatyrka is both a village and a river, and it has never
heard of Пусторецк. **GeoNames** is a flat file, offline, and carries the small
Siberian features the book is actually full of: 2,636 bays, 2,764 capes and
2,102 *abandoned* settlements inside this edition's window alone, each with a
typed feature code and a list of alternate names in Russian. Between them they
answer nearly the whole store; separately, each leaves a third of it dark.

**Why this is two verbs and not one.** The expensive, error-prone half of
locating a place is deciding *which* place it is; the coordinate that follows is
arithmetic. Collapsing the two would produce exactly the failure this project is
organised against — a coordinate that looks measured and is actually a search
engine's first result. So `propose` reports candidates and writes nothing, a
human writes the `link: wikidata:Q…` or `link: geonames:…` they believe, and
`fill` derives the point from that link alone. The authored fact is the
*identity*; the coordinate is re-derivable from it and fails rather than goes
stale, which is the same argument `#gt` and `#mz` rest on in the TEI.

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

**`fill` over an already-located entry is an audit, not a no-op.** It looks the
identity up anyway and reports the kilometres between the entry's point and the
gazetteer's. Thirty-odd points in this store came off Operational Navigation
Charts and had never been checked against anything; the chart and the gazetteer
share no ancestor, so 0.5 km apart on Anadyr is a real corroboration and a
hundred would be a real finding. Rows are marked `+` would write, `~` would
replace, `=` compared only.

These are outside sources — one live, one a download — so this is a `tools/`
script and not a harness verb: the harness is offline and deterministic over
what is committed, which is the same split `build_geo.py` sits on.
`scratch/geonames/window.tsv` is built by `--build-window` from the country
dumps, and is the same reduce-once-then-match-locally shape.

    tools/gazetteer.py --build-window              cut RU/US dumps to the window
    tools/gazetteer.py propose --unlocated         73 entries, seconds
    tools/gazetteer.py propose place:cape-navarin  small runs also prefix-search
    tools/gazetteer.py fill --all                  audit + what would be written
    tools/gazetteer.py fill --all --commit
"""
from __future__ import annotations

import argparse
import math
import sys
import time
import unicodedata
from functools import lru_cache
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


#: **`maxlag` was here and is gone, and the reason is worth keeping.** It is a
#: write-side courtesy: it asks the API to refuse while the replicas are behind.
#: At 5 it refused constantly — the lag is routinely half a minute — and the
#: refusal reached the caller as "no coordinate", a failed lookup rendered as a
#: fact about the world. Exactly the defect the 429 comment above describes,
#: reintroduced a few lines below it by a politeness knob.
#:
#: Raising it did not help, and the error says why: the lag reported is
#: `wdqs1013`'s, the *Query Service*, which has nothing to do with whether
#: `wbgetentities` returns a correct record. It was guarding the wrong thing.
#: The courtesy that does apply here is the pause and the 429 backoff, which
#: stay. The lasting fix is one file over: a failed fetch is now recorded as
#: `failed` and printed as LOOKUP FAILED, so no outage can ever again be read as
#: an absence.
def _get(params: dict) -> dict:
    r = SESSION.get(API, params={**params, "format": "json"}, timeout=30)
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


# --------------------------------------------------------------- GeoNames
#
# A flat file, matched locally, and it answers what Wikidata cannot: the small
# named things. Inside this edition's window its dumps hold 2,636 `BAY`, 2,764
# `CAPE` and 2,102 `PPLQ` — *abandoned* populated places, which is the category
# Gizhiginsk and Zashiversk belong to and which no live encyclopedia bothers to
# carry.

GEONAMES = Path("scratch/geonames")
WINDOW_TSV = "window.tsv"

#: GeoNames feature codes, grouped by the entity class each answers.
#:
#: **This is a typed check where Wikidata's is a textual one.** `CLASS_WORDS`
#: greps an English description written by a stranger; this reads a code from a
#: controlled vocabulary the source maintains. So a GeoNames candidate whose
#: code disagrees with the entity's class is a much stronger negative than a
#: Wikidata description that happens not to contain the right noun — and a
#: `BAY` under a `water:` is a much stronger positive.
#:
#: `CAPE` and `PT` sit under `place:` on purpose: a headland is a point on the
#: ground, which is what this edition's `place:` means, and filing them with the
#: regions would put Cape Dezhnev in the same class as Kamchatka.
FCODES = {
    "place": {"PPL", "PPLA", "PPLA2", "PPLA3", "PPLA4", "PPLC", "PPLF",
              "PPLG", "PPLL", "PPLQ", "PPLR", "PPLS", "PPLW", "PPLX",
              "STLMT", "CAPE", "PT", "FRM", "MSTY", "MN", "RUIN"},
    # `ADM*` is here and not under `place:` because an administrative division is
    # an *area*, where `PPLA2` — which stays a `place:` — is the settlement that
    # administers one. `land:chukotka` is the okrug, and without these the right
    # answer for it read "NOT a land:".
    "land":  {"ISL", "ISLS", "ISLET", "PEN", "MT", "MTS", "HLL", "HLLS",
              "PLN", "PLAT", "UPLD", "RGN", "AREA", "VAL", "CNYN", "RDGE",
              "RVN", "GRAZ", "FRST", "ADM1", "ADM2", "ADM3", "ADM4", "PCLI"},
    "water": {"BAY", "BAYS", "GULF", "SD", "STRT", "LK", "LKS", "SEA",
              "OCN", "LGN", "COVE", "INLT", "ESTY", "CHN", "FJD", "LKO"},
    "river": {"STM", "STMS", "STMI", "STMX", "STMB", "STMD", "STMC", "STMA"},
}


#: The 1918 Russian orthographic reform, as a character fold.
#:
#: **Bogoras prints pre-reform and every modern gazetteer is post-reform**, so
#: `Пусторѣцкъ` and `Пусторецк` are the same village and no amount of case or
#: accent folding brings them together. The reform is a documented, mechanical
#: substitution — this is not a guess about spelling, it is the rule the language
#: actually changed by. Terminal hard sign is dropped separately, since ъ is
#: still a letter mid-word (`объ-`).
PREREFORM = str.maketrans({"ѣ": "е", "і": "и", "ѳ": "ф", "ѵ": "и", "ѧ": "я"})

#: Generic terms a gazetteer puts on one side of a name and this book's editor on
#: the other: `Tkachen Bay` against `Bukhta Tkachen`, `Baron Korff's Bay` against
#: `Zaliv Korfa`. Stripping them leaves the part that actually identifies, and it
#: is the only reason the two stores meet at all on the bays.
GENERICS = {
    "bay", "bays", "gulf", "sound", "strait", "lake", "river", "cape", "mount",
    "mountain", "mountains", "island", "islands", "isle", "hills", "range",
    "sea", "inlet", "cove", "lagoon", "creek", "point", "fort", "st", "the",
    "bukhta", "zaliv", "guba", "mys", "ozero", "reka", "gora", "gory", "ostrov",
    "ostrova", "proliv", "khrebet", "more", "poluostrov", "selo", "urochishche",
    "бухта", "залив", "губа", "мыс", "озеро", "река", "гора", "горы", "остров",
    "острова", "пролив", "хребет", "море", "полуостров", "село",
}


#: A generic term in the entry's *own* name, and the feature code it implies.
#:
#: **`place:` is a point and says nothing finer, which is right for the store and
#: too coarse for matching.** A cape and the village beside it are both points,
#: so the class check cannot part `Cape Nome` the headland from `Cape Nome` the
#: settlement — both `place:`, both typed, both named exactly that, 4 km apart.
#: But the entry calls itself a *cape*, and the gazetteer publishes a code for
#: that, so the name the editor wrote is itself evidence. Used only to break a
#: tie: a candidate with the implied code sorts above one without, and nothing is
#: rejected for lacking it — plenty of features are named `Mount X` and coded
#: something else entirely.
IMPLIED = {
    "cape": "CAPE", "mys": "CAPE",
    "mount": "MT", "gora": "MT",
    "lake": "LK", "ozero": "LK",
    "bay": "BAY", "bukhta": "BAY", "zaliv": "BAY", "guba": "BAY",
    "island": "ISL", "ostrov": "ISL",
    "river": "STM", "reka": "STM",
}


def _implied(names) -> str:
    """The feature code an entry's own names imply, if they agree on one."""
    got = {IMPLIED[w] for n in names for w in _fold(n).split() if w in IMPLIED}
    return got.pop() if len(got) == 1 else ""


def _fold(s: str) -> str:
    """The match key: NFD, casefolded, de-accented, pre-reform folded.

    Fixes the noise either side of a name — a hard space, the curly apostrophe
    in `Baron Korff's Bay`, a stray accent — and the orthography of a century
    ago, which is the difference between the store's Russian and everyone
    else's.
    """
    s = unicodedata.normalize("NFD", str(s)).casefold().translate(PREREFORM)
    s = "".join(c for c in s
                if not unicodedata.combining(c) and (c.isalnum() or c == " "))
    # Terminal hard sign, per the reform. Word-final only: mid-word ъ survived it.
    return " ".join(w.rstrip("ъ") or w for w in s.split()).strip()


def _specific(key: str) -> str:
    """What is left of a folded name once the generic terms are taken off.

    `tkachen bay` and `bukhta tkachen` both reduce to `tkachen`, which is the
    only way those two stores meet.

    **Four characters, not three, and three was measured to be too few.** This
    is a *secondary* key — the full name always indexes as well — so a short
    remainder costs nothing but noise: `Big River` reduces to `big` and `Red
    River` to `red`, each of which matches half of Siberia, and every hit still
    has to be read by a human. Anything shorter than a distinguishing word is
    not a fuzzy match, it is a wildcard.
    """
    rest = [w for w in key.split() if w not in GENERICS]
    out = " ".join(rest)
    return out if len(out) >= 4 and rest else ""


@lru_cache(maxsize=1)
def geonames_index(root: str = ".") -> dict[str, list[dict]]:
    """`{folded name: [row, …]}` over the window file, every alternate included.

    **The alternate names are the whole value of this source.** The primary name
    is a romanization — `Bukhta Tkachen`, `Zaliv Lavrentiya` — which no entry in
    this store spells that way; the Russian the editor keyed sits in column 4
    among a dozen others. Indexing only the primary would find almost nothing.
    """
    p = Path(root) / GEONAMES / WINDOW_TSV
    if not p.exists():
        return {}
    idx: dict[str, list[dict]] = {}
    with p.open(encoding="utf-8") as fh:
        for line in fh:
            f = line.rstrip("\n").split("\t")
            if len(f) < 8:
                continue
            try:
                lat, lon = float(f[4]), float(f[5])
            except ValueError:
                continue
            row = {"qid": f[0], "label": f[1], "geo": (lat, lon),
                   "desc": f"{f[7]} ({f[6]})", "fcode": f[7],
                   "enwiki": "", "src": "geonames"}
            names = {f[1], f[2], *(f[3].split(",") if len(f) > 3 else ())}
            keys = set()
            for n in names:
                k = _fold(n)
                if not k:
                    continue
                keys.add(k)
                # Indexed under the specific part too, so `Bukhta Tkachen` is
                # reachable from `Tkachen Bay`. Both keys point at the same row,
                # so a name that matches either way is still one candidate.
                if sp := _specific(k):
                    keys.add(sp)
            for k in keys:
                idx.setdefault(k, []).append(row)
    return idx


def geonames_names(terms: list[str], root: str = ".") -> dict[str, list[dict]]:
    """`{searched name: [candidate, …]}`, same row shape as the SPARQL path."""
    idx = geonames_index(root)
    out: dict[str, list[dict]] = {}
    for t in terms:
        k = _fold(t)
        got, seen = [], set()
        for key in (k, _specific(k)):
            for r in idx.get(key, []) if key else ():
                if r["qid"] not in seen:
                    seen.add(r["qid"])
                    got.append(r)
        if got:
            out[t] = got
    return out


def build_window(root: str = ".") -> int:
    """Cut the country dumps down to this edition's window, once.

    2.65 M rows in and 155 k out, 17 MB — small enough to index on every run,
    which is what lets the match be a dict lookup rather than a scan. The same
    reduce-once shape `build_geo.py` has, and for the same reason: the source is
    outside the repository and only this machine holds it.
    """
    d = Path(root) / GEONAMES
    dumps = sorted(d.glob("*.txt"))
    dumps = [p for p in dumps if p.name != "readme.txt"]
    if not dumps:
        print(f"no country dumps in {d} — download RU.zip and US.zip from "
              f"https://download.geonames.org/export/dump/ and unzip them there",
              file=sys.stderr)
        return 2
    w, s, e, n = 79.0, 39.5, -142.0, 77.0
    kept = total = 0
    with (d / WINDOW_TSV).open("w", encoding="utf-8") as out_fh:
        for p in dumps:
            with p.open(encoding="utf-8") as fh:
                for line in fh:
                    total += 1
                    f = line.split("\t")
                    if len(f) < 9:
                        continue
                    try:
                        lat, lon = float(f[4]), float(f[5])
                    except ValueError:
                        continue
                    if not (s <= lat <= n and (lon >= w or lon <= e)):
                        continue
                    out_fh.write("\t".join(f[:9]) + "\n")
                    kept += 1
    print(f"{total} rows in {len(dumps)} dump(s) → {kept} in the window, "
          f"{d / WINDOW_TSV}")
    return 0


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
            # **A failed chunk is recorded, not skipped.** Skipping made a dead
            # request indistinguishable from an item with no P625, and the
            # caller printed the second. Nothing downstream could have known.
            print(f"  ! fetch {chunk[0]}…: {e}", file=sys.stderr)
            for q in chunk:
                out[q] = {"qid": q, "failed": str(e), "geo": None,
                          "label": "", "desc": "", "enwiki": ""}
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


def _parent_shape(ident: str, store: dict):
    """What a candidate coordinate should fall inside: `(area, frame)`.

    Walks up rather than reading `within:` once, because the immediate parent is
    very often shapeless: a village's parent is Chukotka, which no source draws,
    and its grandparent is Northeast Siberia, which none draws either. Stopping
    at the first `within:` would report "no parent shape" for most of the store
    and throw away the check.

    **A `frame:` is taken where no ancestor has an `area:`, and that is not a
    consolation prize.** The chain above most of this store is *entirely*
    shapeless — Chukotka, Northeast Siberia and the Russian Far East are all
    framed by their members and drawn by nobody — so the containment test was
    blind in exactly the region the edition is about. It cost a real error:
    `place:kamenskoye` matched a Kamenskoye in Tomsk oblast, 3,000 km away, and
    nothing in the report objected. Northeast Siberia's frame would have refused
    it on the longitude alone. A box is a weaker witness than a polygon and it is
    an enormously stronger one than nothing, so the row says which it used.
    """
    seen, at = set(), store.get(ident, {}).get("within", "")
    frame = None
    while at and at not in seen:
        seen.add(at)
        rec = store.get(at)
        if rec is None:
            break
        shapes = geo.geo_shapes(rec) if "geo" in rec else []
        if shapes:
            # The first, where an ancestor names several. This is a containment
            # *test* and a candidate outside one half of a two-shape parent is
            # not thereby wrong; taking one is what the check always did, and
            # the row names which.
            return shapes[0], None
        if frame is None and rec.get("frame"):
            frame = (at, rec["frame"])
        at = rec.get("within", "")
    return "", frame


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

    area, frame = _parent_shape(ident, store)
    if area:
        d = doc(area)
        if d:
            got["parent"] = area
            if geo.in_shape((slon, lat), d):
                got["parent_out"] = 0.0
            else:
                got["parent_out"] = round(geo.distance_to((slon, lat), d), 3)
    elif frame:
        # A box, in the store's shifted longitudes, so it needs no antimeridian
        # handling of its own — `frame:` is authored in that window already.
        who, (fw, fs, fe, fn) = frame
        got["parent"] = f"{who} (frame)"
        got["parent_out"] = 0.0 if (fs <= lat <= fn and fw <= slon <= fe) else \
            round(max(fs - lat, lat - fn, fw - slon, slon - fe), 3)

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
                        and not (r["geo"] or r["frame"]))
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
    all_terms = [t for ts in wanted.values() for t, _lg in ts]
    use_api = len(idents) <= a.api_limit
    want_wd = a.source in ("wikidata", "both")
    want_gn = a.source in ("geonames", "both")

    gn = geonames_index(a.root) if want_gn else {}
    lookups = []
    if want_gn:
        lookups.append(f"GeoNames ({len(gn)} indexed names)" if gn
                       else "GeoNames MISSING — run --build-window")
    if want_wd:
        lookups.append("SPARQL exact label/alias match")
        if use_api:
            lookups.append("per-name prefix search")
    print(f"# {len(idents)} entit(ies), against the window "
          f"{' '.join(f'{v:g}' for v in idx['window'])}")
    print(f"# lookup: {' + '.join(lookups)}"
          + ("" if use_api or not want_wd else
             f" (over {a.api_limit} entries the prefix search is rate-limited; "
             f"name them explicitly for that)"))

    pool: dict[str, list[dict]] = {}
    if want_gn:
        pool = {k: list(v) for k, v in geonames_names(all_terms, a.root).items()}
    if want_wd:
        try:
            for k, v in sparql_names(all_terms).items():
                pool.setdefault(k, []).extend(v)
        except Exception as e:                                # noqa: BLE001
            print(f"  ! SPARQL: {e}", file=sys.stderr)
    print()

    for ident in idents:
        rec = store.get(ident)
        if rec is None:
            print(f"{ident}\n  ! no such entity\n")
            continue
        rows = {}
        for term, _lang in wanted.get(ident, []):
            for r in pool.get(term, []):
                rows.setdefault(f"{r.get('src', 'wikidata')}:{r['qid']}", r)
        if want_wd and use_api:
            for term, lang in wanted.get(ident, []):
                for q in search(term, lang):
                    if f"wikidata:{q}" not in rows:
                        rows[f"wikidata:{q}"] = None
            missing = [k.partition(":")[2] for k, v in rows.items() if v is None]
            got = entities(missing)
            for k in list(rows):
                if rows[k] is None:
                    rows[k] = got.get(k.partition(":")[2])
            rows = {k: v for k, v in rows.items() if v}

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
        # **Typed where the source has a type, textual where it does not.**
        # GeoNames publishes a controlled feature code, so `BAY` under a `water:`
        # is a real agreement and `STM` under one is a real disagreement.
        # Wikidata publishes a sentence somebody wrote, so the same test there is
        # a grep over free text and a miss means much less. Same field in the
        # report, two different strengths behind it, which is why the row prints
        # the code itself and not just the verdict.
        words = CLASS_WORDS.get(rec["class"], ())
        codes = FCODES.get(rec["class"], set())
        mine = {_fold(t) for t, _lg in wanted.get(ident, [])}
        implied = _implied(t for t, _lg in wanted.get(ident, []))
        for r, t in cands:
            t["implied"] = bool(implied) and r.get("fcode") == implied
            if r.get("fcode"):
                t["class_match"] = r["fcode"] in codes
            else:
                blob = f"{r['desc']} {r['label']}".lower()
                t["class_match"] = any(w in blob for w in words)
            # **Whether the candidate's *own* name is the one searched.** A row
            # can match on an alternate — a former name, a nearby feature's
            # name — and those are worth showing and not worth ranking first.
            # `Ust'-Penzhino` carries "Kamenskoye" as a former name and outranked
            # the actual Kamenskoye, 30 km away, because every other test tied.
            t["label_exact"] = _fold(r["label"]) in mine
        # Where the entry is already located, its own point outranks everything
        # below it: two sources naming the same coordinate is a stronger answer
        # than any description or containment test, and the nearest candidate is
        # the one being corroborated.
        cands.sort(key=lambda rt: (not rt[1]["in_window"],
                                   rt[1]["own_km"] if rt[1]["own_km"] is not None
                                   else 0,
                                   not rt[1]["class_match"],
                                   not rt[1]["label_exact"],
                                   not rt[1]["implied"],
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
            typed = " (typed)" if r.get("fcode") else ""
            marks.append(f"reads as {rec['class']}:{typed}" if t["class_match"]
                         else f"NOT a {rec['class']}:{typed}")
            if not t["label_exact"]:
                marks.append("matched on an alternate name")
            if t["parent"]:
                marks.append("in " + t["parent"] if t["parent_out"] == 0
                             else f"{t['parent_out']}° from {t['parent']}")
            if t["inside"]:
                marks.append("inside " + " ".join(t["inside"]))
            src = r.get("src", "wikidata")
            print(f"  {src[:2]}/{r['qid']:<11} {lat:>9.4f} {lon:>10.4f}  "
                  f"{r['label'][:30]:30}  {r['desc'][:40]}")
            print(f"  {'':14} {'':>9} {'':>10}  {'; '.join(marks) or '—'}")
            # **The identity line prints whether or not there is an article.** It
            # is the one `fill` reads; a bare item with a coordinate and no
            # Wikipedia page is an ordinary and useful result, and printing the
            # pair only when both exist quietly hid Cape Navarin.
            wp = (f"link: wikipedia:{r['enwiki'].replace(' ', '_')}  "
                  if r["enwiki"] else "")
            print(f"  {'':14} {wp}link: {src}:{r['qid']}")
        if hidden:
            print(f"  {'':10} ({hidden} further candidate(s) outside the "
                  f"window, hidden — --all-candidates shows them)")
        print()
    print("report only — nothing was written. Author the `link:` lines you "
          "believe, then `tools/gazetteer.py fill --all --commit`.")
    return 0


def run_fill(a) -> int:
    """`geo:` derived from an authored `link:`, and from nothing else.

    **Either identity, and `wikidata:` wins a tie.** An entry may carry both; the
    two agree on the ordinary case and where they do not, the one a human is more
    likely to have looked at is the one to derive from. The row prints which
    source it used, so an unexpected coordinate can be traced without opening the
    file.
    """
    from harness.cli._entity import _set_field

    root = Path(a.root)
    store = load(root)
    idents = (sorted(i for i, r in store.items() if r["class"] in GEO_CLASSES)
              if a.all else list(a.idents))
    gn = geonames_index(a.root)

    todo = []
    for ident in idents:
        rec = store.get(ident)
        if rec is None:
            print(f"{ident}: no such entity", file=sys.stderr)
            continue
        ids = {v.partition(":")[0]: v.partition(":")[2] for v in rec["links"]}
        src = ("wikidata" if "wikidata" in ids
               else "geonames" if "geonames" in ids else "")
        if not src:
            continue
        # **An entry that already has a point is looked up anyway.** It used to
        # be skipped with one line, which threw away the most valuable thing
        # here: thirty-odd points in this store came off a chart, and comparing
        # them against a source with no common ancestor is a second witness on
        # work that has never had one. Whether it *writes* is still gated by
        # `--replace`; the comparison is free and always reported.
        #
        # An entry with an `area:` is a different case and is compared rather
        # than written to, without `--replace`. A shape *is* the location —
        # `extent_of` prefers it and would never read the point — so the only
        # thing a nominal centre could add there is a second, weaker statement of
        # the same fact, and a `geo verify` row the day the two disagree.
        todo.append((ident, rec, f"{src}:{ids[src]}"))

    if not todo:
        print("nothing to fill")
        return 0

    rows = entities([q.partition(":")[2] for _i, _r, q in todo
                     if q.startswith("wikidata:")])
    for r in {x["qid"]: x for v in gn.values() for x in v}.values():
        rows.setdefault(f"gn:{r['qid']}", r)
    idx = geo.index(root)
    kids = geo.children(store)
    docs: dict = {}
    wrote = held = 0
    for ident, rec, key in todo:
        src, _, qid = key.partition(":")
        got = rows.get(qid) if src == "wikidata" else rows.get(f"gn:{qid}")
        if got and got.get("failed"):
            print(f"! {ident:30} {key:20} LOOKUP FAILED — {got['failed'][:60]}")
            continue
        if not got or not got["geo"]:
            print(f"  {ident:30} {key:20} no coordinate on the record")
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
        # **Anything the entry already says about where it is counts.** A
        # `geo:` is the obvious one. An `area:` is stronger — `extent_of` prefers
        # the shape and would never read a point beside it, so a nominal centre
        # could only be a second, weaker statement of the same fact and a
        # `geo verify` row the day the two disagree. And a `frame:` is a *choice*:
        # `water:bering-strait` had a point and a human took it out in favour of
        # a box, and writing the same point back is undoing an editorial decision
        # by default, which is the one thing --commit must never do quietly.
        # **A container is framed by its members and a point would replace
        # that.** `extent_of` reads a shape, else a point, else the union of
        # everything beneath — so writing a nominal centre onto Chukotka, which
        # has twenty located descendants and no polygon, swapped a map of the
        # whole region for a dot. The atlas said so immediately and two tests
        # caught it; the rule is that anything already locatable *through its
        # members* is as settled as one carrying its own shape.
        framed_by_kids = (not rec["geo"]
                          and any(geo.located(k, store, root)
                                  for k in kids.get(ident, [])))
        # The member kinds are told apart because they are not equally settling.
        # A point is the thing this tool writes, so an entry that has one is
        # done; a shape or a transcluded extent is *stronger* than the nominal
        # centre a gazetteer would return, and writing one beside it would be
        # the second, weaker statement of the same fact that the old two-field
        # rule existed to refuse.
        held_by = ("geo:" if geo.geo_points(rec)
                   else "area:" if geo.geo_shapes(rec)
                   else "members:" if geo.geo_refs(rec)
                   else "frame:" if rec["frame"]
                   else "members" if framed_by_kids else "")
        settled = bool(held_by) and not a.replace
        act = "=" if settled else "~" if held_by else "+"
        if held_by == "members":
            note.append("framed by its located members")
        elif held_by and held_by != "geo:":
            note.append(f"the entry already carries a {held_by}")
        print(f"{act} {ident:30} {key:20} {lat:>9.4f} {lon:>10.4f}  "
              f"{'; '.join(note) or '—'}")
        if settled:
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
    ap.add_argument("--build-window", action="store_true",
                    help="cut scratch/geonames/*.txt down to the edition's "
                         "window and stop. Run once after downloading RU.zip "
                         "and US.zip from download.geonames.org")
    sub = ap.add_subparsers(dest="action", required=not any(
        x == "--build-window" for x in sys.argv))

    p = sub.add_parser("propose", help="candidate identities, tested against "
                                       "the shapes the store already holds")
    p.add_argument("idents", nargs="*")
    p.add_argument("--source", choices=("both", "wikidata", "geonames"),
                   default="both",
                   help="which gazetteer to ask (default both). GeoNames is "
                        "offline, typed and strong on small Siberian features; "
                        "Wikidata is live, richer, and knows what is a river "
                        "and what is the village on it")
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

    p = sub.add_parser("fill",
                       help="geo: from an authored link: wikidata:Q… or "
                            "link: geonames:…")
    p.add_argument("idents", nargs="*")
    p.add_argument("--all", action="store_true")
    p.add_argument("--replace", action="store_true",
                   help="overwrite an existing geo:. A point a human read off a "
                        "chart outranks one a query returned")
    p.add_argument("--commit", action="store_true")
    p.set_defaults(fn=run_fill)

    a = ap.parse_args()
    if a.build_window:
        return build_window(a.root)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
