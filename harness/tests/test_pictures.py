"""An entity's picture: the `image:` field, the ledger, the gate and the card.

The network half — `tools/entity_images.py` asking Wikidata and Commons — is
tested on canned answers, since what can go wrong quietly there is the
decision over them: which claim wins, which licence passes, and what a failed
lookup is allowed to delete.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from harness import entities, pictures
from harness.tests.test_entities import entry

ROOT = Path(__file__).resolve().parent.parent.parent


def _row(**kw) -> dict:
    row = {"page": "https://commons.wikimedia.org/wiki/File:W.jpg",
           "thumb": "https://upload.wikimedia.org/330px-W.jpg",
           "width": 330, "height": 220, "sha1": "abc",
           "licence": "CC BY-SA 4.0",
           "licence_url": "https://creativecommons.org/licenses/by-sa/4.0",
           "artist": "A. Photographer", "attribution_required": True,
           "retrieved": "2026-10-13"}
    return {**row, **kw}


def _ledger(root: Path, p18=None, files=None) -> None:
    (root / "edition").mkdir(parents=True, exist_ok=True)
    (root / pictures.LEDGER).write_text(
        json.dumps({"p18": p18 or {}, "files": files or {}}), encoding="utf-8")


def _parse(extra: str, ident: str = "taxon:x") -> dict:
    return entities.parse(f"# {ident} — X\n\n- status: ratified\n{extra}"
                          "\n## gloss\n\nx\n")


# ------------------------------------------------------------- the field

@pytest.mark.parametrize("raw,want", [
    ("commons:Canis lupus laying.jpg", "commons:Canis_lupus_laying.jpg"),
    ("commons:canis_lupus.jpg", "commons:Canis_lupus.jpg"),
    ("none", "none"),
])
def test_image_takes_a_commons_title_or_none(raw, want):
    """Spaces, underscores and a lowercase initial are one file to MediaWiki,
    so they are one key here — or an override would read "awaiting fetch" for
    a file that had been fetched under the other spelling."""
    assert _parse(f"- image: {raw}\n")["image"] == want


@pytest.mark.parametrize("raw", [
    "https://upload.wikimedia.org/x.jpg",
    "commons:File:Wolf.jpg",
    "Wolf.jpg",
    "commons:Wolf",
])
def test_image_refuses_a_url_a_prefix_or_a_bare_title(raw):
    with pytest.raises(entities.Malformed):
        _parse(f"- image: {raw}\n")


def test_image_is_given_once():
    with pytest.raises(entities.Malformed):
        _parse("- image: none\n- image: commons:W.jpg\n")


# ------------------------------------------------------------- resolution

def _rec(extra: str = "", ident: str = "taxon:x") -> dict:
    return _parse(extra, ident)


def test_p18_is_reached_through_the_entrys_own_qid():
    led = {"p18": {"Q1": "W.jpg"}, "files": {"W.jpg": _row()}}
    got = pictures.resolve(_rec("- link: wikidata:Q1\n"), led)
    assert got["file"] == "W.jpg" and got["source"] == "wikidata:P18"


def test_an_editors_line_beats_the_rule_and_none_beats_both():
    led = {"p18": {"Q1": "W.jpg"},
           "files": {"W.jpg": _row(), "E.jpg": _row(sha1="e")}}
    over = pictures.resolve(
        _rec("- link: wikidata:Q1\n- image: commons:E.jpg\n"), led)
    assert over["file"] == "E.jpg" and over["source"] == "editor"
    assert pictures.resolve(_rec("- link: wikidata:Q1\n- image: none\n"), led) is None


def test_the_class_is_read_at_render():
    """Moving an entry out of scope takes its picture with it and touches no
    ledger row — the scope follows the entry, not the fetch."""
    led = {"p18": {"Q1": "W.jpg"}, "files": {"W.jpg": _row()}}
    assert pictures.resolve(_rec("- link: wikidata:Q1\n", "people:x"), led)
    assert pictures.resolve(_rec("- link: wikidata:Q1\n", "being:x"), led) is None


# ------------------------------------------------------------- the gate

def test_check_counts_pictures_and_passes_a_clean_ledger(tmp_path):
    entry(tmp_path, "taxon:wolf", extra="- link: wikidata:Q1\n")
    _ledger(tmp_path, {"Q1": "W.jpg"}, {"W.jpg": _row()})
    r = entities.check(tmp_path)
    assert r["ok"], r["errors"]
    assert r["pictures"] == 1 and r["picture_rows"] == []


def test_check_refuses_an_image_line_out_of_scope(tmp_path):
    entry(tmp_path, "being:x", extra="- image: commons:W.jpg\n")
    assert any("Pictures are for" in e for e in entities.check(tmp_path)["errors"])


def test_check_refuses_a_p18_with_no_file_row(tmp_path):
    entry(tmp_path, "taxon:wolf", extra="- link: wikidata:Q1\n")
    _ledger(tmp_path, {"Q1": "W.jpg"}, {})
    assert not entities.check(tmp_path)["ok"]


def test_check_refuses_a_licence_the_card_cannot_attribute(tmp_path):
    """One witness, not two — the tool refused by the same pattern. What this
    catches is a hand-edited row."""
    entry(tmp_path, "taxon:wolf", extra="- link: wikidata:Q1\n")
    _ledger(tmp_path, {"Q1": "W.jpg"}, {"W.jpg": _row(licence="GFDL")})
    assert any("GFDL" in e for e in entities.check(tmp_path)["errors"])


def test_check_refuses_a_row_missing_a_field(tmp_path):
    row = _row()
    del row["artist"]
    entry(tmp_path, "taxon:wolf", extra="- link: wikidata:Q1\n")
    _ledger(tmp_path, {"Q1": "W.jpg"}, {"W.jpg": row})
    assert any("lacks artist" in e for e in entities.check(tmp_path)["errors"])


def test_awaiting_and_orphans_are_reported_and_gate_nothing(tmp_path):
    entry(tmp_path, "taxon:wolf", extra="- image: commons:New.jpg\n")
    _ledger(tmp_path, {"Q9": "Old.jpg"}, {"Old.jpg": _row(), "Stray.jpg": _row()})
    r = entities.check(tmp_path)
    assert r["ok"], r["errors"]
    assert {x["state"] for x in r["picture_rows"]} == {
        "awaiting fetch", "orphaned p18", "orphaned file"}


@pytest.mark.parametrize("lic", ["Public domain", "CC0", "CC BY 2.0",
                                 "CC BY-SA 3.0 de", "CC BY-SA 4.0",
                                 "Copyrighted free use"])
def test_the_five_families_pass(lic):
    assert pictures.licence_ok(lic)


@pytest.mark.parametrize("lic", ["GFDL", "Attribution", "FAL", "CC BY-NC 2.0", ""])
def test_everything_else_is_refused(lic):
    assert not pictures.licence_ok(lic)


def test_a_rename_leaves_the_picture_in_place(tmp_path):
    """The ledger is keyed by QID and file, so `rename` has nothing to rewrite."""
    entry(tmp_path, "place:a", extra="- link: wikidata:Q1\n")
    _ledger(tmp_path, {"Q1": "W.jpg"}, {"W.jpg": _row()})
    old = entities.path_for("place:a", tmp_path)
    new = entities.path_for("land:a", tmp_path)
    new.parent.mkdir(parents=True, exist_ok=True)
    new.write_text(old.read_text(encoding="utf-8").replace("place:a", "land:a"),
                   encoding="utf-8")
    old.unlink()
    store = entities.load(tmp_path)
    assert pictures.resolve(store["land:a"], pictures.load(tmp_path))


def test_the_ledger_is_written_nfd_and_sorted():
    import unicodedata
    led = {"p18": {"Q2": "B.jpg", "Q1": "A.jpg"},
           "files": {"Sámi.jpg": _row()}}
    text = pictures.dump(led)
    assert text == unicodedata.normalize("NFD", text)
    assert text.index('"Q1"') < text.index('"Q2"')


# ------------------------------------------------------------- the card

def _client(root):
    from starlette.testclient import TestClient

    from harness.web import Sessions, create_app
    return TestClient(create_app(root, Sessions(root=root), editor="edition"))


def test_the_card_shows_the_picture_and_owes_it_a_caption(tmp_path):
    entry(tmp_path, "taxon:wolf", extra="- link: wikidata:Q1\n")
    _ledger(tmp_path, {"Q1": "W.jpg"}, {"W.jpg": _row()})
    got = _client(tmp_path).get("/edition/partial/entity/taxon:wolf").text
    assert "330px-W.jpg" in got
    assert "A. Photographer" in got and "CC BY-SA 4.0" in got
    assert "Wikimedia Commons" in got and "via Wikidata" in got


def test_the_picture_links_its_file_page_and_carries_the_lightbox_size(tmp_path):
    entry(tmp_path, "taxon:wolf", extra="- link: wikidata:Q1\n")
    _ledger(tmp_path, {"Q1": "W.jpg"}, {"W.jpg": _row()})
    got = _client(tmp_path).get("/edition/partial/entity/taxon:wolf").text
    assert "data-full='https://commons.wikimedia.org/wiki/Special:FilePath/W.jpg" \
           "?width=1920'" in got
    head = got.split("<figure class='entity-img'>")[1].split("<img")[0]
    assert "class='pic'" in head and f"href='{_row()['page']}'" in head


def test_an_editors_pick_does_not_say_via_wikidata(tmp_path):
    entry(tmp_path, "taxon:wolf", extra="- image: commons:W.jpg\n")
    _ledger(tmp_path, {}, {"W.jpg": _row()})
    got = _client(tmp_path).get("/edition/partial/entity/taxon:wolf").text
    assert "330px-W.jpg" in got and "via Wikidata" not in got


def test_no_picture_out_of_scope_or_unresolved(tmp_path):
    entry(tmp_path, "being:x", extra="- link: wikidata:Q1\n")
    entry(tmp_path, "taxon:y", extra="- link: wikidata:Q2\n")
    _ledger(tmp_path, {"Q1": "W.jpg"}, {"W.jpg": _row()})
    c = _client(tmp_path)
    for ident in ("being:x", "taxon:y"):
        assert "entity-img" not in c.get(f"/edition/partial/entity/{ident}").text


# ------------------------------------------------------------- the tool

def _tool():
    """Loaded by path, as `test_gazetteer_tool.py` loads its sibling."""
    pytest.importorskip("requests")
    spec = importlib.util.spec_from_file_location(
        "_entity_images_tool", ROOT / "tools" / "entity_images.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_entity_images_tool"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_preferred_beats_normal_and_deprecated_is_never_taken():
    t = _tool()
    assert t.choose([("normal", "a.jpg"), ("preferred", "b.jpg")]) == ("b.jpg", 1)
    assert t.choose([("deprecated", "a.jpg"), ("normal", "b.jpg"),
                     ("normal", "c.jpg")]) == ("b.jpg", 2)
    assert t.choose([("deprecated", "a.jpg")]) == ("", 0)


def test_the_artist_comes_out_of_its_html():
    t = _tool()
    assert t.text_of('<a href="//x">Jane&nbsp;Doe</a>\n (talk)') == "Jane Doe (talk)"
    assert t.text_of("") == ""


def _store(tmp_path, *specs):
    for ident, extra in specs:
        entry(tmp_path, ident, extra=extra)
    return entities.load(tmp_path)


def _item(*claims):
    return {"p18": list(claims)}


def test_sweep_writes_the_pick_and_reports_of_n(tmp_path):
    t = _tool()
    store = _store(tmp_path, ("taxon:wolf", "- link: wikidata:Q1\n"))
    empty = {"p18": {}, "files": {}}
    new, rows = t.sweep(store, empty,
                        {"Q1": _item(("normal", "W 1.jpg"), ("normal", "W2.jpg"))},
                        {"W_1.jpg": {"row": _row()}})
    assert new["p18"] == {"Q1": "W_1.jpg"}
    assert rows[0]["mark"] == "+" and rows[0]["note"] == "of 2"


def test_sweep_drops_a_refused_licence_and_its_p18(tmp_path):
    t = _tool()
    store = _store(tmp_path, ("taxon:wolf", "- link: wikidata:Q1\n"))
    new, rows = t.sweep(store, {"p18": {}, "files": {}},
                        {"Q1": _item(("normal", "W.jpg"))},
                        {"W.jpg": {"row": _row(licence="GFDL")}})
    assert new == {"p18": {}, "files": {}}
    assert "refused" in rows[0]["note"]


def test_a_failed_lookup_keeps_the_prior_row(tmp_path):
    """An outage must not read as "no picture" — that would delete a true row
    on the strength of a timeout."""
    t = _tool()
    store = _store(tmp_path, ("taxon:wolf", "- link: wikidata:Q1\n"))
    prior = {"p18": {"Q1": "W.jpg"}, "files": {"W.jpg": _row()}}
    new, rows = t.sweep(store, prior, {"Q1": {"failed": "timeout", "p18": []}}, {})
    assert new == prior and rows[0]["mark"] == "!"
    new, rows = t.sweep(store, prior, {"Q1": _item(("normal", "W.jpg"))},
                        {"W.jpg": {"failed": "timeout"}})
    assert new == prior and rows[0]["mark"] == "!"


def test_an_unchanged_file_keeps_its_retrieved_date(tmp_path):
    t = _tool()
    store = _store(tmp_path, ("taxon:wolf", "- link: wikidata:Q1\n"))
    prior = {"p18": {"Q1": "W.jpg"}, "files": {"W.jpg": _row(retrieved="2020-01-01")}}
    new, rows = t.sweep(store, prior, {"Q1": _item(("normal", "W.jpg"))},
                        {"W.jpg": {"row": _row(retrieved="2026-10-13")}})
    assert new["files"]["W.jpg"]["retrieved"] == "2020-01-01"
    assert rows[0]["mark"] == "="
    new, rows = t.sweep(store, prior, {"Q1": _item(("normal", "W.jpg"))},
                        {"W.jpg": {"row": _row(sha1="new")}})
    assert rows[0]["mark"] == "~"


def test_imageinfo_maps_answers_back_through_normalized_and_redirects():
    """Titles go out NFC and come back however the server folded them; the
    API's own lists map them, not a re-spelling here."""
    t = _tool()
    asked = []

    def get(params, api):
        asked.append(params["titles"])
        return {"query": {
            "normalized": [{"from": "File:Sámi.jpg", "to": "File:Sámi.jpg"}],
            "redirects": [{"from": "File:Old.jpg", "to": "File:New.jpg"}],
            "pages": {
                "1": {"title": "File:Sámi.jpg", "imageinfo": [{
                    "descriptionurl": "d", "url": "u", "thumburl": "t",
                    "width": 900, "height": 600, "thumbwidth": 330,
                    "thumbheight": 220, "sha1": "s",
                    "extmetadata": {"LicenseShortName": {"value": "CC0"},
                                    "Artist": {"value": "<b>X</b>"}}}]},
                "2": {"title": "File:New.jpg", "imageinfo": [{
                    "descriptionurl": "d2", "url": "u2", "width": 100,
                    "height": 100, "sha1": "s2", "extmetadata": {}}]},
                "-1": {"title": "File:Gone.jpg", "missing": ""}}}}

    import unicodedata
    nfd = unicodedata.normalize("NFD", "Sámi.jpg")
    got = t.imageinfo([nfd, "Old.jpg", "Gone.jpg"], "2026-10-13", get=get)
    assert "́" not in asked[0], "titles must go out NFC"
    assert got[nfd]["row"]["artist"] == "X" and got[nfd]["row"]["width"] == 330
    assert got["Old.jpg"]["row"]["thumb"] == "u2"
    assert got["Gone.jpg"] == {"missing": True}
