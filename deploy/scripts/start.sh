#!/usr/bin/env bash
# ============================================================
# ShadowLink — Deployment Startup Script
# ============================================================
# Usage:
#   ./start.sh              # Production (default)
#   ./start.sh dev          # Development with hot-reload
#   ./start.sh dev infra    # Development + MySQL/Redis
#   ./start.sh prod monitor # Production + Prometheus/Grafana
#   ./start.sh stop         # Stop all services
#   ./start.sh logs         # Tail all logs
#   ./start.sh status       # Show service status
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$DEPLOY_DIR")"

cd "$DEPLOY_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_step()  { echo -e "${CYAN}[STEP]${NC}  $*"; }

# ── .env check ──
ensure_env() {
    if [ ! -f ".env" ]; then
        log_warn ".env not found — copying from .env.example"
        cp .env.example .env
        log_info "Created .env — please review and update values"
    fi
}

# ── Commands ──

cmd_start_prod() {
    local profiles=""
    if [[ "${1:-}" == "monitor" ]]; then
        profiles="--profile monitoring"
    fi

    log_step "Starting ShadowLink (production)..."
    ensure_env

    docker compose $profiles up -d --build

    log_info "Services starting..."
    log_info "  Web UI:     http://localhost"
    log_info "  Java API:   http://localhost:8080"
    log_info "  Python AI:  http://localhost:8000"
    if [[ "${1:-}" == "monitor" ]]; then
        log_info "  Prometheus: http://localhost:9090"
        log_info "  Grafana:    http://localhost:3001"
    fi
    echo ""
    log_info "Run './start.sh logs' to tail logs"
    log_info "Run './start.sh status' to check health"
}

cmd_start_dev() {
    local profiles=""
    if [[ "${1:-}" == "infra" ]]; then
        profiles="--profile with-infra"
    fi

    log_step "Starting ShadowLink (development)..."
    ensure_env

    docker compose \
        -f docker-compose.yml \
        -f docker-compose.dev.yml \
        $profiles \
        up -d --build

    log_info "Dev services starting..."
    log_info "  Vite Dev Server: http://localhost:3000"
    log_info "  Nginx Proxy:     http://localhost:80"
    log_info "  Java API:        http://localhost:8080"
    log_info "  Java Debug:      localhost:5005"
    log_info "  Python AI:       http://localhost:8000"
    log_info "  Python Debug:    localhost:5678"
    if [[ "${1:-}" == "infra" ]]; then
        log_info "  MySQL:           localhost:3306"
        log_info "  Redis:           localhost:6379"
    fi
}

cmd_stop() {
    log_step "Stopping all ShadowLink services..."
    docker compose \
        -f docker-compose.yml \
        -f docker-compose.dev.yml \
        --profile with-infra \
        --profile monitoring \
        down

    log_info "All services stopped"
}

cmd_logs() {
    local service="${1:-}"
    if [ -n "$service" ]; then
        docker compose logs -f "$service"
    else
        docker compose logs -f
    fi
}

cmd_status() {
    echo ""
    log_step "ShadowLink Service Status"
    echo "────────────────────────────────────────"
    docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
    echo ""

    # Health checks
    log_step "Health Checks"
    echo "────────────────────────────────────────"

    for endpoint in "localhost:80/health:Nginx" "localhost:8080/actuator/health:Java" "localhost:8000/health:Python"; do
        IFS=':' read -ra parts <<< "$endpoint"
        url="${parts[0]}:${parts[1]}/${parts[2]}"
        name="${parts[3]:-${parts[2]}}"
        if curl -sf "http://$url" > /dev/null 2>&1; then
            echo -e "  ${GREEN}✓${NC} $name"
        else
            echo -e "  ${RED}✗${NC} $name"
        fi
    done
    echo ""
}

cmd_clean() {
    log_step "Cleaning Docker resources..."
    docker compose \
        -f docker-compose.yml \
        -f docker-compose.dev.yml \
        --profile with-infra \
        --profile monitoring \
        down -v --remove-orphans

    log_info "Volumes and containers removed"
}

cmd_help() {
    echo ""
    echo "ShadowLink Deployment Script"
    echo "═══════════════════════════════════════"
    echo ""
    echo "Usage: ./start.sh <command> [options]"
    echo ""
    echo "Commands:"
    echo "  (default)       Start production stack"
    echo "  dev             Start development stack with hot-reload"
    echo "  dev infra       Development + MySQL/Redis"
    echo "  prod monitor    Production + Prometheus/Grafana"
    echo "  stop            Stop all services"
    echo "  logs [service]  Tail logs (all or specific service)"
    echo "  status          Show service status and health"
    echo "  clean           Stop and remove all volumes"
    echo "  help            Show this help"
    echo ""
}

# ── Main ──

case "${1:-prod}" in
    dev)        cmd_start_dev "${2:-}" ;;
    prod)       cmd_start_prod "${2:-}" ;;
    stop)       cmd_stop ;;
    logs)       cmd_logs "${2:-}" ;;
    status)     cmd_status ;;
    clean)      cmd_clean ;;
    help|--help|-h) cmd_help ;;
    *)
        log_error "Unknown command: $1"
        cmd_help
        exit 1
        ;;
esac
