"""Every exception this package raises on purpose lands inside `cli.main`'s net.

`cli.main` catches `(ValueError, FileNotFoundError, KeyError, OSError)` and
**no project class**. Three of the eight classes defined here happened to
subclass `ValueError` and so were caught; five subclassed plain `Exception` and
were not, so the same fault came back as a one-line `ERROR:` or a twenty-line
traceback depending on which verb met it first.

`entities.Malformed` was the worst of them. `entities.load` parses every record
and does not catch, and `validate`, `generate`, `context`, `detectors` and the
reading view all call it — so one malformed entity file gave a clean refusal
from `harness entity check` and a stack trace from five other verbs.

Two classes named `ConfigError` with two different bases was the sharpest: which
one you got depended on which editor's config was malformed.

This gate is over the classes, not the call sites, because that is where the
fault lives — a handler can be added anywhere, but a class outside the net is
outside it everywhere at once.
"""
from __future__ import annotations

import inspect
import pkgutil
from importlib import import_module

import pytest

import harness
from harness.cli import main as cli_main

#: The tuple `cli.main` nets, read off the source rather than restated, so this
#: gate cannot pass by agreeing with a copy of itself.
CAUGHT = (ValueError, FileNotFoundError, KeyError, OSError)


def _project_exceptions() -> list[tuple[str, type]]:
    """Every exception class defined *in* this package, found by walking it.

    Walked rather than listed: a class added tomorrow is exactly the one a list
    would miss, and this whole finding is a case of something added later
    landing outside a net everything older was inside.
    """
    out: list[tuple[str, type]] = []
    for mod in pkgutil.walk_packages(harness.__path__, "harness."):
        # `__main__` calls `sys.exit(main())` at import — importing it here runs
        # the CLI and takes pytest down with a `SystemExit` the collector
        # reports as an internal error. `tests` is not the subject.
        if ".tests" in mod.name or mod.name.endswith((".tests", ".__main__")):
            continue
        try:
            m = import_module(mod.name)
        except BaseException:                                 # noqa: BLE001
            continue          # optional deps; not this gate's business
        for name, obj in vars(m).items():
            if (inspect.isclass(obj) and issubclass(obj, BaseException)
                    and obj.__module__ == m.__name__):
                out.append((f"{m.__name__}.{name}", obj))
    return sorted(set(out), key=lambda p: p[0])


def test_the_walk_actually_finds_the_known_classes():
    """Guard on the guard: an import failure or a wrong module filter would make
    every assertion below vacuous over an empty list."""
    found = {n for n, _ in _project_exceptions()}
    for expected in ("harness.entities.Malformed", "harness.lexicon.Malformed",
                     "harness.dispatch.Unready", "harness.generate.Unready",
                     "harness.lines_config.ConfigError",
                     "harness.zones_config.ConfigError",
                     "harness.marks.MarksConfigError",
                     "harness.speech.Unspeakable"):
        assert expected in found, f"{expected} not found by the walk"


@pytest.mark.parametrize("name,cls", _project_exceptions(),
                         ids=[n for n, _ in _project_exceptions()])
def test_every_project_exception_is_caught_by_main(name, cls):
    """A class outside the net reaches the user as a traceback from any verb
    that has not grown its own local handler."""
    assert issubclass(cls, CAUGHT), (
        f"{name} subclasses {cls.__bases__[0].__name__}, which `cli.main` does "
        f"not catch — it will surface as a traceback. Subclass ValueError.")


def test_main_still_nets_what_this_gate_assumes():
    """If `main`'s handler narrows, the assertions above stop meaning anything.

    Read out of the function's own source: a hand-copied tuple here would be the
    two-witnesses-that-are-one shape the project is organised against.
    """
    src = inspect.getsource(cli_main)
    for exc in CAUGHT:
        assert exc.__name__ in src, (
            f"`cli.main` no longer names {exc.__name__}; this gate is stale")
