"""The CLI surface, held against `harness/VERBS.md`.

**Nothing pinned this CLI until now, and that is why it needed reorganizing.**
Every other test in this suite imports module functions directly; not one built
the parser, called `main`, or shelled out to the binary. So a verb could be
renamed, a flag could grow a second meaning, and a documented mode could stop
existing, with a green suite throughout. The surface drifted into 21 top-level
verbs whose flags formed subcommands nobody had named — `zones` alone carried
21 of them — and no mechanism could have reported it.

This is the `harness header` shape applied to the CLI: two files hold one fact
(the parser and VERBS.md), a page never resolves the correspondence locally, so
without a gate they drift silently. The assertion runs **both directions** —
an action or flag in the parser and not the reference is undocumented, one in
the reference and not the parser is a lie about what the tool does, and both
are the same defect wearing different clothes.

The reference is hand-written rather than generated on purpose. What it has to
carry — which store an action reads, which it writes, what its exit code means
— does not live in the parser and would bloat `--help` past usefulness if it did.
Generation would guarantee agreement about the one thing that is already
checkable and lose the part that is worth writing down.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from harness.cli import build_parser
from harness.cli._common import (
    RENAMED_FLAGS,
    RENAMED_VERBS,
    walk_positionals,
    walk_surface,
)

VERBS_MD = Path(__file__).resolve().parent.parent / "VERBS.md"

# `### group action [ARGS]` — the heading form every entry uses. Positionals are
# part of the heading and deliberately not checked here: a parameter's metavar and
# the reference's prose spelling are allowed to differ (`REF` vs `PP-NNN`), and
# pinning them would be a style gate wearing a correctness gate's clothes.
_HEADING = re.compile(r"^### (\w+) ([\w-]+)", re.M)
# The fenced block under each heading, one flag per line, `--name ... [default]`.
_FENCE = re.compile(r"^```\n(.*?)^```", re.M | re.S)
# Anchored at line start, so a flag *named inside another flag's help* is not
# mistaken for a flag of its own — `--window`'s note mentions `--zoom`, and an
# unanchored search would document it twice and miss nothing in return.
_FLAG = re.compile(r"^(--[\w-]+)", re.M)
# `--root`, `--json` and `--toon` are on every action by construction and share
# one trailing line in each fence rather than being restated twice per entry. They
# have their own assertion (test_every_action_takes_the_globals); comparing them
# per action would be 40 repetitions of a fact one test already holds.
#
# **A flag belongs here only if it is genuinely global**, not merely tedious to
# document. These four qualify because every action emits a payload and all four
# say something about that payload's form or destination. `--jobs` deliberately
# does not, and says why at `_common.add_jobs`: a flag accepted where it does
# nothing is a wrong combination the parser should be rejecting.
#
# `--pager` is the closest call, since `zones edit` and `ocr review` refuse it.
# It stays because *why* they do is a property of the action (it blocks on a
# server) rather than of the flag, and a caller cannot be expected to know which
# two those are before typing.
GLOBALS = {"--root", "--json", "--toon", "--pager"}


def _documented() -> dict[tuple[str, str], set[str]]:
    """`{(group, action): {flags}}` as VERBS.md declares it."""
    text = VERBS_MD.read_text(encoding="utf-8")
    entries = {}
    marks = [(m.start(), m.group(1), m.group(2)) for m in _HEADING.finditer(text)]
    for i, (pos, group, action) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        block = text[pos:end]
        fence = _FENCE.search(block)
        flags = set(_FLAG.findall(fence.group(1))) if fence else set()
        entries[(group, action)] = flags
    return entries


@pytest.fixture(scope="module")
def parser_surface():
    return walk_surface(build_parser())


@pytest.fixture(scope="module")
def doc_surface():
    return _documented()


def test_verbs_md_exists_and_parses():
    """A reference nobody can parse is a reference nothing can gate."""
    assert VERBS_MD.exists(), f"{VERBS_MD} is missing"
    assert _documented(), "no `### group action` headings found — the format moved"


def test_every_action_is_documented(parser_surface, doc_surface):
    undocumented = sorted(set(parser_surface) - set(doc_surface))
    assert not undocumented, (
        "actions exist in the CLI but not in harness/VERBS.md: "
        + ", ".join(f"{g} {a}" for g, a in undocumented))


def test_every_documented_action_exists(parser_surface, doc_surface):
    """The direction that catches a rename nobody propagated — and the one a
    generated reference could never fail."""
    phantom = sorted(set(doc_surface) - set(parser_surface))
    assert not phantom, (
        "harness/VERBS.md documents actions the CLI does not have: "
        + ", ".join(f"{g} {a}" for g, a in phantom))


def test_flags_match_both_directions(parser_surface, doc_surface):
    problems = []
    for key in sorted(set(parser_surface) & set(doc_surface)):
        real = parser_surface[key] - GLOBALS
        documented = doc_surface[key] - GLOBALS
        missing, phantom = real - documented, documented - real
        if missing:
            problems.append(f"{key[0]} {key[1]}: undocumented {sorted(missing)}")
        if phantom:
            problems.append(f"{key[0]} {key[1]}: documented but absent {sorted(phantom)}")
    assert not problems, "\n".join(problems)


def test_every_action_takes_the_globals(parser_surface):
    """`--root`/`--json`/`--toon` are attached to every *action* parser, not the group.

    With two tiers the last parser to run is the action's, so a group-tier
    registration would leave `harness zones predict --json` a parse error while
    `harness zones --json predict` worked — a distinction no user should have to
    hold. Asserted here because it is invisible until someone types it that way.
    """
    for key, flags in parser_surface.items():
        assert GLOBALS <= flags, f"{key[0]} {key[1]} is missing a global"


def test_the_output_modes_are_exclusive(capsys):
    """`--json` and `--toon` may not both be given.

    They name two different serializers for one payload, so a precedence rule
    would be an if-chain silently preferring one — which is what the one-tier CLI
    was retired for, `lexicon --marks --native` having quietly run `--marks`.

    Declared at the parser, as a `cloup` constraint, on **every** action — they
    are on every action by construction, so their exclusivity has to be too, and
    a per-action opt-in is a rule that holds until someone forgets. Checked
    structurally over the whole tree, then once end to end for the exit code.
    """
    from harness.cli import build_parser, main
    from harness.cli._common import _actions

    for (gname, aname), cmd in _actions(build_parser()).items():
        pairs = {frozenset(p.name for p in bc.params) for bc in cmd.all_constraints}
        assert {"json", "toon"} in pairs, \
            f"{gname} {aname}: --json/--toon are not constrained"

    assert main(["lexicon", "marks", "--json", "--toon"]) == 2
    err = capsys.readouterr().err
    assert "--json" in err and "--toon" in err and "mutually exclusive" in err


def test_every_action_has_help(parser_surface):
    """A helpless command is a bare name in the group listing, which is how four
    load-bearing verbs once appeared inside a brace list saying nothing."""
    from harness.cli import build_parser
    from harness.cli._common import _actions

    cli = build_parser()
    groups = {g for g, _ in parser_surface}
    for name, cmd in cli.commands.items():
        assert name in groups, f"group {name} has no actions"
        assert (cmd.help or "").strip(), f"group {name} has no help"
    for (gname, aname), cmd in _actions(cli).items():
        assert (cmd.help or "").strip(), f"{gname} {aname} has no help"


def test_renamed_tables_point_at_real_actions(parser_surface):
    """Every rename target must name something that exists.

    The trap's whole job is to send someone to the right spelling; a stale entry
    sends them to another dead one, which is worse than the parser's own error
    because it reads as authoritative.
    """
    live = {f"{g} {a}" for g, a in parser_surface}
    by_group: dict[str, set[str]] = {}
    for g, a in parser_surface:
        by_group.setdefault(g, set()).add(a)
    for old, new in list(RENAMED_VERBS.items()) + list(RENAMED_FLAGS.items()):
        if "{action}" in new:
            # A flag retired across a whole group has no single action to name, so
            # the entry is a template the trap fills from what was typed. What is
            # checkable is the group, and that *every* action in it would produce a
            # real command — which is the same guarantee, quantified.
            group = new.split()[0]
            assert group in by_group, f"rename for {old!r} names group {group!r}"
            for a in by_group[group]:
                assert f"{group} {a}" in live
            continue
        head = " ".join(new.split()[:2])
        assert head in live, f"rename for {old!r} points at {head!r}, which does not exist"


def test_no_renamed_verb_is_also_a_live_group(parser_surface):
    """A retired top-level verb cannot also be a live group name, or the trap
    would shadow the group and the group would be unreachable."""
    groups = {g for g, _ in parser_surface}
    clash = groups & set(RENAMED_VERBS)
    assert not clash, f"these are both retired verbs and live groups: {sorted(clash)}"


def test_the_trap_does_not_fire_on_a_valid_new_command(parser_surface):
    """`--ink` is a retired `zones` flag *and* a live `zones check` flag.

    A trap that scanned flags regardless of position would reject `zones check
    --ink` — the correct new spelling — and tell the user to type what they had
    just typed. This is the regression that condition exists for.
    """
    from harness.cli._common import check_renamed
    s = parser_surface
    assert check_renamed(["zones", "check", "--ink"], s) is None
    assert check_renamed(["zones", "check", "--lines", "1-048"], s) is None
    assert check_renamed(["zones", "check", "--store", "mz"], s) is None
    assert check_renamed(["ocr", "lines", "--store", "mz"], s) is None
    # ...while the old forms still route.
    assert check_renamed(["zones", "--ink"], s) == "zones check --ink"
    assert check_renamed(["zones", "1-048", "--serve"], s) == "zones edit [REF]"
    assert check_renamed(["validate", "1-101"], s) == "tei validate REF"


def test_a_flag_retired_under_a_live_action_is_still_caught(parser_surface):
    """The case the trap used to give up on.

    `--from` is retired across the whole `ocr` group while every action it sat on
    is still live, so the old "skip the flag table once an action is named" rule
    let it fall through to click's bare `no such option: --from` —
    which names the problem and not the fix. The action typed is echoed back, so
    the message is about the command that was actually run.
    """
    from harness.cli._common import check_renamed
    s = parser_surface
    assert check_renamed(["ocr", "lines", "1-048", "--from", "gt/ocr"], s) == \
        "ocr lines --store gt|mz (omit for the ocr/ view)"
    assert check_renamed(["ocr", "review", "1-048", "--from", "mz/ocr"], s) == \
        "ocr review --store gt|mz (omit for the ocr/ view)"
    # No action named: the placeholder degrades rather than crashing.
    assert "<action>" in check_renamed(["ocr", "--from", "gt/ocr"], s)


def test_write_enable_is_commit_everywhere(parser_surface):
    """One write-enable flag, CLI-wide.

    There used to be four idioms — `--commit`, `--convert`, `--fix`, and simply
    writing on invocation — with no rule saying which applied where, so the only
    way to know whether a command was about to touch `gt/` was to read its
    source. `--convert` and `--fix` are gone as write-enables; anything else
    claiming the role would be a fifth.
    """
    retired = {"--convert", "--dry-run"}
    for key, flags in parser_surface.items():
        overlap = flags & retired
        assert not overlap, f"{key[0]} {key[1]} still carries {sorted(overlap)}"


# **The actions that may name only one page, and why.** Held by name so a new
# singular verb fails the suite rather than passing on the reviewer noticing.
# Every other ref-taking action takes as many as you like.
SINGLE_REF_OK = {
    ("tei", "context"):
        "the payload is one page's collation prompt, built to hand to one model "
        "for one page; a merged stream is not consumable by what it exists for",
    ("ocr", "dispatch"):
        "the same — one page's reading prompt, handed to one agent. Concatenating "
        "two would produce a text that names two refs and instructs on neither",
    ("proposal", "set"):
        "LINE/--field/--value name one entry of one proposal",
    ("proposal", "replace"):
        "the same; a line index is an identity belonging to exactly one page",
}

# **Plural actions that deliberately have no corpus form.** The rule is that a
# plural ref positional carries `--all` unless it is here — so an omission is a
# decision on the record rather than something nobody got round to.
NO_ALL_OK = {
    ("ocr", "crops"):
        "expensive in time and disk, and written per page by a pass working on "
        "that page; a corpus form is a great many bytes nobody asked for",
    ("ocr", "sheets"): "the same as crops",
    ("ocr", "numbered"):
        "the same as crops — one composite per page, written by the pass reading "
        "that page. 832 of them is a gigabyte nobody asked for",
    ("ocr", "zoom"): "magnifies selected lines *of* a page",
    ("zones", "delete"):
        "un-keying the whole ground-truth store must not be one flag away from a "
        "command someone types. `ocr clean` has --all because it deletes only "
        "derived output; this deletes authored work",
    ("tei", "state"):
        "`tei ledger` IS the corpus form, and a second spelling of one report is "
        "how two answers to one question start to drift",
    ("tei", "seam"):
        "--continues/--fresh asserts something about THIS seam; a corpus-wide "
        "'everything continues' is not a claim anyone could mean",
    ("ocr", "queue"):
        "a batch is what you are about to spend that many agents on, so it is "
        "named page by page and never implied. `--all` here would deal out every "
        "unread page in the corpus to however many readers happened to be "
        "dispatched, and the ones nobody claimed would sit in the queue looking "
        "queued",
    ("ocr", "reconcile"):
        "it checks the batch that was just dealt, and the refs are the claim "
        "being made — that THESE pages went out. Reconciling 'everything' cannot "
        "distinguish a page this batch lost from one never sent",
    ("tei", "queue"): "the same as `ocr queue`, and for the same reason",
    ("tei", "reconcile"): "the same as `ocr reconcile`",
}


def test_a_ref_positional_is_plural_unless_declared_otherwise():
    """Naming several pages is the rule; naming one is the exception.

    A shell loop over a single-ref verb was the whole friction this replaced, and
    the fix does not hold by itself — the next action added would be written
    singular unless something failed. So the exemptions are a table with reasons
    and everything else must be `+` or `*`.

    `walk_surface` cannot see this: it collects `option_strings`, and a positional
    has none. Hence the second walk.
    """
    for key, positionals in walk_positionals(build_parser()).items():
        nargs = positionals.get("ref")
        if nargs is None and "ref" not in positionals:
            continue                       # takes no ref at all
        if key in SINGLE_REF_OK:
            assert nargs is None, \
                f"{key[0]} {key[1]} is listed as single-ref but takes {nargs!r}"
            continue
        assert nargs in ("+", "*"), \
            (f"{key[0]} {key[1]} takes one ref. Make it plural, or add it to "
             f"SINGLE_REF_OK with the reason.")


def test_a_plural_action_has_a_corpus_form_unless_declared_otherwise(parser_surface):
    """`--all` where a plural action could sweep, and a named reason where not.

    The companion to the rule above and the more easily forgotten half: a plural
    positional whose corpus form was simply never written looks exactly like one
    where the absence was decided. Single-ref actions are exempt by construction —
    there is nothing for `--all` to mean beside a positional that takes one page.
    """
    positionals = walk_positionals(build_parser())
    for key, flags in parser_surface.items():
        if positionals.get(key, {}).get("ref") not in ("+", "*"):
            continue
        if key in NO_ALL_OK:
            assert "--all" not in flags, \
                f"{key[0]} {key[1]} is listed as having no corpus form but has --all"
            continue
        assert "--all" in flags, \
            (f"{key[0]} {key[1]} is plural but has no --all. Add one, or add it "
             f"to NO_ALL_OK with the reason.")


# An empty invocation here names no work over the corpus, so the rule below does
# not apply: `verbs show` reads one committed document and its empty case prints
# the list of action names, which is the cheapest answer to "what can I run" and
# the reason a caller reaches for it first. The rule guards against a *sweep*
# spelled as an omission, not against a default.
STAR_WITHOUT_ALL_OK = {("verbs", "show"): "lists the action names; touches no store"}


def test_a_star_positional_always_has_all():
    """`nargs="*"` and no `--all` is a sweep spelled as an omission.

    That is the shape this pass removed — `zones check` bare walked 832 pages and
    nothing at the call site said so — and it is worth a gate of its own, because
    the way it would come back is someone widening a `+` to `*` for convenience
    and not noticing that the empty case now means something.
    """
    surface = walk_surface(build_parser())
    for key, positionals in walk_positionals(build_parser()).items():
        if key in STAR_WITHOUT_ALL_OK:
            continue
        for name, nargs in positionals.items():
            if nargs == "*":
                assert "--all" in surface[key], \
                    (f"{key[0]} {key[1]}: {name} accepts nothing at all but the "
                     f"action has no --all, so an empty invocation means a sweep "
                     f"nobody asked for")


def test_the_source_flag_is_always_a_closed_set(parser_surface):
    """One spelling for "which store", and it can never be a free path.

    `--from DIR` and `--store gt|mz` coexisted as two names for one job with
    incompatible types, `--from` free and `--store` closed. `--from` is gone: it
    was never pointed at anything but `gt/ocr`, `mz/ocr` or the view, so the free
    path bought nothing and cost the guarantee — a free path is how a check ends
    up compared against its own input.

    **The view is deliberately not a value.** It is not a store; omitting the flag
    is how a caller says "whatever is current for this page". Letting it be named
    here would put a ratified and an unratified page under one verdict, which is
    the reason `zones check --store` was closed in the first place.
    """
    import click

    from harness.cli._common import _actions

    for (gname, aname), cmd in _actions(build_parser()).items():
        assert "--from" not in {o for p in cmd.params for o in p.opts}, \
            f"{gname} {aname} still carries the retired --from"
        for p in cmd.params:
            if "--store" in p.opts:
                assert isinstance(p.type, click.Choice), \
                    f"{gname} {aname}: --store is not a closed set"
                assert tuple(p.type.choices) == ("gt", "mz"), \
                    f"{gname} {aname}: --store is not the closed pair"


def test_every_flag_that_parses_also_renders_in_help():
    """`--help` and the parser must agree, in the direction that actually failed.

    cloup splits `params` into grouped and ungrouped options once, in
    `OptionGroupMixin.__init__`, and formats `--help` off that split — while click
    parses off `params`. Since every action-specific option in this CLI is hung on
    the command *after* construction, all of them parsed correctly and none of
    them appeared in any help output: `proposal codepoints --line` was real,
    documented in `VERBS.md`, gated by the test above, and invisible to `-h`. A
    reader checked the help, concluded the flag did not exist, guessed a
    positional, and spent two turns on the usage error.

    `test_flags_match_both_directions` cannot see this — it compares the parser
    against the reference, and both of those were right.
    """
    import click

    from harness.cli import build_parser
    from harness.cli._common import _actions

    cli = build_parser()
    ctx = click.Context(cli)
    for (gname, aname), cmd in _actions(cli).items():
        shown = {o.name for o in cmd.get_ungrouped_options(ctx)}
        for grp in getattr(cmd, "option_groups", ()):
            shown |= {o.name for o in grp.options}
        for p in cmd.params:
            if isinstance(p, click.Option):
                assert p.name in shown, (
                    f"{gname} {aname}: {p.opts} parses but renders in no "
                    "--help section")
