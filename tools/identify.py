#!/usr/bin/env python3
"""Propose Wikidata identities for entities of **any** class, and derive the
Wikipedia title from the ones a human has adopted.

`gazetteer.py` answers *where* a place is and can only speak about the four
geographical classes: its whole second witness is geometry, and a person, a
taxon or a book has none. This answers the other question — *which item is
this* — for the classes that question is askable of, and it is the same two-verb
split for the same reason. `propose` reports and writes nothing; a human writes
the `link: wikidata:Q…` they believe (or hands it to `set`, which is the same
act in bulk); the `link: wikipedia:…` beside it is *derived* from that QID's
`enwiki` sitelink and never searched for separately. The authored fact is the
identity; the article title follows from it mechanically, is re-derivable, and
fails rather than goes stale.

**One name match is not an identification, so every class carries a type gate.**
A bare `?item rdfs:label "Parry"` returns a poet, a sound, a village in Ontario
and a hundred more, and adopting the first is precisely the fluent nonsense this
project is organised against. So the query is per class and says what the answer
has to *be*: a `person:` must be `wdt:P31 wd:Q5`, a `taxon:` is matched on its
scientific name `P225` rather than on a label at all, a `people:` must be an
ethnic group, a `source:` a written work. `CLASSES` below carries the table and
the argument for each line. The gate is what makes a *single* surviving
candidate worth calling unique; without it "unique" would only mean "one thing
in the world happens to be spelt this way".

**A gate is a filter and never a verdict.** Two survivors are reported as two,
and one survivor is reported as one — neither is adopted. The classes with no
honest gate (`being:`, `event:`) are searched ungated and say so in the row, and
`animal:` is not searched at all: a reindeer Bogoras's host called by name is not
in Wikidata and never will be.

**Taxon is the one class matched on something other than a name.** `P225` is the
scientific name, so `Gulo gulo` finds the wolverene and nothing else, and the
match is against a *field whose only purpose is to be that binomial* rather than
against a label a hundred items might share. It also means an obsolete binomial
finds its own item where Wikidata holds one — `Agaricus muscarius` is a taxon
synonym with a record of its own — and finds nothing where it does not, which is
the honest answer rather than a silent redirect to the accepted name. The print's
ligatures and its capitalised epithets are folded into query variants
(`_variants`), because `Rubus chamæmorus` and `Cetraria Islandica` are this book's
spellings and `Rubus chamaemorus` and `Cetraria islandica` are Wikidata's.

Like `gazetteer.py` this talks to a live outside source, so it is a `tools/`
script and not a harness verb.

    tools/identify.py propose --class taxon        every taxon at once
    tools/identify.py propose --missing            every entry with no wikidata:
    tools/identify.py propose person:nordenskiold
    tools/identify.py set taxon:gulo-gulo=Q46952 person:boas=Q57285
    tools/identify.py set --from scratch/ids.tsv --commit
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import unquote


def _title(url: str) -> str:
    """The article title out of a `schema:about` URL.

    **Percent-decoded, which it was not at first.** A SPARQL article IRI is
    URL-encoded, so Nordenskiöld's came back as `Adolf Erik Nordenski%C3%B6ld`
    and read in the report as a title with a mojibake in it. Nothing was ever
    written from this — `set` takes its title from the `enwiki` sitelink, which
    is already decoded — so the defect was confined to the report, which is
    exactly where an editor decides whether a candidate is the right one.
    """
    return unquote(url.rsplit("/", 1)[-1]).replace("_", " ")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness.entities import load, parse  # noqa: E402
from tools.gazetteer import SESSION, SPARQL, entities  # noqa: E402
from tools.gazetteer import search as gz_search  # noqa: E402

#: What each class is allowed to match, and what the answer has to be.
#:
#: `gate` is spliced into the query as a triple pattern the candidate must
#: satisfy; `on` says which field the name is matched against. Every line is one
#: judgement about what would make a match an identification rather than a
#: coincidence of spelling, and the geographical four are deliberately absent —
#: `gazetteer.py propose` already answers them, with geometry as a second witness
#: this file cannot offer.
CLASSES: dict[str, dict] = {
    # A human. The weakest gate here and the one that most needs the rest of the
    # row read: `Q5` removes the villages and the ships and leaves every other
    # person who ever shared the surname, which is why a `person:` row prints the
    # description and the dates and expects to be looked at.
    "person": {"on": "label", "gate": "?item wdt:P31 wd:Q5 ."},
    # An ethnic group **or a people**, which in Wikidata are two classes and not
    # a hierarchy. Q41710 alone was the first gate and it silently dropped the
    # Evens, the Yakuts and the Cossacks — every one of them present, none of
    # them an instance of anything under `ethnic group` — while `0` in the report
    # said "Wikidata has never heard of the Evens". A gate that narrow does not
    # make the store safer, it makes an absence in the *ontology* read as an
    # absence in the world, which is the same defect as a failed lookup printing
    # as "no coordinate".
    "people": {"on": "label",
               "gate": "?item wdt:P31/wdt:P279* ?kind . "
                       "VALUES ?kind { wd:Q41710 wd:Q2472587 }"},
    # Matched on the scientific name itself. See the module docstring: this is
    # the one class whose match is against a field that exists to hold exactly
    # this string.
    "taxon": {"on": "P225", "gate": "?item wdt:P31 wd:Q16521 ."},
    # An organisation. The Smithsonian, the Academy of Sciences, the two
    # museums — all of them instances of something under `Q43229`.
    "institution": {"on": "label",
                    "gate": "?item wdt:P31/wdt:P279* wd:Q43229 ."},
    # A written work — **matched on its title, which is not in the entity
    # file.** A `source:` entry's canonical is the siglum the book cites it by,
    # `Krause, I` and `Sauer 1802`, and its aliases are the other spellings of
    # that siglum; none of them is the name of anything in the world. Asked as
    # labels they returned what you would expect and the gate did not save it —
    # `Kyber, I` found a post-quantum key-encapsulation scheme, `Sauer` a 2004
    # video game — which is the whole argument for a type gate arriving at its
    # limit: a gate can say the answer is a written work and cannot say the
    # question was worth asking. So the term comes from `edition/authorities.json`
    # by way of the entry's `authority:` key, and it is the *title*. An exact
    # match on `Beschreibung von dem Lande Kamtschatka` is an identification;
    # nothing else here was.
    "source": {"on": "label", "terms": "authority",
               "gate": "?item wdt:P31/wdt:P279* wd:Q47461344 ."},
    # No honest gate. A Chukchee ke'let has no class in Wikidata to be an
    # instance of, and the entries that do resolve resolve to articles about
    # shamanism and the aurora. Searched ungated, reported as ungated.
    "being": {"on": "label", "gate": "", "ungated": True},
    "event": {"on": "label", "gate": "", "ungated": True},
}

#: Not searched at all. `animal:` is an individual reindeer's name; `lexicon`
#: forms are not entities. Listing them here rather than letting them fall
#: through a `KeyError` is the difference between "nothing to ask" and "asked and
#: found nothing".
UNSEARCHABLE = {
    "animal": "an individual animal's name — Wikidata has no such item",
    "place": "geographical — tools/gazetteer.py propose answers this class",
    "land": "geographical — tools/gazetteer.py propose answers this class",
    "water": "geographical — tools/gazetteer.py propose answers this class",
    "river": "geographical — tools/gazetteer.py propose answers this class",
}

_Q = """
SELECT ?item ?name ?desc ?article ?born ?died WHERE {
  VALUES ?name { %(values)s }
  %(match)s
  %(gate)s
  OPTIONAL { ?item schema:description ?desc FILTER(LANG(?desc) = "en") }
  OPTIONAL { ?item wdt:P569 ?born }
  OPTIONAL { ?item wdt:P570 ?died }
  OPTIONAL {
    ?article schema:about ?item ;
             schema:isPartOf <https://en.wikipedia.org/> .
  }
}
"""

_MATCH = {
    "label": "?item rdfs:label|skos:altLabel ?name .",
    # A literal, not a language-tagged string: `P225` is a monolingual-free
    # scientific name and matching it with an `@en` tag returns nothing at all.
    "P225": "?item wdt:P225 ?name .",
}


def _cyrillic(s: str) -> bool:
    return any("Ѐ" <= c <= "ӿ" for c in s)


#: Ligature expansions the print uses and Wikidata does not. NFD leaves `æ` and
#: `œ` alone — they are letters, not decomposable accents — so this is a fold the
#: normalizer cannot do and must not: `Rubus chamæmorus` is what page 1-101 sets
#: and the store reproduces the print.
_LIG = {"æ": "ae", "Æ": "Ae", "œ": "oe", "Œ": "Oe", "ﬁ": "fi"}


def _variants(name: str, on: str) -> list[str]:
    """Every spelling worth asking for one stored name, the store's own first.

    Three folds, each of which is a difference between how this book spells a
    thing and how Wikidata does: the ligatures above; the accents NFD split,
    recomposed, since a query literal must be NFC to match; and — for a
    scientific name only — the lower-cased species epithet, because the print
    capitalises them (`Cetraria Islandica`) and the nomenclature does not.
    """
    out = [name]
    folded = "".join(_LIG.get(c, c) for c in name)
    out.append(folded)
    out.append(unicodedata.normalize("NFC", folded))
    if on == "P225":
        parts = folded.split()
        if len(parts) > 1:
            out.append(" ".join([parts[0]] + [p.lower() for p in parts[1:]]))
    seen, uniq = set(), []
    for v in out:
        v = unicodedata.normalize("NFC", v).strip()
        if v and v not in seen:
            seen.add(v)
            uniq.append(v)
    return uniq


def _ask(names: list[str], cls: str) -> dict[str, list[dict]]:
    """`{name asked: [candidate, …]}` for one class, in one query.

    One round trip per class rather than per name, for the reason
    `gazetteer.sparql_names` carries: three hundred `wbsearchentities` calls take
    a hard 429 and are the wrong shape of request for a sweep.
    """
    if not names:
        return {}
    spec = CLASSES[cls]
    if spec["on"] == "P225":
        values = " ".join(f'"{n}"' for n in sorted(set(names)))
    else:
        values = " ".join(
            f'"{n}"@{"ru" if _cyrillic(n) else "en"}'
            for n in sorted(set(names)))
    q = _Q % {"values": values, "match": _MATCH[spec["on"]],
              "gate": spec["gate"]}
    # POSTed for the reason `gazetteer.sparql_names` is: a `VALUES` block over a
    # whole class is exactly the query long enough to take a `414 URI Too Long`,
    # and a form body has no such limit.
    r = SESSION.post(SPARQL, data={"query": q},
                     headers={"Accept": "application/sparql-results+json"},
                     timeout=180)
    r.raise_for_status()
    out: dict[str, list[dict]] = {}
    for b in r.json()["results"]["bindings"]:
        qid = b["item"]["value"].rsplit("/", 1)[-1]
        name = b["name"]["value"]
        row = {
            "qid": qid,
            "desc": b.get("desc", {}).get("value", ""),
            "enwiki": _title(b.get("article", {}).get("value", "")),
            "born": b.get("born", {}).get("value", "")[:4],
            "died": b.get("died", {}).get("value", "")[:4],
        }
        bucket = out.setdefault(name, [])
        if not any(x["qid"] == qid for x in bucket):
            bucket.append(row)
    return out


_BY_QID = """
SELECT ?item ?desc ?article ?born ?died WHERE {
  VALUES ?item { %(values)s }
  %(gate)s
  OPTIONAL { ?item schema:description ?desc FILTER(LANG(?desc) = "en") }
  OPTIONAL { ?item wdt:P569 ?born }
  OPTIONAL { ?item wdt:P570 ?died }
  OPTIONAL {
    ?article schema:about ?item ;
             schema:isPartOf <https://en.wikipedia.org/> .
  }
}
"""


def _gate_qids(qids: list[str], cls: str) -> dict[str, dict]:
    """The subset of `qids` the class's gate admits, with their descriptions.

    **The fallback's second half, and the half that makes it usable.**
    `wbsearchentities` is a prefix search with a relevance ranking and no notion
    of type: asked for `Even` it returns an evening, a footballer and a village
    before the Siberian people. Running its results back through the same
    `wdt:P31` the sweep used means the fallback is looser about *spelling* and
    exactly as strict about *what the answer is*, which is the only sense in
    which a search result may be let near this store.
    """
    if not qids:
        return {}
    spec = CLASSES[cls]
    if spec.get("ungated"):
        return {q: {} for q in qids}
    q = _BY_QID % {"values": " ".join(f"wd:{x}" for x in sorted(set(qids))),
                   "gate": spec["gate"]}
    # POSTed for the reason `gazetteer.sparql_names` is: a `VALUES` block over a
    # whole class is exactly the query long enough to take a `414 URI Too Long`,
    # and a form body has no such limit.
    r = SESSION.post(SPARQL, data={"query": q},
                     headers={"Accept": "application/sparql-results+json"},
                     timeout=180)
    r.raise_for_status()
    out: dict[str, dict] = {}
    for b in r.json()["results"]["bindings"]:
        qid = b["item"]["value"].rsplit("/", 1)[-1]
        out[qid] = {
            "qid": qid,
            "desc": b.get("desc", {}).get("value", ""),
            "enwiki": _title(b.get("article", {}).get("value", "")),
            "born": b.get("born", {}).get("value", "")[:4],
            "died": b.get("died", {}).get("value", "")[:4],
        }
    return out


#: **The canonical is asked first and alone**, and the aliases only answer for an
#: entry it left blank.
#:
#: They were peers, and that was wrong in the one way this file exists to avoid.
#: An entry's canonical is the entity's name — `Franz Boas`, `Berthold Laufer`,
#: `William Healey Dall`. Its aliases are *what the page prints*, which for a
#: `person:` is very often a bare surname the book could assume its reader would
#: place. Asked as peers the surname drowns the name: `person:boas` came back
#: with a Danish zoologist and a Holocaust victim beside Franz Boas, and
#: `person:laufer` with a Brazilian musician — an ambiguous row apiece, from a
#: query whose first term had already answered it exactly. Fourteen of the
#: twenty-one ambiguous rows in the first `person:` sweep were this and nothing
#: else.
#:
#: So the two are stages, not a list. Stage one is the canonical; stage two is
#: the aliases, asked only where stage one found nothing, and its rows are marked
#: `[alias]` because a surname match corroborates less than a full name's does.
#: That ordering is also why the Russian aliases still earn their place — for a
#: `place:` whose canonical is Bogoras's transcription, `Хатырка` is the only
#: modern name the store holds, and stage two is exactly where it gets asked.
def _terms(rec: dict, limit: int, authorities: dict | None = None,
           stage: int = 0) -> list[str]:
    spec = CLASSES.get(rec["class"], {})
    if spec.get("terms") == "authority":
        if stage:
            return []
        got = (authorities or {}).get(rec["authority"] or "")
        if not got:
            return []
        return [t for t in (got.get("title"), got.get("title_en")) if t][:limit]
    if stage == 0:
        return [rec["canonical"]] if rec["canonical"] else []
    names = []
    for a in rec["aliases"]:
        f = a["form"]
        if f and f != rec["canonical"] and f not in names:
            names.append(f)
    return names[:limit]


def _authorities(root: Path) -> dict:
    """`{key: record}` out of `edition/authorities.json`.

    The one store outside `edition/entities/` this file reads, and it reads it
    for one class: a `source:` entry holds a siglum and a key, and the title the
    key resolves to is the only string in either store that names the work
    rather than the citation.
    """
    import json
    p = root / "edition" / "authorities.json"
    if not p.exists():
        return {}
    doc = json.loads(p.read_text(encoding="utf-8"))
    return {a["key"]: a for a in doc.get("authorities", [])}


def _has(rec: dict, prefix: str) -> str:
    for v in rec["links"]:
        if v.startswith(prefix + ":"):
            return v.partition(":")[2]
    return ""


def _select(a, store: dict) -> list[str]:
    if a.idents:
        return list(a.idents)
    picked = [i for i, r in store.items()
              if r["class"] in CLASSES
              and (not a.cls or r["class"] == a.cls)
              and (not a.missing or not _has(r, "wikidata"))]
    return sorted(picked)


def run_propose(a) -> int:
    root = Path(a.root)
    store = load(root)
    auth = _authorities(root)
    idents = _select(a, store)

    unknown = [i for i in idents if i not in store]
    for i in unknown:
        print(f"{i}: no such entity", file=sys.stderr)
    idents = [i for i in idents if i in store]

    skipped: dict[str, list[str]] = {}
    todo: list[str] = []
    for i in idents:
        cls = store[i]["class"]
        if cls in UNSEARCHABLE:
            skipped.setdefault(UNSEARCHABLE[cls], []).append(i)
        elif cls not in CLASSES:
            skipped.setdefault(f"no query is defined for {cls}:", []).append(i)
        else:
            todo.append(i)

    # Grouped by class because the query is per class: the gate and the matched
    # field are both class-scoped, and one query per class is one round trip per
    # class rather than per name.
    by_class: dict[str, list[str]] = {}
    for i in todo:
        by_class.setdefault(store[i]["class"], []).append(i)

    if not a.pairs_only:
        print(f"# {len(todo)} entit(ies) in {len(by_class)} class(es)")
    uniq_n = multi_n = none_n = 0
    for cls, members in sorted(by_class.items()):
        spec = CLASSES[cls]
        # Two stages, canonical then aliases, and the second is asked only for
        # the entries the first left blank — `_terms`' note has the argument.
        # Two queries per class rather than one, which is the cost of not
        # letting a surname outvote a name.
        asked: dict[int, dict[str, list[str]]] = {0: {}, 1: {}}
        hits: dict[int, dict[str, list[dict]]] = {0: {}, 1: {}}
        for stage in (0, 1):
            for i in members:
                if stage and any(hits[0].get(v) for v in asked[0].get(i, [])):
                    continue
                for n in _terms(store[i], a.terms, auth, stage):
                    for v in _variants(n, spec["on"]):
                        asked[stage].setdefault(i, []).append(v)
            try:
                hits[stage] = _ask(
                    sorted({v for vs in asked[stage].values() for v in vs}), cls)
            except Exception as e:                          # noqa: BLE001
                # A failed query is a failure, printed as one. The whole point of
                # `gazetteer.entities`' `failed` key is that an outage must never
                # render as an absence, and a class-wide query is the same hazard
                # a hundred entries wide.
                print(f"! {cls} stage {stage}: QUERY FAILED — {e}",
                      file=sys.stderr)
        gate = "ungated" if spec.get("ungated") else spec["gate"].strip()
        if not a.pairs_only:
            print(f"\n## {cls} — matched on {spec['on']}, {gate}")
        # **The prefix search runs only where the sweep found nothing**, and
        # only when asked for. It is a round trip per name — the reason
        # `gazetteer.sparql_names` exists at all — so sweeping a hundred sources
        # through it takes a hard 429; over the twenty-five entries an exact
        # match missed it is cheap, and those twenty-five are exactly where the
        # store spells a thing differently from Wikidata (`Even` for `Evens`,
        # `Yakut` for `Yakuts`). A miss is still reported as a miss.
        fallback: dict[str, dict[str, dict]] = {}
        if a.search:
            blank = [i for i in members
                     if not any(hits[s].get(v)
                                for s in (0, 1) for v in asked[s].get(i, []))]
            for i in blank[:a.search]:
                qids: list[str] = []
                for n in _terms(store[i], a.terms, auth, 0):
                    qids += gz_search(n, "ru" if _cyrillic(n) else "en")
                try:
                    fallback[i] = _gate_qids(qids, cls)
                except Exception as e:                      # noqa: BLE001
                    print(f"! {i}: FALLBACK FAILED — {e}", file=sys.stderr)

        for i in members:
            rec = store[i]
            found: dict[str, dict] = {}
            for stage in (0, 1):
                for v in asked[stage].get(i, []):
                    for row in hits[stage].get(v, []):
                        found.setdefault(
                            row["qid"],
                            {**row, "via": "alias"} if stage else row)
            for qid, row in fallback.get(i, {}).items():
                found.setdefault(qid, {**{"qid": qid, "desc": "", "enwiki": "",
                                          "born": "", "died": ""}, **row,
                                       "via": "search"})
            have = _has(rec, "wikidata")
            mark = ("=" if have else
                    "1" if len(found) == 1 else
                    "?" if found else "0")
            if not found:
                none_n += 1
            elif len(found) == 1:
                uniq_n += 1
            else:
                multi_n += 1
            # **The single-candidate rows, spelled as `set` takes them.** The
            # alternative was a caller pasting eighty pairs out of the report by
            # hand or scraping them back out of it with `awk`, and a two-word
            # binomial breaks the obvious scrape silently — one column off, a
            # QID reading `muscarius`. A worklist a human then edits is still
            # the human's adoption; what this refuses to be is a `--commit` on
            # the report itself.
            if a.pairs_only:
                if len(found) == 1 and not have:
                    row = next(iter(found.values()))
                    print(f"{i}={row['qid']}  # {rec['canonical']} — "
                          f"{row['desc'][:50]}")
                continue
            note = f"  (entry already says {have})" if have else ""
            print(f"{mark} {i:34} {rec['canonical']}{note}")
            for qid, row in sorted(found.items()):
                life = (f" ({row['born']}–{row['died']})"
                        if row["born"] or row["died"] else "")
                # A row the prefix search brought in says so: it matched a
                # spelling the store does not hold, so the name is corroborating
                # less than an exact hit's does and the reader of the report has
                # to supply the rest.
                via = f" [{row['via']}]" if row.get("via") else ""
                print(f"      {qid:12} {row['desc'][:58]:58}{life}{via}")
                if row["enwiki"]:
                    print(f"      {'':12} en: {row['enwiki']}")

    if a.pairs_only:
        return 0

    for why, who in sorted(skipped.items()):
        print(f"\n# {len(who)} not searched — {why}")
        print("  " + ", ".join(who))

    print("\n1 one candidate   ? several   0 none   = the entry already links")
    print(f"{uniq_n} single, {multi_n} ambiguous, {none_n} unmatched")
    print("report only — nothing was written. Adopt with "
          "`identify.py set ID=Q… --commit`.")
    return 0


_PAIR = re.compile(r"^([a-z]+:[a-z0-9][a-z0-9-]*)\s*[=\t ]\s*(Q\d+)$")


def _pairs(a) -> list[tuple[str, str]]:
    """`ID=Q…` from the command line and from `--from`, in the order given.

    A file because a sweep of a hundred taxa is a hundred adoptions and a shell
    line that long is unreviewable; the same syntax in both so a run can be
    pasted out of the file or into it. A `#` comment and a blank line are
    allowed, which is what lets a worklist carry the reasoning beside the pair.
    """
    raw = list(a.pairs)
    if a.from_file:
        for ln in Path(a.from_file).read_text(encoding="utf-8").splitlines():
            ln = ln.split("#", 1)[0].strip()
            if ln:
                raw.append(ln)
    out = []
    for r in raw:
        m = _PAIR.match(r.strip())
        if not m:
            raise SystemExit(f"not an ID=Q… pair: {r!r}")
        out.append((m.group(1), m.group(2)))
    return out


def run_set(a) -> int:
    """`link: wikidata:Q…` written, and `link: wikipedia:…` derived from it.

    **The QID is the authored fact and the article title is not.** A title is
    what the sitelink says today; searching for it separately would be a second
    identification able to disagree with the first, and re-deriving it is the
    same argument `fill` rests on for a coordinate.
    """
    from harness.cli._entity import _set_lines

    root = Path(a.root)
    store = load(root)
    pairs = _pairs(a)
    if not pairs:
        raise SystemExit("nothing to set")

    missing = [i for i, _q in pairs if i not in store]
    for i in missing:
        print(f"{i}: no such entity", file=sys.stderr)
    pairs = [(i, q) for i, q in pairs if i in store]

    rows = entities(sorted({q for _i, q in pairs}))
    wrote = held = 0
    for ident, qid in pairs:
        rec = store[ident]
        got = rows.get(qid)
        if got is None:
            print(f"! {ident:34} {qid:10} NO SUCH ITEM")
            continue
        if got.get("failed"):
            print(f"! {ident:34} {qid:10} LOOKUP FAILED — {got['failed'][:50]}")
            continue
        have = _has(rec, "wikidata")
        if have and have != qid and not a.replace:
            print(f"= {ident:34} {qid:10} the entry says {have} "
                  f"— --replace overrides")
            held += 1
            continue
        links = [v for v in rec["links"]
                 if not v.startswith(("wikidata:", "wikipedia:"))]
        links.append(f"wikidata:{qid}")
        if got["enwiki"]:
            links.append(f"wikipedia:{got['enwiki'].replace(' ', '_')}")
        act = "~" if have else "+"
        print(f"{act} {ident:34} {qid:10} {got['label'][:28]:28} "
              f"{'en:' + got['enwiki'] if got['enwiki'] else 'no en article'}")
        if a.commit:
            p = root / rec["path"] if not Path(rec["path"]).is_absolute() \
                else Path(rec["path"])
            text = _set_lines(p.read_text(encoding="utf-8"), "link",
                              sorted(links))
            parse(text, where=str(p))
            p.write_text(text, encoding="utf-8")
            wrote += 1

    print("\n+ would be written   ~ would replace an existing identity   "
          "= left alone")
    print(f"{wrote} written" if a.commit else "report only; --commit writes")
    return 0


WP_API = "https://en.wikipedia.org/w/api.php"


def _qids_for_titles(titles: list[str]) -> dict[str, str]:
    """`{article title: QID}`, fifty titles a call.

    `pageprops`/`wikibase_item` is the sitelink read backwards, and the API
    normalizes and follows redirects on the way — both of which are reported, so
    a title that resolved through a redirect is visible rather than silently
    swapped.
    """
    out: dict[str, str] = {}
    for i in range(0, len(titles), 50):
        chunk = titles[i:i + 50]
        r = SESSION.get(WP_API, params={
            "action": "query", "prop": "pageprops", "ppprop": "wikibase_item",
            "redirects": 1, "titles": "|".join(chunk), "format": "json"},
            timeout=60)
        r.raise_for_status()
        q = r.json().get("query", {})
        alias = {n["from"]: n["to"] for n in q.get("normalized", [])}
        alias.update({n["from"]: n["to"] for n in q.get("redirects", [])})
        by_title = {p["title"]: (p.get("pageprops") or {}).get("wikibase_item")
                    for p in (q.get("pages") or {}).values()}
        for t in chunk:
            seen, cur = set(), t
            while cur in alias and cur not in seen:
                seen.add(cur)
                cur = alias[cur]
            if by_title.get(cur):
                out[t] = by_title[cur]
    return out


def run_fill(a) -> int:
    """`link: wikidata:Q…` derived from an authored `link: wikipedia:…`.

    **The mirror of `set`, and it is a derivation rather than a search.** Ten
    entries in this store carry an article title a human chose — `taˊɪrg̣ɪn` is
    filed at *Addison's disease*, `iteˊyun` at *Trichinellosis*, and those are
    editorial identifications no query would have made. The QID behind such a
    title is not a second opinion about which item is meant; it is the same
    identification, read off the sitelink the human already committed to. So
    this needs no gate and no judgement, and it refuses to touch an entry that
    has a `wikidata:` of its own — where the two disagree, the disagreement is a
    finding for a human and not a thing to resolve by overwriting.
    """
    from harness.cli._entity import _set_lines

    root = Path(a.root)
    store = load(root)
    todo = [(i, r) for i, r in sorted(store.items())
            if _has(r, "wikipedia") and not _has(r, "wikidata")
            and (i in a.idents if a.idents else True)]
    if not todo:
        print("nothing to fill — no entry carries a wikipedia: without a "
              "wikidata:")
        return 0

    got = _qids_for_titles(sorted({_has(r, "wikipedia").replace("_", " ")
                                   for _i, r in todo}))
    wrote = 0
    for ident, rec in todo:
        title = _has(rec, "wikipedia").replace("_", " ")
        qid = got.get(title)
        if not qid:
            print(f"  {ident:34} {title[:34]:34} NO ITEM BEHIND THAT ARTICLE")
            continue
        print(f"+ {ident:34} {title[:34]:34} {qid}")
        if a.commit:
            p = root / rec["path"] if not Path(rec["path"]).is_absolute() \
                else Path(rec["path"])
            text = _set_lines(p.read_text(encoding="utf-8"), "link",
                              sorted(rec["links"] + [f"wikidata:{qid}"]))
            parse(text, where=str(p))
            p.write_text(text, encoding="utf-8")
            wrote += 1
    print(f"\n{wrote} written" if a.commit else "\nreport only; --commit writes")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=".", help="repo root (default .)")
    sub = ap.add_subparsers(dest="action", required=True)

    p = sub.add_parser("propose", help="candidate identities, type-gated by "
                                       "class")
    p.add_argument("idents", nargs="*")
    p.add_argument("--class", dest="cls", default="",
                   help="only this entity class")
    p.add_argument("--missing", action="store_true",
                   help="only entries carrying no link: wikidata: yet")
    p.add_argument("--terms", type=int, default=4,
                   help="how many of an entry's names to ask for (default 4)")
    p.add_argument("--search", type=int, default=0, metavar="N",
                   help="for up to N entries the exact sweep missed, also run "
                        "the per-name prefix search and gate its results by "
                        "class. A round trip per name, so it is a number and "
                        "not a switch: a whole class through it takes a 429")
    p.add_argument("--pairs", dest="pairs_only", action="store_true",
                   help="print only the single-candidate rows, as the `ID=Q… "
                        "# name — description` lines `set --from` reads. A "
                        "worklist to edit and adopt, not an adoption")
    p.set_defaults(fn=run_propose)

    p = sub.add_parser("set", help="adopt an identity: link: wikidata:Q…, and "
                                   "link: wikipedia:… derived from it")
    p.add_argument("pairs", nargs="*", metavar="ID=Q…")
    p.add_argument("--from", dest="from_file", default="",
                   help="a file of ID=Q… lines; # comments allowed")
    p.add_argument("--replace", action="store_true",
                   help="overwrite an identity the entry already carries")
    p.add_argument("--commit", action="store_true")
    p.set_defaults(fn=run_set)

    p = sub.add_parser("fill", help="wikidata: derived from an authored "
                                    "wikipedia: article title")
    p.add_argument("idents", nargs="*")
    p.add_argument("--commit", action="store_true")
    p.set_defaults(fn=run_fill)

    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
