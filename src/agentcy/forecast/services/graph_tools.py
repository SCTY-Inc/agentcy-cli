"""
Graph retrieval tools service — public assembly point.

Composes GraphToolsService from focused modules:
- graph_models     — data classes (SearchResult, NodeInfo, EdgeInfo, ...)
- graph_retrieval  — base CRUD (search_graph, get_all_nodes/edges, ...)
- graph_search_tools — advanced search (insight_forge, panorama_search, ...)
- graph_interview  — agent interviews (interview_agents, ...)

All callers import GraphToolsService from here; internal layout is an
implementation detail.
"""

from .graph_models import (
    SearchResult,
    NodeInfo,
    EdgeInfo,
    InsightForgeResult,
    PanoramaResult,
    AgentInterview,
    InterviewResult,
)
from .graph_retrieval import GraphRetrievalBase
from .graph_search_tools import GraphSearchToolsMixin
from .graph_interview import GraphInterviewMixin


class GraphToolsService(GraphRetrievalBase, GraphSearchToolsMixin, GraphInterviewMixin):
    """
    Graph retrieval tools service.

    [Core Retrieval Tools - Optimized]
    1. insight_forge - Deep insight retrieval (most powerful, auto-generates sub-queries, multi-dimensional retrieval)
    2. panorama_search - Broad search (get the full picture, including expired content)
    3. quick_search - Simple search (fast retrieval)
    4. interview_agents - In-depth interview (interview simulated agents, obtain multi-perspective viewpoints)

    [Basic Tools]
    - search_graph - Graph semantic search
    - get_all_nodes - Get all nodes in the graph
    - get_all_edges - Get all edges in the graph (with temporal information)
    - get_node_detail - Get detailed node information
    - get_node_edges - Get edges related to a node
    - get_entities_by_type - Get entities by type
    - get_entity_summary - Get relationship summary for an entity
    """


# Backward-compat alias (was KuzuToolsService in original)
KuzuToolsService = GraphToolsService
