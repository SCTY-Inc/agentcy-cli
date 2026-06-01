FORECAST_BIN ?= forecast/.venv-simulation/bin/agentcy-forecast

.PHONY: install install-studio sync install-python-suite install-forecast-simulation install-full-operator doctor check check-python check-studio test lint lint-full pipeline pipeline-fixtures pipeline-givecare pipeline-givecare-preview

# Install Python workspace members + repo-local dev tools
install:
	uv sync --group dev

# Install the base Python suite only (root CLI + protocols + voice + briefs + forecast base CLI + measure)
install-python-suite:
	uv sync --group dev

# Add the Forecast simulation runtime in an isolated Python 3.11 environment
install-forecast-simulation:
	cd forecast && uv venv --python 3.11 --allow-existing .venv-simulation
	cd forecast && uv pip install --python .venv-simulation/bin/python -r requirements-simulation.lock
	cd forecast && uv pip install --python .venv-simulation/bin/python --no-deps -e ../protocols -e .

# Install Studio (TypeScript)
install-studio:
	cd studio && pnpm install

# Install the full local operator stack
install-full-operator: install-python-suite install-forecast-simulation install-studio

# Sync without optional extras, but keep repo-local dev tools available
sync:
	uv sync --group dev

# Lightweight readiness checks

doctor:
	uv run agentcy doctor --json
	uv run agentcy-measure doctor --json
	uv run agentcy-forecast doctor --json
	cd studio && node bin/studio.js help --json > /dev/null

# Typecheck + test the maintained monorepo surfaces
check: check-python check-studio

check-python:
	uv run pytest tests briefs/tests forecast/tests measure/tests voice/tests protocols/tests -q

check-studio:
	cd studio && pnpm check

# Run tests for a single member: make test member=briefs
# Special cases:
#   make test member=root
#   make test member=protocols
#   make test member=studio

test:
	@if [ "$(member)" = "root" ]; then \
		uv run pytest tests -q; \
	elif [ "$(member)" = "protocols" ]; then \
		uv run pytest protocols/tests -q; \
	elif [ "$(member)" = "studio" ]; then \
		cd studio && pnpm test; \
	else \
		uv run pytest $(member)/tests -q; \
	fi

# Green lint path for the actively maintained consolidation surfaces
lint:
	uv run ruff check agentcy tests measure/src protocols/src

# Full lint inventory across the repo (currently expected to report legacy debt)
lint-full:
	uv run --with ruff ruff check briefs/src forecast/agentcy_forecast measure/src voice/src protocols/src agentcy tests

# Run the canonical pipeline end-to-end.
# Requirements:
# - agentcy-forecast simulation needs `make install-forecast-simulation`
# - Studio runtime needs `make install-studio`
pipeline:
	@test -x "$(FORECAST_BIN)" || (echo "missing $(FORECAST_BIN); run: make install-forecast-simulation" >&2; exit 2)
	@echo "==> voice: export voice pack"
	uv run agentcy-voice --json export $(persona) --to voice-pack.v1 > /tmp/voice_pack.json
	@echo "==> briefs: generate canonical brief.v1"
	uv run agentcy-briefs plan run "$(req)" --brand $(brand) --voice-pack-input /tmp/voice_pack.json --brief-v1-output /tmp/brief.json -f json > /tmp/brief_plan.json
	@echo "==> forecast: run (requires Python 3.11 simulation runtime)"
	$(FORECAST_BIN) run --files $(files) --brief /tmp/brief.json --json > /tmp/forecast.json
	@echo "==> studio: execute"
	cd studio && node bin/studio.js run social.post --brand $(brand) --brief-file /tmp/brief.json --json > /tmp/run_result.json
	@echo "==> measure: adapt"
	uv run agentcy-measure adapt --run-result /tmp/run_result.json --sidecar $(sidecar) --output /tmp/performance.json --json > /tmp/performance.stdout.json
	@echo "==> measure: calibrate"
	uv run agentcy-measure calibrate --forecast /tmp/forecast.json --performance /tmp/performance.json --json > /tmp/calibration.json

# Fixture-backed smoke path that proves downstream protocol plumbing without
# requiring the optional Forecast simulation runtime.
pipeline-fixtures:
	cp protocols/examples/voice_pack.v1.rich.json /tmp/voice_pack.json
	cp protocols/examples/brief.v1.rich.json /tmp/brief.json
	cp protocols/examples/forecast.v1.completed-rich.json /tmp/forecast.json
	cp protocols/examples/run_result.v1.published.json /tmp/run_result.json
	uv run agentcy-measure adapt --run-result /tmp/run_result.json --sidecar $(sidecar) --output /tmp/performance.json --json > /tmp/performance.stdout.json
	uv run agentcy-measure calibrate --forecast /tmp/forecast.json --performance /tmp/performance.json --json > /tmp/calibration.json

# GiveCare end-to-end pipeline (full live run)
# Requirements: `make install-forecast-simulation` + `make install-studio`
# Usage:
#   make pipeline-givecare req="launch post: SMS crisis support for dementia caregivers" files=docs/
#   make pipeline-givecare req="..." files=... sidecar=path/to/sidecar.json
pipeline-givecare:
	@test -x "$(FORECAST_BIN)" || (echo "missing $(FORECAST_BIN); run: make install-forecast-simulation" >&2; exit 2)
	@echo "==> voice: export GiveCare companion voice pack"
	uv run agentcy-voice --json export givecare-companion --to voice-pack.v1 > /tmp/gc_voice_pack.json
	@echo "==> briefs: generate brief.v1 for GiveCare"
	uv run agentcy-briefs plan run "$(req)" \
		--brand givecare \
		--voice-pack-input /tmp/gc_voice_pack.json \
		--brief-v1-output /tmp/gc_brief.json \
		-f json > /tmp/gc_brief_plan.json
	@echo "==> forecast: social adoption"
	$(FORECAST_BIN) run \
		--files $(if $(files),$(files),docs/) \
		--brief /tmp/gc_brief.json \
		--json > /tmp/gc_forecast.json
	@echo "==> studio: render + publish"
	cd studio && node bin/studio.js run social.post \
		--brand givecare \
		--brief-file /tmp/gc_brief.json \
		--json > /tmp/gc_run_result.json
	@echo "==> measure: adapt (performance)"
	uv run agentcy-measure adapt \
		--run-result /tmp/gc_run_result.json \
		$(if $(sidecar),--sidecar $(sidecar),) \
		--output /tmp/gc_performance.json \
		--json > /tmp/gc_performance_stdout.json
	@echo "==> measure: calibrate (forecast vs. actuals)"
	uv run agentcy-measure calibrate \
		--forecast /tmp/gc_forecast.json \
		--performance /tmp/gc_performance.json \
		--json > /tmp/gc_calibration.json
	@echo "Pipeline complete. Artifacts in /tmp/gc_*.json"

# GiveCare preview pipeline — root pipeline smoke path
pipeline-givecare-preview:
	@echo "==> pipeline: preview mode (auto-approve, dry publish)"
	uv run agentcy pipeline run \
		--mode preview \
		--brand givecare \
		--brief "$(req)" \
		--with-forecast \
		--files $(if $(files),$(files),docs/) \
		--smoke \
		--studio-workflow social.post \
		--json > /tmp/gc_pipeline_preview.json
	@echo "Preview complete. Artifacts in /tmp/gc_pipeline_preview.json"
