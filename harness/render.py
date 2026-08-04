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

import contextlib
import os
import shlex
import shutil
import subprocess
import sys
import time

from .emit import emit

MODES = ("json", "toon", "table")


def mode(a) -> str:
    """Which of the three, decided once per invocation.

    `--json` and `--toon` are mutually exclusive at the parser, so their order
    here is not a precedence rule — argparse has already refused both.

    **Resolved once and cached on the namespace**, because `main` replaces
    `sys.stdout` with the pager's pipe before the action runs. Asked again after
    that, `isatty()` is False and every table would silently come back as TOON —
    the terminal's own output format decided by the fact that we are showing it
    to the terminal.
    """
    if (cached := getattr(a, "_mode", None)) is not None:
        return cached
    if getattr(a, "json", False):
        m = "json"
    elif getattr(a, "toon", False):
        m = "toon"
    else:
        m = "table" if sys.stdout.isatty() else "toon"
    try:
        a._mode = m
    except AttributeError:                      # a mapping-ish fake in a test
        pass
    return m


# ------------------------------------------------------------------- palette
#
# **The palette is rich's own `repr.*` theme, not one invented here**, and that is
# the whole justification for it. A renderer knows the *type* of a cell and nothing
# about its meaning: it cannot tell `keyed: false` (unread page, ordinary) from
# `ok: false` (a gate failed), so any scheme claiming to say which is a verdict the
# display layer is not entitled to. Colouring by type says only what is true —
# this cell is a boolean, that one is absent — and borrowing rich's defaults means
# the association is one a reader has already met rather than a local convention.
#
# The one place a verdict *is* known is `report` below, which paints a fixed
# vocabulary the gate itself prints.
# **Numbers are deliberately not painted**, though rich's theme has a colour for
# them and the first cut used it. Two reasons, and the second is the general one:
# the grid already right-justifies a column whose every value is a number, so
# painting it encodes one fact twice — and numbers are most of the cells in most of
# these tables, so `views check --all` came back as a wall of cyan zeros with the
# two marks that carry information lost inside it. Colour is worth having only
# where it is rare.
NULL = "repr.none"
BOOL = {True: "repr.bool_true", False: "repr.bool_false"}
HEADER = "bold"


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


# ------------------------------------------------------------------ sections
#
# A verb may print several tables, because TOON collapses a uniform record list and
# degrades on a ragged key set, so two key sets have to be two tables. Under
# `--json` that meant several *documents* on one stream — 15 of 58 captured
# invocations were not `json.load`-able, including `tei validate` with two refs,
# which interleaves `# 1-100` comment lines between objects. `--json` is the flag
# whose entire purpose is being parseable.
#
# So JSON mode buffers instead of printing, and `flush` emits **one document**:
# the payload bare when a verb printed one section, an object keyed by section name
# when it printed several. Nothing changes for TOON or table mode, and 43 of the 58
# stay byte-identical.
#
# **Known limit, stated rather than half-fixed.** The key set reflects which
# sections had content, so a verb whose second table is empty this run omits its
# key. Making the shape a pure function of the verb would mean each one declaring a
# schema, which does not exist here and is a much larger job than making the output
# parseable. Consumers should use `.get()`. What *is* guaranteed is that the stream
# is always one document, and `_MULTI` below refuses rather than silently emitting
# two — a verb that grows a second section without naming it fails loudly at the
# call site instead of quietly at the consumer's.
_SECTIONS: list[tuple[str | None, object, str | None]] = []


def collect(name: str | None, obj, default: str | None = None) -> None:
    _SECTIONS.append((name, obj, default))


def flush() -> str | None:
    """The buffered sections as one JSON document, or None if nothing buffered.

    **A verb names only its extra sections.** The primary table is whatever the
    action is called, filled in here, so `zones check --json` reads
    `{"check": {...}, "pages": [...]}` and a verb does not have to name its main
    output merely because a second one exists further down — which would couple
    two call sites that know nothing about each other, and would break the moment
    a conditional second table appeared.

    What refuses is a **collision**: two sections resolving to one key would drop
    a whole table into the other's slot, silently, and a consumer would see a
    plausible document missing half its content.
    """
    sections, _SECTIONS[:] = list(_SECTIONS), []
    if not sections:
        return None
    if len(sections) == 1:
        return emit(sections[0][1], as_json=True)
    names = [n or d or "" for n, _, d in sections]
    if len(set(names)) != len(names) or not all(names):
        raise ValueError(
            f"--json: {len(sections)} sections resolve to {sorted(set(names))} — a "
            "verb printing more than one table must give each a distinct name, or "
            "they cannot be one document (see harness/render.py)")
    return emit(dict(zip(names, (o for _, o, _ in sections), strict=True)),
                as_json=True)


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
    if (sections := _sections(obj)) is not None:
        return sections
    return None


def _sections(obj) -> str | None:
    """A payload built of named sections, drawn as a head block then one table each.

    The fifth shape, and it is not the "invent a layout" the module docstring
    refuses. A verb that calls `out()` once per section already renders exactly
    this — a `rule(name)` line above each grid — so a verb that hands its sections
    over in one dict was getting TOON purely because `_table` had no composite
    case, not because the payload was ambiguous. `proposal marks` is the one that
    made it visible: four record lists and four scalars, every one of them
    perfectly tabular on its own, and none of them drawn.

    The bar stays where the rest of the module puts it: **every** value must be a
    scalar or a renderable record list, and at least one must be a list. Anything
    else is genuinely ragged and still falls back, so nothing is drawn with a hole
    in it. An empty list keeps `_table`'s `(none)`, since blank is
    indistinguishable from clean.
    """
    if not isinstance(obj, dict) or not obj:
        return None
    head, blocks = {}, []
    for k, v in obj.items():
        if _is_scalar(v):
            head[k] = v
        elif isinstance(v, list) and (not v or _records(v) is not None):
            blocks.append((k, _grid(list(v[0]), v) if v else "(none)"))
        else:
            return None
    if not blocks:
        return None
    parts = [_pairs(head)] if head else []
    parts += [f"{rule(k)}\n{body}" for k, body in blocks]
    return "\n".join(parts)


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


def _cell(v):
    """One value as a styled `Text` — the colour is the value's *type*, see above."""
    from rich.text import Text

    if v is None:
        return Text("null", style=NULL)
    if isinstance(v, bool):
        return Text(_scalar(v), style=BOOL[v])
    return Text(_scalar(v))


def _grid(keys: list[str], rows: list[dict]) -> str:
    from rich.table import Table

    # A column is right-justified only when **every** value in it is a number.
    # Deciding per cell would stagger a column holding a count and a `null`.
    right = {k for k in keys if all(_numeric(r[k]) for r in rows)}

    def build():
        t = Table(box=None, pad_edge=False, header_style=HEADER)
        for k in keys:
            t.add_column(k, justify="right" if k in right else "left",
                         no_wrap=True, overflow="ignore")
        for r in rows:
            t.add_row(*(_cell(r[k]) for k in keys))
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
    """A single flat record as aligned `key: value`.

    Through the same `Table` the grid uses rather than a hand-rolled `ljust`: the
    keys carry the header's style, the values carry their type's, and the column is
    measured with `cell_len` for free — which is the whole reason rich is here, a
    Tier-1 form's combining mark making `len` and display width disagree.
    """
    from rich.table import Table

    def build():
        # `collapse_padding` so the gap between the two columns is one space and
        # not two — a key/value list is read as `key: value`, and rich's default
        # padding on both sides of a cell would put a hole in the middle of it.
        t = Table(box=None, pad_edge=False, show_header=False,
                  collapse_padding=True)
        t.add_column(style=HEADER, no_wrap=True, overflow="ignore")
        t.add_column(no_wrap=True, overflow="ignore")
        for k, v in record.items():
            t.add_row(f"{k}:", _cell(v))
        return t

    probe = _console(10_000)
    console = _console(max(build().__rich_measure__(probe, probe.options).maximum,
                           _term_width()))
    console.print(build())
    return _flush(console)


def _wrapped(items: list[str]) -> str:
    """A bare list of scalars — `ocr pages`' 34 refs — comma-joined and wrapped."""
    import textwrap

    return "\n".join(textwrap.wrap(", ".join(items), width=_term_width(),
                                   break_long_words=False,
                                   break_on_hyphens=False)) or "(none)"


# ----------------------------------------------------------------- progress
#
# **On stderr**, so stdout stays a clean pipe and `harness … > file` still holds
# exactly the payload.
#
# **Started on elapsed time, never on item count.** A bar that flashes for 200 ms
# is noise, and a count threshold cannot tell a 4-page raster sweep (~1 s) from a
# 40-page `ocr lines` (~5 ms). Nothing is drawn until the work has been going for
# `PROGRESS_AFTER`, at which point the bar appears with its count already correct.
PROGRESS_AFTER = 0.5


@contextlib.contextmanager
def progress(label: str):
    """Yield a `tick(item, done, total)` for `parallel.pmap`, if anyone is watching.

    Yields **None** whenever stderr is not a terminal, and `pmap` skips the call
    entirely — so a redirected or piped run does exactly what it did before the
    bar existed. That is what keeps the benched sweeps diffable against
    `--jobs 1`, and it is why the guard is here rather than inside the callback.

    The bar is `transient`, so it leaves nothing behind: what stays on the screen
    is the payload, which is what the command was for.
    """
    if not sys.stderr.isatty():
        yield None
        return

    from rich.console import Console
    from rich.progress import (
        BarColumn,
        MofNCompleteColumn,
        Progress,
        TextColumn,
        TimeElapsedColumn,
    )

    bar = Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(), MofNCompleteColumn(), TimeElapsedColumn(),
        TextColumn("{task.fields[item]}"),
        console=Console(stderr=True), transient=True)
    task, started = bar.add_task(label, total=None, item=""), time.monotonic()

    def tick(item, done: int, total: int) -> None:
        if not bar.live.is_started:
            if time.monotonic() - started < PROGRESS_AFTER:
                return
            bar.start()
        bar.update(task, completed=done, total=total, item=str(item))

    try:
        yield tick
    finally:
        if bar.live.is_started:
            bar.stop()


DEFAULT_PAGER = "less -SRFX"


@contextlib.contextmanager
def pager(a):
    """Send this invocation's stdout to `$PAGER`, on `--pager` only.

    **Opt-in, and that is a reversal.** It was on by default for table mode, on
    git's reasoning: `less -F` prints and exits when the content already fits, so
    short output was supposed to pass straight through. What it actually costs is
    that the *usual* case — a table that fits — now goes through a subprocess and
    a pipe to arrive looking the same, and the unusual one takes the terminal away
    from a person who did not ask for it. A flag is the honest shape for something
    wanted occasionally, and `harness zones check --all --pager` is no harder to
    type than the `q` that dismissing it costs.

    With it, `-S` chops long lines rather than wrapping them, which is what makes a
    table wider than the screen readable at all: columns stay aligned and you
    scroll sideways. `-R` passes the colour through; `-X` leaves the output in the
    scrollback on exit; `-F` still means a short payload prints inline.

    Redirecting `sys.stdout` rather than pushing each section through means every
    print reaches it, including `tei validate`'s rendered prose, which never went
    through `out()`. It also streams: `less` renders progressively, so a long
    multi-ref run shows its first report immediately rather than after the last.

    **Two actions refuse it, and declare that rather than being special-cased
    here.** `zones edit` and `ocr review --serve` block on `serve_forever` after
    printing a URL the human is meant to open; paged, that URL would sit unread
    inside a pager the human is not looking at, on a command that never returns to
    release it. They refuse `--pager` outright rather than honouring it, since the
    request is one nobody can mean.
    """
    cmd = os.environ.get("PAGER", DEFAULT_PAGER)
    if (mode(a) != "table" or not getattr(a, "pager", False)
            or not getattr(a, "_pageable", True) or not cmd.strip()):
        yield
        return
    argv = shlex.split(cmd)
    if not shutil.which(argv[0]):
        yield
        return
    proxy = _LazyPager(argv)
    saved, sys.stdout = sys.stdout, proxy
    try:
        yield
    finally:
        sys.stdout = saved
        proxy.close()


class _LazyPager:
    """A stdout stand-in that starts the pager on the first byte written.

    **Lazy because of the progress bar.** The bar draws on stderr, i.e. straight
    at the terminal, while a pager started up front is already holding it — two
    writers on one screen. Every pooled sweep accumulates and prints at the end,
    so deferring the spawn until the first write puts the bar strictly before the
    pager rather than across it.

    It also means a command that prints nothing never spawns one, which is the
    right behaviour for its own sake.
    """

    def __init__(self, argv: list[str]):
        self._argv, self._proc = argv, None

    def _stdin(self):
        if self._proc is None:
            self._proc = subprocess.Popen(
                self._argv, stdin=subprocess.PIPE, text=True,
                env={**os.environ, "LESSCHARSET": "utf-8"})
        return self._proc.stdin

    def write(self, s: str) -> int:
        try:
            return self._stdin().write(s)
        except BrokenPipeError:
            # The reader quit first — `q` in less before the writer was done.
            # Ordinary, and not an error about the payload.
            return len(s)

    def flush(self) -> None:
        with contextlib.suppress(BrokenPipeError, ValueError):
            if self._proc is not None:
                self._proc.stdin.flush()

    def isatty(self) -> bool:
        # The pager is one, and something downstream may ask. `mode` does not —
        # it is resolved and cached before this object exists, deliberately.
        return True

    def close(self) -> None:
        if self._proc is None:
            return
        with contextlib.suppress(BrokenPipeError, ValueError):
            self._proc.stdin.close()
        self._proc.wait()


# The gate reports' own vocabulary — `validate.Report.render` prints exactly these
# line heads and nothing else. **This is the one place a verdict is known**, which
# is why it is the only colour here that means anything rather than naming a type:
# the report says PASS or FAIL itself, so painting it asserts nothing the text does
# not already.
_VERDICTS = {
    "RESULT: PASS": "bold green", "RESULT: FAIL": "bold red",
    "ERROR": "red", "WARN": "yellow", "WORKLIST": "cyan", "METRICS": "bold",
}


def report(text: str, m: str = "toon") -> str:
    """`validate.Report.render`'s prose, with its verdict lines painted.

    Prose rather than records, so it does not go through `_table` at all — but it
    is what a human reads to decide whether to commit, and the line deciding it is
    buried between forty worklist entries. It stays plain text in `validate.py`,
    which keeps that module out of the display business and keeps the line heads
    greppable by whatever comes after.

    **Gated on table mode, not on `colour()`.** Every other painted path is
    reachable only at a terminal, and this one is printed unconditionally, so
    without the mode test `FORCE_COLOR` would put ANSI into a piped gate report —
    the one output shape a script is most likely to be reading.
    """
    if m != "table" or not colour():
        return text
    # `Style.render` and **not** a `Console`, which every other painted path here
    # uses: a console has a width, and a width crops. The first cut printed through
    # one and silently cut `METRICS:` off at the eightieth column — a line whose
    # whole content is a count of what the gate found. This is prose, it is as wide
    # as it is, and wrapping it is the terminal's business.
    from rich.style import Style

    out = []
    for line in text.split("\n"):
        head = next((h for h in _VERDICTS if line.startswith(h)), None)
        style = _VERDICTS.get(head)
        out.append(Style.parse(style).render(line) if style else line)
    return "\n".join(out)


def rule(name: str) -> str:
    """A section label for table mode — the `# name` line's terminal spelling."""
    from rich.cells import cell_len

    pad = max(0, _term_width() - cell_len(name) - 1)
    line = f"{name} {'─' * pad}"
    return f"\033[1m{line}\033[0m" if colour() else line


def _term_width() -> int:
    import shutil

    return shutil.get_terminal_size(fallback=(80, 24)).columns
