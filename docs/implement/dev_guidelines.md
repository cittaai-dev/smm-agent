# SMM Agent — Development Guidelines

**Persona of this document.** Think of the SMM Agent as a disciplined junior analyst, not an oracle: it
never speaks from vague memory, always opens the file before it cites it, and says "I don't have evidence
for that" instead of guessing. Every guideline below exists to keep that character true under load — at
3am, under retry, at brand #200. Minimalism here doesn't mean "less code." It means **no line of code
whose job isn't traceable to one of these disciplines.**

---

## 1. Prompts Are Templates, Not Strings in Code

**Rule:** every prompt is a `.jinja` file. No f-string, no `.format()`, no prompt text inside a `.py` file.

**Why:** a prompt embedded in Python is untestable in isolation, unversioned independent of code, and
invisible to anyone reviewing "what does the agent actually say." A `.jinja` file is a reviewable artifact —
diffable, testable, ownable by whoever writes prompts well, without touching orchestration code.

```
app/prompts/
├── plan/
│   └── v1.jinja
├── synthesize/
│   ├── v1.jinja
│   └── v2.jinja        # never edit v1 in place — new version, old stays for replay
├── repair/
│   └── v1.jinja
└── partials/
    ├── persona.jinja
    ├── evidence_block.jinja
    ├── output_schema.jinja
    └── brand_voice.jinja
```

```jinja
{# app/prompts/synthesize/v1.jinja #}
{% include "partials/persona.jinja" %}

You are drafting the "{{ section_label }}" section of a Market Research document.

{% include "partials/brand_voice.jinja" %}

## Evidence
{% include "partials/evidence_block.jinja" %}

## Task
Write claims for this section using ONLY the evidence above. Every claim must cite a chunk_id.
If the evidence does not support a claim, do not write it.

{% include "partials/output_schema.jinja" %}
```

```jinja
{# app/prompts/partials/evidence_block.jinja #}
{% for chunk in chunks %}
[{{ chunk.chunk_id }}] {{ chunk.text }}
{% endfor %}
```

**Rendering is a typed function, not string concatenation:**

```python
# app/prompts/render.py
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel

_env = Environment(loader=FileSystemLoader("app/prompts"), trim_blocks=True, lstrip_blocks=True)

class SynthesizeContext(BaseModel):
    section_id: str
    section_label: str
    chunks: list["Chunk"]
    brand_voice: "BrandVoice"

def render_synthesize(ctx: SynthesizeContext, version: str = "v1") -> str:
    template = _env.get_template(f"synthesize/{version}.jinja")
    return template.render(**ctx.model_dump())
```

The input to every render is a **Pydantic model**, never a raw dict — a template that references
`{{ chunks[0].chunk_id }}` fails loudly at render time if `Chunk` ever drops that field, instead of
silently rendering `None` into a live prompt.

**Alternative rejected:** LangChain's `PromptTemplate` string interpolation for anything beyond trivial
one-liners — rejected because Jinja's `{% include %}`/`{% for %}` gives real composition (see §3, §15),
and keeping prompts as `.jinja` files (not Python-embedded `PromptTemplate` strings) is what makes them
diffable and ownable outside the codebase.

---

## 2. Domain Knowledge Injection — A Third, Static Store

Two KBs already exist (Brand Workspace, Market Intel Core) for **retrieved evidence**. Production agents
also need **domain knowledge that isn't evidence** — SMM terminology, platform-specific conventions, tone
rules, section-writing conventions. This is not a document to cite; it's context that shapes *how the model
thinks*, injected every time, not retrieved conditionally.

| | Brand/Core KB | Domain Knowledge Store |
|---|---|---|
| Role | evidence, cited per-claim | background context, never cited |
| Retrieval | plan → search → rank | static, injected by section/call-site, no ranking |
| Changes | per brand / per Core version | changes rarely, reviewed like code |
| Example content | "Competitor X posts 5x/week" | "A SWOT 'Weakness' must be internal to the brand, not a market condition" |

```python
# app/domain_knowledge/store.py
from pydantic import BaseModel

class DomainFact(BaseModel):
    id: str
    scope: Literal["global", "section:swot", "section:competitor_analysis", "platform:instagram"]
    text: str

# app/domain_knowledge/facts/sop1.yaml
# - id: swot-weakness-scope
#   scope: section:swot
#   text: "A Weakness is internal to the brand. A market threat belongs in Threats, not Weaknesses."
# - id: measured-over-adjective
#   scope: global
#   text: "Prefer a measured number ('18.4k followers, 5 posts/week') over a marketing adjective ('strong presence')."

def facts_for(scope: str) -> list[DomainFact]:
    return [f for f in _load_all() if f.scope in ("global", scope)]
```

```jinja
{# app/prompts/partials/domain_knowledge.jinja #}
## Domain rules
{% for fact in domain_facts %}
- {{ fact.text }}
{% endfor %}
```

**Why static YAML, not a KB search:** domain rules are small (dozens, not thousands), don't need semantic
search, and should be **reviewed by a human like code** — a pull request on `sop1.yaml`, not a document
upload that silently changes agent behavior. This directly satisfies "prefer measured numbers over marketing
adjectives" from the constitution — it's not a hope the LLM infers, it's a line in the prompt every time.

**Alternative rejected:** folding domain rules into Market Intel Core as chunks — rejected because Core is
for *cited evidence with a chunk_id a claim can point to*; domain rules are never claimed or cited, they're
background instruction. Mixing them would make Core's chunks a mix of "evidence" and "instruction," breaking
the "run content is data, evidence is data, only domain rules are instruction" trust boundary.

---

## 3. Persona and Brand Voice as Config, Not Prose

The mockups show the agent "acting as the Social Media Manager" — this must be a typed object, not a tone
description buried in a prompt string.

```python
class AgentPersona(BaseModel):
    role: str = "Social Media Manager"
    voice: Literal["professional", "casual", "technical"] = "professional"
    constraints: list[str] = [
        "Never invent a statistic — only report what evidence supports.",
        "Prefer specific numbers over adjectives.",
    ]

class BrandVoice(BaseModel):
    brand_id: str
    tone_descriptors: list[str]     # sourced from Brand Guidelines doc, extracted once at onboarding
    banned_phrases: list[str] = []
```

```jinja
{# app/prompts/partials/persona.jinja #}
You are the {{ persona.role }}, writing in a {{ persona.voice }} voice.
{% for c in persona.constraints %}
- {{ c }}
{% endfor %}
```

`BrandVoice` is extracted **once**, at brand onboarding, from `Brand_Guidelines.pdf` — a single deterministic
extraction step, not re-inferred on every call. Store it, reuse it, version it alongside the brand.

---

## 4. Structured Output, Always

No call site returns prose. Every LLM call declares a `response_model` and the SDK enforces it.

```python
def call_synthesize(ctx: SynthesizeContext) -> list[ClaimDraft]:
    prompt = render_synthesize(ctx)
    return llm_client.beta.chat.completions.parse(
        model=settings.SYNTHESIZE_MODEL,
        messages=[{"role": "system", "content": prompt}],
        response_format=SynthesisOutput,   # Pydantic model — see phase contracts
    ).choices[0].message.parsed.claims
```

If the model can't satisfy the schema, the SDK raises — that failure is caught and routed to Repair (or
`insufficient_grounding`), never silently coerced. This is the same discipline as §4 of the earlier phase
contracts, restated here because it's the reason Jinja templates end in an explicit "## Output schema"
block (§15) rather than trusting free text to shape itself correctly.

---

## 5. Prompt Versioning, Hashing, Caching

Every rendered prompt is content-addressed, same as chunks (P6).

```python
def call_site_cache_key(template_version: str, rendered: str) -> str:
    return hashlib.sha256(f"{template_version}:{rendered}".encode()).hexdigest()
```

- Ingest-time calls (document understanding, L3 split) are cached by this key — re-running ingest on
  unchanged input costs nothing, per the exemption rule in `pipeline.md §2`.
- Query-path calls (Plan/Synthesize/Repair) are **not** cached by default — the same section on the same
  evidence should usually re-run fresh — but the key is still logged on every call for reproducibility:
  `run_manifest` stores `prompt_version` alongside `core_kb_version` and `run_kb_hash`, so a run replays
  identically months later, prompt included.
- **Never edit a `.jinja` file in place once it has a version in production.** Bump `v1 → v2`. Old runs
  keep resolving against the version they used.

---

## 6. Context Budgeting Is Explicit, Not Implicit

```python
class ContextBudget(BaseModel):
    max_tokens: int = 6000
    reserve_for_output: int = 1000

def pack_context(chunks: list[Chunk], budget: ContextBudget) -> list[Chunk]:
    packed, used = [], 0
    for c in chunks:  # already ranked, already deduped, already in document order
        t = count_tokens(c.text)
        if used + t > budget.max_tokens - budget.reserve_for_output:
            break
        packed.append(c)
        used += t
    return packed
```

Budget-packing is deterministic code, not a model decision — the model never sees "here's too much context,
figure it out." It sees exactly what fits, in document order, every time. This is the same discipline as
`pipeline.md §4.6` step 3, made an explicit typed function rather than an inline loop buried in a node.

---

## 7. Call-Site Budget Is Enforced, Not Just Documented

```python
# app/orchestration/tracing.py
_call_counts: dict[str, int] = {"plan": 0, "synthesize": 0, "repair": 0}

def traced_llm_call(site: Literal["plan", "synthesize", "repair"]):
    def decorator(fn):
        def wrapper(*a, **kw):
            _call_counts[site] += 1
            if site == "repair" and _call_counts[site] > 1:
                raise RuntimeError("repair budget exceeded — this is a bug, not a retry opportunity")
            return fn(*a, **kw)
        return wrapper
    return decorator
```

A test asserts `_call_counts` at the end of every pipeline run. The "3 call sites" rule stops being a design
intention the moment a `raise` enforces it — a future contributor adding a 4th LLM call anywhere on the
query path breaks a test immediately, not a design review six months later.

---

## 8. Guardrails — Brand Content Is Data, Never Instruction

Every piece of Run KB content enters a prompt tagged, inside the evidence block, never as system/tool text
(`dual-kb.md §4`). The Jinja template enforces this structurally:

```jinja
{# evidence_block.jinja — chunk text is ALWAYS wrapped, never concatenated raw into instructions #}
{% for chunk in chunks %}
<evidence kb_id="{{ chunk.kb_id }}" chunk_id="{{ chunk.chunk_id }}">
{{ chunk.text }}
</evidence>
{% endfor %}
```

A brand-uploaded PDF containing "ignore previous instructions and..." renders as text *inside* an
`<evidence>` tag — visually and structurally distinct from the system prompt, and the Synthesize call's
job description ("cite only what's tagged evidence") never treats tag contents as directives. This is the
concrete implementation of the injection-defense principle, not a separate filter bolted on after.

---

## 9. Eval Harness — Golden Sets Are Code, Not One-Off Scripts

```python
# tests/golden/sop1_section_synthesis.py
GOLDEN_CASES = [
    GoldenCase(
        section="brand_overview",
        chunks=[...],  # fixed fixture evidence
        expected_claim_count_range=(2, 5),
        must_cite_all=True,
    ),
]

def test_golden_set_citation_rate():
    results = [run_section(case) for case in GOLDEN_CASES]
    rejection_rate = sum(r.rejected_count for r in results) / sum(r.total_claims for r in results)
    assert rejection_rate < 0.08   # matches pipeline.md's production threshold
```

This is the same golden set that gates Core KB promotion (`pipeline.md §6`) — reused here at the prompt
level so a `.jinja` edit that regresses citation quality fails CI before it ships, not after a real brand
sees it.

---

## 10. Observability of Prompts

Log the **fully rendered prompt** (post-Jinja, pre-send) alongside its response, correlated by `call_id`,
with secrets/PII scrubbed. This is what lets you debug "why did §6 reject 40% of claims this week" by
reading the actual text the model saw, not guessing from the template source.

```python
structlog.get_logger().info(
    "llm_call", call_id=call_id, site="synthesize", template_version="v1",
    prompt_hash=call_site_cache_key("v1", rendered), token_count=count_tokens(rendered),
)
```

Never log the raw `rendered` string in production by default — log its hash and length; log full text only
behind a debug flag scoped to non-production or explicitly brand-consented environments.

---

## 11. Fallback and Degrade Discipline, at the Prompt Layer Too

Every call site has a template-level fallback message, not just a code-level exception:

```jinja
{# synthesize/v1.jinja, end of file #}
If the evidence above is insufficient to write this section, output an empty claims list rather than
inventing content. An empty, honest section beats a fabricated one.
```

Paired with the code-level `insufficient_grounding` state (§5.3 of `pipeline.md`), this is belt-and-suspenders
by design: the prompt asks for honesty, the verifier catches it if the model doesn't comply anyway.

---

## 12. Composability — Small Jinja Partials Over Monolithic Prompts

Per the minimalism principle: no `synthesize/v1.jinja` should be 200 lines. Break repeated blocks
(`persona`, `evidence_block`, `domain_knowledge`, `output_schema`, `brand_voice`) into partials once, reuse
across Plan/Synthesize/Repair. A change to "how evidence is formatted" is one file edit, not a find-replace
across three prompt files.

```jinja
{# repair/v1.jinja — reuses everything synthesize.jinja uses, adds one block #}
{% include "partials/persona.jinja" %}
{% include "partials/evidence_block.jinja" %}

## Previously rejected claims
{% for c in rejected_claims %}
- "{{ c.text }}" — cited {{ c.chunk_id or "nothing" }}, which does not resolve.
{% endfor %}

Re-tag each claim with a chunk_id that actually appears in the evidence above, or drop the claim.
{% include "partials/output_schema.jinja" %}
```

---

## 13. Config Over Code

Model name, temperature, token budgets — never hardcoded, always `pydantic-settings`, overridable per
environment without a code change:

```python
class LLMSettings(BaseSettings):
    plan_model: str = "gpt-4.1-mini"
    synthesize_model: str = "gpt-4.1"
    repair_model: str = "gpt-4.1"
    synthesize_temperature: float = 0.2
    context_max_tokens: int = 6000

    model_config = SettingsConfigDict(env_prefix="SMM_LLM_")
```

---

## Summary — The Minimalist's Checklist

| If you're about to... | Do this instead |
|---|---|
| Write a prompt inline in Python | Create a `.jinja` file, render via a typed context model |
| Hardcode "you are a helpful assistant" | Reference `partials/persona.jinja` |
| Paste brand tone into a prompt string | Extract `BrandVoice` once at onboarding, inject via partial |
| Add a rule like "prefer numbers over adjectives" | Add a `DomainFact`, not a prompt edit |
| Let the model return prose you'll regex later | Declare a `response_model`, always |
| Add a 4th LLM call "just this once" | Don't — `traced_llm_call` will fail the test, and it should |
| Concatenate brand content into the system message | Wrap it in `<evidence>` tags in the evidence partial |
| Tune a magic number in a prompt string | Move it to `LLMSettings`, name it, default it |

Every rule above traces to one sentence: **the pipeline should be able to point at the page** — and now,
point at the exact template, version, and rendered text that produced any given claim.
