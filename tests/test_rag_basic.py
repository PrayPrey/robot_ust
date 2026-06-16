"""
Basic RAG System Test

Quick validation that ChromaDB and knowledge base work correctly.
This test doesn't require OpenAI API calls.
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.rag import RobotKnowledgeBase


def test_knowledge_base_setup():
    """Test ChromaDB setup and data loading."""
    print("\n" + "="*60)
    print("Testing ChromaDB Knowledge Base Setup")
    print("="*60)

    # Check if OPENAI_API_KEY is set
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("[FAIL] OPENAI_API_KEY not set. Please set it in environment or .env file")
        return False

    try:
        # Initialize knowledge base
        print("\n[Step 1] Initializing ChromaDB...")
        kb = RobotKnowledgeBase(
            persist_directory="./data/chromadb_test",
            openai_api_key=api_key
        )
        print("[PASS] ChromaDB initialized successfully")

        # Clear existing data
        print("\n[Step 2] Clearing existing collections...")
        kb.clear_collections()
        print("[PASS] Collections cleared")

        # Check data files exist
        capabilities_file = "src/rag/data/robot_capabilities.json"
        constraints_file = "src/rag/data/environment_constraints.json"

        if not Path(capabilities_file).exists():
            print(f"[FAIL] Capabilities file not found: {capabilities_file}")
            return False

        if not Path(constraints_file).exists():
            print(f"[FAIL] Constraints file not found: {constraints_file}")
            return False

        print(f"[PASS] Data files found")

        # Populate knowledge base
        print("\n[Step 3] Populating knowledge base...")
        print("   (This will call OpenAI API to generate embeddings)")
        counts = kb.populate_from_files(capabilities_file, constraints_file)
        print(f"[PASS] Populated {counts['capabilities']} capabilities")
        print(f"[PASS] Populated {counts['constraints']} constraints")

        # Verify collections
        stats = kb.get_collection_stats()
        print(f"\n[Step 4] Collection Statistics:")
        print(f"   - Capabilities: {stats['capabilities_count']} items")
        print(f"   - Constraints: {stats['constraints_count']} items")

        if stats['capabilities_count'] == 0 or stats['constraints_count'] == 0:
            print("[FAIL] Collections are empty!")
            return False

        # Test search capabilities
        print("\n[Step 5] Testing search capabilities...")
        print("   Query: 'maximum speed'")
        results = kb.search_capabilities("maximum speed", n_results=2)
        print(f"   Found {len(results)} results:")
        for i, result in enumerate(results, 1):
            print(f"   {i}. {result['document'][:80]}...")
            print(f"      Distance: {result['distance']:.4f}")

        # Test search constraints
        print("\n[Step 6] Testing search constraints...")
        print("   Query: 'obstacle distance'")
        results = kb.search_constraints("obstacle distance", n_results=2)
        print(f"   Found {len(results)} results:")
        for i, result in enumerate(results, 1):
            print(f"   {i}. {result['document'][:80]}...")
            print(f"      Distance: {result['distance']:.4f}")

        # Test search all
        print("\n[Step 7] Testing search all...")
        print("   Query: 'safety'")
        all_results = kb.search_all("safety", n_results=2)
        print(f"   Capabilities found: {len(all_results['capabilities'])}")
        print(f"   Constraints found: {len(all_results['constraints'])}")

        print("\n" + "="*60)
        print("[SUCCESS] ALL TESTS PASSED!")
        print("="*60)
        return True

    except Exception as e:
        print(f"\n[FAIL] Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_knowledge_base_setup()
    sys.exit(0 if success else 1)
