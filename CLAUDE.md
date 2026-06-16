# CRITICAL: ARCHON-FIRST RULE - READ THIS FIRST

Archon Knowledge Management & RAG Workflow
CRITICAL: This project utilizes the Archon MCP server as its centralized system for knowledge management, technical research, and RAG (Retrieval-Augmented Generation). ALWAYS consult Archon's RAG capabilities for relevant knowledge and best practices before implementing new features or making design decisions.

Knowledge Management Integration
Documentation Queries
Use RAG for both high-level and specific technical guidance:

Bash

# Architecture & patterns
archon:perform_rag_query(query="microservices vs monolith pros cons", match_count=5)

# Security considerations  
archon:perform_rag_query(query="OAuth 2.0 PKCE flow implementation", match_count=3)

# Specific API usage
archon:perform_rag_query(query="React useEffect cleanup function", match_count=2)

# Configuration & setup
archon:perform_rag_query(query="Docker multi-stage build Node.js", match_count=3)

# Debugging & troubleshooting
archon:perform_rag_query(query="TypeScript generic type inference error", match_count=2)
Code Example Integration
Search for implementation patterns before coding:

Bash

# Before implementing any feature
archon:search_code_examples(query="React custom hook data fetching", match_count=3)

# For specific technical challenges
archon:search_code_examples(query="PostgreSQL connection pooling Node.js", match_count=2)
Usage Guidelines:

Search for examples before implementing from scratch

Adapt patterns to project-specific requirements  

Use for both complex features and simple API usage

Validate examples against current best practices

Research-Driven Development Standards
Before Any Implementation
Research checklist:

[ ] Search for existing code examples of the pattern

[ ] Query documentation for best practices (high-level or specific API usage)

[ ] Understand security implications

[ ] Check for common pitfalls or antipatterns

Knowledge Source Prioritization
Query Strategy:

Start with broad architectural queries, narrow to specific implementation

Use RAG for both strategic decisions and tactical "how-to" questions

Cross-reference multiple sources for validation

Keep match_count low (2-5) for focused results

Error Handling & Recovery
When Research Yields No Results
If knowledge queries return empty results:

Broaden search terms and try again

Search for related concepts or technologies

Proceed with conservative, well-tested approaches

Quality Assurance Integration
Research Validation
Always validate research findings:

Cross-reference multiple sources

Verify recency of information

Test applicability to current project context

