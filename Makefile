COMPOSE := docker compose -f infra/docker-compose.yml
GIT_SHA := $(shell git rev-parse --short HEAD)

.PHONY: up down restart build logs rebuild-frontend rebuild-backend ps

# The canonical local-dev restart. `docker compose up -d` alone reuses
# whatever image was last built -- both Dockerfiles COPY source in at build
# time, no bind mount, so code changes silently don't appear without
# --build. This target makes rebuilding the default, not an easy-to-forget
# flag.
up: build
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

restart: down up

build:
	GIT_SHA=$(GIT_SHA) $(COMPOSE) build

# Faster than `make restart` when only one side changed.
rebuild-frontend:
	GIT_SHA=$(GIT_SHA) $(COMPOSE) build frontend
	$(COMPOSE) up -d frontend

rebuild-backend:
	GIT_SHA=$(GIT_SHA) $(COMPOSE) build backend worker-ingest worker-core worker-data-collection beat
	$(COMPOSE) up -d backend worker-ingest worker-core worker-data-collection beat

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps
