# FastAPI Web Control Server - 설치 및 사용 가이드

**Story 3.2: FastAPI Web Control Server**
**Phase 1-2 구현 완료** (2025-11-03)
**실시간 10Hz 상태 브로드캐스팅 기능 포함**

## 📦 설치

### 1. Dependencies 설치

가상환경에서 필수 패키지를 설치합니다:

```bash
# 가상환경 활성화 (Windows)
C:\Users\OWNER\Desktop\Woo_Yoon_Kyu\BMAD-METHOD\venv\Scripts\activate

# FastAPI 및 웹 서버 패키지 설치
pip install fastapi "uvicorn[standard]" websockets python-socketio
```

### 2. 설치 확인

```bash
python -c "import fastapi; print(f'FastAPI {fastapi.__version__} installed')"
```

## 🚀 서버 실행

### 개발 모드 실행

**주의:** 현재 Phase 1 구현이므로, Orchestrator가 초기화되지 않은 상태에서 API 테스트만 가능합니다.

```bash
# 프로젝트 루트에서 실행
uvicorn src.web.server:app --reload --host 127.0.0.1 --port 8000
```

서버 시작 후:
- API 문서: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health Check: http://localhost:8000/health

## 📡 API 엔드포인트

### REST API

#### 1. Health Check
```bash
GET http://localhost:8000/health
```

응답 예시:
```json
{
  "status": "ok",
  "timestamp": "2025-11-03T10:30:45.123456",
  "details": {
    "uptime_seconds": 3600,
    "active_connections": 0,
    "orchestrator_status": "not_initialized"
  }
}
```

#### 2. Get Status
```bash
GET http://localhost:8000/api/status
```

#### 3. Execute Mission (Orchestrator 필요)
```bash
POST http://localhost:8000/api/mission
Content-Type: application/json

{
  "command": "앞으로 5미터 전진",
  "language": "ko",
  "priority": 5
}
```

**주의:** Mission 실행은 Orchestrator 초기화 후에만 동작합니다 (Phase 3에서 통합 예정).

### WebSocket 엔드포인트

#### 1. Command Control
```
ws://localhost:8000/ws/control
```

#### 2. Status Broadcasting (10Hz)
```
ws://localhost:8000/ws/robot-status
```

## 🔧 구현 상태

### ✅ Phase 1 완료 (2025-11-03)
- [x] FastAPI 프로젝트 구조 설정
- [x] Pydantic Request/Response 스키마
- [x] REST API 엔드포인트 (GET /health, GET /api/status, POST /api/mission)
- [x] ConnectionManager 클래스
- [x] WebSocket 엔드포인트 골격 (기본 구현)
- [x] CORS 미들웨어 설정
- [x] FastAPI 자동 문서화 (/docs)

### ✅ Phase 2 완료 (2025-11-03) - WebSocket 전체 구현
- [x] **Background Task 기반 10Hz 상태 브로드캐스팅**
  - `status_broadcast_worker()` - 100ms마다 상태 전송
  - `start_status_broadcasting()` / `stop_status_broadcasting()` 제어
  - `toggle_status_broadcasting()` - 런타임 활성화/비활성화
- [x] **시스템 상태 실시간 조회**
  - `get_current_system_status()` - Actor agent에서 RobotState 조회
  - Position, sensors, mission state 추출
  - Reactive log 요약 (CRITICAL/MODERATE/NORMAL 카운트)
- [x] **Orchestrator 비동기 통합**
  - `set_orchestrator()` - Orchestrator 인스턴스 등록
  - Startup/shutdown 이벤트에서 broadcasting 자동 시작/종료
  - `asyncio.to_thread()` 패턴으로 blocking 호출 래핑
- [x] **WebSocket 완전 구현**
  - `/ws/robot-status` - 실시간 상태 수신 + 클라이언트 제어 메시지
  - Ping/pong 메커니즘으로 연결 유지
  - Broadcasting toggle 런타임 제어

### 🚧 Phase 3 예정 (추가 최적화)
- [ ] WebSocket /ws/control 미션 실행 스트리밍
- [ ] 오류 처리 및 재연결 로직 강화
- [ ] Connection 메트릭 및 모니터링

### 🚧 Phase 4-6 예정
- [ ] 웹 UI (HTML/JavaScript)
- [ ] 문서화 및 배포 가이드
- [ ] 종합 테스트 (Unit/Integration/E2E)

## 📝 주요 파일

```
src/web/
├── __init__.py           # 패키지 초기화 + exports (32 lines)
├── server.py            # FastAPI 앱 및 엔드포인트 (650+ lines)
│   ├── ConnectionManager 클래스
│   ├── REST API 엔드포인트 (health, status, mission)
│   ├── WebSocket 엔드포인트 (control, robot-status)
│   ├── Background broadcasting worker (10Hz)
│   └── Helper functions (get_current_system_status, set_orchestrator 등)
└── schemas.py           # Pydantic 데이터 모델 (250 lines)
```

### 주요 함수 (Phase 2 추가)

**상태 조회 및 브로드캐스팅:**
- `get_current_system_status()` - Actor에서 현재 로봇 상태 조회
- `status_broadcast_worker()` - 10Hz background task
- `start_status_broadcasting()` / `stop_status_broadcasting()` - 생명주기 관리
- `toggle_status_broadcasting(enabled)` - 런타임 토글

**Orchestrator 통합:**
- `set_orchestrator(orch)` - Orchestrator 인스턴스 등록 및 broadcasting 시작

## 🧪 테스트

### 수동 테스트

#### 1. Health Check
```bash
curl http://localhost:8000/health
```

#### 2. Swagger UI에서 테스트
1. 브라우저에서 http://localhost:8000/docs 열기
2. "Try it out" 버튼 클릭
3. API 엔드포인트 테스트

### 자동 테스트 (Phase 6에서 구현 예정)
```bash
pytest tests/test_web_api.py -v
```

## ⚙️ 설정

### 환경 변수 (.env 파일)

Phase 5에서 `.env.template` 파일이 생성될 예정입니다.

필수 환경 변수:
- `OPENAI_API_KEY`: OpenAI API 키 (Planner/Actor 실행용)
- `SERVER_PORT`: 서버 포트 (기본값: 8000)
- `SERVER_HOST`: 서버 호스트 (기본값: 127.0.0.1)

## 🐛 문제 해결

### 1. Import 오류
```
ModuleNotFoundError: No module named 'fastapi'
```

**해결:** Dependencies 재설치
```bash
pip install -r requirements.txt
```

### 2. 포트 충돌
```
ERROR: [Errno 98] Address already in use
```

**해결:** 다른 포트 사용
```bash
uvicorn src.web.server:app --port 8001
```

### 3. Orchestrator not initialized
```
503 Service Unavailable: Orchestrator not initialized
```

**원인:** 이것은 정상입니다. Phase 1에서는 Orchestrator 통합이 완료되지 않았습니다.
**해결:** Phase 3 구현 후 Webots Robot 인스턴스와 함께 Orchestrator를 초기화해야 합니다.

## 📚 참고 자료

- FastAPI 공식 문서: https://fastapi.tiangolo.com/
- WebSocket 가이드: https://fastapi.tiangolo.com/advanced/websockets/
- Story 3.2 상세 명세: `docs/stories/3-2-fastapi-web-server.md`
- Context 파일: `docs/stories/3-2-fastapi-web-server.context.xml`

## 🚀 사용 예제 (Phase 2)

### Orchestrator 통합 예제

Webots controller에서 웹 서버와 orchestrator를 통합하는 방법:

```python
from controller import Robot
from src.orchestrator import MissionOrchestrator
from src.web import app, set_orchestrator, start_status_broadcasting
import uvicorn
import asyncio
import threading

# Webots robot 초기화
robot = Robot()

# Orchestrator 생성
orchestrator = MissionOrchestrator(
    robot=robot,
    openai_api_key=os.getenv("OPENAI_API_KEY")
)

# 웹 서버에 orchestrator 등록
set_orchestrator(orchestrator)

# Background thread로 FastAPI 서버 실행
def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8000)

server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()

# Webots 시뮬레이션 루프
while robot.step(timestep) != -1:
    # 로봇 제어 루프
    pass
```

### WebSocket 클라이언트 예제 (JavaScript)

```javascript
// 실시간 상태 구독
const ws = new WebSocket('ws://localhost:8000/ws/robot-status');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (data.type === 'status_update') {
    const status = data.data;
    console.log('Position:', status.position);
    console.log('Sensors:', status.sensors);
    console.log('Mission:', status.mission_state);
    console.log('Reactive interventions:', status.reactive_log_summary);
  }

  if (data.type === 'ping') {
    // Keep-alive ping
    ws.send(JSON.stringify({action: 'pong'}));
  }
};

// Broadcasting 제어
function toggleBroadcasting(enabled) {
  ws.send(JSON.stringify({
    action: 'toggle_broadcast',
    enabled: enabled
  }));
}
```

## 🔄 다음 단계

### Phase 3 예정 사항:
1. WebSocket `/ws/control` 미션 실행 스트리밍
2. 오류 처리 및 재연결 로직 강화
3. Connection 메트릭 및 모니터링

### Phase 4 예정 사항:
1. 웹 UI (HTML/JavaScript) 구현
2. 실시간 3D 위치 시각화
3. Reactive log 이벤트 타임라인

---

**구현 날짜:** 2025-11-03
**구현자:** Claude Sonnet 4.5 (Dev Agent)
**상태:** Phase 1-2 완료 ✅
**새 기능:** 실시간 10Hz 상태 브로드캐스팅, Orchestrator 비동기 통합
