"""The entity store is read once per `tei validate` run, not twice per page.

`build_context` loads it for `entity_hits` and `validate` loads it again to
resolve `@ref`, at **29ms** a read over 461 files. Profiling 20 pages through
the real handler: **193 ms/page before, 143 after** — 50 ms/page, 33s across the
663-page corpus, and the store was the largest remaining per-page cost once A1
had hoisted the lexicon index.

**One parameter, not four.** The item this came from left the choice open
between four caller-supplied reads and one bundle. Measured, the question
answers itself: `entities.load` is 29.34ms, and `alias_index` (0.32ms),
`auto_forms` (0.09ms), `apparatus.sigla` (0.90ms), `authority_names` (0.83ms)
and `load_toc` (0.65ms) are 2.4ms between them. Four more parameters would buy
under 8% of what one buys, against the house rule of one meaning per name.

**Why this is not the `tier1_terms` case.** That one is re-read from `gt/ocr/`
deliberately and must never come out of `ctx`: the pass authored the TEI *from*
`ctx`, so checking one against the other would make the two witnesses one. The
entity store is the reference identity resolves *against*, not anything the pass
produced, and both call sites read the same files moments apart. Hoisting shares
an input; it does not merge a comparison — which is why the tests below check
that the verdict is unchanged rather than merely that the read happened once.
"""
from __future__ import annotations

from pathlib import Path

import pytest

TEI_NS = "http://www.tei-c.org/ns/1.0"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    d = tmp_path / "edition" / "entities" / "place"
    d.mkdir(parents=True)
    (d / "mariinsky-post.md").write_text(
        "# place:mariinsky-post — Mariinsky Post\n\n"
        "- status: ratified\n\n"
        "## aliases\n\n"
        "| form | lang | auto | note |\n"
        "|---|---|---|---|\n"
        "| Mariinsky Post | | yes | |\n",
        encoding="utf-8")
    # `entity_hits` checks for the page's ground truth *before* it loads the
    # store and returns `[]` if it is absent — so without this the load never
    # happens and a spy counting zero would look like the hoist working.
    g = tmp_path / "gt" / "ocr"
    g.mkdir(parents=True)
    (g / "chukchi-1-151.xml").write_text(
        '<alto xmlns="http://www.loc.gov/standards/alto/ns-v4#"><Layout><Page>'
        '<PrintSpace><TextBlock ID="r1" TAGREFS="T1" HPOS="100" VPOS="100" '
        'WIDTH="800" HEIGHT="40"><TextLine ID="l1" HPOS="100" VPOS="100" '
        'WIDTH="800" HEIGHT="40">'
        '<String CONTENT="The party reached Mariinsky Post that winter."/>'
        "</TextLine></TextBlock></PrintSpace></Page></Layout>"
        '<Tags><OtherTag ID="T1" TYPE="type" LABEL="MainZone-P"/></Tags>'
        "</alto>", encoding="utf-8")
    return tmp_path


def _page(repo: Path, body: str) -> Path:
    p = repo / "tei" / "chukchi-1-151.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f'<TEI xmlns="{TEI_NS}"><teiHeader/><text><body><p>{body}</p>'
                 "</body></text></TEI>", encoding="utf-8")
    return p


def _count_loads(monkeypatch) -> list[int]:
    """Record every entity-store glob-and-parse.

    **Patched at both bound names, and the second one is not optional.**
    `validate.py:26` imports `load` at module scope, so patching
    `harness.entities.load` alone never reaches it, while `context.entity_hits`
    imports it inside the function body and does. Two resolution paths; a spy on
    one reads zero and looks like a pass. The same trap ate the first version of
    `test_tier1_index_cost.py`, from the other side.
    """
    import harness.entities as E
    import harness.validate as V

    loads: list[int] = []
    real = E.load

    def spy(root=Path(".")):
        loads.append(1)
        return real(root)

    monkeypatch.setattr(E, "load", spy)
    monkeypatch.setattr(V, "load", spy)
    return loads


class TestValidateTakesASuppliedStore:
    def test_it_loads_nothing_when_handed_one(self, repo, monkeypatch):
        from harness.entities import load
        from harness.validate import validate

        store = load(repo)
        page = _page(repo, "The party reached Mariinsky Post that winter.")
        loads = _count_loads(monkeypatch)
        validate(page, {"page_ref": "1-151", "root": str(repo)}, store=store)
        assert loads == []

    def test_it_loads_one_when_handed_none(self, repo, monkeypatch):
        """Guard on the guard: if this is also zero the spy is not wired up."""
        from harness.validate import validate

        page = _page(repo, "The party reached Mariinsky Post that winter.")
        loads = _count_loads(monkeypatch)
        validate(page, {"page_ref": "1-151", "root": str(repo)})
        assert len(loads) == 1

    def test_the_verdict_does_not_depend_on_where_the_store_came_from(self, repo):
        """The property that matters. An unmarked proper noun the store claims
        is a finding either way — the hoist moves a read, never a judgement."""
        from harness.entities import load
        from harness.validate import validate

        page = _page(repo, "The party reached Mariinsky Post that winter.")
        ctx = {"page_ref": "1-151", "root": str(repo)}
        a = validate(page, ctx, store=load(repo))
        b = validate(page, ctx)
        assert (a.errors, a.warnings, a.worklist) == \
               (b.errors, b.warnings, b.worklist)
        assert a.metrics == b.metrics

    def test_a_supplied_store_is_not_remembered(self, repo):
        """A hoist, not a cache. An entity minted after the first call is seen by
        the next one that supplies nothing."""
        from harness.validate import validate

        page = _page(repo, "The party reached Mariinsky Post that winter.")
        ctx = {"page_ref": "1-151", "root": str(repo)}
        first = validate(page, ctx).metrics["entity_refs"]
        (repo / "edition" / "entities" / "place" / "anadyr.md").write_text(
            "# place:anadyr — Anadyr\n\n- status: ratified\n\n## aliases\n\n"
            "| form | lang | auto | note |\n|---|---|---|---|\n"
            "| Anadyr | | yes | |\n", encoding="utf-8")
        assert validate(page, ctx).metrics["entity_refs"] == first


class TestBuildContextTakesOneToo:
    def test_entity_hits_uses_the_supplied_store(self, repo, monkeypatch):
        from harness.context import entity_hits
        from harness.entities import load

        store = load(repo)
        loads = _count_loads(monkeypatch)
        entity_hits("1-151", repo, store)
        assert loads == []

    def test_entity_hits_loads_one_without(self, repo, monkeypatch):
        from harness.context import entity_hits

        loads = _count_loads(monkeypatch)
        entity_hits("1-151", repo)
        assert len(loads) == 1
