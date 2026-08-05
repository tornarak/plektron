"""The reader's contract carries two files verbatim, and this is what keeps them so.

`keying_spec.md` and the reading checklist are copied into
`.claude/agents/groundtruth-reader.md` between markers, because a subagent's system
prompt is the only block its siblings can share and a `Read` of the spec costs ~15k
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

REPO = Path(__file__).resolve().parent.parent.parent


def blocks(text: str) -> list[tuple[str, str]]:
    """Each `(source, body)` pair the markers delimit."""
    return [(m.group("src"),
             m.group(0).split("\n", 1)[1].rsplit("\n", 1)[0].strip("\n"))
            for m in TRANSCLUDE.finditer(text)]


def test_the_agent_carries_the_two_texts_it_says_it_does():
    """Named, so removing one is a failure rather than a quiet economy.

    The body tells the reader not to open either file because it already has
    them. If a block went missing, that instruction would send readers into a
    page with no spec and nothing would say so.
    """
    got = {src for src, _ in blocks((REPO / AGENT).read_text(encoding="utf-8"))}
    assert got == {"keying_spec.md",
                   ".claude/skills/rebuild-groundtruth/checklist.md"}


@pytest.mark.parametrize("src", ["keying_spec.md",
                                 ".claude/skills/rebuild-groundtruth/checklist.md"])
def test_every_transcluded_block_matches_its_source_byte_for_byte(src):
    """The gate itself. Edit the source and this fails until `queue` re-syncs.

    Byte-for-byte and not "substantially the same": the spec's content is
    codepoints, and a copy that differs by a combining mark is precisely the
    class of error the spec exists to prevent.
    """
    text = (REPO / AGENT).read_text(encoding="utf-8")
    body = dict(blocks(text))[src]
    assert body == (REPO / src).read_text(encoding="utf-8").strip("\n"), (
        f"{src} and its copy in {AGENT} disagree. Run `harness ocr queue` (which "
        "re-syncs), or sync_transcludes(), and commit the result.")


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
