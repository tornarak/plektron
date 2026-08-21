"""Routes for the adjudication queue, `harness ocr review`.

The judgement stays in `harness/review.py`: what a span is, what a decision
means, and the guard that a save names the page it belongs to. What moved here
is the routing, and what moved to `templates/review/page.html` is the markup.

**The crops are a route now.** They are files on disk under
`review/<ref>/crops/`, one PNG per line, and they were base64'd into a `<style>`
block — 311 KB on 1-021, re-sent uncached on every navigation — because the old
handler had exactly one image route and no way to address one. That is the whole
reason the inlining existed, and it goes away with the constraint.
"""
from __future__ import annotations

import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .. import review as rv
from ..context import norm_ref
from ..lines import raster_path
from ..paths import crops_dir, decisions_path
from . import Editor, register, templates
from .errors import fetched
from .files import send_file

BASE = "/review"
router = APIRouter()


def _session(request: Request) -> dict:
    return request.app.state.sessions.get("review")


def _root(request: Request) -> Path:
    return Path(request.app.state.root)


def _queue(request: Request) -> list[str]:
    return list(_session(request).get("queue") or [])


def _state(request: Request) -> list[dict]:
    """**Adjudicated-ness is read off the disk, never held in memory.**

    A page is done when its `decision.json` exists, which is a fact
    `save_decisions` establishes and a reload, a second tab, a back button or a
    restart cannot contradict. The alternative — a set of finished refs in this
    process — is state the browser can disagree with, and the disagreement would
    express itself as the server writing one page's adjudicated text into
    another page's file.
    """
    root = _root(request)
    return [{"ref": r, "done": decisions_path(r, root).exists()}
            for r in _queue(request)]


def _in_queue(request: Request, ref: str) -> str:
    """Only refs this session was asked for.

    Not a security boundary — it is loopback — but a URL naming a page nobody
    queued would render a review whose Done button belongs to another session.
    """
    try:
        r = norm_ref(ref)
    except ValueError:
        raise HTTPException(404, f"{ref!r} is not a PP-NNN ref") from None
    if r not in _queue(request):
        raise HTTPException(404, f"{r} is not in this review session "
                                 f"({', '.join(_queue(request))})")
    return r


def _render(request: Request, ref: str):
    s = _session(request)
    ctx = rv.page_context(ref, s.get("alto_dir") or "", _root(request),
                          queue=_state(request),
                          scan_href=f"{BASE}/scan/{ref}",
                          crop_base=f"{BASE}/crop/{ref}",
                          font=s.get("font"), font_size=s.get("font_size"),
                          box_lines=s.get("box_lines"))
    return templates.TemplateResponse(request, "review/page.html",
                                      {**ctx, "base": BASE, "static": "/static"})


@router.get("/")
def index(request: Request):
    """Bare `/` is "wherever this session is up to": the first page still wanting
    a decision, falling back to the first page when every one already has them —
    a session opened over finished work must still show something rather than
    404."""
    state = _state(request)
    if not state:
        raise HTTPException(404, "no review session — start one with "
                                 "`harness ocr review PP-NNN`")
    cur = next((q["ref"] for q in state if not q["done"]), state[0]["ref"])
    return _render(request, cur)


@router.get("/p/{ref}")
def page(request: Request, ref: str):
    return _render(request, _in_queue(request, ref))


def _issues(request: Request) -> list[dict]:
    return list(_session(request).get("issues") or [])


@router.get("/issues")
def issues(request: Request):
    """The distributed page: every listed line, across pages, in one document.

    Guarded rather than forbidden — `review.issues_context`'s header says which
    guards and what they are for.
    """
    items = _issues(request)
    if not items:
        raise HTTPException(404, "no issue list in this session — start one with "
                                 "`harness ocr review --issues -`")
    s = _session(request)
    ctx = rv.issues_context(items, s.get("alto_dir") or "", _root(request),
                            crop_base=f"{BASE}/crop",
                            font=s.get("font"), font_size=s.get("font_size"),
                            box_lines=s.get("box_lines"))
    return templates.TemplateResponse(request, "review/issues.html",
                                      {**ctx, "base": BASE, "static": "/static"})


@router.get("/scan/{ref}")
def scan(request: Request, ref: str):
    r = _in_queue(request, ref)
    return send_file(request, raster_path(r, _root(request)),
                     missing=f"no raster for {r} — scans/ is derived; render it "
                             "with tools/extract_scans.py over pdfs/")


@router.get("/crop/{ref}/{name}")
def crop(request: Request, ref: str, name: str):
    """One line's crop, off disk.

    Matched against the directory's own listing rather than sanitized, in the
    shape the other editors use: nothing here depends on having thought of every
    escape. `FileResponse` sets the validators, so the second visit to a page is
    free where the base64 version re-sent every crop every time.
    """
    r = _in_queue(request, ref)
    d = crops_dir(r, _root(request))
    p = d / name
    if name not in {q.name for q in d.glob("*.png")}:
        raise HTTPException(404, f"no crop {name!r} for {r}")
    return send_file(request, p)


class Save(BaseModel):
    """The page says which ref it is, and the server writes where it is told.

    `ref` is required rather than defaulted to "the current page": a current page
    is state the browser can contradict — a second tab, a back button, a reload
    after navigating — and the failure it would produce is one page's adjudicated
    text written into another's `decision.json`. That is the session-restore
    incident, and this field is the guard against it.
    """

    ref: str
    lines: dict = Field(default_factory=dict)
    #: "I mean to clear this page's adjudication." Never sent by the page — no
    #: workflow clears a decision file — so it exists to make the store's refusal
    #: overridable by a caller that means it, and to keep an empty payload from
    #: meaning it by accident.
    withdraw: bool = False


class Done(BaseModel):
    ref: str = ""


@router.post("/save")
@fetched
def save(request: Request, body: Save):
    cur = _in_queue(request, body.ref)
    res = rv.save_decisions(cur, body.lines, _root(request),
                            stamp=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                            withdraw=body.withdraw)
    edited = ",".join(map(str, res["edited_lines"])) or "none"
    changed = (f" · changed this save: {','.join(map(str, res['changed_lines']))}"
               if res["changed_lines"] else "")
    print(f"saved {res['path']}: {res['edited']}/{res['lines']} edited "
          f"(lines {edited}){changed}")
    return res


class Edit(BaseModel):
    ref: str
    index: int
    text: str
    #: The text the server sent for this field. See `review.patch_decisions`.
    prior: str = ""
    #: The ruling. Required on every listed line — that is what the flag asked for.
    note: str = ""


class PatchBody(BaseModel):
    edits: list[Edit] = Field(default_factory=list)


@router.post("/issues/save")
@fetched
def issues_save(request: Request, body: PatchBody):
    """All-or-nothing, then the store's own guards.

    Completeness is checked *here* because only the session knows what was
    listed; a payload short of the list is a half-filled form, and on a page whose
    fields belong to different files that is the one thing worth refusing outright.
    """
    listed = {(i["ref"], i["index"]) for i in _issues(request)}
    if not listed:
        raise HTTPException(404, "no issue list in this session")
    got = {(norm_ref(e.ref), e.index) for e in body.edits}
    if got != listed:
        short = sorted(f"{r}:{i}" for r, i in listed - got)
        extra = sorted(f"{r}:{i}" for r, i in got - listed)
        raise HTTPException(400, "an issue list saves whole or not at all — "
                                 + (f"missing {', '.join(short)}. " if short else "")
                                 + (f"not listed: {', '.join(extra)}. " if extra else "")
                                 + "Nothing was written.")
    unruled = sorted(f"{norm_ref(e.ref)}:{e.index}"
                     for e in body.edits if not e.note.strip())
    if unruled:
        raise HTTPException(400, f"no ruling on {', '.join(unruled)} — every "
                                 f"flagged line needs one, including 'fine'. "
                                 f"Nothing was written.")
    empty = sorted(f"{norm_ref(e.ref)}:{e.index}"
                   for e in body.edits if not e.text.strip())
    if empty:
        raise HTTPException(400, f"the reading is empty on {', '.join(empty)} — "
                                 f"a line's text is its content, and blanking it "
                                 f"is not something this page is for. Nothing was "
                                 f"written.")
    try:
        res = rv.patch_decisions([e.model_dump() for e in body.edits],
                                 _root(request),
                                 stamp=time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    except ValueError as e:
        raise HTTPException(409, str(e)) from None
    for r in res:
        changed = ",".join(map(str, r["changed_lines"])) or "none"
        print(f"patched {r['path']}: {r['edited']}/{r['lines']} edited "
              f"(changed this save: {changed})")
    return {"saved": res}


@router.post("/done")
@fetched
def done(request: Request, body: Done):
    """The page has finished with *one* ref. Whether that ends the session
    depends on what is left, and the answer comes from the disk rather than from
    the page — `save` has already written this page's decisions, so it is done by
    definition of the file.

    The next page is the first still wanting a decision in the caller's order,
    never `cur` itself — so a page reached out of order from the strip hands back
    to the front of what is left instead of skipping everything before it.
    """
    queue = _queue(request)
    try:
        cur = norm_ref(body.ref) if body.ref else (queue[0] if queue else "")
    except ValueError:
        cur = queue[0] if queue else ""
    state = {q["ref"]: q["done"] for q in _state(request)}
    nxt = next((r for r in queue if r != cur and not state.get(r)), None)
    if nxt:
        print(f"{cur} adjudicated -> next {nxt}")
        return {"next": nxt}
    # Last one. Stop, so nobody has to hunt the process afterwards: a server left
    # bound to a page that has since been restored is how a later save lands on
    # stale text.
    server = request.app.state.server
    if server is not None:
        server.should_exit = True
    return {"next": None}


register(Editor(name="review", port=8731, home="/", router=router))
