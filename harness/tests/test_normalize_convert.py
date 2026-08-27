"""`corpus normalize --convert`'s structure gate, and the hole it had in it.

`convert` writes to `gt/` and `tei/` unattended, which it is allowed to do
because two checks stand behind it: a read-back, and a structure comparison
across the rewrite. The structure check is the load-bearing one — the read-back
proves the bytes landed, never that they still mean what they meant.

`shape_before is None` meant two different things: this suffix has no structure
check, or **this file did not parse**. The gate was guarded on that value, so a
file in the second class was rewritten with the check silently not running —
the one file class where a rewrite is least distinguishable from a corruption.

These tests hold both sides. The refusal must fire on an unparseable file with a
declared shape, and it must *not* fire on a suffix that legitimately has no
shape check — `config/lexicon_extra.txt` and `edition/entities/*/*.md` are in the sweep
and neither parses as anything.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.normalize import convert

#: Precomposed, so NFD changes the bytes and the file is a conversion candidate.
#: Without this every fixture below is skipped at the `after == before` guard and
#: the whole module passes having exercised nothing.
PRECOMPOSED = "café"


def _write(root: Path, rel: str, text: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path


class TestTheRefusal:

    def test_unparseable_xml_is_refused_and_left_alone(self, root):
        p = _write(root, "gt/ocr/chukchi-1-001.xml", f"<alto><nope {PRECOMPOSED}")
        before = p.read_text(encoding="utf-8")

        out = convert(root)

        assert out["changed"] == []
        assert len(out["failed"]) == 1
        assert "REFUSED" in out["failed"][0]["note"]
        assert "XML" in out["failed"][0]["note"]
        assert p.read_text(encoding="utf-8") == before, "refused, so untouched"

    def test_unparseable_json_is_refused_and_left_alone(self, root):
        p = _write(root, "edition/toc.json", '{"a": "' + PRECOMPOSED + '"')
        before = p.read_text(encoding="utf-8")

        out = convert(root)

        assert out["changed"] == []
        assert len(out["failed"]) == 1
        assert "REFUSED" in out["failed"][0]["note"]
        assert p.read_text(encoding="utf-8") == before

    def test_the_refusal_names_the_file(self, root):
        _write(root, "gt/ocr/chukchi-1-001.xml", f"<alto><nope {PRECOMPOSED}")
        out = convert(root)
        assert out["failed"][0]["path"] == "gt/ocr/chukchi-1-001.xml"

    def test_a_refusal_is_reported_in_dry_run_too(self, root):
        """A preview that showed a file as convertible and then refused it on the
        real run would be a preview of a different operation."""
        _write(root, "gt/ocr/chukchi-1-001.xml", f"<alto><nope {PRECOMPOSED}")
        out = convert(root, dry_run=True)
        assert out["changed"] == []
        assert len(out["failed"]) == 1


class TestTheRefusalDoesNotOverreach:
    """The fix must not turn "no check for this suffix" into a refusal."""

    def test_a_plain_text_file_still_converts(self, root):
        p = _write(root, "config/lexicon_extra.txt", PRECOMPOSED + "\n")

        out = convert(root)

        assert out["failed"] == []
        assert len(out["changed"]) == 1
        assert p.read_text(encoding="utf-8") == "café\n"

    def test_an_entity_markdown_file_still_converts(self, root):
        p = _write(root, "edition/entities/place/x.md", f"# x\n\n{PRECOMPOSED}\n")

        out = convert(root)

        assert out["failed"] == []
        assert len(out["changed"]) == 1
        assert "́" in p.read_text(encoding="utf-8")

    def test_parseable_xml_still_converts(self, root):
        p = _write(root, "gt/ocr/chukchi-1-001.xml",
                   f'<alto><String CONTENT="{PRECOMPOSED}"/></alto>')

        out = convert(root)

        assert out["failed"] == []
        assert len(out["changed"]) == 1
        assert "́" in p.read_text(encoding="utf-8")

    def test_json_that_parses_but_has_no_lines_key_still_converts(self, root):
        """The trap, and the reason the refusal cannot read `shape_before`.

        `_json_shape` answers `None` for **two** reasons — the file did not
        parse, or it parsed and holds no `lines` key. The second is every
        `data/*.json` but a decision, and is entirely ordinary. A refusal gated
        on `None` refuses all of them; `_xml_shape` has no such second case,
        which is exactly what makes the mistake easy to make from the XML side.
        """
        # `ensure_ascii=False`, or `json.dumps` escapes it to `caf\\u00e9` — pure
        # ASCII, NFD-invariant, and the file is skipped before any gate runs.
        p = _write(root, "edition/toc.json",
                   json.dumps({"a": PRECOMPOSED}, ensure_ascii=False))

        out = convert(root)

        assert out["failed"] == []
        assert len(out["changed"]) == 1
        assert "́" in p.read_text(encoding="utf-8")

    def test_a_lines_shaped_json_converts_and_is_shape_checked(self, root):
        """The case that *does* yield a shape, so the comparison really runs."""
        p = _write(root, "review/1-001/decision.json",
                   json.dumps({"ref": "1-001",
                               "lines": {"0": {"text": PRECOMPOSED}}},
                              ensure_ascii=False))

        out = convert(root)

        assert out["failed"] == []
        assert len(out["changed"]) == 1
        assert "́" in p.read_text(encoding="utf-8")
