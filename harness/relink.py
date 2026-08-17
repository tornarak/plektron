"""Rule-applied entity links, applied to a page that was collated without them.

**The gap this closes.** `tei generate` links every auto form the store held
*at the moment it ran*, and collation follows generation. Ratify an entity
afterwards and every page already collated keeps plain text where a rule would
now put a link — silently, because `validate` re-derives the `#mz` links a page
*has* and has nothing to say about the ones it lacks. Forty-two entries were
scaffolded in one afternoon; ratifying them would otherwise have left the
corpus's only collated page behind.

**It rewrites the source text, not a parse tree.** A signed page must come back
byte-identical everywhere the rule did not act, so that its diff is exactly the
links and a reader can check them by eye. Round-tripping through a parser would
re-indent, re-quote and re-order attributes across the whole file, and the one
thing that must be reviewable would be the one thing buried.

**What it will not touch**, each reported rather than skipped in silence:

- text already inside an `<rs>` — it is linked, and `validate` re-derives it;
- text inside a `<name>`, `<foreign>` or `<term>` is never *pierced* — a Tier-1
  handle is enclosed by a reference, and enclosure edits the element's markup
  rather than its text. It is now offered, where the element's **whole content**
  is the form: `<rs><name>Kuluˊči</name></rs>`, which is what `tei generate`
  writes. A hit that is only part of the content is reported and refused,
  because picking where such a span ends is `_entity_spans`' judgement and not
  this module's;
- a segment carrying an XML entity, because matching would have to run on
  unescaped text and the offsets would no longer be the source's;
- a match that would cross an element boundary, which is the same refusal
  `_entity_spans` makes and for the same reason: nothing may pick the extent.
"""
from __future__ import annotations

import re

from .entities import alias_index, auto_forms, match

#: A tag, a comment, or a run of text. Comments first, because one may hold a
#: `>` — the generator writes prose in them — and a naive `<[^>]*>` would end the
#: comment at that character and read the rest of it as page text.
_SEG = re.compile(r"<!--.*?-->|<[^>]*>|[^<]+", re.S)

#: Inside any of these, a form is not linked here. `rs` is already a reference;
#: the other three hold glyphs a rule may not reach into.
_OPAQUE = ("rs", "name", "foreign", "term")

_TAG = re.compile(r"<\s*(/?)\s*([A-Za-z][\w:.-]*)([^>]*?)(/?)\s*>", re.S)

#: An existing reference and what it encloses, for the `once` count below.
_LINKED = re.compile(r"<rs\b[^>]*>(.*?)</rs>", re.S)
_INNER_TAGS = re.compile(r"<[^>]*>")


def relink(text: str, store: dict) -> tuple[str, list[dict], list[dict]]:
    """`(new_text, applied, skipped)` — the page with every missing rule link in it.

    `applied` and `skipped` are rows, not counts: a caller reporting "3 links"
    has told the reader nothing they can check, and the whole point of doing
    this to a collated page is that it stays checkable.
    """
    idx = alias_index(store)
    autos = auto_forms(idx)
    if not autos:
        return text, [], []

    # **`once` is counted over the links the page already has, not over the text
    # this pass can see.** Everything else here works on unlinked text, because
    # linked text is by definition done; counting a `once` form that way would
    # find the second occurrence with the first one hidden inside an `<rs>`,
    # read it as the first, and link it — turning "once per page" into twice on
    # exactly the pages this module exists to fix.
    once = {" ".join(_INNER_TAGS.sub("", m.group(1)).split())
            for m in _LINKED.finditer(text)}

    def spend(form: str) -> bool:
        """May a rule link this occurrence? Consumes a `once` form's one link."""
        if idx[form][0]["scope"] != "first":
            return True
        if form in once:
            return False
        once.add(form)
        return True

    out: list[str] = []
    applied: list[dict] = []
    skipped: list[dict] = []
    stack: list[dict] = []   # the open _OPAQUE elements, innermost last
    in_body = False

    def close(frame) -> None:
        """An opaque element has ended: enclose it, or say why not.

        **This is the half that was missing, and it was missing silently.**
        A Tier-1 handle is enclosed by a reference and never pierced by one —
        `<rs><name>Kuluˊči</name></rs>`, which is what `tei generate` writes —
        and the enclosure is an edit to the element's *markup*, not to its text.
        This function rewrites text, so it had nothing to say and said nothing:
        the segment was appended and skipped without a row, in a module whose
        docstring promises every refusal is reported. So a ratified entity whose
        only form on a page was Tier-1 linked on regeneration and never on a
        page a collator had already signed.

        Enclosure is offered only where the element's **whole content** is the
        form. That is narrower than `generate._entity_spans`, which can also take
        a hit spanning the handle and the words after it — "Kuluˊči Bay" — and
        the difference is deliberate: that hit crosses element boundaries, which
        is the one edit this module refuses on principle, since nothing here may
        pick where a span ends. A partial hit is reported instead.
        """
        inner = "".join(frame["text"])
        if frame["tag"] == "rs" or frame["child"] or not inner.strip():
            return
        if any(f["tag"] == "rs" for f in stack):
            return                                   # already inside a reference
        hits = [h for h in match(inner, idx)
                if not h["hyphenated"] and autos.get(h["form"])]
        if not hits:
            return
        if "&" in inner:
            skipped.extend(
                {"form": h["form"], "why": "segment carries an XML entity"}
                for h in hits)
            return
        whole = [h for h in hits
                 if not inner[:h["start"]].strip() and not inner[h["end"]:].strip()]
        if not whole:
            skipped.append({
                "form": hits[0]["form"],
                "why": f"a hit inside <{frame['tag']}> that is not its whole "
                       f"content — enclosing would have to pick where the span "
                       f"ends, which is `tei generate`'s to do and not this"})
            return
        if not spend(whole[0]["form"]):
            return
        owner = autos[whole[0]["form"]]
        out[frame["at"]] = f'<rs ref="{owner}" resp="#mz">' + out[frame["at"]]
        out.append("</rs>")
        applied.append({"form": whole[0]["form"], "id": owner})

    for m in _SEG.finditer(text):
        seg = m.group(0)
        if seg.startswith("<!--"):
            out.append(seg)
            continue
        if seg.startswith("<"):
            out.append(seg)
            t = _TAG.match(seg)
            if t:
                closing, name, _attrs, selfclose = t.groups()
                local = name.rpartition(":")[2]
                if local == "body":
                    in_body = not closing
                elif local in _OPAQUE and not selfclose:
                    if closing:
                        if stack:
                            frame = stack.pop()
                            close(frame)
                            if stack:
                                stack[-1]["text"] += frame["text"]
                    else:
                        if stack:
                            stack[-1]["child"] = True
                        stack.append({"tag": local, "at": len(out) - 1,
                                      "text": [], "child": False})
            continue
        if not in_body:
            out.append(seg)
            continue
        if stack:
            # Inside an opaque element: the text is kept for `close` to judge as
            # a whole, and never rewritten in place.
            stack[-1]["text"].append(seg)
            out.append(seg)
            continue
        if "&" in seg:
            hits = [h for h in match(seg, idx) if autos.get(h["form"])]
            skipped += [{"form": h["form"], "why": "segment carries an XML entity"}
                        for h in hits]
            out.append(seg)
            continue

        pos = 0
        pieces = []
        for h in match(seg, idx):
            owner = None if h["hyphenated"] else autos.get(h["form"])
            if not owner or not spend(h["form"]):
                continue
            pieces.append(seg[pos:h["start"]])
            pieces.append(f'<rs ref="{owner}" resp="#mz">'
                          f'{seg[h["start"]:h["end"]]}</rs>')
            pos = h["end"]
            applied.append({"form": h["form"], "id": owner})
        pieces.append(seg[pos:])
        out.append("".join(pieces))
    return "".join(out), applied, skipped


def missing(text: str, store: dict) -> list[dict]:
    """Every auto form sitting unlinked in this page — the worklist, no rewriting.

    `validate` re-derives the links a page *has*; without this, the ones it
    lacks are invisible, and an entry ratified after the page was collated looks
    from the outside exactly like one whose form the page never printed.
    """
    _new, applied, skipped = relink(text, store)
    return applied + skipped


def apply_to_corpus(root, store: dict,
                    write: bool = True) -> tuple[list[dict], list[dict], list]:
    """Every collated page brought up to date with `store`.

    `(applied, skipped, undo)` — `undo` is a list of thunks restoring each page
    it wrote, so a caller that gates *after* writing can put the corpus back.

    **`write=False` computes and touches nothing**, rather than writing and
    undoing. A report-only run that wrote first would leave the corpus edited if
    anything between the two raised, in the store this project has already lost
    work in once — and "report by default, `--commit` writes" is meant to hold
    on the disk and not only in the output.

    **One implementation, two callers**, and the reason is that there are two
    ways to ratify: `harness entity ratify` and the click in the reading view.
    They were already two code paths for the status flip alone; adding the page
    pass to one of them would have made ratifying in the browser and ratifying
    at the terminal leave the corpus in different states, which is the shape of
    defect this project is organised against.
    """
    from .tei_html import collated

    applied: list[dict] = []
    skipped: list[dict] = []
    undo: list = []
    for ref in collated(root):
        p = root / "tei" / f"chukchi-{ref}.xml"
        text = p.read_text(encoding="utf-8")
        new, got, left = relink(text, store)
        applied += [{"ref": ref, **r} for r in got]
        skipped += [{"ref": ref, **r} for r in left]
        if write and new != text:
            p.write_text(new, encoding="utf-8")
            undo.append(lambda p=p, t=text: p.write_text(t, encoding="utf-8"))
    return applied, skipped, undo


def refresh_drafts(root, store: dict, ids, write: bool = True) -> list[str]:
    """Regenerate the draft pages holding an unlinked mention of `ids`.

    **Regenerated, not relinked, and the difference is the whole reason this is
    a separate function.** A draft carries the generator's own questions beside
    its text — `<!-- entity candidate: 'Wrangell’s Land' — …, whose entry is
    still `proposed` -->` — and applying the link without answering the comment
    would leave a fresh `<rs>` standing next to a note saying no rule may write
    one. Half-updating a derived file is worse than leaving it: the two halves
    contradict each other and neither is marked as the stale one. `tei generate`
    rebuilds both from the same store in one pass, so it is what runs here.

    Scoped to the pages that actually mention the entity, because the
    alternative is a corpus sweep on every click. A page a collator has claimed
    is in `tei/` and so is not a draft, which is what keeps `--force` from
    moving a baseline under a review in progress.
    """
    from .entities import occurrences
    from .generate import Unready, generate
    from .tei_html import collated, readable

    drafts = [r for r in readable(root) if r not in set(collated(root))]
    got = occurrences(ids, drafts, store, root)
    stale = sorted({r["ref"] for i in ids for r in got[i]["unlinked"]})
    if write:
        for ref in stale:
            try:
                generate(ref, root, force=True)
            except Unready:
                # **Ratifying does not fail because a derived file cannot be
                # rebuilt.** The act is a human's judgement about an entry; a
                # draft whose ground truth was withdrawn is a fact about another
                # store entirely, and letting it raise would turn a click on an
                # entity card into a 500 naming a page the reader never touched.
                # The ref stays in the returned list, which is what says the
                # page is still out of date.
                pass
    return stale
