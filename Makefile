SHELL := /bin/bash
PYTHON := backend/.venv/bin/python
PIP := backend/.venv/bin/pip
NPM := npm

.PHONY: help install test backend-test frontend-test build dev-api dev-web seed-demo readiness up down logs backup restore smoke

help:
	@echo "Heritage Learning Studio"
	@echo "  make install       install backend and frontend dependencies"
	@echo "  make test          run backend and frontend tests"
	@echo "  make build         build the frontend bundle"
	@echo "  make seed-demo     seed neutral demo content (dev/test only; requires a configured DB)"
	@echo "  make readiness     print protocol readiness checks"
	@echo "  make up            docker compose build and start"
	@echo "  make down          stop the stack"
	@echo "  make backup        create database and app-data backup"
	@echo "  make restore BACKUP=... restore a backup (requires CONFIRM_RESTORE=YES)"

install:
	python3 -m venv backend/.venv
	$(PIP) install -r backend/requirements-dev.txt --no-cache-dir
	cd frontend && npm ci --no-audit --no-fund

test: backend-test frontend-test

backend-test:
	cd backend && PYTHONPYCACHEPREFIX=../.pycache .venv/bin/pytest -q

frontend-test:
	cd frontend && npm test

build:
	cd frontend && npm run build

dev-api:
	cd backend && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

dev-web:
	cd frontend && npm run dev

seed-demo:
	cd backend && .venv/bin/python -m app.cli seed-demo

readiness:
	cd backend && .venv/bin/python -m app.cli readiness

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

backup:
	./scripts/backup.sh

restore:
	CONFIRM_RESTORE=YES ./scripts/restore.sh "$(BACKUP)"

smoke:
	cd backend && PYTHONPYCACHEPREFIX=../.pycache .venv/bin/pytest -q tests/test_load.py
