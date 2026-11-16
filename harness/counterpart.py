"""A native form's counterpart in another text by the same author, by rule.

The 1900 *Materials* and *The Chukchee* are one author's transcriptions of one set
of field notes, in two notations. `config/counterpart.json` maps the first's
sequences to the second's (`docs/multitext.md`, "Counterparts in *The Chukchee*"),
and this module matches a form against the other text's **ratified** index.

**A counterpart is a witness against a misreading, never a source.** What it
returns is `#mz` rule output, worked out on every call and stored nowhere. It may
send an editor back to the scan; it never supplies a glyph, and agreement with it
raises no rank.

Three answers per form:

- **exact**: some spelling the table derives is, letter for letter and mark for
  mark, a ratified form of the other text (`Ку́ркыl` is *Kuˊrkɪl*);
- **near**: the letters agree once marks are set aside, an obscure vowel (*ᴀ ᴇ ɪ*)
  is allowed to stand for any vowel, hyphens are ignored and either side may
  carry an ending of up to two letters (`кама́к` against *kaˊmak*: the stress sits
  on a different vowel, which is where to look);
- **none**.
"""
from __future__ import annotations

import itertools
import json
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

CONFIG = "config/counterpart.json"
#: More spellings than this from one form means the table is too loose to say
#: anything; the form is matched on the near test alone.
MAX_SPELLINGS = 256
#: Either side may carry this many trailing letters the other lacks: a Russian
#: case ending (`Мээ́мђына`, *Meeˊmhɪn*) or an inflection.
ENDING = 2
#: A near match needs this many letters, so two-letter particles match nothing.
MIN_LETTERS = 4


class CounterpartError(ValueError):
    """A correspondence table that cannot be read or trusted."""


@dataclass(frozen=True)
class Table:
    text: str                       # the other text's directory, beside this one
    pairs: dict[str, tuple[str, ...]]   # Materials sequence -> its spellings there
    obscure: frozenset[str]         # the other notation's obscure vowels
    vowels: frozenset[str]          # this side's vowels, once reduced
    path: Path

    def other_root(self, root: Path) -> Path:
        return (Path(root).resolve().parent / self.text).resolve()


def _nfd(s: str) -> str:
    return unicodedata.normalize("NFD", s)


def table(root: Path) -> Table | None:
    """The text's correspondence table, or None when it declares none."""
    p = Path(root) / CONFIG
    if not p.exists():
        return None
    return _load(str(p.resolve()), p.stat().st_mtime_ns)


@lru_cache(maxsize=8)
def _load(path: str, _mtime: int) -> Table:
    p = Path(path)
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise CounterpartError(f"{p}: not JSON: {e}") from None
    text, pairs = d.get("text"), d.get("pairs")
    if not (isinstance(text, str) and text and "/" not in text):
        raise CounterpartError(f"{p}: `text` is the other text's directory name, "
                               f"beside this one; got {text!r}")
    if not isinstance(pairs, dict) or not pairs:
        raise CounterpartError(f"{p}: `pairs` maps a sequence to its spellings")
    why = d.get("_why", {})
    out: dict[str, tuple[str, ...]] = {}
    for src, dst in pairs.items():
        if src.startswith("_"):
            continue
        if not (isinstance(dst, str) and _nfd(src) == src):
            raise CounterpartError(f"{p}: pairs[{src!r}] is a string of "
                                   "space-separated spellings, keyed in NFD")
        if not str(why.get(src, "")).strip():
            raise CounterpartError(f"{p}: pairs[{src!r}] has no `_why`: each pair "
                                   "carries its attestation")
        # An empty spelling is written `∅`: a letter the other notation omits.
        out[src] = tuple("" if s == "∅" else _nfd(s) for s in dst.split()) or ("",)
    obscure = frozenset(d.get("obscure", ""))
    vowels = frozenset(d.get("vowels", "aeiouɪɵᴇᴀ"))
    return Table(text, out, obscure, vowels, p)


def spellings(form: str, t: Table) -> list[str]:
    """Every spelling the table derives for `form`, longest sequence first; a
    character the table does not name passes through as itself."""
    form = _nfd(form).casefold()
    keys = sorted(t.pairs, key=len, reverse=True)
    parts: list[tuple[str, ...]] = []
    i = 0
    while i < len(form):
        k = next((k for k in keys if form.startswith(k, i)), None)
        if k:
            parts.append(t.pairs[k])
            i += len(k)
        else:
            parts.append((form[i],))
            i += 1
    n = 1
    for p in parts:
        n *= len(p)
        if n > MAX_SPELLINGS:
            return []
    return ["".join(c) for c in itertools.product(*parts)]


def reduce(s: str) -> str:
    """Letters only, casefolded: marks, modifier letters and hyphens set aside."""
    return "".join(c for c in _nfd(s).casefold()
                   if unicodedata.category(c)[0] == "L"
                   and unicodedata.category(c) != "Lm")


def _near(m: str, j: str, t: Table) -> bool:
    """`m` (reduced, derived) against `j` (reduced, the other text's)."""
    if min(len(m), len(j)) < MIN_LETTERS or abs(len(m) - len(j)) > ENDING:
        return False
    for a, b in zip(m, j, strict=False):
        if a != b and not (b in t.obscure and a in t.vowels):
            return False
    return True


def _skeleton(reduced: str, t: Table) -> str:
    """The consonants of a reduced spelling, for finding candidates quickly."""
    return "".join(c for c in reduced if c not in t.vowels and c not in t.obscure)


def other_index(root: Path, t: Table) -> dict:
    """The other text's ratified forms, as the counterpart match reads them."""
    from .web.stores import native
    idx = native(t.other_root(root))
    return index_forms({f["form"]: f for b in idx["buckets"].values()
                        for f in b["forms"].values()}, t)


def index_forms(forms: dict[str, dict], t: Table) -> dict:
    """`{form: {refs, lines, ...}}` as `match` reads it. Its own function so a
    test can hand it forms without building a second text."""
    exact: dict[str, list[str]] = {}
    by_skel: dict[str, list[tuple[str, str]]] = {}
    # A compound's parts are matchable too: the Materials sets `та́н̀ӈен wе́т̀һаw` as
    # two words where The Chukchee has *Taˊn˙ñɪn-wêˊthaw*. A part points at its
    # whole form, and the row says it matched a part.
    for f in forms:
        for piece in dict.fromkeys([f, *f.split("-")]):
            if piece != f and len(reduce(piece)) < MIN_LETTERS:
                continue
            exact.setdefault(_nfd(piece).casefold(), []).append(f)
            r = reduce(piece)
            by_skel.setdefault(_skeleton(r, t)[:3], []).append((r, f))
    return {"forms": forms, "exact": exact, "by_skel": by_skel}


def match(form: str, root: Path, t: Table | None = None,
          oidx: dict | None = None) -> dict:
    """`{form, status, matches: [{form, pages, refs, line}]}` for one native form;
    `status` is `exact`, `near` or `none`. `line` is the other text's first
    printed line holding the counterpart, which is the context an editor reads."""
    t = t or table(root)
    if t is None:
        return {"form": form, "status": "none", "matches": []}
    oidx = oidx or other_index(root, t)
    stem = form.split("’")[0]
    spells = spellings(stem, t)
    hits = []
    for s in spells:
        hits += oidx["exact"].get(s.casefold(), [])
    status = "exact" if hits else "none"
    if not hits:
        derived = {reduce(s) for s in spells} or {reduce(stem)}
        for d in derived:
            for r, f in oidx["by_skel"].get(_skeleton(d, t)[:3], []):
                if _near(d, r, t):
                    hits.append(f)
        status = "near" if hits else "none"
    # A compound with no counterpart whole may have one per part (`ӄор-емте́`
    # against *qor-êmtêˊ-qaˊa-raˊmkɪt*): its parts are matched alone, and a hit
    # is never better than near, since only part of the form was witnessed.
    if not hits and "-" in stem:
        for piece in stem.split("-"):
            if len(reduce(piece)) >= MIN_LETTERS:
                sub = match(piece, root, t, oidx)
                hits += [m["form"] for m in sub["matches"]]
        status = "near" if hits else "none"
    rows = []
    for f in dict.fromkeys(hits):
        rec = oidx["forms"][f]
        first = (rec.get("lines") or [{}])[0]
        rows.append({"form": f, "pages": len(rec["refs"]),
                     "part": reduce(f) not in {reduce(x) for x in spells},
                     "refs": " ".join(sorted(rec["refs"])[:6]),
                     "line": f"{first.get('ref', '')} l{first.get('line', '')}: "
                             f"{first.get('text', '')}".strip()})
    rows.sort(key=lambda r: -r["pages"])
    return {"form": form, "status": status, "matches": rows[:5]}


# ---------------------------------------------------------------------------
# What a reader was shown. The editor's ruling (2026-11-16): a reader may see a
# counterpart before keying, and every form it keyed after seeing one is marked.
# The mark is derived from what the verb wrote, never from what the reader says.

SHOWN = "counterparts.jsonl"


def record_shown(ref: str, root: Path, rows: list[dict]) -> Path:
    """Append what `lexicon counterpart` showed for page `ref`."""
    from .paths import review_dir
    p = review_dir(ref, root) / SHOWN
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps({"query": r["form"],
                                 "shown": [m["form"] for m in r["matches"]]},
                                ensure_ascii=False) + "\n")
    return p


def shown(ref: str, root: Path) -> set[str]:
    """Every counterpart form the reader of `ref` was shown."""
    from .paths import review_dir
    p = review_dir(ref, root) / SHOWN
    if not p.exists():
        return set()
    out: set[str] = set()
    for ln in p.read_text(encoding="utf-8").splitlines():
        try:
            out.update(json.loads(ln).get("shown", []))
        except json.JSONDecodeError:
            continue
    return out
