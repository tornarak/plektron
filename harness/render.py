"""The human view. `emit.py` stays the serializer and never learns about terminals.

Three output modes, and **the default is decided by `sys.stdout.isatty()`**:

    --json      indented JSON, the parse-this-as-a-contract escape
    --toon      TOON, whatever the stream is
    (neither)   TOON down a pipe, an aligned table at a terminal

That split is the whole design. TOON was chosen for a model reading a pipe and is
merely tolerable for a human reading a screen — unaligned commas, a header row of
bare field names, `tei ledger`'s 833 lines dumped whole. A model's invocation has no
TTY (verified: the agent harness pipes both streams), so it keeps getting TOON
byte-for-byte while a human gets columns, and neither has to ask.

`--toon` exists so a human can reproduce exactly what a skill's model saw. `| cat`
does the same thing by accident; a flag says it on purpose.

**Nothing here truncates, and that is not a style preference.** `rich.Table`'s
default is to ellipsize a cell that will not fit, and prototyped against `views
check --all` (169 columns natural) at an 80-column terminal it also wrapped one
field across five rows — strictly worse than the TOON it replaces. A `…` inside a
page ref or a Tier-1 form is a value that reads as a value and is not, which is this
project's governing failure mode arriving through the display layer. So the console
is built **at the table's own natural width**, measured by rich before rendering,
and never smaller. Output too wide for the terminal is the pager's problem.

**Four payload shapes, and only three are rendered.** A uniform list of records
becomes a table, a flat dict becomes aligned `key: value`, a list of scalars becomes
a wrapped comma list. **Anything ragged or nested falls back to TOON** rather than
inventing a layout — the same reflex as `views check`'s `verified` column, which
reports how deep it looked instead of implying more.

**Scalars are spelled the way TOON spells them** — `null`, `true`, `false`, never
Python's `None`/`True`. Two renderings of one payload disagreeing about the word for
a value would be two files holding one fact, and would put `None` in front of a
human and `null` in front of the model for the same ledger cell.

**rich is imported lazily and only in table mode.** Measured: `rich.table` +
`rich.console` + `rich.progress` costs 38 ms against `harness.cli`'s 55 ms, on a CLI
whose whole `--help` is 110 ms. Paying a 69% startup tax on every non-interactive
invocation — which is every invocation a model makes — to load a library that path
never touches is not a trade worth making, and `test_render.py` pins it.

It has to be rich rather than a hand-rolled aligner for one reason, and it is this
corpus's reason: `len("g̣")` is 2 where its display width is 1, because the dot is
combining (U+0323) and the store is NFD corpus-wide. `rich.cells.cell_len` returns 1.
An aligner counting characters would misalign every column of Tier-1 forms — which
is to say `lexicon marks`, `lexicon native` and `proposal codepoints`, the three
tables most worth reading.
"""
from __future__ import annotations

import os
import sys

from .emit import emit

MODES = ("json", "toon", "table")


def mode(a) -> str:
    """Which of the three, decided once per invocation.

    `--json` and `--toon` are mutually exclusive at the parser, so their order
    here is not a precedence rule — argparse has already refused both.
    """
    if getattr(a, "json", False):
        return "json"
    if getattr(a, "toon", False):
        return "toon"
    return "table" if sys.stdout.isatty() else "toon"


def colour() -> bool:
    """Whether to emit ANSI, by the conventions the environment already uses.

    `NO_COLOR` wins over `FORCE_COLOR` because it is the one that says *don't*, and
    a tool that can be made to shout over an explicit refusal is worse than one with
    no colour at all. Both beat the TTY test, which is how argparse 3.14 behaves in
    this same process — this repo's own environment sets `FORCE_COLOR=3`, and a
    usage error is already coloured down a pipe because of it.
    """
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return sys.stdout.isatty()


def render(obj, m: str = "toon") -> str:
    """Serialize a payload for one of the three modes. Never mutates `obj`."""
    if m == "json":
        return emit(obj, as_json=True)
    if m == "toon":
        return emit(obj)
    text = _table(obj)
    return emit(obj) if text is None else text


# --------------------------------------------------------------------- shapes


def _scalar(v) -> str:
    """One cell, spelled as TOON spells it.

    TOON additionally quotes any value containing its delimiter; a table does not
    need that, the column edge being the delimiter, and quotes on half the cells of
    `views check` are noise rather than information.
    """
    if v is None:
        return "null"
    if v is True:
        return "true"
    if v is False:
        return "false"
    return str(v)


def _is_scalar(v) -> bool:
    return v is None or isinstance(v, (str, int, float, bool))


def _numeric(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _records(obj) -> list[dict] | None:
    """`obj` as a uniform list of flat records, or None if it is not one.

    Uniform means **identical key sets and every value a scalar** — the same
    condition TOON's own tabular collapse requires, so a payload that would degrade
    to TOON's verbose form falls back here rather than being drawn as a table with
    a hole in it.
    """
    if not isinstance(obj, list) or not obj:
        return None
    if not all(isinstance(r, dict) and r for r in obj):
        return None
    keys = list(obj[0])
    if any(list(r) != keys for r in obj):
        return None
    if any(not _is_scalar(v) for r in obj for v in r.values()):
        return None
    return obj


# ---------------------------------------------------------------------- table


def _table(obj) -> str | None:
    """The rendered payload, or None to fall back to TOON."""
    if isinstance(obj, list) and not obj:
        # Blank is indistinguishable from clean — the rule `exempt` exists for in
        # `gt/zones/`, and the one the ink cache's `?` column keeps. A bare header
        # row over no rows reads as a table that happened to be empty; this says a
        # verb was asked and answered nothing.
        return "(none)"
    if rows := _records(obj):
        return _grid(list(rows[0]), rows)
    if isinstance(obj, dict) and obj and all(_is_scalar(v) for v in obj.values()):
        return _pairs(obj)
    if isinstance(obj, list) and all(_is_scalar(v) for v in obj):
        return _wrapped([_scalar(v) for v in obj])
    return None


def _console(width: int):
    """A string-capturing console at exactly `width`, never narrower."""
    import io

    from rich.console import Console

    return Console(file=io.StringIO(), width=width, force_terminal=colour(),
                   soft_wrap=False, highlight=False)


def _flush(console) -> str:
    # rich right-pads every line to the console width. At natural width that is
    # trailing space on every row, which shows up in a diff and in a paste.
    return "\n".join(ln.rstrip() for ln in console.file.getvalue().split("\n")).rstrip("\n")


def _grid(keys: list[str], rows: list[dict]) -> str:
    from rich.table import Table

    # A column is right-justified only when **every** value in it is a number.
    # Deciding per cell would stagger a column holding a count and a `null`.
    right = {k for k in keys if all(_numeric(r[k]) for r in rows)}

    def build():
        t = Table(box=None, pad_edge=False, header_style="bold" if colour() else "")
        for k in keys:
            t.add_column(k, justify="right" if k in right else "left",
                         no_wrap=True, overflow="ignore")
        for r in rows:
            t.add_row(*(_scalar(r[k]) for k in keys))
        return t

    # Measured before it is drawn: `maximum` is what the table wants if nothing is
    # taken away from it. The console is built at least that wide, so rich is never
    # in the position of having to shrink a column — which is the only way a `…`
    # can appear. `overflow="ignore"` above is the belt to this braces.
    probe = _console(10_000)
    natural = build().__rich_measure__(probe, probe.options).maximum

    console = _console(max(natural, _term_width()))
    console.print(build())
    return _flush(console)


def _pairs(record: dict) -> str:
    """A single flat record as aligned `key: value`."""
    from rich.cells import cell_len

    w = max(cell_len(k) for k in record)
    return "\n".join(f"{k}:{' ' * (w - cell_len(k) + 1)}{_scalar(v)}"
                     for k, v in record.items())


def _wrapped(items: list[str]) -> str:
    """A bare list of scalars — `ocr pages`' 34 refs — comma-joined and wrapped."""
    import textwrap

    return "\n".join(textwrap.wrap(", ".join(items), width=_term_width(),
                                   break_long_words=False,
                                   break_on_hyphens=False)) or "(none)"


def rule(name: str) -> str:
    """A section label for table mode — the `# name` line's terminal spelling."""
    from rich.cells import cell_len

    pad = max(0, _term_width() - cell_len(name) - 1)
    line = f"{name} {'─' * pad}"
    return f"\033[1m{line}\033[0m" if colour() else line


def _term_width() -> int:
    import shutil

    return shutil.get_terminal_size(fallback=(80, 24)).columns
