"""In `zones.py`, `ink` names a flag and nothing else.

It used to name two things. At nine sites it was an **ink-mask array** — a
decoded page handed down so the raster is read once rather than per check — and
at two it was a **boolean**, with *opposite* defaults: `validate_page(ink=True)`
and `validate_corpus(ink=False)`. One keyword, one module, meaning and default
both depending on which function you reached for.

**What made it more than untidiness** is `validate_page`'s own
`bool(ink and zones)`. That is correct for the flag and, for the array, a
`ValueError: truth value of an array with more than one element is ambiguous`.
The two readings were one refactor away from meeting, and the array sites were
the majority — so the plausible "clean this up" edit was the one that breaks.

The arrays are `mask` now. **Not `ink_mask`**: that is the function they are
built by (`lines.ink_mask`, called on the very next line in two of them), and a
parameter of that name would shadow it — a second collision introduced while
fixing the first, which is how this kind of rename usually goes wrong.

Left alone deliberately: `lines.ink_bands(ink, …)` and
`zones_ui._ink_cell(ink: dict)`. Each is the only `ink` in its module and neither
is ambiguous, so renaming them would be consistency for its own sake.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

HARNESS = Path(__file__).resolve().parent.parent


def _params(module: str, name: str) -> list[tuple[str, bool]]:
    """`(function, is_annotated)` for every parameter called `name`."""
    tree = ast.parse((HARNESS / module).read_text(encoding="utf-8"))
    out = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for a in fn.args.args + fn.args.kwonlyargs:
            if a.arg == name:
                out.append((fn.name, a.annotation is not None))
    return out


def test_ink_in_zones_is_only_ever_the_flag():
    """Every surviving `ink` parameter must be the annotated boolean. An
    unannotated one is the array shape coming back."""
    got = _params("zones.py", "ink")
    assert got, "no `ink` parameter at all — has the flag been renamed?"
    unannotated = [fn for fn, ann in got if not ann]
    assert not unannotated, (
        f"{unannotated} take an unannotated `ink`. In this module `ink` is the "
        "boolean flag; the decoded ink-mask array is `mask`, because "
        "`validate_page` reads `bool(ink and zones)` — true for a flag and a "
        "ValueError for an array."
    )


def test_the_flag_is_exactly_those_two_functions():
    assert {fn for fn, _ in _params("zones.py", "ink")} == \
        {"validate_page", "validate_corpus"}


def test_the_two_defaults_still_disagree_on_purpose():
    """They are opposite and that is correct, which is why renaming rather than
    unifying was the fix. `validate_page` checks one page and the raster is the
    point; `validate_corpus` sweeps 832 and the ink pass is ~0.2s each, so it is
    opt-in there and the list reads the cache instead."""
    tree = ast.parse((HARNESS / "zones.py").read_text(encoding="utf-8"))
    seen = {}
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef) or fn.name not in (
                "validate_page", "validate_corpus"):
            continue
        names = [a.arg for a in fn.args.args]
        pad = len(names) - len(fn.args.defaults)
        for i, a in enumerate(names):
            if a == "ink":
                seen[fn.name] = fn.args.defaults[i - pad].value
    assert seen == {"validate_page": True, "validate_corpus": False}


def test_the_mask_parameter_carries_the_arrays():
    """The other half: the rename landed rather than merely deleting the name."""
    got = {fn for fn, _ in _params("zones.py", "mask")}
    assert {"measure_frame", "page_windows", "uncovered_ink",
            "paragraph_starts", "split_at_paragraphs"} <= got


def test_mask_does_not_shadow_the_function_that_builds_it():
    """`lines.ink_mask` is called inside two of the functions that take a `mask`.
    Naming the parameter `ink_mask` — the obvious choice — would shadow it."""
    src = (HARNESS / "zones.py").read_text(encoding="utf-8")
    assert "ink_mask(mask if mask is not None" in src
    assert not _params("zones.py", "ink_mask"), (
        "a parameter is named `ink_mask`, which shadows the function of that "
        "name imported in the same scope"
    )


@pytest.mark.parametrize("module,name", [("lines.py", "ink"),
                                         ("zones_ui.py", "ink")])
def test_the_untouched_ones_are_still_unambiguous(module, name):
    """Each is the only `ink` in its module. If a second one appears with the
    other meaning, that module has acquired the collision this file records."""
    got = _params(module, name)
    kinds = {ann for _, ann in got}
    assert len(kinds) <= 1, (
        f"{module} now has `{name}` in two shapes — annotated and not — which is "
        "the ambiguity `zones.py` had. Rename the array to `mask`."
    )
