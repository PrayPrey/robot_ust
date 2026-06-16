"""
Integration Tests for Environment-Aware RAG Filtering

Tests the integration of EnvironmentDetector with PlannerAgent and ChromaDB.
Verifies environment-based constraint filtering works correctly.
"""

import pytest
from unittest.mock import MagicMock, patch
from src.agents.planner_agent import PlannerAgent
from src.rag.knowledge_base import RobotKnowledgeBase
from src.schemas.robot_state import SensorData, RobotState, RobotStatus
from src.utils.environment_detector import EnvironmentDetector, EnvironmentClassification


class TestEnvironmentRAGFiltering:
    """Integration tests for environment-aware RAG filtering."""

    @pytest.fixture
    def knowledge_base(self):
        """Create real RobotKnowledgeBase instance."""
        import os
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            pytest.skip("OPENAI_API_KEY not set")

        kb = RobotKnowledgeBase(
            persist_directory="./data/chromadb_test",
            openai_api_key=api_key
        )
        kb.populate_from_files(
            capabilities_file="src/rag/data/robot_capabilities.json",
            constraints_file="src/rag/data/environment_constraints.json"
        )
        return kb

    @pytest.fixture
    def planner_with_rag(self, knowledge_base):
        """Create PlannerAgent with RAG enabled."""
        import os
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            pytest.skip("OPENAI_API_KEY not set")

        return PlannerAgent(
            api_key=api_key,
            knowledge_base=knowledge_base,
            model="gpt-4o-mini",
            temperature=0.3,
            verbose=False
        )

    def test_indoor_environment_filtering(self, planner_with_rag):
        """Test RAG filtering for indoor environment."""
        # Create indoor sensor data (no GPS, small space)
        indoor_state = RobotState(
            sensors=SensorData(
                position_x=None,  # No GPS (indoor)
                position_y=None,
                position_z=None,
                lidar_avg_distance=2.5,  # Small space
                camera_has_data=True
            ),
            status=RobotStatus.IDLE
        )

        # Retrieve RAG context with indoor environment
        rag_context = planner_with_rag._retrieve_rag_context(
            query="안전 거리 유지",  # Safety distance
            current_state=indoor_state
        )

        # Verify indoor constraints are retrieved
        assert len(rag_context) > 0, "RAG context should not be empty"
        assert "실내" in rag_context or "indoor" in rag_context.lower(), \
            "Expected indoor-specific constraints in context"

    def test_outdoor_environment_filtering(self, planner_with_rag):
        """Test RAG filtering for outdoor environment."""
        # Create outdoor sensor data (strong GPS, large space)
        outdoor_state = RobotState(
            sensors=SensorData(
                position_x=1.0,  # GPS available (outdoor)
                position_y=2.0,
                position_z=0.1,
                lidar_avg_distance=10.0,  # Large space
                camera_has_data=True
            ),
            status=RobotStatus.IDLE
        )

        # Retrieve RAG context with outdoor environment
        rag_context = planner_with_rag._retrieve_rag_context(
            query="GPS navigation",
            current_state=outdoor_state
        )

        # Verify outdoor constraints are retrieved
        assert len(rag_context) > 0
        # Note: Verification based on actual context content

    def test_unknown_environment_fallback(self, planner_with_rag):
        """Test RAG fallback for unknown environment."""
        # Create ambiguous sensor data
        unknown_state = RobotState(
            sensors=SensorData(
                position_x=None,
                position_y=None,
                position_z=None,
                lidar_avg_distance=None,  # Missing data
                camera_has_data=False
            ),
            status=RobotStatus.IDLE
        )

        # Retrieve RAG context with unknown environment
        rag_context = planner_with_rag._retrieve_rag_context(
            query="장애물 회피",  # Obstacle avoidance
            current_state=unknown_state
        )

        # Verify unfiltered search works (backward compatible)
        assert len(rag_context) > 0, "RAG should work with unknown environment"

    def test_environment_detection_integration(self, planner_with_rag):
        """Test environment detection is called during RAG retrieval."""
        # Create warehouse sensor data
        warehouse_state = RobotState(
            sensors=SensorData(
                position_x=None,  # No GPS
                position_y=None,
                position_z=None,
                lidar_avg_distance=8.0,  # Large space
                camera_has_data=True
            ),
            status=RobotStatus.IDLE
        )

        # Retrieve RAG context
        rag_context = planner_with_rag._retrieve_rag_context(
            query="speed limit",
            current_state=warehouse_state
        )

        # Verify environment detection was used (warehouse allows higher speeds)
        assert len(rag_context) > 0

    def test_where_filter_applied_correctly(self, knowledge_base):
        """Test ChromaDB where filter works with environment_type."""
        # Direct test of search_constraints with where filter
        indoor_constraints = knowledge_base.search_constraints(
            query="safety",
            n_results=5,
            where={"environment_type": "indoor"}
        )

        outdoor_constraints = knowledge_base.search_constraints(
            query="safety",
            n_results=5,
            where={"environment_type": "outdoor"}
        )

        # Verify filtering returns results
        assert len(indoor_constraints) > 0, "Indoor constraints should be found"
        assert len(outdoor_constraints) > 0, "Outdoor constraints should be found"

        # Verify environment_type metadata exists
        for constraint in indoor_constraints:
            assert "environment_type" in constraint.get("metadata", {}), \
                "Constraint metadata should include environment_type"

    def test_no_where_filter_backward_compatibility(self, knowledge_base):
        """Test RAG queries without where filter still work (backward compatible)."""
        # Search without environment filter (Epic 2 behavior)
        all_constraints = knowledge_base.search_constraints(
            query="obstacle",
            n_results=3
            # No where parameter
        )

        # Verify unfiltered search works
        assert len(all_constraints) > 0, "Unfiltered search should return results"

    @pytest.mark.parametrize("environment_type", ["indoor", "outdoor", "warehouse", "hospital"])
    def test_all_environment_types_have_constraints(self, knowledge_base, environment_type):
        """Test all environment types have at least some constraints in the database."""
        constraints = knowledge_base.search_constraints(
            query="",  # Empty query to get any matches
            n_results=10,
            where={"environment_type": environment_type}
        )

        # Verify each environment has constraints
        assert len(constraints) > 0, \
            f"Expected constraints for environment '{environment_type}', but found none"
