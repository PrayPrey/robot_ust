# Epic 3 Integration Test Plan

**Project:** LLM_ROBOT_2
**Epic:** Epic 3 - Advanced Real-time Control & Web Interface
**Story:** 3.5 - Epic 3 Integration Testing
**Generated:** 2025-11-03
**Author:** Amelia (Dev Agent)

---

## 1. Executive Summary

This document outlines the comprehensive integration testing strategy for Epic 3, which introduces:
- **Hybrid Reactive Controller** (Story 3.1) - Real-time obstacle avoidance
- **FastAPI Web Control Server** (Story 3.2) - Web-based robot operation
- **Environment-Aware Planning** (Story 3.3) - Adaptive planning based on environment detection

The test plan ensures all Epic 3 components integrate seamlessly with existing Epic 1-2 functionality while maintaining backward compatibility.

---

## 2. Test Objectives

### Primary Objectives
1. **Integration Validation**: Verify all Epic 3 components work together end-to-end
2. **Performance Validation**: Confirm system meets performance targets under load
3. **Error Resilience**: Validate graceful degradation and error recovery
4. **Backward Compatibility**: Ensure no regressions in Epic 1-2 functionality

### Success Criteria
- ✅ All 10+ E2E integration scenarios pass (100% success rate)
- ✅ 10 concurrent WebSocket connections stable with <5s response times
- ✅ All error scenarios handled gracefully without crashes
- ✅ 270+ Epic 1-2 regression tests pass (100% pass rate)
- ✅ Test coverage remains >80% across entire codebase

---

## 3. Test Environment

### Required Infrastructure
```yaml
Hardware:
  - CPU: 4+ cores
  - RAM: 8GB minimum
  - Storage: 2GB available

Software:
  - Python: 3.11+
  - Webots: R2025a
  - Ollama: Service with tinyllama model (optional)
  - FastAPI: Server running on port 8000

Dependencies:
  - pytest >= 7.4.0
  - pytest-asyncio >= 0.21.0
  - pytest-cov >= 4.1.0
  - FastAPI TestClient
```

### Test Data
```python
# Indoor Environment
INDOOR_SENSOR_DATA = {
    "gps_signal": 0.2,  # Weak GPS
    "lidar_ranges": [1.5, 2.0, 1.8] * 120,  # Close walls
    "camera_brightness": 150  # Moderate lighting
}

# Outdoor Environment
OUTDOOR_SENSOR_DATA = {
    "gps_signal": 0.9,  # Strong GPS
    "lidar_ranges": [10.0, 12.0, 11.5] * 120,  # Open space
    "camera_brightness": 220  # Bright sunlight
}

# Obstacle Scenarios
CRITICAL_OBSTACLE = 0.1m  # <0.15m → EMERGENCY_STOP
MODERATE_OBSTACLE = 0.3m  # 0.15-0.5m → DETOUR
NORMAL_SCENARIO = 1.5m    # >0.5m → CONTINUE
```

---

## 4. End-to-End Integration Test Scenarios

### Scenario 1: Web UI → Reactive Controller → Success
**Objective:** Validate full workflow from WebSocket to reactive intervention
**Test File:** `tests/integration/test_epic3_e2e.py::test_web_to_reactive_controller_e2e`

**Steps:**
1. Establish WebSocket connection to FastAPI server
2. Send command: "장애물 회피하며 5미터 전진"
3. Simulate obstacle at 0.3m (triggers reactive intervention)
4. Verify mission completes with reactive_log populated

**Expected Results:**
- WebSocket connection established successfully
- Mission command processed by Orchestrator
- Reactive controller intervenes on obstacle detection
- Mission completes successfully with intervention logged

**Pass Criteria:** Mission success AND reactive_log contains intervention record

---

### Scenario 2: Environment Detection → RAG Filtering → Planning
**Objective:** Validate environment-aware planning with RAG filtering
**Test File:** `tests/integration/test_epic3_e2e.py::test_environment_detection_integration`

**Steps:**
1. Inject indoor sensor data (GPS=0.2, Lidar=2m, brightness=150)
2. Verify EnvironmentDetector classifies as "indoor" (confidence >0.8)
3. Verify PlannerAgent retrieves indoor-specific constraints from RAG
4. Execute mission and verify Lidar-based navigation (no GPS reliance)

**Expected Results:**
- Environment correctly classified as "indoor"
- RAG query filtered by environment="indoor"
- Mission plan adapts to indoor constraints
- Mission execution uses appropriate indoor strategies

**Pass Criteria:** Environment="indoor" detected AND indoor constraints applied

---

### Scenario 3-4: Indoor/Outdoor Mission Workflows
**Objective:** Validate mission execution in different environments
**Test Files:**
- `tests/integration/test_epic3_e2e.py::test_full_workflow_indoor`
- `tests/integration/test_epic3_e2e.py::test_full_workflow_outdoor`

**Indoor Mission:**
- Weak GPS signal (0.2)
- Close walls (Lidar 1.5-2m)
- Moderate lighting (150)
- **Expected:** Lidar-based navigation, potential reactive interventions

**Outdoor Mission:**
- Strong GPS signal (0.9)
- Open space (Lidar 10-12m)
- Bright lighting (220)
- **Expected:** GPS waypoint navigation, minimal reactive interventions

**Pass Criteria:** Both missions complete successfully with appropriate strategies

---

### Scenario 5: Concurrent Missions with Isolation
**Objective:** Verify mission isolation across environment changes
**Test File:** `tests/integration/test_epic3_e2e.py::test_concurrent_missions`

**Steps:**
1. Execute Mission 1: Indoor environment
2. Execute Mission 2: Outdoor environment (change sensors)
3. Execute Mission 3: Warehouse environment (indoor variant)
4. Verify each mission uses correct environment constraints
5. Verify reactive_logs don't cross-contaminate
6. Verify state properly reset between missions

**Expected Results:**
- Each mission detects correct environment
- Different RAG constraints retrieved per mission
- Reactive logs isolated per mission
- State cleanly reset between missions

**Pass Criteria:** All 3 missions complete AND no state leakage detected

---

### Scenarios 6-10: Additional Integration Tests
- **Scenario 6:** Reactive Log WebSocket Broadcasting (real-time events)
- **Scenario 7:** Ollama MODERATE Detour (Level 2 intervention)
- **Scenario 8:** CRITICAL Emergency Stop (Level 1 intervention)
- **Scenario 9:** Multiple Detours in One Mission (multiple interventions)
- **Scenario 10:** Environment Change Between Missions (adaptation)

**Pass Criteria:** All scenarios execute without crashes AND expected behaviors verified

---

## 5. Performance and Load Testing

### Test 1: Concurrent WebSocket Connections
**Objective:** Validate 10 simultaneous connections without degradation
**Test File:** `tests/performance/test_load_testing.py::test_concurrent_web_requests`

**Test Configuration:**
```python
num_concurrent_requests = 10
expected_success_rate = >90%
max_response_time = <5 seconds (SLA)
avg_response_time = <2 seconds (target)
```

**Metrics Tracked:**
- Total requests: 10
- Success rate: (successful / total)
- Response times: min, avg, max, P90, P99
- Throughput: requests per second
- Error rate: (failed / total)

**Pass Criteria:**
- ✅ Success rate ≥90%
- ✅ Max response time <5s (SLA met)
- ✅ Avg response time <2s (performance target)
- ✅ No connection errors or timeouts

---

### Test 2: WebSocket Message Throughput
**Objective:** Verify stability with 100+ messages on single connection
**Test File:** `tests/performance/test_load_testing.py::test_websocket_message_throughput`

**Test Configuration:**
```python
num_messages = 100
avg_latency_target = <50ms
p90_latency_target = <100ms
```

**Metrics Tracked:**
- Messages processed: 100
- Average latency: (sum / count)
- P90 latency: 90th percentile
- Max latency: worst case
- Connection stability: no drops

**Pass Criteria:**
- ✅ All 100 messages processed
- ✅ Avg latency <50ms
- ✅ P90 latency <100ms
- ✅ No connection drops

---

### Test 3: Ollama Concurrent Inference
**Objective:** Validate Ollama handling multiple reactive decisions
**Test File:** `tests/performance/test_load_testing.py::test_ollama_concurrent_inference`

**Test Configuration:**
```python
num_concurrent_decisions = 5
p90_execution_time_target = <1200ms
```

**Note:** Simplified mock test. Production would test actual Ollama inference.

**Pass Criteria:**
- ✅ All 5 concurrent decisions complete
- ✅ P90 execution time reasonable for mock test

---

## 6. Error Handling and Graceful Degradation

### Error Scenario 1: Ollama Service Failure
**Objective:** Verify fallback to rules-only mode
**Test File:** `tests/integration/test_error_handling.py::test_ollama_failure_graceful_degradation`

**Test Steps:**
1. Initialize reactive controller (Ollama unavailable)
2. Execute mission with potential obstacles
3. Verify system falls back to rules-only mode
4. Verify mission completes without crash

**Expected Behavior:**
- Reactive controller detects Ollama unavailable
- Falls back to Level 1 (CRITICAL) and Level 3 (NORMAL) rules
- Mission continues with rules-only interventions
- No crashes or exceptions

**Pass Criteria:** Mission completes AND no Ollama-related crashes

---

### Error Scenario 2: WebSocket Disconnect
**Objective:** Verify reconnection handling
**Test File:** `tests/integration/test_error_handling.py::test_websocket_disconnect_reconnect`

**Test Steps:**
1. Establish WebSocket connection
2. Send mission command
3. Close connection
4. Establish new connection (simulate reconnect)
5. Verify server accepts new connection

**Expected Behavior:**
- Server handles disconnect gracefully
- New connections accepted after disconnect
- No server state corruption

**Pass Criteria:** Reconnection successful AND server remains stable

---

### Error Scenarios 3-6: Additional Error Tests
- **Scenario 3:** Network Errors → Appropriate error responses (400/503)
- **Scenario 4:** Webots Simulator Errors → Cleanup and recovery
- **Scenario 5:** Timeout Handling → Ollama >1500ms timeout triggers fallback
- **Scenario 6:** Environment Misclassification → Handles low-confidence classifications

**Pass Criteria:** All error scenarios handled gracefully without data corruption

---

## 7. Regression Testing

### Objective
Verify Epic 3 changes don't break existing Epic 1-2 functionality.

### Test Execution
```bash
pytest tests/ -v --cov=src --cov-report=html --ignore=tests/performance
```

### Expected Results
```yaml
Total Tests: 270+ (Epic 1-2) + 20+ (Epic 3) = 290+ tests
Expected Pass Rate: 100%
Expected Coverage: >80%
Execution Time: <10 minutes
```

### Test Categories
- **Epic 1 Foundation Tests (~150 tests):**
  - Planner Agent: Action plan generation
  - Actor Agent: Action execution
  - Verifier Agent: Success/failure validation
  - Orchestrator: Multi-agent coordination

- **Epic 2 Advanced Tests (~120 tests):**
  - RAG: Knowledge retrieval from ChromaDB
  - Multi-Sensor Integration: GPS, Lidar, Camera
  - Safety Constraints: Collision detection, boundary checks
  - Failure Recovery: Replanning on mission failure
  - Monitoring & Evaluation: Structured logging

### Pass Criteria
- ✅ All 270+ Epic 1-2 tests pass (0 failures)
- ✅ Test coverage ≥80%
- ✅ No degradation in test execution time
- ✅ No new warnings or errors introduced

---

## 8. Test Execution Schedule

### Phase 1: Unit Tests (Already Complete)
```bash
pytest tests/unit/ -v
# Expected: 40+ Epic 3 unit tests passing
```

### Phase 2: Integration Tests (Story 3.5)
```bash
pytest tests/integration/test_epic3_e2e.py -v
pytest tests/integration/test_error_handling.py -v
# Expected: 16 integration tests passing (10 E2E + 6 error)
```

### Phase 3: Performance Tests (Story 3.5)
```bash
pytest tests/performance/test_load_testing.py -v -m slow
# Expected: 3 performance tests passing
```

### Phase 4: Regression Tests (Story 3.5)
```bash
pytest tests/ -v --cov=src --cov-report=html
# Expected: 290+ total tests passing
```

### Phase 5: Generate Reports (Story 3.5)
- HTML coverage report: `htmlcov/index.html`
- Integration test report: `docs/integration_test_report.md`

---

## 9. Risk Assessment

### High Risk Areas
1. **WebSocket Concurrent Connections**
   - Risk: Connection drops under load
   - Mitigation: Thorough load testing, connection pooling

2. **Ollama Service Availability**
   - Risk: Service crashes impact reactive control
   - Mitigation: Rules-only fallback, graceful degradation

3. **Environment Detection Accuracy**
   - Risk: Misclassification leads to wrong constraints
   - Mitigation: Confidence thresholds, "unknown" fallback

### Medium Risk Areas
4. **Test Database State**
   - Risk: ChromaDB state contamination between tests
   - Mitigation: Isolated test databases, cleanup fixtures

5. **Mock vs. Real Testing**
   - Risk: Mocks don't reflect production behavior
   - Mitigation: Comprehensive integration tests with real components

---

## 10. Acceptance Gates

Story 3.5 is **APPROVED** for completion when:

✅ **AC #1: E2E Integration Tests**
- All 10+ scenarios pass (100% success rate)
- Full workflow coverage (Web → Reactive → Environment → Success)

✅ **AC #2: Performance Validation**
- 10 concurrent connections stable (<5s response times)
- 100+ message throughput verified
- Ollama concurrent handling validated

✅ **AC #3: Error Propagation Testing**
- Ollama failure handled gracefully
- WebSocket disconnects recoverable
- Network errors return appropriate responses
- Webots errors trigger cleanup

✅ **AC #4: Regression Testing**
- All 270+ Epic 1-2 tests pass (100%)
- Test coverage >80%
- No backward compatibility issues

✅ **AC #5: Integration Test Documentation**
- Test plan created (`test_plan_epic3.md`)
- Test results report generated (`integration_test_report.md`)

---

## 11. Contact and Support

**Test Engineer:** Amelia (Dev Agent)
**Story:** 3.5 - Epic 3 Integration Testing
**Estimated Effort:** 4 hours
**Actual Effort:** TBD (will be documented in test report)

For issues or questions:
- Review test output logs in `pytest -v` mode
- Check HTML coverage report: `htmlcov/index.html`
- Consult story context: `docs/stories/3-5-integration-testing.context.xml`

---

**Document Status:** DRAFT
**Last Updated:** 2025-11-03
**Next Review:** After test execution completion
