"""
Robot Knowledge Base using ChromaDB

Manages robot capabilities and environment constraints using vector embeddings
for intelligent retrieval during mission planning.
"""

import os
import json
from typing import List, Dict, Any, Optional
from pathlib import Path

import chromadb
from chromadb.config import Settings
from loguru import logger
import openai


class RobotKnowledgeBase:
    """
    ChromaDB-based knowledge base for robot capabilities and environment constraints.

    Collections:
    - robot_capabilities: Robot abilities (speed, rotation, sensor ranges)
    - environment_constraints: Safety rules (obstacle distance, boundaries, zones)

    Example:
        >>> kb = RobotKnowledgeBase()
        >>> kb.populate_from_files(
        ...     "src/rag/data/robot_capabilities.json",
        ...     "src/rag/data/environment_constraints.json"
        ... )
        >>> results = kb.search_capabilities("최대 속도", n_results=3)
    """

    def __init__(
        self,
        persist_directory: str = "./data/chromadb",
        openai_api_key: Optional[str] = None,
        embedding_model: str = "text-embedding-3-small"
    ):
        """
        Initialize ChromaDB knowledge base.

        Args:
            persist_directory: Directory to persist ChromaDB data
            openai_api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            embedding_model: OpenAI embedding model to use
        """
        self.persist_directory = persist_directory
        self.embedding_model = embedding_model

        # Set OpenAI API key
        self.api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not provided. Set OPENAI_API_KEY env var or pass api_key parameter.")

        openai.api_key = self.api_key

        # Create persist directory if it doesn't exist
        Path(persist_directory).mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB client with persistence
        self.client = chromadb.PersistentClient(path=persist_directory)

        # Create or get collections
        self.capabilities_collection = self.client.get_or_create_collection(
            name="robot_capabilities",
            metadata={"description": "Robot capabilities and specifications"}
        )

        self.constraints_collection = self.client.get_or_create_collection(
            name="environment_constraints",
            metadata={"description": "Environment constraints and safety rules"}
        )

        logger.info(f"RobotKnowledgeBase initialized with persist_directory={persist_directory}")
        logger.info(f"Capabilities collection: {self.capabilities_collection.count()} items")
        logger.info(f"Constraints collection: {self.constraints_collection.count()} items")

    def _get_embedding(self, text: str) -> List[float]:
        """
        Generate OpenAI embedding for text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        try:
            response = openai.embeddings.create(
                input=text,
                model=self.embedding_model
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise

    @staticmethod
    def _sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize metadata for ChromaDB.

        ChromaDB only supports: str, int, float, bool, None
        Converts lists to comma-separated strings.
        Converts other types to strings.

        Args:
            metadata: Raw metadata dictionary

        Returns:
            Sanitized metadata dictionary
        """
        sanitized = {}
        for key, value in metadata.items():
            if isinstance(value, (str, int, float, bool, type(None))):
                sanitized[key] = value
            elif isinstance(value, list):
                # Convert list to comma-separated string
                sanitized[key] = ", ".join(str(v) for v in value)
            else:
                # Convert other types to string
                sanitized[key] = str(value)
        return sanitized

    def populate_robot_capabilities(
        self,
        capabilities_file: str
    ) -> int:
        """
        Populate robot capabilities from JSON file.

        Args:
            capabilities_file: Path to robot_capabilities.json

        Returns:
            Number of capabilities added
        """
        logger.info(f"Loading robot capabilities from {capabilities_file}")

        with open(capabilities_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        capabilities = data.get('capabilities', [])

        if not capabilities:
            logger.warning(f"No capabilities found in {capabilities_file}")
            return 0

        # Prepare data for ChromaDB
        documents = []
        embeddings = []
        metadatas = []
        ids = []

        for cap in capabilities:
            # Document text
            documents.append(cap['description'])

            # Generate embedding
            embedding = self._get_embedding(cap['description'])
            embeddings.append(embedding)

            # Metadata (sanitize to ensure ChromaDB compatibility)
            raw_metadata = {
                'category': cap['category'],
                **cap.get('metadata', {})
            }
            metadata = self._sanitize_metadata(raw_metadata)
            metadatas.append(metadata)

            # ID
            ids.append(cap['id'])

        # Add to collection
        self.capabilities_collection.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )

        logger.info(f"Added {len(capabilities)} robot capabilities to ChromaDB")
        return len(capabilities)

    def populate_environment_constraints(
        self,
        constraints_file: str
    ) -> int:
        """
        Populate environment constraints from JSON file.

        Args:
            constraints_file: Path to environment_constraints.json

        Returns:
            Number of constraints added
        """
        logger.info(f"Loading environment constraints from {constraints_file}")

        with open(constraints_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        constraints = data.get('constraints', [])

        if not constraints:
            logger.warning(f"No constraints found in {constraints_file}")
            return 0

        # Prepare data for ChromaDB
        documents = []
        embeddings = []
        metadatas = []
        ids = []

        for const in constraints:
            # Document text
            documents.append(const['description'])

            # Generate embedding
            embedding = self._get_embedding(const['description'])
            embeddings.append(embedding)

            # Metadata (sanitize to ensure ChromaDB compatibility)
            raw_metadata = {
                'category': const['category'],
                'environment_type': const.get('environment_type', 'general'),  # Story 3.3: Add environment_type
                **const.get('metadata', {})
            }
            metadata = self._sanitize_metadata(raw_metadata)
            metadatas.append(metadata)

            # ID
            ids.append(const['id'])

        # Add to collection
        self.constraints_collection.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )

        logger.info(f"Added {len(constraints)} environment constraints to ChromaDB")
        return len(constraints)

    def populate_from_files(
        self,
        capabilities_file: str,
        constraints_file: str
    ) -> Dict[str, int]:
        """
        Populate both collections from JSON files.

        Args:
            capabilities_file: Path to robot_capabilities.json
            constraints_file: Path to environment_constraints.json

        Returns:
            Dictionary with counts: {'capabilities': n, 'constraints': m}
        """
        cap_count = self.populate_robot_capabilities(capabilities_file)
        const_count = self.populate_environment_constraints(constraints_file)

        return {
            'capabilities': cap_count,
            'constraints': const_count
        }

    def search_capabilities(
        self,
        query: str,
        n_results: int = 3,
        where: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search robot capabilities collection.

        Args:
            query: Search query (natural language)
            n_results: Number of results to return
            where: Optional metadata filter (e.g., {"category": "movement"})

        Returns:
            List of results with documents, metadata, and distances
        """
        # Generate query embedding
        query_embedding = self._get_embedding(query)

        # Query collection
        results = self.capabilities_collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where
        )

        # Format results
        formatted = []
        if results['documents'] and len(results['documents'][0]) > 0:
            for i in range(len(results['documents'][0])):
                formatted.append({
                    'document': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                    'distance': results['distances'][0][i] if results.get('distances') else 0.0,
                    'id': results['ids'][0][i] if results['ids'] else None
                })

        logger.debug(f"Found {len(formatted)} capabilities for query: {query}")
        return formatted

    def search_constraints(
        self,
        query: str,
        n_results: int = 3,
        where: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search environment constraints collection.

        Args:
            query: Search query (natural language)
            n_results: Number of results to return
            where: Optional metadata filter (e.g., {"category": "safety"})

        Returns:
            List of results with documents, metadata, and distances
        """
        # Generate query embedding
        query_embedding = self._get_embedding(query)

        # Query collection
        results = self.constraints_collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where
        )

        # Format results
        formatted = []
        if results['documents'] and len(results['documents'][0]) > 0:
            for i in range(len(results['documents'][0])):
                formatted.append({
                    'document': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                    'distance': results['distances'][0][i] if results.get('distances') else 0.0,
                    'id': results['ids'][0][i] if results['ids'] else None
                })

        logger.debug(f"Found {len(formatted)} constraints for query: {query}")
        return formatted

    def search_all(
        self,
        query: str,
        n_results: int = 3
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search both capabilities and constraints.

        Args:
            query: Search query (natural language)
            n_results: Number of results per collection

        Returns:
            Dictionary with 'capabilities' and 'constraints' keys
        """
        capabilities = self.search_capabilities(query, n_results)
        constraints = self.search_constraints(query, n_results)

        return {
            'capabilities': capabilities,
            'constraints': constraints
        }

    def search(
        self,
        query: str,
        n_results: int = None,
        k: int = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search both capabilities and constraints (alias for search_all).

        Story 3.6: Added for compatibility with integration tests.
        Supports both n_results and k parameters for flexibility.

        Args:
            query: Search query (natural language)
            n_results: Number of results per collection (default: 3)
            k: Alternative parameter for number of results (for compatibility)

        Returns:
            Dictionary with 'capabilities' and 'constraints' keys
        """
        # Support both n_results and k parameters
        result_count = n_results if n_results is not None else (k if k is not None else 3)
        return self.search_all(query, result_count)

    def get_collection_stats(self) -> Dict[str, int]:
        """
        Get statistics about collections.

        Returns:
            Dictionary with collection counts
        """
        return {
            'capabilities_count': self.capabilities_collection.count(),
            'constraints_count': self.constraints_collection.count()
        }

    def clear_collections(self):
        """Clear all data from both collections."""
        logger.warning("Clearing all collections")
        self.client.delete_collection("robot_capabilities")
        self.client.delete_collection("environment_constraints")

        # Recreate collections
        self.capabilities_collection = self.client.get_or_create_collection(
            name="robot_capabilities",
            metadata={"description": "Robot capabilities and specifications"}
        )
        self.constraints_collection = self.client.get_or_create_collection(
            name="environment_constraints",
            metadata={"description": "Environment constraints and safety rules"}
        )

        logger.info("Collections cleared and recreated")
