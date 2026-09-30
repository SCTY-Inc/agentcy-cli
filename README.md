# agentcy

CLI suite for brand work: voice, briefs, forecasting, studio drafts, and measurement, connected by explicit protocol artifacts (`brief.v1`, `forecast.v1`, `run_result.v1`, `performance.v1`, `voice_pack.v1`).

```bash
uv tool install git+https://github.com/SCTY-Inc/agentcy-cli
agentcy --help
```

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/). The `studio` runtime also needs Node 22+.

## Members

| Dir | Bin | Purpose |
| --- | --- | --- |
| `protocols/` | `agentcy-protocols` | Shared schemas, examples, adapters |
| `voice/` | `agentcy-voice` | Personas and `voice_pack.v1` export |
| `briefs/` | `agentcy-briefs` | Brand planning and `brief.v1` |
| `forecast/` | `agentcy-forecast` | Forecast from documents + requirement |
| `studio/` | `agentcy-studio` | TypeScript runtime: draft, render, review, publish |
| `measure/` | `agentcy-measure` | `run_result.v1` to `performance.v1`, calibration, study |

A brand kit lives at `brands/<brand>/{BRAND.md, DESIGN.md, brand.yml, assets/}`. See [`docs/`](docs/) for the capability model and design contract.

## Usage

```bash
agentcy doctor --json                 # member readiness
agentcy catalog --json                # members, extensions, install profiles
agentcy member briefs --json plan list

# brief.v1 -> Studio draft/render (default path; no providers, no publish)
agentcy pipeline run --brand givecare --brief "Before fall gets busy, make caregiving feel lighter" \
  --mode preview --output-dir artifacts/pipelines --json
```

Voice, Forecast, publish, and Measure are opt-in stages (`--persona`, `--with-forecast --files ...`, `--publish`). Run `agentcy pipeline run --help` for all flags. Full forecast simulation needs `make install-forecast-simulation` (isolated Python 3.11 env); `--smoke` skips it.

## Development

```bash
uv sync --group dev
cd studio && pnpm install
make check        # pytest + studio vitest/tsc
make lint
```

See [`AGENTS.md`](AGENTS.md) for layout and contracts.

## License

MIT. `forecast/` is AGPL-3.0 (see `forecast/LICENSE`).
