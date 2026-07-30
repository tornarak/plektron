"""Span-level review queue: two witnesses, grouped by substitution class.

The eval rebuild needs 18 pages of ground truth back, and the arithmetic of the
page decides the shape of the tool. On the two surviving hand-keyed pages,
inventory glyphs are 3.3% of characters but fall in 43.8% of lines, so
line-at-a-time review means re-reading nearly half the book to fix a thirtieth of
it. Hence spans, not lines.

The second number is why spans are then *grouped*. On `1-074`, my reading and the
CATMuS output differ in 62 places — but those 62 collapse to 26 distinct
substitution classes, and the top six cover 65%. A queue keyed on the instance
asks "is this ' really ˊ?" twelve times; a queue keyed on the class asks once and
shows you the twelve crops.

**Grouping is presentation. The tool decides nothing.** It does not rank the
witnesses, does not mark a class safe, does not suppress a difference, and never
extends a decision to an instance the human did not accept. Every span reaches
the queue; grouping only changes how they are stacked on screen.

Two display mechanisms rather than one, because a capable font does not help if
the terminal is not:

  * every span is rendered with a **codepoint breakdown** — `g̣ro` reads as
    `g, U+0323 DOT BELOW, r, o`. Environment-independent, and the only form that
    cannot silently lose a mark. This is not hypothetical: a missing U+0323 in a
    terminal is exactly how `1-074`'s `Am-g̣roˊkĭ` was first mis-keyed.
  * the browser view stacks the scan crop above the same line rendered in DejaVu
    Sans, whose single-storey `g` leaves clean space under the bowl for a dot
    below. Charis SIL is the closer match to Bogoras's serif letterforms and is
    better for comparing *shapes*, but it crowds that dot against the descender,
    and confirming a mark exists is this tool's job.

CATMuS is a witness to line geometry and to English, and to nothing else. Against
the human-collated `1-151` it produced 13 non-ASCII characters where the human had
41, and not one was an inventory glyph. So a non-ASCII span has exactly one
witness — the image — and is queued unconditionally.
"""
from __future__ import annotations
import difflib
import json
import unicodedata
from pathlib import Path

from .context import norm_ref
from .detectors import DOT_ABOVE_G, INVENTORY_CHARS, LOOKALIKES
from .lines import alto_for_lines, page_lines

CONTEXT_CHARS = 24


def _nfd(s: str) -> str:
    return unicodedata.normalize("NFD", s)


def codepoints(s: str) -> str:
    """`g̣ro` -> `g, U+0323 DOT BELOW, r, o`.

    Named marks are spelled out; printable ASCII is shown as itself, because
    `U+0072 LATIN SMALL LETTER R` for every letter buries the one that matters.
    """
    out = []
    for ch in s:
        if ch == " ":
            out.append("SPACE")
        elif ord(ch) < 128 and ch.isprintable():
            out.append(ch)
        else:
            # Full Unicode name, unabbreviated. Trimming the prefix would turn
            # "COMBINING DOT BELOW" into "DOT BELOW" and lose the one word that
            # says the mark attaches to the character before it — which is the
            # whole distinction this function exists to make visible.
            out.append(f"U+{ord(ch):04X} {unicodedata.name(ch, 'UNNAMED')}")
    return ", ".join(out)


def classify(catmus: str, claude: str) -> str:
    """Space-separated class tags for one differing span. Flat, for TOON."""
    tags = []
    both = catmus + claude
    if any(ord(c) > 127 for c in both):
        tags.append("non_ascii")
    else:
        tags.append("ascii_only")
    if any(c in INVENTORY_CHARS for c in claude):
        tags.append("inventory")
    if any(c in LOOKALIKES for c in claude):
        tags.append("lookalike_in_proposal")
    if DOT_ABOVE_G.search(claude):
        tags.append("dot_above_g_in_proposal")
    if not catmus:
        tags.append("insertion")
    elif not claude:
        tags.append("deletion")
    return " ".join(tags)


def load_proposal(ref: str, root: Path = Path(".")) -> dict[int, dict]:
    """`review/proposals/<ref>.json` -> `{index: record}`.

    A proposal, never ground truth: no glyph identity in it is adopted. Kept out
    of any directory named for truth precisely so the distinction cannot be lost
    to a path, which is how 18 pages of real ground truth were lost.
    """
    p = root / "review" / "proposals" / f"{norm_ref(ref)}.json"
    doc = json.loads(p.read_text(encoding="utf-8"))
    return {int(k): v for k, v in doc["lines"].items()}


def line_spans(catmus: str, claude: str) -> list[dict]:
    """Differing spans between two readings of one line, with local context."""
    a, b = _nfd(catmus), _nfd(claude)
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        out.append({
            "catmus": a[i1:i2],
            "claude": b[j1:j2],
            "at": j1,
            "context": b[max(0, j1 - CONTEXT_CHARS):j2 + CONTEXT_CHARS],
            "classes": classify(a[i1:i2], b[j1:j2]),
        })
    return out


def page_spans(ref: str, alto_dir: str = "end-of-eval",
               root: Path = Path(".")) -> list[dict]:
    """Every differing span on one page, one flat record each."""
    ref = norm_ref(ref)
    prop = load_proposal(ref, root)
    out = []
    for rec in page_lines(alto_for_lines(ref, alto_dir, root)):
        mine = prop.get(rec["index"])
        if mine is None:
            continue
        for sp in line_spans(rec["text"], mine["text"]):
            out.append({"ref": ref, "index": rec["index"],
                        "line_id": rec["line_id"], **sp})
    return out


def group_spans(spans: list[dict]) -> list[dict]:
    """Collapse spans to substitution classes, most frequent first.

    `instances` is a compact `index:at` list rather than nested records — a nested
    list would de-tabularize the TOON table, and the caller can rejoin against
    `page_spans` on those keys when it wants the full record.
    """
    byclass: dict[tuple[str, str], list[dict]] = {}
    for sp in spans:
        byclass.setdefault((sp["catmus"], sp["claude"]), []).append(sp)
    out = []
    for (catmus, claude), items in byclass.items():
        out.append({
            "n": len(items),
            "catmus": catmus,
            "claude": claude,
            "catmus_cp": codepoints(catmus),
            "claude_cp": codepoints(claude),
            "classes": items[0]["classes"],
            "instances": " ".join(f"{i['index']}:{i['at']}" for i in items),
        })
    out.sort(key=lambda r: (-r["n"], r["claude"]))
    return out


def _data_uri(path: Path) -> str:
    import base64
    return ("data:image/png;base64,"
            + base64.b64encode(path.read_bytes()).decode("ascii"))


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


# DejaVu Sans first, deliberately. Its single-storey `g` has a short descender, so
# a U+0323 below the bowl stays legible; Charis SIL matches Bogoras's serif
# letterforms far better and is the right choice for comparing *shapes*, but it
# crowds that dot. Confirming a mark exists is this view's job. No webfont: the
# font is installed locally and a CSS reference cannot silently substitute the way
# a missing glyph in a terminal does.
_FONT_STACK = "'DejaVu Sans', 'Charis SIL', 'Noto Sans', sans-serif"


def render_queue_html(ref: str, alto_dir: str = "end-of-eval",
                      root: Path = Path("."), crops: Path | None = None) -> str:
    """Self-contained review page for one ref. Crops embedded, no external refs.

    Every span appears. Grouping is stacking only: nothing is pre-accepted, no
    class is marked safe, and the two witnesses are shown in a fixed order with no
    visual precedence, because the tool has no opinion about which is right.
    """
    from .lines import write_line_crops
    ref = norm_ref(ref)
    crops = crops or (root / "review" / "crops")
    recs = {r["index"]: r for r in write_line_crops(ref, crops, alto_dir, root)}
    prop = load_proposal(ref, root)
    spans = page_spans(ref, alto_dir, root)
    groups = group_spans(spans)
    summ = summary(spans, len(recs))

    h = [f"<title>review {ref}</title>", "<style>",
         f":root{{--f:{_FONT_STACK}}}",
         "body{font:15px var(--f);margin:0;padding:1.5rem;max-width:1100px}",
         "h1{font-size:1.1rem;margin:0 0 .3rem}",
         ".sum{color:#555;font-size:.85rem;margin-bottom:1.4rem}",
         ".cls{border:1px solid #ccc;border-radius:6px;margin:0 0 1.1rem;padding:.7rem .9rem}",
         ".sub{font-size:1.5rem;letter-spacing:.02em}",
         ".arrow{color:#888;padding:0 .5rem}",
         ".cp{font:12px ui-monospace,monospace;color:#036;margin:.25rem 0}",
         ".tags{font:11px ui-monospace,monospace;color:#666}",
         ".inst{border-top:1px solid #eee;padding:.55rem 0;display:flex;gap:.8rem;align-items:flex-start}",
         # Crops are emitted as one CSS rule per line and referenced by class, not
         # inlined per instance. A line with six queued spans would otherwise embed
         # its own image six times; on 1-074 that was 676 KB against 60.
         ".crop{border:1px solid #ddd;background-repeat:no-repeat;"
         "background-size:contain;background-color:#fff;max-width:640px}",
         ".ctx{font-size:1.05rem}",
         ".hit{background:#ffe9a8;outline:1px solid #d9a400}",
         "textarea{font:15px var(--f);width:100%;min-height:2.4rem}",
         "@media(prefers-color-scheme:dark){body{background:#161616;color:#e6e6e6}"
         ".cls{border-color:#3a3a3a}.cp{color:#8ec7ff}.inst{border-color:#2a2a2a}"
         ".hit{background:#5c4a00;outline-color:#c9a227}"
         ".crop{filter:invert(1) hue-rotate(180deg)}}",
         "</style>"]

    # One rule per unique line crop, scaled down to fit the column while keeping
    # aspect ratio, so the div reserves the right height before the image paints.
    from PIL import Image
    used = sorted({int(p.split(":")[0]) for g in groups for p in g["instances"].split()})
    css = []
    for idx in used:
        rec = recs.get(idx)
        if rec is None:
            continue
        path = Path(rec["crop"])
        w, ht = Image.open(path).size
        scale = min(1.0, 640 / w)
        css.append(f".c{idx}{{background-image:url({_data_uri(path)});"
                   f"width:{round(w * scale)}px;height:{round(ht * scale)}px}}")
    h += ["<style>", "\n".join(css), "</style>"]
    h += [
         f"<h1>{ref} — {len(groups)} substitution classes, {summ['spans']} spans</h1>",
         "<div class=sum>"
         f"{summ['lines_identical']}/{summ['lines']} lines already identical · "
         f"{summ['inventory_spans']} spans touch inventory glyphs · "
         f"{summ['non_ascii_spans']} non-ASCII · "
         f"{summ['lookalikes_in_proposal']} lookalike traps in the proposal<br>"
         "CATMuS is a witness to geometry and English only; it produced no "
         "inventory glyph anywhere in this book, so a non-ASCII span has one "
         "witness — the image.</div>"]

    for g in groups:
        h.append("<div class=cls>")
        h.append(f"<div class=sub>{_esc(g['catmus']) or '∅'}"
                 f"<span class=arrow>→</span>{_esc(g['claude']) or '∅'}"
                 f" <span class=tags>×{g['n']}</span></div>")
        h.append(f"<div class=cp>catmus: {_esc(g['catmus_cp']) or '(nothing)'}</div>")
        h.append(f"<div class=cp>claude: {_esc(g['claude_cp']) or '(nothing)'}</div>")
        h.append(f"<div class=tags>{_esc(g['classes'])}</div>")
        for pair in g["instances"].split():
            idx, at = (int(x) for x in pair.split(":"))
            rec = recs.get(idx)
            if rec is None:
                continue
            full = _nfd(prop[idx]["text"])
            a, b = at, at + len(g["claude"])
            ctx = (_esc(full[:a]) + "<span class=hit>"
                   + (_esc(full[a:b]) or "‸") + "</span>" + _esc(full[b:]))
            h.append("<div class=inst>")
            h.append(f"<div><div class=tags>line {idx}</div>"
                     f"<div class='crop c{idx}' role=img "
                     f"aria-label='scan of line {idx}'></div></div>")
            h.append(f"<div style='flex:1'><div class=ctx>{ctx}</div>"
                     f"<textarea data-line='{idx}' spellcheck=false>{_esc(full)}</textarea>"
                     "</div>")
            h.append("</div>")
        h.append("</div>")
    return "\n".join(h)


def summary(spans: list[dict], n_lines: int) -> dict:
    """Counts worth having before deciding whether to open the queue at all."""
    lines_with = {s["index"] for s in spans}
    return {
        "lines": n_lines,
        "lines_identical": n_lines - len(lines_with),
        "spans": len(spans),
        "classes": len({(s["catmus"], s["claude"]) for s in spans}),
        "non_ascii_spans": sum(1 for s in spans if "non_ascii" in s["classes"]),
        "inventory_spans": sum(1 for s in spans if "inventory" in s["classes"]),
        "lookalikes_in_proposal": sum(
            1 for s in spans if "lookalike_in_proposal" in s["classes"]),
    }
