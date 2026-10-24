# OJA backend entry points (NFR-11). Run from the repository root; settings come from .env.
PYTHON := .venv/bin/python

.PHONY: help setup migrate seed dev test eval eval-live

help:
	@echo "make setup      create .venv and install requirements.txt"
	@echo "make migrate    apply database migrations (alembic upgrade head)"
	@echo "make seed       load reference data and seed a demo trader if none exist"
	@echo "make dev        migrate, seed startup data, and run the API with reload"
	@echo "make test       run the backend tests (no API key or network needed)"
	@echo "make eval       score the 40 eval cases offline (DEMO_MODE rules)"
	@echo "make eval-live  score the 40 eval cases with the LLM from .env"

setup:
	test -d .venv || python3 -m venv .venv
	$(PYTHON) -m pip install -r requirements.txt

migrate:
	.venv/bin/alembic upgrade head

seed:
	cd server && ../$(PYTHON) -m app.demo.index

dev:
	.venv/bin/alembic upgrade head
	cd server && ../$(PYTHON) -m app.demo.index
	cd server && ../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

test:
	cd server && ../$(PYTHON) -m unittest discover -s tests -t .

eval:
	cd server && ../$(PYTHON) -m eval.run_eval

eval-live:
	cd server && ../$(PYTHON) -m eval.run_eval --live
