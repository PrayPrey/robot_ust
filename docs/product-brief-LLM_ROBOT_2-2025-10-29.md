# Product Brief: LLM_ROBOT_2

**Date:** 2025-10-29
**Author:** BMad
**Status:** Draft for PM Review

---

## Executive Summary

LLM_ROBOT_2는 자연어 명령을 통해 로봇을 제어하는 LLM 기반 에이전트 시스템입니다. 사용자가 자연어로 미션을 지시하면, Multi-agent 시스템(Planner/Actor/Verifier)이 이를 분석하고 Webots 시뮬레이터에서 순차적 행동으로 실행합니다. 본 프로젝트는 중간고사 대체 과제로, LLM과 로봇 시뮬레이션의 통합을 통해 자율 로봇 제어의 새로운 패러다임을 제시합니다.

주요 목표는 6개 평가 항목에서 만점(5점)을 획득하는 것이며, RAG, Multi-agent, Function Calling, 다중 센서 활용을 통해 범용적이고 확장 가능한 시스템을 구현합니다.

---

## Problem Statement

**현재 상황:**

로봇 제어는 전통적으로 저수준 프로그래밍이나 복잡한 스크립팅을 요구하여, 비전문가의 접근성이 낮고 개발 시간이 오래 걸립니다. 특히 다음과 같은 문제가 존재합니다:

- **높은 진입 장벽**: 로봇 제어를 위해 로보틱스 전문 지식과 프로그래밍 기술 필요
- **유연성 부족**: 새로운 작업마다 코드를 다시 작성해야 함
- **복잡한 통합**: 센서 데이터 처리, 경로 계획, 행동 실행의 통합이 복잡
- **제한적인 자율성**: 실패 시 재계획 및 복구 능력 부족

**정량적 영향:**

- 전통적 방식: 간단한 작업도 수십 줄의 코드 필요
- 개발 시간: 새로운 시나리오마다 수시간~수일 소요
- 오류 복구: 수동 개입 필요

**왜 지금 해결해야 하는가:**

중간고사 대체 과제 마감(11월 3일)까지 5일 내에 평가 기준을 충족하는 시스템을 구현해야 하며, LLM 기술의 발전으로 자연어 기반 로봇 제어의 실현 가능성이 높아진 시점입니다.

---

## Proposed Solution

**핵심 접근:**

LLM을 중심으로 한 Multi-agent 아키텍처를 통해 자연어 명령을 로봇 행동으로 자동 변환하는 Agentic Robot Controller를 구현합니다.

**시스템 구성:**

1. **Planner Agent**: 자연어 미션을 분석하고 단계별 행동 계획 수립
2. **Actor Agent**: 계획된 행동을 Webots API 함수 호출로 변환 및 실행
3. **Verifier Agent**: 실행 결과 검증, 실패 시 재계획 트리거

**핵심 차별화:**

- **자연어 인터페이스**: 코드 없이 자연어로 로봇 제어
- **자율 재계획**: 실패 감지 시 자동으로 대안 계획 수립
- **다중 센서 융합**: 카메라, Lidar 등 여러 센서 데이터 통합 활용
- **RAG 기반 지식**: 로봇 능력, 환경 정보를 벡터 DB에서 검색하여 정확한 계획 수립
- **Function Calling**: LLM이 직접 로봇 제어 API 호출

**왜 성공할 것인가:**

- 최신 LLM의 강력한 추론 능력 활용
- Multi-agent 패턴으로 복잡도 관리
- Webots의 안정적인 시뮬레이션 환경
- 평가 기준에 최적화된 설계

---

## Target Users

### Primary User Segment

**프로필:**

- **대상**: 과제 평가자(교수님 및 조교)
- **배경**: 로보틱스 및 LLM 기술 전문가
- **평가 관점**: 기술 깊이, 구현 완성도, 혁신성

**현재 문제 해결 방식:**

- 학생들의 과제 제출물을 평가 기준표에 따라 채점
- 영상과 명세서를 통해 프로젝트 이해

**구체적 Pain Points:**

- 피상적 구현과 깊이 있는 구현 구별 필요
- 6개 평가 항목의 명확한 증거 확인 필요
- 5분 영상 내에서 핵심 기술 파악

**목표:**

- 기술적 완성도 높은 프로젝트 평가
- 평가 기준별 명확한 증거 확인
- 혁신적 접근 발견

### Secondary User Segment

**프로필:**

- **대상**: 프로젝트 개발자(본인)
- **목표**: 5일 내 만점 획득 가능한 시스템 구축
- **제약**: 시간 제한, 평가 항목 준수

**Pain Points:**

- 제한된 시간에 모든 평가 항목 만족
- 기술 깊이와 구현 속도의 균형
- 명세서 및 영상 제작 시간 확보

---

## Goals and Success Metrics

### Business Objectives

**학업 목표:**

- **중간고사 대체 과제 만점 획득**: 6개 항목 × 5점 = 30점 만점
- **기술 포트폴리오 강화**: LLM + Robotics 융합 경험
- **마감 준수**: 11월 3일 자정까지 제출 완료

### User Success Metrics

**평가자 관점:**

- **명확성**: 5분 영상으로 시스템 이해 가능
- **검증 가능성**: 각 평가 항목의 구현 증거 명확
- **재현 가능성**: 코드 실행으로 동일 결과 재현

**개발자 관점:**

- **개발 완료**: 11월 3일까지 모든 기능 구현
- **문서화 완료**: 명세서 1페이지 작성
- **영상 제작**: 5분 프레젠테이션 완성

### Key Performance Indicators (KPIs)

**평가 점수 (각 0-5점):**

1. **프로젝트 기획**: 5점 - 대규모 범용 기술 기획
2. **LLM 활용**: 5점 - 로컬/API 최적 선택, 트레이드오프 분석
3. **LLM 응용 기술**: 5점 - RAG + Function Calling + Multi-agent 통합
4. **시뮬레이터 활용**: 5점 - 로봇 및 환경 직접 구성, 센서/액추에이터 제어
5. **시뮬레이터 응용 기술**: 5점 - 다중 센서(카메라+Lidar) + 외부 데이터 + 노이즈 대응
6. **LLM 기반 제어 기술**: 5점 - Function Calling + Sequential Actions + 실패 복구 + 로깅

**기술 성능 지표:**

- **작업 성공률**: 90% 이상
- **평균 실행 시간**: 미션당 30초 이내
- **재계획 성공률**: 실패 시 80% 이상 복구

**보너스 항목:**

- 안전 제약 형식화 (충돌 회피)
- 비용/지연 벤치마크
- 자동 평가 스크립트
- 로컬 LLM 최적화 보고서

---

## Strategic Alignment and Financial Impact

### Financial Impact

**개발 투자:**

- **시간**: 5일 집중 개발
- **비용**: API 사용료 (예상 $10-20) 또는 로컬 LLM (무료)
- **ROI**: 학점 + 포트폴리오 가치

**비용 절감:**

- 로컬 LLM 사용 시 API 비용 0원
- 재사용 가능한 프레임워크 구축

### Company Objectives Alignment

**학업 목표 정렬:**

- 중간고사 대체 과제 완수
- LLM 및 로보틱스 학습 심화
- 실무 적용 가능한 기술 습득

### Strategic Initiatives

**기술 역량 강화:**

- Multi-agent 시스템 설계 경험
- RAG 및 LLM 통합 실습
- 로봇 시뮬레이션 전문성

**포트폴리오 구축:**

- GitHub 공개 프로젝트
- 기술 블로그 작성 소재
- 취업/대학원 지원 자료

---

## MVP Scope

### Core Features (Must Have)

**1. LLM 통합 (평가 항목 2, 3)**

- OpenAI API 또는 로컬 LLM (Ollama + Qwen/Gemma) 선택
- Function Calling 구현
- Multi-agent 시스템 (Planner/Actor/Verifier)
- RAG 시스템 (로봇 능력, 환경 지식)

**2. Webots 시뮬레이션 (평가 항목 4, 5)**

- 로봇 모델 구성 (예: 이동 로봇)
- 환경 설계 (장애물, 목표 지점)
- 다중 센서 통합 (카메라 + Lidar)
- 센서 노이즈 처리
- 외부 데이터 연동 (경로 CSV, 지도 JSON)

**3. 제어 시스템 (평가 항목 6)**

- Sequential Action 계획
- Function Calling으로 모터/센서 API 호출
- 실패 감지 및 재계획
- 행동 로깅 및 리플레이

**4. 안전 시스템 (보너스)**

- 충돌 회피 제약
- 속도 제한
- 안전 영역 정의

**5. 평가 및 문서화**

- 자동 평가 스크립트 (성공률, 시간 측정)
- 벤치마크 보고서
- 명세서 (1페이지)
- 5분 프레젠테이션 영상

### Out of Scope for MVP

**Phase 2 이후로 연기:**

- 실제 하드웨어 통합
- 복잡한 조작 작업 (picking, assembly)
- 다중 로봇 협업
- 실시간 음성 명령
- 웹 기반 UI
- 강화학습 통합

### MVP Success Criteria

**기능 완성:**

- [ ] 자연어 명령 입력 → 로봇 행동 실행 성공
- [ ] 3개 이상의 시나리오 테스트 (예: 이동, 물체 회피, 목표 도달)
- [ ] 실패 시 재계획 동작 확인
- [ ] 모든 평가 항목 증거 확보

**문서 완성:**

- [ ] 명세서 1페이지 작성
- [ ] 5분 영상 제작 (1920×1080, 30fps)
- [ ] 코드 정리 및 README 작성

**평가 준비:**

- [ ] 압축 파일 생성 (이름_학번.zip)
- [ ] 11월 3일 자정 전 제출 준비 완료

---

## Post-MVP Vision

### Phase 2 Features

**시스템 확장 (학기말 프로젝트 또는 개인 연구):**

- 실제 로봇 하드웨어 연동 (ROS2 통합)
- 복잡한 조작 작업 (물체 집기, 조립)
- 웹 기반 제어 대시보드
- 음성 명령 인터페이스

### Long-term Vision

**1-2년 후:**

- 범용 로봇 제어 플랫폼으로 발전
- 다양한 로봇 타입 지원 (드론, 로봇 팔, AGV)
- 오픈소스 커뮤니티 구축
- 논문 발표 또는 특허 출원

### Expansion Opportunities

- **교육 분야**: 로봇 교육용 툴킷
- **연구 분야**: LLM-Robotics 융합 연구 플랫폼
- **산업 분야**: 창고 자동화, 스마트 팩토리

---

## Technical Considerations

### Platform Requirements

**개발 환경:**

- OS: Windows/Linux/macOS
- Python: 3.8+
- Webots: R2023a 이상

**실행 환경:**

- CPU: Intel i5 이상 (로컬 LLM 시) 또는 인터넷 연결 (API)
- RAM: 8GB+ (로컬 LLM 시 16GB 권장)
- GPU: 선택사항 (로컬 LLM 가속)

### Technology Preferences

**필수 기술 (과제 요구사항):**

- **시뮬레이터**: Webots
- **언어**: Python 3.8+
- **RAG**: 벡터 DB 기반 지식 검색

**핵심 프레임워크 (Archon KB 기반 선정):**

**1. Multi-Agent 시스템: CrewAI ⭐ 최우선 추천**

- **선정 이유**:
  - 5일 프로젝트에 최적화된 개발 속도
  - Role-based agent 구조 (Planner/Actor/Verifier)
  - 자동 delegation 및 협업 기능 내장
  - Function Calling 자동 지원
  - LangGraph 대비 학습 곡선 낮음

- **대안**: LangGraph (복잡도 높음, 시간 부족 시 부적합)

**2. 데이터 검증: Pydantic (필수 추가)**

- **사용 목적**:
  - Function Calling Schema 정의 (평가 항목 6)
  - LLM Output Validation (hallucination 방지)
  - 구조화된 데이터 모델 (센서 데이터, 행동 계획)
  - Type safety 및 자동 문서화

**3. Vector DB: ChromaDB ⭐ 추천**

- **선정 이유**:
  - 설치 및 사용 간편 (`pip install chromadb`)
  - 로컬 실행 가능 (비용 0원)
  - 메타데이터 관리 우수
  - FAISS 대비 초보자 친화적

- **대안**: FAISS (더 복잡하지만 성능 우수)

**4. LLM 선택:**

- **OpenAI API (GPT-4o-mini)**: 빠르고 저렴, 안정적 ($10-20 예상)
- **Ollama + Qwen2.5 7B**: 무료, 로컬 실행, API 비용 0원

**5. 보너스 도구 (평가 점수 극대화):**

- **OpenLit**: LLM 호출 추적, 비용/지연 벤치마크 (보너스 항목)
- **Loguru**: 행동 로깅 및 리플레이 (평가 항목 6)
- **pytest**: 자동 평가 스크립트 (보너스 항목)

**최종 기술 스택 요약:**

```yaml
필수:
  - Webots: 로봇 시뮬레이터
  - Python: 3.8+

핵심:
  - CrewAI: Multi-agent 오케스트레이션
  - Pydantic: Schema 정의 및 검증
  - ChromaDB: RAG 벡터 DB

LLM:
  - OpenAI GPT-4o-mini (추천) 또는
  - Ollama + Qwen2.5 7B (무료)

보너스:
  - OpenLit: 모니터링 및 벤치마크
  - Loguru: 로깅
  - pytest: 자동 평가
```

**평가 항목별 기술 매핑:**

| 평가 항목 | 사용 기술 | 증거 제시 방법 |
|-----------|-----------|----------------|
| 1. 프로젝트 기획 | CrewAI Multi-agent 시스템 | 아키텍처 다이어그램, 범용성 설명 |
| 2. LLM 활용 | OpenAI API/Ollama 선택 분석 | 비용/지연/정확도 트레이드오프 표 |
| 3. LLM 응용 기술 | CrewAI + ChromaDB + Pydantic | 코드에서 3가지 기술 통합 시연 |
| 4. 시뮬레이터 활용 | Webots Python API | 로봇/환경 구성 코드, 제어 인터페이스 |
| 5. 시뮬레이터 응용 | 다중 센서 + JSON 외부 데이터 | 센서 노이즈 처리 코드, 데이터 통합 |
| 6. LLM 제어 기술 | Pydantic Function Calling + Loguru | Sequential Plan + 재계획 로직 + 로그 |
| 보너스 | OpenLit + pytest | 벤치마크 리포트, 자동 평가 스크립트 |

### Architecture Considerations

**시스템 아키텍처:**

```
[자연어 입력]
    ↓
[CrewAI Crew]
    ├─ [Planner Agent] ← [ChromaDB RAG: 로봇 능력, 환경 지식]
    │      ↓ (Pydantic Schema)
    ├─ [Actor Agent] → [Webots API: Function Calls]
    │      ↓ (센서 데이터)
    └─ [Verifier Agent] → [실패 감지] → [재계획 트리거]
         ↓
    [OpenLit 모니터링] + [Loguru 로깅]
         ↓
    [Success/Failure Report]
```

**데이터 흐름:**

1. **자연어 입력** → CrewAI Crew 시작
2. **Planner Agent** → ChromaDB에서 로봇 능력 검색 (RAG)
3. **Planner** → Pydantic Schema로 검증된 Sequential Plan 생성
4. **Actor Agent** → Pydantic Function Calling으로 Webots API 호출
5. **Verifier Agent** → 센서 데이터 분석 및 성공/실패 판단
6. **실패 시** → Planner에게 재계획 요청 (자동 delegation)
7. **전 과정** → Loguru 로깅, OpenLit 모니터링

**주요 컴포넌트 (구현 우선순위):**

**Priority 1 (필수):**

- **CrewAI Agents**: Planner, Actor, Verifier 정의
- **Pydantic Models**: RobotAction, SensorData, MissionPlan
- **Webots Controller**: Python API 래퍼
- **ChromaDB**: 로봇 능력 및 제약 저장

**Priority 2 (핵심):**

- **RAG Pipeline**: ChromaDB 검색 로직
- **Function Calling**: Pydantic → Webots API 변환
- **실패 감지**: 센서 데이터 기반 검증
- **재계획 로직**: Verifier → Planner 피드백 루프

**Priority 3 (보너스):**

- **OpenLit 통합**: 자동 모니터링
- **Loguru 설정**: JSON 형식 로깅
- **pytest 스크립트**: 자동 평가 및 벤치마크

**코드 예시 (CrewAI + Pydantic):**

```python
from crewai import Agent, Task, Crew
from pydantic import BaseModel

# Pydantic Schema
class RobotAction(BaseModel):
    action: str  # "move", "rotate", "scan"
    parameters: dict
    safety_check: bool = True

# CrewAI Agents
planner = Agent(
    role="Mission Planner",
    goal="자연어를 로봇 계획으로 변환",
    allow_delegation=True
)

actor = Agent(
    role="Robot Controller",
    goal="계획 실행",
    tools=[webots_tool]
)

verifier = Agent(
    role="Execution Verifier",
    goal="결과 검증 및 재계획"
)

crew = Crew(
    agents=[planner, actor, verifier],
    tasks=[mission_task]
)
```

**기술 선정 근거 (Archon KB):**

- **CrewAI**: KB 내 다수의 multi-agent 예제 확인, 개발 속도 최적화
- **Pydantic**: Function Calling 및 validation 표준
- **ChromaDB**: 간편한 벡터 DB, 5일 프로젝트 적합
- **Webots**: KB 내 완전한 Python API 문서 확보

---

## Constraints and Assumptions

### Constraints

**시간 제약:**

- 마감: 11월 3일 자정 (5일)
- 개발 가능 시간: 약 40-50시간

**기술 제약:**

- Webots 필수 사용
- Python 기반 (Webots Python API)
- 시뮬레이션 환경 (실제 하드웨어 X)

**리소스 제약:**

- 1인 개발
- API 비용 제한 ($20 이내)
- 로컬 컴퓨팅 리소스

**평가 제약:**

- 5분 영상 제한
- 1페이지 명세서
- 6개 평가 항목 모두 충족 필요

### Key Assumptions

**기술 가정:**

- LLM이 Function Calling을 안정적으로 수행 가능
- Webots API가 충분히 문서화되어 있음
- RAG로 로봇 능력 검색이 효과적

**시나리오 가정:**

- 시뮬레이션 환경에서 충분한 테스트 가능
- 3-5개 시나리오로 시스템 검증 가능

**평가 가정:**

- 명세서와 영상으로 구현 증명 가능
- 자동 평가 스크립트가 신뢰성 입증

---

## Risks and Open Questions

### Key Risks

**기술 리스크:**

| 리스크 | 영향 | 가능성 | 대응 방안 |
|--------|------|--------|-----------|
| LLM Hallucination (잘못된 함수 호출) | 높음 | 중간 | Verifier Agent로 검증, RAG로 정확한 능력 제공 |
| API 비용 초과 | 중간 | 낮음 | 로컬 LLM 대안 준비 |
| Webots 통합 복잡도 | 높음 | 중간 | 간단한 로봇 모델 선택, 초기 프로토타입 |
| 시간 부족 | 높음 | 중간 | 우선순위 명확화, MVP 범위 엄격 관리 |

**평가 리스크:**

| 리스크 | 영향 | 가능성 | 대응 방안 |
|--------|------|--------|-----------|
| 증거 부족 판정 | 높음 | 낮음 | 명세서에 명확한 증거 표시, 영상에 모든 항목 시연 |
| 영상 시간 초과 | 중간 | 중간 | 스크립트 작성, 리허설 |

### Open Questions

**기술 결정:**

- [ ] OpenAI API vs 로컬 LLM? (비용 vs 성능)
- [ ] LangChain vs LlamaIndex? (개발 속도)
- [ ] 어떤 Webots 로봇 모델? (복잡도)
- [ ] RAG DB 크기? (얼마나 많은 지식 필요?)

**구현 세부사항:**

- [ ] Function Calling 스키마 설계?
- [ ] 실패 감지 기준? (센서 임계값)
- [ ] 재계획 횟수 제한?
- [ ] 로깅 형식? (JSON, CSV?)

### Areas Needing Further Research

**단기 (개발 전):**

- Webots Python API 문서 숙지
- LangChain Multi-agent 예제 분석
- Function Calling 베스트 프랙티스

**중기 (개발 중):**

- 센서 노이즈 모델링 방법
- 충돌 회피 알고리즘
- 벤치마크 메트릭 정의

---

## Appendices

### A. Research Summary

**평가 기준 분석:**

6개 평가 항목의 만점 기준을 충족하기 위해 다음 기술 조합 필요:

- 대규모 범용 기획
- 로컬/API LLM 선택 최적화
- RAG + Function Calling + Multi-agent
- 로봇 및 환경 직접 구성
- 다중 센서 + 외부 데이터 + 노이즈 대응
- Sequential Actions + 실패 복구 + 로깅

**기술 스택 조사:**

- Track A (Webots + Python + Ollama): 빠른 시작, 비용 절감
- Track B (Isaac Sim): 고급 물리, 하드웨어 요구 높음 → 제외
- Track C (PyBullet + ROS2): 확장성 우수하나 복잡도 높음 → 제외

**결론**: Track A 선택 (Webots + Python + Ollama/OpenAI)

### B. Stakeholder Input

**교수님 요구사항 (과제 명세):**

- LLM + Robot Simulator 결합
- 자연어 → 절차적 행동
- 6개 평가 항목 충족
- 5분 영상 + 1페이지 명세서 + 코드 제출

**개인 목표:**

- 만점 획득
- 포트폴리오 강화
- 재사용 가능한 프레임워크 구축

### C. References

**과제 자료:**

- 중간고사 대체 프로젝트 평가 기준표

**기술 문서:**

- Webots Documentation: https://cyberbotics.com/doc/
- LangChain Documentation: https://python.langchain.com/
- OpenAI Function Calling: https://platform.openai.com/docs/guides/function-calling
- Ollama: https://ollama.ai/

**관련 연구:**

- LLM-based Robot Control (arxiv 검색 예정)
- Multi-agent Systems for Robotics

---

_This Product Brief serves as the foundational input for Product Requirements Document (PRD) creation._

_Next Steps: Handoff to Product Manager for PRD development using the `workflow prd` command._
