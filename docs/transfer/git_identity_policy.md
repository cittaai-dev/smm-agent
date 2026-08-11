---
name: git-identity-policy
description: "smm-agent must be pushed/committed under the cittaai-dev GitHub account, not kranthy09 — and no remote repo exists yet, ask before creating one"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 3c2927fc-d3fc-4131-94ed-20459d6449d7
  modified: 2026-08-11T00:03:32.235Z
---

For the smm-agent repo: all commits/pushes belong to the **cittaai-dev** GitHub identity, not `kranthy09`
(the likely local/global git default). Confirmed by user on 2026-08-11 while scaffolding the project from
`docs/` for the first time.

**Why:** this is an org/client project (cittaai) being built under its own GitHub account, distinct from the
user's personal `kranthy09` account that may be the local git config default.

**Status as of 2026-08-11: done.** Repo created and pushed — https://github.com/cittaai-dev/smm-agent
(private, `main` branch, `origin` tracking). `gh auth status` shows both `cittaai-dev` (active) and
`kranthy09` accounts logged in locally — `cittaai-dev` was already the active `gh` account, so
`gh repo create cittaai-dev/smm-agent --source=. --remote=origin` worked without needing to switch. If `gh`
ever shows `kranthy09` as active before creating/pushing to a cittaai project, run
`gh auth switch --hostname github.com --user cittaai-dev` first (or pass `--user cittaai-dev` where
supported) rather than assuming the active account is correct.

**How to apply going forward:**
- For *new* cittaai-org repos: still confirm with the user before creating (this rule was specifically about
  smm-agent's first repo, which is now resolved, but the "ask before creating a new remote" default still
  holds for anything not yet confirmed).
- Local commit author is left as the local git config default (`Kranthi Kumar
  <g.kranthi2507@gmail.com>`) — the user only flagged the GitHub *account/destination*, not commit author
  identity, so this was not changed and shouldn't be assumed to need changing.
