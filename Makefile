.PHONY: up down db test-db seed test lint api web

up:      ; docker compose up -d db redis opensearch
down:    ; docker compose down
db:      ; psql $$ADMIN_DATABASE_URL -f db/schema.sql && psql $$ADMIN_DATABASE_URL -f db/rls.sql
# pop_test: database terpisah untuk `make test` (apps/api/tests/*.py baca
# TEST_DATABASE_URL_APP) — sengaja beda dari `pop` yang dipakai `make db`,
# supaya tes tidak menulis ke data dev. Ditambahkan 2026-08-24: sebelumnya
# ini langkah manual yang tidak terdokumentasi di mana pun. Asumsi:
# ADMIN_DATABASE_URL diakhiri "/pop" (sesuai .env.example).
test-db: ; TEST_DSN=$$(echo "$$ADMIN_DATABASE_URL" | sed 's#/pop$$#/pop_test#'); \
          psql "$$ADMIN_DATABASE_URL" -c "CREATE DATABASE pop_test OWNER pop" 2>/dev/null; \
          psql "$$TEST_DSN" -f db/schema.sql && psql "$$TEST_DSN" -f db/rls.sql
seed:    ; DATABASE_URL=$$ADMIN_DATABASE_URL python db/seed.py
test:    ; cd apps/api && python -m pytest -q
lint:    ; cd apps/api && ruff check app tests && mypy app/services app/ai app/connectors
api:     ; cd apps/api && uvicorn app.main:app --reload
web:     ; cd apps/web && npm run dev
