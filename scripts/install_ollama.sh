#!/bin/bash

################################################################################
# Ollama Installation Script for LLM_robot_2
# Story 3.0: Ollama Setup & Validation
# Supports: Linux, macOS, Windows (WSL)
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
OLLAMA_HOST="http://localhost:11434"
OLLAMA_API_TAGS="${OLLAMA_HOST}/api/tags"
MODEL_NAME="tinyllama"
MIN_DISK_SPACE_GB=1  # TinyLlama only needs ~637MB
INSTALL_RETRY_COUNT=3
HEALTH_CHECK_TIMEOUT=30

################################################################################
# Utility Functions
################################################################################

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

################################################################################
# OS Detection
################################################################################

detect_os() {
    log_info "Detecting operating system..."

    case "$(uname -s)" in
        Linux*)
            OS="Linux"
            ;;
        Darwin*)
            OS="macOS"
            ;;
        CYGWIN*|MINGW*|MSYS*)
            OS="Windows"
            ;;
        *)
            log_error "Unsupported operating system: $(uname -s)"
            exit 1
            ;;
    esac

    log_success "Detected OS: ${OS}"
}

################################################################################
# Disk Space Check
################################################################################

check_disk_space() {
    log_info "Checking available disk space (minimum ${MIN_DISK_SPACE_GB}GB required for TinyLlama)..."

    case "${OS}" in
        Linux|macOS)
            available_gb=$(df -BG . | tail -1 | awk '{print $4}' | sed 's/G//')
            ;;
        Windows)
            # For Windows/WSL, check current drive
            available_gb=$(df -BG . | tail -1 | awk '{print $4}' | sed 's/G//')
            ;;
    esac

    if [ "${available_gb}" -lt "${MIN_DISK_SPACE_GB}" ]; then
        log_error "Insufficient disk space: ${available_gb}GB available, ${MIN_DISK_SPACE_GB}GB required"
        exit 1
    fi

    log_success "Disk space check passed: ${available_gb}GB available"
}

################################################################################
# Check if Ollama is Already Installed
################################################################################

check_ollama_installed() {
    log_info "Checking if Ollama is already installed..."

    if command -v ollama &> /dev/null; then
        OLLAMA_VERSION=$(ollama --version 2>&1 || echo "unknown")
        log_warning "Ollama is already installed: ${OLLAMA_VERSION}"
        return 0
    else
        log_info "Ollama is not installed"
        return 1
    fi
}

################################################################################
# Install Ollama
################################################################################

install_ollama() {
    log_info "Installing Ollama for ${OS}..."

    case "${OS}" in
        Linux|macOS)
            log_info "Downloading and executing official Ollama install script..."
            for attempt in $(seq 1 ${INSTALL_RETRY_COUNT}); do
                if curl -fsSL https://ollama.ai/install.sh | sh; then
                    log_success "Ollama installation completed"
                    return 0
                else
                    log_warning "Installation attempt ${attempt}/${INSTALL_RETRY_COUNT} failed"
                    if [ ${attempt} -lt ${INSTALL_RETRY_COUNT} ]; then
                        log_info "Retrying in 5 seconds..."
                        sleep 5
                    fi
                fi
            done
            log_error "Failed to install Ollama after ${INSTALL_RETRY_COUNT} attempts"
            exit 1
            ;;
        Windows)
            log_warning "Windows detected. Please install Ollama manually:"
            log_info "1. Download installer from https://ollama.ai/download/windows"
            log_info "2. Run the installer and follow the prompts"
            log_info "3. Restart this script after installation"
            exit 1
            ;;
    esac
}

################################################################################
# Start Ollama Service
################################################################################

start_ollama_service() {
    log_info "Starting Ollama service..."

    case "${OS}" in
        Linux)
            # Check if systemd is available
            if command -v systemctl &> /dev/null; then
                if systemctl is-active --quiet ollama; then
                    log_success "Ollama service is already running"
                else
                    log_info "Starting Ollama service via systemd..."
                    sudo systemctl start ollama
                    log_success "Ollama service started"
                fi
            else
                log_warning "systemd not available. Starting Ollama in background..."
                nohup ollama serve > /tmp/ollama.log 2>&1 &
                log_success "Ollama started in background (PID: $!)"
            fi
            ;;
        macOS)
            # Check if Ollama is running via launchctl
            if pgrep -x ollama > /dev/null; then
                log_success "Ollama is already running"
            else
                log_info "Starting Ollama..."
                nohup ollama serve > /tmp/ollama.log 2>&1 &
                log_success "Ollama started in background (PID: $!)"
            fi
            ;;
        Windows)
            log_warning "Please start Ollama service manually on Windows"
            log_info "Run: ollama serve"
            ;;
    esac

    # Wait for service to be ready
    log_info "Waiting for Ollama service to be ready..."
    sleep 3
}

################################################################################
# Service Health Check
################################################################################

check_service_health() {
    log_info "Checking Ollama service health at ${OLLAMA_HOST}..."

    local elapsed=0
    local interval=2

    while [ ${elapsed} -lt ${HEALTH_CHECK_TIMEOUT} ]; do
        if curl -s -f -m 5 "${OLLAMA_API_TAGS}" > /dev/null 2>&1; then
            log_success "Ollama service is healthy and responding at ${OLLAMA_HOST}"
            return 0
        fi

        sleep ${interval}
        elapsed=$((elapsed + interval))
        log_info "Waiting for service... (${elapsed}s/${HEALTH_CHECK_TIMEOUT}s)"
    done

    log_error "Ollama service health check failed after ${HEALTH_CHECK_TIMEOUT}s"
    log_error "Please check if port 11434 is available and Ollama is running"
    log_info "Troubleshooting:"
    log_info "  - Check logs: tail -f /tmp/ollama.log"
    log_info "  - Check port: lsof -i :11434 (Linux/macOS)"
    log_info "  - Restart service: ollama serve"
    exit 1
}

################################################################################
# Download phi3.5:mini Model
################################################################################

download_model() {
    log_info "Checking if ${MODEL_NAME} model is already downloaded..."

    # Check if model exists
    if ollama list | grep -q "${MODEL_NAME}"; then
        log_success "Model ${MODEL_NAME} is already downloaded"
        return 0
    fi

    log_info "Downloading ${MODEL_NAME} model (this may take a few minutes)..."

    # Download model with retry logic
    for attempt in $(seq 1 ${INSTALL_RETRY_COUNT}); do
        if ollama pull "${MODEL_NAME}"; then
            log_success "Model ${MODEL_NAME} downloaded successfully"
            return 0
        else
            log_warning "Model download attempt ${attempt}/${INSTALL_RETRY_COUNT} failed"
            if [ ${attempt} -lt ${INSTALL_RETRY_COUNT} ]; then
                log_info "Retrying in 10 seconds..."
                sleep 10
            fi
        fi
    done

    log_error "Failed to download model ${MODEL_NAME} after ${INSTALL_RETRY_COUNT} attempts"
    exit 1
}

################################################################################
# Validate Model
################################################################################

validate_model() {
    log_info "Validating ${MODEL_NAME} model..."

    # Check if model is in the list
    if ! ollama list | grep -q "${MODEL_NAME}"; then
        log_error "Model ${MODEL_NAME} not found in ollama list"
        exit 1
    fi

    log_success "Model ${MODEL_NAME} validated successfully"

    # Display model info
    log_info "Installed models:"
    ollama list
}

################################################################################
# Configure Auto-start (Instructions Only)
################################################################################

configure_autostart() {
    log_info "Auto-start configuration instructions:"

    case "${OS}" in
        Linux)
            echo ""
            log_info "To enable Ollama auto-start on Linux (systemd):"
            echo "  sudo systemctl enable ollama"
            echo ""
            ;;
        macOS)
            echo ""
            log_info "To enable Ollama auto-start on macOS (launchd):"
            echo "  1. Create file: ~/Library/LaunchAgents/com.ollama.server.plist"
            echo "  2. Add launch agent configuration (see docs/ollama_setup_guide.md)"
            echo "  3. Load agent: launchctl load ~/Library/LaunchAgents/com.ollama.server.plist"
            echo ""
            ;;
        Windows)
            echo ""
            log_info "Ollama on Windows starts automatically with the system"
            echo ""
            ;;
    esac
}

################################################################################
# Main Installation Flow
################################################################################

main() {
    echo ""
    log_info "========================================="
    log_info "Ollama Installation Script"
    log_info "Story 3.0: Ollama Setup & Validation"
    log_info "========================================="
    echo ""

    # Step 1: Detect OS
    detect_os

    # Step 2: Check disk space
    check_disk_space

    # Step 3: Check if already installed
    if check_ollama_installed; then
        log_info "Skipping installation, proceeding to service check..."
    else
        # Step 4: Install Ollama
        install_ollama
    fi

    # Step 5: Start service
    start_ollama_service

    # Step 6: Health check
    check_service_health

    # Step 7: Download and validate model
    download_model

    # Step 8: Validate model
    validate_model

    # Step 9: Auto-start instructions
    configure_autostart

    echo ""
    log_success "========================================="
    log_success "Ollama installation completed successfully!"
    log_success "Model ${MODEL_NAME} is ready to use!"
    log_success "========================================="
    echo ""
    log_info "Next steps:"
    log_info "  1. Run validation tests: pytest tests/test_ollama_setup.py -v"
    log_info "  2. See setup guide: docs/ollama_setup_guide.md"
    log_info "  3. Test model: ollama run ${MODEL_NAME} (TinyLlama 1.1B)"
    echo ""
}

# Execute main function
main "$@"
