# agentcy-voice

Part of the agentcy monorepo — invoke via `agentcy voice` or `agentcy-voice`.

Manage, compose, test, and evolve AI personas.

## Current surfaces (monorepo)

- repo: `agentcy`
- Python distribution/package: `agentcy-voice`
- Python import path: `agentcy_voice`
- installed CLI: `agentcy-voice`
- dispatcher alias: `agentcy voice ...`
- writer contract: `voice_pack.v1.writer = { repo: "agentcy-voice", module: "agentcy-voice" }`

## Install

```bash
uv pip install -e .
```

## What It Does

**Turn AI personas from throwaway prompt strings into managed, testable, self-improving assets.**

Recent repo-local upgrade: persona bootstrap now runs a repair pass for internal consistency, and `agentcy-voice test` can generate `basic`, `mixed`, and `stress` eval tiers with optional saved reports for later operator review.

| Without agentcy-voice | With agentcy-voice |
|---------------|------------|
| Prompts scattered across files | `agentcy-voice ls` — versioned library |
| Made-up traits | Real person data via Exa |
| "Seems right?" | Consistency score: 73% |
| Manual prompt tweaking | GEPA auto-optimizes |
| Persona degrades over chat | Drift detection + refresh |
| Static forever | Self-learning from interactions |

## Quick Start

### CLI

```bash
# Bootstrap a persona with AI
agentcy-voice create "skeptical investigative journalist"

# Or base on a real person
agentcy-voice create --like "Marc Andreessen" "tech investor"

# Chat with it
agentcy-voice chat journalist

# Check consistency with generated eval tiers
agentcy-voice test journalist --difficulty stress --save-report

# Inspect saved eval reports
agentcy-voice evals journalist --latest

# Compare the latest two eval reports
agentcy-voice evals journalist --compare

# Let it learn from interactions
agentcy-voice learn journalist --apply
```

### Library

```python
from agentcy_voice import Persona, bootstrap_from_description, LLMError

# Load and chat
vc = Persona.load("voice/personas/tech-investor.yaml")
response = vc.chat("Should I raise now?")

# Multi-turn conversation
with vc.conversation() as conv:
    print(conv.send("I have $50k MRR"))
    print(conv.send("Should I raise?"))

# Streaming
for chunk in vc.stream("Tell me about market timing"):
    print(chunk, end="", flush=True)

# Synthetic user generation (for testing chatbots)
angry = Persona(**bootstrap_from_description("frustrated customer"))
test_input = angry.as_user("asking about refund policy")
bot_response = my_chatbot(test_input)

# Batch generation
responses = persona.generate(["prompt1", "prompt2", "prompt3"])

# Error handling
try:
    response = persona.chat("Hello")
except LLMError as e:
    print(f"LLM failed: {e}")
```

## Commands

```bash
# GLOBAL FLAGS
agentcy-voice --version                   # Show version
agentcy-voice --json ls                   # Output as JSON (for scripting)
agentcy-voice --quiet ls                  # Minimal output (names only)

# CREATE
agentcy-voice init scientist              # Empty template (manual edit)
agentcy-voice create "description"        # AI-generated from description
agentcy-voice create --like "Person"      # Based on real person (Exa)
agentcy-voice create --role "Job Title"   # Based on job role

# MANAGE
agentcy-voice ls                          # List all personas
agentcy-voice show scientist              # Show details
agentcy-voice edit scientist              # Open in $EDITOR
agentcy-voice rm scientist                # Delete

# COMPOSE
agentcy-voice mix scientist comedian --as science-comedian

# ENRICH
agentcy-voice enrich scientist --query "MIT AI researcher"

# TEST & OPTIMIZE
agentcy-voice test scientist --difficulty mixed --samples 6     # structured eval tiers + drift-based scoring
agentcy-voice test scientist --cases cases.json --save-report   # custom eval corpus + saved report under ~/.agentcy/evals/
agentcy-voice evals scientist --latest                          # inspect latest saved eval report
agentcy-voice evals scientist --compare                         # compare latest vs previous saved report
agentcy-voice optimize scientist --iterations 50               # GEPA prompt evolution
agentcy-voice drift scientist "response text"                  # Check single response

# LEARN & IMPROVE
agentcy-voice learn scientist --apply     # Learn from logged interactions
agentcy-voice critique scientist --apply  # Self-critique and improve

# USE
agentcy-voice chat scientist              # Interactive REPL
agentcy-voice ask scientist "question"    # One-shot
echo "question" | agentcy-voice ask scientist -  # Pipe from stdin

# EXPORT
agentcy-voice export scientist --to voice-pack.v1  # Canonical Agentcy voice_pack.v1 JSON
agentcy-voice export scientist --to eliza       # PersonaKit/Eliza
agentcy-voice export scientist --to v2          # Character Card V2
agentcy-voice export scientist --to ollama      # Ollama Modelfile
agentcy-voice export scientist --to hub         # PERSONA HUB format
```

The canonical family protocol for downstream Agentcy handoffs lives in `../protocols/voice_pack.v1.schema.json` and `../protocols/examples/voice_pack.v1.*.json`. `agentcy-voice` owns writing that artifact; strategy, briefs, and publishing stay in sibling repos.


## Persona Format

```yaml
name: scientist
version: 1
description: A curious research scientist who values evidence

traits:
  - curious
  - methodical
  - precise
  - humble about uncertainty

voice:
  tone: academic
  vocabulary: technical
  patterns:
    - "The evidence suggests..."
    - "It's worth noting that..."

boundaries:
  - Never claim certainty without data
  - Acknowledge limitations

examples:
  - user: "Is this true?"
    assistant: "The current evidence suggests..."

dynamic:
  source: exa
  query: "Dr. Jane Smith MIT"
  refresh: weekly

providers:
  default: gpt-4o-mini
```

## How It Works

```
┌──────────────────────────────────────────────────────────────────┐
│                         LIFECYCLE                                │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  CREATE ──▶ ENRICH ──▶ TEST ──▶ OPTIMIZE ──▶ USE ──▶ LEARN      │
│     │         │         │          │         │         │        │
│     ▼         ▼         ▼          ▼         ▼         ▼        │
│  Bootstrap  Exa      DSPy       GEPA     Chat/Ask  Analyze      │
│  from desc  people   fidelity   evolve   with      interactions │
│  or person  search   scoring    prompt   drift     & improve    │
│                                          detect                  │
│                                                                  │
│                    ◀──── CONTINUOUS IMPROVEMENT ────▶           │
└──────────────────────────────────────────────────────────────────┘
```

## Research Foundation

Built on techniques from recent persona research:

| Paper | Technique Used |
|-------|----------------|
| [Scaling Synthetic Data with 1B Personas](https://arxiv.org/abs/2406.20094) | Persona Hub integration |
| [Measuring Persona Drift](https://arxiv.org/abs/2402.10962) | Drift detection |
| [Persona Vectors](https://arxiv.org/abs/2507.21509) | Consistency monitoring |
| [Self-Improving Agents](https://arxiv.org/abs/2510.07841) | Learning from interactions |
| [PersonaGym](https://arxiv.org/abs/2407.18416) | Fidelity evaluation |
| [RoleLLM](https://arxiv.org/abs/2310.00746) | Role-conditioned tuning |

## Stack

- **typer** — CLI framework
- **dspy** — LLM programming & signatures
- **gepa** — Genetic-Pareto prompt optimization
- **litellm** — Multi-provider LLM calls (via centralized `llm.py`)
- **exa-py** — People search enrichment
- **pydantic** — Data validation
- **rich** — Terminal formatting

## Environment Variables

```bash
OPENAI_API_KEY=sk-...      # Required for most features
EXA_API_KEY=...            # Required for enrich, create --like
```

## Development

```bash
cd ~/projects/agentcy/voice
uv sync --dev
uv run agentcy-voice --help
uv run pytest
ruff check src/
```

## Why agentcy-voice?

**Personas are the new prompts.** As AI systems get more capable, the bottleneck shifts from "can it do X?" to "does it behave consistently as Y?"

agentcy-voice treats personas as first-class software artifacts:
- **Versioned** — Track changes, roll back
- **Testable** — Measure consistency, catch regressions
- **Composable** — Mix traits, extend bases
- **Evolvable** — Learn from use, self-improve
- **Portable** — Export to any format/platform, including canonical `voice_pack.v1`

---

**agentcy-voice** = Git + npm + CI for AI personas
