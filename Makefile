.PHONY: up down db seed test lint api web

up:      ; docker compose up -d db redis opensearch
down:    ; docker compose down
db:      ; psql $$ADMIN_DATABASE_URL -f db/schema.sql && psql $$ADMIN_DATABASE_URL -f db/rls.sql
seed:    ; DATABASE_URL=$$ADMIN_DATABASE_URL python db/seed.py
test:    ; cd apps/api && python -m pytest -q
lint:    ; cd apps/api && ruff check app && mypy app/services app/ai
api:     ; cd apps/api && uvicorn app.main:app --reload
web:     ; cd apps/web && npm run dev
