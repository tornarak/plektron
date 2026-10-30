"""Which text an invocation means: the four outcomes, and the two groups that need none."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from conftest import write_project

from harness import cli
from harness.layout import (
    ProjectError,
    project_root,
    refuse_another_texts,
    repo_root,
    shared,
    workspace_root,
)


def test_a_named_root_with_a_manifest_is_that_text(tmp_path):
    assert project_root(tmp_path) == tmp_path


def test_a_named_root_without_one_refuses_and_never_falls_back_to_the_cwd(
        tmp_path, monkeypatch):
    """A mistyped root that ran on whatever project the shell was in would write to
    the wrong book, so a text under the cwd must not rescue it."""
    monkeypatch.chdir(write_project(tmp_path / "here"))
    with pytest.raises(ProjectError, match="no project.json"):
        project_root(tmp_path / "typo")


def test_named_nothing_the_nearest_ancestor_answers_relative_to_the_cwd(
        tmp_path, monkeypatch):
    """Relative, because what a run records must not carry this machine's paths."""
    text = write_project(tmp_path / "ws" / "text")
    (text / "gt" / "ocr").mkdir(parents=True)
    monkeypatch.chdir(text)
    assert project_root(None) == Path(".")
    monkeypatch.chdir(text / "gt" / "ocr")
    assert project_root(None) == Path("../..")


def test_named_nothing_outside_any_text_refuses_and_names_what_exists(
        tmp_path, monkeypatch):
    bare = tmp_path / "bare"
    bare.mkdir()
    (tmp_path / "project.json").unlink()
    monkeypatch.chdir(bare)
    with pytest.raises(ProjectError, match="jesup/bogoras-chukchi"):
        project_root(None)


def test_a_workspace_is_found_above_a_text_and_is_optional(tmp_path):
    text = write_project(tmp_path / "ws" / "text")
    assert workspace_root(text) is None
    (tmp_path / "ws" / "workspace.json").write_text("{}", encoding="utf-8")
    assert workspace_root(text) == (tmp_path / "ws").resolve()


def test_the_cli_exits_2_outside_a_text_and_the_repo_groups_still_answer(capsys):
    """`verbs` and `agents` read the repo, so a person at its top may ask them."""
    os.chdir(repo_root())
    try:
        assert cli.main(["corpus", "state", "--all"]) == 2
        assert "not inside a text" in capsys.readouterr().err
        assert cli.main(["verbs", "show", "tei diff"]) == 0
    finally:
        os.chdir(repo_root() / "jesup" / "bogoras-chukchi")


def test_a_text_composes_over_its_workspace_by_relative_path(tmp_path):
    """Reads fall through; a write lands in the workspace unless the text holds the
    store, so adding one entry cannot start shadowing all of them."""
    (tmp_path / "ws" / "workspace.json").parent.mkdir(parents=True)
    (tmp_path / "ws" / "workspace.json").write_text("{}", encoding="utf-8")
    text = write_project(tmp_path / "ws" / "text")
    ws = (tmp_path / "ws").resolve()
    assert shared(text, "edition/entities") == ws / "edition/entities"
    (text / "edition/entities").mkdir(parents=True)
    assert shared(text, "edition/entities") == text / "edition/entities"
    assert shared(tmp_path, "edition/entities") == tmp_path / "edition/entities"


def test_a_model_fitted_to_another_text_is_read_but_not_overwritten_or_scored(tmp_path):
    (tmp_path / "ws" / "models").mkdir(parents=True)
    (tmp_path / "ws" / "workspace.json").write_text("{}", encoding="utf-8")
    text = write_project(tmp_path / "ws" / "text", "koryak")
    man = tmp_path / "ws" / "models" / "m.json"
    man.write_text('{"text": "chukchi"}', encoding="utf-8")
    with pytest.raises(ValueError, match="fitted to `chukchi`"):
        refuse_another_texts(man, text)
    man.write_text('{"text": "koryak"}', encoding="utf-8")
    refuse_another_texts(man, text)
