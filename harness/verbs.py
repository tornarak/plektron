"""`VERBS.md`, addressable by verb, so nobody has to read all of it to use one of it.

**Someone wanting the full surface of their own commands is asking a reasonable
question, and the only answer on offer was a 100 KB file.** A `groundtruth-reader`
did exactly that mid-page: two `Read`s of `VERBS.md`, 22,517 tokens and then 10,734
more, a fifth of that reader's entire context and more than every folio hunt on the
page put together. It was not misbehaving — its contract tells it the CLI is
documented there, `--help` is thin in places, and nothing offered a way to consult
one entry.

So the file gets an index. `VERBS.md` stays the single source and stays gated by
`test_cli_surface.py`; this only slices it, on the `### group action` headings it
already carries, so there is no second copy to drift.

The Conventions block is returned with any lookup that asks for a whole group,
because the rules that hold across every action — report by default, `--commit`
writes, exit 0/1/2, refs are `PP-NNN` — are what a caller reading one entry is
most likely to be missing.
"""
from __future__ import annotations

import re
from pathlib import Path

DOC = Path("harness/VERBS.md")

#: `### group action`, and **both words are required**.
#:
#: The second was optional, which made a bare `### ocr` heading parse as an
#: *action* named `ocr` — and `lookup` tests `q in all_` before it tries the
#: group prefix, so that stub would answer every `lookup("ocr")` with one blurb
#: instead of the group's twelve entries, and without the Conventions block,
#: which is the one thing a group lookup exists to attach. `test_cli_surface`'s
#: own `_HEADING` requires both words, so it could never have reported such a
#: heading: the two parsers of this file would simply have disagreed in silence.
#:
#: The character class matches `_HEADING`'s `[\w-]` for the same reason. It was
#: `[a-z-]`, under which `### tei validate2` truncated to `tei validate` and
#: **silently overwrote** the real entry in `entries()`, dropping an action from
#: the index with no error, while the surface gate read `validate2` and saw
#: nothing wrong. No heading triggers either case today; the set-equality test
#: in `test_verbs_and_codepoints.py` is what keeps it that way.
HEAD = re.compile(r"^### (?P<name>[\w-]+ [\w-]+)", re.MULTILINE)


def _text(root: Path = Path(".")) -> str:
    p = root / DOC
    if not p.exists():
        raise FileNotFoundError(f"{DOC} is missing; it is the CLI's reference")
    return p.read_text(encoding="utf-8")


def entries(root: Path = Path(".")) -> dict[str, str]:
    """Every `### group action` heading mapped to its body, heading included."""
    text = _text(root)
    hits = list(HEAD.finditer(text))
    out: dict[str, str] = {}
    for i, m in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(text)
        out[m.group("name")] = text[m.start():end].rstrip()
    return out


def conventions(root: Path = Path(".")) -> str:
    """The `## Conventions` block — what holds across every action."""
    text = _text(root)
    i = text.find("## Conventions")
    if i < 0:
        return ""
    j = text.find("\n## ", i + 1)
    return text[i:j if j > 0 else len(text)].rstrip()


def lookup(query: str, root: Path = Path(".")) -> dict:
    """One action, or a whole group, or the list of what there is.

    `""` lists every action name and nothing else — the cheapest possible answer
    to "what can I run", and the one a caller should reach for first. `"ocr"`
    returns that group's entries plus Conventions. `"ocr zoom"` returns one entry.
    An unknown name is an error naming the near misses rather than an empty
    result, since a silent nothing reads as "no such command" when the real
    answer is usually a typo.
    """
    all_ = entries(root)
    q = " ".join(str(query or "").split())
    if not q:
        return {"query": "", "actions": sorted(all_), "text": ""}
    if q in all_:
        return {"query": q, "actions": [q], "text": all_[q]}
    group = {k: v for k, v in all_.items() if k.split()[0] == q}
    if group:
        return {"query": q, "actions": sorted(group),
                "text": conventions(root) + "\n\n"
                        + "\n\n".join(group[k] for k in sorted(group))}
    near = sorted(k for k in all_ if q in k)
    raise ValueError(
        f"{q!r} names no action in {DOC}. "
        + (f"Did you mean: {', '.join(near)}?" if near else
           f"Run it with no argument for the list of {len(all_)} actions."))
