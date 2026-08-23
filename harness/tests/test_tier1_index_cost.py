"""`tier1_terms` builds the lexicon index only when someone reads the column.

`lookup.index` walks every keyed page — `_restored_refs` parses them to find
them, then `native_corpus_context` parses them again — and measured **1.57s** on
the live corpus against ~3ms for everything else `tier1_terms` does. So the
`key` column is not part of the cost of this function, it *is* the cost.

Three of the four callers never read that column: `validate` takes `text`,
`expand` takes `index` and `text`, `generate` takes `line`. Only `build_context`
prints it, in the collator prompt. `tei validate` was therefore building the
whole index twice a page — once in `build_context`, once inside `validate`.

**Invisible in the output by construction**: the rows are byte-identical either
way but for the column, so only a test of what gets *built* can hold it. Same
method and the same guard-on-the-guard as `test_folio_fold.py`, one layer up.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"
REPO = Path(__file__).parent.parent.parent


@pytest.fixture
def page(tmp_path: Path) -> Path:
    """Ground truth carrying two Tier-1 forms, as `test_tier1_expand` builds it.

    With the real `data/marks_config.json` beside it, copied the way
    `test_lookup.py` does: without one `lookup.index` raises `MarksConfigError`,
    which `_with_keys` catches and turns into an empty column — so a tree
    lacking it would exercise the *refusal* path and prove nothing about what
    gets built.
    """
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "marks_config.json").write_text(
        (REPO / "data" / "marks_config.json").read_text(encoding="utf-8"),
        encoding="utf-8")
    p = tmp_path / "gt" / "ocr" / "chukchi-1-151.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f'<alto xmlns="{ALTO_NS}"><Layout><Page><PrintSpace>'
        '<TextBlock ID="r1" TAGREFS="T1"><TextLine ID="l1">'
        '<String CONTENT="the ringed seal is called kełiˊlın here"/>'
        "</TextLine>"
        '<TextLine ID="l2"><String CONTENT="and the bearded seal uˊᵋnel"/>'
        "</TextLine></TextBlock>"
        "</PrintSpace></Page></Layout>"
        '<Tags><OtherTag ID="T1" TYPE="type" LABEL="MainZone-P"/></Tags>'
        "</alto>", encoding="utf-8")
    # The read view, as `views build ocr` makes it: a symlink into the store that
    # holds the page. `tier1_terms` reads `gt/ocr/` directly and never needs it,
    # but `build_context` resolves the page through the view.
    view = tmp_path / "ocr"
    view.mkdir(parents=True, exist_ok=True)
    (view / p.name).symlink_to(Path("..") / "gt" / "ocr" / p.name)
    # `build_context` walks `scans/` for the page's neighbours. Only the names
    # are read here, so the rasters are empty — `farms.require` refuses an absent
    # tree outright, which is the check being satisfied rather than dodged.
    (tmp_path / "scans").mkdir(parents=True, exist_ok=True)
    for n in ("1-151", "1-152"):
        (tmp_path / "scans" / f"chukchi-{n}.png").write_bytes(b"")
    return tmp_path


def _count_index_builds(monkeypatch) -> list[int]:
    """Record every `lookup.index` build `context` triggers."""
    import harness.lookup as lk

    built: list[int] = []
    real = lk.index

    # `**kw` rather than the signature spelled out: this spy counts *builds*, and
    # the only thing it needs to be right about is that it forwards whatever it
    # was given. It named `exclude` alone and broke the moment `index` grew a
    # `tick`, which is a test failing on a parameter it has no opinion about.
    def spy(root, exclude=None, **kw):
        built.append(1)
        return real(root, exclude, **kw)

    monkeypatch.setattr(lk, "index", spy)
    return built


class TestTheColumnIsOptional:
    def test_the_rows_are_identical_but_for_the_key(self, page):
        from harness.context import tier1_terms
        with_ = tier1_terms("1-151", page)
        without = tier1_terms("1-151", page, keys=False)
        assert [{k: v for k, v in r.items() if k != "key"} for r in with_] == without
        assert without, "the fixture produced no terms — this test proves nothing"

    def test_the_column_is_absent_rather_than_empty(self, page):
        """`key: ""` is a claim — no key resolves back to this form — and a
        missing field is the absence of one. A consumer that wants a key it did
        not ask for should get a KeyError, not a false negative."""
        from harness.context import tier1_terms
        rows = tier1_terms("1-151", page, keys=False)
        assert all("key" not in r for r in rows)
        with pytest.raises(KeyError):
            _ = rows[0]["key"]

    def test_keys_true_still_carries_the_column(self, page):
        from harness.context import tier1_terms
        assert all("key" in r for r in tier1_terms("1-151", page))


class TestWhatGetsBuilt:
    def test_keys_false_builds_no_index_at_all(self, page, monkeypatch):
        from harness.context import tier1_terms
        built = _count_index_builds(monkeypatch)
        tier1_terms("1-151", page, keys=False)
        assert built == []

    def test_keys_true_builds_one(self, page, monkeypatch):
        """The guard on the guard: if this is also zero the spy is not wired up
        and the test above proves nothing."""
        from harness.context import tier1_terms
        built = _count_index_builds(monkeypatch)
        tier1_terms("1-151", page)
        assert len(built) == 1

    def test_a_supplied_index_is_used_rather_than_rebuilt(self, page, monkeypatch):
        from harness.context import tier1_terms
        from harness.lookup import index
        idx = index(page)
        built = _count_index_builds(monkeypatch)
        tier1_terms("1-151", page, idx=idx)
        assert built == []

    def test_a_supplied_index_gives_the_same_rows(self, page):
        from harness.context import tier1_terms
        from harness.lookup import index
        assert tier1_terms("1-151", page) == \
            tier1_terms("1-151", page, idx=index(page))

    def test_a_page_with_no_terms_builds_nothing(self, tmp_path, monkeypatch):
        """`_with_keys` returns early on an empty list, so eager construction in
        a caller would be a regression on exactly this page. It is why the CLI
        builds the index only for a batch of more than one ref."""
        from harness.context import tier1_terms
        built = _count_index_builds(monkeypatch)
        assert tier1_terms("1-151", tmp_path) == []
        assert built == []


class TestTheLoopHoistsIt:
    """The done-when this item was written against: a multi-page run builds the
    index once, not once a ref."""

    def test_build_context_takes_a_prebuilt_index(self, page, monkeypatch):
        from harness.context import build_context
        from harness.lookup import index
        idx = index(page)
        built = _count_index_builds(monkeypatch)
        ctx = build_context("1-151", page, idx=idx)
        assert built == []
        assert ctx["tier1_terms"], "no terms — the assertion above is vacuous"
        assert all("key" in t for t in ctx["tier1_terms"])

    def test_build_context_still_builds_one_when_given_none(self, page, monkeypatch):
        from harness.context import build_context
        built = _count_index_builds(monkeypatch)
        build_context("1-151", page)
        assert len(built) == 1

    def test_a_two_ref_validate_builds_it_once(self, page, monkeypatch):
        """Two refs through the real CLI handler. Before this item it was four
        builds — `build_context` and `validate` each rebuilding it per ref."""
        from types import SimpleNamespace

        from harness.cli._tei import run_validate

        src = page / "gt" / "ocr" / "chukchi-1-151.xml"
        for ref in ("1-151", "1-152"):
            name = f"chukchi-{ref}.xml"
            (page / "gt" / "ocr" / name).write_text(
                src.read_text(encoding="utf-8"), encoding="utf-8")
            link = page / "ocr" / name
            if not link.exists():
                link.symlink_to(Path("..") / "gt" / "ocr" / name)
            tei = page / "tei" / f"chukchi-{ref}.xml"
            tei.parent.mkdir(parents=True, exist_ok=True)
            tei.write_text(
                '<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader/><text>'
                "<body><p>plain English prose.</p></body></text></TEI>",
                encoding="utf-8")

        a = SimpleNamespace(root=page, ref=("1-151", "1-152"), all=False,
                            itinerary=None, ratified=False, schema=False,
                            json=False, toon=False, pager=False)
        built = _count_index_builds(monkeypatch)
        run_validate(a)
        assert len(built) == 1, f"built the index {len(built)} times, not once"


class TestValidateDoesNotRebuildIt:
    def test_validate_builds_no_index_for_its_adopted_set(self, page, monkeypatch):
        """The doubling this item removed: `validate` re-reads the store on
        purpose — reading the terms out of `ctx` would make the two witnesses
        one — but re-reading the *store* never needed the corpus-wide index."""
        from harness.validate import validate

        tei = page / "tei" / "chukchi-1-151.xml"
        tei.parent.mkdir(parents=True, exist_ok=True)
        tei.write_text(
            '<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader/><text><body>'
            "<p>plain English prose with no marked spans at all.</p>"
            "</body></text></TEI>", encoding="utf-8")
        ctx = {"page_ref": "1-151", "root": str(page)}
        built = _count_index_builds(monkeypatch)
        validate(tei, ctx)
        assert built == [], "validate rebuilt the lexicon index"
