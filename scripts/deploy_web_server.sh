#!/bin/bash
# LLM Robot Web Server Deployment Script
# Story 3.2: FastAPI Web Control Server - Task 10
#
# This script automates the deployment of the FastAPI web control server
# for the LLM Robot system. It handles environment setup, dependency installation,
# and server startup with production-ready configuration.

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PATH="${PROJECT_ROOT}/BMAD-METHOD/venv"
ENV_FILE="${PROJECT_ROOT}/.env"
ENV_TEMPLATE="${PROJECT_ROOT}/.env.template"
SERVER_HOST="${SERVER_HOST:-127.0.0.1}"
SERVER_PORT="${SERVER_PORT:-8000}"
WORKERS="${WORKERS:-4}"
LOG_LEVEL="${LOG_LEVEL:-info}"
MODE="${MODE:-development}"

# Function: Print colored messages
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function: Check prerequisites
check_prerequisites() {
    print_info "Checking prerequisites..."

    # Check Python version
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 not found. Please install Python 3.10+."
        exit 1
    fi

    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    print_info "Python version: $PYTHON_VERSION"

    # Check pip
    if ! command -v pip3 &> /dev/null; then
        print_error "pip3 not found. Please install pip."
        exit 1
    fi

    # Check Ollama (optional but recommended)
    if ! command -v ollama &> /dev/null; then
        print_warn "Ollama not found. Reactive controller will use rule-based fallback."
        print_warn "Install Ollama for full reactive control: https://ollama.com/download"
    else
        print_info "Ollama found: $(ollama --version)"
    fi

    print_info "Prerequisites check completed."
}

# Function: Setup virtual environment
setup_venv() {
    print_info "Setting up virtual environment..."

    if [ ! -d "$VENV_PATH" ]; then
        print_info "Creating virtual environment at $VENV_PATH"
        python3 -m venv "$VENV_PATH"
    else
        print_info "Virtual environment already exists at $VENV_PATH"
    fi

    # Activate virtual environment
    source "${VENV_PATH}/bin/activate" || source "${VENV_PATH}/Scripts/activate"
    print_info "Virtual environment activated."
}

# Function: Install dependencies
install_dependencies() {
    print_info "Installing Python dependencies..."

    # Upgrade pip
    pip install --upgrade pip

    # Install requirements
    if [ -f "${PROJECT_ROOT}/requirements.txt" ]; then
        pip install -r "${PROJECT_ROOT}/requirements.txt"
        print_info "Dependencies installed from requirements.txt"
    else
        print_error "requirements.txt not found at $PROJECT_ROOT"
        exit 1
    fi
}

# Function: Setup environment variables
setup_env() {
    print_info "Configuring environment variables..."

    if [ ! -f "$ENV_FILE" ]; then
        if [ -f "$ENV_TEMPLATE" ]; then
            print_warn ".env file not found. Creating from template..."
            cp "$ENV_TEMPLATE" "$ENV_FILE"
            print_warn "IMPORTANT: Edit .env file and set your OPENAI_API_KEY"
            print_warn "Location: $ENV_FILE"
        else
            print_error ".env.template not found. Cannot create .env file."
            exit 1
        fi
    else
        print_info ".env file found at $ENV_FILE"
    fi

    # Check critical environment variables
    source "$ENV_FILE"

    if [ -z "$OPENAI_API_KEY" ]; then
        print_error "OPENAI_API_KEY not set in .env file!"
        print_error "Please edit $ENV_FILE and add your OpenAI API key."
        exit 1
    fi

    print_info "Environment variables configured."
}

# Function: Run tests (optional)
run_tests() {
    if [ "$RUN_TESTS" = "true" ]; then
        print_info "Running tests..."
        pytest tests/test_web_api.py -v || true
        print_info "Tests completed (check output for failures)."
    fi
}

# Function: Setup firewall (Linux only)
setup_firewall() {
    if [ "$MODE" = "production" ] && [ "$(uname)" = "Linux" ]; then
        print_info "Configuring firewall for port $SERVER_PORT..."

        # Check if ufw is available
        if command -v ufw &> /dev/null; then
            sudo ufw allow "$SERVER_PORT"/tcp
            print_info "Firewall rule added for port $SERVER_PORT"
        else
            print_warn "ufw not found. Manually configure firewall to allow port $SERVER_PORT"
        fi
    fi
}

# Function: Start web server
start_server() {
    print_info "Starting FastAPI web server..."

    # Set host based on mode
    if [ "$MODE" = "production" ]; then
        SERVER_HOST="0.0.0.0"  # Listen on all interfaces
        RELOAD_FLAG=""
    else
        SERVER_HOST="127.0.0.1"  # Localhost only
        RELOAD_FLAG="--reload"
    fi

    print_info "Configuration:"
    print_info "  Mode: $MODE"
    print_info "  Host: $SERVER_HOST"
    print_info "  Port: $SERVER_PORT"
    print_info "  Workers: $WORKERS"
    print_info "  Log Level: $LOG_LEVEL"

    # Change to project root
    cd "$PROJECT_ROOT"

    # Start server with uvicorn
    if [ "$MODE" = "production" ]; then
        print_info "Starting production server with $WORKERS workers..."
        uvicorn src.web.server:app \
            --host "$SERVER_HOST" \
            --port "$SERVER_PORT" \
            --workers "$WORKERS" \
            --log-level "$LOG_LEVEL" \
            --access-log \
            --no-use-colors
    else
        print_info "Starting development server with auto-reload..."
        uvicorn src.web.server:app \
            --host "$SERVER_HOST" \
            --port "$SERVER_PORT" \
            --reload \
            --log-level "$LOG_LEVEL"
    fi
}

# Function: Print usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Deploy and start the LLM Robot Web Control Server.

OPTIONS:
    -m, --mode MODE          Deployment mode: 'development' or 'production' (default: development)
    -h, --host HOST          Server host address (default: 127.0.0.1 for dev, 0.0.0.0 for prod)
    -p, --port PORT          Server port (default: 8000)
    -w, --workers NUM        Number of worker processes for production (default: 4)
    -l, --log-level LEVEL    Log level: debug, info, warning, error (default: info)
    -t, --test               Run tests before starting server
    --help                   Show this help message

EXAMPLES:
    # Development mode (default)
    $0

    # Production mode with custom port
    $0 --mode production --port 8080

    # Run tests before starting
    $0 --test

    # Custom configuration
    $0 --mode production --host 0.0.0.0 --port 8000 --workers 8 --log-level debug

ENVIRONMENT VARIABLES:
    SERVER_HOST              Override default host
    SERVER_PORT              Override default port
    WORKERS                  Override worker count
    LOG_LEVEL                Override log level
    RUN_TESTS                Set to 'true' to run tests

REQUIREMENTS:
    - Python 3.10+
    - Virtual environment at BMAD-METHOD/venv
    - .env file with OPENAI_API_KEY
    - Ollama installed and running (optional, for reactive control)

For more information, see README.md
EOF
}

# Main script
main() {
    print_info "LLM Robot Web Server Deployment"
    print_info "================================"

    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -m|--mode)
                MODE="$2"
                shift 2
                ;;
            -h|--host)
                SERVER_HOST="$2"
                shift 2
                ;;
            -p|--port)
                SERVER_PORT="$2"
                shift 2
                ;;
            -w|--workers)
                WORKERS="$2"
                shift 2
                ;;
            -l|--log-level)
                LOG_LEVEL="$2"
                shift 2
                ;;
            -t|--test)
                RUN_TESTS="true"
                shift
                ;;
            --help)
                usage
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done

    # Execute deployment steps
    check_prerequisites
    setup_venv
    install_dependencies
    setup_env
    run_tests
    setup_firewall
    start_server
}

# Run main function
main "$@"
