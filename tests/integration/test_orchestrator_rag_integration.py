"""
Integration test for Orchestrator with RAG (Story 3.3)

Tests that the Orchestrator properly initializes and integrates RobotKnowledgeBase
for environment-aware planning.
"""

import pytest
import os
from unittest.mock import MagicMock
from src.orchestrator import MissionOrchestrator, OrchestratorFactory


@pytest.fixture
def mock_robot():
    """Create a mock Webots Robot instance."""
    robot = MagicMock()
    robot.getTime.return_value = 0.0
    return robot


@pytest.fixture
def api_key():
    """Get API key from environment."""
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        pytest.skip("OPENAI_API_KEY not set")
    return key


class TestOrchestratorRAGIntegration:
    """Test RAG integration in Orchestrator."""

    def test_orchestrator_initializes_with_rag_enabled(self, mock_robot, api_key):
        """Test that Orchestrator initializes with RAG enabled by default."""
        # Create orchestrator with RAG enabled
        orchestrator = MissionOrchestrator(
            robot=mock_robot,
            api_key=api_key,
            enable_rag=True,
            rag_persist_directory="./data/chromadb_test",
            verbose=False
        )

        # Verify planner has knowledge_base
        assert orchestrator.planner.knowledge_base is not None, \
            "PlannerAgent should have knowledge_base when RAG is enabled"

        # Verify knowledge base is populated
        assert orchestrator.planner.knowledge_base.capabilities_collection.count() > 0, \
            "Capabilities collection should be populated"
        assert orchestrator.planner.knowledge_base.constraints_collection.count() > 0, \
            "Constraints collection should be populated"

    def test_orchestrator_initializes_without_rag(self, mock_robot, api_key):
        """Test that Orchestrator can initialize with RAG disabled."""
        # Create orchestrator with RAG disabled
        orchestrator = MissionOrchestrator(
            robot=mock_robot,
            api_key=api_key,
            enable_rag=False,
            verbose=False
        )

        # Verify planner does NOT have knowledge_base
        assert orchestrator.planner.knowledge_base is None, \
            "PlannerAgent should not have knowledge_base when RAG is disabled"

    def test_factory_creates_with_rag_enabled(self, mock_robot, api_key):
        """Test that OrchestratorFactory creates instance with RAG enabled."""
        # Reset factory
        OrchestratorFactory.reset()

        # Create orchestrator via factory
        orchestrator = OrchestratorFactory.create(
            robot=mock_robot,
            api_key=api_key,
            enable_rag=True,
            rag_persist_directory="./data/chromadb_test",
            verbose=False
        )

        # Verify planner has knowledge_base
        assert orchestrator.planner.knowledge_base is not None, \
            "Factory-created orchestrator should have RAG enabled"

        # Clean up
        OrchestratorFactory.reset()

    def test_rag_knowledge_base_accessible_through_planner(self, mock_robot, api_key):
        """Test that RAG knowledge base is accessible through planner."""
        # Create orchestrator
        orchestrator = MissionOrchestrator(
            robot=mock_robot,
            api_key=api_key,
            enable_rag=True,
            rag_persist_directory="./data/chromadb_test",
            verbose=False
        )

        # Verify we can access knowledge base through planner
        kb = orchestrator.planner.knowledge_base
        assert kb is not None

        # Test basic search functionality
        capabilities = kb.search_capabilities("속도", n_results=3)
        assert len(capabilities) > 0, "Should find capabilities related to speed"

        constraints = kb.search_constraints("안전", n_results=3)
        assert len(constraints) > 0, "Should find constraints related to safety"

    def test_environment_detector_initialized(self, mock_robot, api_key):
        """Test that PlannerAgent has EnvironmentDetector initialized."""
        # Create orchestrator
        orchestrator = MissionOrchestrator(
            robot=mock_robot,
            api_key=api_key,
            enable_rag=True,
            rag_persist_directory="./data/chromadb_test",
            verbose=False
        )

        # Verify environment detector exists
        assert orchestrator.planner.environment_detector is not None, \
            "PlannerAgent should have EnvironmentDetector initialized"

    def test_rag_handles_empty_database_gracefully(self, mock_robot, api_key):
        """Test that RAG handles empty/new database gracefully."""
        import shutil
        import gc

        # Clean up test directory
        test_dir = "./data/chromadb_test_empty"
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir, ignore_errors=True)

        # Create orchestrator with fresh database
        orchestrator = MissionOrchestrator(
            robot=mock_robot,
            api_key=api_key,
            enable_rag=True,
            rag_persist_directory=test_dir,
            verbose=False
        )

        # Verify knowledge base is populated automatically
        assert orchestrator.planner.knowledge_base is not None
        assert orchestrator.planner.knowledge_base.capabilities_collection.count() > 0

        # Clean up - release ChromaDB resources
        if orchestrator.planner.knowledge_base:
            orchestrator.planner.knowledge_base.client = None
        del orchestrator
        gc.collect()  # Force garbage collection

        # Clean up test directory (ignore Windows file lock errors)
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir, ignore_errors=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
