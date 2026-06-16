# LLM 기반 Mobile Manipulator 제어 시스템

**과목:** LLM 로봇 제어
**제출일:** 2025-12-21
**프로젝트:** LLM_ROBOT_2 - Mobile Manipulator Extension

---

## 목차
1. [문제와 시나리오](#1-문제와-시나리오)
2. [시스템 아키텍처](#2-시스템-아키텍처)
3. [핵심 기법](#3-핵심-기법)
4. [데모](#4-데모)
5. [결과 및 지표](#5-결과-및-지표)
6. [한계와 개선 방향](#6-한계와-개선-방향)
7. [동적 물체 배치 (Supervisor API)](#7-동적-물체-배치-supervisor-api)

---

## 1. 문제와 시나리오

### 1.1 문제 정의

기존 모바일 로봇 제어 시스템에서는 이동(navigation)만 지원하며, 물체 조작(manipulation)을 위한 로봇 팔 제어가 불가능했다. 본 프로젝트는 **자연어 명령을 통해 모바일 매니퓰레이터(Mobile Manipulator)를 제어**하는 시스템을 구현한다.

### 1.2 목표

- Pioneer 3-DX 로봇에 2-DOF 로봇 팔 및 그리퍼 장착
- 한국어/영어 자연어 명령으로 팔 제어
- Pick & Place 시나리오 구현

### 1.3 시나리오: 재난 구조 물체 수거

```
시나리오: 재난 현장에서 중요 물품 수거

1. 로봇이 시작 위치(-3.8, -3.8)에서 대기
2. 사용자: "앞으로 1미터 이동해서 물체를 집어"
3. 로봇이 전진 → 팔 뻗기 → 그리퍼로 물체 집기
4. 사용자: "물체를 들고 출구로 이동해"
5. 로봇이 팔을 들어 올리고 목표 지점으로 이동
6. 사용자: "물체를 내려놓아"
7. 로봇이 팔을 내리고 그리퍼 열어 물체 방출
```

---

## 2. 시스템 아키텍처

### 2.1 전체 구조

```
┌─────────────────────────────────────────────────────────────────┐
│                     사용자 인터페이스                              │
│            (Web UI / CLI / Natural Language Input)               │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Mission Orchestrator                           │
│              (CrewAI Multi-Agent Coordinator)                    │
└──────┬───────────────────┬──────────────────────┬───────────────┘
       │                   │                      │
       ▼                   ▼                      ▼
┌──────────────┐   ┌──────────────┐      ┌──────────────┐
│   Planner    │   │    Actor     │      │   Verifier   │
│    Agent     │   │    Agent     │      │    Agent     │
│  (GPT-4o)    │   │ (GPT-4o-mini)│      │ (GPT-4o-mini)│
└──────────────┘   └──────────────┘      └──────────────┘
       │                   │                      │
       │                   ▼                      │
       │          ┌──────────────────────────────┐│
       │          │    Webots Robot Controller   ││
       │          │ ┌──────────┐ ┌─────────────┐ ││
       │          │ │ Motors   │ │ Arm Motors  │ ││
       │          │ │(L/R Wheel)│ │(Shoulder,   │ ││
       │          │ │          │ │ Elbow,      │ ││
       │          │ │          │ │ Gripper)    │ ││
       │          │ └──────────┘ └─────────────┘ ││
       │          └──────────────────────────────┘│
       │                                          │
       └──────────────────────────────────────────┘
```

### 2.2 핵심 컴포넌트

| 컴포넌트 | 역할 | 기술 |
|---------|------|------|
| PlannerAgent | 자연어 → 액션 플랜 변환 | GPT-4o, LLM Function Calling |
| ActorAgent | 액션 플랜 → 로봇 제어 실행 | Webots Python API |
| VerifierAgent | 미션 성공/실패 검증 | GPT-4o-mini |
| RobotAction Schema | 액션 타입 정의 및 검증 | Pydantic |

### 2.3 로봇 팔 구조 (Webots)

```
arm_base (Solid)
  └── arm_shoulder (HingeJoint, RotationalMotor)
       └── upper_arm (Solid)
            └── arm_elbow (HingeJoint, RotationalMotor)
                 └── forearm (Solid)
                      └── gripper_base (Solid)
                           ├── gripper_left (HingeJoint, RotationalMotor)
                           │    └── finger_left (Solid)
                           └── gripper_right (HingeJoint, RotationalMotor)
                                └── finger_right (Solid)
```

**모터 사양:**
- `arm_shoulder`: -90° ~ +90° (어깨 관절)
- `arm_elbow`: -115° ~ +115° (팔꿈치 관절)
- `gripper_left/right`: -0.5 ~ +0.5 rad (그리퍼 개폐)

---

## 3. 핵심 기법

### 3.1 LLM Function Calling

자연어 명령을 구조화된 액션으로 변환하기 위해 LLM Function Calling 기법을 사용한다.

```python
class ActionType(str, Enum):
    # 기존 모바일 액션
    MOVE = "move"
    ROTATE = "rotate"
    SCAN = "scan"
    STOP = "stop"
    WAIT = "wait"
    # 신규 매니퓰레이션 액션
    ARM_MOVE = "arm_move"    # 팔 관절 이동
    GRIP = "grip"            # 그리퍼 닫기
    RELEASE = "release"      # 그리퍼 열기
```

### 3.2 Pydantic 스키마 검증

액션 파라미터의 안전성과 유효성을 Pydantic으로 검증한다.

```python
class RobotAction(BaseModel):
    action: ActionType
    # 모바일 파라미터
    x: Optional[float] = Field(ge=-5.0, le=5.0)
    y: Optional[float] = Field(ge=-5.0, le=5.0)
    # 팔 파라미터
    shoulder_angle: Optional[float] = Field(ge=-90.0, le=90.0)
    elbow_angle: Optional[float] = Field(ge=-115.0, le=115.0)
    gripper_force: Optional[float] = Field(ge=0.0, le=1.0)
```

### 3.3 자연어 키워드 매핑

다국어(한국어/영어) 명령을 지원하기 위한 키워드 매핑:

| 한국어 | 영어 | 액션 |
|--------|------|------|
| "집다", "잡다", "픽업" | "pick up", "grab", "grasp" | GRIP |
| "놓다", "놓아줘", "내려놓다" | "release", "drop", "put down" | RELEASE |
| "팔 이동", "팔 움직여" | "move arm", "extend arm" | ARM_MOVE |

### 3.4 Multi-Agent 협업 (CrewAI)

```
User Command → PlannerAgent → [Action Plan]
                                    ↓
                              ActorAgent → [Execute]
                                    ↓
                            VerifierAgent → [Verify]
                                    ↓
                              Success/Retry
```

---

## 4. 데모

### 4.1 실행 방법

**Webots 시뮬레이션 시작:**
```bash
# Webots에서 rescue_robot.wbt 월드 열기
# 시뮬레이션 시작 (재생 버튼)
```

**Web UI 서버 시작:**
```bash
cd LLM_robot_2
python -m src.web.server
# http://localhost:8000 에서 Web UI 접속
```

**명령줄 데모 실행:**
```bash
# 기본 미션 실행
python -m src.main

# 팔 조작 데모 실행
python -m src.main --arm

# 전체 데모 실행
python -m src.main --all
```

### 4.2 데모 시나리오

| 단계 | 명령 (한국어) | 명령 (영어) | 예상 동작 |
|------|--------------|-------------|----------|
| 1 | "팔을 앞으로 뻗어" | "extend arm forward" | 어깨 45°, 팔꿈치 0° |
| 2 | "물체를 집어" | "grab the object" | 그리퍼 닫힘 |
| 3 | "팔을 위로 올려" | "raise arm up" | 어깨 -30°, 팔꿈치 30° |
| 4 | "앞으로 1미터 이동" | "move forward 1 meter" | 전진 이동 |
| 5 | "팔을 내리고 놓아줘" | "lower arm and release" | 팔 하강 + 그리퍼 열림 |

### 4.3 Pick & Place 복합 명령

```
명령: "물체를 집어서 앞으로 2미터 가서 내려놓아"

생성되는 액션 플랜:
1. ARM_MOVE (shoulder=45°, elbow=-30°)  - 집기 위치로 팔 이동
2. GRIP (force=0.5)                      - 물체 집기
3. ARM_MOVE (shoulder=0°, elbow=0°)     - 팔 들어올리기
4. MOVE (x=2, y=0, relative=true)        - 2미터 전진
5. ARM_MOVE (shoulder=45°, elbow=-30°)  - 놓기 위치로 팔 이동
6. RELEASE                               - 물체 놓기
```

---

## 5. 결과 및 지표

### 5.1 구현 결과

| 항목 | 상태 | 비고 |
|------|------|------|
| 2-DOF 로봇 팔 추가 | 완료 | Webots HingeJoint |
| 그리퍼 구현 | 완료 | 양손 그리퍼 |
| ARM_MOVE 액션 | 완료 | 어깨/팔꿈치 제어 |
| GRIP 액션 | 완료 | 힘 조절 가능 |
| RELEASE 액션 | 완료 | 그리퍼 열기 |
| 한국어 명령 지원 | 완료 | 키워드 매핑 |
| 영어 명령 지원 | 완료 | 키워드 매핑 |
| Pick & Place 시나리오 | 완료 | 복합 명령 지원 |

### 5.2 액션 타입별 파라미터

| 액션 | 필수 파라미터 | 옵션 파라미터 |
|------|--------------|--------------|
| ARM_MOVE | shoulder_angle 또는 elbow_angle | reason |
| GRIP | - | gripper_force (기본: 0.5) |
| RELEASE | - | reason |

### 5.3 시스템 성능

- **LLM 모델**: GPT-4o (Planner), GPT-4o-mini (Actor, Verifier)
- **응답 시간**: 약 2-5초 (자연어 → 액션 플랜 변환)
- **시뮬레이션 환경**: Webots R2025a, 10m x 10m 아레나

---

## 6. 한계와 개선 방향

### 6.1 현재 한계

1. **물리 시뮬레이션 한계**
   - 실제 물체 집기(grasping) 물리 검증 미흡
   - 충돌 감지 및 힘 피드백 미구현

2. **센서 제약**
   - 물체 인식을 위한 비전 시스템 미구현
   - 팔 끝단(end-effector) 위치 센싱 미구현

3. **동작 계획**
   - Inverse Kinematics (IK) 미구현
   - 관절 각도를 직접 지정해야 함

4. **안전성**
   - 팔 동작 중 충돌 감지 미구현
   - 작업 공간(workspace) 제한 검증 미흡

### 6.2 개선 방향

1. **비전 통합**
   ```python
   # 향후 구현 예시
   class ObjectDetector:
       def detect_object(self, camera_image) -> ObjectInfo:
           # YOLO 또는 vision LLM 활용
           pass
   ```

2. **Inverse Kinematics 적용**
   ```python
   # 목표 위치 기반 관절 각도 자동 계산
   def compute_ik(target_position: Tuple[float, float, float]) -> Dict:
       return {"shoulder_angle": ..., "elbow_angle": ...}
   ```

3. **힘 제어 및 피드백**
   - 그리퍼 토크 센서 추가
   - 적응형 gripping force 제어

4. **안전 기능 강화**
   - 팔 동작 경로 충돌 검사
   - 작업 공간 경계 검증
   - 비상 정지 기능

---

## 7. 동적 물체 배치 (Supervisor API)

### 7.1 개요

Webots Supervisor API를 활용하여 시뮬레이션 시작 시 물체를 랜덤하게 배치합니다. 이를 통해 매번 다른 시나리오에서 로봇의 적응 능력을 테스트할 수 있습니다.

### 7.2 구현 방식

```python
from controller import Supervisor

def initialize_pickup_object(supervisor: Supervisor) -> dict:
    """Supervisor API로 물체를 랜덤 위치에 배치"""
    # DEF 이름으로 노드 접근
    pickup_node = supervisor.getFromDef("PICKUP_OBJECT")

    # 유효한 랜덤 위치 생성 (장애물 회피)
    x, y, z = generate_random_position()

    # translation 필드 수정
    translation_field = pickup_node.getField("translation")
    translation_field.setSFVec3f([x, y, z])

    return {"x": x, "y": y, "z": z}
```

### 7.3 장애물 회피 알고리즘

```python
OBSTACLES = [
    {"x": -2.5, "y": 1.8, "sx": 0.6, "sy": 0.6},  # obstacle_1
    {"x": 1.2, "y": -2.3, "sx": 0.8, "sy": 0.4},  # obstacle_2
    # ... 모든 장애물 정의
]

def is_position_valid(x: float, y: float, margin: float = 0.3) -> bool:
    # 1. 아레나 경계 확인 (-4.5 ~ 4.5)
    # 2. 로봇 시작 위치와 충돌 확인
    # 3. 모든 장애물과 충돌 확인 (안전 마진 포함)
    return True/False
```

### 7.4 좌표 전달 흐름

```
시뮬레이션 시작
    ↓
Supervisor: 물체 랜덤 배치
    ↓
MissionOrchestrator 초기화 (dynamic_objects 전달)
    ↓
PlannerAgent: 프롬프트에 물체 좌표 포함
    ↓
LLM: "물체가 (2.15, -1.32)에 있습니다" 인식
    ↓
로봇: 해당 좌표로 이동 후 물체 집기
```

### 7.5 사용 예시

```
# 시뮬레이션 시작 시 로그
📦 Pickup object placed at: (2.15, -1.32, 0.025)

# LLM에게 전달되는 컨텍스트
**DYNAMIC OBJECTS IN ENVIRONMENT:**
- pickup_object: X=2.15m, Y=-1.32m (small orange cube - can be picked up)

# 자연어 명령 예시
"물체가 있는 곳으로 가서 집어와"
→ LLM이 좌표를 인식하고 MOVE + GRIP 액션 생성
```

---

## 부록: 파일 구조

```
LLM_robot_2/
├── worlds/
│   └── rescue_robot.wbt                # Webots 월드 (팔 + 물체 포함)
├── controllers/
│   └── rescue_robot_controller/
│       └── rescue_robot_controller.py  # Supervisor 기반 로봇 컨트롤러
├── src/
│   ├── agents/
│   │   ├── planner_agent.py            # 자연어 → 액션 플랜 (dynamic_objects 지원)
│   │   └── actor_agent.py              # 액션 실행 (팔 제어 포함)
│   ├── schemas/
│   │   └── robot_action.py             # ActionType, RobotAction
│   ├── orchestrator.py                 # Multi-Agent 조정 (dynamic_objects 전달)
│   ├── main.py                         # 데모 실행 진입점
│   └── web/
│       └── server.py                   # FastAPI 웹 서버
└── docs/
    └── LLM_Mobile_Manipulator_Report.md  # 본 보고서
```

---

## 참고 문헌

1. Webots User Guide - Robot Arm Tutorial
2. OpenAI Function Calling Documentation
3. CrewAI Multi-Agent Framework
4. Pydantic Data Validation

---

*본 보고서는 LLM_ROBOT_2 프로젝트의 Mobile Manipulator 확장 기능을 문서화한 것입니다.*
