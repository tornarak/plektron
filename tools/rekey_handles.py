"""One-time: re-spell the `{key}` handles in a text's review records under its new
key table.

`as_typed` keeps a line as the reader typed it, handles included, and `proposal
check` re-expands it against `text` (`proposal_check._handle_issues`), so a handle
spelled in a retired key alphabet reads as a reading that disagrees with its own
record. The reader's act was the same; only its spelling has changed, and this
re-spells it. A note's handles are re-spelled too, since `_named_key_issues` reads
those as keys.

**Where the old spelling comes from.** The old table is read out of git at
`--rev` (`git show REV:<the table's path>`), never retyped here. Each handle is
matched against every attested form's *old* key, case-insensitively, because a
reader's handle may raise a case the corpus attests lower (`lookup`'s case
ladder); the new key is that form's new key with the handle's case laid over it
letter by letter, which is sound because the two tables spell the same letters
and differ only in their markers.

**Refuses rather than guesses.** An old key the old table gave to more than one
form is settled by which of them the line's `text` holds; a handle that matches
none, or still more than one, is reported and left as it was. `text` is never
touched.

Also reports the forms the old table could key and the new one cannot, which is
what narrowing the passthrough costs.

    uv run python tools/rekey_handles.py --rev HEAD            # report
    uv run python tools/rekey_handles.py --rev HEAD --commit   # write
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness import marks  # noqa: E402
from harness.detectors import native_corpus_context  # noqa: E402
from harness.layout import shared  # noqa: E402
from harness.lookup import HANDLE  # noqa: E402
from harness.proposal_check import _write_json  # noqa: E402


def _old_table(table_path: Path, rev: str) -> marks.HandleTable:
    rel = table_path.resolve().relative_to(Path.cwd().resolve())
    doc = json.loads(subprocess.run(["git", "show", f"{rev}:{rel}"], check=True,
                                    capture_output=True, text=True).stdout)
    return marks.HandleTable(tokens=doc["tokens"], passthrough=doc["passthrough"],
                             injective=False, path=f"{rev}:{rel}")


def _key(form: str, table: marks.HandleTable) -> str | None:
    try:
        return marks.handle_key(form, table)
    except ValueError:
        return None


def _with_case(handle: str, key: str) -> str:
    """`key` with each ASCII letter given the case of the handle's letter in the
    same position among letters. Both spell one letter sequence."""
    cases = [c.isupper() for c in handle if c.isascii() and c.isalpha()]
    out, n = [], 0
    for c in key:
        if c.isascii() and c.isalpha():
            out.append(c.upper() if cases[n] else c.lower())
            n += 1
        else:
            out.append(c)
    return "".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", type=Path, default=Path("jesup/bogoras-chukchi"))
    ap.add_argument("--rev", required=True,
                    help="the commit whose key table the handles were typed in")
    ap.add_argument("--commit", action="store_true")
    a = ap.parse_args()

    new = marks.handle_table(a.root)
    old = _old_table(shared(a.root, marks.HANDLE), a.rev)
    forms = {unicodedata.normalize("NFD", r["token"])
             for r in native_corpus_context(a.root)}
    by_old: dict[str, set[str]] = {}
    lost = []
    for f in sorted(forms):
        ok, nk = _key(f, old), _key(f, new)
        if ok is not None:
            by_old.setdefault(ok.casefold(), set()).add(f)
            if nk is None:
                lost.append(f)

    rewrites, refused, files = 0, [], {}
    for path in sorted(a.root.glob("review/*/*.json")):
        if path.name not in ("proposal.json", "decision.json"):
            continue
        src = path.read_text(encoding="utf-8")
        doc = json.loads(src)
        edits = []
        for idx, rec in doc.get("lines", {}).items():
            text = rec.get("text", "").casefold()

            def sub(m, idx=idx, text=text, path=path):
                nonlocal rewrites
                h = m.group(1)
                cands = by_old.get(h.casefold(), set())

                def keys_of(fs):
                    return {_with_case(h, _key(f, new)) for f in fs
                            if _key(f, new) is not None}
                keys = keys_of(cands)
                if len(keys) > 1:
                    cands = {f for f in cands if f.casefold() in text}
                    keys = keys_of(cands)
                if len(keys) != 1:
                    refused.append((path.parent.name, idx, h, sorted(cands)))
                    return m.group(0)
                (k,) = keys
                if k != h:
                    rewrites += 1
                return "{" + k + "}"

            for field in ("as_typed", "note"):
                if isinstance(rec.get(field), str):
                    v = HANDLE.sub(sub, rec[field])
                    if v != rec[field]:
                        edits.append({"line": idx, "field": field,
                                      "from": rec[field], "to": v})
                        rec[field] = v
        if edits:
            files[path] = (src, doc, edits)

    print(f"old table {old.path}; {len(forms)} forms, {len(lost)} no longer keyable")
    for f in lost:
        print(f"  unkeyable now: {f!r}")
    print(f"{rewrites} handles re-spelled in {len(files)} files; "
          f"{len(refused)} left as they were")
    for ref, idx, h, c in refused:
        print(f"  {ref} l{idx} {{{h}}}: candidates {c}")
    if a.commit:
        for path, (src, doc, edits) in files.items():
            _write_json(path, doc, src, {"by": "tools/rekey_handles.py",
                                         "rev": a.rev, "edits": edits})
    return 0


if __name__ == "__main__":
    sys.exit(main())
