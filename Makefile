.PHONY: setup build serve demo dev test verify evaluate replay benchmark-shadow clean-artifacts

setup:
	uv sync --frozen
	npm --prefix apps/web ci

build:
	npm --prefix apps/web run build

serve:
	uv run uvicorn marketbridge.api:app --app-dir backend --host 0.0.0.0 --port $${PORT:-8000}

demo: build serve

dev:
	NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000 npm --prefix apps/web run dev

test:
	uv run pytest -q

verify:
	uv run ruff check backend tests scripts
	uv run pytest -q
	npm --prefix apps/web run typecheck
	npm --prefix apps/web run build

evaluate:
	uv run python scripts/evaluate.py

replay:
	uv run python scripts/replay.py --scenario $${SCENARIO:-bad-print} --symbol $${SYMBOL:-NVDA}

benchmark-shadow:
	uv run python scripts/benchmark_shadow.py
