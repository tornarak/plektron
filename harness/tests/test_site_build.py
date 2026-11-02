"""`site build`: every published text under one landing page, rebuilt only if stale.

The direction that matters is a false skip: a stale page published with nothing to
say so. So most of what is here is what has to count as upstream, and the guard at
the end holds that set against what a build actually reads.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest
from conftest import write_project
from test_edition import draft, page
from test_edition_build import _files
from test_edition_runs import _scan
from test_entities import entry

from harness import layout
from harness.web import cache, site
from harness.web.build import build
from harness.web.site import OUT_MARK, SITE_MARK, STAMP, build_site, stale, upstream


def _publish(root: Path, value: str | None = "drafts") -> None:
    p = root / "project.json"
    rec = json.loads(p.read_text(encoding="utf-8"))
    rec.pop("publish", None)
    if value:
        rec["publish"] = value
    p.write_text(json.dumps(rec), encoding="utf-8")
    layout._project.cache_clear()


def _as_own(path: Path, stem: str) -> Path:
    """The shared helpers spell one book's stem. Under any other a page is not this
    text's at all, and the text would build empty and clean."""
    return path.rename(path.with_name(path.name.replace("chukchi-", f"{stem}-", 1)))


def _age(top: Path) -> None:
    """Everything set up so far is an hour old, so a build's mark cannot tie with it."""
    old = time.time() - 3600
    for d, dirs, files in os.walk(top):
        for n in (*dirs, *files):
            os.utime(Path(d) / n, (old, old), follow_symlinks=False)
    os.utime(top, (old, old))


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    ws = repo / "ws"
    ws.mkdir(parents=True)
    (ws / "workspace.json").write_text('{"title": "A Series"}', encoding="utf-8")
    for stem, ref in (("one", "1-021"), ("two", "1-022")):
        root = write_project(ws / f"text-{stem}", stem=stem)
        _publish(root)
        _as_own(page(root, ref, f'<pb n="1"/><p>In {stem}.</p>'), stem)
        _scan(root, ref)
        _as_own(root / "scans" / f"chukchi-{ref}.png", stem)
    (repo / "site").mkdir()
    (repo / "site" / "landing.html").write_text("<h1>Above</h1>", encoding="utf-8")
    _age(repo)
    return repo


def _states(rep) -> dict[str, str]:
    return {r["text"]: r["state"] for r in rep.rows}


ONE, TWO = "ws/text-one", "ws/text-two"


def test_both_texts_are_written_and_the_landing_page_links_both(repo, tmp_path):
    rep = build_site(repo, tmp_path / "out", jobs=1)
    assert _states(rep) == {ONE: "built", TWO: "built"}, rep.refused
    html = (tmp_path / "out" / "index.html").read_text(encoding="utf-8")
    assert "<h1>Above</h1>" in html and "A Series" in html
    assert 'href="/ws/text-one/"' in html and 'href="/ws/text-two/"' in html
    assert (tmp_path / "out" / ONE / "page" / "1-021" / "index.html").is_file()
    assert (tmp_path / "out" / TWO / "page" / "1-022" / "index.html").is_file()
    assert (tmp_path / "out" / "static" / "css" / "edition.css").is_file()
    assert (tmp_path / "out" / "static" / "css" / "landing.css").is_file()
    # The marks the landing page names, and the icon a text's own pages name.
    assert (tmp_path / "out" / "static" / "site" / "plektron.svg").is_file()
    assert (tmp_path / "out" / "favicon.ico").is_file()
    assert 'src="/static/site/plektron.svg"' in html
    page = (tmp_path / "out" / ONE / "index.html").read_text(encoding="utf-8")
    assert f'href="/{ONE}/static/site/favicon.ico"' in page
    assert (tmp_path / "out" / ONE / "static" / "site" / "favicon.ico").is_file()


def test_a_text_links_back_to_the_landing_page_and_a_plain_build_does_not(repo, tmp_path):
    build_site(repo, tmp_path / "out", jobs=1)
    assert "all editions" in (tmp_path / "out" / ONE / "index.html").read_text("utf-8")
    build(repo / "ws" / "text-one", tmp_path / "alone", base="/ws/text-one", drafts=True)
    assert "all editions" not in (tmp_path / "alone" / "index.html").read_text("utf-8")


def test_a_text_that_declares_nothing_is_not_published(repo, tmp_path):
    _publish(repo / "ws" / "text-two", None)
    rep = build_site(repo, tmp_path / "out", jobs=1)
    assert _states(rep) == {ONE: "built", TWO: "unpublished"}
    assert not (tmp_path / "out" / TWO).exists()
    assert "text-two" not in (tmp_path / "out" / "index.html").read_text("utf-8")


def test_collated_publishes_no_drafts_and_says_so_on_the_landing_page(repo, tmp_path):
    # One draft apiece, where `tei generate` writes them; only text-two shows its own.
    for t, ref in (("one", "1-023"), ("two", "1-024")):
        root = repo / "ws" / f"text-{t}"
        _as_own(draft(root, ref, '<pb n="2"/><p>A draft.</p>'), t)
        _scan(root, ref)
        _as_own(root / "scans" / f"chukchi-{ref}.png", t)
    _publish(repo / "ws" / "text-one", "collated")
    rep = build_site(repo, tmp_path / "out", jobs=1)
    assert rep.refused == []
    html = (tmp_path / "out" / "index.html").read_text("utf-8")
    assert html.count("1 machine-generated draft,") == 1
    assert not (tmp_path / "out" / ONE / "page" / "1-023").exists()
    assert (tmp_path / "out" / TWO / "page" / "1-024" / "index.html").is_file()


def test_a_second_run_rebuilds_nothing_and_force_rebuilds(repo, tmp_path):
    out = tmp_path / "out"
    build_site(repo, out, jobs=1)
    canary = out / ONE / "canary.txt"
    canary.write_text("this build's folder was not cleared")
    assert _states(build_site(repo, out, jobs=1)) == {ONE: "fresh", TWO: "fresh"}
    assert canary.exists()
    assert _states(build_site(repo, out, force=True, jobs=1)) == {ONE: "built", TWO: "built"}
    assert not canary.exists()


def test_a_store_touched_rebuilds_its_text_and_names_why(repo, tmp_path):
    out = tmp_path / "out"
    build_site(repo, out, jobs=1)
    (repo / "ws" / "text-one" / "project.json").touch()
    rep = build_site(repo, out, jobs=1)
    assert _states(rep) == {ONE: "built", TWO: "fresh"}
    why = next(r["why"] for r in rep.rows if r["text"] == ONE)
    assert why == "project.json is newer"


def test_a_shared_store_touched_rebuilds_every_text(repo, tmp_path):
    out = tmp_path / "out"
    (repo / "ws" / "edition").mkdir()
    shared = repo / "ws" / "edition" / "shared.json"
    shared.write_text("{}")
    _age(repo)
    build_site(repo, out, jobs=1)
    shared.touch()
    assert _states(build_site(repo, out, jobs=1)) == {ONE: "built", TWO: "built"}


def test_a_deleted_file_rebuilds_though_no_surviving_file_changed(repo, tmp_path):
    out = tmp_path / "out"
    gone = repo / "ws" / "text-one" / "edition" / "gone.json"
    gone.parent.mkdir(parents=True, exist_ok=True)
    gone.write_text("{}")
    _age(repo)
    build_site(repo, out, jobs=1)
    gone.unlink()
    rep = build_site(repo, out, jobs=1)
    assert _states(rep)[ONE] == "built"
    assert next(r["why"] for r in rep.rows if r["text"] == ONE) == "edition is newer"


def test_a_tie_with_the_mark_rebuilds(repo, tmp_path):
    """mtimes here are coarse (`cache.py`), so equal says nothing about order."""
    out = tmp_path / "out"
    build_site(repo, out, jobs=1)
    root = repo / "ws" / "text-one"
    t = (out / ONE / OUT_MARK).stat().st_mtime_ns
    os.utime(root / "project.json", ns=(t, t))
    assert stale(root, out / ONE, "/ws/text-one", True) == "project.json is newer"


def test_the_code_that_renders_is_upstream(repo):
    paths = set(upstream(repo / "ws" / "text-one"))
    code = layout.repo_root()
    assert code / "harness" / "web" / "build.py" in paths
    assert code / "harness" / "web" / "templates" / "edition" / "base.html" in paths
    assert code / "uv.lock" in paths
    assert not any("__pycache__" in p.parts for p in paths)
    assert code / "harness" / "tests" / "test_site_build.py" not in paths


def test_a_sibling_text_is_not_upstream(repo):
    paths = {p.resolve() for p in upstream(repo / "ws" / "text-one")}
    assert (repo / "ws" / "text-one" / "project.json").resolve() in paths
    assert (repo / "ws" / "text-two" / "project.json").resolve() not in paths


def test_a_changed_publish_setting_rebuilds(repo, tmp_path):
    out = tmp_path / "out"
    build_site(repo, out, jobs=1)
    _publish(repo / "ws" / "text-one", "collated")
    _age(repo)
    rep = build_site(repo, out, jobs=1)
    assert _states(rep) == {ONE: "built", TWO: "fresh"}
    assert "drafts setting" in next(r["why"] for r in rep.rows if r["text"] == ONE)


def test_a_refused_build_leaves_no_stamp_and_the_next_run_retries(
        repo, tmp_path, monkeypatch):
    out = tmp_path / "out"
    real = site.build

    def refusing(*a, **k):
        s = real(*a, **k)
        s.rows.append({"url": "/ws/x", "why": "a test's refusal", "from": []})
        return s
    monkeypatch.setattr(site, "build", refusing)
    rep = build_site(repo, out, jobs=1)
    assert set(_states(rep).values()) == {"refused"} and len(rep.refused) == 2
    assert not (out / ONE / STAMP).exists()
    monkeypatch.undo()
    assert _states(build_site(repo, out, jobs=1)) == {ONE: "built", TWO: "built"}


def test_an_unpublished_text_comes_down_and_a_foreign_folder_stays(repo, tmp_path):
    out = tmp_path / "out"
    build_site(repo, out, jobs=1)
    foreign = out / "ws" / "not-ours"
    foreign.mkdir()
    (foreign / "notes.txt").write_text("mine")
    _publish(repo / "ws" / "text-two", None)
    _age(repo)
    rep = build_site(repo, out, jobs=1)
    assert not (out / TWO).exists()
    assert (foreign / "notes.txt").exists()
    # Keyed by text, and the two rows for it are its removal and its census.
    assert [r["state"] for r in rep.rows if r["text"] == TWO] == ["withdrawn", "unpublished"]


def test_an_out_no_site_build_wrote_is_refused(repo, tmp_path):
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "notes.txt").write_text("mine")
    before = _files(foreign)
    with pytest.raises(ValueError, match="holds no"):
        build_site(repo, foreign, jobs=1)
    assert _files(foreign) == before


def test_an_out_inside_a_text_is_refused(repo):
    with pytest.raises(ValueError, match="which a build reads"):
        build_site(repo, repo / "ws" / "text-one" / "site", jobs=1)


def test_nothing_published_is_refused_rather_than_an_empty_site(repo, tmp_path):
    for t in ("text-one", "text-two"):
        _publish(repo / "ws" / t, None)
    with pytest.raises(ValueError, match="nothing to build"):
        build_site(repo, tmp_path / "out", jobs=1)


def test_a_published_text_in_no_workspace_is_refused(repo, tmp_path):
    (repo / "ws" / "workspace.json").unlink()
    with pytest.raises(ValueError, match="sits in no workspace"):
        build_site(repo, tmp_path / "out", jobs=1)


def test_a_bad_publish_value_is_refused(repo):
    root = repo / "ws" / "text-one"
    rec = json.loads((root / "project.json").read_text("utf-8"))
    (root / "project.json").write_text(json.dumps({**rec, "publish": "yes"}))
    layout._project.cache_clear()
    with pytest.raises(layout.ProjectError, match="`publish` must be"):
        layout.publish(root)


def test_every_store_a_build_reads_is_upstream(repo, tmp_path, monkeypatch):
    """**The rule's own guard.** A store outside `upstream` is the false skip this
    verb most has to avoid, and it would pass every other test here."""
    root = (repo / "ws" / "text-one").resolve()
    entry(root, "place:markova", status="proposed", aliases=[("Markova", True)])
    seen: set[Path] = set()
    real = cache.file_digest

    def spying(path):
        seen.add(Path(path).resolve())
        return real(path)
    monkeypatch.setattr(cache, "file_digest", spying)
    build(root, tmp_path / "out", base="/ws/text-one", drafts=True)
    assert seen, "the build read nothing through the cache: this test has gone blind"
    walked = {p.resolve() for p in upstream(root)}
    assert {p for p in seen if p.exists()} - walked == set()


def test_two_sites_build_in_one_process_through_the_pool(repo, tmp_path):
    """The pool's fork path has otherwise only ever run once per process."""
    rep = build_site(repo, tmp_path / "pooled", jobs=2)
    assert _states(rep) == {ONE: "built", TWO: "built"}, rep.refused
    build_site(repo, tmp_path / "serial", jobs=1)
    assert _files(tmp_path / "pooled") == _files(tmp_path / "serial")


def test_the_licence_text_is_the_headers_own_words_with_its_links(repo, tmp_path):
    (repo / "ws" / "text-one" / "tei").mkdir(exist_ok=True)
    (repo / "ws" / "text-one" / "tei" / "corpus-header.xml").write_text(
        '<teiHeader xmlns="http://www.tei-c.org/ns/1.0"><fileDesc><titleStmt>'
        '<title type="main">The Koryak</title><author><persName>'
        '<forename>Waldemar</forename> <surname>Jochelson</surname></persName></author>'
        '</titleStmt><publicationStmt><availability><licence target="https://x.example/">'
        '<p>Applies to <gi>p</gi> &amp; more.<!-- not for readers --> See '
        '<ref target="https://y.example/">here</ref>.</p></licence></availability>'
        '</publicationStmt><sourceDesc><biblStruct><monogr><imprint><date>1908</date>'
        '</imprint></monogr></biblStruct></sourceDesc></fileDesc></teiHeader>',
        encoding="utf-8")
    _age(repo)
    build_site(repo, tmp_path / "out", jobs=1)
    html = (tmp_path / "out" / "index.html").read_text("utf-8")
    assert "The Koryak" in html and "Waldemar Jochelson, 1908" in html
    assert 'Applies to p &amp; more. See <a href="https://y.example/">here</a>.' in html
    assert "not for readers" not in html


def test_the_marks_are_where_the_upload_rule_expects_them(repo, tmp_path):
    """`.edition-*` is what `docs/edition.md` tells an upload to leave behind."""
    build_site(repo, tmp_path / "out", jobs=1)
    marks = {p.name for p in (tmp_path / "out").rglob(".*") if p.is_file()}
    assert marks == {SITE_MARK, OUT_MARK, STAMP}
    assert all(m.startswith(".edition-") for m in marks)


def _declare_image(root: Path, stem: str, *, crop: bool = True) -> None:
    from PIL import Image
    p = root / layout.PROJECT_JSON
    rec = json.loads(p.read_text(encoding="utf-8"))
    rec["image"] = {"fig": "1-021/001", "caption": "A plate."}
    p.write_text(json.dumps(rec), encoding="utf-8")
    layout._project.cache_clear()
    if crop:
        out = root / "scans" / "fig-crops" / f"{stem}-1-021-001.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        Image.new("L", (1000, 500), 200).save(out)


def test_a_declared_image_stands_on_the_landing_page_and_links_to_its_text(repo, tmp_path):
    _declare_image(repo / ONE, "one")
    build_site(repo, tmp_path / "out", jobs=1)
    html = (tmp_path / "out" / "index.html").read_text(encoding="utf-8")
    assert 'src="/static/covers/ws-text-one.jpg"' in html and 'alt="A plate."' in html
    assert (tmp_path / "out" / "static" / "covers" / "ws-text-one.jpg").is_file()
    # And nothing for the text that declares none.
    assert "ws-text-two.jpg" not in html


def test_a_cover_comes_down_with_its_declaration(repo, tmp_path):
    _declare_image(repo / ONE, "one")
    build_site(repo, tmp_path / "out", jobs=1)
    p = repo / ONE / layout.PROJECT_JSON
    rec = json.loads(p.read_text(encoding="utf-8"))
    del rec["image"]
    p.write_text(json.dumps(rec), encoding="utf-8")
    layout._project.cache_clear()
    build_site(repo, tmp_path / "out", jobs=1)
    assert not (tmp_path / "out" / "static" / "covers" / "ws-text-one.jpg").exists()


def test_a_declared_image_with_no_crop_refuses_before_anything_builds(repo, tmp_path):
    _declare_image(repo / ONE, "one", crop=False)
    with pytest.raises(ValueError, match="fig crops"):
        build_site(repo, tmp_path / "out", jobs=1)
    assert not (tmp_path / "out" / ONE).exists()


@pytest.mark.parametrize("image", ["1-021/001", {"fig": "1-021/001"}, {"fig": "21", "caption": "x"}])
def test_a_malformed_image_is_a_manifest_error(repo, image):
    p = repo / ONE / layout.PROJECT_JSON
    rec = json.loads(p.read_text(encoding="utf-8"))
    rec["image"] = image
    p.write_text(json.dumps(rec), encoding="utf-8")
    layout._project.cache_clear()
    with pytest.raises(layout.ProjectError, match="image"):
        layout.image(repo / ONE)
    layout._project.cache_clear()


def test_the_header_says_which_licence_words_are_bold(tmp_path):
    from lxml import etree

    from harness.ns import TEI_NS
    from harness.web.stores import _header_html
    el = etree.fromstring(f'<p xmlns="{TEI_NS}">Licensed <hi rend="bold"><ref target="u">'
                          'CC BY</ref></hi>, <hi>not this</hi>.</p>')
    assert _header_html(el) == 'Licensed <strong><a href="u">CC BY</a></strong>, not this.'
    # A source is named by its `<title>`, which is bold wherever one is cited.
    el = etree.fromstring(f'<p xmlns="{TEI_NS}"><bibl><title>GeoNames</title>, a gazetteer.'
                          '</bibl></p>')
    assert _header_html(el) == '<strong>GeoNames</strong>, a gazetteer.'


def test_the_index_is_headed_by_the_books_title(repo, tmp_path):
    root = repo / ONE
    (root / "tei").mkdir(exist_ok=True)
    (root / "tei" / "corpus-header.xml").write_text(
        '<teiHeader xmlns="http://www.tei-c.org/ns/1.0"><fileDesc><titleStmt>'
        '<title type="main">A Book</title><author><persName><surname>Writer</surname>'
        '</persName></author></titleStmt></fileDesc></teiHeader>', encoding="utf-8")
    build_site(repo, tmp_path / "out", jobs=1)
    html = (tmp_path / "out" / ONE / "index.html").read_text(encoding="utf-8")
    assert "<h1>A Book</h1>" in html and "<p>Writer</p>" in html


def test_a_declared_turn_stands_a_sideways_picture_up(repo, tmp_path):
    from PIL import Image
    _declare_image(repo / ONE, "one")
    p = repo / ONE / layout.PROJECT_JSON
    rec = json.loads(p.read_text(encoding="utf-8"))
    rec["image"]["turn"] = 90
    p.write_text(json.dumps(rec), encoding="utf-8")
    layout._project.cache_clear()
    build_site(repo, tmp_path / "out", jobs=1)
    with Image.open(tmp_path / "out" / "static" / "covers" / "ws-text-one.jpg") as im:
        # 1000 x 500 on disk, so upright it is the taller way round.
        assert im.size == (500, 1000)


def test_a_cover_turns_clockwise():
    """Pillow's own `rotate` runs the other way, and a picture upside down reads as a
    bug only to whoever looks: the book's sideways plates turn clockwise."""
    import tempfile
    from io import BytesIO

    from PIL import Image

    from harness.edition_ui import _thumb
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "x.png"
        im = Image.new("L", (40, 20), 255)
        im.paste(0, (0, 0, 20, 20))               # the left half dark
        im.save(src)
        out = Image.open(BytesIO(_thumb(str(src), 0, 40, 90)))
    # Clockwise puts what was on the left at the top.
    assert out.getpixel((10, 5)) < 60 and out.getpixel((10, 35)) > 200
