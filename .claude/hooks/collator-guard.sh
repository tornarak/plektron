#!/bin/bash
# PreToolUse guard for the collator subagent: the standing rules made mechanical.
# A checkable rule beats a prohibition — it does not depend on the pass behaving.
# Frontmatter hook, so nothing here constrains the main session or any other agent.
#
# Four rules, and each is one this pass actually needs:
#
#   1. THE BASH SURFACE IS AN ALLOWLIST. The collator's legitimate verbs are a
#      closed set; everything else — seam, queue, reconcile, any --all sweep, git,
#      python3 -c — is what the standing rules forbid, and a denylist would have to
#      anticipate every route around itself.
#   2. WRITES LAND IN TWO PLACES: the page's TEI file and the agent's own memory.
#   3. `tei seam` IS REFUSED BY NAME. It is the coordinator's, and it is the one
#      refusal here that is about *ordering* rather than authority: under a
#      dispatched batch the neighbour may be half-written or not written at all, so
#      a page that seams itself is asserting a gap against a file nobody finished.
#      The collator records `<!-- opens: … -->` and stops.
#   4. NO --all FORM OF ANYTHING. One agent, one page — and a corpus-wide form here
#      would read a sibling's half-written file as if it were input.
#
# Where a rule is an allowlist, the hook DECIDES rather than deferring: it returns
# permissionDecision=allow, and the call runs without a prompt. Exiting 0 would hand
# an already-checked call back to the normal permission flow, which asks the human
# about every verb and every write — approval fatigue on a batch, and the fifth
# prompt is not read as carefully as the first. Only rules that actually enumerate
# their targets may do this; a denylist must not, because `allow` on it would
# approve everything the list happens not to name.
#
# What this hook CANNOT check: which page is this collator's. Nothing in the hook
# input names the ref, so "only your own page" holds for `tei/` and for `review/`
# and stays a prose rule. `tei context` supplying `prev_tail` is what removes the
# reason to reach for a neighbour's file in the first place.

INPUT=$(cat)
TOOL=$(printf '%s' "$INPUT" | jq -r '.tool_name // empty')

MEMORY='.claude/agent-memory/collator/'

# $1 is the reason, and it is shown to the human as the ground of the decision.
allow() {
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":%s}}\n' \
    "$(printf '%s' "$1" | jq -Rs .)"
  exit 0
}

# Matched as substrings, so a `..` anywhere is refused outright — otherwise
# tei/../gt/ocr/chukchi-1-030.xml satisfies every prefix and defeats the rule.
readable() {
  case "$1" in *..*) return 1 ;; esac
  case "$1" in
    # **The raster, and it is the point of the pass.** Unlike the reading loop,
    # which meets the page through an indexed ladder, this pass reads the scan
    # directly — `tei context` hands over `page_image` for exactly that, and the
    # rules call it "the only witness that matters".
    */scans/*|scans/*) return 0 ;;
    # Where `ocr zoom` puts its crops, and the page's working directory generally.
    */review/*|review/*) return 0 ;;
    # The collator's own output, re-read once against the image before it declares
    # done. The hook cannot tell its page from a sibling's — see the header.
    */tei/*|tei/*) return 0 ;;
    # The normative text a collator does NOT already carry. `keying_spec.md` and
    # `harness/VERBS.md` are refused below and deliberately absent here: one is
    # transcluded into the system prompt and the other has a verb.
    *concordance.md|*CLAUDE.md) return 0 ;;
    */harness/README.md|harness/README.md) return 0 ;;
    */docs/*|docs/*) return 0 ;;
    *"$MEMORY"*) return 0 ;;
    # The apparatus the verbs read off: authorities.json, loi.json, toc.json,
    # readings.md, the schema.
    */data/*|data/*) return 0 ;;
  esac
  return 1
}

case "$TOOL" in
  Read)
    P=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty')
    case "$P" in
      */gt/ocr/*|gt/ocr/*|*/mz/ocr/*|mz/ocr/*|*/ocr/*|ocr/*|*/zones/*|zones/*)
        echo "Blocked: the draft reaches you through 'uv run harness tei context PP-NNN', which gives you catmus_draft, ocr_lines with the indices @facs cites, and tier1_terms with the ratified forms already keyed. The raw ALTO adds geometry the collation output carries none of, and a page of machine text you would then be reading as a witness rather than as a draft to correct." >&2
        exit 2 ;;
      *keying_spec.md)
        echo "Blocked: keying_spec.md is TRANSCLUDED WHOLE into your system prompt — scroll up, it is already in your context under 'The keying spec, transcluded'. Reading it buys nothing and pays ~15k tokens for it twice. Cite the section you need by number; if a rule you expect is genuinely missing from what you were given, that is a finding for your report, not a file to go looking for." >&2
        exit 2 ;;
      */harness/VERBS.md|harness/VERBS.md)
        echo "Blocked: ask the verb, don't read the reference — 'uv run harness verbs show tei validate' prints that one entry, and bare 'verbs show' lists every action name. Reading the whole file cost one agent 33,251 tokens, a fifth of its context, for two lookups it could have made in a few hundred." >&2
        exit 2 ;;
    esac
    readable "$P" && allow "collator reading its page, the raster, the apparatus, or its own memory"
    echo "Blocked: you read your page's raster and working directory, tei/, the normative text (concordance.md, CLAUDE.md, harness/README.md, docs/), data/, and your own memory under $MEMORY. Nothing else on this machine is evidence about your page. If something you genuinely need is outside that list, say so in your report rather than reaching around the rule." >&2
    exit 2 ;;

  Write|Edit)
    P=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty')
    case "$P" in
      *..*) ;;
      */tei/chukchi-*.xml|tei/chukchi-*.xml) allow "collator authoring its page's TEI" ;;
      *"$MEMORY"*) allow "collator writing its own memory" ;;
    esac
    echo "Blocked: you write exactly two places — tei/chukchi-PP-NNN.xml, and your own memory under $MEMORY. That is the whole deliverable. gt/, mz/, ocr/, zones/, scans/ and data/ are off-limits by any route; tei/corpus-header.xml is the corpus's and not one page's; and a reservation you cannot settle is a COMMENT IN YOUR PAGE plus a line in your report, never a change to something else." >&2
    exit 2 ;;
esac

COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')
[ -z "$COMMAND" ] && exit 0

# One plain invocation: no chaining, substitution, or redirection. A pipe or `&&`
# is how an allowed verb smuggles a forbidden one.
#
# **Scanned with quote state, not as a substring.** The test cannot be a `case` over
# the raw string: that cannot tell an operator from the same character inside a
# quoted argument, and this pass puts them there constantly — a `find authority`
# query is a printed citation, semicolons and all. Single quotes are literal, so
# nothing inside them can execute; double quotes still expand, so `$(` and a
# backtick stay forbidden there while a bare `;` does not. Outside quotes everything
# is an operator and everything is refused.
BAD=$(printf '%s' "$COMMAND" | awk '
  BEGIN { q = "" }
  {
    n = length($0)
    for (i = 1; i <= n; i++) {
      c = substr($0, i, 1)
      if (q != "\x27" && c == "\\") { i++; continue }   # escape, outside '"'"'...'"'"'
      if (q == "") {
        if (c == "\x27" || c == "\"") { q = c; continue }
        if (c ~ /[;|&<>`]/) { print "op"; exit }
        if (c == "$" && substr($0, i + 1, 1) == "(") { print "sub"; exit }
      } else if (c == q) {
        q = ""
      } else if (q == "\"") {
        if (c == "`") { print "sub"; exit }
        if (c == "$" && substr($0, i + 1, 1) == "(") { print "sub"; exit }
      }
    }
  }')
if [ -n "$BAD" ]; then
  echo "Blocked: run one plain command at a time — no pipes, chaining, substitution or redirection. Your verbs emit TOON down a pipe already; read their output whole. (Punctuation inside a quoted argument is fine — this fired on an operator outside quotes.)" >&2
  exit 2
fi

# **The seam, named separately so the refusal can say why.** Not a permission
# question but an ordering one: under a dispatched batch your neighbour may be
# half-written or not written at all, so a page that seams itself asserts a gap
# against a file nobody finished. Generic "not in your surface" would leave a
# collator to conclude the verb was merely unavailable and look for another route
# to the same claim, which is the one thing it must not find.
case "$COMMAND" in
  uv\ run\ harness\ tei\ seam|uv\ run\ harness\ tei\ seam\ *)
    echo "Blocked: 'tei seam' is the coordinator's, and it runs after the whole batch is in. Your neighbour may be half-collated or not started, so a seam written now asserts a gap against a file nobody finished. Record what only you can see — the '<!-- opens: … -->' comment, from the three, immediately after <pb> — and say in your report which value you wrote and why. The coordinator batches the seam off those." >&2
    exit 2 ;;
  uv\ run\ harness\ tei\ queue*|uv\ run\ harness\ tei\ reconcile*|uv\ run\ harness\ tei\ reservations*|uv\ run\ harness\ tei\ ledger*)
    echo "Blocked: queue, reconcile, reservations and ledger are the coordinator's view of a batch you are a subject of. A collator that can queue can deal itself pages; one that can reconcile is auditing a run it is in. Your page is the one 'tei claim' gave you." >&2
    exit 2 ;;
esac

case "$COMMAND" in
  cat|cat\ *|head|head\ *|tail|tail\ *|less|less\ *|more|more\ *)
    echo "Blocked: use Read, not cat — it opens every file you are allowed, it numbers the lines so you can cite one, and it renders the raster as an image instead of as bytes. head/tail are the same answer: Read takes an offset and a limit. Nothing about this file is refused; the shell is." >&2
    exit 2 ;;
esac

# The collator's whole legitimate surface. `claim` is the exception to read-only and
# has to be, since taking a ref off the queue is how the collator learns which page
# is its own. `corpus normalize` and the three `tei` gates act on the collator's own
# output; `find` and `lexicon lookup` are measurement over apparatus a human keyed.
#
# `ocr zoom` carries no pinned `--store`. The rules say `--store gt` and that is
# right on the 30 pages that have ground truth; on the other 802 the indices come
# from the view, and a hook pinning `gt` would refuse the ordinary case. Which store
# to cite is the contract's rule, not the guard's — the guard's business is that no
# other page is touched.
if printf '%s' "$COMMAND" | grep -qE '^uv run harness (tei (claim|context|expand|ids|pair|validate)|ocr zoom|corpus normalize|lexicon (conflicts|digraphs|glosses|lookup|marks|misses|suffixes)|find [a-z]+|verbs show)( |$)'; then
  case "$COMMAND" in
    *--all*)
      echo "Blocked: no --all form of anything; you have exactly one page, and your siblings' files are half-written while you work." >&2
      exit 2 ;;
  esac
  allow "collator running a verb from its closed surface, on one page"
fi

echo "Blocked: Read answers content and the verbs answer everything else — reach for those before the shell. Your Bash surface is exactly: uv run harness {tei claim|context|expand|ids|pair|validate, ocr zoom, corpus normalize, lexicon *, find *, verbs show} — one plain command, no --all. If you want to know what a command does, that is 'verbs show tei expand', not a Read of the reference. Everything else (tei seam|queue|reconcile|ledger, git, python3, the other groups) is not yours. If a tool you genuinely need is missing from this list, say so in your report rather than working around it." >&2
exit 2
