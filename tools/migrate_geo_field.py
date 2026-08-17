#!/usr/bin/env python3
"""Fold `area:` into `geo:`, and take `within:` off everything but geography.

One design change, so one pass. `geo:` is now repeatable and its members are a
point, a shape in `data/geo/`, or another entity whose extent this one takes —
which makes `area:` a second spelling of the same field, and makes `within:` on
a people the encyclopedia's hierarchy wearing the atlas's field. Both go.

**The transform is a pure `rewrite(text) -> str`** so a test can drive it on a
string, which is `migrate_fig_bboxes.py`'s rule and the reason its own
conservation argument was checkable. Everything else here is reading files,
counting, and refusing.

WHAT IT REFUSES TO DO QUIETLY. It computes every entity's extent from the store
as it stands, computes it again from the rewritten text **without writing
anything**, and writes only if the two agree for all 315 records. That is
possible because `entities.parse` currently folds `area:` into `geo:` while the
field is being retired, so both sides of the comparison come from one
implementation reading two spellings — not from two versions of the program,
which would have compared a migration against itself.

Idempotent: a file with no `area:` and no non-geographical `within:` comes back
byte-identical, and a second run reports nothing to do.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from harness import geo  # noqa: E402
from harness.cli._entity import FIELD_ORDER  # noqa: E402
from harness.entities import GEO_CLASSES, ent_dir, load, parse, split_id  # noqa: E402

_HEAD = re.compile(r"^##\s", re.M)
_FIELD = re.compile(r"^-\s+([a-z][a-z-]*):\s*(.*?)\s*$")
_TITLE = re.compile(r"^#\s+([a-z]+):([a-z0-9][a-z0-9-]*)\s+—", re.M)

#: What the store is expected to hold going in. Named so a surprise stops the
#: run rather than being migrated: a fourth non-geographical `within:` is a
#: record somebody added while this was being written, and it wants a human
#: reading it, not a rule guessing which of two rewrites it meant.
EXPECT_AREA = 66
EXPECT_WITHIN = 3


def _rank(key: str) -> int:
    return FIELD_ORDER.index(key) if key in FIELD_ORDER else len(FIELD_ORDER)


def _insert(lines: list[str], key: str, value: str) -> list[str]:
    """`- key: value` into its `FIELD_ORDER` slot among the field lines."""
    out = list(lines)
    for i, line in enumerate(out):
        m = _FIELD.match(line)
        if m and _rank(m.group(1)) > _rank(key):
            out.insert(i, f"- {key}: {value}")
            return out
    last = max(i for i, line in enumerate(out) if _FIELD.match(line))
    out.insert(last + 1, f"- {key}: {value}")
    return out


def rewrite(text: str, *, areas: bool = True, withins: bool = True) -> str:
    """One entity file's text, migrated. Unchanged text is returned unchanged.

    **The two halves are separable, and they are separable because only one of
    them is inert.** Folding `area:` into `geo:` may not move a single extent —
    it is one spelling replacing another, and `main` proves it. Taking `within:`
    off a people *does* move two, on purpose: a people filed inside a village
    hung from that village in the atlas tree, so its extent never rolled up to
    its ethnicity, and the Yupik map excluded two Yupik peoples. That is the
    defect this change was started for. Running the halves separately is what
    lets the first be asserted and the second be read.

    **Scoped to the field block**, the text above the first `##`, for
    `_set_field`'s reason: a `- area: …` inside a gloss is prose, and an
    unscoped substitution rewrites a sentence.

    An `area:` line becomes one `- geo:` line per member, **in place and in the
    order the file wrote them**. In place is already the right place —
    `FIELD_ORDER` puts `area` immediately after `geo`, so the slot vacated is
    the slot wanted — and authored order replaces the sorted canonical spelling
    a composite used to be stored in. That sorting existed only to give a union
    one identity so it could not read as two shapes; a repeatable field has no
    union to name.

    A `within:` is rewritten only where one of its two ends is not one of the
    four geographical classes, and which rewrite depends on the *other* end: a
    people inside a village was borrowing an extent, so it becomes a `geo:`
    member; a tale inside the collection that prints it was never anywhere at
    all, so it becomes `part-of:`.
    """
    m = _HEAD.search(text)
    at = m.start() if m else len(text)
    head, rest = text[:at], text[at:]

    title = _TITLE.search(head)
    if not title:
        raise ValueError("no `# class:slug — Name` heading")
    cls = title.group(1)

    out: list[str] = []
    deferred: list[tuple[str, str]] = []
    for line in head.split("\n"):
        f = _FIELD.match(line)
        if not f:
            out.append(line)
            continue
        key, value = f.group(1), f.group(2)
        if key == "area" and areas:
            out += [f"- geo: {v.strip()}" for v in value.split(",") if v.strip()]
        elif key == "within" and value and withins:
            target, _ = split_id(value)
            if cls in GEO_CLASSES and target in GEO_CLASSES:
                out.append(line)
            elif target in GEO_CLASSES:
                deferred.append(("geo", value))
            else:
                deferred.append(("part-of", value))
        else:
            out.append(line)

    for key, value in deferred:
        out = _insert(out, key, value)
    return "\n".join(out) + rest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=".", help="repo root (default .)")
    ap.add_argument("--commit", action="store_true",
                    help="write the files; without it, report and write nothing")
    a = ap.parse_args(argv)
    root = Path(a.root)

    paths = sorted(ent_dir(root).glob("*/*.md"))
    before = load(root)

    areas = sum(1 for p in paths
                if re.search(r"^-\s+area:", p.read_text(encoding="utf-8"), re.M))
    withins = sum(1 for r in before.values()
                  if r["within"]
                  and (r["class"] not in GEO_CLASSES
                       or before[r["within"]]["class"] not in GEO_CLASSES))
    print(f"{areas} record(s) with `area:`, {withins} with a "
          f"non-geographical `within:`")
    if areas > EXPECT_AREA or withins > EXPECT_WITHIN:
        print(f"! more than the {EXPECT_AREA}/{EXPECT_WITHIN} this was written "
              f"against — read the new ones before migrating them",
              file=sys.stderr)
        return 1

    def restore(**how) -> tuple[dict, dict, list]:
        """The store as it would be, built in memory. Nothing reaches disk, so a
        conservation failure costs a message rather than a `git checkout`."""
        texts, store, changed = {}, {}, []
        for p in paths:
            text = p.read_text(encoding="utf-8")
            new = rewrite(text, **how)
            texts[p] = new
            rec = parse(new, where=str(p))
            rec["path"] = str(p)
            store[rec["id"]] = rec
            if new != text:
                changed.append(p)
        return texts, store, changed

    def moves(store: dict) -> list[str]:
        rows = []
        for ident in sorted(before):
            was, now = (geo.extent_of(ident, s, root) for s in (before, store))
            if was != now:
                rows.append(f"{ident}: {was} → {now}")
            shapes = [sorted(geo.geo_shapes(s[ident])) for s in (before, store)]
            if shapes[0] != shapes[1]:
                rows.append(f"{ident}: shapes {shapes[0]} → {shapes[1]}")
        return rows

    # **The `area:` half must be inert, and this is the assertion.** One
    # spelling replacing another may not move an extent or change which shapes
    # an entity claims; if it does, the fold is wrong and nothing should be
    # written on the strength of it.
    stray = moves(restore(areas=True, withins=False)[1])
    if stray:
        print(f"! folding `area:` into `geo:` would move {len(stray)} record(s), "
              f"and it is a change of spelling — nothing written", file=sys.stderr)
        for row in stray[:20]:
            print(f"  {row}", file=sys.stderr)
        return 1
    print("`area:` → `geo:` moves nothing: every extent and every shape claim "
          f"identical across all {len(before)} records")

    # **The `within:` half moves two extents and is supposed to.** Shown rather
    # than asserted, because the assertion would be a restatement of the change.
    texts, after, changed = restore()
    print("\ntaking `within:` off the three non-geographical records:")
    for row in moves(after):
        print(f"  {row}")

    print(f"\n{len(changed)} file(s) to rewrite")
    for p in changed:
        print(f"  {p.relative_to(root)}")
    if not a.commit:
        print("\nreport only — pass --commit to write")
        return 0
    for p in changed:
        p.write_text(texts[p], encoding="utf-8")
    print(f"\nwrote {len(changed)} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
