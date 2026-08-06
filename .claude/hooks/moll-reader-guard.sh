#!/bin/bash
# PreToolUse guard for the moll-reader subagent: the standing rules made
# mechanical. A checkable rule beats a prohibition — it does not depend on the
# reader behaving. Frontmatter hook, so nothing here constrains the main
# session or any other agent.
#
# Three rules, and each is one this pass has actually needed:
#
#   1. BLIND TO THE OCR STORE. `moll-scans/ocr/` is the independent witness
#      every keyed page is diffed against afterwards, and it is worth having
#      only because it cannot have made the reader's mistake. One Read of it
#      collapses the two witnesses into one, silently and unrecoverably.
#   2. WRITES LAND IN THE ENTRY STORE (or the agent's own memory). Nothing this
#      side quest produces may enter `gt/`, `tei/`, `ocr/` or any corpus store.
#   3. THE BASH SURFACE IS AN ALLOWLIST — two verbs and a crop tool. A denylist
#      would have to anticipate every route around itself.
#   4. AND SO ARE THE TARGETS. Every path a reader reads or crops must be inside
#      the pass's own trees. A rule naming only the tools leaves `identify
#      moll-scans/ocr/moll-035.txt` and `convert` of anything on the box wide
#      open, which is rule 1 defeated through a different tool name.
#
# Exit 2 blocks the call and the reader sees the message.
#
# Where a rule is an allowlist, the hook DECIDES rather than deferring: it
# returns permissionDecision=allow, and the call runs without a prompt. Exiting
# 0 would hand an already-checked call back to the normal permission flow, which
# asks the human about every crop — approval fatigue on a batch of six readers,
# and the fifth prompt is not read as carefully as the first. Only rules that
# actually enumerate their targets may do this; a denylist must not, because
# `allow` on it would approve everything the list happens not to name.

INPUT=$(cat)
TOOL=$(printf '%s' "$INPUT" | jq -r '.tool_name // empty')

ENTRIES='scratch/chukchi/moll-scans/entries/'
MEMORY='.claude/agent-memory/moll-reader/'

CROPS='scratch/chukchi/moll-scans/crops/'

# Every place a reader has business looking: the rasters (originals, marked,
# zoom output, crops/, its own table), its memory, and its pass doc. Matched as
# substrings, so a `..` anywhere is refused outright — otherwise
# .../marked/../ocr/x satisfies the prefix and defeats the rule.
readable() {
  case "$1" in *..*) return 1 ;; esac
  case "$1" in
    */moll-scans/ocr/*) return 1 ;;
    */scratch/chukchi/moll-scans/*|scratch/chukchi/moll-scans/*) return 0 ;;
    *"$MEMORY"*|*.claude/skills/read-moll-page/*) return 0 ;;
  esac
  return 1
}

# $1 is the reason, and it is shown to the human as the ground of the decision.
allow() {
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":%s}}\n' \
    "$(printf '%s' "$1" | jq -Rs .)"
  exit 0
}

case "$TOOL" in
  Read)
    P=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty')
    case "$P" in
      */moll-scans/ocr/*)
        echo "Blocked: scratch/chukchi/moll-scans/ocr/ is the tesseract witness your page will be diffed against after you finish. Reading it collapses the two witnesses into one and destroys the only check on this book that can see a dropped soft sign. Read the marked raster." >&2
        exit 2 ;;
    esac
    readable "$P" && allow "moll-reader reading inside the pass's own trees"
    echo "Blocked: you read the raster trees under scratch/chukchi/moll-scans/ (originals, marked/, zoom/, entries/ — never ocr/), your own memory under $MEMORY, your pass doc, and the crops you wrote under $CROPS. Nothing else on this machine is evidence about your page. Read takes a file, not a directory: for your memory that is $MEMORY/MEMORY.md, which indexes the notes by filename. If something you genuinely need is outside that list, say so in your report rather than reaching around the rule." >&2
    exit 2 ;;

  Write|Edit)
    P=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty')
    case "$P" in
      *"$ENTRIES"*|*"$MEMORY"*) allow "moll-reader writing inside its two permitted directories" ;;
      *)
        echo "Blocked: you write exactly two places — your page's table under $ENTRIES and your own memory under $MEMORY. Nothing this pass produces may be written into gt/, tei/, ocr/ or any corpus store, and the marked rasters and the OCR store are not yours to edit." >&2
        exit 2 ;;
    esac ;;
esac

COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')
[ -z "$COMMAND" ] && exit 0

# One plain invocation: no chaining, substitution, or redirection. A pipe or
# `&&` is how an allowed verb smuggles a forbidden one, and a shell loop over
# labels re-measures the whole page once per label — the verb takes several.
case "$COMMAND" in
  *';'*|*'&&'*|*'||'*|*'|'*|*'`'*|*'$('*|*'>'*|*'<'*|*'for '*|*'{'*)
    echo "Blocked: run one plain command at a time — no pipes, chaining, substitution, redirection or loops. Send each command as its own call. zoom takes every label you want in one call, so a loop is never the way: uv run python scratch/chukchi/entry_bounds.py zoom moll-NNN:17,23,41" >&2
    exit 2 ;;
esac

# The reader's whole legitimate verb surface. `context` is the measurement of
# its own page, run first-hand rather than copied into its prompt; `zoom`
# magnifies it. Everything else in
# entry_bounds.py either writes a store (mark, measure --commit, ocr) or reads
# across pages (witness, suffixes), and neither is a reader's business.
if printf '%s' "$COMMAND" | grep -qE '^uv run python scratch/chukchi/entry_bounds\.py (zoom|context|claim|rows)( |$)'; then
  case "$COMMAND" in
    *--all*)
      echo "Blocked: no --all form of anything; you have exactly one page. Name it and only it — e.g. uv run python scratch/chukchi/entry_bounds.py rows moll-NNN, with the ref \`claim\` gave you and no second ref." >&2
      exit 2 ;;
  esac
  allow "entry_bounds.py zoom/context/claim/rows — one page, its own"
fi

# The crop escape hatch, and it is for CROPPING. Filtering manufactures
# evidence: a mark visible only after -sharpen is a fact about the filter.
# -resize is out for the same reason zoom caps at 4x. There is no `magick` on
# this box, only ImageMagick 6.
if printf '%s' "$COMMAND" | grep -qE '^(identify|convert)( |$)'; then
  if printf '%s' "$COMMAND" | grep -qE ' -(sharpen|contrast|contrast-stretch|normalize|threshold|level|modulate|resize|scale|sample|enhance|despeckle|equalize|auto-level|unsharp)( |$)'; then
    echo "Blocked: cropping only. Every enhancement operator is out by the same reasoning that caps zoom at 4x — a mark that appears after processing is evidence about the filter, not about the paper. If it will not resolve off the original, that is the finding: write ? and say so in the note." >&2
    exit 2
  fi

  # Targets, not just operators. Words beginning `-` or `+` are operators and
  # words made only of digits and geometry punctuation are geometry; whatever is
  # left is a path, and every one of them must be somewhere this reader may
  # look. Without this the crop hatch reads any image on the box, the OCR store
  # included — `identify` on it would leak its line count, and `convert` a crop
  # of its text.
  set -f
  # shellcheck disable=SC2086
  set -- $COMMAND
  shift
  LAST=
  for W in "$@"; do
    W=${W%\"}; W=${W#\"}; W=${W%\'}; W=${W#\'}
    case "$W" in
      -*|+*) continue ;;
      *[!0-9xX+%.,:-]*) ;;
      *) continue ;;
    esac
    if ! readable "$W"; then
      echo "Blocked: '$W' is not a path you may touch. identify/convert operate on the raster trees under scratch/chukchi/moll-scans/ (never ocr/) and write into $CROPS. A crop of anything else is not evidence about your page." >&2
      exit 2
    fi
    LAST=$W
  done
  case "$COMMAND" in
    convert*)
      case "$LAST" in
        *"$CROPS"*) ;;
        *)
          echo "Blocked: write your crop into $CROPS. '$LAST' is convert's output argument, and a crop is the evidence behind a reading — whoever adjudicates your page has to find it beside the page it came from, which a temp directory does not allow. A crop dropped in moll-scans/ itself sits beside the originals looking like one, and zoom/ belongs to the verb." >&2
          exit 2 ;;
      esac ;;
  esac

  allow "identify/convert on the pass's rasters, no enhancement operator, output under $CROPS"
fi

# Name the replacement rather than only the rule. Every pattern below was
# measured refusing in a real batch, and a reader that is told what to run
# instead does not spend a second round trip finding out.
case "$COMMAND" in
  *"$MEMORY"*|*agent-memory*)
    echo "Blocked: use the Read tool on your memory, not the shell. Read $MEMORY/MEMORY.md — it indexes every note by filename, one line each — then Read the notes whose summary bears on your page. There is no ls and no cat here, and the directory does not need listing." >&2
    exit 2 ;;
  ls\ *|ls|find\ *|tree*|wc\ *|stat\ *)
    echo "Blocked: nothing here needs a directory listing. Your page is the one \`claim\` gave you; \`context\` measures it, \`zoom\` prints the path of every crop it writes, \`rows\` counts the table you wrote, and Read opens any of them by name. If you are counting your own rows, that is: uv run python scratch/chukchi/entry_bounds.py rows moll-NNN" >&2
    exit 2 ;;
  grep\ *|rg\ *|sed\ *|awk\ *|head\ *|tail\ *|cat\ *)
    echo "Blocked: Read the file. Your table is one page long and you wrote it, so there is nothing in it to search for that reading it will not answer — and a partial view of your own cell is how a wrong reading gets confirmed. Read scratch/chukchi/moll-scans/entries/moll-NNN.md" >&2
    exit 2 ;;
  mkdir*|touch\ *|cp\ *|mv\ *|rm\ *)
    echo "Blocked: you never create or move a path. \`zoom\` writes its own output and prints where; \`convert\` writes the crop you name under $CROPS, which already exists; your table goes to $ENTRIES via Write. Every directory this pass writes into is already there." >&2
    exit 2 ;;
esac

echo "Blocked by your standing instructions. Your Bash surface is exactly: uv run python scratch/chukchi/entry_bounds.py {claim|zoom|context|rows}, plus identify/convert for a crop the verb cannot express — one plain command, no --all. Everything else (mark, measure, ocr, witness, suffixes, git, python3, shell listing) is not yours; Read answers what is in a file and zoom prints the path it wrote. If a tool you genuinely need is missing from this list, say so in your report rather than working around it." >&2
exit 2
