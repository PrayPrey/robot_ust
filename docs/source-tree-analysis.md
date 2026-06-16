# Source Tree Analysis

**Generated:** 2025-12-16
**Scan Level:** Deep

---

## Directory Structure

```
LLM_robot_2/
├── src/                          # Main source code
│   ├── __init__.py
│   ├── main.py                   # Entry point
│   ├── orchestrator.py           # Mission coordinator (core)
│   │
│   ├── agents/                   # Multi-agent system (CrewAI)
│   │   ├── __init__.py
│   │   ├── planner_agent.py      # NL → Action plan (GPT-4o)
│   │   ├── actor_agent.py        # Execute actions on Webots
│   │   └── verifier_agent.py     # Verify mission success
│   │
│   ├── schemas/                  # Pydantic data models
│   │   ├── __init__.py
│   │   ├── mission_command.py    # Mission input schema
│   │   ├── robot_action.py       # Action plan schema
│   │   ├── robot_state.py        # Robot state schema
│   │   └── replan_request.py     # Failure recovery schema
│   │
│   ├── rag/                      # RAG knowledge base (ChromaDB)
│   │   ├── __init__.py
│   │   ├── knowledge_base.py     # ChromaDB integration
│   │   ├── tools.py              # RAG helper functions
│   │   └── data/                 # Knowledge base data files
│   │       ├── robot_capabilities.json
│   │       └── environment_constraints.json
│   │
│   ├── sensors/                  # Sensor integration
│   │   ├── __init__.py
│   │   ├── sensor_manager.py     # Multi-sensor coordinator
│   │   ├── noise_filter.py       # Signal processing
│   │   ├── filter_factory.py     # Filter factory pattern
│   │   ├── config.py             # Sensor configuration
│   │   ├── environment_map.py    # Environment mapping
│   │   └── exceptions.py         # Custom exceptions
│   │
│   ├── reactive/                 # Hybrid reactive controller (Story 3.1)
│   │   ├── __init__.py
│   │   └── hybrid_controller.py  # 3-level decision system
│   │
│   ├── safety/                   # Safety constraints
│   │   ├── __init__.py
│   │   ├── constraints.py        # Safety rules
│   │   └── safety_validator.py   # Validation logic
│   │
│   ├── web/                      # FastAPI web server (Story 3.2)
│   │   ├── __init__.py
│   │   ├── server.py             # FastAPI app, endpoints
│   │   ├── schemas.py            # Web API schemas
│   │   └── templates/            # Web UI (HTML)
│   │       └── index.html
│   │
│   ├── config/                   # Configuration
│   │   └── robot_config.py       # Robot parameters
│   │
│   └── utils/                    # Utilities
│       ├── __init__.py
│       ├── logger_config.py      # Logging setup
│       ├── openlit_config.py     # OpenLit monitoring
│       ├── benchmark_report.py   # Performance reports
│       └── environment_detector.py # Environment classification
│
├── tests/                        # Test suite
│   ├── conftest.py               # Pytest fixtures
│   ├── test_schemas.py           # Schema tests
│   ├── test_planner_agent.py     # Planner tests
│   ├── test_safety_validator.py  # Safety tests
│   ├── test_rag_basic.py         # RAG basic tests
│   ├── test_rag_integration.py   # RAG integration
│   ├── test_reactive_controller.py # Reactive tests
│   ├── test_web_api.py           # Web API tests
│   ├── test_ollama_setup.py      # Ollama tests
│   ├── test_failure_recovery.py  # Recovery tests
│   │
│   ├── unit/                     # Unit tests
│   │   └── test_environment_detector.py
│   │
│   ├── integration/              # Integration tests
│   │   ├── test_web_integration.py
│   │   ├── test_reactive_integration.py
│   │   ├── test_orchestrator_rag_integration.py
│   │   ├── test_environment_rag_filtering.py
│   │   ├── test_error_handling.py
│   │   └── test_epic3_e2e.py
│   │
│   ├── e2e/                      # End-to-end tests
│   │   └── test_web_e2e.py
│   │
│   ├── evaluation/               # Evaluation tests
│   │   └── test_evaluation.py
│   │
│   └── performance/              # Performance tests
│       └── test_load_testing.py
│
├── controllers/                  # Webots robot controllers
│   └── rescue_robot_controller/
│       ├── rescue_robot_controller.py      # Main controller
│       ├── rescue_robot_controller_web.py  # Web-enabled controller
│       ├── rescue_robot_controller_backup.py
│       ├── rescue_robot_controller_old.py
│       └── test_minimal.py
│
├── worlds/                       # Webots simulation worlds
│   └── (*.wbt files)
│
├── web/                          # Web UI static files
│   └── (HTML, CSS, JS)
│
├── data/                         # Data files
│   └── chromadb/                 # ChromaDB vector store
│
├── docs/                         # Documentation
│   ├── architecture.md           # Architecture overview
│   ├── architecture-overview.md
│   ├── architecture-core.md
│   ├── architecture-epic3.md
│   ├── epics.md                  # Epic definitions
│   ├── tech-spec-epic-3.md       # Technical specs
│   ├── ollama_setup_guide.md     # Ollama setup
│   ├── test_plan_epic3.md        # Test plans
│   │
│   ├── stories/                  # User stories
│   │   ├── 2-0-test-infrastructure.md
│   │   ├── 2-3-safety-constraints.md
│   │   ├── 2-4-failure-recovery.md
│   │   ├── 2-5-monitoring-evaluation.md
│   │   ├── 3-0-ollama-setup.md
│   │   ├── 3-1-hybrid-reactive-controller.md
│   │   ├── 3-2-fastapi-web-server.md
│   │   ├── 3-3-environment-aware-planning.md
│   │   ├── 3-5-integration-testing.md
│   │   ├── 3-6-production-fixes.md
│   │   └── 3-7-architectural-refactoring.md
│   │
│   ├── evaluation/               # Evaluation docs
│   │   ├── evaluation_spec.md
│   │   └── presentation_script.md
│   │
│   ├── retrospectives/           # Sprint retrospectives
│   │   ├── epic-2-retro-2025-11-02.md
│   │   └── epic-3-retro-2025-12-15.md
│   │
│   └── archive/                  # Completed epics
│       ├── epic-1-completed.md
│       └── epic-2-completed.md
│
├── scripts/                      # Utility scripts
│   ├── install_ollama.sh
│   └── deploy_web_server.sh
│
├── logs/                         # Mission logs
│
├── .bmad/                        # BMad workflow config
├── BMAD-METHOD/                  # BMad method source
│
├── requirements.txt              # Python dependencies
├── pytest.ini                    # Pytest configuration
├── README.md                     # Project readme
├── CLAUDE.md                     # Claude Code instructions
├── WEB_SERVER_GUIDE.md          # Web server documentation
└── WEBOTS_WEB_CONTROL_GUIDE.md  # Webots integration guide
```

## Critical Directories

### `/src/` - Main Source Code
The core application code organized by domain:
- **agents/**: Multi-agent system using CrewAI framework
- **schemas/**: Pydantic models for type safety
- **rag/**: Knowledge retrieval using ChromaDB
- **reactive/**: Real-time obstacle avoidance
- **web/**: FastAPI server and API endpoints
- **safety/**: Safety validation and constraints

### `/tests/` - Test Suite
Comprehensive test coverage:
- **26 test files** covering unit, integration, e2e, and performance
- **pytest** framework with async support
- **Coverage target**: >80%

### `/controllers/` - Webots Controllers
Robot controller code that runs inside Webots simulation:
- `rescue_robot_controller.py`: Main production controller
- `rescue_robot_controller_web.py`: Web-enabled version

### `/docs/` - Documentation
Rich documentation including:
- Architecture documents
- Epic and story definitions
- Technical specifications
- Retrospectives

## Entry Points

| Entry Point | Location | Purpose |
|-------------|----------|---------|
| **Main App** | `src/main.py` | Direct Python execution |
| **Web Server** | `src/web/server.py` | FastAPI application |
| **Orchestrator** | `src/orchestrator.py` | Mission coordination |
| **Webots Controller** | `controllers/rescue_robot_controller/` | Simulation control |

## Key Integration Points

1. **Web UI → FastAPI**: REST/WebSocket communication
2. **FastAPI → Orchestrator**: Mission execution
3. **Orchestrator → Agents**: CrewAI multi-agent workflow
4. **Agents → RAG**: ChromaDB knowledge retrieval
5. **Actor → Webots**: Robot control commands
6. **Reactive → Ollama**: Real-time LLM decisions

---

*Generated by BMad Document Project Workflow*
