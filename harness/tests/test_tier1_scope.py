"""The Tier-1 set is stated in code and in three documents. Hold them together.

`validate.TIER1` decides where the ASCII policy, the lookalike greps, the `@resp`
requirement and `tei expand` all apply — so adding a language is a corpus-wide act
and a code the docs do not name is one no keyer knows to reach for. Three places
say the set outside the code: `keying_spec.md` §1 scopes the ASCII policy by
listing it, `.claude/agents/collator.md` gives the closed set with the
rule for when each fires, and `tei/corpus-header.xml` declares it to the corpus in
`langUsage`.

`eve` and `ipk` are why this exists. `1-359`'s reader keyed the raised dot in the
Lamut river name `Buks·unda` as ordinary punctuation, correctly, because the word
sat in English footnote prose and Lamut was in no tier — the set was silently the
whole of what "which languages carry the inventory" meant, and nothing checked
that a language's absence from it was a decision rather than an omission.

**The header is checked in both directions, and it is the reason for that.** It
had declared `xcv` (Chuvan) "Tier-1, as above" for as long as it existed, while
`TIER1` carried three codes and its own comment said "the three" — so a Chuvan span
would have been declared Tier-1 to every consumer of the header and enforced as
nothing of the sort by the gate. Under-enforcement is the silent direction: the
declaration is a human's, so the code was what had to move.

CLAUDE.md is deliberately not checked for the codes themselves: it names the count
and routes to §1, because a fact stated twice is a defect and the router is the
one file every subagent pays for.
"""

from __future__ import annotations

import re
from pathlib import Path

from harness.langs import base, is_tier1, name, script
from harness.validate import TIER1

REPO = Path(__file__).resolve().parent.parent.parent
PROJECT = REPO / "jesup" / "bogoras-chukchi"
SPEC = REPO / "keying_spec.md"
SKILL = REPO / ".claude" / "agents" / "collator.md"
HEADER = PROJECT / "tei" / "corpus-header.xml"


def declared_tier1() -> set[str]:
    """The codes `langUsage` marks Tier-1, by the sentence it marks them with."""
    import re
    return {m.group(1) for m in re.finditer(
        r'<language ident="([^"]+)"[^>]*>(.*?)</language>',
        HEADER.read_text(encoding="utf-8"), re.DOTALL)
        if "Tier-1" in m.group(2)}


def test_the_spec_scopes_the_ascii_policy_by_naming_every_code():
    """§1's scoping sentence is the normative statement of the set.

    Read as a whole bullet rather than a single line: the first version matched
    only the line carrying the bold lead-in, so adding a seventh code and
    rewrapping the paragraph — which put the list on the continuation line —
    failed the gate over nothing. A gate that fires on reflow trains its reader to
    work around it.
    """
    lines = SPEC.read_text(encoding="utf-8").splitlines()
    start = next(i for i, ln in enumerate(lines)
                 if "ASCII policy, scoped to Tier-1" in ln)
    end = next(i for i in range(start + 1, len(lines))
               if lines[i].startswith("- ") or not lines[i].strip())
    bullet = " ".join(lines[start:end])
    missing = sorted(c for c in TIER1 if f"`{c}`" not in bullet)
    assert not missing, f"keying_spec §1 scopes the policy without naming {missing}"


def test_the_collation_skill_gives_every_code_a_firing_rule():
    """A code with no rule for when it fires is a code a keyer cannot apply."""
    body = SKILL.read_text(encoding="utf-8")
    tier1 = body.split("## Tier 1", 1)[1].split("## Tier 2", 1)[0]
    missing = sorted(c for c in TIER1 if f"**`{c}`**" not in tier1)
    assert not missing, f"the collator's closed set omits {missing}"


def test_the_corpus_header_declares_exactly_the_set():
    """Both directions: a code the header calls Tier-1 that the gate does not
    enforce is the failure this pins, and it had been live."""
    assert declared_tier1() == TIER1


def test_the_skill_declares_no_code_the_set_does_not_carry():
    """The converse: a documented code outside TIER1 gates nothing it promises."""
    import re
    body = SKILL.read_text(encoding="utf-8")
    tier1 = body.split("## Tier 1", 1)[1].split("## Tier 2", 1)[0]
    declared = set(re.findall(r"^- \*\*`([a-z]{2,3})`\*\*", tier1, re.MULTILINE))
    assert declared <= TIER1, f"documented as Tier-1 but not in the set: {sorted(declared - TIER1)}"


# --- a tag with a script subtag is still its language ----------------------


def test_a_script_subtag_keeps_the_base_in_tier1():
    assert is_tier1("ckt") and is_tier1("ckt-Cyrl")
    assert not is_tier1("ru") and not is_tier1("ru-Latn")
    assert not is_tier1(None) and not is_tier1("")
    assert (base("ckt-Cyrl"), script("ckt-Cyrl"), script("ckt")) == ("ckt", "Cyrl", None)
    assert script("ipk-x-cited") is None


def test_a_subtagged_name_reads_as_its_language_and_script():
    assert name("ckt-Cyrl") == "Chukchi (Cyrillic)"
    assert name("zz-Cyrl") == "zz-Cyrl"


def test_resp_is_required_on_a_subtagged_tier1_span():
    """The silent direction this whole helper exists for: under a bare `in TIER1`
    a `ckt-Cyrl` span asked for no rank at all, and nothing said so."""
    from lxml import etree

    from harness.validate import Report, _rule_provenance
    doc = etree.fromstring('<p xmlns="http://www.tei-c.org/ns/1.0">'
                           '<foreign xml:lang="ckt-Cyrl">қаават</foreign></p>')
    r = Report()
    _rule_provenance(doc, None, None, r)
    assert any("ckt-Cyrl" in e and "PROVENANCE" in e for e in r.errors), r.errors


#: The membership tests no caller may spell, and the one module allowed to.
_BARE = re.compile(r"\bnot in (?:langs\.)?(?:TIER1|LEXICON_LANGS|ALIAS_LANGS)\b"
                   r"|\bin (?:langs\.)?(?:TIER1|LEXICON_LANGS|ALIAS_LANGS)\b")


def test_no_caller_tests_a_language_set_directly():
    """`ckt-Cyrl in TIER1` is False, and every gate on a Tier-1 span falls silent
    on it with no error. So the sets are asked through `langs.is_tier1` and
    `langs.is_known`, which read the base, and nothing else may ask them bare."""
    harness = REPO / "harness"
    found = [f"{p.relative_to(REPO)}:{i}"
             for p in sorted(harness.rglob("*.py"))
             if p.name != "langs.py" and "tests" not in p.parts
             for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
             if not ln.lstrip().startswith("#") and _BARE.search(ln)]
    assert not found, ("bare language-set membership; ask `langs.is_tier1` or "
                       f"`langs.is_known`: {found}")
