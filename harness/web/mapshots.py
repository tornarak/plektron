"""An entity's map as a picture, for its link preview: what the atlas pane draws
for that entity alone, rasterized.

**The composition is `static/js/geomap.js`'s and is run, not restated.** That
module is where a map is composed and nowhere else (its own header), so
`mapshot.mjs` calls its `compose` under Node, and the picture is that function's
output. Painting is the stylesheets' — `edition.css`'s light tokens and
`geomap.css` — run by headless Chromium, because they use `var()`,
`color-mix()` and `:where()`, and a rasterizer without them would need a second
copy of the styling to agree with the first.

**Batched, because a map costs a browser.** Every located entity is composed in
one Node run and painted in a few screenshots of maps stacked on one sheet,
which is seconds where one browser per entity would be minutes. `stores.mapshots`
caches the result on every input, and `build._warm` builds it before the
workers fork.

**The entity alone, framed on what holds it** (`mapshot.mjs`): the viewport is
the extent of what it is `within`, so a preview says where the place is rather
than drawing its silhouette in an empty frame, and nothing but the coast and
the entity is painted — a live pane's siblings and root outline are context a
reader can switch off, and in a picture they are only clutter. The frame is
then only grown to `W:H`.
"""
from __future__ import annotations

import io
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from .. import geo
from . import STATIC

HERE = Path(__file__).parent
SCRIPT = HERE / "mapshot.mjs"
#: Open Graph's preferred size.
W, H = 1200, 630
#: Pins and their names, scaled by this: `compose` sizes them to the pane's
#: view, and a preview is seen smaller than a pane.
PIN_GROW = 1.6
#: `compose`'s context layers around a single subject, left unpainted.
UNPAINTED = (".kin", ".parent")
#: Maps per screenshot: a sheet `SHEET * H` pixels tall stays well inside what
#: one Chromium capture holds.
SHEET = 16
BROWSERS = ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable")
#: The inputs a picture is drawn from beside the stores: the composition and
#: the paint.
CODE = (SCRIPT, STATIC / "js" / "geomap.js", STATIC / "css" / "geomap.css",
        STATIC / "css" / "edition.css")


class Unavailable(OSError):
    """A tool the pictures need is not installed."""


def _tool(*names: str) -> str:
    for n in names:
        if found := shutil.which(n):
            return found
    raise Unavailable(f"none of {', '.join(names)} on PATH: an entity's map picture "
                      "needs Node (for `geomap.js`) and Chromium (to paint it)")


def compose(root: Path, atlas: dict) -> dict[str, str]:
    """`{ident: svg}` for every entity the atlas draws something for."""
    sids = set(atlas["base"])
    for e in atlas["entities"].values():
        sids.update(e["shapes"])
        sids.update(sid for _ent, sid in e["members"])
    shapes = {s: geo.shape(s, root) for s in sorted(sids)}
    payload = json.dumps({"atlas": atlas, "shapes": shapes,
                          "ids": sorted(atlas["entities"])})
    run = subprocess.run([_tool("node"), str(SCRIPT)], input=payload.encode(),
                         capture_output=True, check=True)
    return json.loads(run.stdout)


def _fitted(svg: str) -> str:
    """The pane's `viewBox` grown to `W:H` about its centre, never cut."""
    m = re.search(r"viewBox='([^']*)'", svg)
    vx, vy, vw, vh = map(float, m.group(1).split())
    cx, cy = vx + vw / 2, vy + vh / 2
    if vw / vh < W / H:
        vw = vh * W / H
    else:
        vh = vw * H / W
    box = f"{cx - vw / 2:.1f} {cy - vh / 2:.1f} {vw:.1f} {vh:.1f}"
    return _pins(svg[:m.start(1)] + box + svg[m.end(1):], PIN_GROW)


def _pins(svg: str, k: float) -> str:
    """Every pin's radius and label scaled by `k` about the pin, by the offsets
    `geomap.render` placed them with (`PIN.dx`, `PIN.dy`, `PIN.font` times `r`)."""
    found = re.search(r"data-pin='([^']*)'", svg)
    if found is None:
        return svg
    pin = json.loads(found.group(1).replace("&quot;", '"'))

    def circle(m: re.Match) -> str:
        return f"{m.group(1)}r='{float(m.group(2)) * k:.1f}'"

    def label(m: re.Match) -> str:
        x, y, anchor, size = (float(m["x"]), float(m["y"]), m["anchor"],
                              float(m["size"]) * k)
        r = size / pin["font"]
        lx = x - r * pin["dx"] if anchor == "end" else x + r * pin["dx"]
        return (f"<text class='pin-label' data-x='{m['x']}' data-y='{m['y']}' "
                f"x='{lx:.1f}' y='{y + r * pin['dy']:.1f}' text-anchor='{anchor}' "
                f"font-size='{size:.1f}'>")
    svg = re.sub(r"(<circle class='pin'[^>]*?)r='([\d.]+)'", circle, svg)
    return re.sub(r"<text class='pin-label' data-x='(?P<x>[-\d.]+)' data-y='(?P<y>[-\d.]+)' "
                  r"x='[-\d.]+' y='[-\d.]+' text-anchor='(?P<anchor>\w+)' "
                  r"font-size='(?P<size>[\d.]+)'>", label, svg)


def _light_tokens() -> str:
    """`edition.css`'s `:root` block — the light theme, which a preview is drawn in
    whatever the reader's own setting, since it is shown on somebody else's page."""
    css = (STATIC / "css" / "edition.css").read_text(encoding="utf-8")
    return re.search(r"^:root \{.*?^\}", css, re.S | re.M).group(0)


def _sheet(svgs: list[str]) -> str:
    style = (f"{_light_tokens()}\n"
             f"{(STATIC / 'css' / 'geomap.css').read_text(encoding='utf-8')}\n"
             "html,body{margin:0;background:var(--sea)}"
             f".t{{width:{W}px;height:{H}px;overflow:hidden}}"
             f".t svg.map{{width:{W}px;height:{H}px;max-height:none;border:0}}"
             + "".join(f"svg.map {c}{{display:none}}" for c in UNPAINTED))
    tiles = "".join(f"<div class='t'>{_fitted(s)}</div>" for s in svgs)
    return f"<!doctype html><meta charset='utf-8'><style>{style}</style>{tiles}"


def paint(svgs: dict[str, str]) -> dict[str, bytes]:
    """`{ident: png}`, one screenshot per `SHEET` maps."""
    browser = _tool(*BROWSERS)
    ids = sorted(svgs)
    out: dict[str, bytes] = {}
    with tempfile.TemporaryDirectory(prefix="mapshots-") as tmp:
        t = Path(tmp)
        for start in range(0, len(ids), SHEET):
            chunk = ids[start:start + SHEET]
            page, shot = t / "sheet.html", t / "sheet.png"
            page.write_text(_sheet([svgs[i] for i in chunk]), encoding="utf-8")
            # A profile of its own: the default one may be a running browser's,
            # which would take the job and never write the file.
            subprocess.run([browser, "--headless=new", "--disable-gpu",
                            "--hide-scrollbars", f"--user-data-dir={t / 'profile'}",
                            f"--window-size={W},{H * len(chunk)}",
                            f"--screenshot={shot}", page.as_uri()],
                           capture_output=True, check=True, timeout=120)
            with Image.open(shot) as im:
                for k, ident in enumerate(chunk):
                    buf = io.BytesIO()
                    im.crop((0, k * H, W, (k + 1) * H)).convert("RGB").save(
                        buf, "PNG", optimize=True)
                    out[ident] = buf.getvalue()
    return out
