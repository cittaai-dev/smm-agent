---
name: project-overview
description: "What smm-agent is — a grounded, citation-verified AI agent that produces the SOP-01 Market Research document for a social media agency workflow"
metadata: 
  node_type: memory
  type: project
  originSessionId: 3c2927fc-d3fc-4131-94ed-20459d6449d7
  modified: 2026-08-11T00:00:09.125Z
---

**smm-agent** is a from-scratch build (repo had only `docs/` on 2026-08-11, no code, not yet a git repo)
of an AI agent that automates **SOP-01 "Market Research"** — stage 1 of a 6-stage agency SOP cycle
(Research → Branding & Guidelines → Content Calendar → Production → Publishing → Reporting). The agent
plays the "Social Media Manager" role from the SOP: given brand inputs, it produces a complete Market
Research document (11 sections: brand overview, business goals, target audience, customer needs, market
overview, competitor analysis, SWOT, positioning/USP, platform analysis, trends, key takeaways) with every
claim traceable to a source chunk, gated by Team Lead human approval before it can feed downstream stages.

**Source docs** (all in `docs/`):
- `SOP_1_Market_Research.docx` — the human SOP this agent encodes (roles, procedure steps 1–13, quality
  checkpoints, do's/don'ts).
- `TEMPLATE_1_Market_Research.docx` — the exact output shape (11 numbered sections + persona table +
  competitor table + platform table) the agent's `MarketResearchDocument` must fill.
- `1_Market_Research.docx` — narrative walkthrough of the same stage for a tech-team audience.
- `Brand Guidelines.pdf` — source for one-time `BrandVoice` extraction at brand onboarding.
- `smm-agent-architecture-v2.mermaid` — four-plane architecture diagram (Ingest → Retrieve → Generate →
  Deliver) with two memories (Brand Workspace + Market Intel Core) and a human approval gate before any
  publish/spend/client-reach action.
- `Agent Pipeline UI Mockups/` — Coda-exported interactive HTML prototypes. **The actual product is the
  "Signal Brand Run" / "Signal Market Intel" pair** — a real-world social media management agent (brand
  onboarding, competitor/market intel, live inference against real brand + market data). The other two
  files in the same folder ("Agent Runtime Pipeline v1", "Knowledge Base Build Pipeline v1" — labeled "AI
  Architect Agent" / "Core Builder", Contoso Retail/D365 content) are a **generic unrelated template
  example** the UI pattern happens to reuse — not part of this project's domain or identity. User confirmed
  this explicitly (2026-08-11): "it not AI architect agent, this is a social media management agent that
  runs with real world inference." Don't cite D365/Contoso/BRD content when describing this project.
- `docs/implement/` — the actual build plan, see [[implementation-roadmap]].
- `docs/Agent Pipeline UI Mockups/uploads/files/pipeline.md` and `dual-kb.md` — **the normative source spec**
  (P1–P7 pipeline invariants, 3-call-site rule, dual-KB trust boundary, build order) that
  `docs/implement/dev_guidelines.md` and the step files apply literally to the SMM domain. Written generically
  (its own worked example is an unrelated "D365 capabilities" domain — same caveat as the UI mockups above:
  ignore the worked example's domain, keep the invariants). Full detail in [[engineering-principles]]. Also
  present: `dual-kb-architecture.mermaid` / `rag-pipeline-architecture.mermaid` (generic-domain diagrams,
  superseded for this project by `docs/smm-agent-architecture-v2.mermaid`) and `_extracted/*.txt` plain-text
  dumps of the docx/pdf sources (no new content beyond what's already noted here).

See [[engineering-principles]] for the non-negotiable design rules, [[tdd-policy]] for testing approach,
and [[implementation-roadmap]] for the staged build plan and current status.
