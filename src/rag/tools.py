"""
RAG Tools for Planner Agent

Provides LLM Function Calling tools for knowledge base search and action plan creation.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from loguru import logger

from .knowledge_base import RobotKnowledgeBase
from ..schemas import RobotAction, ActionType


# ============================================================================
# Tool 1: Search Knowledge Base
# ============================================================================

class SearchKnowledgeInput(BaseModel):
    """Input schema for search_knowledge_tool."""

    query: str = Field(
        description="Natural language search query to find relevant robot capabilities or environment constraints. Examples: '최대 속도', 'obstacle distance', 'sensor range'"
    )
    category: Optional[str] = Field(
        default=None,
        description="Optional category filter. Use 'capabilities' to search only robot capabilities, 'constraints' to search only environment constraints, or None to search both."
    )
    n_results: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Number of most relevant results to return (1-10). Default is 3."
    )


class SearchKnowledgeOutput(BaseModel):
    """Output schema for search_knowledge_tool."""

    results: List[Dict[str, Any]] = Field(
        description="List of relevant knowledge documents with metadata and similarity scores"
    )
    summary: str = Field(
        description="Human-readable summary of retrieved knowledge"
    )
    total_found: int = Field(
        description="Total number of results found"
    )


def create_search_knowledge_tool(knowledge_base: RobotKnowledgeBase):
    """
    Factory function to create search_knowledge_tool with bound knowledge base.

    Args:
        knowledge_base: RobotKnowledgeBase instance

    Returns:
        search_knowledge_tool function
    """

    def search_knowledge_tool(
        query: str,
        category: Optional[str] = None,
        n_results: int = 3
    ) -> SearchKnowledgeOutput:
        """
        Search robot knowledge base for relevant information.

        This tool allows the LLM to query ChromaDB for:
        - Robot capabilities (speed limits, sensor ranges, movement constraints)
        - Environment constraints (safe zones, obstacle information, boundaries)

        The search uses semantic similarity (OpenAI embeddings) to find the most
        relevant knowledge for the given query.

        Args:
            query: Natural language search query
            category: Optional filter - 'capabilities', 'constraints', or None for both
            n_results: Number of results to return (1-10)

        Returns:
            SearchKnowledgeOutput with relevant documents and summary

        Example:
            >>> result = search_knowledge_tool("빠르게 이동", category="capabilities", n_results=2)
            >>> print(result.summary)
            "Found 2 relevant capabilities. Top result: Pioneer 3-DX 로봇의 최대 이동 속도는 1.2m/s..."
        """
        logger.info(f"RAG Tool - Searching knowledge: query='{query}', category={category}, n_results={n_results}")

        results = []

        try:
            # Search based on category
            if category == "capabilities":
                results = knowledge_base.search_capabilities(query, n_results)
            elif category == "constraints":
                results = knowledge_base.search_constraints(query, n_results)
            else:
                # Search both
                all_results = knowledge_base.search_all(query, n_results)
                results = all_results['capabilities'] + all_results['constraints']
                # Sort by distance (similarity)
                results = sorted(results, key=lambda x: x.get('distance', 1.0))[:n_results]

            # Generate summary
            if results:
                top_result = results[0]['document']
                summary = f"Found {len(results)} relevant knowledge item(s). "
                summary += f"Top result: {top_result[:150]}{'...' if len(top_result) > 150 else ''}"
            else:
                summary = f"No relevant knowledge found for query: '{query}'"

            logger.info(f"RAG Tool - Search completed: {len(results)} results")

            return SearchKnowledgeOutput(
                results=results,
                summary=summary,
                total_found=len(results)
            )

        except Exception as e:
            logger.error(f"RAG Tool - Search failed: {e}")
            return SearchKnowledgeOutput(
                results=[],
                summary=f"Search failed due to error: {str(e)}",
                total_found=0
            )

    return search_knowledge_tool


# ============================================================================
# Tool 2: Create Action Plan
# ============================================================================

class CreateActionPlanInput(BaseModel):
    """Input schema for create_action_plan_tool."""

    actions: List[Dict[str, Any]] = Field(
        description="List of robot actions to execute. Each action must have: 'action' (move/rotate/scan/wait/stop), appropriate parameters (x, y, speed, angle, duration), and 'reason' (explanation)."
    )


class CreateActionPlanOutput(BaseModel):
    """Output schema for create_action_plan_tool."""

    plan: List[Dict[str, Any]] = Field(
        description="Validated list of RobotAction objects (serialized to dict)"
    )
    total_actions: int = Field(
        description="Total number of actions in the plan"
    )
    estimated_duration_sec: float = Field(
        description="Estimated total execution time in seconds"
    )
    safety_validated: bool = Field(
        description="Whether all actions passed Pydantic safety validation"
    )
    validation_errors: List[str] = Field(
        default_factory=list,
        description="List of validation errors (if any)"
    )


def create_action_plan_tool(
    actions: List[Dict[str, Any]]
) -> CreateActionPlanOutput:
    """
    Create a validated action plan from action list.

    This tool converts raw action dictionaries into validated RobotAction objects
    with full Pydantic safety constraint checking:
    - Position limits: -5m to 5m
    - Speed limits: 0.1 to 2.0 m/s
    - Angle limits: -180° to 180°
    - Duration limits: 0.1 to 10.0 seconds

    Args:
        actions: List of action dictionaries

    Returns:
        CreateActionPlanOutput with validated plan and estimates

    Example:
        >>> actions = [
        ...     {"action": "move", "x": 3.0, "y": 0.0, "speed": 0.5, "reason": "Move forward"},
        ...     {"action": "scan", "duration": 5.0, "reason": "Search for survivors"}
        ... ]
        >>> result = create_action_plan_tool(actions)
        >>> print(f"Plan has {result.total_actions} actions, estimated {result.estimated_duration_sec}s")
    """
    logger.info(f"RAG Tool - Creating action plan: {len(actions)} actions")

    validated_actions = []
    validation_errors = []
    total_duration = 0.0
    safety_validated = True

    for i, action_dict in enumerate(actions):
        try:
            # Pydantic validation
            action = RobotAction(**action_dict)

            # Serialize back to dict for output
            validated_actions.append(action.model_dump())

            # Estimate execution time
            if action.action == ActionType.MOVE:
                # Distance / speed
                x = action.x or 0.0
                y = action.y or 0.0
                distance = (x**2 + y**2)**0.5
                speed = action.speed or 1.0
                total_duration += distance / speed

            elif action.action == ActionType.ROTATE:
                # Angle / rotation_speed (assume 45 deg/sec)
                angle = abs(action.angle or 0.0)
                rotation_speed = 45.0  # deg/sec
                total_duration += angle / rotation_speed

            elif action.action in [ActionType.SCAN, ActionType.WAIT]:
                # Direct duration
                total_duration += action.duration or 0.0

            logger.debug(f"Action {i+1} validated: {action.action.value}")

        except Exception as e:
            safety_validated = False
            error_msg = f"Action {i+1} validation failed: {str(e)}"
            validation_errors.append(error_msg)
            logger.error(error_msg)

    if safety_validated:
        logger.info(f"RAG Tool - Action plan created: {len(validated_actions)} actions, estimated {total_duration:.1f}s")
    else:
        logger.warning(f"RAG Tool - Action plan validation failed: {len(validation_errors)} errors")

    return CreateActionPlanOutput(
        plan=validated_actions,
        total_actions=len(validated_actions),
        estimated_duration_sec=round(total_duration, 2),
        safety_validated=safety_validated,
        validation_errors=validation_errors
    )


# ============================================================================
# Helper: Format RAG context for Planner prompt
# ============================================================================

def format_rag_context(
    capabilities: List[Dict[str, Any]],
    constraints: List[Dict[str, Any]]
) -> str:
    """
    Format RAG search results into human-readable context string.

    Args:
        capabilities: List of capability search results
        constraints: List of constraint search results

    Returns:
        Formatted context string for LLM prompt
    """
    context = "\n## 🤖 Robot Knowledge Base (Retrieved from ChromaDB)\n\n"

    # Capabilities section
    if capabilities:
        context += "### 📚 Relevant Robot Capabilities:\n"
        for i, cap in enumerate(capabilities, 1):
            context += f"{i}. {cap['document']}\n"
            if cap.get('metadata'):
                # Show key metadata
                meta_str = ", ".join([f"{k}={v}" for k, v in list(cap['metadata'].items())[:3]])
                context += f"   ({meta_str})\n"
        context += "\n"

    # Constraints section
    if constraints:
        context += "### 🚨 Relevant Environment Constraints:\n"
        for i, const in enumerate(constraints, 1):
            context += f"{i}. {const['document']}\n"
            if const.get('metadata'):
                # Show key metadata
                meta_str = ", ".join([f"{k}={v}" for k, v in list(const['metadata'].items())[:3]])
                context += f"   ({meta_str})\n"
        context += "\n"

    context += "⚠️ **IMPORTANT**: You MUST consider the above knowledge when planning actions.\n"
    context += "Use the constraints to ensure safety and the capabilities to set realistic parameters.\n"

    return context
