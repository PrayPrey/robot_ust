"""
Environment Map Loader

Loads and parses external environment data from JSON files.
Provides obstacle locations, safe zones, and navigation constraints.
"""

import json
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from pydantic import BaseModel, Field, field_validator
from loguru import logger


class Obstacle(BaseModel):
    """
    Environment obstacle definition.
    """
    id: str = Field(description="Unique obstacle identifier")
    type: str = Field(description="Obstacle type (box, cylinder, sphere)")
    position: Tuple[float, float, float] = Field(description="XYZ position in meters")
    size: Tuple[float, float, float] = Field(description="Dimensions (width, depth, height)")
    is_static: bool = Field(default=True, description="Whether obstacle is static")


class SafeZone(BaseModel):
    """
    Safe zone definition for robot operation.
    """
    id: str = Field(description="Zone identifier")
    center: Tuple[float, float] = Field(description="Zone center (X, Y)")
    radius: float = Field(gt=0.0, description="Zone radius in meters")
    description: Optional[str] = Field(default=None, description="Zone description")


class DangerZone(BaseModel):
    """
    Danger zone to avoid.
    """
    id: str = Field(description="Zone identifier")
    center: Tuple[float, float] = Field(description="Zone center (X, Y)")
    radius: float = Field(gt=0.0, description="Zone radius in meters")
    severity: str = Field(default="high", pattern="^(low|medium|high)$")


class EnvironmentMap(BaseModel):
    """
    Complete environment map with obstacles and zones.
    """
    map_id: str = Field(description="Map identifier")
    map_name: str = Field(description="Human-readable map name")
    dimensions: Tuple[float, float, float] = Field(
        description="Environment dimensions (width, depth, height)"
    )

    obstacles: List[Obstacle] = Field(default_factory=list)
    safe_zones: List[SafeZone] = Field(default_factory=list)
    danger_zones: List[DangerZone] = Field(default_factory=list)

    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @field_validator("dimensions")
    @classmethod
    def validate_dimensions(cls, v: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """Validate environment dimensions are positive."""
        if any(d <= 0 for d in v):
            raise ValueError("All dimensions must be positive")
        return v

    def get_obstacles_near(self, position: Tuple[float, float], radius: float) -> List[Obstacle]:
        """
        Get obstacles within radius of position.

        Args:
            position: XY position
            radius: Search radius in meters

        Returns:
            List of nearby obstacles
        """
        nearby = []
        for obs in self.obstacles:
            dx = obs.position[0] - position[0]
            dy = obs.position[1] - position[1]
            distance = (dx**2 + dy**2) ** 0.5

            if distance <= radius:
                nearby.append(obs)

        return nearby

    def is_in_safe_zone(self, position: Tuple[float, float]) -> bool:
        """
        Check if position is in any safe zone.

        Args:
            position: XY position

        Returns:
            True if in safe zone
        """
        for zone in self.safe_zones:
            dx = position[0] - zone.center[0]
            dy = position[1] - zone.center[1]
            distance = (dx**2 + dy**2) ** 0.5

            if distance <= zone.radius:
                return True

        return False

    def is_in_danger_zone(self, position: Tuple[float, float]) -> Optional[DangerZone]:
        """
        Check if position is in danger zone.

        Args:
            position: XY position

        Returns:
            DangerZone if in danger, None otherwise
        """
        for zone in self.danger_zones:
            dx = position[0] - zone.center[0]
            dy = position[1] - zone.center[1]
            distance = (dx**2 + dy**2) ** 0.5

            if distance <= zone.radius:
                return zone

        return None

    def get_nearest_obstacle(self, position: Tuple[float, float]) -> Optional[Tuple[Obstacle, float]]:
        """
        Find nearest obstacle to position.

        Args:
            position: XY position

        Returns:
            (Obstacle, distance) tuple or None if no obstacles
        """
        if not self.obstacles:
            return None

        nearest = None
        min_distance = float('inf')

        for obs in self.obstacles:
            dx = obs.position[0] - position[0]
            dy = obs.position[1] - position[1]
            distance = (dx**2 + dy**2) ** 0.5

            if distance < min_distance:
                min_distance = distance
                nearest = obs

        return (nearest, min_distance) if nearest else None


class EnvironmentMapLoader:
    """
    Loader for environment map JSON files.
    """

    @staticmethod
    def load_from_file(file_path: str) -> EnvironmentMap:
        """
        Load environment map from JSON file.

        Args:
            file_path: Path to JSON file

        Returns:
            EnvironmentMap instance

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If JSON is invalid
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Environment map not found: {file_path}")

        logger.info(f"Loading environment map from {file_path}")

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            env_map = EnvironmentMap(**data)

            logger.info(
                f"Loaded map '{env_map.map_name}' with "
                f"{len(env_map.obstacles)} obstacles, "
                f"{len(env_map.safe_zones)} safe zones, "
                f"{len(env_map.danger_zones)} danger zones"
            )

            return env_map

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {file_path}: {e}")
            raise ValueError(f"Invalid JSON: {e}")
        except Exception as e:
            logger.error(f"Failed to load environment map: {e}")
            raise

    @staticmethod
    def create_sample_map(output_path: str) -> None:
        """
        Create a sample environment map JSON file.

        Args:
            output_path: Where to save sample map
        """
        sample_map = {
            "map_id": "rescue_environment_001",
            "map_name": "Rescue Robot Test Environment",
            "dimensions": [10.0, 10.0, 3.0],
            "obstacles": [
                {
                    "id": "wall_north",
                    "type": "box",
                    "position": [0.0, 5.0, 0.5],
                    "size": [10.0, 0.2, 1.0],
                    "is_static": True
                },
                {
                    "id": "debris_1",
                    "type": "box",
                    "position": [2.0, 2.0, 0.3],
                    "size": [1.0, 1.0, 0.6],
                    "is_static": True
                },
                {
                    "id": "pillar_1",
                    "type": "cylinder",
                    "position": [-2.0, -2.0, 1.0],
                    "size": [0.5, 0.5, 2.0],
                    "is_static": True
                }
            ],
            "safe_zones": [
                {
                    "id": "start_zone",
                    "center": [0.0, 0.0],
                    "radius": 1.5,
                    "description": "Robot starting area"
                },
                {
                    "id": "safe_zone_east",
                    "center": [3.0, 0.0],
                    "radius": 2.0,
                    "description": "Eastern safe area"
                }
            ],
            "danger_zones": [
                {
                    "id": "collapse_risk_1",
                    "center": [-3.0, 3.0],
                    "radius": 1.5,
                    "severity": "high"
                },
                {
                    "id": "unstable_floor",
                    "center": [4.0, -4.0],
                    "radius": 1.0,
                    "severity": "medium"
                }
            ],
            "metadata": {
                "created_by": "RobotKnowledgeBase",
                "version": "1.0",
                "coordinate_system": "meters",
                "origin": "center"
            }
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(sample_map, f, indent=2, ensure_ascii=False)

        logger.info(f"Sample environment map created: {output_path}")
