"""An editor's leaf, and the two layers it is delivered as.

`ed/page-img/` holds a master somebody made and vouches for — for `1-361`, part
1's foldout map, a ChaiNNer upscale hand-repaired where the upscaler wrecked the
legend swatches. It is tracked because nothing in this repo rebuilds it.

It is also 21 MB, which is not a thing to hand a browser, so
`tools/build_leaf_layers.py` splits it into Mixed Raster Content — a 1-bit-ish
anti-aliased linework PNG over a colour JPEG at a third scale — and the reading
view stacks those. What is tested here is the *resolution and serving* of that
pair, not the image processing: the derivation's own guarantee is that it was
scored against the authored linework it reimplements, and that check lives in the
script's docstring where the numbers are.

**The rule with teeth is both-or-neither.** Half a Mixed Raster pair still
renders, and still looks like the map — colour alone is a smear with no names,
linework alone an outline with every ethnic area gone. Either would be a
confident, wrong picture of an ethnographic map, which is the failure this whole
project is built against, so a missing half falls back to the master.
"""
from __future__ import annotations

from pathlib import Path

from conftest import write_captions

from harness import edition_ui as ui


def _exempt_lst(root: Path, *refs: str, kind: str = "map") -> None:
    """Rule these leaves. `map` by default — every fixture here is `1-361`, the
    folding tribal-distribution map, which is the one leaf with a hand-made
    master and the whole reason the Mixed Raster pair exists."""
    p = root / "gt" / "zones" / f"_{kind}.lst"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(f"chukchi-{r}.xml\n" for r in refs), encoding="utf-8")


def _master(root: Path, ref: str) -> Path:
    from PIL import Image
    p = root / ui.PAGE_IMG / f"chukchi-{ref}.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (40, 44), (200, 190, 170)).save(p)
    return p


def _layers(root: Path, ref: str, *, colour: bool = True,
            lines: bool = True) -> None:
    from PIL import Image
    d = root / ui.PAGE_IMG_LAYERS
    d.mkdir(parents=True, exist_ok=True)
    if colour:
        Image.new("RGB", (13, 15), (200, 190, 170)).save(
            d / f"chukchi-{ref}.colour.jpg")
    if lines:
        Image.new("RGBA", (40, 44), (42, 33, 24, 0)).save(
            d / f"chukchi-{ref}.lines.png")


def _raster(root: Path, ref: str) -> None:
    from PIL import Image
    p = root / "scans" / f"chukchi-{ref}.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("L", (40, 44), 255).save(p)


def _readings(root: Path) -> None:
    """No captions. The store says that by holding no FigDesc text, which a page
    with no figure ALTO already does — so this is a no-op kept for its call
    sites, where it names the precondition the test depends on."""
    write_captions(root, {})


def _app(root):
    from starlette.testclient import TestClient

    from harness.web import Sessions, create_app
    return TestClient(create_app(root, Sessions(root=root), editor="edition"))


# -- resolution ---------------------------------------------------------------

def test_both_layers_present_resolves(tmp_path):
    _exempt_lst(tmp_path, "1-361")
    _master(tmp_path, "1-361")
    _layers(tmp_path, "1-361")

    got = ui.leaf_layers("1-361", tmp_path)
    assert got is not None
    assert set(got) == {"colour", "lines"}
    assert got["colour"].name == "chukchi-1-361.colour.jpg"
    assert got["lines"].name == "chukchi-1-361.lines.png"


def test_half_a_pair_refuses(tmp_path):
    """The one that matters. A surviving half renders and lies."""
    _exempt_lst(tmp_path, "1-361")
    _master(tmp_path, "1-361")
    _layers(tmp_path, "1-361", lines=False)
    assert ui.leaf_layers("1-361", tmp_path) is None

    _layers(tmp_path, "1-361", colour=False)
    (tmp_path / ui.PAGE_IMG_LAYERS / "chukchi-1-361.colour.jpg").unlink()
    assert ui.leaf_layers("1-361", tmp_path) is None


def test_layers_without_a_master_resolve_to_nothing(tmp_path):
    """Derived files whose source has gone are not an artefact anybody vouches
    for. `leaf_source` is the gate, so the rank rule is stated once."""
    _exempt_lst(tmp_path, "1-361")
    _layers(tmp_path, "1-361")
    assert ui.leaf_layers("1-361", tmp_path) is None


def test_a_non_exempt_page_is_refused_layers_and_master_alike(tmp_path):
    """`leaf_source`'s exempt-only rule, inherited rather than restated — a leaf
    for a page the pipeline still owns must not be honoured quietly."""
    _master(tmp_path, "1-100")
    _layers(tmp_path, "1-100")
    assert ui.leaf_source("1-100", tmp_path)[0] is None
    assert ui.leaf_layers("1-100", tmp_path) is None


def test_the_pipeline_resolver_never_sees_an_editors_leaf(tmp_path):
    """`zones.scan_for` is what the segmenters, the ink checks and `fig crops`
    resolve through. A sharpened or upscaled leaf is manufactured evidence and
    must not reach anything that measures ink."""
    from harness import zones

    _exempt_lst(tmp_path, "1-361")
    _master(tmp_path, "1-361")
    _layers(tmp_path, "1-361")
    _raster(tmp_path, "1-361")

    assert zones.scan_for("1-361", tmp_path) == \
        tmp_path / "scans" / "chukchi-1-361.png"
    assert ui.leaf_source("1-361", tmp_path)[0] is not None, "the leaf is there"


# -- serving ------------------------------------------------------------------

def test_each_layer_serves_with_its_own_media_type(tmp_path):
    _exempt_lst(tmp_path, "1-361")
    _master(tmp_path, "1-361")
    _layers(tmp_path, "1-361")
    c = _app(tmp_path)

    colour = c.get("/edition/leaf/1-361/colour")
    assert colour.status_code == 200
    assert colour.headers["content-type"].startswith("image/jpeg")
    lines = c.get("/edition/leaf/1-361/lines")
    assert lines.status_code == 200
    assert lines.headers["content-type"].startswith("image/png")


def test_the_master_keeps_its_own_address(tmp_path):
    """The pair is a delivery format; the master is the artefact. A reader must
    be able to reach the thing somebody actually vouched for."""
    _exempt_lst(tmp_path, "1-361")
    _master(tmp_path, "1-361")
    _layers(tmp_path, "1-361")

    r = _app(tmp_path).get("/edition/leaf/1-361")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/png")


def test_an_unknown_layer_name_is_a_404_that_says_the_names(tmp_path):
    _exempt_lst(tmp_path, "1-361")
    _master(tmp_path, "1-361")
    _layers(tmp_path, "1-361")

    r = _app(tmp_path).get("/edition/leaf/1-361/sepia")
    assert r.status_code == 404
    assert "colour" in r.text and "lines" in r.text


def test_missing_layers_point_at_the_command_that_builds_them(tmp_path):
    _exempt_lst(tmp_path, "1-361")
    _master(tmp_path, "1-361")

    r = _app(tmp_path).get("/edition/leaf/1-361/colour")
    assert r.status_code == 404
    assert "build_leaf_layers" in r.text


# -- the page -----------------------------------------------------------------

def test_the_exempt_page_stacks_the_pair_when_it_exists(tmp_path):
    _exempt_lst(tmp_path, "1-361")
    _readings(tmp_path)
    _master(tmp_path, "1-361")
    _layers(tmp_path, "1-361")
    _raster(tmp_path, "1-361")

    text = _app(tmp_path).get("/edition/page/1-361").text
    assert "leaf-mrc" in text
    assert "/edition/leaf/1-361/colour" in text
    assert "/edition/leaf/1-361/lines" in text
    # The label is unchanged: the pair is the same made artefact, and the scan
    # is still the evidence beside it. All three addresses are on the page —
    # what is shown, what it was built from, and what neither may change.
    assert "editor's version" in text
    assert "/edition/page/1-361.png" in text
    assert "/edition/leaf/1-361'" in text, "the master is reachable from the page"


def test_a_master_with_no_layers_still_shows_the_master(tmp_path):
    """The fallback, and it must be the whole leaf rather than nothing — the
    reason `leaf_layers` may return None at all."""
    _exempt_lst(tmp_path, "1-361")
    _readings(tmp_path)
    _master(tmp_path, "1-361")
    _raster(tmp_path, "1-361")

    text = _app(tmp_path).get("/edition/page/1-361").text
    assert "leaf-mrc" not in text
    assert "/edition/leaf/1-361'" in text or '/edition/leaf/1-361"' in text


def test_a_plain_exempt_page_is_untouched_by_any_of_this(tmp_path):
    _exempt_lst(tmp_path, "1-050")
    _readings(tmp_path)
    _raster(tmp_path, "1-050")

    text = _app(tmp_path).get("/edition/page/1-050").text
    assert "leaf-mrc" not in text
    assert "editor's version" not in text
    assert "/edition/page/1-050.png" in text
