# LLM_ROBOT_2 - 재난 구조 로봇 Architecture

**Project:** LLM_ROBOT_2 - Search & Rescue Robot
**Author:** BMad
**Date:** 2025-10-29
**Version:** 1.0

---

## Executive Summary

**범용 LLM 기반 로봇 제어 프레임워크 (Generic LLM-powered Robot Control Framework)**

본 아키텍처는 자연어 명령으로 다양한 로봇을 제어할 수 있는 **도메인 중립적** 플랫폼을 정의합니다. CrewAI Multi-agent 시스템(Planner/Actor/Verifier), Pydantic Function Calling, ChromaDB RAG를 결합하여 **로봇 타입, 도메인, 작업에 무관하게** 적용 가능한 범용 아키텍처를 제시합니다.

**첫 번째 구현 유스케이스**: 재난 구조 로봇 (Search & Rescue Robot)으로 프레임워크를 검증합니다. 이는 재난 현장에서 자연어 명령을 통해 생존자를 자율 탐색하는 시스템이며, 동일한 아키텍처는 창고 자동화, 드론 제어, 로봇 팔 조작 등 다양한 도메인에 확장 가능합니다.

---

## 1. System Overview

### 1.1 High-Level Architecture

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

### 1.2 Core Components

| 컴포넌트 | 기술 스택 | 역할 |
|----------|-----------|------|
| **Planner Agent** | CrewAI + OpenAI GPT-4o-mini | 자연어 미션 → 순차 행동 계획 생성 |
| **Actor Agent** | CrewAI + Webots Python API | 계획 실행 → 로봇 제어 |
| **Verifier Agent** | CrewAI + 센서 데이터 분석 | 실행 검증, 실패 시 재계획 트리거 |
| **RAG System** | ChromaDB + OpenAI Embeddings | 건물 구조, 안전 프로토콜 검색 |
| **Data Models** | Pydantic | Function Calling Schema, 검증 |
| **Simulator** | Webots R2023a + Python Controller | 재난 환경 시뮬레이션 |
| **Monitoring** | OpenLit + Loguru | LLM 추적, 행동 로깅 |

---

## 2. Data Flow

### 2.1 Mission Execution Flow

```
1. 구조대 명령 입력
   │
   ▼
2. Planner Agent
   ├─ ChromaDB RAG: 건물 구조 검색
   ├─ 안전 프로토콜 검색
   └─ MissionPlan 생성 (Pydantic Schema)
      [{action: "scan_structure", ...},
       {action: "navigate_safe_path", ...},
       {action: "detect_survivor", ...}]
   │
   ▼
3. Actor Agent
   ├─ RobotAction (Pydantic) 검증
   ├─ Webots API 호출 (move, scan, detect)
   └─ SensorData 수집 (카메라, Lidar, 열 감지)
   │
   ▼
4. Verifier Agent
   ├─ 경로 안전성 검증 (Lidar → 붕괴 위험 감지)
   ├─ 생존자 발견 여부 확인
   └─ 성공/실패 판단
      ├─ 성공 → 위치 보고
      ├─ 경로 차단 → Planner에게 재계획 요청 (delegation)
      └─ 위험 감지 → 즉시 중단 + 보고
```

### 2.2 Replanning Flow

```
실패 감지 (Verifier)
   │
   ▼
재계획 트리거 (최대 3회)
   │
   ▼
Planner에게 컨텍스트 전달
   - 실패 원인 (경로 차단, 위험 구역 등)
   - 현재 로봇 위치
   - 환경 상태 (Lidar 데이터)
   │
   ▼
Planner가 대안 경로 생성
   - RAG에서 우회 경로 패턴 검색
   - 안전 제약 재확인
   │
   ▼
Actor 재실행
```

---

## 3. Technology Stack

### 3.1 Core Technologies

**Multi-Agent Framework:**
- **CrewAI** (최우선 선택)
  - Role-based agents (Planner/Actor/Verifier)
  - 자동 delegation (Verifier → Planner)
  - 빠른 개발 속도 (5일 프로젝트 최적)

**Data Validation:**
- **Pydantic 2.x**
  - Function Calling Schema 정의
  - LLM output validation
  - Type safety

**RAG System:**
- **ChromaDB**
  - 로컬 벡터 DB
  - 건물 구조, 안전 프로토콜 저장
  - OpenAI Embeddings

**LLM:**
- **OpenAI GPT-4o-mini** (추천)
  - 빠른 응답, 저렴한 비용
  - Function Calling 지원
- 대안: **Ollama + Qwen2.5 7B** (무료)

**Simulator:**
- **Webots R2023a**
  - Python Controller
  - 재난 환경 구성 (붕괴된 건물, 잔해, 장애물)
  - 센서: 카메라, Lidar, (시뮬) 열 감지

**Monitoring:**
- **OpenLit**: LLM 호출 비용/지연 추적
- **Loguru**: JSON 형식 행동 로깅

### 3.2 Data Models (Pydantic Schemas)

```python
# Mission Planning
class RobotAction(BaseModel):
    action: str  # "scan_structure", "navigate", "detect_survivor"
    parameters: dict
    safety_check: bool = True
    priority: int = 1  # 1=일반, 5=긴급

class MissionPlan(BaseModel):
    mission_id: str
    steps: List[RobotAction]
    estimated_time: float
    risk_level: str  # "low", "medium", "high"

# Execution
class SensorData(BaseModel):
    camera_data: Optional[dict]  # 생존자 감지
    lidar_data: dict  # 구조 안정성, 장애물
    thermal_data: Optional[dict]  # 열 신호
    timestamp: datetime

class MissionResult(BaseModel):
    success: bool
    survivor_found: bool
    survivor_location: Optional[tuple]
    message: str
    execution_log: List[dict]
    replanning_count: int
```

---

## 4. Key Architectural Decisions

### 4.1 Why CrewAI over LangGraph?

| 항목 | CrewAI | LangGraph |
|------|--------|-----------|
| 개발 속도 | 🚀 매우 빠름 | 🐢 느림 |
| Role-based | ✅ 내장 | ❌ 수동 구현 |
| Delegation | ✅ 자동 | ❌ 수동 구현 |
| **5일 프로젝트** | ✅ 최적 | ❌ 부적합 |

**결정**: CrewAI 선택 (개발 속도 최우선)

### 4.2 Why ChromaDB over FAISS?

| 항목 | ChromaDB | FAISS |
|------|----------|-------|
| 설치 | 1줄 | 복잡 |
| 사용 난이도 | 쉬움 | 어려움 |
| 메타데이터 | 풍부 | 제한적 |

**결정**: ChromaDB (초보자 친화적, 빠른 구현)

### 4.3 Safety-First Design

**안전 제약 우선순위:**

1. **즉시 중단 조건**:
   - Lidar가 붕괴 위험 감지 (임계값 초과)
   - 안전 영역 벗어남
   - 배터리/통신 임계값 이하

2. **재계획 조건**:
   - 경로 차단 (장애물)
   - 목표 미도달 (시간 초과)

3. **모든 행동에 safety_check 필수**:
   ```python
   if not action.safety_check:
       raise SafetyViolationError()
   ```

---

## 5. Component Details

### 5.1 ChromaDB Knowledge Base

**저장 데이터:**

1. **건물 구조 정보**:
   ```
   "3층 동쪽은 회의실, 내진 구조, 비상구 2개"
   "3층 서쪽은 붕괴 위험, 접근 금지"
   ```

2. **안전 프로토콜**:
   ```
   "장애물 0.5m 이내 접근 금지"
   "붕괴 위험 징후: Lidar 신호 불규칙"
   ```

3. **생존자 탐지 패턴**:
   ```
   "열 신호 36-37도 → 생존자 가능성 높음"
   "움직임 감지 + 음향 → 즉시 확인"
   ```

### 5.2 Webots Environment

**재난 환경 구성:**

- 3층 건물 (일부 붕괴)
- 잔해 및 장애물 배치
- 안전 구역 / 위험 구역 표시
- 생존자 더미 객체 (열 신호 시뮬)

**로봇 모델:**
- Pioneer 3-DX 또는 TurtleBot
- 센서: 카메라, Lidar, (시뮬) 열 감지

**외부 데이터:**
- `building_layout.json`: 건물 평면도
- `safe_zones.csv`: 안전/위험 구역 좌표

---

## 6. Framework Generalizability (범용성)

### 6.1 Domain-Neutral Design

**핵심 원칙**: 본 아키텍처는 **재난 구조에 특화되지 않고**, 어떤 로봇, 어떤 작업에도 적용 가능하도록 설계되었습니다.

**도메인 독립성을 보장하는 설계 요소:**

| 컴포넌트 | 범용성 메커니즘 | 확장 방법 |
|----------|----------------|-----------|
| **Planner Agent** | 도메인 지식을 RAG에서 동적 로드 | Role/Goal 재정의만으로 다른 도메인 적용 |
| **Actor Agent** | Pydantic Schema로 로봇 API 추상화 | RobotAction Schema 확장으로 다른 로봇 지원 |
| **Verifier Agent** | 성공 기준을 MissionPlan에서 정의 | 검증 로직을 작업별로 커스터마이징 |
| **ChromaDB RAG** | 도메인별 지식을 컬렉션으로 분리 | 새 컬렉션 추가만으로 도메인 확장 |

### 6.2 Extension Scenarios (확장 시나리오)

**Scenario 1: 창고 자동화 (Warehouse Automation)**

```python
# 동일한 아키텍처, 다른 지식만 주입
planner = Agent(
    role="Warehouse Mission Planner",  # Role만 변경
    goal="자연어 물류 명령을 로봇 작업으로 변환",
    # RAG에서 "창고 레이아웃", "재고 위치" 검색
)

# RobotAction 확장
class WarehouseAction(RobotAction):
    action: str  # "pick", "place", "navigate_to_bin"
    bin_id: Optional[str]
    item_id: Optional[str]
```

**Scenario 2: 드론 감시 (Drone Surveillance)**

```python
planner = Agent(
    role="Aerial Surveillance Planner",
    goal="자연어 감시 미션을 드론 비행 계획으로 변환",
    # RAG에서 "비행 규제", "감시 구역" 검색
)

class DroneAction(RobotAction):
    action: str  # "takeoff", "hover", "scan_area", "land"
    altitude: Optional[float]
    flight_path: Optional[List[tuple]]
```

**Scenario 3: 로봇 팔 조립 (Robot Arm Assembly)**

```python
planner = Agent(
    role="Assembly Task Planner",
    goal="자연어 조립 명령을 로봇 팔 동작으로 변환",
    # RAG에서 "부품 정보", "조립 순서" 검색
)

class ArmAction(RobotAction):
    action: str  # "grasp", "move_to", "release"
    joint_angles: Optional[List[float]]
    end_effector_pose: Optional[dict]
```

### 6.3 Scalability Metrics

**프레임워크 재사용률 예측:**

- **재사용 가능 코드**: 80% (Planner/Actor/Verifier 로직)
- **도메인 특화 코드**: 20% (RobotAction Schema, RAG 지식)
- **새 도메인 추가 시간**: 1-2일 (RAG 구축 + Schema 정의)

**검증 전략:**

1. **Phase 1 (현재)**: 재난 구조 로봇 - 프레임워크 검증
2. **Phase 2 (향후 3개월)**: 드론 또는 AGV - 범용성 실증
3. **Phase 3 (향후 1년)**: 오픈소스 공개 - 커뮤니티 다양한 도메인 적용

---

## 7. Implementation Priorities

### Priority 1 (Epic 1 - Foundation)

1. CrewAI Agents 구현 (Planner, Actor, Verifier)
2. Pydantic Schemas 정의
3. Webots 재난 환경 구성
4. 기본 미션 End-to-End (전진, 스캔)

### Priority 2 (Epic 2 - Advanced)

1. ChromaDB RAG 통합
2. 다중 센서 처리
3. 안전 제약 시스템
4. 실패 복구 및 재계획

### Priority 3 (최종 제출)

1. OpenLit + Loguru 로깅
2. pytest 자동 평가
3. 벤치마크 리포트
4. 명세서 + 영상

---

## 8. Risk Mitigation

| 리스크 | 영향 | 대응 방안 |
|--------|------|-----------|
| LLM Hallucination | 높음 | Pydantic 검증 + Verifier Agent |
| Webots 통합 복잡도 | 높음 | 간단한 로봇 모델 선택 |
| 시간 부족 (5일) | 높음 | MVP 범위 엄격 관리, Epic 우선순위 |
| API 비용 초과 | 중간 | Ollama 로컬 LLM 대안 준비 |

---

## 9. Success Metrics

**기술 성능:**
- 미션 성공률: 90% 이상
- 계획 수립 시간: 10초 이내
- 실행 시간: 60초 이내
- 재계획 성공률: 80% 이상

**평가 점수:**
- 6개 항목 × 5점 = 30점 만점 목표

---

## Appendix A: File Structure

```
llm_robot_2/
├── src/
│   ├── agents/
│   │   ├── planner.py      # Planner Agent
│   │   ├── actor.py        # Actor Agent
│   │   └── verifier.py     # Verifier Agent
│   ├── schemas/
│   │   └── models.py       # Pydantic Schemas
│   ├── rag/
│   │   └── knowledge_base.py  # ChromaDB 관리
│   ├── webots_controller/
│   │   └── robot_controller.py  # Webots API 래퍼
│   └── main.py             # Entry point
├── tests/
│   └── test_*.py           # pytest
├── data/
│   ├── building_layout.json
│   └── safe_zones.csv
├── logs/
├── docs/
│   ├── PRD.md
│   ├── epics.md
│   └── architecture.md     # 이 문서
└── requirements.txt
```

---

## Appendix B: API Reference

### CrewAI Agents

```python
from crewai import Agent, Task, Crew

planner = Agent(
    role="Search & Rescue Mission Planner",
    goal="자연어 구조 미션을 안전하고 효율적인 행동 계획으로 변환",
    backstory="재난 구조 전문가로 건물 구조와 안전 프로토콜에 정통",
    allow_delegation=True
)

actor = Agent(
    role="Robot Controller",
    goal="계획된 행동을 Webots에서 안전하게 실행",
    tools=[webots_move_tool, webots_scan_tool, webots_detect_tool]
)

verifier = Agent(
    role="Mission Verifier",
    goal="실행 결과 검증 및 안전성 확인",
    allow_delegation=True  # 실패 시 Planner에게 재계획 요청
)

crew = Crew(
    agents=[planner, actor, verifier],
    tasks=[rescue_mission_task],
    verbose=True
)
```

---

**Architecture Document Complete**

이 아키텍처는 5일 타임라인에 최적화되어 있으며, 모든 평가 항목을 충족하도록 설계되었습니다.
