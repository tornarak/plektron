"""The render layer: three modes over one payload, and what must not differ.

The load-bearing assertion in this file is that **rendering is a view and never a
transformation**. A display layer that quietly reshapes, reorders, rounds or elides
is the project's governing failure mode wearing a friendly face — output that reads
as the payload and is not — and unlike a bad detector it produces no error signal at
all, because the thing it disagrees with is never printed beside it.

So most of what follows compares a mode against the payload rather than against a
golden string. Golden strings would pin the layout, which is allowed to change; the
values are not.
"""
from __future__ import annotations

import io
import json
import re
import sys
from types import SimpleNamespace

import pytest

from harness import render as R
from harness.emit import emit

# A payload with one of everything the renderer distinguishes: a null, both
# booleans, an int, a float, an empty string, a value containing the TOON
# delimiter, and a Tier-1 form whose combining mark makes len() and display width
# disagree.
ROWS = [
    {"ref": "1-048", "folio": None, "keyed": True, "zones": 6,
     "share": 93.9, "note": "", "form": "g̣"},
    {"ref": "1-101", "folio": 115, "keyed": False, "zones": 12,
     "share": 6.1, "note": "pdftoppm -r 300, then greyscale", "form": "ɪ"},
]

ANSI = re.compile(r"\033\[[0-9;]*m")


def args(**kw):
    return SimpleNamespace(**kw)


def plain(text: str) -> str:
    return ANSI.sub("", text)


# ----------------------------------------------------------------- mode choice


def test_a_pipe_gets_toon_and_a_terminal_gets_a_table(monkeypatch):
    """The whole dispatch, and the reason the default needs no flag.

    An agent's Bash tool pipes both streams — verified against this harness — so a
    model keeps getting TOON byte-for-byte while a human gets columns, and neither
    has to say which it wanted.
    """
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    assert R.mode(args()) == "toon"
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    assert R.mode(args()) == "table"


@pytest.mark.parametrize("tty", [True, False])
def test_the_flags_beat_the_terminal(monkeypatch, tty):
    monkeypatch.setattr(sys.stdout, "isatty", lambda: tty)
    assert R.mode(args(json=True)) == "json"
    assert R.mode(args(toon=True)) == "toon"


def test_toon_mode_is_byte_identical_to_the_old_emitter():
    """The compatibility claim the whole pass rests on: nothing that reads this
    tool through a pipe sees any change at all."""
    for obj in (ROWS, ROWS[0], ["1-048", "1-101"], [], {"a": [1, 2]}):
        assert R.render(obj, "toon") == emit(obj)
        assert R.render(obj, "json") == emit(obj, as_json=True)


# ------------------------------------------------- rendering is not a transform


def test_every_value_survives_into_the_table():
    """No cell is dropped, reordered, rounded or abbreviated.

    Checked against the payload rather than a golden string, so the layout stays
    free to change and the values do not.
    """
    text = plain(R.render(ROWS, "table"))
    lines = [ln for ln in text.split("\n") if ln.strip()]
    assert lines[0].split() == list(ROWS[0]), "header is the record's own key order"
    for row, line in zip(ROWS, lines[1:], strict=True):
        for value in row.values():
            if value == "":
                continue
            assert R._scalar(value) in line, f"{value!r} missing from {line!r}"


def test_nothing_is_ever_truncated(monkeypatch):
    """A `…` in a page ref or a Tier-1 form is a value that reads as a value and
    is not. rich ellipsizes by default; the console is built at the table's own
    natural width so it is never asked to.

    80 columns is the fallback terminal size and the width the prototype failed
    at, which is why it is tested rather than assumed.
    """
    wide = [{"ref": r["ref"], "builder": "harness views build w-figs-blotted",
             "note": "pdftoppm -r 300 over pdfs/, then tools/greyscale_scans.py "
                     "--commit, and never a re-render"} for r in ROWS]
    for width in (40, 80, 100, 120):
        monkeypatch.setattr(R, "_term_width", lambda w=width: w)
        text = plain(R.render(wide, "table"))
        assert "…" not in text, f"truncated at width {width}"
        for row in wide:
            for value in row.values():
                assert value in text


def test_scalars_are_spelled_the_way_toon_spells_them():
    """`null`/`true`/`false`, never Python's `None`/`True`.

    Two renderings of one payload disagreeing about the word for a value would put
    `None` in front of a human and `null` in front of the model for the same
    ledger cell — two files holding one fact, in the one place nobody would think
    to check.
    """
    assert (R._scalar(None), R._scalar(True), R._scalar(False)) == \
        ("null", "true", "false")
    table = plain(R.render(ROWS, "table"))
    for word in ("null", "true", "false"):
        assert word in table
    assert "None" not in table and "True" not in table and "False" not in table


def test_a_combining_mark_does_not_stagger_its_column():
    """`len("g̣")` is 2 and its display width is 1, the store being NFD
    corpus-wide. An aligner counting characters would misalign every column of
    Tier-1 forms — which is `lexicon marks`, `lexicon native` and `proposal
    codepoints`, the three tables most worth reading."""
    from rich.cells import cell_len

    rows = [{"form": f, "n": 1} for f in ("g", "g̣", "ä", "ɪ")]
    lines = [ln for ln in plain(R.render(rows, "table")).split("\n") if ln.strip()]
    assert len({cell_len(ln) for ln in lines}) == 1, "columns do not line up"


# -------------------------------------------------------------- shape fallback


def test_a_ragged_or_nested_payload_falls_back_to_toon():
    """Rather than inventing a layout for it.

    Same reflex as `views check`'s `verified` column, which reports how deep it
    looked instead of implying more. A table drawn over a ragged key set would
    have to leave a hole and say nothing about it.
    """
    for obj in (
        [{"a": 1}, {"b": 2}],                    # ragged key sets
        [{"a": 1}, {"a": 2, "b": 3}],            # a missing field
        [{"a": [1, 2]}],                         # a list in a cell
        {"a": {"b": 1}},                         # a nested record
        [[1, 2], [3, 4]],                        # not records at all
    ):
        assert R.render(obj, "table") == emit(obj), f"{obj!r} should fall back"


def test_a_flat_record_renders_as_aligned_pairs():
    text = plain(R.render(ROWS[0], "table"))
    assert text.startswith("ref:   1-048")
    assert "folio: null" in text


def test_a_list_of_scalars_wraps(monkeypatch):
    monkeypatch.setattr(R, "_term_width", lambda: 30)
    text = R.render([f"1-{i:03d}" for i in range(12)], "table")
    assert "\n" in text and max(len(ln) for ln in text.split("\n")) <= 30
    assert "1-011" in text


def test_an_empty_payload_says_so_rather_than_drawing_a_header():
    """Blank is indistinguishable from clean.

    The rule `exempt` exists for in `gt/zones/` and the one the ink cache's `?`
    column keeps: a bare header over no rows reads as a table that happened to be
    empty, where this says a verb was asked and answered nothing.
    """
    assert R.render([], "table") == "(none)"


# --------------------------------------------------------------------- colour


def test_colour_follows_the_environment_not_the_renderer(monkeypatch):
    """`NO_COLOR` beats `FORCE_COLOR` because it is the one that says *don't*.

    A tool that can be made to shout over an explicit refusal is worse than one
    with no colour at all. Both beat the TTY test, which is how argparse 3.14
    behaves in this same process — this repo's environment sets `FORCE_COLOR=3`,
    and a usage error is already coloured down a pipe because of it.
    """
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("FORCE_COLOR", "3")
    assert R.colour() is False
    monkeypatch.delenv("NO_COLOR")
    assert R.colour() is True
    monkeypatch.delenv("FORCE_COLOR")
    assert R.colour() is True
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    assert R.colour() is False


def test_no_ansi_escapes_reach_toon_or_json(monkeypatch):
    monkeypatch.setenv("FORCE_COLOR", "3")
    for m in ("toon", "json"):
        assert ANSI.search(R.render(ROWS, m)) is None


def test_the_literals_are_painted_and_numbers_are_not(monkeypatch):
    """**The palette is by type, never by verdict**, which is the whole of what
    the renderer is entitled to say: it knows a cell is a boolean and cannot know
    whether `false` there means an unread page or a failed gate.

    Numbers stay plain, and that is the half worth pinning. The grid already
    right-justifies an all-numeric column, so painting it says the same thing
    twice — and since numbers are most of the cells in most of these tables,
    doing it drowned the two marks that carry information. Colour earns its place
    by being rare.

    Which escape each literal gets is deliberately not asserted: that would pin
    rich's default theme, which is allowed to move.
    """
    monkeypatch.setenv("FORCE_COLOR", "3")
    styled = {R._scalar(v): ANSI.findall(R.render([{"x": v}], "table").split("\n")[1])
              for v in (None, True, False, 6, "1-048")}
    assert not styled["6"] and not styled["1-048"], styled
    lit = {k: tuple(v) for k, v in styled.items() if k in ("null", "true", "false")}
    assert all(lit.values()), f"an unpainted literal: {lit}"
    assert len(set(lit.values())) == 3, lit


def test_colour_is_a_layer_over_the_payload_and_strips_back_to_it(monkeypatch):
    """The load-bearing property: paint is not content. Stripped, a coloured
    table is byte-identical to the same table rendered with colour refused — so
    nothing downstream depends on whether the terminal wanted ANSI."""
    monkeypatch.setenv("FORCE_COLOR", "3")
    monkeypatch.delenv("NO_COLOR", raising=False)
    lit = R.render(ROWS, "table")
    monkeypatch.setenv("NO_COLOR", "1")
    assert plain(lit) == R.render(ROWS, "table")
    assert ANSI.search(lit), "nothing was painted, so the test proved nothing"


def test_a_gate_report_is_painted_only_at_a_terminal(monkeypatch):
    """`tei validate` prints its report unconditionally, unlike every other
    painted path, which is reachable only in table mode. Without the mode test
    `FORCE_COLOR` would put ANSI into a piped gate report — the one output shape
    a script is most likely to be reading."""
    monkeypatch.setenv("FORCE_COLOR", "3")
    text = "RESULT: FAIL\nERROR: no @resp on a Tier-1 span\nMETRICS: lines=59"
    assert R.report(text, "toon") == text
    painted = R.report(text, "table")
    assert plain(painted) == text
    assert ANSI.search(painted)


def test_a_gate_report_is_never_cropped(monkeypatch):
    """The regression that painting introduced and this caught: the first cut
    printed through a rich `Console`, and a console has a width, and a width
    crops. `METRICS:` — the line whose whole content is a count of what the gate
    found — came back cut off at the eightieth column."""
    monkeypatch.setenv("FORCE_COLOR", "3")
    monkeypatch.setattr(R, "_term_width", lambda: 40)
    text = "METRICS: " + " ".join(f"k{i}={i}" for i in range(40))
    assert plain(R.report(text, "table")) == text


# --------------------------------------------------------------- startup cost


def test_the_pipe_path_never_imports_rich():
    """rich costs 38 ms against `harness.cli`'s 55 ms, on a CLI whose whole
    `--help` is 110 ms. A 69% startup tax on every non-interactive invocation —
    which is every invocation a model makes — to load a library that path never
    touches.

    Run in a subprocess because this suite has certainly imported rich by now;
    the claim is about a fresh process, which is what a caller gets.
    """
    import subprocess

    src = ("import sys;"
           "from harness.cli import main;"
           "main(['lexicon','marks']);"
           "sys.stderr.write(str(any(m.startswith('rich') for m in sys.modules)))")
    p = subprocess.run([sys.executable, "-c", src], capture_output=True, text=True,
                       cwd=str(__import__("pathlib").Path(__file__).parents[2]))
    assert p.stderr.strip().endswith("False"), p.stderr


# -------------------------------------------------------------- one document


@pytest.fixture(autouse=True)
def _no_leftover_sections():
    """The buffer is module state, so a test that collects and never flushes
    would leak into the next one — and the failure would land somewhere else."""
    R._SECTIONS.clear()
    yield
    R._SECTIONS.clear()


def test_a_single_section_is_the_bare_payload():
    """43 of the 58 captured invocations print one section, and they must not
    grow a wrapper for the sake of the 15 that print several."""
    R.collect(None, ROWS, "check")
    assert json.loads(R.flush()) == ROWS


def test_several_sections_become_one_keyed_document():
    """`--json` is the flag whose entire purpose is being parseable, and it was
    emitting several documents on one stream — `tei validate` with two refs even
    interleaved `# 1-100` comment lines between them."""
    R.collect(None, {"ok": True}, "check")
    R.collect("pages", ROWS, "check")
    assert json.loads(R.flush()) == {"check": {"ok": True}, "pages": ROWS}


def test_the_primary_section_takes_the_action_name():
    """So a verb names only its *extra* tables. Requiring the main one to be
    named as soon as a second appeared would couple two call sites that know
    nothing about each other, and would break the moment the second became
    conditional — which it is, in every one of these verbs."""
    R.collect(None, [1], "paragraphs")
    R.collect("boundaries", [2], "paragraphs")
    assert list(json.loads(R.flush())) == ["paragraphs", "boundaries"]


def test_a_name_collision_refuses_rather_than_dropping_a_table():
    """Two sections resolving to one key would put a whole table in the other's
    slot, silently, and the consumer would see a plausible document missing half
    its content. This is the failure the refusal exists for; it is also exactly
    what every one of the 15 broken verbs did before it was named."""
    R.collect(None, [1], "check")
    R.collect(None, [2], "check")
    with pytest.raises(ValueError, match="distinct name"):
        R.flush()


def test_flush_empties_the_buffer():
    R.collect(None, [1], "x")
    R.flush()
    assert R.flush() is None


# ------------------------------------------------------------------- progress


class _FakeTTY(io.StringIO):
    def isatty(self):
        return True


# Broader than ANSI: a redrawing bar uses cursor-up and erase-line (`[1A`, `[2K`)
# as well as colour, and `ANSI` deliberately matches only SGR — the payload tests
# want to see anything else that leaks into a table.
CSI = re.compile(r"\033\[[0-9;?]*[a-zA-Z]")


def _frames(buf) -> list[str]:
    return [f.strip() for f in CSI.sub("\n", buf.getvalue()).split("\n") if f.strip()]


def test_no_bar_when_stderr_is_not_a_terminal(monkeypatch):
    """`tick` is None and `pmap` skips the call entirely, so a redirected run does
    exactly what it did before the bar existed. That is what keeps the four
    benched sweeps diffable against `--jobs 1`."""
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stderr", buf)
    with R.progress("x") as tick:
        assert tick is None
    assert buf.getvalue() == ""


def test_a_short_sweep_draws_nothing(monkeypatch):
    """The threshold is elapsed time, not item count. A bar that flashes for
    200 ms is noise, and a count cannot tell a 4-page raster sweep from a 40-page
    `ocr lines` — one is seconds and the other is milliseconds."""
    from harness.parallel import pmap

    buf = _FakeTTY()
    monkeypatch.setattr(sys, "stderr", buf)
    monkeypatch.setattr(R, "PROGRESS_AFTER", 10.0)
    with R.progress("checking") as tick:
        pmap(lambda x: x, range(30), 4, tick)
    assert _frames(buf) == []


def test_a_long_sweep_draws_a_bar_and_leaves_nothing_behind(monkeypatch):
    from harness.parallel import pmap

    buf = _FakeTTY()
    monkeypatch.setattr(sys, "stderr", buf)
    monkeypatch.setattr(R, "PROGRESS_AFTER", 0.0)
    with R.progress("checking zones") as tick:
        pmap(lambda x: x, range(30), 4, tick)
    # Against the whole stream rather than the last frame: rich's Live refreshes
    # on its own clock, so which frame is last depends on thread timing.
    drawn = " ".join(_frames(buf))
    assert drawn, "no bar drawn"
    assert "checking zones" in drawn and "30/30" in drawn
    # `transient`: the payload is what should stay on the screen, not the bar, so
    # the last thing written is an erase rather than the final count.
    assert buf.getvalue().rstrip().endswith("\033[2K")


def test_the_bar_names_the_current_item(monkeypatch):
    """"Which page is it on" is most of what a progress line is for on a sweep
    that takes seventeen seconds a page."""
    from harness.parallel import pmap

    buf = _FakeTTY()
    monkeypatch.setattr(sys, "stderr", buf)
    monkeypatch.setattr(R, "PROGRESS_AFTER", 0.0)
    with R.progress("recognizing") as tick:
        pmap(lambda x: x, [f"1-{i:03d}" for i in range(30)], 1, tick)
    assert "1-029" in " ".join(_frames(buf))


# ---------------------------------------------------------------------- pager


def test_the_mode_is_resolved_before_the_pager_can_hide_the_terminal(monkeypatch):
    """The trap the cache exists for.

    `main` replaces `sys.stdout` with the pager's pipe before the action runs.
    Asked again after that, `isatty()` is False and every table would come back
    as TOON — the terminal's own output format decided by the fact that we are
    showing it to the terminal. Silent, and it would look like the table feature
    simply not working.
    """
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    a = args()
    assert R.mode(a) == "table"
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    assert R.mode(a) == "table", "mode changed when stdout was redirected"


def test_only_table_mode_pages(monkeypatch, tmp_path):
    """A pipe must never page even when asked, or every consumer downstream gets
    a pager's idea of the payload — and `--json`/`--toon` are what a machine
    reads."""
    sink = tmp_path / "paged"
    monkeypatch.setenv("PAGER", f"tee {sink}")
    for m, paged in (("toon", False), ("json", False), ("table", True)):
        sink.unlink(missing_ok=True)
        with R.pager(args(_mode=m, pager=True)):
            print("payload")
        assert sink.exists() is paged, f"{m}: paged={sink.exists()}"


def test_the_pager_is_opt_in(monkeypatch, tmp_path):
    """The default is off, and this is the assertion that says so.

    It was on in table mode, on git's reasoning that `less -F` prints and exits
    when the content fits. What that costs is the *ordinary* case — a table that
    fits going through a subprocess and a pipe to arrive looking the same.
    """
    sink = tmp_path / "paged"
    monkeypatch.setenv("PAGER", f"tee {sink}")
    with R.pager(args(_mode="table")):
        print("payload")
    assert not sink.exists()


def test_an_opted_out_action_refuses_the_flag(monkeypatch, tmp_path):
    """`zones edit` and `ocr review` declare `pageable=False` at registration:
    they print a URL and block on a server, so a URL inside a pager sits unread on
    a command that never returns to release it. `--pager` there is a request
    nobody can mean, and is refused rather than honoured."""
    sink = tmp_path / "paged"
    monkeypatch.setenv("PAGER", f"tee {sink}")
    with R.pager(args(_mode="table", pager=True, _pageable=False)):
        print("payload")
    assert not sink.exists()


def test_an_absent_pager_falls_back_to_printing(monkeypatch, capsys):
    """Rather than failing the command. The payload is the point; the pager is a
    convenience, and a machine with no `less` still has to be able to run this."""
    monkeypatch.setenv("PAGER", "definitely-not-a-real-pager-9c3f")
    with R.pager(args(_mode="table", pager=True)):
        print("payload")
    assert capsys.readouterr().out.strip() == "payload"


def test_the_payload_reaches_the_pager_intact_and_stdout_is_restored(
        monkeypatch, tmp_path):
    """Restoring matters beyond tidiness: `main` prints the `--json` flush and
    the `ERROR:` handler after the context closes, and a `sys.stdout` still
    pointing at a dead pipe would lose both."""
    sink = tmp_path / "paged"
    monkeypatch.setenv("PAGER", f"tee {sink}")
    before = sys.stdout
    with R.pager(args(_mode="table", pager=True)):
        assert sys.stdout is not before, "stdout was not redirected"
        print(R.render(ROWS, "table"))
    assert sys.stdout is before, "stdout was not restored"
    text = sink.read_text()
    assert "1-048" in text and "g̣" in text and "pdftoppm -r 300" in text


def test_a_real_two_section_verb_emits_one_document(tmp_path, capsys):
    """End to end through `main`, because the unit tests above cannot see the
    wiring: the buffering only helps if `out` actually defers and `main`
    actually flushes, and either could be right alone while the pair is not.

    `corpus normalize` is the cheapest two-section verb — over an empty root it
    still runs both passes, which is the point of it having two (`scan`
    classifies characters, `convert` reports the files it would rewrite; folding
    them would leave the preview agreeing with itself).
    """
    from harness.cli import main

    assert main(["--root", str(tmp_path), "corpus", "normalize", "--all",
                 "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert list(doc) == ["normalize", "would_convert"]
