"""Is this actually TEI? — the conformance check, against a committed schema.

`validate.py` checks *project* rules: that a Tier-1 span declares a `@resp` rank,
that a `<figure>` names a number the page prints, that no whitespace precedes a
`<note>`. Every one of those is a statement about this edition, and a file can
satisfy all of them while using an attribute TEI has never defined. Nothing saw
that until now — CLAUDE.md listed nine attribute usages nobody checked, and the
whole surface was held in place by the collation skill's prose.

**What it catches, concretely.** A hand-written `provenance="uncertain"` on
`<foreign>` is rejected; so is `version="stock"` on `<application>`, because
`teidata.versionNumber` is a pattern and "stock" does not match it — which is a
real defect this found in `tei/corpus-header.xml` on its first run, after that
file had been read by hand more than once. Datatype and content-model errors are
the kind a reader's eye slides over and a grammar cannot.

**What it cannot catch**, and why `validate.py` does not shrink: every project
rule above is expressible in conformant TEI, so the schema is silent on all of
them. The two checks are complementary and neither subsumes the other.

**`tei_all`, deliberately, and not `tei_lite`.** The smaller customizations are
*subsets*: valid `tei_lite` is a strict subset of valid TEI, so a document this
project legitimately writes could be rejected by one. A gate that fails correct
input teaches a reader to ignore it, which is worse than no gate — the same
reasoning that removed the verbatim firewall and the `misordered` column.

**The cost is the compile, not the check.** libxml2 takes ~17 s to compile
`tei_all` (identically under `xmllint`, so it is the schema's size and not
lxml), and then validates a page in ~0.3 ms. So it is cached per process and a
corpus sweep pays it once: `tei validate --all` over 832 pages is ~17 s plus a
quarter of a second. Per page it is 17 s against a collation that took minutes,
which is why the CLI runs it by default and the library function does not — the
test suite would otherwise pay it on every call.

**A page file is a complete TEI document and validates standalone.** CLAUDE.md
said the opposite for a long time ("a page file is a fragment and will not
validate standalone"); that is true of `tei/corpus-header.xml`, which is a bare
`<teiHeader>`, and false of every page, which has a real `<TEI>` root and a
minimal but structurally complete header. The header is wrapped in a minimal
`<TEI>` in memory to be checked at all — never on disk, since inventing a
container there would settle the assembly scheme by accident.

**Run it after `harness tei expand`.** The `index=` handle the collation pass
writes is not a TEI attribute — that is the property that makes an unexpanded
page detectable — so a page still holding one fails here as well as in
`validate`. Both name the same missing step.
"""
from __future__ import annotations

import copy
from pathlib import Path

from lxml import etree

TEI_NS = "http://www.tei-c.org/ns/1.0"

# TEI P5 Version 4.12.0, revision 113e933e2, 2026-07-28, from
# https://www.tei-c.org/Vault/P5/4.12.0/ — committed rather than fetched, so the
# gate means the same thing on a fresh clone and after an upstream release. 1.1 MB.
SCHEMA = Path("data") / "tei_all.rng"

_cache: dict[Path, etree.RelaxNG] = {}


def load(root: Path = Path(".")) -> etree.RelaxNG:
    """The compiled schema, once per process per root.

    Raises rather than skipping if the file is absent: a conformance gate that
    silently passes when its schema is missing is the fluent-nonsense shape —
    a PASS that means nothing was checked.
    """
    path = (root / SCHEMA).resolve()
    if path not in _cache:
        if not path.exists():
            raise FileNotFoundError(
                f"no TEI schema at {path} — it is committed at {SCHEMA}; "
                "a conformance check with no schema would report a PASS that "
                "means nothing was checked")
        _cache[path] = etree.RelaxNG(etree.parse(str(path)))
    return _cache[path]


def _messages(rng: etree.RelaxNG, doc) -> list[str]:
    if rng.validate(doc):
        return []
    return [f"not conformant TEI at line {e.line}: {e.message}"
            for e in rng.error_log]


def check(doc, root: Path = Path(".")) -> list[str]:
    """Conformance errors for one parsed page, empty if it is valid TEI."""
    return _messages(load(root), doc)


def check_header(header, root: Path = Path(".")) -> list[str]:
    """Conformance errors for a bare `<teiHeader>`, wrapped to be checkable.

    `teiCorpus` requires at least one `TEI` child, so there is no conformant
    container for a header alone and none is written to disk. The wrapper is
    built here, in memory, from a deep copy — the caller's tree is never
    reparented, which lxml would otherwise do silently.
    """
    wrap = etree.Element(f"{{{TEI_NS}}}TEI")
    wrap.append(copy.deepcopy(header))
    text = etree.SubElement(wrap, f"{{{TEI_NS}}}text")
    body = etree.SubElement(text, f"{{{TEI_NS}}}body")
    etree.SubElement(body, f"{{{TEI_NS}}}p")
    return _messages(load(root), etree.ElementTree(wrap))
