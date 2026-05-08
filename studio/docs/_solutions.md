# Solutions Log

## 2026-04-15 — Protocol seam CI now installs loom runtime before Python tests
- Problem: the canonical `brief.v1 -> run_result.v1` protocol test invokes `node bin/loom.js`, so clean CI jobs that only ran `uv sync --group dev` failed before the loom runtime dependencies were installed.
- Fix: the root CI workflow now installs `loom/runtime` with `pnpm install --frozen-lockfile` in the Python/protocol job, and the root docs now note that clean-checkout protocol tests require the loom runtime install.

## 2026-04-15 — Packaged Loom launcher now resolves `tsx` from the runtime root
- Problem: `node bin/loom.js help --json` could fail from the monorepo root because the launcher inherited the caller cwd and Node could not resolve the runtime-local `tsx` dependency.
- Fix: `bin/loom.js` now spawns Node with `cwd` pinned to `runtime/`, so packaged help and doctor-style probes resolve `tsx` consistently.

## 2026-04-15 — CLI help and social workflows no longer hard-fail without native canvas
- Problem: `agentcy-loom` imported canvas-backed render modules at startup, so even `help` and unrelated CLI tests crashed when `canvas.node` was unavailable.
- Fix: lazy-load command modules, lazy-load the social renderer inside workflow steps, and fall back to SVG/resvg social asset rendering when native canvas bindings are missing.

## 2026-04-01 — Fonts not rendering on Linux/Hetzner
- Problem: Card renderer used system fonts (Alegreya, Inter, JetBrains Mono) that exist on macOS but not on Linux servers. `registerFont` was imported but never called. JetBrains Mono wasn't bundled at all.
- Fix: Bundle all TTFs in `runtime/fonts/`, call `registerFont()` at startup via shared `render/fonts.ts`. Un-ignore TTFs in `.gitignore` so they deploy.

## 2026-04-01 — Logo not rendering on deterministic cards
- Problem: `CardInput.logoPath` field existed but `renderCard()` never drew it — brand mark was always letter-spaced text.
- Fix: Draw logo PNG at brand mark position when `logoPath` is provided, fall back to text. Wire `logoPath` through `lab.ts` → `renderCardToFile`.

## 2026-04-01 — Gemini rendering text and logos in social assets
- Problem: social.ts prompt asked Gemini to render headline text, brand name, AND incorporate logo PNG. Results: misspellings ("Patcchwork"), wrong fonts, triple branding, illustrative clipart.
- Fix: Two-phase pipeline — Gemini generates art-only image (no text/logos), canvas composites typography + logo on top deterministically. One Gemini call instead of five.

## 2026-04-01 — Render pipeline duplication and dead code
- Problem: Three independent renderers (card.ts, social.ts, generate-card.sh) with duplicated helpers (hexToRgb ×3, muted ×2, font registration ×2, Gemini call ×3). Dead features (contentTypes, image_brief artifact, canvas motifs).
- Fix: Extract shared modules (colors.ts, fonts.ts, gemini.ts). Archive generate-card.sh. Remove contentTypes and image_brief. Net -680 lines.

## 2026-03-31 — Card lab body text missing letter "s"
- Problem: Body text on social cards was rendering with the letter "s" completely missing. Appeared to be a font subsetting issue — the symptom (missing glyphs) pointed at the woff2 font file.
- Root cause: `truncateWords()` in the card lab HTML had `/s+/` instead of `/\s+/` as the regex for `String.split()`. The literal letter "s" was being used as a word delimiter, stripping every "s" from the output.
- Fix: Added the missing backslash: `.split(/\s+/)`. The font file was fine all along.

## 2026-03-30 — CLI failures now stay machine-readable
- Problem: CLI commands could return plain stderr text on failure even when `--json` was requested, which broke agent workflows and made invalid input harder to recover from automatically.
- Fix: centralized CLI error handling now returns JSON error envelopes, and command boundaries validate workflows, steps, variants, artifact paths, and requested publish platforms before side effects begin.

## 2026-03-30 — Failed runs are persisted instead of looking reviewable
- Problem: a workflow step could throw after a run record was created, leaving partial state that still looked like a normal in-review run.
- Fix: runtime execution now marks runs as `failed`, stores the failing step plus `error_message`, reports failed counts in `ops health`, and blocks review on failed runs until the operator retries.

## 2026-03-30 — Brand and publish validation fail fast on unsafe config
- Problem: bad brand config and unsafe publish requests were accepted too late or silently, including unsupported handle keys, missing logo assets, explicit publish targets without configured auth, and re-initializing an existing brand.
- Fix: brand loading now validates supported social handles, `brand validate` checks referenced assets, `brand init` refuses to overwrite an existing foundation, and explicit publish targets must already be configured for the brand unless the command is a dry run.
