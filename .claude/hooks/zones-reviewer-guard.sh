#!/bin/bash
# PreToolUse guard for the zones-reviewer subagent: the standing rules made
# mechanical. Frontmatter hook, so nothing here constrains any other session.
#
# Three rules, each one this pass needs:
#
#   1. THE BASH SURFACE IS AN ALLOWLIST: claim, bands, verdict, numbered, zoom,
#      lines, verbs show. No --all, no --commit: one agent, one page at a time,
#      and nothing on this surface writes a store.
#   2. ONE WRITE TARGET: review/PP-NNN/zones.json, the verdict. gt/ is a human's
#      and mz/ is the rule's; an agent's edit is #llm and lives nowhere else.
#   3. THE RULE'S FILE IS READ THROUGH ITS VERB. `zones bands` prints it numbered
#      with its digest, which is what the verdict must quote; a raw read of the
#      ALTO gives neither, and numbering bands by eye is how an edit comes to name
#      the wrong band.
#
# Allow decisions are returned rather than deferred, for collator-guard.sh's
# reason: an enumerated surface is checked here, and handing it back to the
# permission flow asks a human about every call of a batch.
#
# What this hook CANNOT check: which page is this agent's. It may write any
# page's verdict; the contract says only the ones `claim` gave it.

INPUT=$(cat)
TOOL=$(printf '%s' "$INPUT" | jq -r '.tool_name // empty')

allow() {
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":%s}}\n' \
    "$(printf '%s' "$1" | jq -Rs .)"
  exit 0
}

readable() {
  case "$1" in *..*) return 1 ;; esac
  case "$1" in
    # The page images: the composite `ocr numbered` writes, the zooms, the scan.
    */review/*|*/scans/*) return 0 ;;
    # The types' declarations and the book's design notes.
    */config/zones.json|*/docs/multitext.md|docs/multitext.md) return 0 ;;
  esac
  return 1
}

case "$TOOL" in
  Read)
    P=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty')
    case "$P" in
      */mz/zones/*|*/mz/ocr/*|*/gt/*)
        echo "Blocked: read the rule's file through 'uv run harness zones bands PP-NNN --root …'. It prints every band numbered, with its lines and the file's sha256, which your verdict must quote; the raw ALTO gives neither, and gt/ is a human's store, which this pass never reads." >&2
        exit 2 ;;
    esac
    readable "$P" && allow "zones reviewer reading a page image, the zone config or the book's notes"
    echo "Blocked: you read the page images under review/ and scans/, config/zones.json and docs/multitext.md. Everything else you need comes from the verbs. If something you genuinely need is outside that, say so in your report." >&2
    exit 2 ;;

  Write|Edit)
    P=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty')
    case "$P" in
      *..*) ;;
      */review/[0-9]-[0-9][0-9][0-9]/zones.json) allow "zones reviewer writing its verdict" ;;
    esac
    echo "Blocked: you write exactly one kind of file, review/PP-NNN/zones.json, the verdict on a page 'zones claim' gave you. gt/ is a human's, mz/ is the rule's, and a doubt you cannot settle is a note in the verdict, never a change to something else." >&2
    exit 2 ;;
esac

COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')
[ -z "$COMMAND" ] && exit 0

# One plain invocation, scanned with quote state: collator-guard.sh has the why.
BAD=$(printf '%s' "$COMMAND" | awk '
  BEGIN { q = "" }
  {
    n = length($0)
    for (i = 1; i <= n; i++) {
      c = substr($0, i, 1)
      if (q != "\x27" && c == "\\") { i++; continue }
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
  echo "Blocked: run one plain command at a time — no pipes, chaining, substitution or redirection. The verbs print everything you need; read their output whole." >&2
  exit 2
fi

if printf '%s' "$COMMAND" | grep -qE '^uv run harness (zones (claim|bands|verdict)|ocr (numbered|zoom|lines)|verbs show)( |$)'; then
  case "$COMMAND" in
    *--all*)
      echo "Blocked: no --all form of anything; you review the pages 'zones claim' gives you, one at a time." >&2
      exit 2 ;;
    *--commit*)
      echo "Blocked: nothing on your surface writes a store. Your one write is review/PP-NNN/zones.json, with Write." >&2
      exit 2 ;;
  esac
  allow "zones reviewer running a verb from its closed surface"
fi

echo "Blocked: your Bash surface is exactly: uv run harness {zones claim|bands|verdict, ocr numbered|zoom|lines, verbs show}, one plain command, no --all, no --commit. Everything else (queue, reconcile, propose, edit, git, python) is not yours. If a tool you need is missing, say so in your report." >&2
exit 2
