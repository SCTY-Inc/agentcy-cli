.PHONY: install install-studio sync doctor check check-python check-studio test lint pipeline pipeline-fixtures

install:
	uv sync --all-extras --group dev

install-studio:
	cd src/studio/runtime && pnpm install

install-full: install install-studio

sync:
	uv sync --group dev

doctor:
	uv run agentcy --help > /dev/null
	cd src/studio/runtime && node bin/loom.js help --json > /dev/null

check: check-python check-studio

check-python:
	uv run pytest tests -q

check-studio:
	cd src/studio/runtime && pnpm check

test:
	@if [ "$(member)" = "studio" ]; then \
		cd src/studio/runtime && pnpm test; \
	else \
		uv run pytest tests/$(member) -q; \
	fi

lint:
	uv run ruff check src tests

pipeline:
	@echo "==> persona: export voice pack"
	uv run agentcy persona --json export $(persona) --to voice-pack.v1 > /tmp/voice_pack.json
	@echo "==> brand: generate brief.v1"
	uv run agentcy brand plan run "$(req)" --brand $(brand) --voice-pack-input /tmp/voice_pack.json --brief-v1-output /tmp/brief.json -f json > /tmp/brief_plan.json
	@echo "==> forecast: predict"
	uv run agentcy forecast run --files $(files) --brief /tmp/brief.json --json > /tmp/forecast.json
	@echo "==> studio: render + publish"
	cd src/studio/runtime && node bin/loom.js run social.post --brand $(brand) --brief-file /tmp/brief.json --json > /tmp/run_result.json
	@echo "==> metrics: measure"
	uv run agentcy metrics adapt --run-result /tmp/run_result.json --sidecar $(sidecar) --output /tmp/performance.json --json
	@echo "==> metrics: calibrate"
	uv run agentcy metrics calibrate --forecast /tmp/forecast.json --performance /tmp/performance.json --json

pipeline-fixtures:
	cp src/agentcy/protocols/examples/voice_pack.v1.rich.json /tmp/voice_pack.json
	cp src/agentcy/protocols/examples/brief.v1.rich.json /tmp/brief.json
	cp src/agentcy/protocols/examples/forecast.v1.completed-rich.json /tmp/forecast.json
	cp src/agentcy/protocols/examples/run_result.v1.published.json /tmp/run_result.json
	uv run agentcy metrics adapt --run-result /tmp/run_result.json --sidecar $(sidecar) --output /tmp/performance.json --json
	uv run agentcy metrics calibrate --forecast /tmp/forecast.json --performance /tmp/performance.json --json
