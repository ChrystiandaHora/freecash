#!/usr/bin/env bash
# ======================================================================
#   [$]  FreeCash Dynamic Port Orchestrator (Universal Shell Version)
#   Automatically detects host port conflicts and re-routes postgres,
#   backend, and frontend services to available ports.
# ======================================================================

# Force script to run from its own directory
cd "$(dirname "$0")"

# ANSI Color Codes for Premium Console Styling
BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
BLUE="\033[34m"
CYAN="\033[36m"
RED="\033[31m"
RESET="\033[0m"

# Print Welcome Banner
echo -e "\n${CYAN}${BOLD}======================================================================${RESET}"
echo -e "${CYAN}${BOLD}   [$]  FreeCash Dynamic Port Orchestrator${RESET}"
echo -e "${CYAN}${BOLD}======================================================================${RESET}\n"

# 1. Check and Auto-Create .env File
if [ ! -f .env ]; then
    echo -e "${YELLOW}[ENV]  .env file not found. Auto-configuring from .env_example...${RESET}"
    if [ -f .env_example ]; then
        cp .env_example .env
        echo -e "    ${GREEN}[ OK ] Created .env file successfully with default credentials!${RESET}\n"
    else
        echo -e "    ${RED}[FAIL] Error: .env_example not found. Cannot auto-configure .env.${RESET}"
        exit 1
    fi
fi

# 2. Pre-requisite Checks
if ! command -v docker >/dev/null 2>&1; then
    echo -e "${RED}${BOLD}[FAIL] Error: Docker is not installed.${RESET}"
    echo -e "Please install Docker Desktop (https://www.docker.com/products/docker-desktop/) and try again."
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo -e "${RED}${BOLD}[FAIL] Error: Docker daemon is not running.${RESET}"
    echo -e "Please start Docker Desktop/Engine and try again."
    exit 1
fi

# 3. Port Scanning & Conflict Resolution Functions
is_port_free() {
    local port=$1
    # Try using bash's built-in /dev/tcp (extremely fast, zero dependencies)
    if (echo > /dev/tcp/127.0.0.1/$port) >/dev/null 2>&1; then
        return 1 # Port is busy
    fi
    # Fallback to nc (netcat) if available
    if command -v nc >/dev/null 2>&1; then
        if nc -z 127.0.0.1 "$port" >/dev/null 2>&1; then
            return 1 # Port is busy
        fi
    fi
    # Fallback to lsof if available
    if command -v lsof >/dev/null 2>&1; then
        if lsof -i :"$port" >/dev/null 2>&1; then
            return 1 # Port is busy
        fi
    fi
    return 0 # Port is free
}

find_next_free_port() {
    local port=$1
    local has_conflict=0
    while ! is_port_free "$port"; do
        has_conflict=1
        port=$((port + 1))
    done
    echo "$port $has_conflict"
}

format_status() {
    local default_port=$1
    local actual_port=$2
    local conflict=$3
    if [ "$conflict" -eq 1 ]; then
        echo -e "${YELLOW}${actual_port} [CONFLICT -> RESOLVED]${RESET}"
    else
        echo -e "${GREEN}${actual_port} [FREE]${RESET}"
    fi
}

echo -e "[SCAN]  ${BOLD}Scanning local ports for conflicts...${RESET}"

# Scan PostgreSQL
read -r pg_port pg_conflict <<< "$(find_next_free_port 5432)"
# Scan Django Backend
read -r backend_port backend_conflict <<< "$(find_next_free_port 8000)"
# Scan React Frontend
read -r front_port front_conflict <<< "$(find_next_free_port 5173)"

echo -e "   • ${BOLD}PostgreSQL Database${RESET} : 5432 -> Mapped to $(format_status 5432 "$pg_port" "$pg_conflict")"
echo -e "   • ${BOLD}Django Backend API${RESET}  : 8000 -> Mapped to $(format_status 8000 "$backend_port" "$backend_conflict")"
echo -e "   • ${BOLD}React Vite Frontend${RESET} : 5173 -> Mapped to $(format_status 5173 "$front_port" "$front_conflict")"

# 4. Generate Dynamic env.docker
env_docker_path=".env.docker"

echo "# ======================================================================" > "$env_docker_path"
echo "# Generated automatically by run.sh - DO NOT EDIT MANUALLY" >> "$env_docker_path"
echo "# ======================================================================" >> "$env_docker_path"
echo "" >> "$env_docker_path"

# Copy base .env variables
cat .env >> "$env_docker_path"
echo "" >> "$env_docker_path"

# Inject dynamically computed values
echo "POSTGRES_PORT=$pg_port" >> "$env_docker_path"
echo "BACKEND_PORT=$backend_port" >> "$env_docker_path"
echo "FRONTEND_PORT=$front_port" >> "$env_docker_path"
echo "VITE_API_URL=http://localhost:$backend_port" >> "$env_docker_path"

# Print URLs and access credentials
echo -e "\n${CYAN}${BOLD}   [Access URLs & Integration info]${RESET}"
echo -e "     -> ${BOLD}Frontend Client:${RESET}    ${BLUE}http://localhost:${front_port}${RESET}"
echo -e "     -> ${BOLD}Backend API url:${RESET}    ${BLUE}http://localhost:${backend_port}/api/${RESET}"
echo -e "     -> ${BOLD}CORS Integration:${RESET}   Django allows origin ${YELLOW}http://localhost:${front_port}${RESET}"
echo -e "     -> ${BOLD}PostgreSQL Port:${RESET}    ${BLUE}${pg_port}${RESET} (internal: 5432)"

# 5. Launch Docker Compose
echo -e "\n${CYAN}${BOLD}======================================================================${RESET}"
echo -e "   [START]  ${BOLD}Starting Docker Compose...${RESET} (Press ${RED}${BOLD}Ctrl+C${RESET} to shut down)"
echo -e "${CYAN}${BOLD}======================================================================${RESET}\n"

# Setup Graceful shutdown handler
cleanup() {
    echo -e "\n\n${YELLOW}[STOP]  Ctrl+C detected. Shutting down containers gracefully...${RESET}"
    docker compose --env-file "$env_docker_path" down
    echo -e "${GREEN}[ OK ] Containers stopped successfully. Have a nice day!${RESET}\n"
    exit 0
}
trap cleanup INT

# Determine action (default to up)
if [ $# -eq 0 ]; then
    docker compose --env-file "$env_docker_path" up --build
else
    docker compose --env-file "$env_docker_path" "$@"
fi
