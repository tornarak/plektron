"""Which text an invocation means: the four outcomes, and the two groups that need none."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from conftest import write_project

from harness import cli
from harness.entities import alias_index, auto_forms, load, ratify_text
from harness.layout import (
    ProjectError,
    bare_own_citations,
    citation_errors,
    dpi,
    lang,
    notation,
    page_files,
    project,
    project_root,
    px,
    ref_of,
    refuse_another_texts,
    repo_root,
    shared,
    site_base,
    witness,
    witnesses,
    workspace_root,
    workspace_stems,
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


def _workspace_with(tmp_path, *stems):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "workspace.json").write_text("{}", encoding="utf-8")
    return [write_project(ws / f"t{i}", s) for i, s in enumerate(stems)]


def test_a_citation_in_a_shared_store_names_a_book_a_text_declares(tmp_path):
    text, _ = _workspace_with(tmp_path, "chukchi", "koryak")
    assert citation_errors("see chukchi-1-044 and koryak-2-010", text) == []
    assert "is bare" in citation_errors("see 1-044", text)[0]
    assert "no text here declares" in citation_errors("see yukaghir-1-044", text)[0]
    # Neither a URL's digits nor a printed date is a page.
    assert citation_errors("https://x.org/a/1-044 in 1904-1907", text) == []


def test_a_reader_sees_the_served_texts_citations_bare_and_anothers_whole():
    got = bare_own_citations("chukchi-1-044 and chukchi-mythology-1-044, koryak-2-010",
                             "chukchi")
    assert got == "1-044 and chukchi-mythology-1-044, koryak-2-010"


def test_two_texts_sharing_a_stem_are_found(tmp_path):
    text, _ = _workspace_with(tmp_path, "chukchi", "chukchi")
    assert workspace_stems(text) == ["chukchi", "chukchi"]


def test_a_ratification_licenses_the_rule_on_the_text_it_was_made_against(tmp_path):
    """An alias says what a form means in *this* book, so the next book's pages must
    not be linked on a judgement nobody made about them. It is asked about instead."""
    chukchi, koryak = _workspace_with(tmp_path, "chukchi", "koryak")
    f = tmp_path / "ws" / "edition" / "entities" / "place" / "markova.md"
    f.parent.mkdir(parents=True)
    f.write_text("# place:markova — Markova\n\n- status: ratified chukchi\n\n## aliases\n\n"
                 "| form | lang | auto | note |\n|---|---|---|---|\n| Markova | | yes | |\n",
                 encoding="utf-8")
    assert auto_forms(alias_index(load(chukchi))) == {"Markova": "place:markova"}
    assert load(koryak)["place:markova"]["status"] == "proposed"
    assert auto_forms(alias_index(load(koryak))) == {}

    f.write_text(ratify_text(f.read_text(encoding="utf-8"), koryak), encoding="utf-8")
    assert "- status: ratified chukchi koryak\n" in f.read_text(encoding="utf-8")
    assert auto_forms(alias_index(load(koryak))) == {"Markova": "place:markova"}
    assert ratify_text(f.read_text(encoding="utf-8"), koryak) == f.read_text(encoding="utf-8")


def test_a_sites_prefix_comes_from_its_folders(tmp_path):
    text, _ = _workspace_with(tmp_path, "chukchi", "koryak")
    assert site_base(text) == "/ws/t0"
    assert site_base(write_project(tmp_path / "alone")) == "/alone"


# --- what a second text declares -------------------------------------------


def _manifest(root: Path, **fields) -> Path:
    """`root`'s manifest with `fields` laid over the fixture's."""
    write_project(root)
    p = root / "project.json"
    rec = json.loads(p.read_text(encoding="utf-8"))
    p.write_text(json.dumps({**rec, **fields}) + "\n", encoding="utf-8")
    return root


def test_a_manifest_that_says_nothing_means_what_the_first_text_always_meant(tmp_path):
    assert (lang(tmp_path), notation(tmp_path), dpi(tmp_path)) == ("en", "jesup", 300)
    assert witnesses(tmp_path) == []
    assert px(tmp_path, 20) == 20


def test_a_manifest_declares_its_prose_language_from_the_table(tmp_path):
    assert lang(_manifest(tmp_path / "ru", lang="ru")) == "ru"
    with pytest.raises(ProjectError, match="not in langs.LANGS"):
        lang(_manifest(tmp_path / "xx", lang="xx"))


def test_a_books_prose_is_never_in_a_tier1_language(tmp_path):
    """A Tier-1 base would make every unmarked span a native form, which is the
    firewall's whole question answered by a manifest default."""
    with pytest.raises(ProjectError, match="Tier-1"):
        lang(_manifest(tmp_path, lang="ckt"))


def test_a_notation_is_one_the_harness_has_tables_for(tmp_path):
    assert notation(_manifest(tmp_path / "k", notation="kolyma-1900")) == "kolyma-1900"
    with pytest.raises(ProjectError, match="notation"):
        notation(_manifest(tmp_path / "x", notation="boas"))


@pytest.mark.parametrize("bad", [0, -300, 600.0, "600", True])
def test_dpi_is_a_positive_integer(tmp_path, bad):
    with pytest.raises(ProjectError, match="dpi"):
        dpi(_manifest(tmp_path, dpi=bad))


def test_a_threshold_keeps_its_physical_size_at_another_resolution(tmp_path):
    root = _manifest(tmp_path, dpi=600)
    assert px(root, 20) == 40
    assert px(root, 6) == 12


def test_a_witness_pdf_is_declared_under_its_own_folder_and_is_not_a_part(tmp_path):
    """Under `pdfs/witness/`, because `scans` substring-matches part names over
    `pdfs/*.pdf`, and a witness named like the master would be cut into `scans/`."""
    w = {"id": "b", "pdf": "pdfs/witness/copy-2.pdf", "label": "Berkeley copy"}
    root = _manifest(tmp_path / "ok", witnesses=[w])
    assert witness(root, "b") == w
    with pytest.raises(ProjectError, match="declared: b"):
        witness(root, "c")
    with pytest.raises(ProjectError, match="witness"):
        project(_manifest(tmp_path / "flat", witnesses=[{**w, "pdf": "pdfs/copy-2.pdf"}]))
    with pytest.raises(ProjectError, match="twice"):
        project(_manifest(tmp_path / "dup", witnesses=[w, w]))


def test_masterless_entries_are_refs(tmp_path):
    with pytest.raises(ProjectError, match="masterless"):
        project(_manifest(tmp_path, masterless=["1"]))


def test_a_stem_that_prefixes_another_is_not_that_other(tmp_path):
    """`chukchi` is a prefix of `chukchi-materials`, and both live in one workspace.
    A page file, a ref and a ratification must each match the stem whole."""
    chukchi, materials = _workspace_with(tmp_path, "chukchi", "chukchi-materials")
    scans = materials / "scans"
    scans.mkdir()
    (scans / "chukchi-materials-1-058.png").write_bytes(b"")
    assert page_files(scans, ".png", chukchi) == []
    assert [p.name for p in page_files(scans, ".png", materials)] == [
        "chukchi-materials-1-058.png"]
    with pytest.raises(ValueError):
        ref_of("chukchi-materials-1-058", chukchi)
    assert ref_of("chukchi-materials-1-058", materials) == "1-058"

    f = tmp_path / "ws" / "edition" / "entities" / "place" / "markova.md"
    f.parent.mkdir(parents=True)
    f.write_text("# place:markova — Markova\n\n- status: ratified chukchi-materials\n",
                 encoding="utf-8")
    assert load(chukchi)["place:markova"]["status"] == "proposed"
    assert load(materials)["place:markova"]["status"] == "ratified"
