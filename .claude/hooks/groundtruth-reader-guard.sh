#!/bin/bash
# PreToolUse guard for the groundtruth-reader subagent: the standing rules made
# mechanical. A checkable rule beats a prohibition — it does not depend on the
# pass behaving. Frontmatter hook, so nothing here constrains the main session
# or any other agent.
#
# Four rules, and each is one this pass has actually needed:
#
#   1. THE BASH SURFACE IS AN ALLOWLIST. The reader's legitimate verbs are a
#      closed set; everything else — restore, review, clean, any --all sweep,
#      git, python3 -c, ls/cat/find, compound commands — is exactly what the
#      hard rules forbid, and a denylist would have to anticipate every route
#      around itself.
#   2. WRITES LAND IN TWO PLACES: the page's proposal and the agent's own
#      memory. `gt/ocr/` is off-limits by any route; so is page geometry.
#   3. READS ARE AN ALLOWLIST TOO. The evidence stores are named and refused
#      first, so the refusal says which rule it is: `gt/ocr/` is another page's
#      adjudicated truth and a convention derived from a neighbour is what the
#      firewall forbids; `mz/ocr/` is the CATMuS ALTO, which `ocr lines` already
#      serves in the form the pass is meant to see it.
#   4. NO --all FORM OF ANYTHING. One agent, one page.
#
# Where a rule is an allowlist, the hook DECIDES rather than deferring: it
# returns permissionDecision=allow, and the call runs without a prompt. Exiting
# 0 would hand an already-checked call back to the normal permission flow, which
# asks the human about every verb and every write — approval fatigue on a batch
# of six readers, and the fifth prompt is not read as carefully as the first.
# Only rules that actually enumerate their targets may do this; a denylist must
# not, because `allow` on it would approve everything the list happens not to
# name.
#
# What this hook CANNOT check: which page is this reader's. Nothing in the hook
# input names the ref, so "read only your own page" holds for `gt/ocr/` and the
# adjudications, and stays a prose rule between one `review/PP-NNN/` and
# another. Exit 2 blocks the call and the reader sees the message.

INPUT=$(cat)
TOOL=$(printf '%s' "$INPUT" | jq -r '.tool_name // empty')

PROPOSAL='proposal.json'
MEMORY='.claude/agent-memory/groundtruth-reader/'

# $1 is the reason, and it is shown to the human as the ground of the decision.
allow() {
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":%s}}\n' \
    "$(printf '%s' "$1" | jq -Rs .)"
  exit 0
}

# Matched as substrings, so a `..` anywhere is refused outright — otherwise
# review/1-031/../../gt/ocr/1-030.xml satisfies every prefix and defeats the rule.
readable() {
  case "$1" in *..*) return 1 ;; esac
  case "$1" in
    # The working directory of some page: its images, its proposal, its symlink
    # to the raster. Everything the ladder writes lands here.
    */review/*|review/*) return 0 ;;
    # The normative text. keying_spec.md and the checklist are named in the
    # standing brief as required reading; the rest is what a reader legitimately
    # reaches for when a flag or an invariant is in doubt.
    *keying_spec.md|*concordance.md|*CLAUDE.md) return 0 ;;
    */harness/VERBS.md|harness/VERBS.md|*/harness/README.md|harness/README.md) return 0 ;;
    */docs/*|docs/*) return 0 ;;
    *.claude/skills/rebuild-groundtruth/*) return 0 ;;
    *"$MEMORY"*) return 0 ;;
    # data/ is the apparatus the verbs read off: lexicon_extra.txt, readings.md.
    */data/*|data/*) return 0 ;;
  esac
  return 1
}

case "$TOOL" in
  Read)
    P=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty')
    case "$P" in
      */gt/ocr/*|gt/ocr/*)
        echo "Blocked: gt/ocr/ is adjudicated ground truth for OTHER pages — your own has none, which is why you were sent. Deriving a convention from a neighbouring page is what the firewall forbids: the settled answers are in keying_spec.md, and if one is missing from it, that is the finding. Say so in your report." >&2
        exit 2 ;;
      */mz/ocr/*|mz/ocr/*)
        echo "Blocked: read the CATMuS ALTO through 'uv run harness ocr lines PP-NNN --store mz', which gives you the line indices and the zone labels in the form this pass is meant to see them. The raw XML adds geometry you have no use for and a whole page of machine text you are forbidden to treat as a witness." >&2
        exit 2 ;;
      # The read view, checked after both stores it points into so the refusal
      # above names the store the symlink actually resolves to.
      */ocr/*|ocr/*|*/zones/*|zones/*)
        echo "Blocked: ocr/ and zones/ are the read views — symlinks into gt/ and mz/, so reading one is reading whichever store won, and neither is yours to read directly. 'ocr lines --store mz' gives you your page's lines and their zone labels." >&2
        exit 2 ;;
      */decision.json|*/decision.jsonl)
        echo "Blocked: decision.json is the adjudication — a human's, made after you finish. Reading one is reading the answers to a page someone else already keyed. Your deliverable is a proposal." >&2
        exit 2 ;;
      */scans/*|scans/*)
        echo "Blocked: the raster comes to you through the image ladder, not off the disk. 'ocr numbered' gives you the whole page with every line indexed, and it is the rung you are meant to start on; the full-resolution scan is the same pixels with nothing to key them against." >&2
        exit 2 ;;
    esac
    readable "$P" && allow "groundtruth-reader reading its working directory, the spec, or its own memory"
    echo "Blocked: you read your page's working directory under review/, the normative text (keying_spec.md, concordance.md, CLAUDE.md, harness/VERBS.md, harness/README.md, docs/, your pass doc), data/, and your own memory under $MEMORY. Nothing else on this machine is evidence about your page. If something you genuinely need is outside that list, say so in your report rather than reaching around the rule." >&2
    exit 2 ;;

  Write|Edit)
    P=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty')
    case "$P" in
      *..*) ;;
      */review/*/"$PROPOSAL"|review/*/"$PROPOSAL") allow "groundtruth-reader authoring its page's proposal" ;;
      *"$MEMORY"*) allow "groundtruth-reader writing its own memory" ;;
    esac
    echo "Blocked: you write exactly two places — review/PP-NNN/proposal.json, and your own memory under $MEMORY. That is the whole deliverable: gt/ocr/ is off-limits by any route, decision.json is a human's, and nothing in your loop writes page geometry — a band you judge to be a dropped line is REPORTED, in the proposal's segmenter_missed block, never repaired." >&2
    exit 2 ;;
esac

COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')
[ -z "$COMMAND" ] && exit 0

# One plain invocation: no chaining, substitution, or redirection. A pipe or
# `&&` is how an allowed verb smuggles a forbidden one.
case "$COMMAND" in
  *';'*|*'&&'*|*'||'*|*'|'*|*'`'*|*'$('*|*'>'*|*'<'*)
    echo "Blocked: run one plain command at a time — no pipes, chaining, substitution or redirection. Your verbs emit TOON down a pipe already; read their output whole." >&2
    exit 2 ;;
esac

# The reader's whole legitimate surface, and it is read-only over the stores:
# `corpus normalize` gates the reader's own proposal, `lexicon` and `find` are
# measurement and always exit 0. `adopt-gap` is deliberately absent — it writes
# gt/ocr/, it cannot run on a restoration anyway (no ground truth to append to),
# and a verb in the allowlist is a verb a reader will find a reason to try.
if printf '%s' "$COMMAND" | grep -qE '^uv run harness (ocr (gaps|lines|numbered|sheets|zoom)|proposal (fix|check|codepoints|set|replace|marks)|corpus normalize|lexicon [a-z]+|find [a-z]+)( |$)'; then
  case "$COMMAND" in
    *--all*)
      echo "Blocked: no --all form of anything; you have exactly one page." >&2
      exit 2 ;;
  esac
  allow "groundtruth-reader running a verb from its closed surface, on one page"
fi

echo "Blocked by your standing instructions. Your Bash surface is exactly: uv run harness {ocr gaps|lines|numbered|sheets|zoom, proposal fix|check|codepoints|set|replace|marks, corpus normalize, lexicon *, find *} — one plain command, no --all. Everything else (restore, review, clean, views, git, python3, shell listing) is not yours; Glob answers existence, Read answers content, and the verbs answer the rest. If a tool you genuinely need is missing from this list, say so in your report rather than working around it." >&2
exit 2
