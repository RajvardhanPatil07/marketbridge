.PHONY: setup build serve demo dev test verify evaluate replay benchmark-shadow live-check e2e e2e-live train-ai build-ml-dataset export-evidence clean-artifacts

setup:
	uv sync --frozen
	npm --prefix apps/web ci

build:
	npm --prefix apps/web run build

serve:
	uv run --env-file .env uvicorn marketbridge.api:app --app-dir backend --host 0.0.0.0 --port $${PORT:-8000}

demo: build serve

dev:
	NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000 npm --prefix apps/web run dev

test:
	uv run pytest -q

verify:
	uv run ruff check backend tests scripts
	uv run pytest -q
	npm --prefix apps/web run typecheck
	npm --prefix apps/web run test:unit
	npm --prefix apps/web run build

evaluate:
	uv run python scripts/evaluate.py

replay:
	uv run python scripts/replay.py --scenario $${SCENARIO:-bad-print} --symbol $${SYMBOL:-NVDA}

benchmark-shadow:
	uv run python scripts/benchmark_shadow.py

live-check:
	uv run --env-file .env python scripts/check_live_config.py

e2e:
	npm --prefix apps/web run build
	npm --prefix apps/web run test:e2e
	npm --prefix apps/web run test:e2e:healthy

e2e-live:
	npm --prefix apps/web run build
	npm --prefix apps/web run test:e2e:live

train-ai:
	uv run python scripts/train_ai_models.py

build-ml-dataset:
	uv run python scripts/build_ml_dataset.py

export-evidence:
	uv run python scripts/export_evidence.py
