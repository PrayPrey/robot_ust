# LLM_ROBOT_2 - Architecture Overview

**Project:** LLM_ROBOT_2 - Search & Rescue Robot
**Author:** BMad
**Date:** 2025-10-29
**Version:** 1.0

---

## 📚 Architecture Documentation Structure

This architecture is split into multiple documents for better navigation and LLM context efficiency:

1. **[architecture-overview.md](./architecture-overview.md)** (This file) - Executive Summary + Navigation
2. **[architecture-core.md](./architecture-core.md)** - Epic 1-2 Foundation (Multi-Agent System, RAG, Safety)
3. **[architecture-epic3.md](./architecture-epic3.md)** - Epic 3 Advanced Features (Real-time Control, Web Interface)

---

## Executive Summary

**범용 LLM 기반 로봇 제어 프레임워크 (Generic LLM-powered Robot Control Framework)**

본 아키텍처는 자연어 명령으로 다양한 로봇을 제어할 수 있는 **도메인 중립적** 플랫폼을 정의합니다. CrewAI Multi-agent 시스템(Planner/Actor/Verifier), Pydantic Function Calling, ChromaDB RAG를 결합하여 **로봇 타입, 도메인, 작업에 무관하게** 적용 가능한 범용 아키텍처를 제시합니다.

**첫 번째 구현 유스케이스**: 재난 구조 로봇 (Search & Rescue Robot)으로 프레임워크를 검증합니다. 이는 재난 현장에서 자연어 명령을 통해 생존자를 자율 탐색하는 시스템이며, 동일한 아키텍처는 창고 자동화, 드론 제어, 로봇 팔 조작 등 다양한 도메인에 확장 가능합니다.

---

## System Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────┐
│                    구조대 (User)                             │
│              "3층 동쪽 구역 생존자 탐색"                       │
└────────────────────┬────────────────────────────────────────┘
                     │ 자연어 명령
                     ▼
┌─────────────────────────────────────────────────────────────┐
│               CrewAI Multi-Agent System                      │
│  ┌────────────┐  ┌────────────┐  ┌──────────────┐          │
│  │  Planner   │→ │   Actor    │→ │  Verifier    │          │
│  │   Agent    │  │   Agent    │  │   Agent      │          │
│  └─────┬──────┘  └─────┬──────┘  └──────┬───────┘          │
│        │ RAG           │ Function        │ 검증             │
│        ▼               │ Calling         ▼                  │
│  ┌────────────┐        ▼         ┌──────────────┐          │
│  │ ChromaDB   │  ┌─────────────┐ │ 재계획       │          │
│  │ (지식 DB)  │  │  Pydantic   │ │ 트리거       │          │
│  └────────────┘  │  Schemas    │ └──────────────┘          │
│                  └─────┬───────┘                            │
└────────────────────────┼────────────────────────────────────┘
                         │ Webots API Calls
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Webots 시뮬레이터                               │
│  ┌──────────┐  ┌─────────┐  ┌──────────┐                  │
│  │ 재난     │  │ 로봇    │  │ 센서     │                  │
│  │ 환경     │  │ (이동)  │  │ (카메라  │                  │
│  │ (붕괴)   │  │         │  │ /Lidar)  │                  │
│  └──────────┘  └─────────┘  └──────────┘                  │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│          Monitoring & Logging Layer                         │
│      OpenLit (LLM 추적) + Loguru (행동 로깅)                │
└─────────────────────────────────────────────────────────────┘
```

---

## Core Technology Stack

| Component | Technology | Role |
|-----------|-----------|------|
| **Multi-Agent** | CrewAI + OpenAI GPT-4o-mini | Planner/Actor/Verifier orchestration |
| **Data Validation** | Pydantic 2.x | Function Calling, type safety |
| **RAG System** | ChromaDB + OpenAI Embeddings | Knowledge retrieval |
| **Simulator** | Webots R2023a | Rescue environment simulation |
| **Monitoring** | OpenLit + Loguru | LLM tracking, structured logging |
| **Web Control (Epic 3)** | FastAPI + React 18 | Natural language web interface |
| **Reactive AI (Epic 3)** | Ollama tinyllama 1.1B | Real-time obstacle avoidance |

---

## Project Phases

### Epic 1-2: Foundation (Completed ✅)
**Detailed in:** [architecture-core.md](./architecture-core.md)

- CrewAI Multi-agent system (Planner/Actor/Verifier)
- Pydantic Function Calling schemas
- ChromaDB RAG integration
- Multi-sensor processing (Camera, Lidar, GPS, IMU)
- Safety constraint system
- Failure recovery & replanning
- Monitoring, logging, evaluation system

**Total Stories:** 12 (7 Epic 1 + 5 Epic 2)
**Test Coverage:** 200+ tests
**Status:** Production-ready ✅

### Epic 3: Advanced Real-time Control (In Progress 🚧)
**Detailed in:** [architecture-epic3.md](./architecture-epic3.md)

- Hybrid Reactive Controller (3-level decision: CRITICAL/MODERATE/NORMAL)
- Ollama integration for on-device AI (~680ms avg latency)
- FastAPI Web Control Server (REST + WebSocket)
- Environment-aware planning (indoor/outdoor/warehouse/hospital)
- React Web UI Dashboard (optional)

**Total Stories:** 6 (4 completed, 2 pending)
**Progress:** 67% complete
**Status:** Story 3.0-3.3 done ✅, Story 3.4-3.5 planned 📋

---

## Quick Navigation

### For Developers Starting Epic 1-2 Work
→ Go to [architecture-core.md](./architecture-core.md)
- Section 1: System Overview
- Section 2: Data Flow
- Section 5: Component Details (Agents, RAG, Sensors)

### For Developers Working on Epic 3
→ Go to [architecture-epic3.md](./architecture-epic3.md)
- Section 11.3: Hybrid Reactive Controller
- Section 11.4: FastAPI Web Server
- Section 11.5: Environment-Aware Planning

### For Understanding Design Decisions
→ Go to [architecture-core.md](./architecture-core.md)
- Section 4: Key Architectural Decisions (Why CrewAI? Why ChromaDB?)
- Section 6: Framework Generalizability

### For Testing & Deployment
→ Go to [architecture-core.md](./architecture-core.md)
- Section 7: Testing Infrastructure
- Section 8: Implementation Priorities

---

## Success Metrics

**Epic 1-2 (Core System):**
- Mission success rate: 90%+ ✅
- Planning time: <10s ✅
- Execution time: <60s ✅
- Replanning success: 80%+ ✅

**Epic 3 (Real-time Control):**
- Reactive check latency: <10ms (95th percentile)
- Ollama detour decision: <300ms (90th percentile)
- Emergency stop time: <50ms
- WebSocket latency: <100ms

---

## Document Change History

| Date | Version | Changes |
|------|---------|---------|
| 2025-10-29 | 1.0 | Initial architecture (Epic 1-2) |
| 2025-11-02 | 1.1 | Added Epic 3 architecture |
| 2025-11-03 | 2.0 | Split into 3 documents for better navigation |

---

**Navigation:**
- **Current:** Overview
- **Next:** [Core Architecture (Epic 1-2) →](./architecture-core.md)
- **Advanced:** [Epic 3 Architecture →](./architecture-epic3.md)
