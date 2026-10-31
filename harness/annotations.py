"""The editor's own voice over the book: notices and supplements.

Everything else `edition/` serves is either the book or a handle on the book —
the collated text, an entity's card, a form's card, the atlas. This store is the
one place the editor speaks *as the editor*, and the two classes exist because
the two things an editor needs to say want opposite placement:

    notice      necessary retrospective context, or a correction. Renders
                **above** what it attaches to, before the reader meets it.
    supplement  further material, mostly on the web. Renders **below**, after
                the reader is done with the text.

**The class is the placement.** `ANNOTATION_CLASSES` states it once, here, so no
file and no template can disagree about where a notice goes, and an author
cannot put one in the wrong place by typing a field. It is the same ruling
`AUTO_VALUES` makes for the entity store's alias modes: a closed vocabulary whose
consequence is derived rather than restated.

**Attachment is declared on the annotation and never on the target.** One file
carries the whole join, so adding a notice touches no page, no entity and no
`toc.json` entry; and the authored order of `attaches:` survives to become the
"attached to" list a reader sees. The alternative — a `notices:` field on every
page that wanted one — would put the same fact in fifteen files and give the
gate fifteen places to find it stale.

**`status:` gates attachment, not the annotation's own page.** A `proposed`
annotation has a URL, renders there with its status pill, and attaches to
nothing. The asymmetry is the point: an entity card is reached by a click, but a
notice is the editor's voice inserted at the top of the artifact, *unasked*, and
rendering an unratified one there would be the edition asserting something no
human signed. A reviewer still has to read it before ratifying, which is exactly
what the standalone page is for.

The section-attachment problem — a notice on `chII.1` reaching that section's
pages — is not solved here on purpose. See `for_page`.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from . import entities
from .refs import norm_ref

ANNDIR = "edition/annotations"

#: The classes, each mapped to where it renders relative to what it attaches to.
#: Stated once so that placement is derived from the identity and never authored
#: — a `- placement: top` field could contradict the directory a file sits in,
#: and nothing could say which of the two was meant.
ANNOTATION_CLASSES = {"notice": "top", "supplement": "bottom"}

#: Same two states as the entity and lexicon stores, and for the same reason:
#: `annotation new` writes `proposed`, and only a human moves an entry on.
STATUSES = ("proposed", "ratified")

#: What an `attaches:` value may name. Namespaced rather than three separate
#: fields, because `check`, `coverage` and every resolver want one ordered list
#: of targets — three fields would be merged back into that list at parse time,
#: which is three spellings of one structure, and would lose the authored order
#: the "attached to" list prints in.
ATTACH_KINDS = ("page", "toc", "entity")

#: The authored sections, closed. `## full` and deliberately **not** `## page`:
#: "page" already means a leaf of the book everywhere in this repository —
#: `PP-NNN`, `/edition/page/`, `page.html`, `paths.all_refs` — and a section
#: named after the corpus's central noun is a trap for every later reader of
#: this module.
SUMMARY, FULL, LINKS = "summary", "full", "links"
SECTIONS = (SUMMARY, FULL, LINKS)

#: Every key `parse` reads, refused rather than ignored when it is not one of
#: these — `entities.KNOWN_FIELDS`' rule, adopted for its reason: a typo'd
#: `- attachs:` that parsed cleanly into nothing would produce an annotation
#: attached to less than its author wrote, and every gate would pass.
#:
#: **There is deliberately no `link:` field.** The entity store's `link:` holds
#: an *identifier* that `edition_ui.LINK_KINDS` turns into an address; the
#: `## links` table below holds URLs. Two ways to record a link in one file
#: would be one too many, and the table is the one that can be checked.
KNOWN_FIELDS = frozenset({"status", "attaches"})

LINK_FIELDS = ("alias", "url", "title", "note")

#: What `edition_ui._LINK` will accept once `expand_links` has built a markdown
#: link out of a row. Held here rather than imported so this module stays free
#: of the web layer, and asserted against the real thing by a test.
LINK_SCHEMES = ("http://", "https://")

# The three regexes below are the shape `harness/entities.py` :313-343 settled
# on, copied rather than imported: they are private there, and the two stores
# have to stay free to diverge. `_FIELD` keeps the `[a-z][a-z-]*` key pattern
# and not `[a-z]+` — the hyphen is what `part-of:` needed, and a narrower
# pattern silently discarded that field for as long as it was wrong.
_HDR = re.compile(r"^#\s+([a-z]+):([a-z0-9][a-z0-9-]*)\s+—\s+(.+?)\s*$", re.M)
_FIELD = re.compile(r"^-\s+([a-z][a-z-]*):\s*(.*?)\s*$", re.M)
_SECTION = re.compile(r"^##\s+(\S+)\s*$", re.M)
_ROW = re.compile(r"^\|(.*)\|\s*$", re.M)

#: A links-table alias, and **the colon is what makes the two bracket forms
#: decidable**. `entities.WIKILINK` requires a `class:slug` with a colon in it,
#: so `[[people:mongoloids]]` is an entity reference and `[[melodiya-1974]]` is
#: a row of this file's own links table, and no rule has to guess which was
#: meant. An alias may therefore never contain a colon.
_ALIAS = re.compile(r"^[a-z0-9][a-z0-9-]*$")
LINKREF = re.compile(r"\[\[([a-z0-9][a-z0-9-]*)\]\]")

#: A ToC id as `edition/toc.json` spells one: `chII`, `chXIX.10`,
#: `front.authorities-quoted`. Shape only — that the id *exists* is `check`'s
#: question, because `parse` never reads a file.
_TOCID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]*$")


class Malformed(ValueError):
    """A file the parser will not guess at. The message names the file and why.

    `ValueError` for `entities.Malformed`'s reason: `cli.main`'s net is four
    concrete types and no project class, so a plain `Exception` reaches the user
    as a traceback from every consumer that has no local handler.
    """


def ann_dir(root: Path = Path(".")) -> Path:
    return root / ANNDIR


def split_id(ann_id: str) -> tuple[str, str]:
    """`"notice:physical-anthropology"` → `("notice", "physical-anthropology")`.

    Every caller that takes an identity from outside goes through here, so the
    error message for a malformed one is the same wherever it is wrong.
    """
    cls, sep, slug = ann_id.partition(":")
    if not sep or not cls or not slug:
        raise ValueError(
            f"{ann_id!r}: an annotation's identity is `class:slug` — "
            f"`notice:physical-anthropology`, not a bare slug")
    if cls not in ANNOTATION_CLASSES:
        raise ValueError(
            f"{ann_id!r}: unknown class {cls!r}. One of: "
            f"{', '.join(sorted(ANNOTATION_CLASSES))} — and the class is also "
            f"the placement, `notice` above what it attaches to and "
            f"`supplement` below")
    return cls, slug


def path_for(ann_id: str, root: Path = Path(".")) -> Path:
    cls, slug = split_id(ann_id)
    return ann_dir(root) / cls / f"{slug}.md"


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_attach(raw: str, at: str = "") -> dict:
    """One `- attaches:` line → a typed target. Raises `Malformed` on anything else.

    Three forms, told apart by the namespace they name and by nothing else:

        - attaches: page:3-060                a leaf of the book
        - attaches: toc:chII.1                a section of the printed Contents
        - attaches: entity:people:mongoloids  an entry in the encyclopedia

    The entity form carries a second colon, which is harmless: the split is on
    the *first* one, so `entity:people:mongoloids` yields the kind `entity` and
    the value `people:mongoloids`, which is exactly the identity the entity
    store uses.

    **Shape only. Nothing here touches the filesystem** — `entities.parse` draws
    the same line, and it is what lets a record be parsed, tested and reasoned
    about without a repository around it. Whether the target *exists* is
    `check`'s question.
    """
    kind, sep, value = raw.strip().partition(":")
    if not sep or not value:
        raise Malformed(
            f"{at}`attaches: {raw}` — a target is `kind:value`, one of "
            f"{', '.join(f'`{k}:`' for k in ATTACH_KINDS)}. "
            f"`attaches: 3-060` names no kind, and a bare ref could as easily "
            f"be a folio")
    if kind not in ATTACH_KINDS:
        raise Malformed(
            f"{at}`attaches: {raw}` — unknown kind {kind!r}. One of: "
            f"{', '.join(ATTACH_KINDS)}")

    if kind == "page":
        # Normalised, so `page:1-55` and `page:1-055` cannot mint two
        # attachments to one leaf; and `norm_ref` refuses a bare integer, which
        # is the corpus-wide rule that a page number names no page.
        try:
            value = norm_ref(value)
        except ValueError as exc:
            raise Malformed(f"{at}`attaches: {raw}` — {exc}") from exc
    elif kind == "entity":
        try:
            entities.split_id(value)
        except ValueError as exc:
            raise Malformed(f"{at}`attaches: {raw}` — {exc}") from exc
    elif not _TOCID.match(value):
        raise Malformed(
            f"{at}`attaches: {raw}` — {value!r} is not a ToC id. They are "
            f"spelled `chII`, `chXIX.10`, `front.alphabet`, and "
            f"`edition/toc.json` is the list")

    return {"kind": kind, "value": value, "raw": f"{kind}:{value}"}


def _link_rows(text: str, at: str = "") -> list[dict]:
    """The `## links` table → rows. Raises `Malformed` on a row that cannot render.

    The validation here is not fussiness: `expand_links` builds a markdown
    `[title](url)` out of every row, and `edition_ui._LINK` is
    `\\[([^\\]\\n]+)\\]\\(([^\\s()<>]+)\\)`. So a `]` in a title or a space in a
    URL does not produce a broken link — it produces a link that silently fails
    to render *as a link*, leaving raw brackets in the reader's prose. The table
    is checkable and prose links are not, and this is the whole of what that
    buys.
    """
    rows: list[dict] = []
    aliases: set[str] = set()
    urls: set[str] = set()
    for row in _ROW.finditer(text):
        cells = _cells(row.group(1))
        if len(cells) < 2 or set("".join(cells)) <= set("-: "):
            continue                      # the header rule, or a blank row
        if cells[0].lower() == "alias":
            continue                      # the header row's own labels
        alias, url = cells[0], cells[1]
        title = cells[2] if len(cells) > 2 else ""
        note = cells[3] if len(cells) > 3 else ""

        if not _ALIAS.match(alias):
            raise Malformed(
                f"{at}link alias {alias!r}: an alias is lower-case letters, "
                f"digits and hyphens — and **never a colon**, which is what "
                f"tells `[[melodiya-1974]]` (a row of this table) from "
                f"`[[people:mongoloids]]` (an entity)")
        if alias in aliases:
            raise Malformed(f"{at}link alias {alias!r} listed twice in one file")
        aliases.add(alias)

        if not url.lower().startswith(LINK_SCHEMES):
            raise Malformed(
                f"{at}link {alias!r}: {url!r} is not an http or https URL. "
                f"Nothing else is rendered as a link, and a scheme that is not "
                f"on that list survives escaping untouched")
        if any(c in url for c in " \t()<>"):
            raise Malformed(
                f"{at}link {alias!r}: the URL holds a space, a parenthesis or "
                f"an angle bracket, so the markdown link built from this row "
                f"would not render as one")
        if url in urls:
            raise Malformed(
                f"{at}link {alias!r}: this URL is already on another row. One "
                f"target, one alias — two aliases for one URL would put the "
                f"same shelf entry in front of a reader twice")
        urls.add(url)

        if not title:
            raise Malformed(
                f"{at}link {alias!r}: no title. The title is what the prose "
                f"shows where the alias resolves, so a row without one renders "
                f"as an empty link")
        if "]" in title:
            raise Malformed(
                f"{at}link {alias!r}: the title holds a `]`, which would close "
                f"the markdown link early and leave brackets in the prose")

        rows.append({"alias": alias, "url": url, "title": title, "note": note})
    return rows


def parse(text: str, where: str = "") -> dict:
    """One annotation file's text → its record. Raises `Malformed` on anything unclear.

    NFD on read, as the entity and lexicon stores are: the file is
    hand-maintained, it can drift between edits, and a title's normal form must
    not depend on which session keyed it.
    """
    text = unicodedata.normalize("NFD", text)
    at = f"{where}: " if where else ""
    m = _HDR.search(text)
    if not m:
        raise Malformed(
            f"{at}no heading. The first line is `# class:slug — Title`, and it "
            f"is where the identity and the display title live")
    cls, slug, title = m.group(1), m.group(2), m.group(3)
    if cls not in ANNOTATION_CLASSES:
        raise Malformed(
            f"{at}unknown class {cls!r} in the heading. One of: "
            f"{', '.join(sorted(ANNOTATION_CLASSES))}")

    # Fields are the lines above the first `##`; a `- attaches:` written inside
    # the prose is prose. `entities.parse` draws the line the same way, and
    # `lexicon.set_status` exists because a writer that did not draw it rewrote
    # a sentence and reported a change that had not happened.
    first = _SECTION.search(text)
    head = text[:first.start()] if first else text
    fields: dict[str, list[str]] = {}
    for f in _FIELD.finditer(head):
        fields.setdefault(f.group(1), []).append(f.group(2))

    unknown = sorted(set(fields) - KNOWN_FIELDS)
    if unknown:
        raise Malformed(
            f"{at}unknown field{'s' if len(unknown) > 1 else ''} "
            f"{', '.join(f'`{u}:`' for u in unknown)} — one of "
            f"{', '.join(sorted(KNOWN_FIELDS))}. A field this store does not "
            f"read is a fact nothing carries")

    def one(key: str) -> str:
        v = fields.get(key, [])
        if len(v) > 1:
            raise Malformed(f"{at}`{key}:` given {len(v)} times; it takes one value")
        return v[0] if v else ""

    status = one("status")
    if status not in STATUSES:
        raise Malformed(f"{at}status {status!r} — one of {', '.join(STATUSES)}")

    attaches, seen = [], set()
    for raw in fields.get("attaches", []):
        target = parse_attach(raw, at)
        if target["raw"] in seen:
            raise Malformed(
                f"{at}`attaches: {target['raw']}` listed twice in one file; it "
                f"would render the annotation twice on the same thing")
        seen.add(target["raw"])
        attaches.append(target)

    # **An unknown section is refused, and this store is stricter than the
    # entity store on purpose.** There, an unrecognised heading is inert prose.
    # Here a `## Summary` typo would yield an *empty summary*, and an empty
    # summary renders as a blank editorial banner across the top of a page of
    # the book. `lexicon.parse` refuses a stray heading for the same shape of
    # reason. Compared lower-cased and stripped, so the refusal is about the
    # name and not about the shift key.
    sections: dict[str, str] = {}
    marks = list(_SECTION.finditer(text))
    for i, s in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        name = s.group(1).strip().lower()
        if name not in SECTIONS:
            raise Malformed(
                f"{at}section `## {s.group(1)}` — the authored sections are "
                f"{', '.join(f'`## {s}`' for s in SECTIONS)}. The long text is "
                f"`## {FULL}` and not `## page`, because a page in this corpus "
                f"is a leaf of the book")
        sections[name] = text[s.end():end].strip("\n")

    summary = sections.get(SUMMARY, "").strip()
    if not summary:
        raise Malformed(
            f"{at}no `## {SUMMARY}`. It is what renders inline wherever this "
            f"annotation attaches, so an annotation without one would put an "
            f"empty block on a page")

    links = _link_rows(sections.get(LINKS, ""), at)
    defined = {r["alias"] for r in links}
    prose = f"{summary}\n{sections.get(FULL, '')}"
    used = set(LINKREF.findall(prose))
    if missing := sorted(used - defined):
        raise Malformed(
            f"{at}{', '.join(f'`[[{a}]]`' for a in missing)} resolves to no row "
            f"of `## {LINKS}`. A bracketed name with no colon is a link alias; "
            f"one with a colon is an entity")

    return {
        "id": f"{cls}:{slug}",
        "class": cls,
        "slug": slug,
        "title": title,
        "status": status,
        # Derived from the class, never read from a field. There is no spelling
        # for an annotation that disagrees with its own directory.
        "placement": ANNOTATION_CLASSES[cls],
        "attaches": attaches,
        "summary": summary,
        "full": sections.get(FULL, "").strip(),
        "links": links,
        # The aliases the prose actually reaches for, so `check` can report a
        # shelf entry nothing discusses without gating on it.
        "used_links": sorted(used),
    }


def expand_links(text: str, links: list[dict]) -> str:
    """`[[alias]]` → `[title](url)`, before any markup rule sees the text.

    **This is why `edition_ui` needs no change at all.** `inline_html` resolves
    `entities.WIKILINK` through `_entity_link`, and that function's whole safety
    argument is that its rule set is closed — it knows one store and renders
    everything else as escaped text. Teaching it a second store would widen the
    set that argument rests on. Rewriting the alias into an ordinary markdown
    link *first* means the result goes through the `_LINK` rule and the
    `LINK_SCHEMES` allowlist that were already there, with no new markup path
    and no new `| safe`.

    Runs before escaping, which is safe because every part it substitutes is
    validated: `_link_rows` has already refused a non-http URL, a URL holding
    a paren or a space, and a `]` in a title. The title itself is authored text
    and is escaped downstream like any other prose.

    An entity reference is untouched: `LINKREF` has no colon in its character
    class, and `entities.WIKILINK` requires one.
    """
    by_alias = {r["alias"]: r for r in links}

    def sub(m: re.Match) -> str:
        row = by_alias.get(m.group(1))
        # An unresolved alias is left exactly as written rather than dropped:
        # `parse` refuses one, so reaching this means a caller assembled a
        # record by hand, and visible brackets are a better report than silence.
        return f"[{row['title']}]({row['url']})" if row else m.group(0)

    return LINKREF.sub(sub, text)


def set_status(text: str, status: str, where: str = "") -> str:
    """Move an annotation's `status`, keyed off the line the parser reads.

    **Not a literal substring replace**, for the false success `lexicon.py`
    records in full: `_FIELD` accepts `- status:proposed` with no space, and
    fields are read only from the head, so on a file spelled that way the first
    literal match in the whole text can sit inside `## full` — rewriting that
    prose, leaving the status alone, and reporting a ratification that did not
    happen.
    """
    if status not in STATUSES:
        raise ValueError(f"status {status!r} — one of {', '.join(STATUSES)}")
    at = f"{where}: " if where else ""
    first = _SECTION.search(text)
    head_end = first.start() if first else len(text)
    for f in _FIELD.finditer(text[:head_end]):
        if f.group(1) == "status":
            # `end(2)`: the field's `\s*$` runs on through the blank line where
            # this is the head's last field, and the next heading would join it.
            return f"{text[:f.start()]}- status: {status}{text[f.end(2):]}"
    raise Malformed(f"{at}no `- status:` line to move")


def load(root: Path = Path(".")) -> dict[str, dict]:
    """Every annotation, keyed by identity.

    An absent store is `{}` and never an error: this store is young, a clone may
    not have one yet, and the reading view asks for it on every page.
    """
    out: dict[str, dict] = {}
    base = ann_dir(root)
    if not base.is_dir():
        return out
    for path in sorted(base.glob("*/*.md")):
        rec = parse(path.read_text(encoding="utf-8"), str(path))
        rec |= {"dir_class": path.parent.name, "stem": path.stem, "path": path}
        out[rec["id"]] = rec
    return out


def renderable(store: dict[str, dict]) -> dict[str, dict]:
    """The subset that may attach to anything: the ratified ones.

    One place, so no route and no template re-derives the rule. `proposed`
    records are still served at their own URL — see the module docstring for why
    the two questions are not the same question.
    """
    return {k: v for k, v in store.items() if v["status"] == "ratified"}


def has_toc_attachments(store: dict[str, dict]) -> bool:
    """Does any ratified annotation attach to a ToC section?

    The reading view asks before printing its unwitnessed-folio sentence. Without
    this guard, 452 leaves would each grow a banner explaining why they cannot
    show a kind of annotation nobody has written.
    """
    return any(t["kind"] == "toc"
               for rec in renderable(store).values() for t in rec["attaches"])


def _placed(recs: list[dict]) -> dict[str, list[dict]]:
    """Records → `{"top": [...], "bottom": [...]}`, each sorted `(class, slug)`.

    The sort is mechanical and stable. Ranking two notices by editorial
    importance is not something a sort can do, and a heuristic that pretended to
    would be a judgement nothing authored. If it ever matters, the answer is an
    authored rank field.
    """
    out: dict[str, list[dict]] = {"top": [], "bottom": []}
    for rec in sorted(recs, key=lambda r: (r["class"], r["slug"])):
        out[rec["placement"]].append(rec)
    return out


def for_entity(store: dict[str, dict], ident: str) -> dict[str, list[dict]]:
    return _placed([r for r in renderable(store).values()
                    if any(t["kind"] == "entity" and t["value"] == ident
                           for t in r["attaches"])])


def for_toc(store: dict[str, dict], toc_id: str) -> dict[str, list[dict]]:
    return _placed([r for r in renderable(store).values()
                    if any(t["kind"] == "toc" and t["value"] == toc_id
                           for t in r["attaches"])])


def for_page(store: dict[str, dict], ref: str,
             toc_ids: list[str] | None = None) -> dict[str, list[dict]]:
    """What attaches to this leaf: named directly, or through a section of it.

    **`toc_ids` is passed in and never computed here, and this function never
    touches the filesystem.** It is the one design decision in this module worth
    arguing for.

    Placing a leaf in a section runs `ref → folio → toc ids`, and 452 of the
    book's 732 folios have no witness, so the middle step usually refuses. If
    that chain lived here, the refusal would be buried inside a function whose
    return type is a list — and an empty list would mean two different things at
    once: *no annotation attaches here*, and *we cannot say whether one does*.
    That is the exact shape `docs/edition.md` names for the contents panel, where
    the ruling is that the refusal is a sentence and not a silence. Only the
    caller holds the folio, so only the caller can say which happened.

    It also keeps `apparatus.folio_of` — a scan of the whole index per ref — off
    the per-page path; `stores.folio_by_ref` inverts that index once for exactly
    this reason.

    Passing no `toc_ids` therefore means *this leaf is placed in no section*,
    never *look them up for me*.
    """
    ref = norm_ref(ref)
    ids = set(toc_ids or ())
    hits = []
    for rec in renderable(store).values():
        for t in rec["attaches"]:
            if (t["kind"] == "page" and t["value"] == ref) or \
               (t["kind"] == "toc" and t["value"] in ids):
                hits.append(rec)
                break
    return _placed(hits)


def check(root: Path = Path("."), tick=None) -> dict:
    """The store gate: every file parses, and every target it names resolves.

    **What is deliberately not checked here: that a `page:` ref names a leaf the
    book actually has.** There is no leaf universe a clone can read — `scans/` is
    derived and ignored, and the per-part maxima are a fact `seam.next_ref`
    declines to encode a second time, on the ground that a number in two places
    is a number that will drift. So the shape is gated (`norm_ref` refuses a bare
    integer, and `1-55` and `1-055` normalise to one attachment) and *existence*
    is `reach`'s answer, where the folio index is being read anyway.
    """
    errors: list[str] = []
    store: dict[str, dict] = {}
    base = ann_dir(root)

    # A file directly under the store root is invisible to `glob("*/*.md")` —
    # it would be silently unread rather than wrong, which is the failure this
    # project is organised against. `entities.check` names the same case.
    for stray in sorted(base.glob("*.md")) if base.is_dir() else []:
        errors.append(
            f"{stray}: a file directly under {ANNDIR}/ — an annotation lives in "
            f"its class's directory, {'/ or '.join(sorted(ANNOTATION_CLASSES))}/. "
            f"Nothing reads this file")

    for path in sorted(base.glob("*/*.md")) if base.is_dir() else []:
        if tick:
            tick()
        try:
            rec = parse(path.read_text(encoding="utf-8"), str(path))
        except Malformed as exc:
            errors.append(str(exc))
            continue
        if rec["class"] != path.parent.name:
            errors.append(
                f"{path}: heading says `{rec['id']}` but the file sits in "
                f"{path.parent.name}/. The directory is the class")
            continue
        if rec["slug"] != path.stem:
            errors.append(
                f"{path}: heading says slug {rec['slug']!r} but the filename "
                f"says {path.stem!r}. The filename is the slug")
            continue
        if rec["id"] in store:
            errors.append(f"{path}: a second file claiming {rec['id']}")
            continue
        rec |= {"dir_class": path.parent.name, "stem": path.stem, "path": path}
        store[rec["id"]] = rec

    ents = entities.load(root)
    from .state import load_toc
    toc_ids = {e["id"] for e in load_toc(root)}

    unused: list[str] = []
    for ident, rec in sorted(store.items()):
        where = rec["path"]
        if not rec["attaches"]:
            errors.append(
                f"{where}: attaches to nothing. An annotation with no target has "
                f"a URL and no way in — nothing on any page, card or section "
                f"leads to it")
        for t in rec["attaches"]:
            if t["kind"] == "entity" and t["value"] not in ents:
                errors.append(
                    f"{where}: `attaches: {t['raw']}` — no such entry in "
                    f"{entities.ENTDIR}/")
            elif t["kind"] == "toc" and t["value"] not in toc_ids:
                errors.append(
                    f"{where}: `attaches: {t['raw']}` — no such id in "
                    f"edition/toc.json")

        prose = f"{rec['summary']}\n{rec['full']}"
        for target in entities.WIKILINK.findall(prose):
            cls = target.split(":", 1)[0]
            # An annotation reference *looks* like an entity reference and would
            # be rendered as a dangling one by `edition_ui._entity_link`, which
            # knows a single store — silently, and in the reader's prose. Named
            # with its alternative rather than left to the generic message.
            if cls in ANNOTATION_CLASSES:
                errors.append(
                    f"{where}: `[[{target}]]` — one annotation cannot reference "
                    f"another with brackets, because only the entity store is "
                    f"resolved there. Write a markdown link to "
                    f"`/edition/annotation/{target}` instead")
            elif target not in ents:
                errors.append(f"{where}: `[[{target}]]` resolves to nothing")

        # A shelf may hold more than the summary discusses, so this is a row in
        # the report and never a gate.
        for row in rec["links"]:
            if row["alias"] not in rec["used_links"]:
                unused.append(f"{ident} {row['alias']}")

    proposed = sorted(k for k, v in store.items() if v["status"] != "ratified")
    return {
        "annotations": len(store),
        "notices": sum(1 for v in store.values() if v["class"] == "notice"),
        "supplements": sum(1 for v in store.values()
                           if v["class"] == "supplement"),
        "attachments": sum(len(v["attaches"]) for v in store.values()),
        "links": sum(len(v["links"]) for v in store.values()),
        "proposed": proposed,
        "unused_links": sorted(unused),
        "errors": errors,
        "ok": not errors,
    }


def reach(store: dict[str, dict], root: Path = Path("."),
          universe: str = "mz/ocr") -> dict:
    """Per annotation, which leaves it actually reaches, and by what route.

    Three numbers, and the third is the one that has to be read carefully.

    `pages` are the leaves an annotation names directly. That route needs no
    folio and never refuses.

    `via_section` are the leaves a `toc:` attachment reaches, which takes
    `ref → folio → toc ids` and therefore only works where something witnesses
    the folio.

    `unwitnessed` is **a bound, not a miss.** Without a witnessed folio a leaf
    cannot be shown to fall inside the attached section *or* outside it, so the
    set a section attachment misses is not computable at all — only its size is.
    A column read as "pages this annotation misses" would be a confident guess
    wearing a count, which is the failure mode this repository is built against.
    It is `0` for an annotation carrying no `toc:` attachment, because the
    question does not arise there; the asymmetry is deliberate.

    `universe` names the denominator rather than leaving it implicit — every
    count here is against one store's refs, and a number whose denominator is
    unstated describes nothing. `mz/ocr` by default: what the recognizer has
    read is what the reading view can show at all.

    This is also where a `page:` attachment naming a leaf the store does not
    have is reported (`unknown`). `check` cannot ask: it holds no leaf universe,
    and encoding the per-part maxima a second time is what `seam.next_ref`
    refuses to do.
    """
    from . import paths
    from .apparatus import folio_index
    from .state import load_toc, toc_containing

    refs = paths.all_refs(root, universe)
    index = folio_index(root)
    folio_by_ref = {w["ref"]: folio for folio, ws in index.items() for w in ws}
    toc = load_toc(root)
    chains = {f: set(toc_containing(toc, f)) for f in index}

    known = set(refs)
    placed = {r: folio_by_ref[r] for r in refs if r in folio_by_ref}
    unwitnessed = sorted(known - set(placed))

    rows = []
    for ident, rec in sorted(store.items()):
        direct = sorted({t["value"] for t in rec["attaches"] if t["kind"] == "page"})
        sections = {t["value"] for t in rec["attaches"] if t["kind"] == "toc"}
        via = sorted({r for r, f in placed.items()
                      if chains.get(f, set()) & sections} - set(direct))
        rows.append({
            "id": ident,
            "class": rec["class"],
            "status": rec["status"],
            "pages": direct,
            "via_section": via,
            "sections": sorted(sections),
            "entities": sorted(t["value"] for t in rec["attaches"]
                               if t["kind"] == "entity"),
            "unwitnessed": len(unwitnessed) if sections else 0,
            "unknown": [r for r in direct if r not in known],
        })
    return {"universe": universe, "leaves": len(known),
            "witnessed": len(placed), "rows": rows}
