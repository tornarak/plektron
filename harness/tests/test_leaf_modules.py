"""The leaf modules import nothing from this package, and something checks.

Four modules say so in their own docstrings — `refs.py`, `ns.py`, `atomic.py`,
`mets.py` — and until now that was a claim in prose about a property nothing
looked at. It is the kind of claim that decays without a symptom: adding one
convenient import would not break a test, would not fail a lint, and would
quietly re-close the loop the module exists outside of.

**Why it matters here rather than as a tidiness rule.** `norm_ref` and
`parse_ref` are the two most-imported names in the harness, and they lived in
`context.py`, which sat in **10 of the package's 19 mutual import cycles**.
Every module that wanted to spell a page ref had to reach into the module that
assembles a whole collation prompt, and reach for it from inside a function body
to avoid closing a loop — which is where a large share of the package's
function-local imports came from. Moving them to a leaf took the count to 10
cycles and 1 involving `context`. A leaf that stops being a leaf gives that back.

`test_layout.py`'s `DERIVED`-against-`.gitignore` check is the precedent: a
property that is asserted in prose and enforceable by reading the tree should be
enforced by reading the tree.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

HARNESS = Path(__file__).resolve().parent.parent

#: Every module whose docstring promises it imports nothing from the package.
#: Adding one here is how a new leaf declares itself; the companion test below
#: refuses an entry that does not actually make the claim, so the list and the
#: prose cannot drift apart in either direction.
LEAVES = ("refs.py", "ns.py", "atomic.py", "mets.py", "train.py")

#: Modules that import **only leaves**, and so cannot join a cycle either — a
#: leaf's guarantee holds one level up for free, because a leaf has no edges to
#: come back along.
#:
#: `provenance.py` is here rather than in `LEAVES` because it needs `ALTO_NS` and
#: `TEI_NS`, and the alternative was to restate two namespace URIs it does not
#: own. A fact stated twice is the defect `CLAUDE.md` names; a second tier that
#: is still provably acyclic is not. The gate below is what keeps the tier from
#: becoming a place to put anything.
CANOPY = ("provenance.py", "layout.py")


def _package_imports(path: Path) -> list[str]:
    """Relative imports in one module: `from .x import y` and `from . import x`."""
    out = []
    for n in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(n, ast.ImportFrom) and n.level:
            out.append(n.module or ", ".join(a.name for a in n.names))
        elif isinstance(n, ast.Import):
            out += [a.name for a in n.names if a.name.startswith("harness.")]
    return out


@pytest.mark.parametrize("name", LEAVES)
def test_the_leaf_imports_nothing_from_the_package(name):
    """**Function bodies included.** A module-level check would pass on exactly
    the workaround this is guarding against: the deferred import inside a
    function is what a cycle looks like once someone has routed around it."""
    got = _package_imports(HARNESS / name)
    assert not got, (
        f"{name} imports {got} from this package. It is declared a leaf — its "
        "whole value is that it cannot join an import cycle, and one import is "
        "all that takes. Move what it needs into it, or move the caller out."
    )


@pytest.mark.parametrize("name", LEAVES)
def test_the_leaf_says_so_in_its_docstring(name):
    """The guard on the guard, in the other direction. A module listed here but
    silent about it would be held to a rule its own reader cannot see, and the
    next person to add an import would meet a failing test with no explanation
    in the file it names."""
    doc = ast.get_docstring(ast.parse((HARNESS / name).read_text(encoding="utf-8")))
    assert doc and "mports nothing from this package" in doc, (
        f"{name} is in LEAVES but does not say so in its docstring. The prose "
        "and the gate are two halves of one rule; a module cannot be held to a "
        "constraint it does not state."
    )


def test_no_module_claims_leafhood_without_being_listed():
    """The third direction: a docstring making the promise while nothing checks
    it is exactly the state this file was written to end, so a new module that
    copies the sentence is caught rather than trusted."""
    claimants = sorted(
        p.name for p in HARNESS.glob("*.py")
        if (d := ast.get_docstring(ast.parse(p.read_text(encoding="utf-8"))))
        and "mports nothing from this package" in d
    )
    declared = sorted(LEAVES + CANOPY)
    assert claimants == declared, (
        f"modules claiming leafhood: {claimants}, but LEAVES + CANOPY is "
        f"{declared}. A module that makes the promise must be checked against "
        "it — under one list or the other, since the canopy states the same "
        "constraint with one stated exception."
    )


@pytest.mark.parametrize("name", CANOPY)
def test_the_canopy_module_imports_only_leaves(name):
    """One level up from a leaf, and acyclic for the same reason.

    A module whose every package import is a leaf cannot be reached back into by
    what it imports, so it is as safe at module scope as a leaf is. The check is
    the same walk — function bodies included, since a deferred import is what a
    cycle looks like once someone has routed around it.
    """
    stems = {n.removesuffix(".py") for n in LEAVES}
    got = _package_imports(HARNESS / name)
    bad = [g for g in got if g.split(".")[0] not in stems]
    assert not bad, (
        f"{name} imports {bad}, which are not leaves. It is declared canopy — it "
        f"may import {sorted(stems)} and nothing else, because that is the whole "
        "of why its callers can take it at module scope."
    )


@pytest.mark.parametrize("name", CANOPY)
def test_the_canopy_module_says_so_in_its_docstring(name):
    """Same guard-on-the-guard as the leaves get: a module held to a constraint
    its own reader cannot see is a failing test with no explanation in the file
    it names."""
    doc = ast.get_docstring(ast.parse((HARNESS / name).read_text(encoding="utf-8")))
    assert doc and "mports nothing from this package" in doc, (
        f"{name} is in CANOPY but does not state the constraint in its docstring."
    )


def test_refs_is_where_the_ref_primitives_actually_live():
    """Not a tautology: it is the assertion that the split happened and stayed.
    Rolling `norm_ref` back into `context.py` would pass every test above — they
    only constrain what a leaf imports, not what it contains."""
    from harness import refs
    for name in ("REF_RE", "parse_ref", "norm_ref", "ref_in", "parse_context",
                 "figure_number", "FOLIO_ZONES", "APPARATUS_ZONES"):
        assert hasattr(refs, name), f"refs.{name} is gone"
    assert refs.norm_ref("1-48") == "1-048"
