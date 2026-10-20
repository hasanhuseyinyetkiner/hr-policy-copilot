.PHONY: models api web test lint eval

models:
	uv run --project backend python scripts/download_models.py

api:
	cd backend && uv run python -m app

web:
	cd frontend && pnpm dev

test:
	cd backend && uv run pytest -q
	cd frontend && pnpm test

lint:
	cd backend && uv run ruff check .
	cd frontend && pnpm lint && pnpm typecheck

eval:
	cd backend && uv run python ../scripts/run_eval.py
