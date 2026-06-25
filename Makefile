.PHONY: up down logs test lint

up:
	docker compose up --build

down:
	docker compose down -v

logs:
	docker compose logs -f api worker

test:
	pytest tests/unit tests/integration -v

test-all:
	pytest tests/ -v

lint:
	ruff check app tests
