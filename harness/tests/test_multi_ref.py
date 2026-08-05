"""Naming several pages at once: the output rule, the refusals, the up-front check.

The CLI took one ref per invocation almost everywhere, so a two-page batch was a
shell loop — and for the predict verbs a scratch `.lst` file written only to be
handed to `--itinerary`, because there the loop was also the slow way round. What
`test_cli_surface.py` gates is that every ref positional is *plural*; what this
file gates is that being plural means something coherent.

Three properties, and they are separable:

- **one ref emits exactly what it always did.** Every example in VERBS.md, in both
  reading skills and in CLAUDE.md is a single-ref invocation, so a change in that
  shape would falsify the documentation rather than extend it;
- **several pool into one table with `ref` first**, key set identical across rows,
  because TOON collapses a uniform record list and degrades on a ragged one;
- **the refusals happen before any work.** A typo in the fifth ref must not leave
  four pages written, and a flag naming something only one page has must not
  silently pick a page.
"""
from __future__ import annotations

import json
from pathlib import Path

from harness.cli import main

ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"


def _alto(root: Path, store: str, ref: str, texts=("one", "two")) -> Path:
    """A minimal `ocr predict`-shaped page: geometry, one `String` per line."""
    p = root / store / f"chukchi-{ref}.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = "".join(
        f'<TextLine ID="l{i}" HPOS="100" VPOS="{200 + i * 60}" WIDTH="1700" '
        f'HEIGHT="50" BASELINE="100 {245 + i * 60} 1800 {245 + i * 60}">'
        f'<Shape><Polygon POINTS="100 {200 + i * 60} 1800 {250 + i * 60}"/></Shape>'
        f'<String CONTENT="{t}" HPOS="100" VPOS="{200 + i * 60}" WIDTH="1700" '
        f'HEIGHT="50"/></TextLine>'
        for i, t in enumerate(texts, 1))
    p.write_text(f'<alto xmlns="{ALTO_NS}"><Layout><Page><PrintSpace>'
                 f'<TextBlock ID="r1">{lines}</TextBlock>'
                 "</PrintSpace></Page></Layout></alto>", encoding="utf-8")
    return p


def _proposal(root: Path, ref: str, texts=("one", "two")) -> Path:
    p = root / "review" / ref / "proposal.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(
        {"ref": ref,
         "lines": {str(i): {"text": t} for i, t in enumerate(texts)}}),
        encoding="utf-8")
    return p


def _run(capsys, *argv) -> tuple[int, str, str]:
    """Exit code, stdout, stderr — all three, because `readouterr` drains both
    and a second call for the error text would find it already consumed."""
    code = main(list(argv))
    cap = capsys.readouterr()
    return code, cap.out, cap.err


# ------------------------------------------------------------- the output rule

def test_one_ref_emits_what_it_always_did(tmp_path, capsys):
    """No `ref` column, no header, no pooling — the documented single-page shape.

    This is the property that lets the whole change be additive: every example
    written down anywhere in this repo is a single-ref invocation.
    """
    _alto(tmp_path, "gt/ocr", "1-048")
    code, out, _err = _run(capsys, "ocr", "lines", "1-048", "--store", "gt",
                     "--root", str(tmp_path))
    assert code == 0
    header = out.splitlines()[0]
    assert header.startswith("[2]{index,")     # first field is the record's own
    assert "ref" not in header.split("{", 1)[1].split(",")[0]


def test_several_refs_pool_with_ref_first(tmp_path, capsys):
    for ref in ("1-048", "1-049"):
        _alto(tmp_path, "gt/ocr", ref)
    code, out, _err = _run(capsys, "ocr", "lines", "1-048", "1-049", "--store", "gt",
                     "--root", str(tmp_path))
    assert code == 0
    header = out.splitlines()[0]
    assert header.startswith("[4]{ref,"), header
    # One key set across every row, or TOON drops to the verbose nested form and
    # the table stops being a table.
    assert "- ref:" not in out


def test_all_pools_even_when_it_matches_one_page(tmp_path, capsys):
    """The shape follows what was asked for, not what the store happened to hold.

    A sweep whose output changed schema on the day the corpus held one matching
    page would be a trap with a long fuse.
    """
    _alto(tmp_path, "gt/ocr", "1-048")
    code, out, _err = _run(capsys, "ocr", "lines", "--all", "--store", "gt",
                     "--root", str(tmp_path))
    assert code == 0
    assert out.splitlines()[0].startswith("[2]{ref,")


def test_a_scalar_list_field_is_joined_into_the_cell(capsys):
    """A list of bare strings joins with spaces rather than getting its own table.

    The convention `corrections`' `pages` and `marks`' `refs` already use: a table
    of one unnamed column is worse than a string, and a raw list in a cell would
    degrade the row either way.
    """
    from argparse import Namespace

    from harness.cli._common import out_per_ref

    out_per_ref(Namespace(json=False),
                [("1-048", {"n": 1, "hits": []}),
                 ("1-049", {"n": 2, "hits": ["x", "y"]})])
    out = capsys.readouterr().out
    assert "[2]{ref,n,hits}" in out
    assert "1-049,2,x y" in out
    assert "# hits" not in out


def test_a_report_with_list_fields_splits_into_tables(tmp_path, capsys):
    """Counts in the row, each list its own ref-keyed table.

    A count is not a summary standing in for the detail — the detail follows,
    keyed by ref, so nothing is lost and the row stays scannable.
    """
    from argparse import Namespace

    from harness.cli._common import out_per_ref

    out_per_ref(Namespace(json=False),
                       [("1-048", {"n": 1, "hits": []}),
                        ("1-049", {"n": 2, "hits": [{"line": 3}]})])
    out = capsys.readouterr().out
    assert "[2]{ref,n,hits}" in out            # the counts row
    assert "1-049,2,1" in out
    assert "# hits" in out                     # the detail, under its own heading
    assert "[1]{ref,line}" in out


def test_a_list_field_absent_from_the_first_page_is_still_split(capsys):
    """The field set is decided over every payload, never `pairs[0]`.

    It used to be read off the first, so a field that only appeared later reached
    `_pool` unsplit and tripped its list guard — after every page had been
    computed, which is the worst moment for a report to fail.
    """
    from argparse import Namespace

    from harness.cli._common import out_per_ref

    out_per_ref(Namespace(json=False),
                [("1-048", {"n": 1}),
                 ("1-049", {"n": 2, "hits": [{"line": 3}]})])
    out = capsys.readouterr().out
    assert "# hits" in out
    assert "[1]{ref,line}" in out


def test_sub_tables_follow_field_order_not_set_iteration(capsys):
    """`# field` blocks come out in the record's own order, every run.

    They were collected into a `set`, and Python randomises string hashing per
    process — so the blocks of one unchanged command reordered between runs. The
    same hazard the train-zones skill records for `--resize`'s class map, where it permuted
    every label in the model.
    """
    from argparse import Namespace

    from harness.cli._common import out_per_ref

    keys = ["zulu", "alpha", "mike", "bravo"]
    out_per_ref(Namespace(json=False),
                [("1-048", {k: [{"i": 1}] for k in keys}),
                 ("1-049", {k: [{"i": 2}] for k in keys})])
    out = capsys.readouterr().out
    assert [ln[2:] for ln in out.splitlines() if ln.startswith("# ")] == keys


def test_proposal_check_pools_across_refs(tmp_path, capsys):
    """Its six detectors share one key set, so several pages make one table.

    They did not: each named its own fields (`context`, `detail`, `in_text`,
    `in_text_not_resolved`, `explained`), which made the list ragged. TOON drops a
    ragged record list to the verbose nested form silently, and where a field held
    a list the emitter refused outright — so naming two pages failed after all the
    work was done. Fixed at the source; this pins that it stays fixed.
    """
    for ref, text in (("1-048", "dances.¹ The woman"), ("1-049", "Ye'rgɪn")):
        d = tmp_path / "review" / ref
        d.mkdir(parents=True)
        (d / "proposal.json").write_text(json.dumps(
            {"lines": {"1": {"text": text, "resolved": ""}}}), encoding="utf-8")
    code, out, _err = _run(capsys, "proposal", "check", "1-048", "1-049",
                           "--root", str(tmp_path))
    # Both pages carry a defect, so the gate fires. Three of the four findings
    # are defects; the bare suffix is an advisory and would not have gated alone.
    assert code == 1
    # Four findings from four different detectors — footnote (page-level),
    # apostrophe, bare suffix, notation-with-no-resolved — under one header.
    assert out.splitlines()[0].endswith(
        "{ref,line,issue,severity,token,context,detail}:"), out
    assert "- ref:" not in out                         # never the nested form


# --------------------------------------------------------------- the refusals

def test_a_bad_ref_refuses_before_anything_is_emitted(tmp_path, capsys):
    """Format is checked for every ref up front, so a mid-list typo costs nothing.

    `ocr review` had a pre-pass of its own for exactly this reason — a refusal
    arriving after pages of reassuring output is where it is least likely to be
    read — and `page_refs` now gives every action the same guarantee.
    """
    _alto(tmp_path, "gt/ocr", "1-048")
    code, out, _err = _run(capsys, "ocr", "lines", "1-048", "48", "--store", "gt",
                     "--root", str(tmp_path))
    assert code == 2
    assert out == ""


def test_refs_and_all_together_are_a_usage_error(tmp_path, capsys):
    _alto(tmp_path, "gt/ocr", "1-048")
    code, _out, err = _run(capsys, "ocr", "lines", "1-048", "--all", "--store", "gt",
                   "--root", str(tmp_path))
    assert code == 2


def test_naming_nothing_is_a_usage_error_that_says_all(tmp_path, capsys):
    """The sweep-by-omission this pass removed. Bare `zones check` walked 832
    pages and nothing at the call site said so."""
    code, _out, err = _run(capsys, "ocr", "lines", "--store", "gt", "--root", str(tmp_path))
    assert code == 2
    assert "--all" in err


def test_a_per_page_flag_refuses_a_second_ref(tmp_path, capsys):
    """`--out` is why this exists: nothing errored before, the second page simply
    overwrote the first's images in the named directory."""
    for ref in ("1-048", "1-049"):
        _alto(tmp_path, "gt/ocr", ref)
    code, _out, err = _run(capsys, "proposal", "codepoints", "1-048", "1-049", "22",
                           "--root", str(tmp_path))
    assert code == 2

    # `ocr sheets` takes the line selection positionally now, so a second ref there
    # is not a second page — it is a token that would otherwise be read as a line
    # range, and `1-049` would silently mean lines 1 through 49 of `1-048`.
    code, _out, err = _run(capsys, "ocr", "sheets", "1-048", "1-049", "--store", "gt",
                   "--out", str(tmp_path / "x"), "--root", str(tmp_path))
    assert code == 2
    assert "one ref at a time" in err


def test_path_refuses_a_second_ref(tmp_path, capsys):
    for ref in ("1-048", "1-049"):
        _proposal(tmp_path, ref)
    code, _out, err = _run(capsys, "proposal", "check", "1-048", "1-049",
                   "--path", str(tmp_path / "review" / "1-048" / "proposal.json"),
                   "--root", str(tmp_path))
    assert code == 2


# -------------------------------------------------------------- the exit code

def test_exit_is_the_worst_across_refs(tmp_path, capsys):
    """One dirty page fails the batch, or a batch would launder a failure."""
    _proposal(tmp_path, "1-048", texts=("clean text",))
    _proposal(tmp_path, "1-049", texts=("has an ' apostrophe",))
    clean, _o1, _e1 = _run(capsys, "proposal", "check", "1-048", "--root", str(tmp_path))
    dirty, _o2, _e2 = _run(capsys, "proposal", "check", "1-049", "--root", str(tmp_path))
    both, _o3, _e3 = _run(capsys, "proposal", "check", "1-048", "1-049",
                   "--root", str(tmp_path))
    assert (clean, dirty) == (0, 1)
    assert both == 1


# ------------------------------------------------- what the sweep must not do

def test_a_named_exempt_page_still_predicts(tmp_path):
    """`predict_skip`'s `single` has to travel into the sweep.

    Naming a ref means *that page* even where a human ruled it not a text page.
    Several named refs route through `predict_all` so the models load once — and
    without `named=` the override is lost, so the very command that named a plate
    would drop it in silence.
    """
    from harness import zones as Z

    (tmp_path / "gt" / "zones").mkdir(parents=True)
    (tmp_path / "gt" / "zones" / "_exempt.lst").write_text(
        "gt/zones/chukchi-1-048.xml\n", encoding="utf-8")
    splits = Z.load_splits(tmp_path)
    assert splits.get("1-048") == "exempt"

    # The sweep's default holds the ruling; a named ref overrides it. Both go
    # through one function, which is the point — a client deciding for itself
    # would be a second copy of the rule.
    assert Z.predict_skip("1-048", tmp_path, splits=splits) == \
        "ruled not a text page"
    assert Z.predict_skip("1-048", tmp_path, splits=splits, single=True) != \
        "ruled not a text page"


def test_restore_skips_a_page_whose_ground_truth_is_newer(tmp_path):
    """The mtime test `--all` needs, and what `--force` means beside it.

    `restore` refuses a target already holding text unless `force`, which is right
    for a named page and would refuse the entire store in a sweep. So the sweep
    asks the sharper question — is this decision newer than the ground truth it
    produced — and `--force` means ignore even that.
    """
    import os

    from harness.review import restore_skip

    dec = tmp_path / "review" / "1-048" / "decision.json"
    dec.parent.mkdir(parents=True)
    dec.write_text("{}", encoding="utf-8")
    gt = tmp_path / "gt" / "ocr" / "chukchi-1-048.xml"
    gt.parent.mkdir(parents=True)
    gt.write_text("<alto/>", encoding="utf-8")

    os.utime(gt, (2_000_000_000, 2_000_000_000))      # gt newer than the decision
    assert restore_skip("1-048", tmp_path) == \
        "ground truth is already newer than the decision"
    assert restore_skip("1-048", tmp_path, force=True) == ""

    os.utime(dec, (2_100_000_000, 2_100_000_000))     # re-adjudicated since
    assert restore_skip("1-048", tmp_path) == ""


def test_restore_skip_is_silent_about_a_page_with_no_decision(tmp_path):
    """Not an error — a page nobody has adjudicated is simply not in the sweep."""
    from harness.review import restore_skip

    assert restore_skip("1-048", tmp_path) == "no decisions"


# ------------------------------------------------ the mixed positional list

def test_normalize_takes_refs_and_paths_in_one_list(tmp_path, capsys):
    """A `PP-NNN` ref or a path, and the two never collide: a ref's shape is
    closed, so anything that will not parse as one is taken as given."""
    _alto(tmp_path, "gt/ocr", "1-048")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "readings.md").write_text("plain\n", encoding="utf-8")
    code, out, _err = _run(capsys, "corpus", "normalize", "1-048", "data/readings.md",
                     "--root", str(tmp_path))
    assert code == 0
    assert "files: 2" in out


def test_normalize_scopes_a_named_ref_to_its_own_proposal(tmp_path, capsys):
    """**A named ref covers `proposal.json` where `--all` does not.**

    The corpus sweep excludes proposals on purpose: one for an already-restored
    page accumulates apostrophe hits that can never be resolved, so it would be
    permanent noise in a corpus-wide gate. Naming the page is the same explicit
    act `--path review/PP-NNN/proposal.json` was, so the mid-pass protection for
    a proposal being authored survives the change. Pinned in both directions,
    since either read alone looks like an inconsistency worth tidying.
    """
    _proposal(tmp_path, "1-048")
    named, out_named, _en = _run(capsys, "corpus", "normalize", "1-048",
                            "--root", str(tmp_path))
    swept, out_swept, _es = _run(capsys, "corpus", "normalize", "--all",
                            "--root", str(tmp_path))
    assert (named, swept) == (0, 0)
    assert "files: 1" in out_named
    assert "files: 0" in out_swept
