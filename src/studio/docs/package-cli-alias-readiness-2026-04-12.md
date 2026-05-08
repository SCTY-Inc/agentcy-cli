# cli-phantom package and CLI alias readiness for future `agentcy-loom`

Date: 2026-04-12  
Scope: explicit loop-8 policy note for package and CLI naming in `cli-phantom` before any package metadata or installed-bin changes.

## Decision summary

This repo keeps the mixed writer contract unchanged:

```json
{
  "repo": "cli-phantom",
  "module": "agentcy-loom"
}
```

Loop 8 is **not** a repo rename wave. It is the smallest proof wave for package/install surfaces.

The policy for current naming surfaces is:

- `cli-phantom` remains the canonical current repo name
- `agentcy-loom` remains the canonical future family module name
- `loom-runtime` is the current package/distribution surface and should be treated as a **transitional alias**, not the final family package target
- `loom` is the current operator-facing CLI name and should be treated as a **durable CLI alias candidate** even if a future packaged family binary adopts `agentcy-loom` or a scoped family package name
- `run_result.v1.writer` stays `{"repo":"cli-phantom","module":"agentcy-loom"}` throughout loop 8

## What loop 8 is actually proving

Loop 8 should prove packaged local install/help readiness, not cosmetic rename readiness.

The exact proof target is:

1. the runtime can be installed locally as a package from outside the repo root
2. an installed command surface works from that external temp directory
3. `loom --help` succeeds on the installed surface
4. `loom help --json` or the equivalent machine-readable help path succeeds on the installed surface
5. the proof does not rewrite canonical writer fields, repo identity, or runtime storage prefixes just to match the family target name

If those checks are not proven, then `cli-phantom` is still only Loom-shaped on source/help branding, not on packaged runtime readiness.

## Surface policy

| Surface | Current canonical | Policy now | Future-target note |
| --- | --- | --- | --- |
| Repo directory | `cli-phantom` | canonical current repo identity | may change only in a later explicit repo-rename task |
| Writer fields | `repo = cli-phantom`, `module = agentcy-loom` | locked and must not change in loop 8 | repo half changes only after literal repo rename |
| Package name | `loom-runtime` | transitional alias while install proof is still being established | likely later family-normalized to `agentcy-loom` or a scoped equivalent |
| CLI name | `loom` | durable operator-facing alias candidate | may coexist with a future family-named packaged binary |
| Source entrypoint | `npx tsx src/cli.ts ...` | acceptable transitional developer path | should not be mistaken for packaged-bin proof |
| Runtime prefixes | `loom.sqlite`, `LOOM_ROOT`, `loom-runtime/` | leave unchanged during loop 8 | migration only with an explicit compatibility plan |

## Why `loom-runtime` is transitional but `loom` may be durable

### `loom-runtime`

`loom-runtime` is useful because it already matches the current Loom-branded runtime surface, but it is not family-normalized enough to claim as the final package target. It should therefore be documented as a transitional compatibility surface until a later package-metadata task decides the exact family-facing package name.

### `loom`

`loom` is already the command language taught to operators in help text and docs. That makes it the strongest candidate for a durable alias, because preserving `loom` keeps operator ergonomics stable even if the package name later shifts toward `agentcy-loom`.

In other words:

- package name can still move later
- CLI ergonomics should stay stable if possible

## Explicit non-goals

Loop 8 should not be expanded into:

- a literal repo rename
- a change to `writer.repo`
- umbrella CLI work
- runtime-prefix rewrites
- import-path churn unrelated to packaged install/help proof
- broad runtime unification across the family

## Recommended verification shape for the later implementation task

When package/bin work lands, prefer evidence like:

```bash
cd cli-phantom/runtime && npm pack
cd /tmp/<some-external-dir> && npm install /Users/amadad/projects/cli-phantom/runtime/<packed-tarball>
cd /tmp/<some-external-dir> && ./node_modules/.bin/loom --help
cd /tmp/<some-external-dir> && ./node_modules/.bin/loom help --json
```

Equivalent local-install verification is fine, but the proof must come from outside the repo root so source-path assumptions do not masquerade as packaged readiness.

## Verified proof note

The bounded loop-8 proof is now recorded in:

- `docs/packaged-install-help-proof-2026-04-12.md`

That proof confirms a local tarball install of `loom-runtime` from outside the repo root and successful external execution of:

- `loom --help`
- `loom help --json`

The proof does **not** claim a repo rename and does **not** claim that `agentcy-loom` is already the installed binary name.

## Bottom line

The explicit repo-local policy is now:

- `cli-phantom` is still the canonical repo name
- `agentcy-loom` is still the canonical family module name
- `loom-runtime` is a transitional package alias with bounded packaged local-install proof
- `loom` is the preferred durable CLI alias candidate and now has bounded packaged-help proof from outside the repo root
- loop 8 is a packaged local install/help proof target, not a rename target
- the mixed writer contract remains unchanged throughout that work
