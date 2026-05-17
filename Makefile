.PHONY: up down logs build test psql backend-shell frontend-shell clean

up:
	docker compose up --build

up-d:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f

build:
	docker compose build

test:
	docker compose run --rm backend pytest -q

psql:
	docker compose exec postgres psql -U $$POSTGRES_USER -d $$POSTGRES_DB

backend-shell:
	docker compose exec backend bash

frontend-shell:
	docker compose exec frontend sh

clean:
	docker compose down -v
