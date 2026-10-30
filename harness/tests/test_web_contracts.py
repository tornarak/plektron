"""What the browser posts, and what the server declares it will accept.

**Both halves of this contract are written by hand in two files that do not import
each other**, and nothing checked they agreed. The editors' request models were
written from memory when `webui.py` was split into `harness/web/`, and the zones
save model got three fields wrong at once — `exempt` declared a bool where the
client sends the list of exempted order rules, `anchor` where it sends `nudge`,
`figures` where it sends `figs`.

Only the first of those was loud. It made every save a 422, so `Enter` did nothing
and the editor was unusable. The other two were the dangerous kind: **Pydantic
drops undeclared fields silently**, so the save would have returned 200 while
discarding the column nudge and the entire figure track. A save that reports
success and writes less than it was given is precisely the fluent-nonsense shape
this project is arranged against.

So each case below is one endpoint's real client body — copied from the `.js` that
builds it — and the assertion is in two directions: the model must **accept** it,
and must not **drop** any of it. A field the server does not want is a field the
client should stop sending; either way the two files have to be changed together,
which is the property that was missing.

The model checks are pure — they build a request object and look at it. The route
checks at the foot go through the real router, and every one of them runs against
a `tmp_path` root: `gt/zones/` is a tracked store, and somebody may have the page
open in a browser while this suite runs.
"""
from __future__ import annotations

import pytest

from harness.web import edition as E
from harness.web import lines as L
from harness.web import review as R
from harness.web import zones as Z

ZONE = {"label": "MainZone-P", "y0": 100, "y1": 200,
        "column": 0, "x0": 307, "x1": 2085}

#: `(name, model, body the client sends, fields the consumer reads)`.
#: The last column is what the *server-side* function pulls out of the payload, so
#: a field can be listed there and absent from the body — `figs` is, deliberately.
CASES = [
    # static/js/zones.js `save()`, zone track only.
    ("zones /save", Z.Save,
     {"ref": "1-097", "split": "train", "exempt": ["order"], "nudge": 4,
      "ink_exempt": [{"y0": 10, "y1": 20}], "zones": [ZONE]},
     ("ref", "split", "exempt", "nudge", "ink_exempt", "zones")),
    # …and with the figure track touched, which adds three more keys.
    ("zones /save +figs", Z.Save,
     {"ref": "1-097", "split": "train", "exempt": [], "nudge": 0,
      "ink_exempt": [], "zones": [ZONE], "fig_ids": "gt",
      "fig_exempt": {"captions-lte-figures": "the plate's parts share one caption"},
      "figs": [{"id": "f1", "label": "GraphicZone",
                "x0": 1, "y0": 2, "x1": 3, "y1": 4}]},
     ("figs", "fig_ids", "fig_exempt")),
    # static/js/zones.js, the single-page segmenter run.
    ("zones /predict", Z.Predict,
     {"ref": "1-097", "force": True, "single": True}, ("ref", "force", "single")),
    # static/js/zones-list.js, the sweep — no `single`.
    ("zones /predict (list)", Z.Predict,
     {"ref": "1-097", "force": False}, ("ref", "force")),
    ("zones /delete", Z.Delete, {"ref": "1-097"}, ("ref",)),
    # static/js/lines.js `save()`.
    ("lines /save", L.Save,
     {"ref": "1-097", "lines": [{"y0": 1}], "ink_exempt": [{"y0": 2}],
      "withdraw": False},
     ("ref", "lines", "ink_exempt", "withdraw")),
    # static/js/review.js `save()` — `lines` is an object keyed by line number.
    ("review /save", R.Save,
     {"ref": "1-080", "lines": {"1": {"text": "a", "note": ""}}},
     ("ref", "lines", "withdraw")),
    ("review /done", R.Done, {"ref": "1-080"}, ("ref",)),
    # static/js/ratify.js.
    ("edition /ratify", E.Ratify, {"id": "place:markova"}, ("id",)),
    # No JS posts this one today; the fields are `edition_ui._new`'s.
    ("edition /entity/new", E.NewEntity,
     {"id": "place:x", "canonical": "X", "aliases": ["X"]},
     ("id", "canonical", "aliases")),
]


@pytest.mark.parametrize("name,model,body,reads",
                         CASES, ids=[c[0] for c in CASES])
def test_the_model_accepts_what_the_client_sends(name, model, body, reads):
    """The loud half. A rejected field is a 422 and a dead editor."""
    model(**body)


@pytest.mark.parametrize("name,model,body,reads",
                         CASES, ids=[c[0] for c in CASES])
def test_the_model_drops_nothing_the_client_sends(name, model, body, reads):
    """The quiet half, and the one worth having. An undeclared field does not
    raise — it vanishes, and the save returns 200 having written less than it was
    handed."""
    got = model(**body).model_dump()
    assert sorted(set(body) - set(got)) == []


@pytest.mark.parametrize("name,model,body,reads",
                         CASES, ids=[c[0] for c in CASES])
def test_the_model_carries_what_the_server_reads(name, model, body, reads):
    """The third direction: a field the consumer looks for and the model never
    declares can only ever be its default. `_new` reading `aliases` off a model
    that had no such field is how an entity would have been written with the
    placeholder alias row and looked finished."""
    missing = [f for f in reads if f not in model.model_fields]
    assert missing == [], f"{name}: consumer reads {missing}, model declares none"


def test_an_untouched_figure_track_sends_no_figs_key():
    """**Presence is the signal, so the default must not be a value.**
    `zones_ui.save_payload` asks `"figs" not in payload` to decide whether the
    figure store is touched at all — because `zones blot` keys its training
    rasters off `gt/fig/`'s mtimes, and rewriting 252 identical files during
    ordinary zone keying would stale every one of them.

    A `list[dict] = []` default would put the key in every dump. On a figure-less
    page that is worse than wasteful: the store refuses an empty figure file on
    purpose ("absence of the file is how this store records 'no figures here'"),
    so the save would fail outright on the ordinary case.
    """
    body = {"ref": "1-097", "split": "train", "exempt": [], "nudge": 0,
            "ink_exempt": [], "zones": [ZONE]}
    assert "figs" not in Z.Save(**body).model_dump(exclude_unset=True)
    touched = Z.Save(**body, figs=[]).model_dump(exclude_unset=True)
    assert "figs" in touched and touched["figs"] == []


def test_the_save_route_dumps_only_what_was_set():
    """The route's half of the pair above. `model_dump()` without
    `exclude_unset` reinstates every default and undoes it."""
    import inspect
    src = inspect.getsource(Z.save)
    assert "exclude_unset=True" in src


# --- through the route, not past it ------------------------------------------
#
# The existing zones tests call `save_payload` directly, which is exactly why a
# broken request model went unnoticed: every one of them passed while `Enter` in
# the browser returned a 422. These go through the router, so the model is in the
# path.


def _app(root):
    """The app over a temp root, with the committed zone config copied in.

    The route resolves its config from the root it serves — `_cfg(request)` — which
    the direct-call tests sidestep by handing `save_payload` the repo's config
    themselves. Copying the real file rather than writing a stub keeps this
    honest: the shapes under test are the ones the editor is configured with.
    """
    import shutil
    from pathlib import Path

    from starlette.testclient import TestClient

    from harness.web import Sessions, create_app
    repo = Path(__file__).resolve().parent.parent.parent / "jesup" / "bogoras-chukchi"
    (root / "config").mkdir(parents=True, exist_ok=True)
    shutil.copy(repo / "config" / "zones.json", root / "config")
    return TestClient(create_app(root, Sessions(root=root), editor="zones"))


def test_a_zone_save_goes_through_the_route_and_writes(tmp_path):
    """The end-to-end the editor actually performs. `nudge` is non-zero because it
    was one of the fields the old model dropped: the save returned 200 and the
    column offset went nowhere."""
    from test_zones_ui import scans

    from harness import zones as zn
    scans(tmp_path, "1-048")
    r = _app(tmp_path).post("/zones/save", json={
        "ref": "1-048", "split": "eval", "exempt": ["rank-monotone"], "nudge": 4,
        "ink_exempt": [], "zones": [{"label": "MainZone-P", "y0": 600, "y1": 900,
                                     "column": 0, "x0": 307, "x1": 2085}]})
    assert r.status_code == 200, r.text
    assert zn.has_zones("1-048", tmp_path)
    assert zn.load_splits(tmp_path) == {"1-048": "eval"}
    assert zn.load_exempt(tmp_path) == {"1-048": ["rank-monotone"]}


def test_a_zone_save_leaves_the_figure_store_alone(tmp_path):
    """No `figs` key, no trace in `gt/fig/`. The store is not read, not written and
    not stamped — `zones blot` keys the segmenter's training rasters off its
    mtimes, so an ordinary zone save that touched it would stale all 252."""
    from test_zones_ui import scans
    scans(tmp_path, "1-048")
    r = _app(tmp_path).post("/zones/save", json={
        "ref": "1-048", "split": "train", "exempt": [], "nudge": 0,
        "ink_exempt": [], "zones": [{"label": "MainZone-P", "y0": 600, "y1": 900,
                                     "column": 0, "x0": 307, "x1": 2085}]})
    assert r.status_code == 200, r.text
    assert not (tmp_path / "gt" / "fig").exists()
    # And the response says nothing about figures, since none were considered.
    assert "figs_saved" not in r.json()


def test_the_write_endpoints_can_answer_in_json():
    """**A refusal that cannot be read is a refusal that did not happen.**
    `errors.install` returns `{"error": …}` only for endpoints marked `@fetched`,
    and every write endpoint was unmarked — so the domain refusals these stores
    raise ("no zoning", "boxes lie in no zone", and now the withdrawal guards)
    came back as an HTML 500. `lines.js` parsed the body before checking the
    status and `zones.js` parsed it on the error path, so both turned the message
    into a JSON parse error.

    The clients `fetch` these; none of them is navigated to.

    **Derived from the routers, not listed.** The list version named five
    endpoints across three editors, and the edition editor — added last — had
    neither of its writes marked and appeared in neither the fix nor this gate.
    A hand-list cannot catch the editor nobody remembered, which is the only way
    this defect has ever occurred. Three `/done` routes were unmarked too, all
    three `fetch`ed by their clients.

    Scoped to the **editors'** routers. `shell`'s `/session/{editor}` and `/stop`
    are the process's, not an editor's, and `/session` is posted by the CLI's
    handoff rather than by a page.
    """
    from harness.web import EDITORS, errors, load_editors
    load_editors()
    unmarked = []
    for ed in EDITORS.values():
        for route in ed.router.routes:
            if "POST" not in (getattr(route, "methods", None) or set()):
                continue
            if not getattr(route.endpoint, "__web_fetched__", False):
                unmarked.append(f"{ed.name}{route.path}")
    assert unmarked == [], f"POST endpoints not marked @fetched: {unmarked}"
    # The mark is read off the resolved endpoint, so it has to survive the
    # decorator order the routes are written in.
    assert errors.fetched is not None
