"""The print boundary. Nothing here knows what a page is.

Every verb's payload is either a flat uniform table (the ledger, detector flags,
ToC hits) or one nested record (the page context). TOON encodes the first as a
header row plus data rows and the second as YAML-ish indentation, which is a
3-16x reduction over `json.dumps(indent=2)` on this repo's real payloads — the
ledger measured 127,646 bytes as indented JSON.

Two rules follow from how the tabular collapse works, and both are load-bearing
upstream rather than here:

  - Records in a list must have **identical key sets**. A ragged list silently
    degrades to the verbose nested form; it does not error. This is why the
    ledger is a list of records carrying `ref` as a field rather than a dict
    keyed by ref, and why the detectors emit one `token` key rather than
    `span` for some flag types and `token` for others.
  - Values containing the delimiter are quoted by the encoder, so Tier-1 spans
    survive a round trip intact.

`--json` exists on every verb because `toon-format` is beta and says its API may
change before 1.0. Anything that needs to parse harness output as a contract
should pass it; the human- and model-facing default is TOON.
"""
from __future__ import annotations

import json

from toon_format import encode


def emit(obj, as_json: bool = False) -> str:
    """Serialize a payload for stdout. TOON unless `as_json`."""
    if as_json:
        return json.dumps(obj, ensure_ascii=False, indent=2)
    return encode(obj)


def emit_lines(items) -> str:
    """Bare newline-separated values, for payloads that are pipe targets.

    `ledger --untranscribed` is a work queue someone pipes into xargs, not a
    document. Structure would be in the way.
    """
    return "\n".join(str(i) for i in items)
