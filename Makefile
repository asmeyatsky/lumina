# =============================================================================
# LUMINA — Developer Makefile
# =============================================================================
.DEFAULT_GOAL := help
SHELL := /bin/bash

# Detect docker compose command (v2 plugin vs standalone)
DOCKER_COMPOSE := $(shell docker compose version >/dev/null 2>&1 && echo "docker compose" || echo "docker-compose")

# ---------------------------------------------------------------------------
# Development
# ---------------------------------------------------------------------------

.PHONY: dev
dev: ## Start local development environment with hot reload
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml up --build

.PHONY: dev-detach
dev-detach: ## Start local dev environment in background
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml up --build -d

.PHONY: down
down: ## Stop all containers
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml down

.PHONY: logs
logs: ## Tail logs from all containers
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml logs -f

.PHONY: logs-backend
logs-backend: ## Tail backend logs only
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml logs -f backend

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------

.PHONY: test
test: ## Run tests with coverage
	uv run pytest tests/ -v --cov=src/lumina --cov-report=term-missing

.PHONY: test-ci
test-ci: ## Run tests with coverage and XML report (CI mode)
	uv run pytest tests/ -v --cov=src/lumina --cov-report=xml:coverage.xml --cov-fail-under=80

.PHONY: test-watch
test-watch: ## Run tests in watch mode
	uv run pytest tests/ -v --cov=src/lumina -f

# ---------------------------------------------------------------------------
# Linting & Formatting
# ---------------------------------------------------------------------------

.PHONY: lint
lint: ## Run linter (ruff check + format check)
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/

.PHONY: lint-fix
lint-fix: ## Auto-fix lint issues and format code
	uv run ruff check --fix src/ tests/
	uv run ruff format src/ tests/

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

.PHONY: migrate
migrate: ## Run Alembic migrations (upgrade to head)
	uv run alembic upgrade head

.PHONY: migrate-create
migrate-create: ## Create a new migration (usage: make migrate-create msg="add users table")
	uv run alembic revision --autogenerate -m "$(msg)"

.PHONY: migrate-down
migrate-down: ## Rollback last migration
	uv run alembic downgrade -1

# ---------------------------------------------------------------------------
# Docker Build
# ---------------------------------------------------------------------------

.PHONY: build
build: ## Build all Docker images
	$(DOCKER_COMPOSE) build

.PHONY: build-backend
build-backend: ## Build backend Docker image only
	docker build -t lumina-backend:latest -f Dockerfile .

.PHONY: build-frontend
build-frontend: ## Build frontend Docker image only
	docker build -t lumina-frontend:latest -f frontend/Dockerfile frontend/

# ---------------------------------------------------------------------------
# Deployment
# ---------------------------------------------------------------------------

.PHONY: deploy
deploy: ## Deploy to GCP Cloud Run via Cloud Build
	gcloud builds submit --config deploy/cloudbuild.yaml .

.PHONY: deploy-terraform
deploy-terraform: ## Apply Terraform infrastructure changes
	cd deploy/terraform && terraform apply

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

.PHONY: clean
clean: ## Remove all containers, volumes, and build artifacts
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml down -v --remove-orphans
	docker image prune -f --filter "label=project=lumina" 2>/dev/null || true
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov coverage.xml dist build *.egg-info

.PHONY: shell-backend
shell-backend: ## Open a shell in the running backend container
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml exec backend /bin/bash

.PHONY: shell-db
shell-db: ## Open psql shell in the database container
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml exec db psql -U lumina

.PHONY: env
env: ## Create .env from .env.example (will not overwrite existing .env)
	@test -f .env && echo ".env already exists — skipping" || (cp .env.example .env && echo "Created .env from .env.example — edit it with your keys")

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'
