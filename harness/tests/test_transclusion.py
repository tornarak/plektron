"""The reader's contract carries two files verbatim, and this is what keeps them so.

`keying_spec.md` and the reading checklist are copied into
`.claude/agents/groundtruth-reader.md` between markers, because a subagent's system
prompt is the only block its siblings can share and a `Read` of the spec costs ~5k
tokens per reader, per page, behind the turn that varies. But the spec cannot simply
*move* there: it binds the collation pass and the human keying track too.

So there are two copies, and what makes that tolerable is this file. The repo's rule
is not "never state a fact twice" — `VERBS.md` and the CLI tree are two statements of
one surface, held together by `test_cli_surface.py`. The rule is that two copies need
a **gate** between them, never a comment claiming they match. A reader keying against
a spec that drifted a month ago is exactly the failure this project is built to
avoid: the output would look right.

`harness ocr queue` re-syncs before every batch, so the drift window is one commit
wide. This is the check that the committed file is the one readers actually get.
"""

from pathlib import Path

import pytest

from harness.dispatch import AGENT, TRANSCLUDE, Unready, sync_transcludes
from harness.dispatch import COLLATE_AGENT as COLLATOR

REPO = Path(__file__).resolve().parent.parent.parent


def blocks(text: str) -> list[tuple[str, str]]:
    """Each `(source, body)` pair the markers delimit."""
    return [(m.group("src"),
             m.group(0).split("\n", 1)[1].rsplit("\n", 1)[0].strip("\n"))
            for m in TRANSCLUDE.finditer(text)]


# What each dispatched agent must carry. `keying_spec.md` is in both because it
# binds both passes — which is also why it cannot simply *move* into either file.
CARRIES = {
    AGENT: {"keying_spec.md",
            ".claude/skills/rebuild-groundtruth/checklist.md"},
    # **The collator carries nothing, and that is the finding.** It carried the
    # spec whole — 883 lines — from when the pass authored Tier-1 text out of a
    # plaintext draft. A rule copies the adjudicated form in now, `tei expand`
    # confirms it against `gt/ocr/` and `tei validate` gates it whole-token
    # against `tier1_terms`, so the glyphs are never the collator's to originate
    # and the inventory answered a question it is no longer asked. The reader
    # still keeps it: it reads glyphs off the raster, which is what the spec is
    # for.
    COLLATOR: set(),
}


@pytest.mark.parametrize("agent", sorted(CARRIES), ids=lambda p: p.name)
def test_each_agent_carries_the_texts_it_says_it_does(agent):
    """Named, so removing one is a failure rather than a quiet economy.

    The reader's body tells it not to open the spec because it already has it. If
    that block went missing, the instruction would send it into a page with no
    spec and nothing would say so. The collator's empty set is the same rule
    pointing the other way: it is refused the spec *and* carries none, so a copy
    reappearing here would be an unasked-for 883 lines nothing in its contract
    reads.
    """
    got = {src for src, _ in blocks((REPO / agent).read_text(encoding="utf-8"))}
    assert got == CARRIES[agent]


@pytest.mark.parametrize("agent,src",
                         [(a, s) for a, ss in sorted(CARRIES.items()) for s in sorted(ss)],
                         ids=lambda v: getattr(v, "name", v))
def test_every_transcluded_block_matches_its_source_byte_for_byte(agent, src):
    """The gate itself. Edit the source and this fails until a `queue` re-syncs.

    Byte-for-byte and not "substantially the same": the spec's content is
    codepoints, and a copy that differs by a combining mark is precisely the
    class of error the spec exists to prevent.

    **Two agents now carry `keying_spec.md`**, so one edit puts two files out of
    date and `agents sync --commit` is the way to catch both. `ocr queue` re-syncs
    only the reading agent and `tei queue` only the collator — a batch is dispatched
    from one contract, and rewriting the other on its way past would put an
    unrelated tracked file into the commit.
    """
    text = (REPO / agent).read_text(encoding="utf-8")
    body = dict(blocks(text))[src]
    assert body == (REPO / src).read_text(encoding="utf-8").strip("\n"), (
        f"{src} and its copy in {agent} disagree. Run `harness agents sync "
        "--commit` and commit the result.")


def test_sync_is_idempotent(tmp_path):
    """A second run must report nothing changed, or `queue` cries wolf on every
    batch and the message stops being read."""
    (tmp_path / "src.md").write_text("one\ntwo\n", encoding="utf-8")
    a = tmp_path / "agent.md"
    a.write_text("head\n<!-- transclude: src.md -->\n<!-- /transclude -->\ntail\n",
                 encoding="utf-8")
    assert sync_transcludes(tmp_path, Path("agent.md"))["updated"] == ["src.md"]
    assert sync_transcludes(tmp_path, Path("agent.md"))["updated"] == []
    assert "one\ntwo" in a.read_text(encoding="utf-8")


def test_sync_replaces_a_stale_block_rather_than_appending(tmp_path):
    (tmp_path / "src.md").write_text("new\n", encoding="utf-8")
    a = tmp_path / "agent.md"
    a.write_text("<!-- transclude: src.md -->\nold\n<!-- /transclude -->\n",
                 encoding="utf-8")
    sync_transcludes(tmp_path, Path("agent.md"))
    text = a.read_text(encoding="utf-8")
    assert "old" not in text and text.count("new") == 1


def test_text_outside_the_markers_is_untouched(tmp_path):
    """Most of the agent file is authored prose. A sync that reflowed it would
    be rewriting the contract rather than refreshing a copy of one."""
    (tmp_path / "src.md").write_text("body\n", encoding="utf-8")
    a = tmp_path / "agent.md"
    a.write_text("BEFORE\n<!-- transclude: src.md -->\n<!-- /transclude -->\nAFTER\n",
                 encoding="utf-8")
    sync_transcludes(tmp_path, Path("agent.md"))
    text = a.read_text(encoding="utf-8")
    assert text.startswith("BEFORE\n") and text.endswith("AFTER\n")


def test_a_missing_source_is_named_not_skipped(tmp_path):
    """A block whose source is gone is a contract with a hole in it, not a stale
    copy to leave alone — and leaving it alone is what would ship it."""
    a = tmp_path / "agent.md"
    a.write_text("<!-- transclude: gone.md -->\nstale\n<!-- /transclude -->\n",
                 encoding="utf-8")
    with pytest.raises(Unready, match="gone.md"):
        sync_transcludes(tmp_path, Path("agent.md"))


def test_an_agent_file_with_no_markers_is_a_no_op(tmp_path):
    a = tmp_path / "agent.md"
    a.write_text("nothing to do here\n", encoding="utf-8")
    assert sync_transcludes(tmp_path, Path("agent.md"))["updated"] == []
    assert a.read_text(encoding="utf-8") == "nothing to do here\n"
