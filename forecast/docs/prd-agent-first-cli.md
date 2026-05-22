# PRD: Agent-First CLI With Visual Snapshots

## Status

Draft v1

## One-line product definition

MiroFish becomes a headless, agent-first simulation tool that runs from a CLI, emits machine-readable outputs, and generates visual snapshots of swarm behavior as artifacts.

## Problem

The current product surface is centered on a large browser workflow. That is expensive to maintain and is not the best interface for agents, scripts, or automation. The most valuable human-facing output is not the full app workflow; it is the resulting artifacts:

- prediction summary
- run metadata
- swarm snapshots
- timelines
- cluster views

The product should be operable without a browser.

## Product decision

The primary interface is a JSON-first CLI.

The browser UI is not required for v1. If retained later, it should be a minimal artifact viewer rather than a workflow shell.

## Goals

1. Make the full prediction workflow runnable from a non-interactive CLI.
2. Make the CLI easy for agents to call reliably.
3. Generate useful visual snapshots as run artifacts.
4. Make each run immutable and reproducible enough to inspect after completion.
5. Reduce product surface area by removing workflow logic from the frontend.

## Non-goals

1. Maintain the current full multi-step frontend as a first-class product surface.
2. Require a browser for uploads, orchestration, or report access.
3. Build a rich interactive GUI in v1.
4. Redesign the simulation engine in the same phase unless it blocks the CLI product.
5. Optimize for casual human-first onboarding before the agent workflow is stable.

## Target users

### Primary

- coding agents
- automation scripts
- technical operators

### Secondary

- humans reviewing outputs after runs complete

## Core jobs to be done

1. Provide source documents and a simulation requirement.
2. Run the end-to-end workflow from terminal or agent.
3. Poll or wait for completion.
4. Read structured outputs.
5. Inspect generated visual snapshots and summaries.
6. Re-run with modified inputs.

## v1 product shape

### Primary interface

A single CLI executable, `agentcy-echo` (historically `mirofish`).

### Optional human-facing surface

None in v1.

If later needed, add a minimal artifact viewer that:

- lists runs
- opens snapshot files
- opens generated reports
- shows logs and failure reasons

It must not own workflow state.

## CLI principles

The CLI must be:

- non-interactive by default
- deterministic in command shape
- JSON-first
- stable in exit codes
- scriptable
- id-based across the full workflow

### Required CLI behavior

1. `stdout` is reserved for result payloads.
2. `stderr` is reserved for logs and progress.
3. `--json` is supported on all stateful commands.
4. The end-to-end `run` command blocks by default and accepts `--wait` for compatibility.
5. Failures return non-zero exit codes.
6. Returned IDs are stable and reusable across commands.
7. A bounded `--smoke` mode exists for fast deterministic artifact proof when the live OASIS runtime is unavailable or too slow.

## Proposed command surface

### Public surface

- `agentcy-echo run`
- `agentcy-echo runs list`
- `agentcy-echo runs status`
- `agentcy-echo runs export`

Step-level commands are not part of the public v1 CLI.

Graph build, simulation preparation, simulation execution, and report generation remain internal workflow stages behind `agentcy-echo run`.

## Example command shape

```bash
agentcy-echo run \
  --files docs/policy.pdf notes/context.md \
  --requirement "Predict public reaction over 30 days" \
  --output-dir uploads/runs \
  --wait \
  --json
```

Bounded fast-path for e2e validation:

```bash
agentcy-echo run \
  --files docs/policy.pdf notes/context.md \
  --requirement "Predict public reaction over 30 days" \
  --smoke \
  --json
```

`--smoke` keeps ontology, graph build, and profile/config preparation live, then skips the long OASIS subprocess and emits deterministic timeline/report/eval artifacts instead.

## Run artifacts

Each completed run writes a dedicated run directory:

```text
uploads/runs/<run_id>/
  manifest.json
  input/
    requirement.txt
    source_files/
  graph/
    graph.json
    graph_summary.json
  simulation/
    config.json
    actions.jsonl
    timeline.json
    top_agents.json
  report/
    summary.json
    report.md
  eval/
    run_eval.v1.json
  visuals/
    swarm-overview.svg
    cluster-map.svg
    timeline.svg
    platform-split.svg
  logs/
    run.log
    llm_telemetry.jsonl
```

## Visual snapshot requirements

The system must generate visual artifacts without a browser session.

### Required v1 visuals

1. Swarm overview snapshot
   - graph or network-level view of entities/agents
2. Cluster map
   - major opinion groups or coalitions
3. Timeline snapshot
   - key events, shifts, and inflection points
4. Platform split snapshot
   - Twitter vs Reddit behavior comparison when both exist

### Output formats

- SVG required
- PNG optional
- Self-contained HTML optional, not required for v1

## Snapshot rules

Run artifacts are immutable after launch.

At simulation start, the system freezes the effective inputs into the run folder:

- uploaded source documents
- generated ontology
- generated profiles
- simulation config

No later command mutates those files in place. Re-runs create new run IDs.

## State model

The system needs one source of truth for run state.

### Required run states

- `created`
- `graph_building`
- `graph_ready`
- `simulation_preparing`
- `simulation_ready`
- `simulation_running`
- `simulation_completed`
- `report_generating`
- `completed`
- `failed`

### Required metadata

- `run_id`
- `project_id`
- `graph_id`
- `simulation_id`
- `report_id`
- `status`
- `created_at`
- `updated_at`
- `error`

## Backend strategy

v1 should wrap the existing composable backend tools rather than expose raw scripts directly.

Use the existing tool layer as the orchestration boundary:

- ontology generation
- graph build
- simulation prepare
- simulation run
- report generation

The raw OASIS runner scripts remain internal implementation details.

## Scope cuts

The following should be stripped from the primary product path:

1. Full routed frontend workflow
2. Browser-owned step orchestration
3. Browser-required graph inspection
4. Rich interactive post-run chat UI
5. Large amounts of duplicated state between frontend, task files, and run state files

## v1 acceptance criteria

The refactor is done when all of the following are true:

1. A user or agent can run the core workflow without opening a browser.
2. The CLI supports `--json` and returns machine-readable payloads for its small public command surface.
3. Each run creates an immutable run directory with manifest, report, logs, and visual snapshots.
4. The generated visual snapshots are usable without the frontend.
5. The browser app is no longer required for normal operation.
6. The system can list prior runs and inspect their status from the CLI.
7. Failure modes are explicit, with non-zero exit codes and persisted error details.
8. Step-level orchestration commands are not exposed as public CLI APIs.

## Implementation phases

### Phase 1: CLI shell over existing backend

- add a real CLI entrypoint
- wrap the backend tool classes
- standardize JSON output
- standardize status reporting for completed runs

### Phase 2: Immutable run artifacts

- introduce run manifests
- freeze effective inputs at launch
- write outputs to a dedicated run directory
- unify runtime state

### Phase 3: Visual snapshot generation

- generate SVG snapshots from graph and simulation outputs
- persist visuals in `visuals/`
- expose export/open commands from CLI

### Phase 4: Strip UI from the critical path

- stop depending on the frontend for orchestration
- keep or remove the frontend based on whether an artifact viewer is still useful

## Risks

1. The existing simulation/report architecture may still be too heavy for CLI-based LLM providers under long runs; the bounded `--smoke` path helps with artifact proof, but it does not replace a full behavioral simulation.
2. Report generation and live interview features may remain the least reliable parts of the pipeline.
3. Snapshot generation can drift from the underlying state if run artifacts are not frozen correctly.

## Open questions

1. Does v1 keep report chat and agent interview commands, or defer them until the core run flow is stable?
2. Do we keep the current OASIS runtime unchanged in v1, or move immediately to a lighter batch simulation model?
3. Should HTML visual artifacts be generated in v1, or only SVG/PNG snapshots?

## Current recommendation

Proceed with the agent-first CLI and snapshot artifact strategy now.

Do not invest further in the current full workflow UI until the CLI product and immutable run artifact model are stable.
