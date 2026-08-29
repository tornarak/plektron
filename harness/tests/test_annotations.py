"""The annotation store's parser and gate.

Every case here is one rule the format has, and the rules exist because the
failure each prevents is silent: a section name nobody reads is an empty banner
across the top of a page of the book, an alias that resolves to nothing is raw
brackets in a reader's prose, and a `page:` ref that normalises two ways is one
leaf annotated twice.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from harness import annotations as ann
from harness import entities


def _file(text: str) -> str:
    return text.strip() + "\n"


GOOD = _file("""
# notice:physical-anthropology — Race and what replaced it

- status: proposed
- attaches: toc:chII.1
- attaches: entity:people:mongoloids
- attaches: page:3-060

## links

| alias | url | title | note |
|---|---|---|---|
| beringia | https://doi.org/10.1000/xyz | The peopling of Beringia | genetics |

## summary

The vocabulary here is that of 1904 anthropometry. See [[beringia]] and
[[people:mongoloids]].

## full

The long text.
""")


def test_a_good_file_round_trips():
    rec = ann.parse(GOOD, "t.md")
    assert rec["id"] == "notice:physical-anthropology"
    assert rec["class"] == "notice"
    assert rec["status"] == "proposed"
    assert rec["full"] == "The long text."
    assert [t["raw"] for t in rec["attaches"]] == [
        "toc:chII.1", "entity:people:mongoloids", "page:3-060"]
    assert rec["links"][0]["title"] == "The peopling of Beringia"
    assert rec["used_links"] == ["beringia"]


def test_placement_comes_from_the_class_and_cannot_be_authored():
    """The one thing no file may disagree with its own directory about."""
    assert ann.parse(GOOD, "t.md")["placement"] == "top"
    assert ann.ANNOTATION_CLASSES["supplement"] == "bottom"
    # There is no field that could say otherwise.
    assert "placement" not in ann.KNOWN_FIELDS
    with pytest.raises(ann.Malformed, match="unknown field"):
        ann.parse(GOOD.replace("- status:", "- placement: bottom\n- status:"))


def test_an_unknown_field_is_refused_not_ignored():
    with pytest.raises(ann.Malformed, match="unknown field"):
        ann.parse(GOOD.replace("- attaches: page:3-060", "- attachs: page:3-060"))


def test_a_hyphenated_field_key_still_matches():
    """`entities._FIELD` was `[a-z]+` once and silently dropped `part-of:`.

    Nothing in this store has a hyphen in a key yet, which is exactly when a
    narrowed pattern would go unnoticed — so the pattern is asserted directly.
    """
    assert ann._FIELD.match("- part-of: x")


def test_a_capitalised_heading_is_accepted_and_a_wrong_word_is_not():
    """Two halves of one rule, and they pull in opposite directions.

    Names are compared lower-cased, so `## Summary` is the *same section* — the
    shift key is not a way to lose your summary and get a blank banner across
    the top of a page. A different word is refused outright, because that is the
    case a permissive parser would turn into an empty section nobody notices.
    """
    assert ann.parse(GOOD.replace("## summary", "## Summary"))["summary"]
    with pytest.raises(ann.Malformed, match="authored sections"):
        ann.parse(GOOD.replace("## full", "## notes"))
    with pytest.raises(ann.Malformed, match="`## full` and not `## page`"):
        ann.parse(GOOD.replace("## full", "## page"))


def test_an_empty_summary_is_refused():
    with pytest.raises(ann.Malformed, match="no `## summary`"):
        ann.parse(GOOD.replace(
            "The vocabulary here is that of 1904 anthropometry. See [[beringia]] and\n"
            "[[people:mongoloids]].", ""))


def test_an_entity_target_keeps_its_second_colon():
    t = ann.parse_attach("entity:people:mongoloids")
    assert t == {"kind": "entity", "value": "people:mongoloids",
                 "raw": "entity:people:mongoloids"}


def test_a_page_target_is_normalised_and_a_bare_integer_refused():
    assert ann.parse_attach("page:1-55")["value"] == "1-055"
    with pytest.raises(ann.Malformed, match="not a page ref"):
        ann.parse_attach("page:55")


def test_an_unknown_attach_kind_names_all_three():
    with pytest.raises(ann.Malformed) as exc:
        ann.parse_attach("chapter:chII")
    for kind in ann.ATTACH_KINDS:
        assert kind in str(exc.value)


def test_a_target_listed_twice_is_refused():
    with pytest.raises(ann.Malformed, match="listed twice"):
        ann.parse(GOOD.replace("- attaches: page:3-060",
                               "- attaches: page:3-060\n- attaches: page:3-60"))


# --- the links table -------------------------------------------------------

def _with_links(rows: str, prose: str = "See [[a]].") -> str:
    return _file(f"""
# supplement:music — Music

- status: proposed
- attaches: page:1-001

## links

| alias | url | title | note |
|---|---|---|---|
{rows}

## summary

{prose}
""")


def test_a_non_http_url_is_refused():
    with pytest.raises(ann.Malformed, match="not an http or https URL"):
        ann.parse(_with_links("| a | javascript:alert(1) | T | |"))


def test_a_url_that_would_break_the_markdown_link_is_refused():
    with pytest.raises(ann.Malformed, match="space, a parenthesis"):
        ann.parse(_with_links("| a | https://x.test/a(b) | T | |"))


def test_a_title_holding_a_bracket_is_refused():
    with pytest.raises(ann.Malformed, match="close the markdown link early"):
        ann.parse(_with_links("| a | https://x.test/ | T] more | |"))


def test_a_duplicate_alias_and_a_duplicate_url_are_each_refused():
    with pytest.raises(ann.Malformed, match="alias 'a' listed twice"):
        ann.parse(_with_links("| a | https://x.test/1 | T | |\n"
                              "| a | https://x.test/2 | T | |"))
    with pytest.raises(ann.Malformed, match="already on another row"):
        ann.parse(_with_links("| a | https://x.test/1 | T | |\n"
                              "| b | https://x.test/1 | U | |",
                              prose="See [[a]] and [[b]]."))


def test_an_alias_with_a_colon_is_refused():
    """The colon is the whole basis for telling a link alias from an entity."""
    with pytest.raises(ann.Malformed, match="never a colon"):
        ann.parse(_with_links("| a:b | https://x.test/ | T | |", prose="Text."))


def test_a_reference_to_no_row_is_refused():
    with pytest.raises(ann.Malformed, match=r"`\[\[b\]\]` resolves to no row"):
        ann.parse(_with_links("| a | https://x.test/ | T | |",
                              prose="See [[a]] and [[b]]."))


def test_expand_links_builds_a_markdown_link_and_leaves_entities_alone():
    rows = [{"alias": "a", "url": "https://x.test/", "title": "T", "note": ""}]
    out = ann.expand_links("See [[a]] and [[people:x]].", rows)
    assert out == "See [T](https://x.test/) and [[people:x]]."


def test_the_two_bracket_forms_cannot_collide():
    """`LINKREF` has no colon in its class; `entities.WIKILINK` requires one."""
    assert not ann.LINKREF.findall("[[people:mongoloids]]")
    assert not entities.WIKILINK.findall("[[melodiya-1974]]")


def test_link_schemes_match_the_renderer():
    from harness import edition_ui
    assert ann.LINK_SCHEMES == edition_ui.LINK_SCHEMES


# --- set_status ------------------------------------------------------------

def test_set_status_does_not_rewrite_prose():
    """The ported lexicon bug: a `- status:` inside the long text was the first
    literal match, so the writer rewrote a sentence and reported a change that
    had not happened."""
    text = _file("""
# notice:x — X

- status:proposed
- attaches: page:1-001

## summary

S.

## full

A line that reads `- status:proposed` in prose.
""")
    out = ann.set_status(text, "ratified")
    assert ann.parse(out)["status"] == "ratified"
    assert "A line that reads `- status:proposed` in prose." in out


# --- resolvers -------------------------------------------------------------

def _store(**over):
    rec = ann.parse(GOOD, "t.md") | {"status": "ratified"}
    rec |= over
    return {rec["id"]: rec}


def test_for_page_never_touches_the_filesystem():
    """Its whole contract is that the caller holds the folio."""
    store = _store()
    nowhere = Path("/nonexistent-root-for-this-test")
    assert ann.for_page(store, "3-060")["top"]
    assert not ann.for_page(store, "1-001")["top"]
    assert nowhere.exists() is False


def test_for_page_reaches_a_direct_target_with_no_toc_ids_at_all():
    assert ann.for_page(_store(), "3-060")["top"][0]["id"].startswith("notice:")


def test_for_page_reaches_a_section_target_only_when_given_the_chain():
    store = _store()
    assert not ann.for_page(store, "1-056")["top"]
    assert ann.for_page(store, "1-056", ["chII", "chII.1"])["top"]


def test_a_proposed_annotation_attaches_to_nothing():
    store = _store(status="proposed")
    assert not ann.for_page(store, "3-060")["top"]
    assert not ann.for_entity(store, "people:mongoloids")["top"]
    assert not ann.has_toc_attachments(store)


def test_placement_routes_a_supplement_to_the_bottom():
    rec = ann.parse(GOOD.replace("notice:physical-anthropology",
                                 "supplement:physical-anthropology"), "t.md")
    rec["status"] = "ratified"
    out = ann.for_page({rec["id"]: rec}, "3-060")
    assert out["bottom"] and not out["top"]


# --- check -----------------------------------------------------------------

def _write(tmp_path: Path, cls: str, slug: str, text: str) -> Path:
    d = tmp_path / ann.ANNDIR / cls
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{slug}.md"
    p.write_text(text, encoding="utf-8")
    return p


def test_an_absent_store_is_empty_and_not_an_error(tmp_path):
    assert ann.load(tmp_path) == {}
    assert ann.check(tmp_path)["ok"]


def test_a_stray_file_outside_a_class_directory_is_named(tmp_path):
    d = tmp_path / ann.ANNDIR
    d.mkdir(parents=True)
    (d / "loose.md").write_text(GOOD, encoding="utf-8")
    out = ann.check(tmp_path)
    assert not out["ok"]
    assert "Nothing reads this file" in out["errors"][0]


def test_a_heading_disagreeing_with_its_directory_or_filename(tmp_path):
    _write(tmp_path, "supplement", "physical-anthropology", GOOD)
    assert "The directory is the class" in " ".join(ann.check(tmp_path)["errors"])

    for p in (tmp_path / ann.ANNDIR).glob("*/*.md"):
        p.unlink()
    _write(tmp_path, "notice", "other", GOOD)
    assert "The filename is the slug" in " ".join(ann.check(tmp_path)["errors"])


def test_zero_attachments_is_an_error(tmp_path):
    _write(tmp_path, "notice", "x", _file("""
# notice:x — X

- status: proposed

## summary

S.
"""))
    assert "attaches to nothing" in " ".join(ann.check(tmp_path)["errors"])


def test_an_annotation_wikilink_is_refused_with_its_alternative(tmp_path):
    _write(tmp_path, "notice", "x", _file("""
# notice:x — X

- status: proposed
- attaches: page:1-001

## summary

See [[supplement:music]].
"""))
    errs = " ".join(ann.check(tmp_path)["errors"])
    assert "/edition/annotation/supplement:music" in errs


def test_the_committed_store_checks_out():
    assert ann.check(Path("."))["ok"]
