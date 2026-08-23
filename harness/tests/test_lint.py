"""Ruff is a gate, and its rule set is pinned rather than inherited.

Two tests, and the second is the one with a story.

`ruff check` runs in the suite because a linter nobody runs is a linter that
reports nothing. Its value here is not tidiness: `F821` caught two undefined names
*introduced while fixing other ruff findings* in the same sitting, and `B905` found
`restore`'s post-write verification comparing the source and the written page with
a bare `zip`, which stops at the shorter side — so a write that dropped a line
would have been checked over the common prefix and reported clean. That is the
failure this repo has already paid for twice, sitting inside the function whose
entire job is to verify the write.

**The rule set is pinned because ruff's default moves.** It is documented as
`E4,E7,E9,F`; 0.16.1 additionally enables flake8-bandit, implicit-str-concat and much
of RUF, and reports 161 findings on this tree where the pinned selection reports none.
A gate that changes meaning when a dev dependency is upgraded cannot be acted on —
the same reason `train score zones` must be told which model it is scoring rather than
reading whichever lists are lying around. So `select` is asserted to be an explicit
list, and `RUF001`-`003` are asserted absent from it by name.

That last one is not hypothetical fastidiousness. `RUF001`-`003` flag characters
resembling ASCII, which in this corpus is a description of the subject matter:
`ˊ` U+02CA, `ɪ` U+026A and `ᵋ` U+1D4B are inventory glyphs. They fire 152 times, on
the glyphs the project exists to transcribe. The project already has a lookalike
detector whose whole design is that it is *scoped* — Tier-1 spans only, and
`test_lookalike_scope.py` exists because a consolidation was once nearly carried out
on an audit that mistook that scoping for drift. An unscoped second detector firing
on the inventory would bury the real one's signal, which is the noise-over-signal
failure named at the top of CLAUDE.md.
"""
from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent

# Ambiguous-unicode rules. Named individually rather than as a family, because the
# rest of RUF is unobjectionable and a blanket ban would overstate the case.
AMBIGUOUS_UNICODE = ("RUF001", "RUF002", "RUF003")


def lint_config() -> dict:
    with (REPO / "pyproject.toml").open("rb") as fh:
        return tomllib.load(fh)["tool"]["ruff"]["lint"]


def test_the_tree_is_clean():
    """`uv run ruff check harness/ tools/` — the gate itself."""
    r = subprocess.run([sys.executable, "-m", "ruff", "check", "harness", "tools"],
                       cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_the_rule_set_is_pinned_not_inherited():
    """An explicit `select` is what keeps the gate's meaning fixed across upgrades."""
    cfg = lint_config()
    assert cfg.get("select"), (
        "pyproject.toml must pin [tool.ruff.lint] select — ruff's default "
        "selection has changed between releases and reports 161 findings here")


@pytest.mark.parametrize("rule", AMBIGUOUS_UNICODE)
def test_the_ambiguous_unicode_rules_stay_off(rule):
    """They fire on the transcription inventory itself. See this module's docstring."""
    cfg = lint_config()
    selected = cfg.get("select", []) + cfg.get("extend-select", [])
    assert rule not in selected, (
        f"{rule} flags characters that resemble ASCII, which here means the "
        "inventory glyphs (U+02CA, U+026A, U+1D4B). 152 hits, all false. The "
        "scoped lookalike detector in normalize.py/validate.py is the real one.")
    # `RUF` as a family would enable all three by implication.
    assert "RUF" not in selected, (
        f"selecting the whole RUF family enables {rule}; pick individual rules")
