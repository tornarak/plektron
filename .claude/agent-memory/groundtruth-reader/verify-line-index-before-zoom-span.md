---
name: verify-line-index-before-zoom-span
description: Before spanning a zoom --only call by line index, re-check the index against harness ocr lines' text column, not just the numbered.png composite's visual row
metadata:
  type: feedback
---

On `1-032`, I picked zoom spans for two Tier-1 terms by eyeballing where they sat in
`numbered.png` and pattern-matching against a mental line count, and named the wrong
indices (38/40 as 39/41 — off by one). The zoom came back showing unrelated English
text ("its covering of reindeer-skins" instead of the umkᴀˊ-neˊlhɪn term), which was
the tell, but it cost a wasted call.

**Why:** `harness ocr lines` output is the authority for which index holds which text
(`index,line_id,...,text` columns) — the numbered composite shows the same indices as
ruled bands, but miscounting rows or misreading a folded caption is easy when several
lines carry similar phrasing.

**How to apply:** before issuing a `zoom --only N@lo-hi` for a specific term, confirm
via the `text` field in the `ocr lines` table (already fetched earlier in the pass)
that index N is actually the line containing the term — don't just count rows in the
numbered.png image by eye. If a zoom result doesn't match what was expected, re-check
the index against the lines table first, before assuming a wrong span percentage.
