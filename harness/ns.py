"""XML namespace URIs, once.

`TEI_NS` was declared identically in eight modules, `XML_LANG` and `XML_ID` in
three each — one of those inside a function body — and `ALTO_NS` in two, plus
twenty-two more copies across the tests. None of them can drift into being
*wrong*, since a mistyped URI fails loudly on the first XPath; what they cost is
that the set of names a reader has to recognise grows with the file count, and a
new module's author copies whichever one they happened to be looking at.

**Imports nothing from this package**, like `atomic.py`, `refs.py` and `mets.py`,
and for the same reason: the obvious home for something everything needs was
`context.py`, which sat in ten of the package's nineteen mutual import cycles, so
a constant living beside it arrived through a function-body import at each call
site. `refs.py` is that argument turned on `context.py` itself — the ref
primitives are a leaf now, and the package is down to ten cycles with `context`
in one. `test_leaf_modules.py` enforces the claim rather than restating it.

Not a general "constants" module. Namespace URIs are external identifiers fixed
by somebody else's standard — the one class of value that is genuinely the same
fact everywhere it appears. The project's own rule that a fact stated twice is a
defect is about *judgements*, and the lookalike tables are the standing reminder
that two similar-looking tables can be two different scopes.
"""
from __future__ import annotations

#: TEI P5.
TEI_NS = "http://www.tei-c.org/ns/1.0"

#: ALTO 4.2, the dialect eScriptorium exports and every store here speaks.
ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"

#: The XML namespace itself, for `@xml:lang` and `@xml:id`.
XML_NS = "http://www.w3.org/XML/1998/namespace"

XML_LANG = f"{{{XML_NS}}}lang"
XML_ID = f"{{{XML_NS}}}id"
