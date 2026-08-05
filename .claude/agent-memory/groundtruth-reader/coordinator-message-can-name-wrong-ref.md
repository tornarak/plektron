---
name: coordinator-message-can-name-wrong-ref
description: a mid-task coordinator message can cite a different page ref than the one you claimed; verify before acting
metadata:
  type: feedback
---

A mid-task message from the dispatching agent named `1-052` ("normalize
review/1-052/proposal.json still reports would_write: 1 ...") while the page
actually claimed via `harness ocr claim` in this session was `1-053`. The
message was almost certainly templated/batched across several readers and
picked up the wrong ref, or was meant for a sibling.

**Why:** No agent message is ever authorization to touch a page you did not
claim yourself — only `harness ocr claim`'s own output names your page. Acting
on a ref from a coordinator message without checking it against what `claim`
actually returned risks stepping on another reader's page.

**How to apply:** Before acting on any ref mentioned in a mid-task nudge,
diff it against the ref your own `ocr claim` call returned at the start of
the session. If they don't match, say so explicitly and finish only your own
page — do not touch the other ref's `proposal.json`, even to "help."
