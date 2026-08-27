"""The edition lexicon: what an editor has written about one Tier-1 form.

**Deliberately thin, and the thinness is the design.** Everything a reader wants
about a native word is already derivable — the pronunciation by rule from the
notation (`ipa.impute`), the pages and printed lines it occurs on from `gt/ocr/`
(`lookup.index`), the language a collator assigned and the gloss the book prints
from committed TEI (`ids.glossary`). None of that is copied in here. A store
holding a second copy of a derived fact is the defect this project is organised
against, and the copy would go stale in the direction that hides it: the entry
would still read as an entry.

So a file holds exactly what nothing can derive — an **editor's note**, the
extra-textual clarification the book cannot make because it was written in 1904
and the reader is not. `edition/entities/` is the model: 42 files against thousands of
proper nouns, because it is not a census but the places somebody had something
to say. **A form with no file is not missing from the lexicon**; it is a form
nobody has written about yet, and its card renders in full from the derived
half.

**The identity is the exact surface form, NFD, and carries no language.** Two
consequences, both intended. The book sets one word two ways — `Čeˊwɪn` on 1-042
and `Čeˊwin` on 1-052, ruled a real ambiguity in `config/marks_exempt.json` — and a
headword scheme would have to pick a side, which is precisely what that ruling
says not to do; here they are two entries and `see:` may point one at the other
without asserting they are one word. And a form only becomes `ckt` when a
collator judges it, which has not happened for most of the corpus: an id
containing a language would leave every unjudged form unaddressable, in a store
whose whole point is that Americanist notation is phonetic and a form is
readable before anyone knows what language it is in.

**The slug is authored, and `handle_key` is only a suggestion.** The obvious
scheme — name the file after the form's typeable key — is measurably unusable:
over the corpus's 609 attested forms it produces 23 pairs differing only in case
(`Aiˊwan`/`aiˊwan` both key to `ai'wan`), which a case-insensitive filesystem
collapses to one file, and 34 keys containing a colon, the portability trap
`entities.py` says the class-as-directory layout exists to avoid. Worse, the
check that would catch it cannot: `handle_key` is non-injective by design, so
"the heading's form re-keys to the filename" passes on *both* of a colliding
pair while only one can exist. A human names the file, `check` refuses two names
that a filesystem might not tell apart, and the key stays what it was built to
be — a way to say a form out loud without retyping its glyphs.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from .marks import handle_key

LEXDIR = "edition/lexicon"

#: Same two states as the entity store, and for the same reason: `lexicon new`
#: writes `proposed`, and only a human moves an entry on.
STATUSES = ("proposed", "ratified")

_HDR = re.compile(r"^#\s+(\S.*?)\s*$", re.M)
_FIELD = re.compile(r"^-\s+([a-z]+):\s*(.*?)\s*$", re.M)
_SECTION = re.compile(r"^##\s+(.+?)\s*$", re.M)

#: The one authored section. Named here rather than accepted loosely so a
#: misspelt heading is a parse error and not a silently empty entry.
NOTE = "editor's note"


class Malformed(ValueError):
    """A file the parser will not guess at. The message names the file and why.

    `ValueError` for `entities.Malformed`'s reason: `cli.main`'s net is four
    concrete types and no project class, so a plain `Exception` is a traceback
    wherever a local handler does not happen to exist.
    """


def lex_dir(root: Path = Path(".")) -> Path:
    return root / LEXDIR


def norm_form(form: str) -> str:
    """A form as this store keys it: NFD, inner whitespace collapsed.

    NFD is folded silently rather than gated. The file is hand-maintained and can
    drift between edits, and an entry that failed to resolve because a session
    keyed a precomposed `ö` would be a silent miss — the failure class this
    project is organised against, and one a fold recovers completely.
    """
    return unicodedata.normalize("NFD", " ".join(form.split()))


def suggest_slug(form: str) -> str:
    """What `lexicon new` prints for a human to accept or override.

    The typeable key, reduced to what a filesystem is safe with. Reduced and not
    used raw: `handle_key`'s alphabet includes `:` and distinguishes case, and
    both are exactly what a filename must not depend on.
    """
    try:
        key = handle_key(form)
    except ValueError:
        key = unicodedata.normalize("NFKD", form)
    slug = re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-")
    return slug or "form"


def path_for(slug: str, root: Path = Path(".")) -> Path:
    return lex_dir(root) / f"{slug}.md"


def parse(text: str, where: str = "") -> dict:
    """One lexicon file's text → its record. Raises `Malformed` on anything unclear."""
    text = unicodedata.normalize("NFD", text)
    at = f"{where}: " if where else ""
    m = _HDR.search(text)
    if not m:
        raise Malformed(
            f"{at}no heading. The first line is `# <form>`, and the form is the "
            f"identity — the exact string as the page sets it, no language "
            f"prefix and no slug")
    form = norm_form(m.group(1))
    if not form:
        raise Malformed(f"{at}the heading names no form")

    first = _SECTION.search(text)
    head = text[:first.start()] if first else text
    fields: dict[str, list[str]] = {}
    for f in _FIELD.finditer(head):
        fields.setdefault(f.group(1), []).append(f.group(2))

    def one(key: str) -> str:
        v = fields.get(key, [])
        if len(v) > 1:
            raise Malformed(
                f"{at}`{key}:` given {len(v)} times; it takes one value")
        return v[0] if v else ""

    status = one("status")
    if status not in STATUSES:
        raise Malformed(
            f"{at}status {status!r} — one of {', '.join(STATUSES)}")
    sections: dict[str, str] = {}
    marks = list(_SECTION.finditer(text))
    for i, s in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        name = s.group(1).strip().lower()
        if name != NOTE:
            raise Malformed(
                f"{at}section `## {s.group(1)}` — the only authored section is "
                f"`## {NOTE}`. Glosses, attestations and pronunciation are "
                f"derived on every load and must not be written here")
        sections[name] = text[s.end():end].strip("\n")

    return {
        "form": form,
        "status": status,
        # A pointer, never a claim that the two are one word. The inverse is
        # derived at render time, as `property_rows` does for `contains`: a
        # hand-maintained back-link is two facts that will disagree.
        "see": norm_form(one("see")),
        "note": sections.get(NOTE, "").strip(),
    }


def set_status(text: str, status: str, where: str = "") -> str:
    """Move an entry's `status`, keyed off the line the parser actually reads.

    **Not a literal substring replace, and the difference is a false success.**
    `cli/_lexicon.run_ratify` searched the whole file for `- status: proposed`
    with `count=1`. Two things make that wrong together: `_FIELD` accepts
    `- status:proposed` with no space after the colon, and `parse` reads fields
    only from `head`, the text *before* the first `## section`. So on an entry
    spelled without the space, the first literal match was inside the editor's
    note — the verb rewrote that prose, left the status `proposed`, and reported
    `now: ratified, wrote: true`. A report asserting a change that did not
    happen, with nothing to notice it.

    So this reuses `_FIELD` itself rather than restating its shape, and searches
    the same `head` region `parse` does. The two cannot disagree about what a
    field line is, because there is only one pattern.
    """
    if status not in STATUSES:
        raise ValueError(f"status {status!r} — one of {', '.join(STATUSES)}")
    at = f"{where}: " if where else ""
    first = _SECTION.search(text)
    head = text[:first.start()] if first else text
    for m in _FIELD.finditer(head):
        if m.group(1) == "status":
            s, e = m.span(2)          # the value alone, not the line
            return text[:s] + status + text[e:]
    raise Malformed(
        f"{at}no `- status:` field above the first `##` section — that is where "
        f"`parse` reads it, so an entry without one does not load either")


def load(root: Path = Path(".")) -> dict:
    """The whole store, keyed by form. An absent store is `{}`, not an error."""
    d = lex_dir(root)
    if not d.is_dir():
        return {}
    out = {}
    for p in sorted(d.glob("*.md")):
        rec = parse(p.read_text(encoding="utf-8"), where=str(p))
        out[rec["form"]] = {**rec, "slug": p.stem, "path": str(p)}
    return out


def check(root: Path = Path(".")) -> dict:
    """The store's gate. Reports; the caller decides what a non-empty list means."""
    d = lex_dir(root)
    errors: list[str] = []
    unkeyable: list[dict] = []
    by_form: dict[str, str] = {}
    by_lower: dict[str, str] = {}
    store: dict[str, dict] = {}

    for p in sorted(d.glob("*.md")) if d.is_dir() else []:
        try:
            rec = parse(p.read_text(encoding="utf-8"), where=str(p))
        except Malformed as e:
            errors.append(str(e))
            continue
        rec = {**rec, "slug": p.stem, "path": str(p)}
        if rec["form"] in by_form:
            errors.append(
                f"{p}: form {rec['form']!r} is already the identity of "
                f"{by_form[rec['form']]}. Two files, one entry")
        by_form[rec["form"]] = str(p)
        # Case-insensitively, because a case-insensitive filesystem is not a
        # hypothetical: `Aiˊwan` and `aiˊwan` are two forms of this corpus whose
        # obvious slugs differ only in case, and there one file would overwrite
        # the other with nothing to show for it.
        if p.stem.lower() in by_lower and by_lower[p.stem.lower()] != str(p):
            errors.append(
                f"{p}: the slug {p.stem!r} differs from "
                f"{by_lower[p.stem.lower()]} only in case. A case-insensitive "
                f"filesystem holds one of these two files, silently")
        by_lower[p.stem.lower()] = str(p)
        try:
            handle_key(rec["form"])
        except ValueError as e:
            # Reported, never fatal and never dropped. The form is real and the
            # entry is fine; what it has not got is a canonical URL, and a
            # reader is owed that fact rather than left to find it.
            unkeyable.append({"form": rec["form"], "slug": p.stem,
                              "why": str(e)})
        store[rec["form"]] = rec

    for form, rec in store.items():
        if rec["see"] and rec["see"] not in store:
            errors.append(
                f"{rec['path']}: `see: {rec['see']}` resolves to no entry. It "
                f"names another form's heading exactly, and a pointer to "
                f"nothing reads as a resolved one")
        if rec["see"] == form:
            errors.append(f"{rec['path']}: `see:` points at its own form")

    return {"entries": len(store),
            "proposed": sum(1 for r in store.values()
                            if r["status"] == "proposed"),
            "unkeyable": unkeyable,
            "errors": errors,
            "ok": not errors}
