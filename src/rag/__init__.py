"""
RAG (Retrieval-Augmented Generation) module for robot knowledge base.

This module provides ChromaDB-based vector storage for:
- Robot capabilities (speed limits, sensor ranges, movement constraints)
- Environment constraints (safe zones, obstacle information, boundaries)
"""

from .knowledge_base import RobotKnowledgeBase

__all__ = ["RobotKnowledgeBase"]
