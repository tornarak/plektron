"""Shapes to an inline SVG map. No map library, no tiles, no network.

The same constraint every other view here works under, and it suits the
material: the polygons *are* the content, there is no imagery to fetch, and a
tile server would make the reading view depend on somebody else's uptime to
show a river. One `<svg>` with a `viewBox`, shapes as `<path>`, every
coordinate projected on the server.

**Lambert azimuthal equal-area, centred per map on its own subject.** Two
reasons, and neither is taste.

The first is the antimeridian. A longitude-as-x projection tears every shape
that crosses 180 into two halves at opposite edges — Chukotka, which is most of
this book. The store already normalizes longitudes into one continuous window
so a *planar* library can work on them (see `tools/build_geo.py`), and an
azimuthal projection then closes the question for good: it goes through
`sin`/`cos` of longitude, which are periodic, so 185 and −175 project to the
same point and no window convention can leak into the picture.

The second is that equal-area makes the one comparison a reader actually makes
— this basin against that one, inside the same frame — mean what it looks like.
A conformal or plate-carrée map at 65°N would show the northern half of a basin
half again too large.

Centred per map rather than once for the store, because the store spans 137
degrees of longitude: a single centre would put the Amur 60 degrees off-axis
and visibly shear it. Nothing compares two separately-framed maps, so there is
nothing to lose by it.

Sized in nothing. Every map's `viewBox` is the same 1000-unit square and the
element carries no width or height, so a map fills whatever the card or the
column gives it — the same discipline as `tei_html.crop_style`, and for the
same reason: a dimension in pixels is a guess about a panel this module cannot
see. Normalizing the frame rather than emitting projected radians is also what
lets one decimal place be enough at every zoom.
"""
from __future__ import annotations

import math
from html import escape

from . import geo

#: Layer order, back to front, with the class each gets. Order is the whole of
#: the legibility: the subject drawn under its own siblings would be lost.
LAYERS = ("land", "lakes", "kin", "members", "parent", "subject", "rivers")

#: Padding around the framed extent, as a fraction of the larger dimension. A
#: shape flush against the frame reads as clipped — which, for `langarea:chuk1273`,
#: it genuinely is, and that is the one case a reader must not confuse with
#: framing.
PAD = 0.06

#: Below this many projected units across, a frame is widened to it. A single
#: point has no extent at all, and a village would otherwise be rendered at
#: infinite zoom onto a blank field.
MIN_SPAN = 0.02


def project(lon: float, lat: float, lon0: float, lat0: float):
    """Lambert azimuthal equal-area, in radians of the unit sphere.

    Returns `None` for the antipode of the centre, where the projection is
    undefined. Nothing in this store is 180 degrees from its own subject, so
    this is a guard rather than a case — but an unguarded `sqrt` of a negative
    would raise from inside a page render, which is the wrong place to find out.
    """
    p, p0 = math.radians(lat), math.radians(lat0)
    dl = math.radians(lon - lon0)
    denom = 1 + math.sin(p0) * math.sin(p) + math.cos(p0) * math.cos(p) * math.cos(dl)
    if denom <= 1e-12:
        return None
    k = math.sqrt(2.0 / denom)
    return (k * math.cos(p) * math.sin(dl),
            # SVG's y grows downward and latitude grows upward, so the sign is
            # flipped here rather than in every caller.
            -k * (math.cos(p0) * math.sin(p)
                  - math.sin(p0) * math.cos(p) * math.cos(dl)))


def centre_of(box) -> tuple[float, float]:
    w, s, e, n = box
    return ((w + e) / 2.0, (s + n) / 2.0)


def union_box(boxes):
    boxes = [b for b in boxes if b]
    if not boxes:
        return None
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


#: Every map's viewBox is this many units square, whatever it frames.
#:
#: **The alternative couples precision to zoom and gets one of them wrong.**
#: Emitting projected radians at a fixed number of decimals gives a
#: continent-wide frame more resolution than any screen and a small basin about
#: two hundred steps across, which is visibly faceted. Normalizing first means
#: one decimal place is right everywhere: 10,000 addressable positions across
#: a box no browser will render wider than a couple of thousand pixels.
SPAN = 1000.0

#: Half a viewBox's worth of margin before a ring is dropped as off-frame. Not
#: zero: a ring whose vertices all sit outside can still cross the frame, and
#: dropping it would punch a hole in the coastline exactly where the map is.
CULL = 1.0


def _fmt(v: float) -> str:
    return f"{v:.1f}".rstrip("0").rstrip(".")


def _path(points, close: bool) -> str:
    if not points:
        return ""
    d = "M" + " L".join(f"{_fmt(x)},{_fmt(y)}" for x, y in points)
    return d + ("Z" if close else "")


class Frame:
    """A projection centre plus the projected extent it draws into."""

    def __init__(self, box, lon0=None, lat0=None):
        self.lon0, self.lat0 = (lon0, lat0) if lon0 is not None else centre_of(box)
        xs, ys = [], []
        w, s, e, n = box
        # The corners alone under-report a curved edge, so the frame is measured
        # along the box rather than at its four points: at these latitudes the
        # top edge of a wide box bows well past its own corners, and a frame
        # taken from the corners clips the very shape it was computed for.
        steps = 24
        for i in range(steps + 1):
            t = i / steps
            for lon, lat in ((w + (e - w) * t, s), (w + (e - w) * t, n),
                             (w, s + (n - s) * t), (e, s + (n - s) * t)):
                p = project(lon, lat, self.lon0, self.lat0)
                if p:
                    xs.append(p[0])
                    ys.append(p[1])
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        span = max(x1 - x0, y1 - y0, MIN_SPAN) * (1 + 2 * PAD)
        self._cx, self._cy = (x0 + x1) / 2, (y0 + y1) / 2
        self._scale = SPAN / span

    viewbox = f"0 0 {SPAN:.0f} {SPAN:.0f}"

    def _at(self, lon: float, lat: float):
        """Projected, then normalized into the viewBox. `None` off the sphere."""
        p = project(lon, lat, self.lon0, self.lat0)
        if p is None:
            return None
        return (SPAN / 2 + (p[0] - self._cx) * self._scale,
                SPAN / 2 + (p[1] - self._cy) * self._scale)

    def _ring(self, ring):
        """One ring's points, or `None` if it cannot touch the frame.

        The cull is the difference between a 130 KB card and an 8 KB one: a map
        of the Wolverine was carrying every coastline in the store, clipped by
        the browser after being serialized in full.
        """
        pts = []
        for lon, lat in ring:
            p = self._at(lon, lat)
            if p is not None:
                pts.append(p)
        if not pts:
            return None
        lo, hi = -CULL * SPAN, (1 + CULL) * SPAN
        if (max(x for x, _ in pts) < lo or min(x for x, _ in pts) > hi
                or max(y for _, y in pts) < lo or min(y for _, y in pts) > hi):
            return None
        return pts

    def paths(self, doc: dict, close=True) -> list[str]:
        out = []
        for ring in geo.rings(doc):
            pts = self._ring(ring)
            if pts and (d := _path(pts, close)):
                out.append(d)
        return out

    def rivers(self, doc: dict) -> list[tuple[str, int]]:
        out = []
        for line, sorder in geo.lines(doc):
            pts = self._ring(line)
            if pts and (d := _path(pts, close=False)):
                out.append((d, sorder))
        return out

    def point(self, lon: float, lat: float):
        return self._at(lon, lat)


CSS = """
svg.map { width:100%; height:auto; display:block; background:var(--sea);
  border:1px solid var(--rule); border-radius:.3rem }
svg.map .land { fill:var(--land); stroke:none }
svg.map .lakes { fill:var(--sea); stroke:none }
svg.map .kin { fill:none; stroke:var(--dim); stroke-width:.15%; opacity:.5 }
svg.map .members { fill:color-mix(in srgb,var(--accent) 8%,transparent);
  stroke:var(--accent); stroke-width:.18%; opacity:.75 }
svg.map .parent { fill:none; stroke:var(--dim); stroke-width:.25%;
  stroke-dasharray:1%,.8% }
svg.map .subject { fill:color-mix(in srgb,var(--accent) 22%,transparent);
  stroke:var(--accent); stroke-width:.35% }
svg.map .rivers { fill:none; stroke:var(--water); stroke-width:.22%;
  stroke-linecap:round; opacity:.85 }
svg.map .pin { fill:var(--accent); stroke:var(--card); stroke-width:.15% }
svg.map .pin-label { fill:var(--fg); font-family:system-ui,sans-serif;
  paint-order:stroke; stroke:var(--sea); stroke-width:.4%;
  stroke-linejoin:round }
"""


def render(frame: Frame, layers: dict, pins=()) -> str:
    """One map. `layers` maps a `LAYERS` name to a list of path `d` strings.

    Rivers arrive as `(d, sorder)` so the higher orders can be drawn heavier —
    the trunk should read as the trunk. `pins` are `(x, y, label)` already
    projected, which keeps the label-placement question out of here.
    """
    parts = []
    for name in LAYERS:
        got = layers.get(name)
        if not got:
            continue
        if name == "rivers":
            orders = [s for _d, s in got] or [0]
            top = max(orders)
            parts.append("<g class='rivers'>" + "".join(
                f"<path d='{d}' style='stroke-width:{0.10 + 0.10 * (s - top + 2):.2f}%'/>"
                if s >= top - 1 else f"<path d='{d}'/>"
                for d, s in got) + "</g>")
        else:
            parts.append(f"<g class='{name}'>"
                         + "".join(f"<path d='{d}'/>" for d in got) + "</g>")
    # The pin radius and the label offset are percentages of the viewBox, so a
    # marker keeps its size on the page whatever extent the frame ended up with.
    r = SPAN * 0.012
    for x, y, label in pins:
        parts.append(f"<circle class='pin' cx='{_fmt(x)}' cy='{_fmt(y)}' r='{r:.1f}'/>")
        if not label:
            continue
        # A label always sits to the right of its pin until the pin is near the
        # right edge, where it would run off — `Uelen` and `Chukchee Peninsula`
        # both did, and a truncated place name on a map reads as a data problem
        # rather than as a layout one. The flip is on the *frame*, not on the
        # text width, because this module cannot measure text.
        flip = x > SPAN * 0.72
        parts.append(
            f"<text class='pin-label' x='{_fmt(x + (-r * 1.4 if flip else r * 1.4))}' "
            f"y='{_fmt(y + r * 0.5)}' "
            f"text-anchor='{'end' if flip else 'start'}' "
            f"font-size='{r * 2.2:.1f}'>{escape(label)}</text>")
    return (f"<svg class='map' viewBox='{frame.viewbox}' "
            f"preserveAspectRatio='xMidYMid meet' role='img'>"
            + "".join(parts) + "</svg>")
