# Development Guide

**Generated:** 2025-12-16
**Python Version:** 3.10+

---

## Prerequisites

### Required Software

| Software | Version | Purpose |
|----------|---------|---------|
| Python | 3.10+ | Runtime |
| Webots | R2023b+ | Robot simulation |
| Ollama | Latest | Local LLM (reactive control) |
| Git | 2.x | Version control |

### API Keys

- **OpenAI API Key**: Required for Planner/Actor/Verifier agents
- Get from: https://platform.openai.com/api-keys

---

## Installation

### 1. Clone Repository

```bash
git clone <repository-url>
cd LLM_robot_2
```

### 2. Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Environment Setup

```bash
# Copy template
cp .env.template .env

# Edit .env file with your values:
OPENAI_API_KEY=sk-...
WEBOTS_PATH=C:\Program Files\Webots
SERVER_PORT=8000
SERVER_HOST=127.0.0.1
```

### 5. Install Ollama

```bash
# Windows: Download from https://ollama.com/download

# Linux/Mac:
curl -fsSL https://ollama.com/install.sh | sh

# Pull tinyllama model
ollama pull tinyllama

# Verify
curl http://localhost:11434/api/tags
```

---

## Running the Application

### Option 1: Web Server (Recommended)

```bash
# Development mode (auto-reload)
uvicorn src.web.server:app --reload --host 127.0.0.1 --port 8000

# Open browser: http://localhost:8000
```

### Option 2: Direct Python

```bash
# Start Webots first (open worlds/robot_world.wbt)

# Run mission
python src/main.py
```

### Option 3: Webots Controller

1. Open Webots
2. Load `worlds/robot_world.wbt`
3. Controller will auto-start

---

## Testing

### Run All Tests

```bash
pytest tests/ -v
```

### Run Specific Categories

```bash
# Unit tests
pytest tests/test_*.py -v

# Integration tests
pytest tests/integration/ -v

# End-to-end tests
pytest tests/e2e/ -v

# Performance tests
pytest tests/performance/ -v
```

### Run with Coverage

```bash
pytest tests/ -v --cov=src --cov-report=html
# Open htmlcov/index.html
```

### Run Specific Test File

```bash
pytest tests/test_web_api.py -v
pytest tests/integration/test_epic3_e2e.py -v
```

---

## Development Workflow

### BMad Workflow Commands

```bash
# Create new story
/bmad:bmm:workflows:create-story

# Implement story
/bmad:bmm:workflows:dev-story

# Code review
/bmad:bmm:workflows:code-review

# Mark story complete
/bmad:bmm:workflows:story-done
```

### Code Quality Standards

1. **Type Hints**: All functions must have type hints
2. **Docstrings**: Google style docstrings for all public functions
3. **Pydantic**: Use Pydantic models for data validation
4. **Logging**: Use loguru for structured logging
5. **Tests**: Maintain >80% coverage

### Pre-commit Checklist

- [ ] All tests passing
- [ ] Type hints added
- [ ] Docstrings complete
- [ ] No linting errors
- [ ] Coverage maintained

---

## Project Structure

```
src/
├── agents/           # Multi-agent system
│   ├── planner_agent.py    # NL → Action plan
│   ├── actor_agent.py      # Execute on robot
│   └── verifier_agent.py   # Verify completion
│
├── schemas/          # Pydantic models
├── rag/              # ChromaDB knowledge base
├── reactive/         # Obstacle avoidance
├── safety/           # Safety constraints
├── web/              # FastAPI server
├── sensors/          # Sensor processing
├── config/           # Configuration
└── utils/            # Utilities
```

---

## Common Tasks

### Adding a New Agent

1. Create file in `src/agents/`
2. Inherit from CrewAI Agent pattern
3. Add to `__init__.py` exports
4. Register in Orchestrator if needed
5. Add tests in `tests/`

### Adding a New API Endpoint

1. Add endpoint in `src/web/server.py`
2. Create request/response schemas in `src/web/schemas.py`
3. Add tests in `tests/test_web_api.py`
4. Update API documentation

### Adding a New Pydantic Model

1. Create or update file in `src/schemas/`
2. Add to `__init__.py` exports
3. Add validation tests in `tests/test_schemas.py`

### Updating RAG Knowledge Base

1. Edit JSON files in `src/rag/data/`
2. Delete ChromaDB cache: `rm -rf data/chromadb/`
3. Restart application (will repopulate)

---

## Debugging

### Common Issues

**Orchestrator not initialized:**
```python
# Ensure robot is running first
# Call set_orchestrator() before API requests
```

**WebSocket connection fails:**
```bash
# Check server is running
curl http://localhost:8000/health

# Check firewall allows port 8000
```

**Ollama not responding:**
```bash
# Verify Ollama is running
curl http://localhost:11434/api/tags

# Restart Ollama service
ollama serve
```

### Logging

```python
from loguru import logger

# Log levels
logger.debug("Detailed info")
logger.info("General info")
logger.warning("Warning")
logger.error("Error")
```

### Structured Logging (Mission Events)

```python
from src.utils import LoggerConfig

LoggerConfig.log_mission_event(
    event="mission_start",
    status="started",
    details={"command": "...", "language": "ko"}
)
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | - | OpenAI API key (required) |
| `WEBOTS_PATH` | - | Webots installation path |
| `SERVER_HOST` | `127.0.0.1` | Web server host |
| `SERVER_PORT` | `8000` | Web server port |
| `OLLAMA_HOST` | `localhost:11434` | Ollama server URL |

### Robot Configuration

Edit `src/config/robot_config.py`:

```python
class RobotConfig:
    MAX_SPEED = 2.0          # m/s
    MIN_SPEED = 0.1          # m/s
    OBSTACLE_DISTANCE = 0.3  # m
    WORKSPACE_SIZE = 5.0     # m (±5m)
```

---

## Performance Targets

| Metric | Target |
|--------|--------|
| Planning latency | < 3s |
| WebSocket latency | < 50ms |
| REST API response | < 500ms |
| Reactive check | 64ms (15.6Hz) |
| Status broadcast | 100ms (10Hz) |
| Ollama inference | P90 < 1200ms |

---

## Deployment

### Development Server

```bash
uvicorn src.web.server:app --reload --host 127.0.0.1 --port 8000
```

### Production Server

```bash
uvicorn src.web.server:app --host 0.0.0.0 --port 8000 --workers 4
```

### Security Checklist

- [ ] Enable HTTPS/TLS
- [ ] Configure authentication
- [ ] Restrict CORS origins
- [ ] Set up firewall rules
- [ ] Use environment-specific config
- [ ] Enable rate limiting

---

*Generated by BMad Document Project Workflow*
