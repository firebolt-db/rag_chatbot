# RAG Chatbot

This repository contains code and instructions for running your own Firebolt-powered chatbot that uses retrieval-augmented generation (RAG).

## Quick Start

### Prerequisites
- Python 3.12 (for local setup)
- Docker and Docker Compose (for Docker setup)
- GPU with NVIDIA drivers (optional, for better performance)
- Git

### Installing Task

[Task](https://taskfile.dev/) is a task runner / build tool that aims to be simpler and easier to use than, for example, GNU Make. It's used in this project to simplify common operations.

Install Task using one of the following methods:

```bash
# macOS (via Homebrew)
brew install go-task/tap/go-task

# Linux (via script)
sh -c "$(curl --location https://taskfile.dev/install.sh)" -- -d
```

For other installation methods, see the [official Task installation guide](https://taskfile.dev/installation/).

### Option 1: Automated Setup (Recommended)
```bash
# Clone the repository
git clone <repository-url>
cd rag_chatbot

# Run the automated setup script (interactive mode)
./setup.sh

# Or specify setup mode directly:
./setup.sh --docker  # for Docker setup
./setup.sh --local   # for local Python setup
```

The script will:
1. Check your system for required dependencies
2. Install Ollama if not already installed
3. Set up environment files
4. Install Python dependencies or build Docker containers
5. Download required Ollama models

### Option 2: Task-based Setup
If you have Task installed:
```bash
# Install dependencies
task install-deps

# Setup Ollama models
task setup-ollama

# Start the server
task start-server
```

## Configuration
1. Copy `.env.example` to `.env` and fill in your Firebolt credentials
2. Update the GitHub repository paths and chunking strategy configuration in your `.env` file
3. Run `task populate` or `python populate_table.py` to populate your vector database
4. The system automatically ensures chunking strategy consistency across embedding generation and retrieval

### Docker Setup for populate_table.py
When using Docker, you can populate the table using the following methods:

**Option 1: Using Task (Recommended)**
```bash
# This automatically detects Docker vs local setup
task populate
```

**Option 2: Direct Docker Command**
```bash
# Ensure your Docker services are running
docker compose up -d

# Run populate_table.py inside the container
docker compose exec rag_chatbot python populate_table.py
```

**Important Notes for Docker:**
- The `FIREBOLT_RAG_CHATBOT_LOCAL_GITHUB_PATH` environment variable should point to your local GitHub repositories directory
- This directory is automatically mounted to `/github` inside the Docker container
- The script will automatically use `/github` as the base path when running in Docker
- Make sure your document repositories are cloned locally in the `FIREBOLT_RAG_CHATBOT_LOCAL_GITHUB_PATH` directory before running

## Troubleshooting
- **GPU Support**: For Docker GPU support, ensure NVIDIA Docker runtime is installed
- **Ollama Models**: Models are automatically downloaded but may take time on first run
- **Port Conflicts**: Default ports are 5000 (web) and 11434 (Ollama)
- **Ollama Performance**: For better performance with large models, consider the following:
  - On macOS: `OLLAMA_FLASH_ATTENTION="1" OLLAMA_KV_CACHE_TYPE="q8_0" /usr/local/opt/ollama/bin/ollama serve`
  - For production: Use GPU-accelerated or cloud-hosted inference services

---

# Prerequisites

## Firebolt Account Setup
1. [Register for Firebolt](https://docs.firebolt.io/Guides/getting-started/index.html)
2. Set up your account following [these instructions](https://docs.firebolt.io/Guides/managing-your-organization/managing-accounts.html)
3. Create a database by following the [Create a Database](https://docs.firebolt.io/Guides/getting-started/get-started-sql.html) section
4. Create or use an existing engine (Firebolt may have automatically created `my_engine`)
5. Create a service account:
   - Follow the [service account setup instructions](https://docs.firebolt.io/Guides/managing-your-organization/service-accounts.html)
   - When creating a user, select `Service Account` in the `Assign To` dropdown and `account_admin` for the role

## System Requirements
- Python 3.12
- GPU support (recommended) - many local computers have GPUs, but for better performance consider using a cloud GPU instance

# Detailed Setup Guide

## Environment Setup

### Option 1: Automated Setup (Recommended)
Run the automated script which will handle all dependencies:
```bash
./setup.sh
```

Choose either Docker or local setup when prompted, or specify directly:
```bash
./setup.sh --docker  # for Docker setup
./setup.sh --local   # for local Python setup
```

### Option 2: Manual Setup
If you prefer to set up manually:

1. **Install Ollama**:
   - **macOS**: `brew install ollama && brew services start ollama`
   - **Linux**: `curl -fsSL https://ollama.com/install.sh | sh`
   - **Windows**: Download from [ollama.com/download](https://ollama.com/download)

2. **Pull Required Models**:
   ```bash
   ollama pull llama3.1
   ollama pull nomic-embed-text
   ```

3. **Setup Python Environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

## Configuration

1. **Environment Variables**:
   - Copy `.env.example` to `.env`
   - Fill in the required Firebolt credentials and configuration:
     ```
     # Firebolt Database Configuration
     FIREBOLT_RAG_CHATBOT_CLIENT_ID=<your-service-account-id>
     FIREBOLT_RAG_CHATBOT_CLIENT_SECRET=<your-service-account-secret>
     FIREBOLT_RAG_CHATBOT_ENGINE=<your-engine-name>
     FIREBOLT_RAG_CHATBOT_DB=<your-database-name>
     FIREBOLT_RAG_CHATBOT_ACCOUNT_NAME=<your-account-name>
     FIREBOLT_RAG_CHATBOT_TABLE_NAME=<your-table-name>
     FIREBOLT_RAG_CHATBOT_LOCAL_GITHUB_PATH=<path-to-your-github-repos>
     
     # Chunking Strategy Configuration (Environment-Driven)
     FIREBOLT_RAG_CHATBOT_CHUNKING_STRATEGY=recursive_character_text_splitting
     FIREBOLT_RAG_CHATBOT_CHUNK_SIZE=300
     FIREBOLT_RAG_CHATBOT_CHUNK_OVERLAP=50
     FIREBOLT_RAG_CHATBOT_NUM_WORDS_PER_CHUNK=100
     FIREBOLT_RAG_CHATBOT_NUM_SENTENCES_PER_CHUNK=3
     FIREBOLT_RAG_CHATBOT_BATCH_SIZE=150
     ```
   
   **Chunking Strategy Options:**
   - `recursive_character_text_splitting` (recommended)
   - `semantic_chunking`
   - `by_paragraph`
   - `by_sentence`
   - `by_sentence_with_sliding_window`
   - `every_n_words`

2. **Prepare Documents for RAG**:
   - Clone your document repositories locally
   - Update `repo_dict` in `populate_table.py` with your repositories
   - Configure chunking strategy and parameters via environment variables (no code changes needed)
   - Optionally, add file names to `DISALLOWED_FILENAMES` in `constants.py` to exclude them

3. **Populate the Vector Database**:
   - The script automatically validates chunking strategy consistency to prevent embedding mismatches
   - For local setup: `python populate_table.py`
   - For Docker setup: `task populate` or `docker compose exec rag_chatbot python populate_table.py`
   - **Important**: The system will warn you if changing chunking strategies on existing embeddings

4. **Customize the Chatbot**:
   - Modify the prompt in `run_chatbot()` function in `run_llm.py` to suit your use case
   - Configure chunking strategy and parameters via environment variables in your `.env` file
   - The system automatically ensures consistency between embedding generation and retrieval phases

## Running the Chatbot

### Local Setup:
```bash
python web_server.py
```

### Docker Setup:
```bash
docker-compose up -d
```

Access the web UI at [http://127.0.0.1:5000](http://127.0.0.1:5000)

## Common Issues and Solutions

### Document Handling
- **Supported Formats**: Only `.docx`, `.txt`, and `.md` files are processed
- **Character Issues**: Null characters and certain Unicode values may cause errors in Firebolt tables
- **Markdown Syntax**: Ensure all Markdown files have valid syntax to prevent errors

### Chunking Strategy Configuration
- **Environment-Driven**: All chunking parameters are configurable via environment variables
- **Consistency Validation**: The system automatically validates chunking strategy consistency before processing
- **No Code Changes**: Switch between chunking strategies by updating your `.env` file only
- **Strategy Mismatch Warning**: The system warns when attempting to mix different chunking strategies in the same database

### User Access Control
To toggle between internal/external user access:
- Go to `web_server.py`
- Set `is_customer=True` in the `run_chatbot()` function to restrict access to public documents only

## Example Dataset

We have provided an example dataset that you can use to build your chatbot! You can find the dataset at [this GitHub repository](https://github.com/firebolt-analytics/rag_dataset), which contains documentation for HuggingFace Transformers.
