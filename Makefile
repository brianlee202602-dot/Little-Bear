ENV_FILE ?= .env
-include $(ENV_FILE)
export

COMPOSE ?= docker compose
POSTGRES_DB ?= little_bear
POSTGRES_USER ?= little_bear
MINIO_API_PORT ?= 9000
QDRANT_HTTP_PORT ?= 6333
MODEL_GATEWAY_PORT ?= 8080

.PHONY: env up down restart ps logs logs-model health clean reset

env:
	@if [ ! -f $(ENV_FILE) ]; then cp .env.example $(ENV_FILE); fi

up: env
	$(COMPOSE) --env-file $(ENV_FILE) up -d

down:
	$(COMPOSE) --env-file $(ENV_FILE) down

restart: down up

ps:
	$(COMPOSE) --env-file $(ENV_FILE) ps

logs:
	$(COMPOSE) --env-file $(ENV_FILE) logs -f

logs-model:
	$(COMPOSE) --env-file $(ENV_FILE) logs -f model-gateway

health:
	@printf "postgres: "; $(COMPOSE) --env-file $(ENV_FILE) exec -T postgres pg_isready -U $(POSTGRES_USER) -d $(POSTGRES_DB)
	@printf "redis: "; $(COMPOSE) --env-file $(ENV_FILE) exec -T redis redis-cli ping
	@printf "minio: "; curl -fsS http://localhost:$(MINIO_API_PORT)/minio/health/live >/dev/null && echo ok
	@printf "qdrant: "; curl -fsS http://localhost:$(QDRANT_HTTP_PORT)/readyz >/dev/null && echo ok
	@printf "model-gateway: "; curl -fsS http://localhost:$(MODEL_GATEWAY_PORT)/internal/v1/model-health >/dev/null && echo ok

clean:
	$(COMPOSE) --env-file $(ENV_FILE) down --remove-orphans

reset:
	$(COMPOSE) --env-file $(ENV_FILE) down --volumes --remove-orphans
