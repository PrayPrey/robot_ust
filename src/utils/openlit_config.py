"""
OpenLit LLM monitoring configuration for LLM_robot_2.

This module provides automatic LLM tracking for cost, latency, and token usage
using OpenLit's instrumentation for OpenAI API calls.

Story: 2.5 - Monitoring, Logging, and Evaluation
AC #2: Track LLM cost, latency, and token usage automatically
"""

import os
from typing import Optional, Dict, Any
from loguru import logger

# OpenLit imports - graceful fallback if not installed
try:
    import openlit
    OPENLIT_AVAILABLE = True
except ImportError:
    OPENLIT_AVAILABLE = False
    logger.warning("OpenLit not installed. LLM monitoring will be disabled.")


class OpenLitConfig:
    """
    Centralized OpenLit configuration for LLM monitoring.

    Features:
    - Automatic OpenAI API instrumentation
    - Cost calculation (gpt-4o-mini pricing)
    - Latency measurement (response time)
    - Token usage tracking (prompt/completion/total)
    - Optional dashboard integration

    Usage:
        >>> from src.utils.openlit_config import setup_openlit
        >>> setup_openlit(application_name="LLM_robot_2")
        >>> # OpenAI calls are now automatically tracked
    """

    _initialized: bool = False
    _application_name: str = "LLM_robot_2"
    _environment: str = "production"

    @classmethod
    def setup(
        cls,
        application_name: str = "LLM_robot_2",
        environment: str = "production",
        api_key: Optional[str] = None,
        disable_batch: bool = True,
        collect_gpu_stats: bool = False
    ) -> None:
        """
        Initialize OpenLit for automatic LLM monitoring.

        Args:
            application_name: Application name for OpenLit dashboard
            environment: Environment name (production, development, testing)
            api_key: OpenLit API key (optional, uses OPENLIT_API_KEY env var)
            disable_batch: Disable batching for real-time metrics (default: True)
            collect_gpu_stats: Enable GPU stats collection (default: False)

        Note:
            OpenLit automatically instruments OpenAI API calls when initialized.
            No code changes needed in agent files.
        """
        if not OPENLIT_AVAILABLE:
            logger.warning("OpenLit not available. Skipping initialization.")
            return

        if cls._initialized:
            logger.warning("OpenLit already initialized. Skipping re-initialization.")
            return

        cls._application_name = application_name
        cls._environment = environment

        # Get API key from environment if not provided
        if api_key is None:
            api_key = os.getenv("OPENLIT_API_KEY")

        # Initialize OpenLit
        try:
            openlit.init(
                application_name=application_name,
                environment=environment,
                # API key is optional - works without dashboard
                otlp_endpoint=os.getenv("OPENLIT_OTLP_ENDPOINT"),
                disable_batch=disable_batch,
                collect_gpu_stats=collect_gpu_stats
            )

            cls._initialized = True

            logger.info(
                "OpenLit initialized",
                application=application_name,
                environment=environment,
                dashboard_enabled=bool(api_key),
                batch_disabled=disable_batch
            )

        except Exception as e:
            logger.error(f"Failed to initialize OpenLit: {e}", exc_info=True)
            logger.warning("Continuing without OpenLit monitoring.")

    @classmethod
    def is_initialized(cls) -> bool:
        """Check if OpenLit is initialized."""
        return cls._initialized and OPENLIT_AVAILABLE

    @classmethod
    def get_config(cls) -> Dict[str, Any]:
        """
        Get current OpenLit configuration.

        Returns:
            Dict with configuration details
        """
        return {
            "initialized": cls._initialized,
            "available": OPENLIT_AVAILABLE,
            "application_name": cls._application_name,
            "environment": cls._environment
        }


def setup_openlit(
    application_name: str = "LLM_robot_2",
    environment: str = "production",
    api_key: Optional[str] = None
) -> None:
    """
    Convenience function to setup OpenLit monitoring.

    Args:
        application_name: Application name for OpenLit dashboard
        environment: Environment name
        api_key: Optional OpenLit API key

    Example:
        >>> from src.utils.openlit_config import setup_openlit
        >>> setup_openlit()
        >>> # All subsequent OpenAI API calls will be automatically tracked
    """
    OpenLitConfig.setup(
        application_name=application_name,
        environment=environment,
        api_key=api_key
    )


def is_openlit_enabled() -> bool:
    """
    Check if OpenLit monitoring is enabled.

    Returns:
        True if OpenLit is available and initialized
    """
    return OpenLitConfig.is_initialized()


# Pricing information for cost calculation (gpt-4o-mini as of 2024)
GPT_4O_MINI_PRICING = {
    "prompt_token_price": 0.00000015,  # $0.150 per 1M tokens
    "completion_token_price": 0.0000006,  # $0.600 per 1M tokens
}


def calculate_llm_cost(
    prompt_tokens: int,
    completion_tokens: int,
    model: str = "gpt-4o-mini"
) -> float:
    """
    Calculate LLM API call cost.

    Args:
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens
        model: Model name (default: gpt-4o-mini)

    Returns:
        Cost in USD

    Note:
        OpenLit tracks this automatically. This function is for manual
        calculation or validation.
    """
    if model != "gpt-4o-mini":
        logger.warning(f"Pricing not available for model: {model}. Using gpt-4o-mini pricing.")

    prompt_cost = prompt_tokens * GPT_4O_MINI_PRICING["prompt_token_price"]
    completion_cost = completion_tokens * GPT_4O_MINI_PRICING["completion_token_price"]
    total_cost = prompt_cost + completion_cost

    return total_cost
