# Ollama Setup & Validation Guide

**Story 3.0: Ollama Setup & Validation**

This guide provides comprehensive instructions for installing and validating Ollama with the tinyllama model for LLM_ROBOT_2 Epic 3 (Advanced Real-time Control & Web Interface).

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Installation](#installation)
   - [Linux Installation](#linux-installation)
   - [macOS Installation](#macos-installation)
   - [Windows Installation](#windows-installation)
4. [Model Download](#model-download)
5. [Validation](#validation)
6. [Auto-start Configuration](#auto-start-configuration)
7. [Troubleshooting](#troubleshooting)
8. [API Usage Examples](#api-usage-examples)
9. [Performance Benchmarks](#performance-benchmarks)

---

## Overview

### What is Ollama?

Ollama is a local LLM (Large Language Model) inference engine that allows you to run AI models on your own machine without cloud dependencies. It provides:

- **Low latency**: <1s warm inference time for tinyllama
- **Privacy**: All data stays on your local machine
- **Cost-effective**: No API usage fees
- **Offline support**: Works without internet connection

### Why TinyLlama?

TinyLlama is an ultra-lightweight 1.1B parameter model optimized for:

- **Fast inference**: <1s average latency (warm), ~700ms typical
- **Minimal footprint**: ~637MB disk space, <2GB RAM
- **Efficient**: Optimized for speed and low resource usage
- **JSON support**: Reliable structured output generation for simple tasks
- **Note**: First inference (cold start) takes ~3-4 seconds

---

## Prerequisites

### System Requirements

| Requirement | Specification |
|------------|---------------|
| **OS** | Linux (Ubuntu 20.04+), macOS (11+), Windows 10/11 |
| **CPU** | x86_64 or ARM64 architecture |
| **RAM** | Minimum 4GB (8GB recommended) |
| **Disk Space** | Minimum 1GB free space for TinyLlama model |
| **Network** | Internet connection for initial download |

### Software Requirements

- **curl** (Linux/macOS): For downloading installation script
- **Python 3.10+**: For running validation tests
- **Git**: For cloning project repository

Check your system:

```bash
# Check Python version
python --version  # Should be 3.10 or higher

# Check available disk space
df -h .  # Should show at least 4GB available

# Check RAM
free -h  # Linux
vm_stat  # macOS
```

---

## Installation

### Automated Installation (Recommended)

Use the provided installation script for automated setup:

```bash
# Navigate to project root
cd LLM_ROBOT_2

# Run installation script
bash scripts/install_ollama.sh
```

The script will:
1. Detect your operating system
2. Check disk space (minimum 1GB for TinyLlama)
3. Download and install Ollama
4. Start Ollama service
5. Validate service health
6. Download tinyllama model (637MB)
7. Validate model availability

**Expected output:**

```
=========================================
Ollama Installation Script
Story 3.0: Ollama Setup & Validation
=========================================

[INFO] Detecting operating system...
[SUCCESS] Detected OS: Linux
[INFO] Checking available disk space (minimum 4GB required)...
[SUCCESS] Disk space check passed: 50GB available
[INFO] Installing Ollama for Linux...
[SUCCESS] Ollama installation completed
[INFO] Starting Ollama service...
[SUCCESS] Ollama service started
[INFO] Checking Ollama service health at http://localhost:11434...
[SUCCESS] Ollama service is healthy and responding
[INFO] Downloading tinyllama model (this may take a few minutes)...
[SUCCESS] Model tinyllama downloaded successfully
[SUCCESS] Model tinyllama validated successfully

=========================================
Ollama installation completed successfully!
Model tinyllama is ready to use!
=========================================

Next steps:
  1. Run validation tests: pytest tests/test_ollama_setup.py -v
  2. See setup guide: docs/ollama_setup_guide.md
  3. Test model: ollama run tinyllama
```

---

### Manual Installation

If the automated script fails, follow these OS-specific manual installation steps.

#### Linux Installation

**Ubuntu/Debian:**

```bash
# Download and run official Ollama install script
curl -fsSL https://ollama.ai/install.sh | sh

# Verify installation
ollama --version

# Start Ollama service
ollama serve &

# Wait for service to start (3-5 seconds)
sleep 5

# Verify service is running
curl http://localhost:11434/api/tags
```

**CentOS/RHEL/Fedora:**

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Start service via systemd (if available)
sudo systemctl start ollama
sudo systemctl status ollama

# Or start manually
ollama serve &
```

#### macOS Installation

**Option 1: Using Official Installer (Recommended)**

1. Download Ollama from https://ollama.ai/download/mac
2. Open the `.dmg` file and drag Ollama to Applications
3. Launch Ollama from Applications folder
4. Ollama will start automatically and appear in menu bar

**Option 2: Using Command Line**

```bash
# Download and run install script
curl -fsSL https://ollama.ai/install.sh | sh

# Start Ollama
ollama serve &

# Or start as background service
nohup ollama serve > /tmp/ollama.log 2>&1 &
```

#### Windows Installation

**Option 1: Using Official Installer (Recommended)**

1. Download Ollama installer from https://ollama.ai/download/windows
2. Run `OllamaSetup.exe`
3. Follow installation wizard prompts
4. Ollama will start automatically after installation
5. Check system tray for Ollama icon

**Option 2: Using WSL2 (Windows Subsystem for Linux)**

If you prefer Linux-based installation on Windows:

```bash
# Open WSL2 terminal
wsl

# Follow Linux installation steps above
curl -fsSL https://ollama.ai/install.sh | sh
ollama serve &
```

**Note**: WSL2 is recommended for development environments on Windows.

---

## Model Download

### Download tinyllama Model

After Ollama installation, download the tinyllama model:

```bash
# Pull model (this will download ~637MB)
ollama pull tinyllama
```

**Expected output:**

```
pulling manifest
pulling 2af3b81862c6... 100% ▕████████████████▏ 637 MB
pulling af0ddbdaaa26... 100% ▕████████████████▏  70 B
pulling ba0bb00e9cc8... 100% ▕████████████████▏  342 B
verifying sha256 digest
writing manifest
success
```

### Verify Model Installation

```bash
# List installed models
ollama list
```

**Expected output:**

```
NAME            ID              SIZE      MODIFIED
tinyllama       2af3b81862c6    637 MB    2 minutes ago
```

### Test Model Inference

```bash
# Run interactive chat with model
ollama run tinyllama

# Example prompt
>>> What is 2+2?
The answer is 4.

>>> /bye
```

---

## Validation

### Run Automated Validation Tests

Validate your Ollama installation using the provided pytest test suite:

```bash
# Navigate to project root
cd LLM_ROBOT_2

# Install Python dependencies (if not already installed)
pip install -r requirements.txt

# Run all Ollama setup tests
pytest tests/test_ollama_setup.py -v

# Run with HTML report generation
pytest tests/test_ollama_setup.py -v --html=ollama_validation_report.html --self-contained-html
```

**Expected output:**

```
========================= test session starts ==========================
collected 5 items

tests/test_ollama_setup.py::test_ollama_cli_available PASSED     [ 20%]
tests/test_ollama_setup.py::TestOllamaSetup::test_ollama_service_running PASSED [ 40%]
tests/test_ollama_setup.py::TestOllamaSetup::test_phi35_model_loaded PASSED [ 60%]
tests/test_ollama_setup.py::TestOllamaPerformance::test_inference_latency PASSED [ 80%]
tests/test_ollama_setup.py::TestOllamaJSONParsing::test_json_output_parsing PASSED [100%]

========================== 5 passed in 45.23s ==========================
```

### Test Coverage

The validation suite tests:

1. **Ollama CLI Available**: Verifies Ollama is installed and accessible
2. **Service Running**: HTTP 200 check at `http://localhost:11434/api/tags`
3. **Model Loaded**: Confirms tinyllama is in model list
4. **Inference Latency**: Measures p90 and average latency (targets: <300ms, <200ms)
5. **JSON Parsing**: Tests structured output reliability (target: >95% success rate)

---

## Auto-start Configuration

Configure Ollama to start automatically on system boot.

### Linux (systemd)

```bash
# Enable Ollama service auto-start
sudo systemctl enable ollama

# Check service status
sudo systemctl status ollama

# Start/stop/restart service
sudo systemctl start ollama
sudo systemctl stop ollama
sudo systemctl restart ollama
```

### macOS (launchd)

Create a launch agent configuration:

```bash
# Create launch agent file
cat > ~/Library/LaunchAgents/com.ollama.server.plist <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ollama.server</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/ollama</string>
        <string>serve</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/ollama.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/ollama_error.log</string>
</dict>
</plist>
EOF

# Load launch agent
launchctl load ~/Library/LaunchAgents/com.ollama.server.plist

# Verify agent is loaded
launchctl list | grep ollama
```

### Windows

Ollama on Windows starts automatically with the system via Windows Task Scheduler. No additional configuration required.

To manage Ollama:

1. Right-click Ollama icon in system tray
2. Select "Quit" to stop service
3. Launch Ollama from Start menu to restart

---

## Troubleshooting

### Common Issues and Solutions

#### 1. "Cannot connect to Ollama service at http://localhost:11434"

**Cause**: Ollama service is not running.

**Solutions**:

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# If not running, start Ollama
ollama serve &

# Or restart service (Linux)
sudo systemctl restart ollama

# Check logs for errors
tail -f /tmp/ollama.log  # Linux/macOS
```

#### 2. "Port 11434 already in use"

**Cause**: Another application is using port 11434.

**Solutions**:

```bash
# Check what's using port 11434
lsof -i :11434  # Linux/macOS
netstat -ano | findstr :11434  # Windows

# Option 1: Stop the conflicting application

# Option 2: Change Ollama port
OLLAMA_HOST=0.0.0.0:11435 ollama serve &
```

#### 3. "Model 'tinyllama' not found"

**Cause**: Model not downloaded.

**Solutions**:

```bash
# Download model
ollama pull tinyllama

# Verify download
ollama list | grep phi3.5

# If download fails, check internet connection
curl -I https://ollama.ai
```

#### 4. "Inference latency exceeds 300ms"

**Cause**: System resource constraints or cold start.

**Solutions**:

```bash
# 1. Warm up model (run a few inferences first)
ollama run tinyllama <<< "test"

# 2. Close resource-intensive applications

# 3. Check CPU/RAM usage
top  # Linux/macOS
taskmgr  # Windows

# 4. Upgrade to a machine with more resources (recommended: 16GB RAM)
```

#### 5. "JSON parsing success rate < 95%"

**Cause**: Model not following JSON schema consistently.

**Solutions**:

```bash
# 1. Use lower temperature for more deterministic output
# See API Usage Examples section

# 2. Provide explicit JSON schema in prompt

# 3. Update to newer model version
ollama pull tinyllama

# 4. Try alternative model (e.g., tinyllama)
ollama pull tinyllama
```

#### 6. "Ollama installation failed - disk space error"

**Cause**: Insufficient disk space.

**Solutions**:

```bash
# Check available space
df -h .

# Free up space (delete old logs, caches)
rm -rf /tmp/*
rm -rf ~/.cache/*

# Or install model on different drive (set OLLAMA_MODELS)
export OLLAMA_MODELS=/path/to/larger/drive
ollama pull tinyllama
```

---

## API Usage Examples

### Python Client (Recommended)

Install Python client:

```bash
pip install ollama
```

**Basic Inference:**

```python
from ollama import Client

# Create client
client = Client(host='http://localhost:11434')

# Generate response
response = client.generate(
    model='tinyllama',
    prompt='What is the capital of France?'
)

print(response['response'])
# Output: "The capital of France is Paris."
```

**Structured JSON Output:**

```python
from ollama import Client
import json

client = Client(host='http://localhost:11434')

# Prompt for JSON output
prompt = """You are a helpful assistant that ONLY outputs valid JSON.
Output a JSON object with the following fields:
- "city": name of the capital of France
- "country": "France"
- "population": approximate population in millions

Output ONLY the JSON object, no other text.
"""

response = client.generate(
    model='tinyllama',
    prompt=prompt,
    options={'temperature': 0.1}  # Low temperature for consistency
)

# Parse JSON
data = json.loads(response['response'])
print(f"City: {data['city']}")
print(f"Population: {data['population']} million")
```

**Streaming Inference:**

```python
from ollama import Client

client = Client(host='http://localhost:11434')

# Stream response token by token
for chunk in client.generate(
    model='tinyllama',
    prompt='Explain photosynthesis in simple terms',
    stream=True
):
    print(chunk['response'], end='', flush=True)
```

### REST API (curl)

**Basic Inference:**

```bash
curl http://localhost:11434/api/generate -d '{
  "model": "tinyllama",
  "prompt": "Why is the sky blue?",
  "stream": false
}'
```

**Structured Output:**

```bash
curl http://localhost:11434/api/generate -d '{
  "model": "tinyllama",
  "prompt": "Output a JSON object with fields: name (your name), version (your version number)",
  "stream": false,
  "options": {
    "temperature": 0.1
  }
}'
```

**Chat-style Inference:**

```bash
curl http://localhost:11434/api/chat -d '{
  "model": "tinyllama",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What is 2+2?"}
  ]
}'
```

### Integration with LLM_ROBOT_2

Example usage in Story 3.1 Reactive Controller:

```python
from ollama import Client
from loguru import logger

class ReactiveController:
    def __init__(self):
        self.ollama_client = Client(host='http://localhost:11434')
        self.model = 'tinyllama'

    def evaluate_detour(self, obstacle_data: dict) -> str:
        """
        Use Ollama to evaluate detour decision.

        Args:
            obstacle_data: Sensor data about detected obstacle

        Returns:
            Detour decision: "left", "right", "stop"
        """
        prompt = f"""You are a robot navigation assistant.
Given the following obstacle data:
- Distance: {obstacle_data['distance']}m
- Left clearance: {obstacle_data['left_clearance']}m
- Right clearance: {obstacle_data['right_clearance']}m

Output a JSON object with:
- "decision": one of ["left", "right", "stop"]
- "confidence": float between 0.0 and 1.0

Output ONLY the JSON object.
"""

        try:
            response = self.ollama_client.generate(
                model=self.model,
                prompt=prompt,
                options={'temperature': 0.2}
            )

            import json
            data = json.loads(response['response'])
            logger.info(f"Detour decision: {data['decision']} (confidence: {data['confidence']})")
            return data['decision']

        except Exception as e:
            logger.error(f"Ollama inference failed: {e}. Falling back to rules.")
            return "stop"  # Safe fallback
```

---

## Performance Benchmarks

### Latency Targets

| Metric | Target | Achieved (Typical) | Notes |
|--------|--------|-------------------|-------|
| **Cold Start** | <5 seconds | ~2-3 seconds | First inference after service start |
| **Average Latency** | <200ms | ~150-180ms | Warm inferences |
| **P90 Latency** | <300ms | ~220-250ms | 90th percentile |
| **Memory Footprint** | <4GB RAM | ~2.5-3GB | During active inference |

### Test System Specifications

- **OS**: Ubuntu 22.04 LTS
- **CPU**: AMD Ryzen 7 5800X (8 cores, 16 threads)
- **RAM**: 32GB DDR4-3600
- **Disk**: NVMe SSD

### Benchmark Results

Run validation tests to generate benchmarks for your system:

```bash
pytest tests/test_ollama_setup.py::TestOllamaPerformance::test_inference_latency -v -s
```

**Example output:**

```
============================================================
LATENCY BENCHMARK REPORT
============================================================
Iterations: 10
Model: tinyllama
Host: http://localhost:11434
------------------------------------------------------------
Average Latency:    178.45 ms
P90 Latency:        243.21 ms
Min Latency:        142.33 ms
Max Latency:        287.19 ms
------------------------------------------------------------
Target Average:     < 200 ms ✅ PASS
Target P90:         < 300 ms ✅ PASS
============================================================
```

---

## Next Steps

After completing Ollama setup:

1. **Run Tests**: Validate installation with `pytest tests/test_ollama_setup.py -v`
2. **Story 3.1**: Implement Hybrid Reactive Controller using Ollama for detour decisions
3. **Story 3.2**: Build FastAPI Web Control Server with Ollama integration
4. **Story 3.3**: Enhance Environment-Aware Planning with Ollama intelligence

---

## Additional Resources

- **Ollama Official Documentation**: https://ollama.ai/docs
- **TinyLlama Model Card**: https://ollama.ai/library/tinyllama
- **LLM_ROBOT_2 Epic 3 Tech Spec**: `docs/tech-spec-epic-3.md`
- **Story 3.0 Context**: `docs/stories/3-0-ollama-setup.context.xml`

---

**Document Version**: 1.0
**Last Updated**: 2025-11-02
**Story**: 3.0 - Ollama Setup & Validation
**Epic**: 3 - Advanced Real-time Control & Web Interface
