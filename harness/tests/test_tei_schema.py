"""Conformance: is what this project writes actually TEI?

`validate.py` checks the edition's own rules, and every one of them is
expressible in conformant TEI — so a page could satisfy all of them while using
an attribute TEI has never defined, and nothing would say so. docs/open-questions.md listed
nine attribute usages nobody checked; the whole surface was held in place by a
skill's prose.

**One test here pays libxml2's ~17 s `tei_all` compile, deliberately.** The
plumbing below (caching, the header wrapper, the missing-schema refusal) is
tested against a two-line stand-in grammar, because none of it is about TEI. But
`test_the_constructs_this_project_writes_are_conformant` uses the real schema and
must: a conformance test against a fake schema proves nothing about conformance.
It is also the regression net that matters while the encoding is still being torn
up and redone — it is what turns "we invented an attribute" from a discovery made
a hundred pages later into a failure made now.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from lxml import etree

N = "http://www.tei-c.org/ns/1.0"

# A minimal page: real header skeleton, body swapped per case.
PAGE = (f'<TEI xmlns="{N}"><teiHeader><fileDesc>'
        "<titleStmt><title>t</title></titleStmt>"
        "<publicationStmt><p>p</p></publicationStmt>"
        "<sourceDesc><p>s</p></sourceDesc>"
        "</fileDesc></teiHeader><text><body>%s</body></text></TEI>")

# Every construct docs/open-questions.md names as unchecked, plus the ones the collation skill
# tells the pass to write. If TEI stops accepting one of these, that is a finding.
CONSTRUCTS = [
    ("plain paragraph", "<p>x</p>"),
    ("pb + milestone", '<pb n="115"/><milestone unit="chapter" n="chVI"/><p>x</p>'),
    ("@part on a seam element", '<p part="I">x</p>'),
    ("@prev pointer", '<p prev="#p-1-100-1">x</p>'),
    ("footnote", '<p>x<note place="bottom" n="1">y</note></p>'),
    ("Tier-1 span with a rank", '<p><foreign xml:lang="ckt" resp="#llm">x</foreign></p>'),
    ("unclear letterform", '<p><unclear xml:lang="ckt" resp="#llm" reason="lf">x</unclear></p>'),
    ("@cert beside @resp",
     '<p><foreign xml:lang="ckt" cert="low" resp="#llm">x</foreign></p>'),
    ("typed proper name", '<p><name xml:lang="ckt" type="mythonym" resp="#llm">K</name></p>'),
    ("figure anchored by printed number", '<p>see <figure n="87"/> here</p>'),
    ("gloss @type", '<p><gloss type="literal">x</gloss></p>'),
    ("gloss list, supplied head, list-valued @target",
     '<list type="gloss" xml:id="list-1-100-1" next="#list-1-101-1">'
     '<head><supplied reason="context" resp="#llm">of a reindeer</supplied></head>'
     '<item><term xml:id="term-1-100-1">a</term>'
     '<gloss target="#term-1-100-1 #term-1-100-2" type="etymon">b</gloss></item></list>'),
]


@pytest.fixture(scope="module")
def real_root() -> Path:
    """The repo itself — the committed schema is the artifact under test."""
    root = Path(__file__).resolve().parents[2]
    if not (root / "data" / "tei_all.rng").exists():
        pytest.skip("committed schema absent")
    return root


def test_the_constructs_this_project_writes_are_conformant(real_root):
    """The regression net. Each of these is markup the collation skill mandates."""
    from harness.schema import check
    bad = []
    for label, body in CONSTRUCTS:
        errs = check(etree.ElementTree(etree.fromstring((PAGE % body).encode())),
                     real_root)
        if errs:
            bad.append(f"{label}: {errs[0]}")
    assert bad == []


def test_an_invented_attribute_is_rejected(real_root):
    """The thing no project rule can see.

    `provenance="uncertain"` was a real proposal for marking an unratified Tier-1
    reading, and it is not a TEI attribute — `@cert` and `@resp` are. Inventing
    one forecloses ever validating the corpus, which is the door this keeps open.
    """
    from harness.schema import check
    doc = etree.ElementTree(etree.fromstring(
        (PAGE % '<p><foreign xml:lang="ckt" provenance="uncertain">x</foreign></p>'
         ).encode()))
    assert any("provenance" in e for e in check(doc, real_root))


def test_an_unexpanded_handle_is_not_conformant_either(real_root):
    """`index=` is not a TEI attribute, which is exactly why it is a usable
    marker for "this page never went through `harness tei expand`" — the state is
    detectable by the grammar as well as by the project gate, and both name the
    same missing step. Run the schema check *after* expand."""
    from harness.schema import check
    doc = etree.ElementTree(etree.fromstring(
        (PAGE % '<p><foreign xml:lang="ckt" index="7"/></p>').encode()))
    assert any("index" in e for e in check(doc, real_root))


def test_a_committed_page_validates_standalone(real_root):
    """The open-questions record (once CLAUDE.md itself) said for a long time that a page file is a fragment and will not
    validate standalone. That is true of `tei/corpus-header.xml`, a bare
    `<teiHeader>`, and false of every page — which has a real `<TEI>` root and a
    minimal but structurally complete header."""
    from harness.schema import check
    page = real_root / "tei" / "chukchi-1-151.xml"
    if not page.exists():
        pytest.skip("no collated page")
    assert check(etree.parse(str(page)), real_root) == []


def test_the_corpus_header_is_checked_through_a_wrapper_that_does_not_mutate_it(
        real_root):
    """`teiCorpus` requires a `TEI` child, so a bare header has no conformant
    container and none is written to disk — inventing one would settle the
    assembly scheme by accident. The wrapper is built in memory from a deep copy;
    appending the caller's element directly would reparent it, silently.
    """
    from harness.schema import check_header
    path = real_root / "tei" / "corpus-header.xml"
    if not path.exists():
        pytest.skip("no corpus header")
    tree = etree.parse(str(path))
    header = tree.getroot()
    assert check_header(header, real_root) == []
    assert header.getparent() is None
    assert tree.getroot() is header


# --- plumbing, against a stand-in grammar -----------------------------------

TINY = """<grammar xmlns="http://relaxng.org/ns/structure/1.0"
  ns="http://www.tei-c.org/ns/1.0">
  <start><element name="TEI"><text/></element></start>
</grammar>"""


def _tiny_root(tmp_path: Path) -> Path:
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "tei_all.rng").write_text(TINY, encoding="utf-8")
    return tmp_path


def test_a_missing_schema_refuses_rather_than_passing(tmp_path):
    """A conformance gate that skips when its schema is absent reports a PASS
    meaning nothing was checked — the fluent-nonsense shape, in the one place
    whose entire job is to be a check."""
    from harness.schema import check
    with pytest.raises(FileNotFoundError, match="no TEI schema"):
        check(etree.ElementTree(etree.Element("x")), tmp_path)


def test_the_compiled_schema_is_cached_per_root(tmp_path):
    """The compile is ~17 s and the check is ~0.3 ms, so a corpus sweep must pay
    it once. Asserted by identity rather than by timing."""
    from harness import schema
    root = _tiny_root(tmp_path)
    schema._cache.clear()
    first = schema.load(root)
    assert schema.load(root) is first


def test_errors_name_the_line_and_say_what_kind_of_failure_it_is(tmp_path):
    """Prefixed, because a conformance failure is a different statement from a
    project-rule failure and they land in one list."""
    from harness.schema import check
    root = _tiny_root(tmp_path)
    errs = check(etree.ElementTree(etree.Element("nope")), root)
    assert errs and errs[0].startswith("not conformant TEI at line ")


def test_the_library_gate_leaves_the_schema_off(tmp_path):
    """`validate()` defaults `schema=False` and the CLI turns it on. Otherwise
    every one of the suite's hundreds of calls would pay the compile."""
    import inspect

    from harness.validate import check_corpus_header, validate
    assert inspect.signature(validate).parameters["schema"].default is False
    assert inspect.signature(
        check_corpus_header).parameters["schema"].default is False
