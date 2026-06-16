"""
Hybrid Reactive Controller

3-level reactive decision system for real-time obstacle avoidance:
- Level 1 CRITICAL: Emergency stop (Lidar < 0.3m)
- Level 2 MODERATE: AI-powered detour (0.3m <= Lidar < 0.5m) - DISABLED due to Ollama latency
- Level 3 NORMAL: No intervention (Lidar >= 0.3m)

Performance targets:
- check_and_react() latency: <10ms (95th percentile, non-Ollama modes)
- Ollama detour decision: ~680ms avg, ~1027ms P90 (Story 3.0 validated)
- Emergency stop time: <50ms
"""

import json
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List
from loguru import logger

try:
    from ollama import Client
    OLLAMA_AVAILABLE = True
except ImportError:
    Client = None  # Make Client available at module level for testing/mocking
    OLLAMA_AVAILABLE = False
    logger.warning("Ollama not installed. Level 2 MODERATE mode will fall back to CRITICAL.")

try:
    from langchain_openai import ChatOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    ChatOpenAI = None
    OPENAI_AVAILABLE = False
    logger.warning("langchain_openai not installed. OpenAI LLM provider unavailable.")


class InterventionType(str, Enum):
    """Reactive intervention types."""
    CRITICAL = "CRITICAL"  # Emergency stop (Lidar < 0.3m)
    MODERATE = "MODERATE"  # AI-powered detour (0.3m <= Lidar < 0.5m)
    POST_DETOUR = "POST_DETOUR"  # Post-detour stabilization (LLM continues control)
    NORMAL = "NORMAL"      # No intervention (Lidar >= 0.3m)
    NONE = "NONE"          # No intervention needed


@dataclass
class ReactiveDecision:
    """
    Reactive controller decision output.

    Attributes:
        intervention_type: Type of intervention (CRITICAL/MODERATE/NORMAL/NONE)
        action: Action to take (emergency_stop, detour, continue)
        metadata: Additional decision context
        timestamp: Decision timestamp
        latency_ms: Decision latency in milliseconds
    """
    intervention_type: InterventionType
    action: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return asdict(self)


@dataclass
class ReactiveIntervention:
    """
    Reactive intervention record for logging.

    Stored in RobotState.reactive_log to inform Verifier tolerance adjustment.

    Attributes:
        timestamp: ISO format timestamp
        type: Intervention type (CRITICAL/MODERATE/NORMAL)
        reason: Human-readable reason for intervention
        action_taken: Action details (type, parameters)
        sensor_state: Sensor readings at intervention time
    """
    timestamp: str
    type: str
    reason: str
    action_taken: Dict[str, Any]
    sensor_state: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for RobotState.reactive_log."""
        return asdict(self)


@dataclass
class DetourPlan:
    """AI-generated detour plan from Ollama."""
    detour_x: float
    detour_y: float
    speed_modifier: float  # 0.5-1.0 range
    confidence: float      # 0.0-1.0 range
    reasoning: str


class HybridReactiveController:
    """
    3-level hybrid reactive controller for real-time obstacle avoidance.

    Integrates rule-based emergency stop (Level 1 CRITICAL) with AI-powered
    detour decisions (Level 2 MODERATE) using Ollama tinyllama model.

    Features hysteresis to prevent rapid state switching due to sensor noise.
    - CRITICAL: Enter at <0.3m, exit at >=0.35m (0.05m hysteresis)
    - MODERATE: Enter at <0.5m, exit at >=0.55m (0.05m hysteresis) - DISABLED

    Performance targets:
    - check_and_react() latency: <10ms (95th percentile, non-Ollama modes)
    - Ollama detour latency: ~680ms avg, ~1027ms P90
    - Emergency stop reaction: <0.001s

    Args:
        ollama_host: Ollama server URL (default: http://localhost:11434)
        model_name: Ollama model name (default: tinyllama)
        enable_ollama: Enable Level 2 MODERATE AI-powered detours
        emergency_threshold: Lidar distance for emergency stop in meters
        detour_threshold: Lidar distance for detour decision in meters
        hysteresis_margin: Hysteresis margin for state exit thresholds in meters
    """

    def __init__(
        self,
        ollama_host: str = "http://localhost:11434",
        model_name: str = "tinyllama",
        enable_ollama: bool = True,
        emergency_threshold: float = 0.3,
        detour_threshold: float = 0.5,
        hysteresis_margin: float = 0.05,
        llm_provider: str = "ollama",  # "ollama" or "openai"
        api_key: Optional[str] = None,  # OpenAI API key (required if llm_provider="openai")
        stabilization_steps: int = 5  # Steps to continue LLM control after detour
    ):
        """Initialize hybrid reactive controller."""
        self.ollama_host = ollama_host
        self.model_name = model_name
        self.llm_provider = llm_provider
        self.api_key = api_key
        self.emergency_threshold = emergency_threshold
        self.detour_threshold = detour_threshold
        self.hysteresis_margin = hysteresis_margin
        self.stabilization_steps = stabilization_steps

        # Current intervention state tracking (for hysteresis)
        self.current_state = InterventionType.NONE
        self.stabilization_steps_remaining = 0  # Counter for post-detour stabilization

        # LLM client initialization
        self.ollama_client: Optional[Client] = None
        self.openai_client: Optional[ChatOpenAI] = None
        self.enable_ollama = False  # Will be set based on provider

        if llm_provider == "openai":
            # OpenAI provider
            if not OPENAI_AVAILABLE:
                logger.error("OpenAI provider requested but langchain_openai not installed")
                enable_ollama = False
            elif not api_key:
                logger.error("OpenAI provider requires api_key parameter")
                enable_ollama = False
            else:
                try:
                    self.openai_client = ChatOpenAI(
                        model="gpt-4o-mini",
                        temperature=0.1,
                        api_key=api_key
                    )
                    self.enable_ollama = enable_ollama
                    logger.info(
                        f"HybridReactiveController initialized with OpenAI "
                        f"(model=gpt-4o-mini, hysteresis={hysteresis_margin}m)"
                    )
                except Exception as e:
                    logger.error(f"Failed to initialize OpenAI client: {e}")
                    self.enable_ollama = False
        elif llm_provider == "ollama":
            # Ollama provider
            self.enable_ollama = enable_ollama and OLLAMA_AVAILABLE
            if self.enable_ollama:
                try:
                    self.ollama_client = Client(host=ollama_host)
                    logger.info(
                        f"HybridReactiveController initialized with Ollama "
                        f"(host={ollama_host}, model={model_name}, hysteresis={hysteresis_margin}m)"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to initialize Ollama client: {e}. "
                        f"Falling back to rules-only reactive mode."
                    )
                    self.enable_ollama = False
                    self.ollama_client = None
            else:
                logger.info("HybridReactiveController initialized in rules-only mode")
        else:
            logger.error(f"Unknown llm_provider: {llm_provider}. Must be 'ollama' or 'openai'")
            self.enable_ollama = False

        # Performance tracking
        self.intervention_count = 0
        self.ollama_call_count = 0
        self.ollama_failure_count = 0
        self.total_latency_ms = 0.0

        # Detour caching (Story 3.1 Re-Review Action Item 1)
        self.detour_cache = {}  # Cache: hash(sensor_pattern) -> DetourPlan
        self.cache_hits = 0
        self.cache_misses = 0

        # LLM cooldown to prevent excessive calls
        self.last_ollama_call_time = 0.0  # Timestamp of last LLM call
        self.last_detour_plan = None  # Last detour plan (for reuse during cooldown)
        # OpenAI: 3 seconds (fast response ~1-2s)
        # Ollama: 15 seconds (slow response ~30s)
        self.ollama_cooldown_seconds = 3.0 if llm_provider == "openai" else 15.0
        self.detour_completed_time = 0.0  # Timestamp when last detour was completed

        # Forward sensor check angle (from constraints)
        self.forward_check_angle = 30.0  # degrees, ±15° from front

        # Detour history for LLM context (Option B: smart detour with history)
        self.detour_history: List[Dict[str, Any]] = []
        self.max_detour_history = 5  # Keep last 5 detour decisions

    def _get_forward_sensor_min(self, lidar_distances: list) -> float:
        """
        Get minimum distance from forward-facing sensors only.

        Lidar has 512 points covering 360 degrees.
        Forward check angle is ±15 degrees from front (0 degrees).

        Webots Lidar Index Convention (verified from official docs):
        - Data stored "left to right" order
        - Index 0 = +180° (back-left)
        - Index 128 = +90° (left)
        - Index 256 = 0° (FRONT/CENTER)
        - Index 384 = -90° (right)
        - Index 511 = -180° (back-right)

        Args:
            lidar_distances: List of 512 lidar distance measurements

        Returns:
            Minimum distance in forward sensor range (meters)
        """
        if not lidar_distances or len(lidar_distances) != 512:
            return float('inf')

        # Calculate forward sensor indices
        # 512 points / 360 degrees = 1.422 points/degree
        # ±15 degrees = ±21 points from center
        center_idx = 256  # FRONT (0°)
        half_angle_points = int((self.forward_check_angle / 2) * (512 / 360))

        # Forward range: center ± half_angle_points
        # idx 235 (+15°, front-left) to idx 277 (-15°, front-right)
        start_idx = center_idx - half_angle_points
        end_idx = center_idx + half_angle_points + 1

        forward_sensors = lidar_distances[start_idx:end_idx]

        return min(forward_sensors) if forward_sensors else float('inf')

    def _get_left_sensor_avg(self, lidar_distances: list) -> float:
        """
        Get minimum clearance from left-front diagonal sensors (30° to 60°).

        Lidar has 512 points covering 360 degrees.
        Left-front diagonal: +30° to +60° from front (detour direction).

        Webots Lidar Index Convention:
        - Index 256 = 0° (FRONT/CENTER)
        - Index formula: idx = 256 - (angle × 512/360)
        - For +30°: idx = 256 - 43 = 213
        - For +60°: idx = 256 - 85 = 171

        Args:
            lidar_distances: List of 512 lidar distance measurements

        Returns:
            Minimum distance on left-front diagonal (meters)
        """
        if not lidar_distances or len(lidar_distances) != 512:
            return float('inf')

        # Left-front diagonal: +30° to +60° (where robot will detour left)
        # Index formula: idx = 256 - (angle × 512/360)
        # +30° → idx = 256 - 43 = 213
        # +60° → idx = 256 - 85 = 171
        start_idx = 171  # +60° (further left)
        end_idx = 214    # +30° (closer to front)

        left_sensors = lidar_distances[start_idx:end_idx]
        # Use MINIMUM - detects closest obstacle in detour path
        return min(left_sensors) if left_sensors else float('inf')

    def _get_right_sensor_avg(self, lidar_distances: list) -> float:
        """
        Get minimum clearance from right-front diagonal sensors (-30° to -60°).

        Lidar has 512 points covering 360 degrees.
        Right-front diagonal: -30° to -60° from front (detour direction).

        Webots Lidar Index Convention:
        - Index 256 = 0° (FRONT/CENTER)
        - Index formula: idx = 256 - (angle × 512/360)
        - For -30°: idx = 256 - (-43) = 299
        - For -60°: idx = 256 - (-85) = 341

        Args:
            lidar_distances: List of 512 lidar distance measurements

        Returns:
            Minimum distance on right-front diagonal (meters)
        """
        if not lidar_distances or len(lidar_distances) != 512:
            return float('inf')

        # Right-front diagonal: -30° to -60° (where robot will detour right)
        # Index formula: idx = 256 - (angle × 512/360)
        # -30° → idx = 256 + 43 = 299
        # -60° → idx = 256 + 85 = 341
        start_idx = 299  # -30° (closer to front)
        end_idx = 342    # -60° (further right)

        right_sensors = lidar_distances[start_idx:end_idx]
        # Use MINIMUM - detects closest obstacle in detour path
        return min(right_sensors) if right_sensors else float('inf')

    def check_and_react(
        self,
        sensor_data: Dict[str, Any],
        is_backward: bool = False,
        target_info: Optional[Dict[str, float]] = None,
        near_target: bool = False
    ) -> ReactiveDecision:
        """
        3-level reactive decision logic with hysteresis for noise tolerance.

        Decision flow with hysteresis:
        - CRITICAL zone: lidar_min < 0.3m (enter), exit at >= 0.35m
        - MODERATE zone: lidar_min < 0.5m (enter), exit at >= 0.55m - DISABLED
        - NORMAL zone: lidar_min >= 0.3m

        Hysteresis prevents rapid state switching due to sensor noise.

        Args:
            sensor_data: Dictionary with keys 'lidar', 'gps', 'imu', 'camera'
                Expected lidar format: {
                    'lidar_distances': List[float],  # 512 points
                    'lidar_min_distance': float,
                    'lidar_avg_distance': float
                }
            is_backward: If True, skip forward obstacle checks (emergency escape mode)
            target_info: Optional target information for smart detour decisions
                {
                    'target_x': float,  # Target X coordinate
                    'target_y': float,  # Target Y coordinate
                    'current_x': float, # Current X position
                    'current_y': float, # Current Y position
                    'current_yaw': float  # Current heading in degrees
                }
            near_target: If True, skip MODERATE intervention (approaching pickup object)

        Returns:
            ReactiveDecision with intervention_type, action, metadata

        Performance:
        - Must return in <10ms (95th percentile, non-Ollama modes)
        - Ollama mode may take ~680ms avg, ~1027ms P90
        """
        start_time = time.time()

        # EMERGENCY ESCAPE MODE: Skip all forward obstacle checks during backward movement
        # This allows robot to reverse away from obstacles that it's stuck against
        if is_backward:
            latency_ms = (time.time() - start_time) * 1000
            self.total_latency_ms += latency_ms

            logger.debug("Backward movement: skipping reactive obstacle checks (emergency escape)")

            return ReactiveDecision(
                intervention_type=InterventionType.NONE,
                action="continue",
                metadata={
                    "reason": "Backward movement - obstacle checks skipped for emergency escape",
                    "is_backward": True
                },
                latency_ms=latency_ms
            )

        # Extract Lidar data
        lidar_min = sensor_data.get('lidar', {}).get('lidar_min_distance', float('inf'))
        lidar_distances = sensor_data.get('lidar', {}).get('lidar_distances', [])

        # Calculate hysteresis thresholds
        critical_exit = self.emergency_threshold + self.hysteresis_margin
        moderate_exit = self.detour_threshold + self.hysteresis_margin

        # State machine with hysteresis
        # CRITICAL state: Emergency stop
        if self.current_state == InterventionType.CRITICAL:
            # Stay in CRITICAL until we exceed exit threshold
            if lidar_min < critical_exit:
                latency_ms = (time.time() - start_time) * 1000
                self.total_latency_ms += latency_ms

                decision = ReactiveDecision(
                    intervention_type=InterventionType.CRITICAL,
                    action="emergency_stop",
                    metadata={
                        "lidar_min": lidar_min,
                        "threshold": self.emergency_threshold,
                        "hysteresis": "maintaining CRITICAL state",
                        "reason": f"Obstacle at {lidar_min:.2f}m (hysteresis exit: {critical_exit:.2f}m)"
                    },
                    latency_ms=latency_ms
                )
                return decision
            else:
                # Exit CRITICAL → transition to MODERATE or NONE
                self.current_state = InterventionType.NONE
                logger.info(
                    f"Exiting CRITICAL state via hysteresis (lidar_min={lidar_min:.2f}m >= {critical_exit:.2f}m)"
                )

        # MODERATE state: AI-powered detour
        if self.current_state == InterventionType.MODERATE:
            # Check forward sensor minimum for detour exit condition
            forward_min = self._get_forward_sensor_min(lidar_distances)

            # Check if we should drop to CRITICAL
            if lidar_min < self.emergency_threshold:
                self.current_state = InterventionType.CRITICAL
                self.intervention_count += 1
                latency_ms = (time.time() - start_time) * 1000
                self.total_latency_ms += latency_ms

                decision = ReactiveDecision(
                    intervention_type=InterventionType.CRITICAL,
                    action="emergency_stop",
                    metadata={
                        "lidar_min": lidar_min,
                        "threshold": self.emergency_threshold,
                        "transition": "MODERATE → CRITICAL",
                        "reason": f"Obstacle detected at {lidar_min:.2f}m (< {self.emergency_threshold}m)"
                    },
                    latency_ms=latency_ms
                )

                logger.warning(
                    f"CRITICAL intervention: Emergency stop triggered "
                    f"(lidar_min={lidar_min:.2f}m, latency={latency_ms:.2f}ms)"
                )
                return decision

            # Stay in MODERATE until forward sensors are clear
            if forward_min < moderate_exit:
                if self.enable_ollama and (self.ollama_client or self.openai_client):
                    try:
                        detour_decision = self._quick_detour_decision(sensor_data, target_info)
                        latency_ms = (time.time() - start_time) * 1000
                        self.total_latency_ms += latency_ms

                        decision = ReactiveDecision(
                            intervention_type=InterventionType.MODERATE,
                            action="detour",
                            metadata={
                                "lidar_min": lidar_min,
                                "forward_min": forward_min,
                                "detour_plan": asdict(detour_decision),
                                "ai_provider": self.llm_provider,
                                "model": "gpt-4o-mini" if self.llm_provider == "openai" else self.model_name,
                                "hysteresis": "maintaining MODERATE state"
                            },
                            latency_ms=latency_ms
                        )
                        return decision

                    except Exception as e:
                        logger.error(f"Ollama detour decision failed: {e}. Maintaining speed reduction.")
                        self.ollama_failure_count += 1
                        latency_ms = (time.time() - start_time) * 1000
                        self.total_latency_ms += latency_ms

                        # Maintain MODERATE with default speed reduction
                        decision = ReactiveDecision(
                            intervention_type=InterventionType.MODERATE,
                            action="detour",
                            metadata={
                                "lidar_min": lidar_min,
                                "forward_min": forward_min,
                                "detour_plan": {
                                    "speed_modifier": 0.5,
                                    "confidence": 0.5,
                                    "reasoning": "Ollama failure - default speed reduction"
                                },
                                "ollama_error": str(e)
                            },
                            latency_ms=latency_ms
                        )
                        return decision
                else:
                    # Ollama disabled - emergency stop
                    self.current_state = InterventionType.CRITICAL
                    latency_ms = (time.time() - start_time) * 1000
                    self.intervention_count += 1
                    self.total_latency_ms += latency_ms

                    return ReactiveDecision(
                        intervention_type=InterventionType.CRITICAL,
                        action="emergency_stop",
                        metadata={
                            "lidar_min": lidar_min,
                            "reason": "Ollama disabled - rules-only mode active"
                        },
                        latency_ms=latency_ms
                    )
            else:
                # Exit MODERATE → POST_DETOUR (stabilization phase before multi-agent return)
                self.current_state = InterventionType.POST_DETOUR
                self.stabilization_steps_remaining = self.stabilization_steps
                self.detour_completed_time = time.time()
                logger.info(
                    f"✅ Exiting MODERATE state - Forward sensors clear "
                    f"(forward_min={forward_min:.2f}m >= {moderate_exit:.2f}m, lidar_min={lidar_min:.2f}m) "
                    f"- Entering POST_DETOUR stabilization ({self.stabilization_steps} steps)"
                )

        # POST_DETOUR state: Stabilization phase before returning to multi-agent
        if self.current_state == InterventionType.POST_DETOUR:
            # Check if we should drop to CRITICAL
            if lidar_min < self.emergency_threshold:
                self.current_state = InterventionType.CRITICAL
                self.stabilization_steps_remaining = 0  # Reset counter
                self.intervention_count += 1
                latency_ms = (time.time() - start_time) * 1000
                self.total_latency_ms += latency_ms

                decision = ReactiveDecision(
                    intervention_type=InterventionType.CRITICAL,
                    action="emergency_stop",
                    metadata={
                        "lidar_min": lidar_min,
                        "threshold": self.emergency_threshold,
                        "transition": "POST_DETOUR → CRITICAL",
                        "reason": f"Obstacle detected at {lidar_min:.2f}m during stabilization"
                    },
                    latency_ms=latency_ms
                )

                logger.warning(
                    f"CRITICAL intervention during stabilization: Emergency stop "
                    f"(lidar_min={lidar_min:.2f}m)"
                )
                return decision

            # Continue stabilization with LLM control
            if self.stabilization_steps_remaining > 0:
                self.stabilization_steps_remaining -= 1

                if self.enable_ollama and (self.ollama_client or self.openai_client):
                    try:
                        # Generate stabilization action using LLM
                        stabilization_decision = self._quick_detour_decision(sensor_data, target_info)
                        latency_ms = (time.time() - start_time) * 1000
                        self.total_latency_ms += latency_ms

                        decision = ReactiveDecision(
                            intervention_type=InterventionType.POST_DETOUR,
                            action="stabilize",
                            metadata={
                                "lidar_min": lidar_min,
                                "stabilization_plan": asdict(stabilization_decision),
                                "steps_remaining": self.stabilization_steps_remaining,
                                "ai_provider": self.llm_provider,
                                "model": "gpt-4o-mini" if self.llm_provider == "openai" else self.model_name,
                                "reason": f"Post-detour stabilization ({self.stabilization_steps_remaining} steps left)"
                            },
                            latency_ms=latency_ms
                        )

                        logger.info(
                            f"🔧 POST_DETOUR stabilization: {self.stabilization_steps_remaining} steps remaining "
                            f"(lidar_min={lidar_min:.2f}m)"
                        )
                        return decision

                    except Exception as e:
                        logger.error(f"LLM stabilization decision failed: {e}. Using default behavior.")
                        latency_ms = (time.time() - start_time) * 1000
                        self.total_latency_ms += latency_ms

                        # Fallback: continue with reduced speed
                        decision = ReactiveDecision(
                            intervention_type=InterventionType.POST_DETOUR,
                            action="stabilize",
                            metadata={
                                "lidar_min": lidar_min,
                                "stabilization_plan": {
                                    "speed_modifier": 0.7,
                                    "confidence": 0.5,
                                    "reasoning": "LLM failure - default stabilization"
                                },
                                "steps_remaining": self.stabilization_steps_remaining,
                                "llm_error": str(e)
                            },
                            latency_ms=latency_ms
                        )
                        return decision

            # Stabilization complete → Resume multi-agent plan
            if self.stabilization_steps_remaining == 0:
                self.current_state = InterventionType.NONE
                logger.info(
                    f"✅ Stabilization complete - Resuming multi-agent plan "
                    f"(lidar_min={lidar_min:.2f}m)"
                )

        # Check for new state entry (from NONE)
        # Enter CRITICAL?
        if lidar_min < self.emergency_threshold:
            self.current_state = InterventionType.CRITICAL
            latency_ms = (time.time() - start_time) * 1000
            self.intervention_count += 1
            self.total_latency_ms += latency_ms

            decision = ReactiveDecision(
                intervention_type=InterventionType.CRITICAL,
                action="emergency_stop",
                metadata={
                    "lidar_min": lidar_min,
                    "threshold": self.emergency_threshold,
                    "transition": "NONE → CRITICAL",
                    "reason": f"Obstacle detected at {lidar_min:.2f}m (< {self.emergency_threshold}m)"
                },
                latency_ms=latency_ms
            )

            logger.warning(
                f"CRITICAL intervention: Emergency stop triggered "
                f"(lidar_min={lidar_min:.2f}m, latency={latency_ms:.2f}ms)"
            )
            return decision

        # Enter MODERATE?
        if lidar_min < self.detour_threshold:
            self.current_state = InterventionType.MODERATE
            if self.enable_ollama and (self.ollama_client or self.openai_client):
                try:
                    detour_decision = self._quick_detour_decision(sensor_data, target_info)
                    latency_ms = (time.time() - start_time) * 1000
                    self.intervention_count += 1
                    self.total_latency_ms += latency_ms

                    decision = ReactiveDecision(
                        intervention_type=InterventionType.MODERATE,
                        action="detour",
                        metadata={
                            "lidar_min": lidar_min,
                            "detour_plan": asdict(detour_decision),
                            "ai_provider": self.llm_provider,
                            "model": "gpt-4o-mini" if self.llm_provider == "openai" else self.model_name,
                            "transition": "NONE → MODERATE"
                        },
                        latency_ms=latency_ms
                    )

                    logger.info(
                        f"MODERATE intervention: AI detour activated "
                        f"(lidar_min={lidar_min:.2f}m, latency={latency_ms:.2f}ms)"
                    )
                    return decision

                except Exception as e:
                    logger.error(
                        f"Ollama detour decision failed: {e}. "
                        f"Falling back to CRITICAL mode."
                    )
                    self.ollama_failure_count += 1
                    self.current_state = InterventionType.CRITICAL
                    latency_ms = (time.time() - start_time) * 1000
                    self.intervention_count += 1
                    self.total_latency_ms += latency_ms

                    return ReactiveDecision(
                        intervention_type=InterventionType.CRITICAL,
                        action="emergency_stop",
                        metadata={
                            "lidar_min": lidar_min,
                            "reason": "Ollama failure - graceful degradation to emergency stop",
                            "ollama_error": str(e)
                        },
                        latency_ms=latency_ms
                    )
            else:
                # Ollama disabled - fallback to emergency stop
                self.current_state = InterventionType.CRITICAL
                latency_ms = (time.time() - start_time) * 1000
                self.intervention_count += 1
                self.total_latency_ms += latency_ms

                return ReactiveDecision(
                    intervention_type=InterventionType.CRITICAL,
                    action="emergency_stop",
                    metadata={
                        "lidar_min": lidar_min,
                        "reason": "Ollama disabled - rules-only mode active"
                    },
                    latency_ms=latency_ms
                )

        # Level 3: NORMAL - No intervention (Lidar >= 0.3m, same as CRITICAL threshold)
        self.current_state = InterventionType.NONE
        latency_ms = (time.time() - start_time) * 1000
        self.total_latency_ms += latency_ms

        decision = ReactiveDecision(
            intervention_type=InterventionType.NONE,
            action="continue",
            metadata={
                "lidar_min": lidar_min,
                "reason": "Path clear - no intervention needed"
            },
            latency_ms=latency_ms
        )

        return decision

    def _quick_detour_decision(
        self,
        sensor_data: Dict[str, Any],
        target_info: Optional[Dict[str, float]] = None
    ) -> DetourPlan:
        """
        Generate AI-powered detour plan using LLM with target awareness.

        Uses structured prompt with target destination and recent history
        to generate intelligent detour decisions.

        Args:
            sensor_data: Current sensor readings
            target_info: Optional target information for smart detour
                {
                    'target_x': float,
                    'target_y': float,
                    'current_x': float,
                    'current_y': float,
                    'current_yaw': float
                }

        Returns:
            DetourPlan with detour_x, detour_y, speed_modifier, confidence, reasoning

        Raises:
            Exception: If LLM call fails or JSON parsing fails
        """
        if not self.ollama_client and not self.openai_client:
            raise RuntimeError("No LLM client initialized")

        start_time = time.time()

        # Extract sensor data
        lidar_data = sensor_data.get('lidar', {})
        gps_data = sensor_data.get('gps', {})
        imu_data = sensor_data.get('imu', {})

        lidar_min = lidar_data.get('lidar_min_distance', 0.0)
        lidar_avg = lidar_data.get('lidar_avg_distance', 0.0)
        position_x = gps_data.get('position_x', 0.0)
        position_y = gps_data.get('position_y', 0.0)
        yaw = imu_data.get('yaw', 0.0)

        # Story 3.1 Re-Review Action Item 1: Check cache first
        cache_key = None  # Initialize cache key
        lidar_distances = lidar_data.get('lidar_distances', [])
        if lidar_distances:
            # Generate cache key from sensor pattern
            # Sample every 10th lidar point to reduce key size (512 points -> ~51 points)
            lidar_pattern = tuple(lidar_distances[::10])
            cache_key = hash((lidar_min, lidar_pattern))

            # Check cache
            if cache_key in self.detour_cache:
                self.cache_hits += 1
                cached_plan = self.detour_cache[cache_key]
                hit_rate = self.cache_hits / (self.cache_hits + self.cache_misses)
                logger.debug(
                    f"Ollama cache HIT (hit_rate={hit_rate:.1%}, "
                    f"cache_size={len(self.detour_cache)})"
                )
                return cached_plan

            # Cache miss - will call Ollama
            self.cache_misses += 1
            logger.debug(
                f"Ollama cache MISS (hit_rate={self.cache_hits/(self.cache_hits+self.cache_misses):.1%})"
            )

        # Check cooldown - reuse last detour if called too recently
        time_since_last_call = time.time() - self.last_ollama_call_time
        if self.last_detour_plan is not None and time_since_last_call < self.ollama_cooldown_seconds:
            logger.info(
                f"⏱ Ollama cooldown active ({time_since_last_call:.1f}s / {self.ollama_cooldown_seconds}s), "
                f"reusing last detour (allows multi-agent plan to resume after detour)"
            )
            return self.last_detour_plan

        # Calculate left/right sensor clearance for detour decision
        raw_left_clearance = self._get_left_sensor_avg(lidar_distances)  # 45°-135°
        raw_right_clearance = self._get_right_sensor_avg(lidar_distances)  # 225°-315°

        # Handle inf values - treat as completely clear (very large distance)
        # inf means sensor max range exceeded = no obstacles = safe to go
        if raw_left_clearance == float('inf'):
            raw_left_clearance = 10.0  # Treat as very clear (safe)
        if raw_right_clearance == float('inf'):
            raw_right_clearance = 10.0  # Treat as very clear (safe)

        # Debug log to verify sensor readings
        # Now using front diagonal angles - these are intuitive (no swap needed)
        left_clearance = raw_left_clearance   # Left-front diagonal (30°-60°)
        right_clearance = raw_right_clearance # Right-front diagonal (300°-330°)

        logger.info(f"🔍 Sensor clearance: Left(30°-60°)={left_clearance:.2f}m, Right(300°-330°)={right_clearance:.2f}m")

        # Build detour prompt with target info and history
        prompt = self._build_detour_prompt(
            lidar_min=lidar_min,
            lidar_avg=lidar_avg,
            position=(position_x, position_y),
            yaw=yaw,
            left_clearance=left_clearance,
            right_clearance=right_clearance,
            target_info=target_info
        )

        # Call LLM (Ollama or OpenAI)
        try:
            llm_start = time.time()

            if self.llm_provider == "openai" and self.openai_client:
                # OpenAI provider - faster, no timeout needed
                logger.info(f"🤖 Calling OpenAI (gpt-4o-mini) for detour decision...")

                response = self.openai_client.invoke(prompt)
                response_text = response.content.strip()

                logger.info(f"⏱ OpenAI responded in {time.time() - llm_start:.2f}s")
                self.ollama_call_count += 1

            elif self.llm_provider == "ollama" and self.ollama_client:
                # Ollama provider - requires timeout
                import threading

                logger.info(f"🤖 Calling Ollama ({self.model_name}) for detour decision...")

                response_container = {}
                exception_container = {}

                def ollama_call():
                    try:
                        response_container['result'] = self.ollama_client.generate(
                            model=self.model_name,
                            prompt=prompt,
                            options={'temperature': 0.1}  # Low temp for consistent output
                        )
                    except Exception as e:
                        exception_container['error'] = e

                # Run Ollama call in separate thread with 30 second timeout
                # Note: tinyllama can take 20+ seconds on CPU mode
                thread = threading.Thread(target=ollama_call, daemon=True)
                thread.start()
                thread.join(timeout=30.0)  # 30 second timeout

                ollama_elapsed = time.time() - llm_start
                logger.info(f"⏱ Ollama thread joined after {ollama_elapsed:.2f}s")

                if thread.is_alive():
                    # Timeout occurred
                    raise TimeoutError("Ollama call exceeded 30 second timeout")

                if 'error' in exception_container:
                    raise exception_container['error']

                if 'result' not in response_container:
                    raise RuntimeError("Ollama call completed but no response received")

                response = response_container['result']
                self.ollama_call_count += 1

                # Parse Ollama response
                response_text = response['response'].strip()
            else:
                raise RuntimeError(f"Invalid LLM provider state: {self.llm_provider}")

            # Parse response (handle markdown code blocks)
            detour_data = self._parse_llm_response(response_text)

            # If parsing failed, ask LLM to reformat (retry once)
            if detour_data is None:
                logger.warning(f"JSON parsing failed, asking LLM to reformat...")
                reformat_prompt = f"""Your previous response was not valid JSON. Please reformat this response as valid JSON only:

{response_text}

OUTPUT FORMAT (JSON only, no other text):
{{
  "detour_x": <number>,
  "detour_y": <number>,
  "speed_modifier": <number>,
  "confidence": <number>,
  "reasoning": "<string>"
}}"""

                # Call LLM for reformat
                if self.llm_provider == "openai" and self.openai_client:
                    reformat_response = self.openai_client.invoke(reformat_prompt)
                    response_text = reformat_response.content.strip()
                elif self.llm_provider == "ollama" and self.ollama_client:
                    reformat_response = self.ollama_client.generate(
                        model=self.model_name,
                        prompt=reformat_prompt,
                        options={'temperature': 0.0}
                    )
                    response_text = reformat_response['response'].strip()

                # Try parsing again
                detour_data = self._parse_llm_response(response_text)

                if detour_data is None:
                    raise RuntimeError(f"Failed to parse JSON even after reformat. Response: {response_text[:200]}")

            # Validate and construct DetourPlan
            detour_plan = DetourPlan(
                detour_x=float(detour_data.get('detour_x', 0.0)),
                detour_y=float(detour_data.get('detour_y', 0.0)),
                speed_modifier=float(detour_data.get('speed_modifier', 0.5)),
                confidence=float(detour_data.get('confidence', 0.0)),
                reasoning=str(detour_data.get('reasoning', 'AI-generated detour'))
            )

            # Story 3.1 Re-Review Action Item 1: Store in cache (LRU eviction if > 50)
            if cache_key is not None:
                if len(self.detour_cache) >= 50:
                    # Remove oldest entry (FIFO-style eviction for simplicity)
                    evicted_key = next(iter(self.detour_cache))
                    self.detour_cache.pop(evicted_key)
                    logger.debug(f"Evicted cache entry (cache was full at 50 items)")

                self.detour_cache[cache_key] = detour_plan
                logger.debug(
                    f"Stored detour plan in cache (cache_size={len(self.detour_cache)})"
                )

            # Update cooldown tracking
            self.last_ollama_call_time = time.time()
            self.last_detour_plan = detour_plan

            # Record detour decision in history (for future context)
            self._record_detour_history(detour_plan, lidar_min, target_info)

            latency_ms = (time.time() - start_time) * 1000

            # Log LLM decision for debugging
            direction_str = "LEFT" if detour_plan.detour_y > 0 else "RIGHT"
            logger.info(
                f"🧠 LLM Decision: direction={direction_str} (dy={detour_plan.detour_y:.2f}m), "
                f"dx={detour_plan.detour_x:.2f}m, speed={detour_plan.speed_modifier:.1%}, "
                f"reasoning: {detour_plan.reasoning}"
            )

            logger.debug(
                f"Ollama detour decision generated "
                f"(latency={latency_ms:.2f}ms, confidence={detour_plan.confidence:.2f})"
            )

            return detour_plan

        except KeyError:
            # Handle response structure error
            raise RuntimeError(
                "Ollama response missing 'response' key. "
                "Check ollama.Client API version."
            )
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"Failed to parse Ollama JSON response: {e}. "
                f"Response text: {response_text[:200]}"
            )
        except Exception as e:
            raise RuntimeError(f"Ollama detour decision failed: {e}")

    def _parse_llm_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """
        Parse LLM response text to extract JSON detour data.

        Args:
            response_text: Raw response text from LLM

        Returns:
            Parsed JSON dict if successful, None if parsing fails
        """
        try:
            text = response_text.strip()

            # Strip markdown code blocks (TinyLlama behavior from Story 3.0)
            if text.startswith("```"):
                lines = text.split('\n')
                if lines[0].strip().startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                text = '\n'.join(lines).strip()

            # Try to extract JSON from response (LLM sometimes adds explanatory text)
            # Look for JSON object pattern: {...}
            json_start = text.find('{')
            json_end = text.rfind('}')
            if json_start != -1 and json_end != -1 and json_end > json_start:
                text = text[json_start:json_end+1]

            # Parse JSON
            return json.loads(text)

        except json.JSONDecodeError:
            return None
        except Exception:
            return None

    def _build_detour_prompt(
        self,
        lidar_min: float,
        lidar_avg: float,
        position: tuple[float, float],
        yaw: float,
        left_clearance: float,
        right_clearance: float,
        target_info: Optional[Dict[str, float]] = None
    ) -> str:
        """
        Build structured prompt for LLM detour decision with target awareness.

        Args:
            lidar_min: Minimum Lidar distance in meters
            lidar_avg: Average Lidar distance in meters
            position: Current (x, y) position
            yaw: Current yaw angle in degrees
            left_clearance: Average clearance on left side (meters)
            right_clearance: Average clearance on right side (meters)
            target_info: Optional target and position info for smart detour
                {
                    'target_x': float,
                    'target_y': float,
                    'current_x': float,
                    'current_y': float,
                    'current_yaw': float  # degrees
                }

        Returns:
            Structured prompt string requesting JSON detour plan
        """
        import math

        # Build target context if available
        target_context = ""
        if target_info:
            target_x = target_info.get('target_x', 0.0)
            target_y = target_info.get('target_y', 0.0)
            current_x = target_info.get('current_x', position[0])
            current_y = target_info.get('current_y', position[1])
            current_yaw_deg = target_info.get('current_yaw', yaw)

            # Calculate relative direction to target
            dx = target_x - current_x
            dy = target_y - current_y
            distance_to_target = math.sqrt(dx**2 + dy**2)

            # Target angle in world frame (Math convention: 0°=East, CCW positive)
            target_angle_world = math.degrees(math.atan2(dy, dx))

            # Relative angle: positive = target is to the LEFT, negative = to the RIGHT
            relative_angle = target_angle_world - current_yaw_deg
            # Normalize to [-180, 180]
            while relative_angle > 180:
                relative_angle -= 360
            while relative_angle < -180:
                relative_angle += 360

            # Determine target direction description
            if abs(relative_angle) < 30:
                target_dir = "AHEAD"
            elif relative_angle > 0:
                target_dir = f"LEFT ({relative_angle:.0f}°)"
            else:
                target_dir = f"RIGHT ({relative_angle:.0f}°)"

            target_context = f"""
TARGET DESTINATION:
- Target position: ({target_x:.2f}, {target_y:.2f})
- Current position: ({current_x:.2f}, {current_y:.2f})
- Distance to target: {distance_to_target:.2f}m
- Target direction: {target_dir} (relative angle: {relative_angle:.0f}°)
- HINT: If target is to the LEFT, prefer LEFT detour. If target is to the RIGHT, prefer RIGHT detour.
"""

        # Build history context if available
        history_context = ""
        if self.detour_history:
            recent_detours = self.detour_history[-5:]  # Last 5 detours
            history_lines = []
            for i, detour in enumerate(recent_detours, 1):
                direction = "LEFT" if detour.get('detour_y', 0) > 0 else "RIGHT"
                history_lines.append(
                    f"  {i}. {direction} detour (dy={detour.get('detour_y', 0):.2f}m) - {detour.get('reasoning', 'N/A')}"
                )
            history_context = f"""
RECENT DETOUR HISTORY (last {len(recent_detours)}):
{chr(10).join(history_lines)}
- WARNING: If same direction keeps failing, consider the OTHER direction!
"""

        prompt = f"""You are a robot navigation AI. An obstacle is detected and you must decide the best detour direction.

CURRENT SITUATION:
- Obstacle distance: {lidar_min:.2f}m ahead (DANGER!)
- Current heading: {yaw:.0f}° (Math convention: 0°=East, 90°=North)
- Left-front clearance (30°-60°): {left_clearance:.2f}m
- Right-front clearance (300°-330°): {right_clearance:.2f}m
{target_context}{history_context}
YOUR TASK:
Decide the best detour direction considering:
1. Sensor clearance (which side has more space?)
2. Target direction (prefer detour toward target if safe)
3. Recent history (avoid repeating failed patterns)

COORDINATE SYSTEM:
- detour_y POSITIVE = move LEFT (in robot's local frame)
- detour_y NEGATIVE = move RIGHT (in robot's local frame)
- detour_x: forward distance (0.3-0.5m typical)

OUTPUT FORMAT (JSON only, no explanation outside JSON):
{{
  "detour_x": <0.3 to 0.5>,
  "detour_y": <-0.5 to 0.5, positive=LEFT, negative=RIGHT>,
  "speed_modifier": <0.5 to 0.8>,
  "confidence": <0.0 to 1.0>,
  "reasoning": "<brief explanation of your decision>"
}}"""

        return prompt

    def _record_detour_history(
        self,
        detour_plan: DetourPlan,
        lidar_min: float,
        target_info: Optional[Dict[str, float]] = None
    ) -> None:
        """
        Record detour decision in history for future context.

        Args:
            detour_plan: The detour plan that was decided
            lidar_min: Obstacle distance at time of decision
            target_info: Target information if available
        """
        history_entry = {
            'timestamp': time.time(),
            'detour_x': detour_plan.detour_x,
            'detour_y': detour_plan.detour_y,
            'speed_modifier': detour_plan.speed_modifier,
            'confidence': detour_plan.confidence,
            'reasoning': detour_plan.reasoning,
            'lidar_min': lidar_min
        }

        # Add target info if available
        if target_info:
            history_entry['target_x'] = target_info.get('target_x')
            history_entry['target_y'] = target_info.get('target_y')

        self.detour_history.append(history_entry)

        # Keep only last N entries
        if len(self.detour_history) > self.max_detour_history:
            self.detour_history = self.detour_history[-self.max_detour_history:]

        logger.debug(
            f"Recorded detour in history (total: {len(self.detour_history)}, "
            f"direction={'LEFT' if detour_plan.detour_y > 0 else 'RIGHT'})"
        )

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get controller performance statistics.

        Returns:
            Dictionary with intervention counts, latencies, and Ollama stats
        """
        avg_latency_ms = (
            self.total_latency_ms / max(self.intervention_count + self.ollama_call_count, 1)
        )

        # Story 3.1 Re-Review Action Item 1: Add cache statistics
        total_cache_requests = self.cache_hits + self.cache_misses
        cache_hit_rate = (
            self.cache_hits / total_cache_requests
            if total_cache_requests > 0 else 0.0
        )

        return {
            "intervention_count": self.intervention_count,
            "ollama_call_count": self.ollama_call_count,
            "ollama_failure_count": self.ollama_failure_count,
            "ollama_success_rate": (
                (self.ollama_call_count - self.ollama_failure_count) / max(self.ollama_call_count, 1)
                if self.ollama_call_count > 0 else 0.0
            ),
            "avg_latency_ms": avg_latency_ms,
            "total_latency_ms": self.total_latency_ms,
            "ollama_enabled": self.enable_ollama,
            # Cache statistics
            "cache_size": len(self.detour_cache),
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": cache_hit_rate
        }

    def reset_statistics(self):
        """Reset performance statistics counters and state."""
        self.intervention_count = 0
        self.ollama_call_count = 0
        self.ollama_failure_count = 0
        self.total_latency_ms = 0.0
        # Story 3.1 Re-Review Action Item 1: Reset cache statistics
        self.cache_hits = 0
        self.cache_misses = 0
        # Reset hysteresis state
        self.current_state = InterventionType.NONE
        # Note: detour_cache dictionary is NOT cleared (cache content preserved)
        # Reset detour history (Option B: smart detour with history)
        self.detour_history = []
