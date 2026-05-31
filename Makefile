# touch-grass — common operator commands. `make help` lists targets.
.DEFAULT_GOAL := help
COMPOSE_HERMES := docker compose -f docker-compose.hermes.yml

.PHONY: help install test doctor doctor-mock serve-all serve-all-mock \
        serve-mock logs down

help:  ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-16s %s\n", $$1, $$2}'

install:  ## Editable install with dev extras
	pip install -e ".[dev]"

test:  ## Run unit + mock MCP-discovery tests
	pytest -q

doctor:  ## Preflight check against real hardware
	touch-grass doctor

doctor-mock:  ## Preflight check assuming no hardware
	TOUCH_GRASS_MOCK_SERIAL=1 touch-grass doctor

serve-all:  ## Run both servers locally (keyboard :8765 + mouse :8766)
	touch-grass serve-all

serve-all-mock:  ## Run both servers locally with no hardware
	touch-grass serve-all --mock

serve-mock:  ## Bring up both Docker servers in safe mock mode
	TOUCH_GRASS_MOCK_SERIAL=1 $(COMPOSE_HERMES) up -d --build

logs:  ## Follow Docker logs
	$(COMPOSE_HERMES) logs -f

down:  ## Stop Docker servers
	$(COMPOSE_HERMES) down
