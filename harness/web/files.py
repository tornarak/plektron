"""Serving a file off disk so the second request for it is free.

**`FileResponse` does not do conditional responses.** It sets `ETag` and
`Last-Modified`, which looks like enough and is not: the check against
`If-None-Match` lives in `StaticFiles` and nowhere else, so a bare `FileResponse`
sends the whole body every time however good its validators look. Every image
route in this package is a `FileResponse` — the page rasters, the blots, the
review crops — and each of them was quietly re-sending megabytes on a reload.

That is the same shape as the bug it was introduced to fix, one layer down: the
review page stopped inlining its crops as base64, and would have gone on
re-transferring them anyway, with a header saying it need not.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, Response

# Echoed back on a 304 because a validator the client is not re-told is a
# validator it may drop; `cache-control` is included so a reload keeps
# revalidating rather than trusting a freshness lifetime nobody set.
_KEEP = ("etag", "last-modified", "cache-control")


def send_file(request: Request, path: Path, media_type: str = "image/png",
              missing: str = "") -> Response:
    """One file, with a real conditional check in front of it."""
    p = Path(path)
    try:
        stat = p.stat()
    except OSError:
        raise HTTPException(404, missing or f"no file at {p}") from None

    resp = FileResponse(p, media_type=media_type, stat_result=stat)
    etag = resp.headers.get("etag")
    inm = request.headers.get("if-none-match")
    if etag and inm and etag in [t.strip().removeprefix("W/")
                                 for t in inm.split(",")]:
        return Response(status_code=304, headers={
            k: v for k, v in resp.headers.items() if k in _KEEP})
    return resp
