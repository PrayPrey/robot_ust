# Webots 시뮬레이션 + 웹 자연어 제어 완벽 가이드

**LLM_ROBOT_2 프로젝트 - 웹 브라우저에서 자연어로 로봇 제어하기**

이 가이드는 Webots 시뮬레이터에서 로봇을 실행하고, 웹 브라우저에서 한국어/영어 자연어 명령으로 제어하는 전체 과정을 안내합니다.

---

## 📋 목차

1. [시스템 개요](#시스템-개요)
2. [사전 준비](#사전-준비)
3. [Quick Start (5분 시작)](#quick-start-5분-시작)
4. [상세 실행 가이드](#상세-실행-가이드)
5. [자연어 명령 예제](#자연어-명령-예제)
6. [웹 UI 사용법](#웹-ui-사용법)
7. [문제 해결](#문제-해결)
8. [고급 기능](#고급-기능)

---

## 🤖 시스템 개요

### 전체 아키텍처

```
┌──────────────────────┐
│   웹 브라우저 (사용자) │
│  http://localhost:8000│
└──────────┬───────────┘
           │ 자연어 명령: "동쪽으로 3미터 이동"
           │ WebSocket 양방향 통신 (10Hz)
           ▼
┌──────────────────────────────┐
│   FastAPI 웹 서버             │
│  - REST API 엔드포인트        │
│  - WebSocket 실시간 통신      │
│  - 10Hz 상태 브로드캐스팅     │
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────────┐
│   MissionOrchestrator         │
│  - 한국어/영어 명령 파싱      │
│  - 멀티 에이전트 조율         │
│  - ChromaDB RAG 통합          │
└──────────┬───────────────────┘
           │
    ┌──────┴───────┬─────────────┬──────────┐
    ▼              ▼             ▼          ▼
┌─────────┐  ┌─────────┐  ┌──────────┐  ┌──────────┐
│Planner  │  │ Actor   │  │ Verifier │  │ Reactive │
│ Agent   │  │ Agent   │  │  Agent   │  │Controller│
└─────────┘  └────┬────┘  └──────────┘  └──────────┘
                  │
                  ▼
         ┌────────────────┐
         │ Webots Simulator│
         │  Pioneer 3-DX   │
         │  10m×10m World  │
         └────────────────┘
```

### 주요 기능

- ✅ **자연어 명령 지원**: 한국어/영어로 로봇 제어
- ✅ **실시간 모니터링**: 10Hz (100ms) 상태 업데이트
- ✅ **양방향 통신**: WebSocket 기반 실시간 통신
- ✅ **멀티 에이전트**: CrewAI Planner/Actor/Verifier
- ✅ **반응형 제어**: Ollama 기반 장애물 회피
- ✅ **안전 제약**: 자동 안전 검증 및 긴급 정지

---

## 📦 사전 준비

### 1. 필수 소프트웨어 설치

#### ① Webots 시뮬레이터 (R2023b+)
```bash
# Windows: https://cyberbotics.com/ 에서 설치
# 설치 경로 예: C:\Program Files\Webots

# 환경 변수 설정 (선택사항)
setx WEBOTS_PATH "C:\Program Files\Webots"
```

#### ② Python 3.10+ 및 가상환경
```bash
# Python 버전 확인
python --version  # Python 3.10 이상 필요

# 가상환경 생성 (프로젝트 루트에서)
python -m venv venv

# 가상환경 활성화 (Windows)
venv\Scripts\activate

# 가상환경 활성화 (Linux/Mac)
source venv/bin/activate
```

#### ③ Ollama (반응형 제어용)
```bash
# Windows: https://ollama.com/download 에서 설치

# Linux/Mac:
curl -fsSL https://ollama.com/install.sh | sh

# tinyllama 모델 다운로드 (~600MB)
ollama pull tinyllama

# Ollama 서비스 확인
ollama list  # tinyllama가 있어야 함
```

### 2. 프로젝트 Dependencies 설치

```bash
# 프로젝트 루트 디렉토리로 이동
cd C:\Users\OWNER\Desktop\Woo_Yoon_Kyu\UST_수업\LLM_robot_2

# 가상환경 활성화
venv\Scripts\activate

# 모든 dependencies 설치
pip install -r requirements.txt

# 주요 패키지:
# - crewai (멀티 에이전트)
# - fastapi, uvicorn (웹 서버)
# - websockets (실시간 통신)
# - chromadb (RAG)
# - ollama (반응형 제어)
```

### 3. 환경 변수 설정

```bash
# .env 파일 생성 (프로젝트 루트)
# Windows:
copy .env.template .env

# Linux/Mac:
cp .env.template .env
```

`.env` 파일 편집:
```ini
# OpenAI API Key (필수)
OPENAI_API_KEY=sk-your-api-key-here

# Webots 경로 (선택사항)
WEBOTS_PATH=C:\Program Files\Webots

# 웹 서버 설정
SERVER_HOST=127.0.0.1
SERVER_PORT=8000

# Ollama 설정
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=tinyllama
```

---

## 🚀 Quick Start (5분 시작)

### Step 1: Ollama 시작 (백그라운드)

```bash
# Windows: Ollama가 자동으로 백그라운드 실행됨 (설치 후)
# 수동 시작 필요 시:
ollama serve

# 새 터미널에서 확인:
curl http://localhost:11434/api/tags
```

### Step 2: Webots 시뮬레이션 시작

```bash
# Webots 실행
"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe"

# Webots GUI에서:
# File → Open World → 프로젝트 경로/worlds/rescue_robot.wbt
```

**중요:** Webots 월드 파일(`rescue_robot.wbt`)을 열면 시뮬레이션이 자동으로 일시 정지 상태로 시작됩니다.

### Step 3: 웹 서버 시작

**새 터미널 열기:**

```bash
# 프로젝트 루트로 이동
cd C:\Users\OWNER\Desktop\Woo_Yoon_Kyu\UST_수업\LLM_robot_2

# 가상환경 활성화
BMAD-METHOD\venv\Scripts\activate

# FastAPI 웹 서버 시작
uvicorn src.web.server:app --reload --host 127.0.0.1 --port 8000
```

**서버 시작 확인:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### Step 4: 웹 브라우저에서 제어

```bash
# 브라우저에서 열기
http://localhost:8000
```

**첫 화면:**
- 로봇 위치 표시 (X, Y 좌표)
- 센서 상태 (GPS, IMU, Lidar, Camera)
- 자연어 명령 입력 창
- 실시간 로그 표시

**테스트 명령어 입력:**
```
동쪽으로 3미터 이동
```

**제출 버튼 클릭** → 로봇이 움직입니다! 🎉

---

## 📖 상세 실행 가이드

### 1단계: Webots 시뮬레이션 설정

#### Webots 월드 파일 구조

```
worlds/
└── rescue_robot.wbt       # 메인 시뮬레이션 월드 (재난 구조 로봇)
    ├── Pioneer3dx Robot   # 로봇 모델
    ├── GPS Sensor         # 위치 센서 (64ms 샘플링)
    ├── InertialUnit       # IMU (64ms 샘플링)
    ├── Lidar              # 512포인트 Lidar
    ├── Camera             # 640×480 카메라
    └── 10m×10m Arena      # 작동 영역
```

#### Webots 실행 옵션

**Option A: GUI에서 실행 (권장)**
```bash
# Webots 실행
webots.exe

# 메뉴: File → Open World
# 선택: LLM_robot_2/worlds/rescue_robot.wbt

# 시뮬레이션 시작: 재생 버튼 (▶)
```

**Option B: 명령줄에서 실행**
```bash
# 백그라운드로 Webots 실행
webots --mode=pause worlds/rescue_robot.wbt

# 시뮬레이션 자동 시작
webots --mode=run worlds/rescue_robot.wbt
```

#### 로봇 초기 상태 확인

Webots가 실행되면:
- ✅ 로봇이 원점 (0, 0) 근처에 배치됨
- ✅ 센서들이 활성화됨 (GPS, IMU, Lidar, Camera)
- ✅ Python 컨트롤러가 대기 상태

### 2단계: Python 컨트롤러 실행 (Option A)

**Webots 내장 컨트롤러로 실행:**

```python
# controllers/robot_controller/robot_controller.py
from controller import Robot
from src.orchestrator import MissionOrchestrator
from src.web import set_orchestrator
import os

# Webots Robot 초기화
robot = Robot()
timestep = int(robot.getBasicTimeStep())  # 64ms

# Orchestrator 생성
orchestrator = MissionOrchestrator(
    robot=robot,
    openai_api_key=os.getenv("OPENAI_API_KEY")
)

# 웹 서버에 Orchestrator 등록
set_orchestrator(orchestrator)

print("✅ Robot controller ready. Waiting for web commands...")

# Webots 시뮬레이션 루프
while robot.step(timestep) != -1:
    # 웹에서 명령 대기
    pass
```

### 3단계: 웹 서버 실행 (독립 프로세스)

**별도 터미널에서 실행:**

```bash
# 터미널 1: Webots 실행 중
# 터미널 2: 웹 서버 실행

cd LLM_robot_2
venv\Scripts\activate
uvicorn src.web.server:app --reload --host 127.0.0.1 --port 8000
```

**서버 엔드포인트:**
- 웹 UI: http://localhost:8000
- API 문서: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

**서버 시작 로그 확인:**
```
INFO:     Started server process
INFO:     Waiting for application startup.
2025-11-03 20:00:00.000 | INFO | src.web.server:startup_event:204 - FastAPI Web Control Server starting...
2025-11-03 20:00:00.001 | INFO | src.web.server:startup_event:205 - Server docs available at: http://localhost:8000/docs
2025-11-03 20:00:00.002 | INFO | src.web.server:startup_event:206 - WebSocket endpoints: /ws/control, /ws/robot-status
```

### 4단계: 웹 브라우저 연결

#### 웹 UI 화면 구성

```
┌───────────────────────────────────────────────────┐
│ 🤖 LLM Robot Control - Web Interface             │
├───────────────────────────────────────────────────┤
│                                                   │
│ 📍 Robot Status                                   │
│ ┌─────────────────────────────────────────────┐   │
│ │ 상태: CONNECTED ● (실시간 업데이트 10Hz)     │   │
│ │ 위치: X=0.00m, Y=0.00m, Yaw=0.0°            │   │
│ │ 미션: idle                                   │   │
│ └─────────────────────────────────────────────┘   │
│                                                   │
│ 📡 Sensors                                        │
│ ┌─────────────────────────────────────────────┐   │
│ │ GPS: (0.00, 0.00)    IMU: Pitch=0° Roll=0° │   │
│ │ Lidar: 512 points    Camera: 640×480       │   │
│ └─────────────────────────────────────────────┘   │
│                                                   │
│ 💬 Command Input                                  │
│ ┌─────────────────────────────────────────────┐   │
│ │ 자연어 명령을 입력하세요 (한국어/English)     │   │
│ │                                             │   │
│ │ 예: "동쪽으로 5미터 이동"                    │   │
│ │     "좌측 90도 회전"                         │   │
│ │     "생존자 탐색"                            │   │
│ └─────────────────────────────────────────────┘   │
│           [Submit Mission] 버튼                   │
│                                                   │
│ 📋 Mission Log (실시간)                           │
│ ┌─────────────────────────────────────────────┐   │
│ │ [20:30:45] 웹 서버 연결 완료                 │   │
│ │ [20:30:46] Mission started: 동쪽으로 3미터...│   │
│ │ [20:30:47] Planner: Plan generated (3 steps)│   │
│ │ [20:30:48] Actor: Moving to X=3.0, Y=0.0    │   │
│ │ [20:30:52] Reactive: NORMAL (no obstacles)  │   │
│ │ [20:30:55] Verifier: Success ✅              │   │
│ └─────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────┘
```

#### WebSocket 연결 확인

브라우저 개발자 도구 (F12) → Console:
```javascript
// WebSocket 연결 성공 시:
WebSocket connection established: ws://localhost:8000/ws/robot-status

// 상태 업데이트 수신 (10Hz):
Received: {"type":"status_update","data":{"position":{...},"sensors":{...}}}
```

---

## 💬 자연어 명령 예제

### 기본 이동 명령

#### 한국어 명령어
```
1. "동쪽으로 3미터 이동"
   → X 좌표 +3.0m 이동

2. "앞으로 5미터 전진"
   → 현재 방향으로 5m 직진

3. "북쪽으로 2미터 이동하세요"
   → Y 좌표 +2.0m 이동

4. "위치 (2, 3)으로 이동"
   → 절대 좌표 X=2.0m, Y=3.0m로 이동
```

#### 영어 명령어
```
1. "Move 3 meters to the east"
   → X coordinate +3.0m

2. "Go forward 5 meters"
   → Move 5m in current direction

3. "Navigate to position (2, 3)"
   → Absolute coordinate X=2.0m, Y=3.0m
```

### 회전 명령

```
한국어:
1. "좌측 90도 회전"
   → 반시계 방향 90° 회전

2. "오른쪽으로 45도 돌아"
   → 시계 방향 45° 회전

3. "180도 회전해서 뒤로 향해"
   → 반대 방향으로 회전

영어:
1. "Rotate 90 degrees left"
2. "Turn right 45 degrees"
3. "Face the opposite direction"
```

### 복합 명령

```
1. "동쪽으로 5미터 이동한 후 생존자 탐색"
   → MOVE (X=+5.0) → SCAN (duration=5s)

2. "위험 구역을 회피하면서 북쪽으로 이동"
   → 장애물 감지 + 우회 경로 계획

3. "천천히 전진하면서 주변 스캔"
   → MOVE (speed=0.3 m/s) + continuous SCAN

4. "좌측 90도 회전 후 3미터 전진"
   → ROTATE (-90°) → MOVE (3m)
```

### 탐색 및 센서 명령

```
1. "주변 환경 스캔"
   → SCAN action (duration=5s, 360° Lidar)

2. "생존자 탐색"
   → SCAN + Camera + AI 분석

3. "장애물 확인"
   → Lidar 데이터 분석

4. "현재 위치 보고"
   → GPS 위치 + 센서 상태 반환
```

### 안전 명령

```
1. "정지" / "멈춰" / "Stop"
   → 즉시 모든 모터 정지 (STOP action)

2. "대기" / "Wait"
   → 지정 시간 동안 대기 (WAIT action)

3. "안전하게 후진"
   → 장애물 확인 후 후진

4. "긴급 정지"
   → Emergency stop (모든 작업 중단)
```

---

## 🖥️ 웹 UI 사용법

### 1. 명령 제출

**방법 1: 텍스트 입력**
1. 명령 입력창에 자연어 명령 입력
2. "Submit Mission" 버튼 클릭
3. 로그 창에서 실행 과정 실시간 확인

**방법 2: 예제 버튼 (구현 예정)**
- 미리 정의된 명령어 버튼 클릭

### 2. 실시간 상태 모니터링

**자동 업데이트 (10Hz = 100ms 간격):**
- 로봇 위치 (X, Y, Yaw)
- 센서 데이터 (GPS, IMU, Lidar, Camera)
- 미션 상태 (idle/executing/completed/failed)
- Reactive 개입 횟수 (CRITICAL/MODERATE/NORMAL)

**상태 표시:**
- 🟢 **CONNECTED**: 웹 서버 연결 성공
- 🔴 **DISCONNECTED**: 연결 끊김 (재연결 시도)
- 🟡 **EXECUTING**: 미션 실행 중
- ⚫ **IDLE**: 대기 상태

### 3. 로그 확인

**로그 레벨:**
- **INFO** (파란색): 일반 정보
- **SUCCESS** (녹색): 성공 메시지
- **WARNING** (노란색): 경고 (장애물 감지 등)
- **ERROR** (빨간색): 오류 발생

**로그 필터링:**
```javascript
// 브라우저 Console에서:
// Reactive 로그만 보기
logEntries.filter(e => e.includes('Reactive'))

// 오류만 보기
logEntries.filter(e => e.type === 'error')
```

### 4. 키보드 단축키 (구현 예정)

- `Ctrl+Enter`: 명령 제출
- `Ctrl+S`: 긴급 정지
- `Ctrl+L`: 로그 지우기

---

## 🔧 문제 해결

### 문제 1: 웹 서버가 시작되지 않음

**증상:**
```
ERROR: [Errno 10048] error while attempting to bind on address ('127.0.0.1', 8000):
only one usage of each socket address (protocol/network address/port) is normally permitted
```

**원인:** 포트 8000이 이미 사용 중

**해결:**
```bash
# Option A: 다른 포트 사용
uvicorn src.web.server:app --port 8001

# Option B: 기존 프로세스 종료 (Windows)
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Option C: 기존 프로세스 종료 (Linux/Mac)
lsof -ti:8000 | xargs kill -9
```

### 문제 2: Webots 연결 안 됨

**증상:**
```
503 Service Unavailable: Orchestrator not initialized. Robot must be running.
```

**원인:** Webots 시뮬레이션이 실행되지 않았거나 Orchestrator가 초기화 안 됨

**해결:**
```bash
# 1. Webots가 실행 중인지 확인
ps aux | grep webots  # Linux/Mac
tasklist | findstr webots  # Windows

# 2. Webots 월드 파일 다시 열기
File → Open World → rescue_robot.wbt

# 3. 로봇 컨트롤러 재시작
Webots GUI → Restart Controller (Ctrl+Shift+R)

# 4. 웹 서버 재시작
Ctrl+C (종료) → uvicorn 다시 실행
```

### 문제 3: Ollama 연결 실패

**증상:**
```
WARNING: Reactive controller failed to connect to Ollama
```

**원인:** Ollama 서비스가 실행되지 않음

**해결:**
```bash
# Ollama 서비스 확인
curl http://localhost:11434/api/tags

# 응답 없으면 Ollama 시작
ollama serve

# tinyllama 모델 확인
ollama list

# 모델이 없으면 다운로드
ollama pull tinyllama
```

### 문제 4: WebSocket 연결 끊김

**증상:**
브라우저 Console에서:
```
WebSocket disconnected. Attempting to reconnect...
```

**원인:** 서버 재시작 또는 네트워크 문제

**해결:**
```javascript
// 자동 재연결 (이미 구현됨)
// 수동 재연결: 페이지 새로고침 (F5)

// 연결 상태 확인:
ws.readyState
// 0: CONNECTING
// 1: OPEN (정상)
// 2: CLOSING
// 3: CLOSED
```

### 문제 5: 로봇이 명령을 따르지 않음

**증상:**
로그에 "Mission failed" 또는 "Goal unreached"

**원인:**
1. 안전 제약 위반 (경계 밖으로 이동 시도)
2. 장애물 충돌
3. LLM API 오류

**해결:**
```bash
# 1. 명령어 단순화
"동쪽으로 10미터 이동" (실패 - 경계 5m)
→ "동쪽으로 3미터 이동" (성공)

# 2. 로그에서 실패 원인 확인
[ERROR] Safety constraint violated: Position out of bounds

# 3. 작업 영역 확인 (-5m to +5m, 10m×10m)
X: -5.0 ~ +5.0
Y: -5.0 ~ +5.0

# 4. OpenAI API 키 확인
echo $OPENAI_API_KEY  # Linux/Mac
echo %OPENAI_API_KEY%  # Windows
```

### 문제 6: 브라우저에서 페이지 로딩 안 됨

**증상:**
```
This site can't be reached
localhost refused to connect
```

**원인:** 웹 서버가 실행되지 않음

**해결:**
```bash
# 1. 서버 프로세스 확인
ps aux | grep uvicorn  # Linux/Mac
tasklist | findstr python  # Windows

# 2. 서버 시작 확인
curl http://localhost:8000/health
# {"status":"ok",...}

# 3. 방화벽 확인 (Windows)
# 설정 → 방화벽 → 앱 허용 → Python 허용

# 4. 서버 재시작
uvicorn src.web.server:app --reload --host 0.0.0.0 --port 8000
```

---

## 🎓 고급 기능

### 1. REST API 직접 호출

```bash
# Health Check
curl http://localhost:8000/health

# 현재 상태 조회
curl http://localhost:8000/api/status

# 미션 실행 (POST)
curl -X POST http://localhost:8000/api/mission \
  -H "Content-Type: application/json" \
  -d '{
    "command": "동쪽으로 3미터 이동",
    "language": "ko",
    "priority": 5
  }'
```

### 2. WebSocket 클라이언트 (Python)

```python
import asyncio
import websockets
import json

async def robot_status_listener():
    uri = "ws://localhost:8000/ws/robot-status"

    async with websockets.connect(uri) as websocket:
        print("✅ WebSocket connected")

        while True:
            message = await websocket.recv()
            data = json.loads(message)

            if data['type'] == 'status_update':
                status = data['data']
                print(f"Position: X={status['position']['x']:.2f}, Y={status['position']['y']:.2f}")
                print(f"Mission: {status['mission_state']}")

asyncio.run(robot_status_listener())
```

### 3. 환경별 RAG 필터링

**실내 환경 명령:**
```
"실내 복도를 따라 3미터 이동"
→ Environment: indoor
→ RAG filters: indoor constraints
→ GPS accuracy: moderate, Lidar primary
```

**실외 환경 명령:**
```
"야외에서 5미터 전진"
→ Environment: outdoor
→ RAG filters: outdoor constraints
→ GPS accuracy: high, terrain aware
```

**창고 환경:**
```
"창고 내부에서 물품 탐색"
→ Environment: warehouse
→ RAG filters: warehouse constraints
→ Narrow aisle detection
```

**병원 환경:**
```
"병원 복도를 조용히 이동"
→ Environment: hospital
→ RAG filters: hospital constraints
→ Low speed, gentle acceleration
```

### 4. Reactive Controller 상세 로그

**로그 레벨 설정:**
```python
# src/reactive/hybrid_controller.py
import logging
logging.getLogger('src.reactive').setLevel(logging.DEBUG)
```

**Reactive 개입 확인:**
```
[REACTIVE] CRITICAL: Emergency stop! Obstacle at 0.15m
[REACTIVE] MODERATE: Detour suggested (left 45°, Ollama)
[REACTIVE] NORMAL: No obstacles detected
```

### 5. 멀티 클라이언트 지원

**동시 10+ 브라우저 연결 가능:**
```bash
# 브라우저 1: http://localhost:8000
# 브라우저 2: http://localhost:8000
# 브라우저 3: http://localhost:8000

# 모든 클라이언트가 동일한 로봇 상태를 10Hz로 수신
```

### 6. 미션 로그 저장

```python
# 로그 파일 위치
logs/mission_YYYYMMDD_HHMMSS.log  # 텍스트 로그
logs/mission_YYYYMMDD_HHMMSS.json # JSON 로그

# 로그 분석
import json

with open('logs/mission_20251103_203000.json', 'r') as f:
    logs = json.load(f)

    # LLM 호출 횟수
    llm_calls = [log for log in logs if 'LLM' in log['message']]
    print(f"LLM calls: {len(llm_calls)}")

    # 평균 실행 시간
    mission_logs = [log for log in logs if 'Mission completed' in log['message']]
    # ...
```

---

## 📊 성능 및 제한사항

### 시스템 사양

| 항목 | 값 |
|-----|-----|
| **작업 영역** | 10m × 10m (-5m to +5m) |
| **최대 속도** | 1.2 m/s (권장: 0.5 m/s) |
| **위치 정확도** | ±0.1m (GPS) |
| **센서 샘플링** | 64ms (15.6 Hz) |
| **상태 업데이트** | 100ms (10 Hz) |
| **Reactive 반응** | 64ms (실시간) |
| **WebSocket 지연** | <50ms (로컬) |
| **동시 연결** | 10+ 클라이언트 |

### 제약사항

- ✅ **한국어/영어 명령만 지원** (다른 언어는 영어로 변환 필요)
- ✅ **10m×10m 영역 제한** (경계 밖 명령은 자동 거부)
- ✅ **장애물 감지 범위: 0.5m~3.0m** (Lidar 512포인트)
- ✅ **Ollama 필수** (Reactive controller용, tinyllama 모델)
- ✅ **OpenAI API 필수** (Planner/Actor agents용, gpt-4o-mini)

---

## 📚 추가 자료

### 관련 문서
- **Story 3.2**: `docs/stories/3-2-fastapi-web-server.md` - 웹 서버 상세 명세
- **Story 3.1**: `docs/stories/3-1-hybrid-reactive-controller.md` - 반응형 제어
- **Story 3.3**: `docs/stories/3-3-environment-aware-planning.md` - 환경 인식
- **Architecture**: `docs/architecture.md` - 전체 시스템 아키텍처
- **README**: `README.md` - 프로젝트 개요

### API 문서
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 소스 코드
```
src/
├── web/
│   ├── server.py          # FastAPI 메인 서버 (666 lines)
│   ├── schemas.py         # Pydantic 스키마 (250 lines)
│   └── templates/
│       └── index.html     # 웹 UI (520 lines)
├── orchestrator.py        # 미션 조율 (800+ lines)
├── agents/
│   ├── planner_agent.py   # 계획 에이전트
│   ├── actor_agent.py     # 실행 에이전트
│   └── verifier_agent.py  # 검증 에이전트
└── reactive/
    └── hybrid_controller.py # 반응형 제어 (441 lines)
```

---

## 🎯 다음 단계

### 완료된 기능 (Epic 3)
- ✅ Ollama Setup & Validation (Story 3.0)
- ✅ Hybrid Reactive Controller (Story 3.1)
- ✅ FastAPI Web Control Server (Story 3.2)
- ✅ Environment-Aware Planning (Story 3.3)
- ✅ Epic 3 Integration Testing (Story 3.5)
- ✅ Production Code Fixes (Story 3.6)

### 선택사항 (Optional)
- 📋 React Web UI Dashboard (Story 3.4) - 12시간
  - React 18 기반 고급 대시보드
  - 3D 로봇 위치 시각화
  - 실시간 센서 그래프

### 프로덕션 배포 (향후)
- Docker 컨테이너화
- Kubernetes 배포
- 원격 로봇 제어 (클라우드)
- 멀티 로봇 조율

---

## 🤝 기여 및 지원

### 이슈 리포트
- GitHub Issues: [프로젝트 저장소]/issues

### 피드백
- Story 개선 제안
- 버그 리포트
- 새 기능 요청

---

**작성일:** 2025-11-03
**작성자:** Claude Sonnet 4.5
**버전:** 1.0.0 (Epic 3 완료)
**상태:** ✅ Production Ready

**Happy Robot Controlling! 🤖🚀**
