# Principal Patterns

Agentcy follows a small-core architecture. The default path should be cheap, local, repeatable, and easy to inspect. Search, forecasting, publishing, live providers, and optimization loops are extensions, not the baseline.

## Reference Patterns

- Karpathy's LLM Wiki pattern separates raw sources, derived wiki, and schema. Agentcy maps this to human-owned brand kits, generated artifacts, and protocol/agent instructions.
- Karpathy's autoresearch pattern keeps a fixed evaluation harness, one clear mutable surface, one metric, and a keep-or-discard loop. Agentcy maps this to deterministic artifact generation first, then optional measured optimization of one mode at a time.

Sources:

- <https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f>
- <https://github.com/karpathy/autoresearch>

## Agentcy Mapping

| Layer | Agentcy Form | Rule |
| --- | --- | --- |
| Raw sources | `BRAND.md`, `DESIGN.md`, assets, source docs | Human-owned. Do not mutate during generation. |
| Compiled artifacts | `brief.v1`, Studio inspect output, rendered cards, reports | Agent-owned. Regenerate from sources. |
| Schema | `AGENTS.md`, skills, protocol schemas, docs | Defines how agents operate and how artifacts are shaped. |
| Experiment surface | One prompt/template/mode at a time | Optimize only with a fixed eval and a clear keep/discard rule. |

## Default Pipeline

`agentcy pipeline run` is the essential path:

```text
brief input + brand kit -> brief.v1 -> Studio draft/render -> inspectable artifacts
```

It does not run Voice, Forecast, Measure, provider-backed image generation, or publish by default.

Use opt-ins for heavier work:

- `--persona` and `--persona-eval` for Voice
- `--with-forecast --files ...` for Forecast
- `--publish` for review/publish
- `pipeline update` and `pipeline study` for Measure after real outcomes exist

## Product Rule

If a capability does not improve the repeated quality of artifacts from the same brand/design/content foundation, it does not belong in the core path. It can exist as an extension only when it declares its inputs, output artifact, provider cost, and verification command.
