"""
Safety module for robot collision avoidance and constraint validation.

This module provides safety validation for robot actions to prevent
collisions, enforce speed limits, and maintain safe operating zones.
"""

from .constraints import SafetyConstraints
from .safety_validator import SafetyValidator

__all__ = ["SafetyConstraints", "SafetyValidator"]
