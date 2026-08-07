---
name: tier1_terms-can-misfire-on-tier2-names
description: tier1_terms is a mechanical floor and can list a Tier-2 name carrying an inventory mark (e.g. German Döring); judge the language before wrapping it in <foreign>/index
metadata:
  type: project
---

On `1-022`, `tier1_terms` listed `{index: 1, line: 6, text: "Döring"}` — but
"Döring" is a German personal name (Mr. A. E. Döring, an illustrator credited
in the front matter), not a Chukchi form.

**This is the detector working, not misfiring.** `tier1_terms` matches
`NON_ENGLISH_HITS` — an inventory glyph or a straight apostrophe — over
`gt/ocr/`, mechanically and with no language awareness, exactly as specified.
U+0308 combining diaeresis *is* an inventory mark (`keying_spec.md` gives `ë`
and `ä`), so a German `ö` trips it by the rule as written. The list is
declared a **floor** in `context.tier1_terms`'s own docstring, and the same
docstring says where the judgement lives: "the model's judgement is *which*
token; the glyphs are never its to originate." Selecting against this list is
the collator's job, so do not report an entry like this as a bug — a note
saying the tool is broken teaches the next collator to distrust a handle that
exists to stop it retyping glyphs, which is the more expensive error.

**Why:** The collation contract's Tier-1 firewall and `tier1_terms` handle
mechanism (`<foreign xml:lang="ckt" resp="#llm" index="N"/>` filled by
`harness tei expand`) are specifically for Americanist notation forms
(ckt/kpy/ypk/xcv/eve/ipk/itl). `harness tei expand` itself refuses to fill a
handle on an element with no Tier-1 `xml:lang` ("English is not
transcluded"), which confirms this reading.

**How to apply:** Your page arrives with the wrap **already there** —
`harness tei generate` lifts every `tier1_terms` hit into an empty
`<foreign index="N"/>` with no `xml:lang`, and `validate` errors on each until
you dispose of it. So the act is a deletion, not an omission: where the entry's
text is plainly a Tier-2 or proper name (German, Russian, English) rather than a
Chukchi/Koryak/etc. form, **unwrap it** and key the word directly — e.g.
`<name type="anthroponym">Döring</name>` per the persons rule, no `xml:lang`,
no `@resp`, following the book's Nordenskiöld precedent in the collator spec.

Unwrapping is a normal outcome and on front matter it is the commoner of the two.
Do not reach for `xml:lang="de"` to make the error go away: that asserts a foreign
*span* where the page has an ordinary English sentence containing a name, and it
would put a Tier-2 code on the firewall's machinery for no reason.
