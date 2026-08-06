"""Shared CLI machinery: the declaration helpers, the emitter, and the rename trap.

Three things live here because every group module needs them and none owns them.

**The parser is click.** `group`/`action`/`opt`/`arg` build the tree
programmatically rather than by decorator, because that is the shape the eight
group modules already had — a `register()` per module, its declarations read in
order, each action pointing at a `run_*` function. The `run_*` functions are
untouched by the migration and still take one namespace object, which `action`'s
callback packs from click's keywords: the claim worth being able to make is that
only the *declaration* changed, and rewriting 54 handlers is the one thing that
could quietly falsify it.

**The globals are declared at all three tiers** — root group, each group, each
action — so `--root`/`--json`/`--toon`/`--pager` may be typed anywhere on the
line. Everything but the root's default is `None`, which is how `_namespace`
tells "not given" from "given false" as it walks the context chain inward-out.
That is the job `argparse.SUPPRESS` used to do.

**The rename trap** exists because this CLI went from one tier to two in a hard
cutover, with no aliases. Nothing mechanical calls the harness — no test, no
script — so the consumers are documents: this repo's CLAUDE.md, three skills,
and a human's memory. A parser's own error for a retired spelling is
`No such command` or `no such option`, neither of which says where the thing
went. These two tables do, and they run on raw `argv` before any parsing, so
they were unaffected by the migration.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import click
import cloup
from cloup.constraints import mutually_exclusive, require_one
from cloup.constraints._support import BoundConstraintSpec

from ..render import collect, colour, flush, mode, render, rule
from ..render import pager as paged

OUTPUT_GROUP = cloup.OptionGroup(
    "Output", help="accepted at every tier — before the group, before the action, "
                   "or after it")

def _markdown(text: str, width: int) -> str:
    """A help string rendered as the Markdown it is written in.

    **These strings have always been Markdown** — `**bold**` for the sentence that
    matters, backticks for every path and flag, the same prose style as CLAUDE.md
    and VERBS.md, because they are read in the source at least as often as on
    screen. They were printed with the asterisks in them, so `zones install`'s
    `--help` advertised `**refuses a permuted class map**` on its most important
    line.

    `rich` renders it, rather than a pair of regexes here: this project's own rule
    is that a one-off reimplementation of something a library does is a tell, and
    inline emphasis is where hand-rolled parsing starts and nested spans, escapes
    and code fences are where it ends.
    """
    import io

    from rich.console import Console
    from rich.markdown import Markdown

    console = Console(file=io.StringIO(), width=max(width, 20),
                      force_terminal=colour(), highlight=False)
    console.print(Markdown(text))
    return console.file.getvalue().rstrip("\n")


class _Formatter(cloup.HelpFormatter):
    """cloup's formatter, with the command help body rendered as Markdown.

    Only the body. An option's one-line help stays cloup's, because cloup wraps it
    into a measured second column and handing it back pre-wrapped ANSI would have
    the two of them wrapping the same text to different widths.
    """

    def write_command_help_text(self, cmd) -> None:
        text = cmd.help or ""
        if not text.strip():
            return
        self.write_paragraph()
        rendered = _markdown(text, self.width - self.current_indent - 2)
        pad = " " * (self.current_indent + 2)
        for line in rendered.split("\n"):
            # rich justifies to the console width, so every line comes back
            # right-padded; that is trailing whitespace in a terminal and in a
            # paste, and it is not what cloup's own output does.
            line = line.rstrip()
            self.write(f"{pad}{line}\n" if line else "\n")


THEME = cloup.HelpTheme(
    invoked_command=cloup.Style(fg="bright_white", bold=True),
    heading=cloup.Style(fg="bright_white", bold=True),
    constraint=cloup.Style(fg="magenta"),
    section_help=cloup.Style(fg="bright_black"),
    col1=cloup.Style(fg="green"),
)

class _Context(cloup.Context):
    """Carries the formatter. `Context.settings` has no `formatter_class` — it is a
    class attribute — and a subcommand builds its context from *its own*
    `context_class`, so `_Command`/`_Group` below name this one too."""
    formatter_class = _Formatter


CONTEXT = cloup.Context.settings(
    formatter_settings=_Formatter.settings(theme=THEME),
    help_option_names=["-h", "--help"],
)


class _Command(cloup.Command):
    context_class = _Context


class _Group(cloup.Group):
    context_class = _Context


def globals_params(root_default: Path | None = None) -> list[click.Parameter]:
    """`--root`/`--json`/`--toon`/`--pager`, for the top group and every action.

    **Declared at all three tiers** — root, group, action — so they may be typed
    anywhere on the line. With two tiers of subcommands the last parser to run is
    the action's, so a root-only registration would leave `harness zones predict
    --json` an error while `harness --json zones predict` worked, a distinction no
    user should have to hold.

    Everything but the root's `--root` therefore defaults to **None rather than
    False**, so "not given" is distinguishable from "given false" and `_namespace`
    can tell which tier actually spoke. That is the job `argparse.SUPPRESS` used to
    do; `None` already carries the distinction.

    They share a cloup `OptionGroup`, which is purely about `--help`: four global
    flags inline in every action's option list crowd out the flags that action is
    actually about. This puts them in their own section under the real ones.
    """
    return [
        cloup.Option(["--root"], type=click.Path(path_type=Path),
                     default=root_default, group=OUTPUT_GROUP,
                     help="repo root; every path resolves against it (default .)"),
        cloup.Option(["--json"], is_flag=True, default=None, group=OUTPUT_GROUP,
                     help="indented JSON instead of TOON"),
        cloup.Option(["--toon"], is_flag=True, default=None, group=OUTPUT_GROUP,
                     help="TOON even at a terminal, where an aligned table is the "
                          "default — what a skill's model sees, reproduced by hand"),
        cloup.Option(["--pager"], is_flag=True, default=None, group=OUTPUT_GROUP,
                     help="page the output through $PAGER (default `less -SRFX`, "
                          "which chops rather than wraps, so a table wider than "
                          "the screen scrolls sideways with its columns intact). "
                          "Table mode only, so it does nothing down a pipe"),
    ]


def exclusive(*names: str) -> BoundConstraintSpec:
    """`names` may not be given together — declared, not checked in a handler.

    "Argument validation is the parser's, not an if-chain's" is a stated
    convention here, and it is the one the one-tier CLI was retired for breaking:
    `lexicon --marks --native` silently ran `--marks`. Plain click has no
    mutually-exclusive group, so this was briefly a hand-rolled check in
    `_namespace` and in `run_seam` — which is the convention's own anti-pattern
    with better manners. `cloup` puts it back where it belongs, and
    `ConstraintViolated` is a `UsageError`, so the exit code is 2 either way.
    """
    return BoundConstraintSpec(mutually_exclusive, list(names))


def require_exactly_one(*names: str) -> BoundConstraintSpec:
    """Exactly one of `names`, neither zero nor two. `tei seam`'s
    `--continues`/`--fresh`, which was argparse's one *required* mutually
    exclusive group."""
    return BoundConstraintSpec(require_one, list(names))


GLOBAL_NAMES = ("root", "json", "toon", "pager")


def _namespace(ctx, group_name: str, action_name: str, kw: dict):
    """The parsed arguments as one object, the shape every `run_*` already reads.

    Click hands a callback its parameters as keywords; the action functions were
    written against an `argparse.Namespace` and read `a.root`, `a.ref`, `a.all`.
    Packing rather than rewriting 54 of them is deliberate — this migration's whole
    claim is that only the *declaration* changed, and rewriting the bodies is the
    one thing that could quietly falsify it.

    Parameter names are click's own and deliberately unrenamed, `all` and `json`
    included: the callback takes `**kw`, so a name that shadows a builtin is a dict
    key rather than a binding, and `a.all`/`a.json` are what the action functions
    already read.
    """
    a = SimpleNamespace(group=group_name, action=action_name,
                        **{k: v for k, v in kw.items() if k not in GLOBAL_NAMES})
    # **The whole context chain, innermost first**, because a global may be
    # declared at any of the three tiers and the one the user actually typed is
    # whichever answered. Only the top tier carries a non-None default, so the
    # first non-None walking outward is the value given — or, at the root, the
    # default.
    chain = []
    c = ctx
    while c is not None:
        chain.append(c.params)
        c = c.parent
    for name in GLOBAL_NAMES:
        setattr(a, name, next((p[name] for p in chain
                               if p.get(name) is not None), None))
    a.json, a.toon, a.pager = bool(a.json), bool(a.toon), bool(a.pager)
    a.root = Path(a.root or ".")
    return a


def group(cli: cloup.Group, name: str, help: str,
          sections: tuple[str, ...] = (), section: str | None = None) -> cloup.Group:
    """One tier-1 group. A bare `harness zones` refuses, as a bare `harness` does.

    **The globals are declared here too**, so all three positions parse:
    `harness --json zones check`, `harness zones --json check`, and
    `harness zones check --json`. The middle one is new — under argparse the
    globals sat on the top parser and on every action but never on a group, so
    it was an error, which is a distinction nobody could have predicted from the
    other two working.

    `sections` names the headings a group's actions are listed under, in order.
    **Only where the group's own module docstring already draws the line** — a
    section title over two entries is decoration, and inventing a taxonomy in the
    reference is how a reader learns a distinction the code does not make.
    """
    g = _Group(name, help=help, no_args_is_help=True,
                    params=globals_params(), callback=lambda **_: None)
    for title in sections:
        g.add_section(cloup.Section(title))
    cli.add_command(g, section=_section(cli, section))
    return g


def action(grp: cloup.Group, name: str, func, *, help: str, pageable: bool = True,
           section: str | None = None,
           constraints: tuple[BoundConstraintSpec, ...] = ()) -> cloup.Command:
    """Declare one action: its name, its handler, its help, and the four globals.

    Returns the `cloup.Command`, so a caller hangs parameters on it with
    `arg`/`opt` in the order the argparse registration read in.

    `pageable=False` is for the two actions that print a URL and then block on a
    server: they refuse `--pager` rather than honouring it, a URL inside a pager on
    a command that never returns being a URL nobody reads. It is a keyword here
    rather than a flag on the namespace because it is a property of the action —
    `--pager` is the only thing a caller says.

    Every action gets the `--json`/`--toon` constraint whether it asks or not:
    they are on every action by construction, so their exclusivity has to be too,
    and a per-action opt-in is a rule that holds until someone forgets.
    """
    @click.pass_context
    def callback(ctx, **kw):
        a = _namespace(ctx, grp.name, name, kw)
        a._pageable = pageable
        # The mode is resolved before the pager can replace `sys.stdout` — see
        # `render.mode` — and the flush runs whatever the exit code is, since
        # `views check` and `tei validate` return 1 with a full payload.
        mode(a)
        with paged(a):
            rc = func(a)
        if (doc := flush()) is not None:
            print(doc)
        return rc

    cmd = _Command(name, help=help, params=globals_params(),
                   callback=callback)
    # **Stored, not passed to the constructor.** cloup resolves a constraint's
    # parameter *names* against `self.params` at construction, and here the params
    # arrive afterwards through `opt`/`arg` — that is the shape these eight modules
    # already had. `seal` binds them once registration is finished, and
    # `build_parser` walks the whole tree so no call site can forget.
    cmd._specs = (exclusive("json", "toon"), *constraints)
    grp.add_command(cmd, section=_section(grp, section))
    return cmd


def seal(cmd: cloup.Command) -> None:
    """Bind `cmd`'s deferred constraints, now that all its parameters exist."""
    specs = getattr(cmd, "_specs", ())
    if not specs:
        return
    cmd._params_by_name = {p.name: p for p in cmd.params}
    cmd.param_constraints = tuple(s.resolve_params(cmd) for s in specs)
    cmd.all_constraints = cmd.optgroup_constraints + cmd.param_constraints


def _section(grp: cloup.Group, title: str | None):
    """The named section of `grp`, or None for the default one."""
    if title is None:
        return None
    for s in grp._user_sections:
        if s.title == title:
            return s
    raise KeyError(f"{grp.name}: no section {title!r} — declare it in `group()`")


def opt(cmd: cloup.Command, *decls, **kw) -> cloup.Command:
    """One option. `decls` is click's: the flags, plus a bare name to set the dest."""
    cmd.params.append(cloup.Option(list(decls), **kw))
    return cmd


def arg(cmd: cloup.Command, name: str, **kw) -> cloup.Command:
    """One positional. `nargs=-1` is argparse's `+` and `*`, `required` telling them
    apart — click has no separate spelling for required-variadic, but it does
    enforce it."""
    cmd.params.append(cloup.Argument([name], **kw))
    return cmd


def out(a, obj, name: str | None = None, heading: bool = False) -> None:
    """Emit one section. Aligned table at a terminal, TOON down a pipe, JSON under `--json`.

    A verb emitting several sections calls this several times, deliberately: TOON
    collapses a uniform record list to a header row plus data rows, and a ragged
    key set degrades it to the verbose nested form. Two key sets, two tables.

    The mode is `render.mode(a)` and is decided per invocation, not per section, so
    a verb cannot emit a table and then a TOON block. Which one it is has exactly
    one input beyond the two flags — `sys.stdout.isatty()`.

    **`name` is a section's key, not a heading**, and the distinction is what
    keeps the model's view byte-identical. Under `--json` the sections become one
    keyed document, so a verb printing a second table has to name it or
    `render.flush` refuses; the single-section verbs — 43 of the 58 measured —
    name nothing and are untouched. But naming a section must not make a `# name`
    line appear in **TOON** where none was printed before, since TOON is what
    every skill and every model reads. So `heading` is separate and is passed only
    where such a line was already going out: `out_per_ref`'s split-out list
    fields, which have printed `# field` since they existed.

    **Table mode labels every named section**, `heading` or not, because it has no
    legacy to preserve and because there the label is doing work a `#` line was
    not: several aligned tables in a row are otherwise indistinguishable from one
    table that changed shape.
    """
    m = mode(a)
    if m == "json":
        collect(name, obj, getattr(a, "action", None))
        return
    if name and (heading or m == "table"):
        print(f"# {name}" if m == "toon" else rule(name))
    print(render(obj, m))


def verdict(a, code: int, means: str) -> int:
    """Emit a gating action's exit code as a row, and return it.

    **A gate that signals only through `$?` is illegible to the actor it gates.**
    A groundtruth-reader is refused a shell operator — no `; echo $?`, no
    chaining — for reasons that hold, so the exit code of the verb it is measured
    by was the one fact about its own work it could not obtain. Measured over a
    six-reader batch: every refusal that batch was the operator arm, and the
    commonest single reach was `proposal check REF; echo "EXIT: $?"`, four times
    across three readers, each costing a turn against a budget of eighty.

    The fix belongs here rather than in the guard. Relaxing the operator rule to
    let one idiom through buys back one fact and gives up the property that makes
    the surface auditable; printing the fact costs a row. And the row says more
    than `$?` could: `means` names *why* the code is what it is, so a clean run
    and a run whose only findings were advisories are distinguishable, which they
    are not from the number alone.

    Emitted last, after the findings, because it is the summary of them.
    """
    out(a, {"exit": code, "means": means}, "verdict", heading=True)
    return code


REF_HELP = "page ref: part and scan index, e.g. 1-048"

ALL_HELP = ("Required for a corpus-wide run: naming nothing is a usage error "
            "rather than a silent sweep, because the cost of a sweep should be "
            "at the call site and not inferred from an omission")


def add_all(p, what: str):
    """`--all`, whose help states *what it enumerates* rather than "everything".

    The parameter is mandatory for that reason. "Every page" is four different
    sets in this repo — the 832 scans, the pages with zones, the pages a store
    holds, the review directories — and which one a sweep walks is the whole
    content of the flag.
    """
    return opt(p, "--all", is_flag=True, help=f"{what}. {ALL_HELP}")


JOBS_HELP = ("worker threads for the per-page raster work; 1 runs serially and "
             "builds no pool [cores, capped]")


def add_jobs(p):
    """`--jobs N`, on the actions whose per-page cost is a raster decode.

    **Declared per-action rather than alongside the globals**, because a flag that
    is accepted where it does nothing is a wrong combination the parser should be
    rejecting, and it is dead surface in the VERBS.md gate besides — the same
    argument that retired `MainZone-Quote` from the store's label set.

    `--jobs 1` is the control arm, not a debug switch: the claim these verbs rest
    on is that concurrency moves wall clock and nothing else, and saying so means
    running both sides and diffing the output.
    """
    return opt(p, "--jobs", type=int, default=None, metavar="N", help=JOBS_HELP)


def refs_arg(p, *, all_: str | None = None, extra: str = ""):
    """The `PP-NNN [PP-NNN ...]` positional, plus `--all` where there is a corpus form.

    The positional is **required** when the action must name pages and optional
    when `--all` is the other way to say what to work on — argparse's `+` and `*`.
    There is deliberately no third case: a bare `*` with no `--all` would be a
    sweep spelled as an omission, which is what this replaced.

    Click has one variadic spelling (`nargs=-1`) and distinguishes the two by
    `required`, which it does enforce. The metavar carries `PP-NNN` because
    `REF [REF ...]` is what a usage line would otherwise say, and the ref's shape
    is the thing a caller gets wrong.

    **A click Argument takes no `help`**, where argparse's did, so the ref's own
    help — and `extra`, which several actions use to say something load-bearing
    ("each the page AFTER its gap") — is appended to the *command's* help instead.
    Dropping it would lose it from `--help` silently, and `extra` is exactly the
    text a caller needs before typing.
    """
    arg(p, "ref", metavar="PP-NNN", nargs=-1, required=not all_)
    p.help = f"{p.help}\n\nPP-NNN: {REF_HELP}. Several may be given{extra}."
    if all_:
        add_all(p, all_)
    return p


def page_refs(a) -> list[str]:
    """The refs this invocation names, normalized — `[]` when it named `--all`.

    **Every ref is parsed before the caller does any work**, which is the whole
    point of routing through here: `ocr review` already checked all its refs
    before emitting anything (a refusal arriving after pages of reassuring output
    is worse than no check), and a write verb has the sharper version of the same
    problem — a typo in the fifth ref must not leave four pages written.

    It also holds the three-way exclusion. Refs, `--all` and `--itinerary` are
    three ways of naming a work-list and exactly one may be used, so a caller
    cannot silently prefer one over another; and an action that has `--all` and
    was given none of the three is a usage error rather than a sweep.

    Returning `[]` for `--all` is safe only because of that error: an empty list
    out of here means the corpus was asked for, never that nothing was named.
    """
    from ..context import norm_ref

    refs = getattr(a, "ref", None)
    refs = [refs] if isinstance(refs, str) else list(refs or [])
    given = [name for name, v in (("refs", refs),
                                  ("--all", getattr(a, "all", False)),
                                  ("--itinerary", getattr(a, "itinerary", None)))
             if v]
    if len(given) > 1:
        raise ValueError(
            f"{' and '.join(given)}: refs, --all and --itinerary are three ways "
            "of naming a work-list, and exactly one may be used")
    if not given and hasattr(a, "all"):
        raise ValueError("nothing named: give one or more PP-NNN refs, or --all "
                         "for the whole corpus")
    return [norm_ref(r) for r in refs]


def one_page_only(a, flags: dict[str, str], refs: list[str]) -> None:
    """Refuse a flag that names something only one page has, given several refs.

    A plural positional silently widens every flag beside it, and some of them
    name a thing that exists per page: `--only` is that page's line indices,
    `--out` is one directory that N pages of images would collide in, `--path` is
    one file. Refusing is the point — `--out` in particular had no error at all,
    the second page simply overwrote the first's sheets.

    `flags` maps the attribute name to the spelling to print.
    """
    if len(refs) <= 1:
        return
    for attr, spelling in flags.items():
        if getattr(a, attr, None):
            raise ValueError(f"{spelling} names one page's own — give one ref, "
                             f"not {len(refs)}")


def out_per_ref(a, pairs, name: str | None = None) -> None:
    """Emit one payload per ref: as-is for one, pooled with a `ref` column for N.

    `name` is `out`'s, and needed for the same reason: an action calling this
    twice — `zones check REF` for its findings then its zones, `ocr review` for
    its summary then its queue — has two sections, and under `--json` they have
    to be two keys of one document.

    One ref emits exactly what the single-ref form always emitted, so every
    example in VERBS.md and in the skills stays literally correct; several pool
    into one table whose first field is `ref`. That is the shape `emit`'s own
    docstring argues for — a list of records carrying `ref` as a field rather
    than a dict keyed by ref — and it is what `proposal marks` already does.

    **A list-valued field is split out, not pooled into the row.** TOON collapses
    a uniform record list to a header and rows, but a record holding a nested list
    degrades the *whole outer table* to the verbose form, so one page's `edits`
    would cost the pooled table its shape. Instead the row carries each list's
    **length** and every non-empty list becomes its own ref-keyed table under a
    `# field` line. A count is not a summary standing in for the detail — the
    detail follows, keyed by ref, so nothing is lost and the row stays scannable.
    Two key sets, two tables, which is the rule `out` states.

    **This used to raise instead**, on the reasoning that a caller should be made
    to think about the shape rather than have it chosen for them. That was the
    wrong trade: the split is exactly what the thinking caller writes, so refusing
    bought nothing and left every plural verb whose payload happened to hold a
    list broken until someone ran it with two refs. `ocr clean` was found that
    way, in use, after its tests passed — the guard fired correctly and the bug
    was that there was anything for it to fire on.

    **`--all` always pools, even where it happened to match one page.** The shape
    a caller gets should follow what it asked for, not what the store happened to
    contain — a sweep whose output changed schema on the day the corpus held one
    matching page would be a trap with a long fuse.

    **The field set is decided over every payload, never the first.** It used to be
    read off `pairs[0]`, so a field absent from page one and a list on page five
    reached `_pool` unsplit and tripped its guard — after all the work was done.

    **A list *inside* a record of a list-valued payload is not handled here, on
    purpose.** Where a payload is already one row per finding, a list in a cell is
    the verb emitting a shape that is not a table, and `_pool`'s guard firing is the
    correct outcome rather than something to absorb. `proposal check` was found that
    way and fixed at the source, by giving its six detectors one key set — which is
    the rule `emit`'s own docstring states and the detectors already follow.
    """
    if len(pairs) == 1 and not getattr(a, "all", False):
        out(a, pairs[0][1], name)
        return
    if not pairs:
        out(a, [], name)
        return

    # An **ordered** set, so the `# field` blocks below follow the record's own
    # field order rather than a set's iteration order — which Python randomises per
    # process for strings. The train-zones skill records the same hazard for `--resize`'s class
    # map, where it permuted every label; here it shuffled sub-tables between runs
    # of one unchanged command.
    listy: dict[str, None] = {}
    for _, rep in pairs:
        if isinstance(rep, dict):
            for k, v in rep.items():
                if isinstance(v, list):
                    listy.setdefault(k)
    if not listy:
        _pool(a, pairs, name)
        return

    # **Which treatment a list field gets is decided per field over every page,
    # never per cell.** A list of **records** becomes a count, the records
    # following in their own table; a list of **scalars** is space-joined into the
    # cell — the convention `corrections`' `pages` and `marks`' `refs` already use,
    # since a table of one bare column is worse than a string. An *empty* list
    # cannot say which it is, so a per-cell rule would print `errors: ""` beside
    # `warnings: 1` in the same row and make the column mean two things.
    tabular = [k for k in listy
               if any(rep.get(k) and isinstance(rep[k][0], dict)
                      for _, rep in pairs)]

    def _cell(key, v):
        if key not in listy:
            return v
        return len(v) if key in tabular else " ".join(map(str, v))

    _pool(a, [(r, {k: _cell(k, v) for k, v in rep.items()}) for r, rep in pairs],
          name)
    for key in tabular:
        found = [(r, rep[key]) for r, rep in pairs if rep.get(key)]
        if found:
            # **Pooled even when one page contributed.** At the top level the count
            # decides the shape because the caller named one page; here the caller
            # named several and these rows are a *subset* of them, so dropping the
            # `ref` column would leave a table whose rows belong to a page it does
            # not name — findable only by elimination.
            _pool(a, found, name=key, heading=True)


def _pool(a, pairs, name: str | None = None, heading: bool = False) -> None:
    """Flatten `[(ref, payload)]` into one table with `ref` first, unconditionally."""
    rows = []
    for ref, payload in pairs:
        for item in (payload if isinstance(payload, list) else [payload]):
            for k, v in item.items():
                if isinstance(v, list):
                    raise ValueError(
                        f"cannot pool {ref}: field {k!r} is a list, which would "
                        "degrade the table — emit it as its own ref-keyed table")
            rows.append({"ref": ref, **item})
    out(a, rows, name, heading)


# Retired tier-1 verbs -> where each went. Keys are what `argv[1]` used to be.
RENAMED_VERBS = {
    "context": "tei context REF",
    "validate": "tei validate REF",
    "state": "tei state REF",
    "ids": "tei ids REF  (or `tei pair REF`, which was --pair)",
    "seam": "tei seam REF --continues|--fresh",
    "header": "tei header",
    "ledger": "tei ledger",
    "pages": "ocr pages",
    "lines": "ocr lines REF  (--gaps/--crops/--sheets/--blot are now `ocr gaps`/"
             "`ocr crops`/`ocr sheets`/`ocr blot`; --adopt-gap is retired — a "
             "human gives a dropped line its box in `ocr edit`)",
    "zoom": "ocr zoom REF",
    "review": "ocr review REF",
    "restore": "ocr restore REF",
    "clean": "ocr clean REF",
    "proposal-check": "proposal check REF  (--fix/--codepoints/--set/--replace "
                      "are now `proposal fix`/`codepoints`/`set`/`replace`)",
    "toc-search": "find toc QUERY",
    "toc-near": "find folio N",
    "authority": "find authority QUERY",
    "figures": "corpus figures",
    "normalize": "corpus normalize  (--convert is now --commit)",
}

# Retired flag spellings under a group name that survived. Keyed by the group,
# because `--blot` is a live flag nowhere and an action in two places.
RENAMED_FLAGS = {
    ("zones", "--serve"): "zones edit [REF]",
    ("zones", "--predict"): "zones predict [REF]",
    ("zones", "--score"): "zones score",
    ("zones", "--assemble"): "zones assemble",
    ("zones", "--install"): "zones install CHECKPOINT",
    ("zones", "--remap-model"): "zones remap",
    ("zones", "--remark-eval"): "zones remark-eval FRACTION",
    ("zones", "--delete"): "zones delete REF",
    ("zones", "--diff"): "zones diff [REF]",
    ("zones", "--paragraphs"): "zones paragraphs [REF]",
    ("zones", "--link"): "zones link",
    ("zones", "--blot"): "zones blot [REF]",
    ("zones", "--ink"): "zones check --ink",
    ("zones", "--lines"): "zones check --lines",
    ("zones", "--from"): "zones check --store gt|mz",
    # The one action whose ref was a flag. Every other action in the CLI names a
    # page positionally, and once they all took several it was the odd one out
    # rather than the concise one.
    ("ocr", "--ref"): "ocr corrections PP-NNN [PP-NNN ...]  (or --all)",
    # `--from DIR` across the whole `ocr` group became `--store gt|mz`, the same
    # closed set `zones` has had, once `mz/ocr/` gave the group a second real
    # store. It was never used as a free path — only ever `gt/ocr`, `mz/ocr` or
    # the view — so nothing was given up, and the view stopped being nameable,
    # which is the point.
    # `{action}` is filled in from what was actually typed. A group-wide flag
    # rename has no single action to name, and the alternative — picking one as an
    # exemplar — points the reader at a command they did not run.
    ("ocr", "--from"): "ocr {action} --store gt|mz (omit for the ocr/ view)",
    ("lexicon", "--native"): "lexicon native",
    ("lexicon", "--marks"): "lexicon marks",
    ("lexicon", "--suffixes"): "lexicon suffixes",
    ("lexicon", "--digraphs"): "lexicon digraphs",
    ("lexicon", "--glosses"): "lexicon glosses",
    # A required *file* argument spelled as a flag was the smell that prompted the
    # plural pass; the scope is now a positional taking refs and paths alike.
    ("corpus", "--path"): "corpus normalize REF|PATH [REF|PATH ...]  (or --all)",
    # `--all` is a real flag on `tei validate`, `ids` and `pair`, and
    # `check_renamed` skips a flag the named action genuinely has — so this fires
    # only on the three that do not, and the message must read sensibly for all
    # of them, which is why it names the corpus form rather than a substitute.
    ("tei", "--all"): "tei ledger  (the corpus form of `state`; `context` and "
                      "`seam` have none by design)",
}

# Retired *positional values*, keyed by group and value. The flag table cannot
# reach these: `check_renamed` scans tokens beginning with `-`, and `all` was a
# `choices=` value of `views`' FARM positional. One entry today, and it needs the
# table rather than a special case because a bare `invalid choice: 'all'` names
# the problem and not the fix.
RENAMED_VALUES = {
    ("views", "all"): "views {action} --all",
}


def walk_surface(parser) -> dict[tuple[str, str], set[str]]:
    """`{(group, action): {flags}}` for the whole two-tier parser.

    One walk, two consumers: the rename trap needs the action names to tell an
    old spelling from a new one, and the VERBS.md gate test needs the flags too.
    Deriving both from the real parser is the point — a second hand-maintained
    list of actions would be one more pair of files holding one fact.
    """
    return {key: {o for p in cmd.params if isinstance(p, click.Option)
                  for o in p.opts + p.secondary_opts
                  if o.startswith("--") and o != "--help"}
            for key, cmd in _actions(parser).items()}


def _actions(cli: click.Group):
    """`{(group, action): Command}` — the one place that knows the tree is two-tier.

    Click exposes its subcommands as a plain dict, so this replaces four levels of
    `parser._subparsers._group_actions` reaching into argparse internals. Both
    walkers and the surface test go through it.
    """
    return {(gname, aname): cmd
            for gname, g in cli.commands.items()
            if isinstance(g, click.Group)
            for aname, cmd in g.commands.items()}


def walk_positionals(parser) -> dict[tuple[str, str], dict[str, object]]:
    """`{(group, action): {positional name: nargs}}` for the whole parser.

    A separate walk from `walk_surface` because that one collects
    `option_strings` and a positional has none — deliberately, since the VERBS.md
    gate is about flags and pinning a metavar there would be a style gate wearing
    a correctness gate's clothes. What *is* a correctness question is whether a
    ref positional is plural, and only this sees it.

    **`nargs` is reported in argparse's vocabulary** — `"+"`, `"*"`, `"?"` or
    `None` — rather than click's, which spells every variadic `-1` and carries the
    required/optional distinction in a separate attribute. Translating here keeps
    the gate's assertions written in the terms the *convention* is stated in
    ("refs are plural", "a `*` positional always has `--all`"), and means the
    migration to click did not touch a single one of them.
    """
    return {key: {p.name: _argparse_nargs(p) for p in cmd.params
                  if isinstance(p, click.Argument)}
            for key, cmd in _actions(parser).items()}


def _argparse_nargs(p: click.Argument) -> str | None:
    if p.nargs == -1:
        return "+" if p.required else "*"
    return None if p.required else "?"


def check_renamed(argv: list[str], surface: dict[tuple[str, str], set[str]]
                  ) -> str | None:
    """The new spelling for a retired one, or None if nothing matched.

    Runs before argparse, so a retired spelling never reaches the `invalid choice`
    or `unrecognized arguments` path. Only the first match is reported: someone
    typing two retired flags wants to be told where the command went, not given a
    list.

    **A retired flag is reported even when a live action was named, but only if it
    is not a flag of that action** — and that qualification is the whole
    subtlety. `--ink` and `--lines` are retired spellings under `zones` *and* live
    flags of `zones check`, so a trap that scanned unconditionally would reject
    `zones check --ink`, the correct new form, and tell the user to type what they
    had just typed.

    It used to skip the flag table entirely once an action was named, which was
    the cheap way to get that right and gave up the case that matters more as the
    CLI ages: a flag retired *within* a surviving action. `ocr lines --from` is
    exactly that — the action is right, the flag is not — and under the old rule
    it fell through to argparse's bare "unrecognized arguments: --from", which
    names the problem and not the fix. Asking the parser itself which flags an
    action really has is what makes the narrow test possible.

    **Positional values get the same treatment**, through `RENAMED_VALUES`. A
    retired `choices=` value is invisible to the flag scan, which only looks at
    tokens beginning with `-`, and argparse's own `invalid choice: 'all'` names
    the problem without the fix — the same gap the flag table exists to close.
    Only tokens after the action are considered, so a group or action that
    happened to share the word is not caught by accident.
    """
    if not argv:
        return None
    head = argv[0]
    if head in RENAMED_VERBS:
        return RENAMED_VERBS[head]
    actions = {a for (g, a) in surface if g == head}
    named = argv[1] if len(argv) > 1 and argv[1] in actions else None
    live = surface.get((head, named), set()) if named else set()
    for tok in argv[1:]:
        if not tok.startswith("-"):
            if named and tok != named and (head, tok) in RENAMED_VALUES:
                return RENAMED_VALUES[(head, tok)].format(action=named)
            continue
        flag = tok.split("=", 1)[0]
        if flag in live:
            continue
        if (head, flag) in RENAMED_FLAGS:
            return RENAMED_FLAGS[(head, flag)].format(action=named or "<action>")
    return None


def die_renamed(new: str) -> int:
    print(f"That spelling is gone. This is now:\n\n    harness {new}\n\n"
          "The verbs are two-tier since the reorganization: a group "
          "(tei/ocr/proposal/zones/lexicon/find/corpus) then an action. "
          "`harness --help`, or harness/VERBS.md for the full reference.",
          file=sys.stderr)
    return 2
