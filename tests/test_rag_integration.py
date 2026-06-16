"""
Test RAG Integration with Planner Agent

Tests ChromaDB knowledge base integration and RAG-enhanced planning.
"""

import pytest
import os
from pathlib import Path

from src.rag import RobotKnowledgeBase
from src.agents.planner_agent import PlannerAgent
from src.schemas import MissionCommand


# Skip tests if no OpenAI API key
pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set"
)


@pytest.fixture(scope="module")
def knowledge_base():
    """Create and populate knowledge base for tests."""
    # Use test-specific ChromaDB directory
    test_db_path = "./data/chromadb_test"

    kb = RobotKnowledgeBase(
        persist_directory=test_db_path,
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )

    # Clear existing data
    kb.clear_collections()

    # Populate from data files
    capabilities_file = "src/rag/data/robot_capabilities.json"
    constraints_file = "src/rag/data/environment_constraints.json"

    kb.populate_from_files(capabilities_file, constraints_file)

    yield kb

    # Cleanup (optional, comment out to inspect data)
    # kb.clear_collections()


@pytest.fixture
def planner_with_rag(knowledge_base):
    """Create Planner Agent with RAG enabled."""
    return PlannerAgent(
        api_key=os.getenv("OPENAI_API_KEY"),
        knowledge_base=knowledge_base,
        model="gpt-4o-mini",  # Use cheaper model for tests
        temperature=0.0,  # Deterministic for testing
        verbose=True
    )


@pytest.fixture
def planner_without_rag():
    """Create Planner Agent without RAG (baseline)."""
    return PlannerAgent(
        api_key=os.getenv("OPENAI_API_KEY"),
        knowledge_base=None,
        model="gpt-4o-mini",
        temperature=0.0,
        verbose=True
    )


class TestKnowledgeBase:
    """Test ChromaDB knowledge base functionality."""

    def test_kb_initialization(self, knowledge_base):
        """Test knowledge base initializes correctly."""
        assert knowledge_base is not None
        stats = knowledge_base.get_collection_stats()
        assert stats['capabilities_count'] > 0
        assert stats['constraints_count'] > 0

    def test_search_capabilities(self, knowledge_base):
        """Test searching robot capabilities."""
        results = knowledge_base.search_capabilities("최대 속도", n_results=2)

        assert len(results) > 0
        # Should find speed-related capability
        assert any("속도" in r['document'] or "speed" in r['document'].lower() for r in results)

    def test_search_constraints(self, knowledge_base):
        """Test searching environment constraints."""
        results = knowledge_base.search_constraints("장애물 거리", n_results=2)

        assert len(results) > 0
        # Should find obstacle distance constraint
        assert any("장애물" in r['document'] or "obstacle" in r['document'].lower() for r in results)

    def test_search_all(self, knowledge_base):
        """Test searching both collections."""
        results = knowledge_base.search_all("안전", n_results=3)

        assert 'capabilities' in results
        assert 'constraints' in results
        assert len(results['capabilities']) > 0 or len(results['constraints']) > 0


class TestRAGIntegration:
    """Test RAG integration with Planner Agent."""

    def test_planner_with_rag_initialization(self, planner_with_rag):
        """Test Planner with RAG initializes correctly."""
        assert planner_with_rag.knowledge_base is not None

    def test_rag_context_retrieval(self, planner_with_rag):
        """Test RAG context retrieval."""
        query = "빠르게 이동"
        context = planner_with_rag._retrieve_rag_context(query)

        assert len(context) > 0
        assert "Robot Knowledge Base" in context or "로봇" in context

    def test_planning_with_rag_speed_constraint(self, planner_with_rag):
        """Test that RAG enforces speed constraints."""
        mission = MissionCommand(
            command="빠르게 3미터 전진",
            language="ko",
            priority=5
        )

        action_plan = planner_with_rag.plan_mission(mission)

        assert len(action_plan) > 0

        # Check if speed is constrained by RAG knowledge
        move_actions = [a for a in action_plan if a.action.value == "move"]
        if move_actions:
            # RAG should suggest safe speed (0.5 m/s or lower)
            # This tests if RAG knowledge influences planning
            assert all(a.speed <= 1.2 for a in move_actions), "Speed should respect hardware limit"

    def test_planning_with_rag_vs_without(self, planner_with_rag, planner_without_rag):
        """Compare planning with and without RAG."""
        mission = MissionCommand(
            command="Move forward quickly",
            language="en",
            priority=5
        )

        # Plan with RAG
        plan_with_rag = planner_with_rag.plan_mission(mission)

        # Plan without RAG
        plan_without_rag = planner_without_rag.plan_mission(mission)

        # Both should produce valid plans
        assert len(plan_with_rag) > 0
        assert len(plan_without_rag) > 0

        # RAG-enhanced planning should consider knowledge base constraints
        # (This is a behavioral test - specific assertions depend on LLM behavior)

    def test_rag_search_for_korean_command(self, planner_with_rag, knowledge_base):
        """Test RAG search for Korean mission command."""
        # Korean query
        query = "장애물 회피하며 이동"

        capabilities = knowledge_base.search_capabilities(query, n_results=2)
        constraints = knowledge_base.search_constraints(query, n_results=2)

        # Should find relevant information
        assert len(capabilities) > 0 or len(constraints) > 0

    def test_rag_search_for_english_command(self, planner_with_rag, knowledge_base):
        """Test RAG search for English mission command."""
        # English query
        query = "maximum speed movement"

        capabilities = knowledge_base.search_capabilities(query, n_results=2)

        # Should find speed-related capabilities
        assert len(capabilities) > 0


class TestRAGTools:
    """Test RAG tools functionality."""

    def test_create_action_plan_tool(self):
        """Test create_action_plan_tool validation."""
        from src.rag.tools import create_action_plan_tool

        # Valid actions
        actions = [
            {"action": "move", "x": 3.0, "y": 0.0, "speed": 0.5, "reason": "Move forward"},
            {"action": "scan", "duration": 5.0, "reason": "Search area"}
        ]

        result = create_action_plan_tool(actions)

        assert result.safety_validated is True
        assert result.total_actions == 2
        assert result.estimated_duration_sec > 0

    def test_create_action_plan_tool_invalid_action(self):
        """Test create_action_plan_tool with invalid action."""
        from src.rag.tools import create_action_plan_tool

        # Invalid action (speed out of range)
        actions = [
            {"action": "move", "x": 3.0, "y": 0.0, "speed": 999.0, "reason": "Too fast"}
        ]

        result = create_action_plan_tool(actions)

        assert result.safety_validated is False
        assert len(result.validation_errors) > 0


class TestEndToEnd:
    """End-to-end RAG integration tests."""

    @pytest.mark.slow
    def test_e2e_korean_mission_with_rag(self, planner_with_rag):
        """End-to-end test: Korean mission with RAG."""
        mission = MissionCommand(
            command="안전하게 3미터 전진한 후 주변을 5초간 스캔",
            language="ko",
            priority=7,
            timeout_seconds=60
        )

        action_plan = planner_with_rag.plan_mission(mission)

        # Verify plan structure
        assert len(action_plan) >= 2  # At least move + scan

        # Verify action types
        action_types = [a.action.value for a in action_plan]
        assert "move" in action_types
        assert "scan" in action_types

        # Verify safety (RAG should enforce safe speed)
        move_actions = [a for a in action_plan if a.action.value == "move"]
        if move_actions:
            assert all(a.speed <= 1.2 for a in move_actions)

    @pytest.mark.slow
    def test_e2e_english_mission_with_rag(self, planner_with_rag):
        """End-to-end test: English mission with RAG."""
        mission = MissionCommand(
            command="Move to coordinates (2, 3) and scan for 10 seconds",
            language="en",
            priority=5,
            timeout_seconds=60
        )

        action_plan = planner_with_rag.plan_mission(mission)

        # Verify plan contains expected actions
        assert len(action_plan) >= 2

        action_types = [a.action.value for a in action_plan]
        assert "move" in action_types
        assert "scan" in action_types


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
