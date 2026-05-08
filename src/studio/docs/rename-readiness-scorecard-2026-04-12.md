# cli-phantom rename-readiness audit for future `agentcy-loom`

Date: 2026-04-12  
Scope: loop-7 repo-local audit of naming surfaces and blockers in `cli-phantom` without renaming anything yet.

## Outcome

`cli-phantom` is already aligned on the canonical family artifact-writer contract for `run_result.v1`:

```json
{
  "repo": "cli-phantom",
  "module": "agentcy-loom"
}
```

That alignment is encoded in `runtime/src/domain/run-result-v1.ts` and is the most important loop-7 invariant for this repo.

Everything else is intentionally mixed:

- repo directory still says `cli-phantom`
- runtime package name is `loom-runtime`
- the active CLI/help surface is `loom`
- README and CLAUDE present the product as `Loom Runtime`
- runtime paths and key prefixes still use `loom` or `loom-runtime`

This is exactly the mixed-state repo described in the family matrix: the runtime already behaves like Loom, while the repo and canonical writer still preserve the current literal repo identity.

## Summary readiness verdict

`cli-phantom` is **not** rename-ready across all surfaces together.

Current honest classification:

- **Repo rename readiness:** partial at best; blocked by repo-path references and the fact that `writer.repo` must remain `cli-phantom` until a literal repo rename really lands
- **Package / binary rename readiness:** closest to ready, because package and CLI already present Loom naming (`loom-runtime`, `loom`), but they are not yet normalized to the future family target `agentcy-loom`
- **All-surfaces-together readiness:** not ready; the repo is intentionally split across `cli-phantom` and Loom-branded runtime surfaces

Loop-7 conclusion: this repo is best described as **runtime/package/binary surfaces already Loom-shaped, repo identity intentionally still Phantom-shaped**.

## Naming audit table

| Surface | Current canonical | Post-rename target | Acceptable legacy alias | Hard blocker |
| --- | --- | --- | --- | --- |
| Repo directory name | `cli-phantom` | `agentcy-loom` | `cli-phantom` in family docs, task taxonomy, and migration notes until a literal repo rename lands | canonical `writer.repo` must stay `cli-phantom` until a real repo rename; repo-path references in docs/tests/tasks still expect `cli-phantom` |
| Package/distribution name | `loom-runtime` in `runtime/package.json` | likely `agentcy-loom` | `loom-runtime` | package target is not yet normalized to family naming and there is no packaged install migration plan yet |
| Import path | runtime-local TypeScript modules under `src/...`; entrypoint `src/cli.ts` / `src/cli/index.ts` | likely unchanged internal module layout plus future family-facing package name | current `src/...` module paths | no public installed package/import contract exists yet, so import-path rename readiness cannot be claimed independently |
| CLI binary | canonical invocation surface is `loom` in help/examples, currently run via `cd runtime && npx tsx src/cli.ts ...` | likely packaged `agentcy-loom` binary, possibly with `loom` alias | `loom`; direct `npx tsx src/cli.ts` invocation | no installed binary exists yet, so binary rename readiness cannot be validated cleanly as a packaged surface |
| Docs/install branding | `cli-phantom` repo plus `Loom Runtime` product/runtime docs | repo/docs/install branding eventually aligned to `agentcy-loom` with legacy guidance | `Loom Runtime`, `cli-phantom` | docs intentionally preserve mixed repo/runtime identity today; install surface is still source-invocation-first rather than package-first |
| Artifact writer fields | `run_result.v1.writer = { repo: "cli-phantom", module: "agentcy-loom" }` | keep `module = "agentcy-loom"`; `repo` changes only after literal repo rename | none beyond the current locked mixed pair | none for loop 7; this surface is already correctly aligned to the family invariant |
| Fixture/test references | parent protocol tests and runtime tests assert `cli-phantom` writer and loom runtime behavior | future repo/path references may move to `agentcy-loom` only when canonical repo rename happens | existing `cli-phantom` references in tests and docs | tests and fixtures correctly preserve current repo identity; broad rewrites now would violate loop-7 rules |
| Runtime path/key prefixes | `state/loom.sqlite`, `loom-runtime/` R2 key prefix, `LOOM_ROOT`, temp/test prefixes like `loom-runtime-`, `loom-cli-`, `loom-brand-`, `loom-lab-` | explicit future `agentcy-loom` policy only if a later migration is approved | existing loom-prefixed runtime keys and paths | runtime prefix migration policy is undefined; changing state/object prefixes prematurely would create unnecessary churn and compatibility risk |

## Canonical surfaces already aligned

### Canonical artifact writer alignment

Sources:

- `cli-phantom/runtime/src/domain/run-result-v1.ts`
- `cli-phantom/runtime/src/runtime/runtime.test.ts`
- `rename-readiness-matrix-2026-04-12.md`

Current canonical writer:

```ts
writer: {
  repo: 'cli-phantom',
  module: 'agentcy-loom',
}
```

Interpretation:

- `writer.repo` correctly remains the current literal repo name `cli-phantom`
- `writer.module` correctly carries the future family module `agentcy-loom`
- this already matches the loop-7 family invariant and should not be rewritten prematurely

### Runtime product naming is already Loom-shaped

Sources:

- `cli-phantom/README.md`
- `cli-phantom/CLAUDE.md`
- `cli-phantom/runtime/package.json`
- `cli-phantom/runtime/src/cli/index.ts`

Current aligned Loom surfaces:

- README title: `Loom Runtime`
- CLAUDE title: `Loom Runtime`
- package name: `loom-runtime`
- CLI/help invocation: `loom <command> [options]`
- help/examples consistently show `loom ...`

Interpretation:

- the active runtime package and command surface are already branded around Loom rather than Phantom
- this means package/binary/docs branding is **closer** to future `agentcy-loom` intent than the repo directory surface is
- the mixed state is deliberate and should be documented, not flattened by premature renames

## Safe legacy aliases

The following legacy names are acceptable during any future transition because they do not create a second artifact authority.

### Repo and docs aliases

- `cli-phantom` as the historical/current repo name in family docs, task taxonomy, fixtures, and migration notes
- `Loom Runtime` as the current runtime/product wording in README and operator docs

### Package and binary aliases

- `loom-runtime` is the strongest compatibility package alias candidate if a future `agentcy-loom` package is introduced
- `loom` is the strongest CLI alias candidate because all current help text and operator examples already use it
- direct `cd runtime && npx tsx src/cli.ts ...` invocation is also an acceptable transitional operator surface until a packaged binary exists

### Runtime/storage aliases

- `state/loom.sqlite`
- `loom-runtime/` object-storage prefix
- `LOOM_ROOT`
- loom-prefixed temporary/test directory names

These are acceptable as legacy runtime conventions because they are already Loom-shaped, do not conflict with the family writer invariant, and should not be churned without an explicit compatibility policy.

## Hard blockers to literal rename

### 1. Repo directory rename blockers

1. family docs, task specs, tests, and repo-local references still correctly use `cli-phantom` as the current repo identity
2. canonical `run_result.v1.writer.repo` must stay `cli-phantom` until a literal repo rename actually lands
3. repo-local breadth/audit docs deliberately describe the runtime as mixed `cli-phantom` / Loom state, so calling the repo itself rename-ready today would be overstated

Conclusion:

- repo rename readiness is not the same thing as Loom-branded runtime readiness
- the repo directory is not yet honestly rename-ready on loop-7 evidence alone

### 2. Package/distribution rename blockers

1. `runtime/package.json` already uses `loom-runtime`, not `agentcy-loom`
2. there is no install/publish plan documenting whether the future target should be `agentcy-loom`, `@agentcy/loom`, or something else
3. there is no packaged-install verification evidence because the active usage model is source invocation via `tsx`

Conclusion:

- package surface is closer to target than the repo surface, but it is still not family-normalized enough to call rename-ready

### 3. CLI-binary rename blockers

1. help text is already Loom-branded, but the binary is not actually packaged or installed
2. the real invocation surface is still `npx tsx src/cli.ts ...`, not a distributable `loom` or `agentcy-loom` executable
3. because there is no installed binary, there is no clean alias policy to validate yet

Conclusion:

- `loom` is the current canonical command language, but future `agentcy-loom` binary readiness is still unproven

### 4. Runtime path/key-prefix blockers

1. runtime persistence and object keys already use `loom` / `loom-runtime` prefixes (`state/loom.sqlite`, `loom-runtime/...`)
2. environment/config policy is only partially visible through `LOOM_ROOT`
3. no migration policy exists for whether these runtime prefixes should stay Loom-shaped forever, stay legacy-compatible, or later shift to `agentcy-loom`

Conclusion:

- runtime prefixes are stable enough for current use, but not rename-ready because compatibility expectations are undocumented

## Loop-8 repo-local policy update

The bounded follow-up for this repo is now explicit:

- loop 8 is a package/CLI readiness wave, not a repo rename wave
- `run_result.v1.writer = { repo: "cli-phantom", module: "agentcy-loom" }` stays locked during that work
- `loom-runtime` is now documented as a transitional package alias
- `loom` is now documented as the preferred durable CLI alias candidate
- the proof target is packaged local install/help readiness from outside the repo root, especially `loom --help` and `loom help --json`
- that bounded proof is now recorded in `docs/packaged-install-help-proof-2026-04-12.md`
- the verified installed surface is still `loom`, not `agentcy-loom`

Decision records:

- `docs/package-cli-alias-readiness-2026-04-12.md`
- `docs/packaged-install-help-proof-2026-04-12.md`

## Bounded next actions

Allowed loop-8 next steps for this repo are still narrow and evidence-first:

1. keep this audit as the repo-local naming scorecard for `cli-phantom`
2. use `docs/package-cli-alias-readiness-2026-04-12.md` as the explicit package/CLI alias policy before changing package metadata
3. treat the packaged install/help proof as complete for the current bounded loop-8 gate and avoid inflating it into a repo/package rename claim
4. keep `run_result.v1.writer = { repo: "cli-phantom", module: "agentcy-loom" }` unchanged until an explicit repo-rename task exists
5. avoid runtime prefix rewrites unless a future task first defines compatibility behavior for `state/loom.sqlite`, `LOOM_ROOT`, and `loom-runtime/` object keys

## Explicit non-goals

This audit does not authorize:

- renaming the repo now
- changing `writer.repo` from `cli-phantom` to `agentcy-loom`
- broad import rewrites
- packaging work just to cosmetically match the family name
- runtime state/key migrations
- umbrella CLI work or runtime unification

## Validation commands

Read-only validation commands for this audit:

```bash
cd cli-phantom && rg -n 'cli-phantom|agentcy-loom|run_result\.v1|writer' docs/agentcy-loom-breadth-scan-2026-04-12.md runtime/src/domain/run-result-v1.ts runtime/src/runtime/runtime.test.ts
cd cli-phantom && rg -n '"name": "loom-runtime"|"cli": "tsx src/cli\.ts"' runtime/package.json
cd cli-phantom && rg -n 'Loom Runtime|loom <command>|loom auto|loom run|loom publish' README.md CLAUDE.md runtime/src/cli/index.ts
cd cli-phantom && rg -n 'loom\.sqlite|LOOM_ROOT|loom-runtime/|loom-cli-|loom-brand-|loom-lab-|loom-env-' runtime/src
```

Repo-local verification commands:

```bash
cd cli-phantom/runtime && npm test
cd cli-phantom/runtime && npx tsc --noEmit
cd cli-phantom/runtime && npx tsx src/cli.ts help --json
```

## Bottom line

`cli-phantom` is the clearest family example of a mixed rename-readiness state.

The explicit repo-local policy is now published:

- `cli-phantom` remains the canonical repo name
- `agentcy-loom` remains the canonical family module name
- `loom-runtime` is a transitional package alias with bounded packaged local-install proof
- `loom` is the preferred durable CLI alias candidate and the currently verified installed binary surface
- loop 8 has now proven packaged local install/help readiness without performing a rename

What is already correct:

- canonical artifact ownership for `run_result.v1`
- `writer.repo = "cli-phantom"`
- `writer.module = "agentcy-loom"`
- active runtime/package/CLI branding centered on Loom

What is not yet honestly rename-ready across all surfaces:

- repo directory naming
- family-normalized package target
- packaged binary target
- explicit runtime-prefix migration policy

The right loop-7 claim is therefore:

- **not ready for all-surfaces-together rename**
- **closest to ready on package/binary/docs branding surfaces, with bounded packaged local-install/help proof but still not a packaged family-target rename claim**
- **repo identity intentionally remains `cli-phantom` until a later, explicit rename task lands**
