"""Find a ratified native form, and name it without retyping its glyphs.

Two halves of one mechanism, and the second is why the first is safe to have.

**The lookup** searches the Tier-1 forms a human has adjudicated in `gt/ocr/`,
returning each with its pages and the lines it was printed on, so a form's sense is
readable from where it occurs — `Kuluˊči` alone is a string, "south of Kuluˊči Bay"
is a place.

**The handle** is how a reader names one without keying it: `{Kulu'c^i}` in a
proposal, expanded by `proposal set` on write. `text` then holds the real form and
`as_typed` holds the line as the reader wrote it, so the review UI can show the
adjudicator a claim about a corpus match rather than a reading — which is the whole
point, because `CLAUDE.md` says a comparison whose witnesses may be one witness must
say so. A reader that quietly copies a corpus spelling stops being an independent
witness and the adjudicator's confirmation becomes a confirmation of the corpus.

**Why the ambiguity refusal is not a nicety.** `data/marks_exempt.json` records that
the book sets `Čeˊwɪn` (1-042) and `Čeˊwin` (1-052) — one word, two settings — and
that 1-042's reader flagged the disagreement instead of harmonizing to the older
page's ground truth. A lookup that answers with one spelling is a machine for
erasing that. So a bucket holding more than one form yields no handle at all, and an
**exemption does not restore it**: ruling that the book sets a word two ways is a
statement that the ambiguity is real, which is the strongest possible reason to
refuse to pick a side.

**The floor.** `--min-pages` counts pages *per bucket*, over all its forms together.
Per-form would be worse than useless: `Čeˊwɪn` and `Čeˊwin` have one page each, so a
per-form floor at the default deletes the corpus's only genuine ambiguity from the
lookup instead of refusing it. A floor may withhold a handle from a form the corpus
barely attests; it may never hide a conflict.

**It defaults to 1 — hapaxes get a key** (editor ruling). Most of this vocabulary is
rare: `reˊkkeñ` is set three times on `2-022` and nowhere else, `Ceˊčin` once, and a
floor of 2 withheld a key from both, so a reader retyped by hand exactly the forms
where a slip is least likely to be caught. Counting *occurrences* instead was
considered and refused: three occurrences on one page are one adjudication event, so
it would have loosened the floor without buying the independence the floor was for.
Allowing hapaxes outright is the same loosening, honestly labelled.

What makes it safe is that thinness stays **visible** rather than being laundered:
every form here was adjudicated by a human at the raster, `search` prints the count
and the pages beside each key, and `_expanded` writes `as_typed` so the review UI
badges a handled form as a corpus match. The adjudicator sees that the reader leaned
on the corpus and on how much of it. **The ambiguity refusal is untouched** — that
is the guard that matters, and it never had anything to do with the floor.

**`gt/ocr/` only.** The lookup's entire authority is that a human adjudicated these
marks at the raster. A list built from `mz/` would be garbled forms offered to be
copied verbatim — the failure this exists to prevent, inverted.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from .detectors import native_corpus_context
from .marks import fold, handle_key, load_config

# A handle is a key in braces. The character class is `handle_key`'s output
# alphabet — ASCII alphanumerics, the two load-bearing ASCII marks the key passes
# through (U+0027, U+002D), and the markers — so a brace holding anything else was
# never a handle and is reported as the stray brace it is.
HANDLE = re.compile(r"\{([A-Za-z0-9'\-_^.~:)=]+)\}")


def index(root: Path = Path(".")) -> dict:
    """Every attested form, bucketed, keyed, and carrying the lines it occurs on.

    Returns `{"buckets": {bucket: {...}}, "by_key": {key: bucket}, "unkeyable":
    {form: {...}}}`. `unkeyable` is named and never silently dropped: a token whose
    key cannot be built is one this instrument cannot offer, and a caller that
    reports "not found" without saying so has converted a gap into a corpus-wide
    negative.

    **`unkeyable` carries the same record a bucket's form does** — count, refs,
    lines, and a `key` of `None` — because a caller that wants every attested
    form rather than every *addressable* one has to be able to union the two
    without going back to the corpus. The reading view is that caller: pre-1918
    Russian is full of `й`, which is и + U+0306 under NFD and so trips the
    inventory detector, and every one of those words was invisible to the
    lexicon while this was a list of bare occurrences.
    """
    contrasts = load_config(root)["contrasts"]
    buckets: dict[str, dict] = {}
    unkeyable: dict[str, dict] = {}
    for r in native_corpus_context(root):
        tok = r["token"]
        try:
            key = handle_key(tok)
        except ValueError as e:
            u = unkeyable.setdefault(tok, {
                "form": tok, "key": None, "count": 0, "refs": set(),
                "lines": [], "why": str(e)})
            u["count"] += 1
            u["refs"].add(r["ref"])
            u["lines"].append({"ref": r["ref"], "line": r["line"],
                               "text": r["text"]})
            continue
        b = buckets.setdefault(fold(tok, contrasts),
                               {"forms": {}, "refs": set(), "count": 0})
        f = b["forms"].setdefault(key, {"form": tok, "key": key, "count": 0,
                                        "refs": set(), "lines": []})
        f["count"] += 1
        f["refs"].add(r["ref"])
        f["lines"].append({"ref": r["ref"], "line": r["line"], "text": r["text"]})
        b["refs"].add(r["ref"])
        b["count"] += 1
    by_key = {k: bk for bk, b in buckets.items() for k in b["forms"]}
    return {"buckets": buckets, "by_key": by_key, "unkeyable": unkeyable}


def spellings(bucket: dict) -> set[str]:
    """A bucket's distinct spellings, **case aside** — what "the book sets this word
    more than one way" counts, and the one definition `resolve` and `search` share.

    Case is position, not spelling: `keˊlet` in the body, `Keˊlet` opening a
    sentence and `KEˊLET` as a run-in heading are one word set three ways, and the
    case ladder in `_resolve_cased` lets a handle name any of them. What the
    ambiguity refusal is for is the book disagreeing about *marks* — `vaˊɪrgɪt`
    beside `vaˊɪrg̣ɪt`, `Čeˊwɪn` beside `Čeˊwin` — which no tool may settle.

    The two callers computed this separately and drifted the moment the corpus first
    held three cases of one word: `resolve` was taught the difference and `search`
    was not, so `lexicon lookup Ke'let` reported all three variants `ambiguous` and
    offered no key at all, for a word `expand` would happily have resolved.
    """
    return {f["form"].casefold() for f in bucket["forms"].values()}


def resolve(key: str, root: Path = Path("."), min_pages: int = 1,
            idx: dict | None = None) -> tuple[str | None, str]:
    """A key to its ratified form, or `(None, why)`.

    Every refusal is a refusal to guess, and each says which one it is so the caller
    can act: an unknown key is a typo or an unattested form, an ambiguous one is the
    book disagreeing with itself, a thin one is a form the corpus barely attests.
    """
    idx = idx if idx is not None else index(root)
    bucket = idx["by_key"].get(key)
    if bucket is None:
        return None, f"no ratified form has the key {key!r}"
    b = idx["buckets"][bucket]
    # **Case variants are one spelling, and the key picks among them** — see
    # `spellings`. Restoring `2-017` and `2-018` put `keˊlet`, `Keˊlet` and `KEˊLET`
    # in `gt/ocr/` at once, and counting forms rather than spellings stopped every
    # `{ke'let}` handle in the chapter resolving: the refusal firing hardest on the
    # word that needs it most. The message still lists every form, since a reader
    # meeting a real conflict needs to see the marks that differ.
    if len(spellings(b)) > 1:
        spelt = ", ".join(sorted(f["form"] for f in b["forms"].values()))
        return None, (f"{key!r} names one of {len(b['forms'])} spellings the corpus "
                      f"holds for this word ({spelt}) — the book sets it more than "
                      "one way and nothing here may pick for you. Read the raster "
                      "and key what it shows")
    if len(b["refs"]) < min_pages:
        return None, (f"{key!r} is attested on {len(b['refs'])} page(s), below the "
                      f"floor of {min_pages} — one page is a neighbour, not a "
                      "convention. Read the raster")
    # One word, possibly several cases of it: an exact key names its own case.
    # `by_key` is built from these keys, so the fallback is only ever reached by a
    # caller holding a bucket this index did not build.
    if key in b["forms"]:
        return b["forms"][key]["form"], ""
    return next(iter(b["forms"].values()))["form"], ""


# The three cases a form is set in, in the order a handle may climb: `keˊlet`
# lowercase in the body, `Keˊlet` capitalized at the head of a sentence, `KEˊLET` in
# caps as a run-in heading. All three occur, often on facing pages, and all three are
# the same word — which is why they share a bucket and why `resolve` no longer counts
# them as competing spellings.
_CASES = ("lowercase", "capitalized", "uppercase")


def _cased(s: str) -> list[str]:
    """The characters of `s` that *have* a case. `ˊ` U+02CA is a modifier letter and
    passes `isalpha`, so an `isalpha` filter would decide `keˊlet` is not lowercase."""
    return [c for c in s if c.islower() or c.isupper()]


def _case_rank(s: str) -> int | None:
    """Which of `_CASES` `s` is set in, or None for a shape the ladder cannot name
    (`McX`, a form with no cased character at all)."""
    cs = _cased(s)
    if not cs:
        return None
    if all(c.islower() for c in cs):
        return 0
    if cs[0].isupper() and all(c.islower() for c in cs[1:]):
        return 1
    if all(c.isupper() for c in cs):
        return 2
    return None


def _raise_case(form: str, rank: int) -> tuple[str | None, str]:
    """`form` re-cased to `rank`, or `(None, why)`.

    **Only ASCII letters are raised, and a form containing anything else refuses
    rather than approximating.** `str.upper()` is not safe over this inventory: `ɪ`
    U+026A maps to `Ɪ` U+0197, a letter the keying spec does not contain at all; `ǰ`
    becomes two characters; `ᴇ` and `ᴀ` map to themselves and would silently ignore
    the request, handing back a form that is not what the handle asked for. Since
    nothing here can know what the compositor set for a small-cap `ɪ` inside an
    all-caps heading, the honest answer is to refuse and let a reader look.

    Characters with no case are passed through untouched, so a combining mark keeps
    its base: `g̣enɪˊmlinet` capitalizes to `G̣enɪˊmlinet` with its dot below intact.
    """
    if rank == 0:
        return form, ""
    out, raised = [], False
    for c in form:
        if not (c.islower() or c.isupper()):
            out.append(c)
            continue
        if rank == 1 and raised:
            out.append(c)
            continue
        if not ("a" <= c <= "z" or "A" <= c <= "Z"):
            return None, (f"{c!r} is not an ASCII letter, and raising its case would "
                          "change the glyph rather than the case")
        out.append(c.upper())
        raised = True
    return "".join(out), ""


def _resolve_cased(key: str, root: Path, min_pages: int,
                   idx: dict) -> tuple[str | None, str]:
    """`resolve`, over the case ladder: an attestation enables its own case and every
    case above it.

    A form attested lowercase can be written `{ke'let}`, `{Ke'let}` or `{KE'LET}`; one
    attested only capitalized enables the last two; one attested only in caps enables
    only itself. **The ladder climbs and never descends** — the corpus capitalizes a
    proper name for a reason, and a handle that quietly lowered `Kuluˊči` would edit a
    ratified identity by a keystroke nobody reviewed. Descending is refused with the
    ratified key named, so a reader who meant it can key the form by hand and say why.

    Without this a reader either retypes the whole form — losing what the handle is
    for — or hands the adjudicator a line to re-case: `2-018` L21 was the latter, and
    the only purely mechanical miss in that batch's correction profile.

    An exact attestation is always preferred to a derived one, so a form the corpus
    holds in the requested case is returned as the corpus holds it, untransformed.
    """
    form, why = resolve(key, root, min_pages, idx)
    if form is not None:
        return form, ""
    want = _case_rank(key)
    if want is None:
        return None, why
    # The bucket is reachable by any case of the key, since all three share one.
    low = key.lower()
    for variant in (low, low[:1].upper() + low[1:], key.upper()):
        if variant in idx["by_key"]:
            src_form, src_why = resolve(variant, root, min_pages, idx)
            if src_form is None:
                return None, src_why          # ambiguous or too thin: say so, once
            have = _case_rank(variant)
            if have is None or have > want:
                return None, (
                    f"{key!r} asks for the {_CASES[want]} of a form the corpus "
                    f"attests {_CASES[have] if have is not None else 'otherwise'} "
                    f"({src_form!r}) — a handle may raise a form's case but never "
                    "lower it. If the page really sets it lower, key it by hand and "
                    "say so in a note")
            out, bad = _raise_case(src_form, want)
            if out is None:
                return None, (f"{key!r} asks for the {_CASES[want]} of {src_form!r}, "
                              f"and {bad}. Key the form by hand")
            return out, ""
    return None, why


def expand(text: str, root: Path = Path("."), min_pages: int = 1,
           idx: dict | None = None) -> tuple[str, list[str]]:
    """Substitute every handle in a line, or refuse the whole line.

    **Nothing half-expands.** `tei expand` leaves an unresolved handle exactly as it
    is rather than dropping it, so the fault stays where a reader will meet it; the
    same rule one stage earlier means a line with one bad handle is not written at
    all, since a partly-expanded line is a record of neither what was read nor what
    was meant.

    Returns `(expanded, refusals)`. A non-empty `refusals` means nothing was
    written. A stray `{` that is not a handle is its own refusal: the corpus keys
    no brace — 1-359 prints one joining two Russian names and its reader recorded
    it in a note, which is the treatment — so a brace in `text` is either a handle
    this cannot resolve or a character that does not belong there.
    """
    idx = idx if idx is not None else index(root)
    refusals: list[str] = []

    def sub(m: re.Match) -> str:
        form, why = _resolve_cased(m.group(1), root, min_pages, idx)
        if form is None:
            refusals.append(why)
            return m.group(0)
        return form

    out = HANDLE.sub(sub, text)
    # Only when nothing else refused: an unresolved handle is left in place by
    # design, so its brace would otherwise raise a second complaint restating the
    # first, and a refusal that says two things says neither clearly.
    if not refusals and ("{" in out or "}" in out):
        refusals.append(
            "a brace survives in the line and is not a handle this can read — "
            "no page keys a brace, so it is either a mistyped handle or a "
            "character that belongs in a note rather than in the reading")
    return out, refusals


def bare(s: str) -> str:
    """`s` reduced to bare ASCII alphanumerics, casefolded.

    **Applied to the query as well as to the haystack**, which is the whole point:
    a reduction on one side only is not a fuzzy match, it is a match against a
    spelling the caller has to guess. `Telqäˊp` has the key `Telqa:'p`, and a reader
    looking for it typed `telqa'p` — reasonable, and it found nothing, because the
    apostrophe it kept is one the key spells elsewhere and the `ä` it dropped is one
    the key spells `a:`. Reduced on both sides, `telqa'p`, `telqap`, `Telqäˊp` and
    `Telqa:'p` all land on `telqap` and all reach the form.

    ASCII-only is what makes the reduction agree across the two alphabets. A
    combining mark is not alphanumeric and falls out on its own, but `ˊ` U+02CA and
    `ɪ` U+026A are modifier letters and letters — `isalnum()` keeps both — so a
    reduction without the ASCII test would leave the stress mark in `telqaˊp` and
    never meet the key's `telqap`.

    **NFD first, and the form is named** (`keying_spec.md` §1). The corpus is NFD, so
    its `ä` is already `a` + U+0308 and reduces to `a`; a query typed at a terminal
    arrives NFC, where `ä` is one non-ASCII character that the ASCII test throws away
    whole — `Telqäˊp` reduced to `telqp` and matched nothing. Decomposing first is
    what lets a reader type the form exactly as the book prints it.
    """
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if c.isalnum() and c.isascii()).casefold()


NEARBY_SPAN = 12
NEARBY_MOST = 15


def nearby(ref: str, root: Path = Path("."), span: int = NEARBY_SPAN,
           most: int = NEARBY_MOST, min_pages: int = 1) -> list[dict]:
    """The forms most often keyed on the pages just before `ref`, with their handles.

    A reader can only look up what it thinks to look up. `2-082` queried the
    `kaˊmak` compounds on its page, never thought to query the word it got wrong,
    and keyed a sort two ways from its neighbour — while `2-087`, ten pages after
    the adjudication that ratified them, reached for `{e'un}` and `{mi'lhi_li_n}`
    and got them right, because it happened to try. This closes that gap from the
    other side: what the neighbourhood has recently been keyed as, offered before
    the reading rather than waited on.

    **It is an error-checking aid, not an input to composition.** The wording is
    `state.foreign_terms_nearby`'s and the rule is the same one: a form here says
    what the pages around this one were *adjudicated* to hold, and it emphatically
    does not license reading this page's ink to match. Tier-1 content is what this
    page sets.

    Three properties keep it on the right side of that line, and none is incidental:

      * **A word the book sets more than one way is shown as both, with no key.**
        `resolve` refuses a side of a live ambiguity and so does this, but refusing
        to *pick* is not a reason to conceal: a reader who cannot see that a word is
        contested will read its page as though it were settled, and `2-076` prints
        `g̣ɪˊrg̣ɪr` beside `g̣iˊrg̣itti` on adjacent lines. The pair is the
        information. `key` is empty on every row of such a bucket, so the block still
        cannot be what settles one, and the two spellings are kept adjacent because
        half of an ambiguity is worse than none of it.
      * **The handle is the offer, so leaning on it is recorded.** A reader that
        writes `{e'un}` gets `as_typed` on the line and the review UI badges it a
        corpus match rather than a reading. A form pasted from a prompt with no
        handle would be indistinguishable from an independent witness, which is the
        collapse `lookup`'s whole design is arranged against.
      * **The preceding `span` scan indices of the same part**, and nothing after.
        Not a corpus-wide frequency table: the point is what this stretch of the
        book has been talking about, and a global list is `lexicon native`.

    The window is arithmetic on the ref rather than a walk of `all_scans`, so this
    reads no derived tree and a clone with no `scans/` still renders a prompt. A
    gap in the range — a plate, a foldout — simply contributes nothing, which is
    what it holds.

    Nothing about how a form is built, segmented or related to any other form is
    computed or implied. These are strings the store holds and counts of them.
    """
    from .context import norm_ref, parse_ref

    part, num = parse_ref(norm_ref(ref))
    window = {f"{part}-{n:03d}" for n in range(max(1, num - span), num)}
    if not window:
        return []

    idx = index(root)
    groups = []
    for bucket, b in idx["buckets"].items():
        # The refusal is on the fold, as everywhere else: marking distinguishes, so
        # resting it on key equality would let a reader name one side by spelling it
        # exactly. See `spellings` and `test_the_precise_key_is_refused_too`.
        ambiguous = len(spellings(b)) > 1
        rows = []
        for key, f in sorted(b["forms"].items()):
            here = [ln for ln in f["lines"] if ln["ref"] in window]
            if not here:
                continue
            rows.append({"key": "" if ambiguous else key, "form": f["form"],
                         "count": len(here),
                         "pages": len({ln["ref"] for ln in here}),
                         "refs": " ".join(sorted({ln["ref"] for ln in here})),
                         "bucket": bucket, "ambiguous": ambiguous})
        if not rows or len({r["refs"] for r in rows}) < 1 or \
                len(b["refs"]) < min_pages:
            continue
        rows.sort(key=lambda r: (-r["count"], r["form"]))
        groups.append(rows)

    # **Capped by bucket, never by row.** Truncating a list of forms could cut a
    # contested word in half and show the reader one spelling as though it stood
    # alone — which is the one thing this must not do.
    groups.sort(key=lambda g: (-sum(r["count"] for r in g),
                               -max(r["pages"] for r in g), g[0]["form"]))
    return [r for g in groups[:most] for r in g]


def _terms(queries: list[str]) -> list[tuple[str, str]]:
    """Each query as `(casefolded, bare)`, plus its key form where it has one.

    **`bare` alone does not reduce the two sides alike, and the gap is the corpus's
    commonest glyph.** A small cap is one non-ASCII character, so `bare` drops it
    whole — `Taˊn˙ñɪn` reduces to `tannn` — while the key spells the same letter
    `i_`, whose ASCII `i` survives, giving `tannin`. The printed form therefore
    matched nothing, and the miss read exactly like a word the corpus lacks. The
    same holds for `ᴇ ᴀ ʟ ɵ` and for `ᵋ`/`ᵉ`, whose key is `e^`.

    `handle_key` is the conversion and already exists; it is applied here so a
    reader may type what the book prints. It raises on a glyph with no marker
    rather than dropping it, and that is left to fall through to the raw query:
    an uncatalogued character is a finding for `keying_spec.md` §2.16, not a
    reason for the search to fail.
    """
    out = []
    for q in queries:
        forms = [q]
        if not q.isascii():
            try:
                forms.append(handle_key(q))
            except ValueError:
                pass
        out += [(f.casefold(), bare(f)) for f in forms]
    return out


def _scan(idx: dict, terms: list[tuple[str, str]], rows: list, seen: set,
          min_pages: int) -> bool:
    """Append every form any term reaches. True if this pass found anything."""
    found = False
    for bucket, b in sorted(idx["buckets"].items()):
        ambiguous = len(spellings(b)) > 1
        pages = len(b["refs"])
        for key, f in sorted(b["forms"].items()):
            reduced = bare(key)
            hay = (key.casefold(), bucket.casefold(), f["form"].casefold(), reduced)
            if not (any(q in h for q, _ in terms for h in hay)
                    or any(qb and qb in reduced for _, qb in terms)):
                continue
            found = True
            usable = not ambiguous and pages >= min_pages
            seen.add(bucket)
            rows.append({
                "key": key if usable else "",
                "form": f["form"],
                "count": f["count"],
                "pages": pages,
                "refs": " ".join(sorted(f["refs"])),
                "ambiguous": ambiguous,
                "why": ("" if usable else
                        "the book sets this word more than one way" if ambiguous
                        else f"attested on {pages} page(s), below the floor "
                             f"of {min_pages}"),
            })
    return found


def search(queries: list[str], root: Path = Path("."), min_pages: int = 1,
           context: int = 2) -> dict:
    """Forms matching any query, with what a reader needs to judge them.

    Matched against the key, the bucket, the form and the key's bare-ASCII
    reduction, so `kulu`, `kuluci` and `Kulu'c^i` all reach `Kuluˊči`. Substring,
    not prefix: the interesting query is often a stem in the middle of a compound.
    A non-ASCII query is also matched as its key (`_terms`), so a reader may type
    the form as the book prints it — `bare` alone does not reduce the two sides
    alike, and small caps are where it parts.

    **Two silent wrong negatives are what this exists to stop**, both of which cost
    real readings: the printed form matching nothing, and a hyphenated compound the
    corpus holds only as its elements. `split` names the elements when the whole
    missed and the answer came from them, so a widened search says it widened.
    """
    idx = index(root)
    rows, seen = [], set()
    terms = _terms(queries)
    split = []
    # **The elements of a compound, but only once the whole has missed.** The corpus
    # indexes tokens, so a hyphenated form it holds only as its parts returns nothing
    # while every part is ratified — `Aˊtal-Taˊn˙ñɪn` misses and `Taˊn˙ñɪn` does not,
    # which is how `3-125` hand-keyed a form attested ten times on six pages. Kept as
    # a fallback rather than folded into the first pass: querying a compound should
    # answer about the compound where the corpus has one, and widening unconditionally
    # would bury that row under every match for each element.
    if not _scan(idx, terms, rows, seen, min_pages):
        split = [p for q in queries for p in q.split("-")
                 if len(bare(p)) >= 2 and p != q]
        if split:
            _scan(idx, _terms(split), rows, seen, min_pages)
    lines = [ln for bucket in sorted(seen)
             for f in idx["buckets"][bucket]["forms"].values()
             for ln in f["lines"][:context]]
    return {
        "queries": " ".join(queries),
        # Empty unless the whole query missed and its elements answered. A reader
        # that sees this got a different question answered than the one it asked.
        "split": " ".join(split),
        "min_pages": min_pages,
        "forms_indexed": sum(len(b["forms"]) for b in idx["buckets"].values()),
        # **Stated on every run, because an empty result is not a corpus-wide
        # negative.** The selection requires an inventory glyph, so a native token
        # carrying no mark at all — a bare `c`, `s`, `j`, `x`, `h` — is invisible
        # here by construction. "Not found" means not found *by this instrument*.
        "floor": "forms carrying no inventory glyph are invisible to this index; "
                 "an empty result is not evidence the corpus lacks the word",
        # Distinct forms, not occurrences: the number is read as "how much of
        # the corpus this instrument cannot offer", and a form set twenty times
        # is one word missing from the index rather than twenty.
        "unkeyable": len(idx["unkeyable"]),
        "matches": rows,
        "context": lines,
    }
