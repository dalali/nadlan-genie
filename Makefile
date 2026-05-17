.PHONY: up down logs build test psql backend-shell frontend-shell clean env dev

# Ensure a .env file exists by copying .env.example if missing.
# All other targets that need .env should depend on this.
env:
	@if [ ! -f .env ]; then \
		if [ -f .env.example ]; then \
			cp .env.example .env; \
			echo "Created .env from .env.example"; \
		else \
			echo "ERROR: neither .env nor .env.example exist" >&2; \
			exit 1; \
		fi; \
	fi

up: env
	docker compose up --build

up-d: env
	docker compose up --build -d

# Convenience alias for "make up"
dev: up

down:
	docker compose down

logs:
	docker compose logs -f

build: env
	docker compose build

test: env
	docker compose run --rm backend pytest -q

psql:
	docker compose exec postgres psql -U $$POSTGRES_USER -d $$POSTGRES_DB

backend-shell:
	docker compose exec backend bash

frontend-shell:
	docker compose exec frontend sh

clean:
	docker compose down -v
