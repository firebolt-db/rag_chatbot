#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

show_help() {
    cat << EOF
RAG Chatbot Setup Script

Usage: $0 [OPTIONS]

Options:
    --docker        Use Docker setup (recommended)
    --local         Use local Python setup
    --help          Show this help message

Prerequisites:
    - Python 3.12 (for local setup)
    - Docker and Docker Compose (for Docker setup)
    - GPU with NVIDIA drivers (optional, for better performance)
    - Git

Examples:
    $0 --docker     # Set up using Docker
    $0 --local      # Set up using local Python environment
    $0              # Interactive mode (asks for preference)

EOF
}

check_python() {
    if command -v python3.12 &> /dev/null; then
        PYTHON_CMD="python3.12"
    elif command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version 2>&1 | grep -oP '\d+\.\d+')
        if [[ "$PYTHON_VERSION" == "3.12" ]]; then
            PYTHON_CMD="python3"
        else
            print_error "Python 3.12 is required but found Python $PYTHON_VERSION"
            return 1
        fi
    else
        print_error "Python 3.12 is not installed"
        return 1
    fi
    print_success "Found Python 3.12: $PYTHON_CMD"
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        return 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed"
        return 1
    fi
    
    if ! docker info &> /dev/null; then
        print_error "Docker daemon is not running"
        return 1
    fi
    
    print_success "Docker and Docker Compose are available"
}

check_gpu() {
    if command -v nvidia-smi &> /dev/null; then
        print_success "NVIDIA GPU detected"
        nvidia-smi --query-gpu=name --format=csv,noheader | head -1
        return 0
    else
        print_warning "No NVIDIA GPU detected. The chatbot will run on CPU (slower performance)"
        return 1
    fi
}

check_ollama() {
    if command -v ollama &> /dev/null; then
        print_success "Ollama is already installed"
        return 0
    else
        print_status "Ollama not found, will be installed"
        return 1
    fi
}

install_ollama() {
    print_status "Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
    print_success "Ollama installed successfully"
}

setup_ollama_models() {
    print_status "Downloading Ollama models (this may take a while)..."
    ollama pull llama3.1
    ollama pull nomic-embed-text
    print_success "Ollama models downloaded successfully"
}

setup_env_file() {
    if [[ ! -f ".env" ]]; then
        print_status "Creating .env file from template..."
        cp .env.example .env
        print_warning "Please edit .env file with your Firebolt credentials before running the chatbot"
        print_status "Required variables: FIREBOLT_RAG_CHATBOT_ENGINE, FIREBOLT_RAG_CHATBOT_DB, FIREBOLT_RAG_CHATBOT_CLIENT_ID, FIREBOLT_RAG_CHATBOT_CLIENT_SECRET, FIREBOLT_RAG_CHATBOT_ACCOUNT_NAME, FIREBOLT_RAG_CHATBOT_TABLE_NAME"
    else
        print_success ".env file already exists"
    fi
}

setup_local() {
    print_status "Setting up local Python environment..."
    
    check_python || exit 1
    
    if [[ ! -d ".venv" ]]; then
        print_status "Creating virtual environment..."
        $PYTHON_CMD -m venv .venv
    fi
    
    print_status "Activating virtual environment..."
    source .venv/bin/activate
    
    print_status "Installing Python dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
    
    if ! check_ollama; then
        install_ollama
    fi
    
    setup_ollama_models
    setup_env_file
    
    print_success "Local setup completed!"
    print_status "To activate the environment: source .venv/bin/activate"
    print_status "To start the chatbot: python web_server.py"
}

setup_docker() {
    print_status "Setting up Docker environment..."
    
    check_docker || exit 1
    
    setup_env_file
    
    print_status "Building Docker image..."
    docker build -t rag_chatbot .
    
    print_success "Docker setup completed!"
    print_status "To start the chatbot: docker-compose up -d"
    print_status "To view logs: docker-compose logs -f"
    print_status "To stop: docker-compose down"
}

validate_setup() {
    print_status "Validating setup..."
    
    if [[ ! -f "requirements.txt" ]]; then
        print_error "requirements.txt not found"
        return 1
    fi
    
    if [[ ! -f ".env" ]]; then
        print_error ".env file not found. Please create it from .env.example"
        return 1
    fi
    
    print_success "Setup validation passed"
}

main() {
    print_status "RAG Chatbot Setup Script"
    print_status "========================="
    
    case "${1:-}" in
        --help)
            show_help
            exit 0
            ;;
        --docker)
            SETUP_MODE="docker"
            ;;
        --local)
            SETUP_MODE="local"
            ;;
        *)
            echo "Choose setup method:"
            echo "1) Docker (recommended)"
            echo "2) Local Python environment"
            read -p "Enter choice (1 or 2): " choice
            case $choice in
                1) SETUP_MODE="docker" ;;
                2) SETUP_MODE="local" ;;
                *) print_error "Invalid choice"; exit 1 ;;
            esac
            ;;
    esac
    
    print_status "Checking prerequisites..."
    check_gpu || true
    
    case $SETUP_MODE in
        docker)
            setup_docker
            ;;
        local)
            setup_local
            ;;
    esac
    
    validate_setup
    
    print_success "Setup completed successfully!"
    print_status "Next steps:"
    print_status "1. Edit .env file with your Firebolt credentials"
    print_status "2. Update constants.py with your FIREBOLT_RAG_CHATBOT_LOCAL_GITHUB_PATH"
    print_status "3. Run 'python populate_table.py' to populate the database"
    print_status "4. Start the chatbot with the appropriate command shown above"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
