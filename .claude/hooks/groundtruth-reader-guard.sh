#!/bin/bash
# PreToolUse guard for the groundtruth-reader subagent: the standing rules made
# mechanical. A checkable rule beats a prohibition — it does not depend on the
# pass behaving. Frontmatter hook, so nothing here constrains the main session
# or any other agent.
#
# An ALLOWLIST, not a denylist. The reader's legitimate Bash surface is a
# closed set of harness verbs; everything else — restore, review, clean, any
# --all sweep, git, python3 -c, ls/cat/find, compound commands — is exactly
# what the hard rules forbid, and a denylist would have to anticipate every
# route around itself. Exit 2 blocks the call and the reader sees the message.

INPUT=$(cat)
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
  exit 0
fi

echo "Blocked by your standing instructions. Your Bash surface is exactly: uv run harness {ocr gaps|lines|numbered|sheets|zoom, proposal fix|check|codepoints|set|replace|marks, corpus normalize, lexicon *, find *} — one plain command, no --all. Everything else (restore, review, clean, views, git, python3, shell listing) is not yours; Glob answers existence, Read answers content, and the verbs answer the rest. If a tool you genuinely need is missing from this list, say so in your report rather than working around it." >&2
exit 2
