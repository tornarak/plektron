"""The reader guards decide; a test is what says they decide the same thing twice.

Both subagent guards (`groundtruth-reader`, `moll-reader`) are PreToolUse hooks that
return `permissionDecision: allow` on calls they have checked, rather than exiting 0
and deferring. That is the difference between a batch of six readers running and a
human answering forty prompts, and it means the hooks are now the only thing standing
between an agent and the corpus stores — a deferral would at least have asked. Nothing
exercised them before this file: they were shell scripts, edited by hand, whose
failure mode is silent (a `case` arm that never matches blocks nothing) and whose
other failure mode is worse (an over-broad arm that `allow`s the store it was written
to protect).

Three properties per guard, and they are the three ways a hook of this shape breaks:

1. **The allowed calls are allowed without a prompt** — exit 0 *and* a decision on
   stdout. Exit 0 alone is the old behaviour and is what this work removed.
2. **The refusals fire**, each on the tree it names.
3. **The refusals cannot be walked around** — `..`, a pipe, a `--all` sweep.

Fed as JSON on stdin, exactly as the runtime feeds them, and asserted on the real
scripts in `.claude/hooks/`. `jq` is a hard dependency of both.
"""

import json
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
GT_GUARD = REPO / ".claude/hooks/groundtruth-reader-guard.sh"
MOLL_GUARD = REPO / ".claude/hooks/moll-reader-guard.sh"


def run(guard: Path, tool: str, **tool_input):
    """Invoke a guard the way the runtime does and return (code, decision, stderr).

    `decision` is the parsed `permissionDecision`, or None when the hook wrote
    nothing — which is the deferral this work exists to eliminate, so the tests
    have to be able to tell it apart from an allow.
    """
    payload = {"tool_name": tool, "tool_input": tool_input}
    p = subprocess.run([str(guard)], input=json.dumps(payload), text=True,
                       capture_output=True, cwd=REPO)
    decision = None
    if p.stdout.strip():
        decision = json.loads(p.stdout)["hookSpecificOutput"]["permissionDecision"]
    return p.returncode, decision, p.stderr


def allowed(guard, tool, **ti):
    code, decision, err = run(guard, tool, **ti)
    assert code == 0, f"blocked: {err}"
    assert decision == "allow", (
        f"exit 0 with no decision defers to the permission prompt: {ti}")


def blocked(guard, tool, **ti):
    code, decision, err = run(guard, tool, **ti)
    assert code == 2, f"not blocked (decision={decision!r})"
    assert decision is None, "a block must not also emit a decision"
    assert err.strip(), "a block the reader cannot read the reason for"
    return err


# --- groundtruth-reader -----------------------------------------------------

@pytest.mark.parametrize("cmd", [
    "uv run harness ocr claim",
    "uv run harness ocr gaps 1-031 --store mz",
    "uv run harness ocr lines 1-031 --store mz",
    "uv run harness ocr numbered 1-031 --store mz",
    "uv run harness ocr sheets 1-031 --store mz --only 4-6",
    "uv run harness ocr zoom 1-031 --store mz --only 12@55-80 --zoom 2",
    "uv run harness ocr calls 1-031",
    "uv run harness verbs show ocr zoom",
    "uv run harness proposal fix 1-031",
    "uv run harness proposal check 1-031",
    "uv run harness corpus normalize review/1-031/proposal.json",
    "uv run harness lexicon misses",
    "uv run harness lexicon marks",
    "uv run harness lexicon conflicts",
    "uv run harness lexicon lookup kulu",
    "uv run harness lexicon lookup kulu --min-pages 3",
    "uv run harness find glyph",
])
def test_gt_the_whole_loop_runs_unprompted(cmd):
    """Every command the standing brief tells the reader to run, in order.

    If one of these ever needs a prompt, the batch stalls on it six times over.

    `ocr calls` is here because it was once missing: the report contract asked
    for the ledger pasted and the allowlist refused the verb, so `1-041`'s reader
    reported its ladder from memory instead — "6 image calls, inside budget"
    against a ledger reading 4 zooms, 3 at 4x, 8 lines re-opened. A contract that
    names a verb and a guard that blocks it is worse than either alone, because
    the fallback is the exact failure the verb was written to remove.

    `verbs show` is here for the same reason one step earlier: wanting to know the
    surface of your own commands is a fair question, and with no way to ask it a
    reader `Read` `VERBS.md` twice mid-page and spent 33,251 tokens — a fifth of
    that reading's whole context.
    """
    allowed(GT_GUARD, "Bash", command=cmd)


@pytest.mark.parametrize("cmd", [
    "uv run harness ocr restore 1-031",           # writes gt/ocr/
    "uv run harness ocr edit 1-031",              # the human's band-vs-line call
    "uv run harness ocr queue 1-031 1-032",       # a reader dealing itself a batch
    "uv run harness ocr reconcile 1-031",         # auditing a run it is a subject of
    "uv run harness ocr dispatch 1-031",          # retired, and stays refused
    "uv run harness ocr clean 1-031",             # destroys the record of the pass
    "uv run harness ocr review --serve",          # a human's tool
    "uv run harness views build",
    "git commit -am wip",
    "python3 -c 'print(1)'",
    "ls /etc",
    "ls gt/ocr",
    "ls review/1-031 /etc",                       # one allowed argument is not enough
    "ls review/1-031/../../gt/ocr",
    "cat keying_spec.md",
    "cat review/1-031/proposal.json",             # allowed to Read, not to shell at
    "uv run harness proposal check --all",
    "uv run harness ocr lines 1-031 --store mz | head -5",
    "uv run harness ocr lines 1-031 --store mz > /tmp/x",
    "uv run harness ocr gaps 1-031 && uv run harness ocr lines 1-031",
])
def test_gt_everything_else_is_refused(cmd):
    blocked(GT_GUARD, "Bash", command=cmd)


@pytest.mark.parametrize("cmd", [
    "uv run harness lexicon native",
    "uv run harness lexicon native --json",
])
def test_gt_the_bare_form_list_is_refused_in_favour_of_the_lookup(cmd):
    """**The hole this allowlist had for four batches.**

    The arm read `lexicon [a-z]+` under a comment calling the group "measurement",
    which is true of `marks`, `digraphs` and `suffixes` — they report distributions
    — and false of `native`, which emits 490 ratified spellings as a bare list. A
    prior says *look again*; a list of spellings says *write this*, and the
    difference is the whole of what the firewall is about.

    `lookup` is the same corpus behind a discipline: a page-count floor, a refusal
    where the book spells a word two ways, and a handle that records in the
    proposal that the corpus supplied the glyphs. A form copied out of a list is
    indistinguishable from a form that was read; the record is the only reason a
    reader is allowed the corpus at all.
    """
    r = blocked(GT_GUARD, "Bash", command=cmd)
    assert "lexicon lookup" in r


@pytest.mark.parametrize("cmd", [
    # The gazetteer prose this corpus is made of. Both were reported as tool
    # facts by readers who then rewrote Bogoras's punctuation to get past them.
    "uv run harness proposal set 1-031 12 --field text --value "
    "'Register, 4 houses, 28 inhabitants; Nordquist, 9 houses'",
    'uv run harness proposal set 1-031 12 --field note --value '
    '"corrected against the raster; the ditto is U+201C"',
    "uv run harness proposal set 1-031 12 --field text --value "
    "\"Ai'wan and Ke'rek, both marked\"",
    "uv run harness proposal replace 1-031 12 --old 'a>b' --new 'a<b'",
])
def test_gt_punctuation_inside_a_quoted_argument_is_not_chaining(cmd):
    """A `;` in a `--value` is page text, not an operator.

    The test was a substring `case` over the raw command, which cannot tell the
    two apart — so keying an ordinary gazetteer line was refused as chaining, and
    two separate readers recorded that as a property of the harness. One of them
    "fixed" it by splitting Bogoras's semicolons into separate sentences, i.e. a
    guard against smuggling ended up altering the transcription it guards.
    """
    allowed(GT_GUARD, "Bash", command=cmd)


@pytest.mark.parametrize("cmd", [
    # Still an operator: outside quotes, or expanding inside double quotes.
    "uv run harness ocr lines 1-031; rm -rf gt",
    'uv run harness proposal set 1-031 12 --field note --value "$(cat /etc/passwd)"',
    'uv run harness proposal set 1-031 12 --field note --value "`id`"',
    "uv run harness ocr lines 1-031 --store mz \"| head -5\" ; ls",
])
def test_gt_an_operator_outside_quotes_is_still_refused(cmd):
    """Quote-awareness is not permissiveness — single quotes are literal and safe,
    double quotes still expand, and bare metacharacters are operators."""
    blocked(GT_GUARD, "Bash", command=cmd)


@pytest.mark.parametrize("cmd", [
    "ls review/1-031",
    "ls review/1-031/",
    "ls -la review/1-031/zoom",
    "ls review",
    "ls .claude/agent-memory/groundtruth-reader/",
    # Without the trailing slash, which is how anyone actually types it — and
    # which the first version of this arm refused, because the constant it
    # matched against carries one. A rule that allows only the spelling nobody
    # uses is a rule that does not exist.
    "ls .claude/agent-memory/groundtruth-reader",
    "ls /home/x/machine_press/.claude/agent-memory/groundtruth-reader",
    "ls review/1-031 review/1-031/sheets",
])
def test_gt_ls_is_allowed_over_the_trees_it_may_already_read(cmd):
    """The one shell command in the surface, and it gives up nothing.

    Every file under `review/` is already readable, so listing that tree exposes
    no path a `Read` could not open — this closes the gap between "you may read
    this" and "you may find out what is here", which is where readers kept
    falling. It was not a marginal habit: measured over four batches, every
    reader tried `ls` and each was refused, 2 to 4 refusals per reader per batch
    at a turn apiece against a budget of 80. Four independent batches make that a
    property of the instruction, not of any reader.
    """
    allowed(GT_GUARD, "Bash", command=cmd)


def test_gt_the_ls_refusal_names_the_trees_and_glob():
    err = blocked(GT_GUARD, "Bash", command="ls /etc")
    assert "review/" in err and "Glob" in err


def test_gt_the_cat_refusal_names_read():
    """A refusal that says only "not in your surface" leaves the reader to work
    out that a *tool* rather than a *permission* was what it was missing. Two
    re-tried the same file with `Read` only after burning the turn."""
    for cmd in ("cat keying_spec.md", "head -5 docs/decisions.md",
                "tail docs/rasters.md", "less CLAUDE.md"):
        err = blocked(GT_GUARD, "Bash", command=cmd)
        assert "Read" in err, f"{cmd}: the refusal does not name the tool: {err}"


def test_gt_edit_is_not_in_the_surface():
    """Named, because it is left out deliberately and would look like an omission.

    `ocr edit` is the human's call on whether a band of ink is a dropped line or
    is not type at all — a browser editor, and a judgement the reading pass is
    explicitly not asked for. A reader describes the band in its report; it does
    not settle it, and it records it nowhere on disk. A verb in the allowlist is a
    verb a reader will find a reason to try.
    """
    blocked(GT_GUARD, "Bash", command="uv run harness ocr edit 1-031")


@pytest.mark.parametrize("path", [
    "review/1-031/proposal.json",
    "/home/x/machine_press/review/1-031/proposal.json",
    ".claude/agent-memory/groundtruth-reader/some-finding.md",
])
def test_gt_writes_land_in_two_places(path):
    allowed(GT_GUARD, "Write", file_path=path, content="{}")
    allowed(GT_GUARD, "Edit", file_path=path, old_string="a", new_string="b")


@pytest.mark.parametrize("path", [
    "gt/ocr/chukchi-1-031.xml",                 # the store the pass may not write
    "review/1-031/decision.json",               # a human's
    "gt/zones/chukchi-1-031.xml",               # page geometry — report, never repair
    "keying_spec.md",                           # normative text is read, not edited
    "review/1-031/../../gt/ocr/chukchi-1-030.xml",
    ".claude/agent-memory/moll-reader/x.md",    # another agent's memory
])
def test_gt_no_other_write_target(path):
    blocked(GT_GUARD, "Write", file_path=path, content="x")
    blocked(GT_GUARD, "Edit", file_path=path, old_string="a", new_string="b")


@pytest.mark.parametrize("path", [
    "review/1-031/numbered.png",
    "review/1-031/sheets/lines-04-06.png",
    "review/1-031/zoom/line-12.png",
    "review/1-031/proposal.json",
    "concordance.md",
    "CLAUDE.md",
    "harness/README.md",
    "docs/decisions.md",
    ".claude/skills/rebuild-groundtruth/checklist.md",
    ".claude/agent-memory/groundtruth-reader/folio-can-sit-on-own-thin-alto-line.md",
    "data/lexicon_extra.txt",
])
def test_gt_reads_the_page_and_the_spec_unprompted(path):
    allowed(GT_GUARD, "Read", file_path=path)


@pytest.mark.parametrize("path,names", [
    ("gt/ocr/chukchi-1-030.xml", "gt/ocr/"),
    ("mz/ocr/chukchi-1-031.xml", "ocr lines"),
    ("ocr/chukchi-1-031.xml", "read views"),
    ("zones/chukchi-1-031.xml", "read views"),
    ("review/1-030/decision.json", "adjudication"),
    ("scans/chukchi-1-031.png", "image ladder"),
])
def test_gt_the_evidence_stores_are_refused_by_name(path, names):
    """Each refusal says which rule it is — a generic block teaches nothing."""
    err = blocked(GT_GUARD, "Read", file_path=path)
    assert names in err, f"the refusal for {path} does not name why: {err}"


@pytest.mark.parametrize("path,names", [
    ("keying_spec.md", "TRANSCLUDED"),
    ("/home/x/machine_press/keying_spec.md", "TRANSCLUDED"),
    ("harness/VERBS.md", "verbs show"),
    ("/home/x/machine_press/harness/VERBS.md", "verbs show"),
])
def test_gt_text_the_reader_already_has_is_refused_with_where_it_is(path, names):
    """Refused for cost, not for secrecy — so the message must say where the
    content already is, or the reader reads the refusal as "do without".

    `keying_spec.md` is transcluded whole into the system prompt, so reading it
    pays for ~15k tokens twice; `harness/VERBS.md` has `verbs show`, and reading
    it whole cost one page 33,251 tokens — a fifth of its context — for two
    lookups. These were allowed on the reasoning that a rule a reader cannot
    verify is worse than a redundant read, which had it backwards: the reader
    cannot fail to have the spec, because the spec is what it was built from.
    """
    err = blocked(GT_GUARD, "Read", file_path=path)
    assert names in err, f"the refusal for {path} does not say where it is: {err}"


def test_gt_the_normative_text_it_does_not_carry_stays_readable():
    """The refusal above is about duplication, so it must not spread to the
    documents a reader genuinely has no other route to."""
    for path in ("concordance.md", "CLAUDE.md", "harness/README.md",
                 "docs/decisions.md", "data/lexicon_extra.txt"):
        allowed(GT_GUARD, "Read", file_path=path)


def test_gt_a_traversal_does_not_reach_the_store():
    blocked(GT_GUARD, "Read", file_path="review/1-031/../../gt/ocr/chukchi-1-030.xml")


# --- moll-reader ------------------------------------------------------------

def test_moll_writes_its_table_and_memory_unprompted():
    allowed(MOLL_GUARD, "Write",
            file_path="scratch/chukchi/moll-md/entries/moll-035.md", content="x")
    allowed(MOLL_GUARD, "Write",
            file_path=".claude/agent-memory/moll-reader/note.md", content="x")


def test_moll_is_blind_to_its_witness_store():
    """The property the whole pass is worth having: two witnesses, not one."""
    err = blocked(MOLL_GUARD, "Read",
                  file_path="scratch/chukchi/moll-scans/ocr/moll-035.txt")
    assert "witness" in err
    # And not through the crop hatch either, which is a different tool name for
    # the same read.
    blocked(MOLL_GUARD, "Bash",
            command="identify scratch/chukchi/moll-scans/ocr/moll-035.txt")


def test_moll_crops_but_does_not_enhance():
    allowed(MOLL_GUARD, "Bash",
            command="convert scratch/chukchi/moll-scans/marked/moll-035.png "
                    "-crop 400x200+100+900 scratch/chukchi/moll-scans/crops/a.png")
    blocked(MOLL_GUARD, "Bash",
            command="convert scratch/chukchi/moll-scans/marked/moll-035.png "
                    "-sharpen 0x1 scratch/chukchi/moll-scans/crops/a.png")


def test_moll_may_not_write_into_the_corpus():
    blocked(MOLL_GUARD, "Write", file_path="gt/ocr/chukchi-1-031.xml", content="x")
    blocked(MOLL_GUARD, "Write", file_path="tei/1-031.xml", content="x")
