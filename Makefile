.PHONY: up down logs seed demo test build check

COMPOSE := docker compose

up:
	$(COMPOSE) up --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f backend

seed:
	python scripts/seed_db.py

demo: seed
	@echo "Opening dashboard at http://localhost:3000"
	start http://localhost:3000 2>/dev/null || open http://localhost:3000 2>/dev/null || echo "Visit http://localhost:3000 manually"

test:
	python -m unittest discover -s tests -v

build:
	cd dashboard && npm run build

check: test
	cd dashboard && npm run format:check && npm run build
