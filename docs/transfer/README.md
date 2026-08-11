# Memory transfer

This folder is a full export of the Claude Code auto-memory store for this project
(`~/.claude/projects/-home-kranthi-Projects-citta-smm-agent/memory/`), captured 2026-08-11. It exists so a
new Claude Code session/account can be re-seeded with the exact same project understanding without
re-deriving it from scratch.

## Contents

- `MEMORY.md` — the index (mirrors the original `MEMORY.md`).
- `project_overview.md` — what smm-agent is, source docs, and the D365-mockup caveat.
- `engineering_principles.md` — P1–P7 pipeline invariants, 3-call-site rule, dual-KB trust boundary,
  server-side enforcement rules.
- `tdd_policy.md` — integration-tests-first testing policy.
- `implementation_roadmap.md` — Steps 1–9 staged plan and status as of 2026-08-11 (Step 1 done and merged).
- `git_identity_policy.md` — push/commit under `cittaai-dev`, not `kranthy09`.

Each file is byte-identical to its source in `~/.claude/.../memory/`, including the YAML frontmatter
(`name`, `description`, `metadata.type`) and `[[wikilink]]` cross-references between memories.

## How to re-seed a new system

On the new machine/account, under the same Claude Code memory root for this project
(`~/.claude/projects/<project-slug>/memory/`):

1. Copy `MEMORY.md` and the five topic files from this folder into that memory directory as-is (filenames
   should be `project_overview.md`, `engineering_principles.md`, `tdd_policy.md`,
   `implementation_roadmap.md`, `git_identity_policy.md` — matching the `name:` slug in each file's
   frontmatter with underscores instead of hyphens).
2. On the next session, these will load automatically as auto-memory context, exactly as they did here.

## Staleness warning

`implementation_roadmap.md` and `git_identity_policy.md` describe *state* (what's done, what repo exists)
as of 2026-08-11 — verify against `git log`, GitHub, and the current repo contents before trusting them, per
the project's own memory-staleness policy. `project_overview.md` and `engineering_principles.md` describe
durable design rules and are less likely to go stale, but should still be checked against
`docs/implement/*.md` and `docs/Agent Pipeline UI Mockups/uploads/files/{pipeline,dual-kb}.md`, which remain
the normative source of truth.
