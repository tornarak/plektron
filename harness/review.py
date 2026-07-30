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


# The notation keyboard, as a toggled mode. Off by default, so U+0027 — which is
# itself the spirant and pause mark (keying spec 2.1), not merely a lookalike for
# U+02CA — stays typeable. That is why this is a mode and not a remap.
#
# The first block is the editor's existing bindings, reproduced key for key so
# muscle memory survives. Note `r`/`R` is deliberately asymmetric (ṛ vs ř) and is
# left as found rather than regularised.
KBD_GLYPHS = {
    "a": "ᴀ", "e": "ᴇ", "i": "ɪ", "c": "č", "g": "g̣", "j": "ǰ",
    "l": "ʟ", "n": "ñ", "r": "ṛ", "R": "ř",
    "'": "ˊ", "<": "ᵋ", ">": "˙", "?": "(??/????)",
    # Atomics the editor's list flagged as having no key.
    "o": "ɵ", ";": "ᵉ",
    # Capitals, likewise unreachable before. Composed, so they are NFD by
    # construction rather than by remembering to normalize.
    "C": "Č", "G": "G̣", "N": "Ñ", "L": "ʟ̣",
}

# Postfix combining marks: they attach to whatever precedes the caret, so one key
# each reaches every marked sort in keying spec 2.2 — ä ë ê ḷ ʟ̣ š ŭ x˙ and both
# length marks — instead of a binding per glyph. This is also exactly the corpus's
# own encoding, so what is typed is what is stored.
KBD_MARKS = {
    ".": "̣", "^": "̂", "~": "̃",
    ":": "̈", '"': "̌", "-": "̄", "=": "̆",
}

# Decomposed at the source, not left to the save to fix. Seven of the literals above
# are precomposed if written naively (č U+010D, ñ U+00F1, ṛ U+1E5B, ř U+0159, ǰ, Č,
# Ñ), so typing them would put precomposed characters on screen and in the palette's
# codepoint tooltips while the entire corpus is NFD. `save_decisions` would still
# normalize the file, which is exactly what makes the discrepancy easy to miss.
KBD_GLYPHS = {k: unicodedata.normalize("NFD", v) for k, v in KBD_GLYPHS.items()}

# The palette is the whole keying-spec inventory, not just what has a binding —
# grouped as the spec groups it so the panel reads as the inventory rather than as a
# pile of characters. Bindings are a shortcut for the frequent ones; the button is
# the guarantee that nothing is unreachable.
#
# The ASCII row earns its place despite being typeable: U+0027 is the spirant *and*
# pause mark, U+002D the connector hyphen, U+0021 increased articulation (2.1). They
# look like ordinary punctuation and are not, and clicking them works even with the
# mode on, which is otherwise the one way to reach U+0027 without toggling.
PALETTE = [
    ("small caps (2.3)", ["ᴀ", "ᴇ", "ɪ", "ʟ", "ʟ̣"]),
    ("modifiers (2.1)", ["ˊ", "ᵋ", "ᵉ", "˙"]),
    ("combining marks", list(KBD_MARKS.values())),
    ("marked sorts (2.2)",
     ["ñ", "č", "š", "ř", "ǰ", "ê", "ë", "ä", "ŭ", "ṛ", "ḷ", "ɵ", "x˙", "g̣"]),
    # Convenience only, and labelled so it cannot be mistaken for inventory: the
    # spec lists no capital rows. G̣ is attested (1-074's G̣ɪthaˊk) and Č occurs in the
    # corpus; Š Ř J̌ are here because a base plus a mark key produces them anyway, not
    # because anything has licensed them.
    ("capitals (composed, not spec rows)", ["Ñ", "Č", "Š", "Ř", "J̌", "G̣"]),
    ("ascii, special function", ["'", "-", "!"]),
    ("catalogue placeholder", ["(??/????)"]),
]
PALETTE = [(label, [unicodedata.normalize("NFD", g) for g in glyphs])
           for label, glyphs in PALETTE]


def decisions_path(ref: str, root: Path = Path(".")) -> Path:
    return root / "review" / "decisions" / f"{norm_ref(ref)}.json"


def load_decisions(ref: str, root: Path = Path(".")) -> dict[int, dict]:
    """Adjudicated lines saved so far, `{index: record}`. Empty if none."""
    p = decisions_path(ref, root)
    if not p.exists():
        return {}
    doc = json.loads(p.read_text(encoding="utf-8"))
    return {int(k): v for k, v in doc.get("lines", {}).items()}


def save_decisions(ref: str, lines: dict, root: Path = Path("."),
                   stamp: str | None = None) -> dict:
    """Write adjudicated lines, recording for each whether it differs from the proposal.

    `edited` is computed here rather than trusted from the client, because it is the
    eval's primary signal — the fraction of proposed lines a human let stand — and a
    number the thing being measured gets to report about itself is worthless.

    NFD on the way in. Browsers submit whatever normal form the keyboard produced,
    and this corpus is NFD by policy (keying spec section 1); an unnormalized save
    would reintroduce exactly the mixed-encoding drift `harness normalize` exists to
    remove.

    Written temp-then-rename so an interrupted save cannot truncate the file, and
    the previous version is kept alongside. Cheap, and this repo has already lost
    18 pages of transcription once.
    """
    ref = norm_ref(ref)
    prop = load_proposal(ref, root)
    out = {}
    for k, v in lines.items():
        idx = int(k)
        text = _nfd(v if isinstance(v, str) else v.get("text", ""))
        proposed = _nfd(prop[idx]["text"]) if idx in prop else None
        out[str(idx)] = {"text": text, "edited": proposed is not None
                         and text != proposed}
    doc = {"ref": ref,
           "proposal": f"review/proposals/{ref}.json",
           "saved_at": stamp,
           "lines": out}
    p = decisions_path(ref, root)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        p.with_suffix(".json.prev").write_bytes(p.read_bytes())
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)
    return {"path": str(p), "lines": len(out),
            "edited": sum(1 for v in out.values() if v["edited"])}


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
    """Self-contained review page for one ref: one entry per line, reading order.

    **The unit is the line, not the span.** An earlier version grouped by
    substitution class on the grounds that glyphs are 3.3% of characters, but that
    measures the wrong cost: the expensive act is re-orienting to a different line,
    not reading the characters in a line you already have open. Since 44% of lines
    need some attention, those lines get opened regardless, and once open the rest
    of the line is nearly free. Span-grouping also scattered one line's corrections
    across the queue, so their sum could not be seen.

    It organised around the wrong thing besides. The spans are diffs against
    CATMuS, which reads no inventory glyph at all, so a class like `'` -> `ˊ`
    describes the recognizer's failure modes rather than the text. `group_spans`
    survives as *measurement* for the eval, not as the review unit.

    Reading order, not difference-first: consecutive lines carry each other's
    context, and a line the two witnesses agree on can still have both of them
    wrong — CATMuS agreeing about ASCII is weak evidence and it has no vote on a
    glyph whatsoever. So every line is present; agreement only sets emphasis.
    """
    from .lines import write_line_crops
    ref = norm_ref(ref)
    crops = crops or (root / "review" / "crops")
    recs = {r["index"]: r for r in write_line_crops(ref, crops, alto_dir, root)}
    prop = load_proposal(ref, root)
    saved = load_decisions(ref, root)
    spans = page_spans(ref, alto_dir, root)
    summ = summary(spans, len(recs))

    h = [f"<title>review {ref}</title>", "<style>",
         f":root{{--f:{_FONT_STACK}}}",
         "body{font:15px var(--f);margin:0;padding:1.5rem;max-width:1100px}",
         "h1{font-size:1.1rem;margin:0 0 .3rem}",
         ".sum{color:#555;font-size:.85rem;margin-bottom:1.4rem}",
         ".ln{border-top:1px solid #ddd;padding:.7rem 0}",
         # Agreement is de-emphasis, never omission: CATMuS agreeing about ASCII is
         # weak evidence, and on a glyph it has no vote at all, so a quiet line is
         # still a line somebody has to look at.
         ".agree{opacity:.62}",
         ".agree:focus-within{opacity:1}",
         ".cp{font:12px ui-monospace,monospace;color:#036;margin:.2rem 0}",
         ".tags{font:11px ui-monospace,monospace;color:#666}",
         ".ref{font:13px ui-monospace,monospace;color:#777;margin-top:.2rem}",
         ".note{font-size:12px;color:#7a4a00;margin-top:.2rem;max-width:70ch}",
         # Crops are emitted as one CSS rule per line and referenced by class, not
         # inlined per occurrence. Inlining embedded a line's image once per queue
         # entry; on 1-074 that was 676 KB against 209.
         ".crop{border:1px solid #ddd;background-repeat:no-repeat;"
         "background-size:contain;background-color:#fff;margin:.2rem 0}",
         "textarea{font:17px/1.4 var(--f);width:100%;border:1px solid #bbb;"
         "border-radius:4px;padding:.35rem .5rem;resize:vertical;overflow:hidden}",
         "textarea:focus{outline:2px solid #47f;border-color:#47f}",
         # Fixed to the bottom, full width, always visible. It is the reference for
         # what the mode does as much as it is an input device, so hiding it behind a
         # scroll position would defeat both jobs.
         "#pal{position:fixed;left:0;right:0;bottom:0;z-index:5;background:#fff;"
         "border-top:1px solid #999;box-shadow:0 -2px 10px #0002;"
         "display:flex;gap:.9rem;align-items:flex-start;padding:.5rem .8rem}",
         "#pgroups{display:flex;flex-wrap:wrap;gap:.35rem .9rem;flex:1}",
         ".pgrp{display:flex;flex-direction:column;gap:.15rem}",
         ".plabel{font:10px ui-monospace,monospace;color:#888;letter-spacing:.02em}",
         ".pkeys{display:flex;flex-wrap:wrap;gap:.2rem}",
         ".pk{font:inherit;min-width:2.5rem;padding:.15rem .25rem;cursor:pointer;"
         "display:flex;flex-direction:column;align-items:center;line-height:1.1;"
         "background:#fafafa;border:1px solid #bbb;border-radius:4px}",
         ".pk b{font-size:1.15rem;font-weight:500}",
         ".pk span{font:10px ui-monospace,monospace;color:#888;min-height:1em}",
         ".pk.mk{background:#eef3ff}",
         "#pctl{display:flex;flex-direction:column;gap:.3rem;align-items:flex-end;"
         "border-left:1px solid #ddd;padding-left:.9rem;font-size:.85rem}",
         "#st{color:#555;min-width:13ch;text-align:right}",
         "#st.bad{color:#b00;font-weight:600}",
         "#kb{font:12px ui-monospace,monospace;color:#777;border:1px solid #bbb;"
         "border-radius:3px;padding:.1rem .4rem}",
         "#kb.on{color:#fff;background:#1a7f37;border-color:#1a7f37;font-weight:700}",
         "#pctl button{font:inherit;padding:.25rem .9rem}",
         # The mode has to be unmissable, since with it on every letter key means
         # something else. A badge alone is too easy to lose track of.
         "body.kbdon textarea:focus{outline-color:#1a7f37;border-color:#1a7f37;"
         "background:#f2fbf4}",
         # Clear of the fixed panel. Generous: the panel wraps on a narrow window.
         "body{padding-bottom:15rem}",
         "@media(prefers-color-scheme:dark){body{background:#161616;color:#e6e6e6}"
         ".ln{border-color:#2f2f2f}.cp{color:#8ec7ff}.ref{color:#8f8f8f}"
         ".note{color:#d9b26a}"
         "textarea{background:#111;color:#eee;border-color:#444}"
         "#st{color:#bbb}"
         "#pal{background:#1b1b1b;border-color:#444}"
         "#pctl{border-color:#3a3a3a}"
         ".pk{background:#242424;border-color:#484848;color:#eee}"
         ".pk.mk{background:#1b2436}"
         "#kb{color:#aaa;border-color:#555}"
         "body.kbdon textarea:focus{background:#0f1a12}"
         ".crop{filter:invert(1) hue-rotate(180deg)}}",
         "</style>"]

    # One rule per unique line crop, scaled down to fit the column while keeping
    # aspect ratio, so the div reserves the right height before the image paints.
    from PIL import Image
    # Every rendered line needs a rule, not only the differing ones. Deriving this
    # from the span instances left the agreeing lines as empty bordered boxes.
    css = []
    for idx in sorted(recs):
        rec = recs[idx]
        if idx not in prop:
            continue
        path = Path(rec["crop"])
        w, ht = Image.open(path).size
        # Full column width. Never upscaled past 1:1 — a magnified bitonal crop
        # invents smoothness, and the reviewer should see the raster it is.
        scale = min(1.0, 1040 / w)
        css.append(f".c{idx}{{background-image:url({_data_uri(path)});"
                   f"width:{round(w * scale)}px;height:{round(ht * scale)}px}}")
    h += ["<style>", "\n".join(css), "</style>"]
    h += [
         f"<h1>{ref} — {summ['lines']} lines, "
         f"{summ['lines'] - summ['lines_identical']} differing from catmus</h1>",
         "<div class=sum>"
         f"{summ['spans']} differing spans in {summ['classes']} substitution "
         f"classes · {summ['inventory_spans']} touch inventory glyphs · "
         f"{summ['lookalikes_in_proposal']} lookalike traps in the proposal<br>"
         "Every line is listed, in reading order. CATMuS is shown for reference "
         "only: it is a witness to geometry and English, and produced no inventory "
         "glyph anywhere in this book, so on a glyph the image is the sole witness "
         "— and a line the two agree on can still have both of them wrong.</div>"]

    differing = {s["index"] for s in spans}
    for idx in sorted(recs):
        rec = recs[idx]
        mine = prop.get(idx)
        if mine is None:
            continue
        proposed = _nfd(mine["text"])
        # Saved work wins on reload, so a session can be resumed. The proposal is
        # still what `edited` is measured against, server-side.
        full = _nfd(saved[idx]["text"]) if idx in saved else proposed
        marks = codepoints("".join(dict.fromkeys(c for c in full if ord(c) > 127)))
        agree = idx not in differing
        h.append(f"<div class='ln{' agree' if agree else ''}'>")
        h.append(f"<div class=tags>line {idx} · {_esc(rec['line_id'])}"
                 + ("" if agree else " · differs from catmus")
                 + (" · <b>edited</b>" if full != proposed else "") + "</div>")
        h.append(f"<div class='crop c{idx}' role=img "
                 f"aria-label='scan of line {idx}'></div>")
        h.append(f"<textarea data-line='{idx}' rows=1 spellcheck=false>"
                 f"{_esc(full)}</textarea>")
        if marks:
            h.append(f"<div class=cp>{_esc(marks)}</div>")
        h.append(f"<div class=ref>catmus: {_esc(rec['text']) or '(empty)'}</div>")
        for key in ("note", "resolved", "corrected"):
            if mine.get(key):
                h.append(f"<div class=note>{key}: {_esc(mine[key])}</div>")
        h.append("</div>")

    # Fixed to the bottom of the viewport, and the save controls live in the same
    # panel: two floating widgets competing for the corner is one too many.
    binding = {g: k for k, g in KBD_GLYPHS.items()}
    binding.update({m: k for k, m in KBD_MARKS.items()})

    pal = ["<div id=pal>", "<div id=pgroups>"]
    for label, glyphs in PALETTE:
        pal.append(f"<div class=pgrp><div class=plabel>{_esc(label)}</div>"
                   "<div class=pkeys>")
        for g in glyphs:
            key = binding.get(g, "")
            combining = len(g) == 1 and unicodedata.category(g) == "Mn"
            shown = ("◌" + g) if combining else g
            tip = codepoints(g) + (
                " — attaches to the character before the caret" if combining else "")
            pal.append(f"<button class='pk{' mk' if combining else ''}' "
                       f"data-ins='{_esc(g)}' title='{_esc(tip)}'>"
                       f"<b>{_esc(shown)}</b>"
                       f"<span>{_esc(key) or '&nbsp;'}</span></button>")
        pal.append("</div></div>")
    pal.append("</div>")
    pal.append("<div id=pctl><span id=kb>kbd off</span>"
               "<span id=st>no changes</span><button id=sv>Save</button>"
               "<div class=tags>ctrl-space toggles · off = plain typing</div></div>")
    pal.append("</div>")
    h += pal
    # Autosave on a debounce *and* an explicit button, plus a beforeunload guard.
    # Belt and braces on purpose: the alternative to a save that fires by itself is
    # a reviewer who closes the tab on forty adjudicated lines.
    h.append("<script>const GL=" + json.dumps(KBD_GLYPHS, ensure_ascii=False)
             + ",MK=" + json.dumps(KBD_MARKS, ensure_ascii=False) + ";</script>")
    h.append("""<script>
const st=document.getElementById('st'), sv=document.getElementById('sv');
const kb=document.getElementById('kb');
let kbdOn=false, last=null;
function setKbd(v){kbdOn=v;kb.textContent='kbd '+(v?'ON':'off');
  kb.className=v?'on':'';document.body.classList.toggle('kbdon',v)}
function insert(el,s){
  const a=el.selectionStart,b=el.selectionEnd;
  el.setRangeText(s,a,b,'end');
  el.dispatchEvent(new Event('input',{bubbles:true}));
}
// Click-to-insert targets whichever field was last focused, so the palette works
// without stealing the caret.
document.addEventListener('mousedown',e=>{
  if(e.target.closest('#pal')) e.preventDefault();
});
for(const b of document.querySelectorAll('.pk')){
  b.addEventListener('click',()=>{ if(last) insert(last,b.dataset.ins) });
}
addEventListener('keydown',e=>{
  if(e.ctrlKey&&e.code==='Space'){e.preventDefault();setKbd(!kbdOn);return}
  if(!kbdOn||!last||document.activeElement!==last) return;
  if(e.ctrlKey||e.altKey||e.metaKey) return;
  const g=Object.prototype.hasOwnProperty.call(GL,e.key)?GL[e.key]
        :(Object.prototype.hasOwnProperty.call(MK,e.key)?MK[e.key]:null);
  if(g===null) return;
  e.preventDefault(); insert(last,g);
});
let dirty=false, timer=null;
const grow=t=>{t.style.height='auto';t.style.height=t.scrollHeight+'px'};
function collect(){const o={};for(const t of document.querySelectorAll('textarea'))
  o[t.dataset.line]=t.value;return o}
async function save(){
  st.textContent='saving…';
  try{
    const r=await fetch('/save',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({lines:collect()})});
    if(!r.ok) throw new Error(await r.text());
    const j=await r.json();
    dirty=false;
    st.textContent=`saved · ${j.edited}/${j.lines} lines edited`;
  }catch(e){ st.textContent='SAVE FAILED: '+e.message; st.className='bad'; }
}
for(const t of document.querySelectorAll('textarea')){
  grow(t);
  t.addEventListener('focus',()=>{last=t});
  t.addEventListener('input',()=>{grow(t);dirty=true;st.className='';
    st.textContent='unsaved…';clearTimeout(timer);timer=setTimeout(save,1200)});
}
sv.addEventListener('click',save);
addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue=''}});
</script>""")
    return "\n".join(h)


def serve(ref: str, alto_dir: str = "end-of-eval", root: Path = Path("."),
          port: int = 8731) -> None:
    """Serve one page's review at 127.0.0.1 and accept saves.

    Loopback only, and no path routing beyond the two endpoints it needs: this
    holds unpublished editorial work and has no business being reachable.
    """
    import json as _json
    import time
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # one line per save is enough; GETs are noise
            pass

        def do_GET(self):
            if self.path not in ("/", "/index.html"):
                self.send_error(404)
                return
            body = render_queue_html(ref, alto_dir, root).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if self.path != "/save":
                self.send_error(404)
                return
            try:
                n = int(self.headers.get("Content-Length") or 0)
                payload = _json.loads(self.rfile.read(n) or b"{}")
                res = save_decisions(ref, payload.get("lines") or {}, root,
                                     stamp=time.strftime("%Y-%m-%dT%H:%M:%S%z"))
            except Exception as e:  # report it to the page, never a blank failure
                msg = _json.dumps({"error": str(e)}).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(msg)))
                self.end_headers()
                self.wfile.write(msg)
                return
            print(f"saved {res['path']}: {res['edited']}/{res['lines']} edited")
            body = _json.dumps(res).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"review {norm_ref(ref)} -> http://127.0.0.1:{port}/   (ctrl-c to stop)")
    print(f"decisions -> {decisions_path(ref, root)}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        srv.server_close()


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
