# ============================================================
# ShadowLink Monorepo — Unified Build Commands
# ============================================================

PYTHON   := D:/software/study/Ana/envs/shadowlink/python.exe
PIP      := $(PYTHON) -m pip
UVICORN  := $(PYTHON) -m uvicorn
MVNW     := cd shadowlink-server && mvnw.cmd
NPM_WEB  := cd shadowlink-web && npm
DEPLOY   := cd deploy

.PHONY: help dev dev-java dev-ai dev-web \
        build build-java build-ai build-web \
        test test-java test-ai test-web \
        lint lint-ai lint-web \
        proto proto-python proto-lint \
        docker-up docker-dev docker-dev-infra docker-monitor \
        docker-down docker-logs docker-status docker-clean docker-ps \
        clean

help: ## Show available targets
	@echo ""
	@echo "  ShadowLink Makefile"
	@echo "  ══════════════════════════════════════"
	@echo ""
	@echo "  Development:"
	@echo "    dev            Start all services locally (no Docker)"
	@echo "    dev-java       Start Java backend (Spring Boot)"
	@echo "    dev-ai         Start Python AI service (FastAPI)"
	@echo "    dev-web        Start React frontend (Vite)"
	@echo ""
	@echo "  Build:"
	@echo "    build          Build all projects"
	@echo "    build-java     Build Java backend"
	@echo "    build-ai       Install Python AI dependencies"
	@echo "    build-web      Build React frontend"
	@echo ""
	@echo "  Test:"
	@echo "    test           Run all tests"
	@echo "    test-java      Run Java tests"
	@echo "    test-ai        Run Python tests"
	@echo "    test-web       Run React type-check"
	@echo ""
	@echo "  Lint:"
	@echo "    lint           Lint all projects"
	@echo "    lint-ai        Lint Python (ruff)"
	@echo "    lint-web       Lint React (eslint)"
	@echo ""
	@echo "  Docker:"
	@echo "    docker-up      Start production stack"
	@echo "    docker-dev     Start dev stack (hot-reload, H2)"
	@echo "    docker-dev-infra  Dev + MySQL + Redis"
	@echo "    docker-monitor Production + Prometheus + Grafana"
	@echo "    docker-down    Stop all services"
	@echo "    docker-ps      Show running services"
	@echo "    docker-logs    Tail all logs (use SVC=name for specific)"
	@echo "    docker-status  Health check all services"
	@echo "    docker-clean   Stop + remove volumes (DESTRUCTIVE)"
	@echo ""
	@echo "  Proto:"
	@echo "    proto          Generate all gRPC stubs (Python + Java)"
	@echo "    proto-python   Generate Python gRPC stubs only"
	@echo "    proto-lint     Lint proto files (requires buf)"
	@echo ""
	@echo "  Misc:"
	@echo "    clean          Clean all build artifacts"
	@echo ""

# ════════════════════════════════════════════
# Development (local, no Docker)
# ════════════════════════════════════════════

dev-java: ## Start Java backend
	$(MVNW) spring-boot:run

dev-ai: ## Start Python AI service
	$(UVICORN) app.main:app --reload --host 0.0.0.0 --port 8000 --app-dir shadowlink-ai

dev-web: ## Start React frontend
	$(NPM_WEB) run dev

# ════════════════════════════════════════════
# Build
# ════════════════════════════════════════════

build: build-java build-ai build-web ## Build all

build-java: ## Build Java backend
	$(MVNW) clean package -DskipTests

build-ai: ## Install Python AI dependencies
	$(PIP) install -e "shadowlink-ai[dev]"

build-web: ## Build React frontend
	$(NPM_WEB) install
	$(NPM_WEB) run build

# ════════════════════════════════════════════
# Test
# ════════════════════════════════════════════

test: test-java test-ai test-web ## Run all tests

test-java: ## Run Java tests
	$(MVNW) test

test-ai: ## Run Python tests
	$(PYTHON) -m pytest shadowlink-ai/tests -v

test-web: ## TypeScript type-check
	$(NPM_WEB) run type-check

# ════════════════════════════════════════════
# Lint
# ════════════════════════════════════════════

lint: lint-ai lint-web ## Lint all

lint-ai: ## Lint Python (ruff)
	$(PYTHON) -m ruff check shadowlink-ai/

lint-web: ## Lint React (eslint)
	$(NPM_WEB) run lint

# ════════════════════════════════════════════
# Proto Generation
# ════════════════════════════════════════════

PROTO_DIR     := proto
PROTO_PY_OUT  := shadowlink-ai/app/api/grpc/generated
PROTO_FILES   := $(wildcard $(PROTO_DIR)/*.proto)

proto: proto-python ## Generate all gRPC stubs

proto-python: ## Generate Python gRPC stubs
	@mkdir -p $(PROTO_PY_OUT)
	$(PYTHON) -m grpc_tools.protoc \
		--proto_path=$(PROTO_DIR) \
		--python_out=$(PROTO_PY_OUT) \
		--grpc_python_out=$(PROTO_PY_OUT) \
		--pyi_out=$(PROTO_PY_OUT) \
		$(PROTO_FILES)
	@echo "Fixing imports to relative..."
	@cd $(PROTO_PY_OUT) && for f in *_pb2.py *_pb2_grpc.py; do \
		if [ -f "$$f" ]; then \
			sed -i 's/^import common_pb2/from . import common_pb2/' "$$f"; \
			sed -i 's/^import agent_service_pb2/from . import agent_service_pb2/' "$$f"; \
			sed -i 's/^import rag_service_pb2/from . import rag_service_pb2/' "$$f"; \
			sed -i 's/^import mcp_service_pb2/from . import mcp_service_pb2/' "$$f"; \
			sed -i 's/^import memory_service_pb2/from . import memory_service_pb2/' "$$f"; \
		fi; \
	done
	@echo "Python gRPC stubs generated in $(PROTO_PY_OUT)"

proto-lint: ## Lint proto files (requires buf)
	cd $(PROTO_DIR) && buf lint

# ════════════════════════════════════════════
# Docker — Production
# ════════════════════════════════════════════

docker-up: ## Start production stack
	$(DEPLOY) && docker compose up -d --build

docker-monitor: ## Production + Prometheus + Grafana
	$(DEPLOY) && docker compose --profile monitoring up -d --build

# ════════════════════════════════════════════
# Docker — Development
# ════════════════════════════════════════════

docker-dev: ## Start dev stack (hot-reload, H2, no MySQL/Redis)
	$(DEPLOY) && docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build

docker-dev-infra: ## Dev stack + MySQL + Redis
	$(DEPLOY) && docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile with-infra up -d --build

# ════════════════════════════════════════════
# Docker — Operations
# ════════════════════════════════════════════

docker-down: ## Stop all services
	$(DEPLOY) && docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile with-infra --profile monitoring down

docker-ps: ## Show running services
	$(DEPLOY) && docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

docker-logs: ## Tail logs (use SVC=service-name for specific)
ifdef SVC
	$(DEPLOY) && docker compose logs -f $(SVC)
else
	$(DEPLOY) && docker compose logs -f
endif

docker-status: ## Health check all services
	@echo ""
	@echo "ShadowLink Health Checks"
	@echo "────────────────────────"
	@curl -sf http://localhost/health 2>/dev/null && echo "  Nginx:  OK" || echo "  Nginx:  FAIL"
	@curl -sf http://localhost:8080/actuator/health 2>/dev/null && echo "  Java:   OK" || echo "  Java:   FAIL"
	@curl -sf http://localhost:8000/health 2>/dev/null && echo "  Python: OK" || echo "  Python: FAIL"
	@echo ""

docker-clean: ## Stop all + remove volumes (DESTRUCTIVE)
	@echo "WARNING: This will delete all Docker volumes (DB data, AI data, etc.)"
	$(DEPLOY) && docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile with-infra --profile monitoring down -v --remove-orphans

# ════════════════════════════════════════════
# Clean
# ════════════════════════════════════════════

clean: ## Clean all build artifacts
	cd shadowlink-server && mvnw.cmd clean 2>/dev/null || true
	rm -rf shadowlink-web/dist shadowlink-web/node_modules
	rm -rf shadowlink-electron/dist shadowlink-electron/node_modules
	rm -rf shadowlink-ai/*.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
