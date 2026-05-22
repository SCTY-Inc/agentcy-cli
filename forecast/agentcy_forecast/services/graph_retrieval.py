"""
Graph retrieval base service.
Core CRUD operations: search_graph, get_all_nodes/edges, get_node_detail,
get_node_edges, get_entities_by_type, get_entity_summary.
"""

import time
from typing import Dict, Any, List, Optional

from .graph_db import GraphDatabase
from .graph_storage import GraphStorage
from .graph_models import SearchResult, NodeInfo, EdgeInfo

from ..utils.logger import get_logger
from ..utils.llm_client import LLMClient

logger = get_logger('mirofish.graph_tools')


class GraphRetrievalBase:
    """
    Base graph retrieval service.
    Provides core CRUD access to nodes and edges.
    """

    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY = 2.0

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        storage: Optional[GraphStorage] = None,
    ):
        self.db = GraphDatabase()
        self.storage = storage
        self._llm_client = llm_client
        logger.info("GraphToolsService initialized successfully (using local GraphDatabase)")

    @property
    def llm(self) -> LLMClient:
        """Lazy initialization of the LLM client"""
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client

    def _node_value(self, node: Any, attr: str, key: str, default: Any = "") -> Any:
        if hasattr(node, attr):
            return getattr(node, attr)
        return node.get(key, default)

    def _node_labels(self, node: Any) -> List[str]:
        if hasattr(node, "labels"):
            return node.labels or []
        label = node.get("label", "Entity")
        return ["Entity"] if label == "Entity" else ["Entity", label]

    def _edge_value(self, edge: Any, attr: str, key: str, default: Any = "") -> Any:
        if hasattr(edge, attr):
            return getattr(edge, attr)
        return edge.get(key, default)

    def _call_with_retry(self, func, operation_name: str, max_retries: int = None):
        """API call with retry mechanism"""
        max_retries = max_retries or self.MAX_RETRIES
        last_exception = None
        delay = self.RETRY_DELAY

        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    logger.warning(
                        f"{operation_name} attempt {attempt + 1} failed: {str(e)[:100]}, "
                        f"retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                    delay *= 2
                else:
                    logger.error(f"{operation_name} still failed after {max_retries} attempts: {str(e)}")

        raise last_exception

    def search_graph(
        self,
        graph_id: str,
        query: str,
        limit: int = 10,
        scope: str = "edges"
    ) -> SearchResult:
        """
        Graph search

        Uses local keyword matching to search for relevant information in the graph.

        Args:
            graph_id: Graph ID (Standalone Graph)
            query: Search query
            limit: Number of results to return
            scope: Search scope, "edges" or "nodes"

        Returns:
            SearchResult: Search results
        """
        logger.info(f"Graph search: graph_id={graph_id}, query={query[:50]}...")

        try:
            if self.storage is not None:
                return self._local_search(graph_id, query, limit, scope)

            search_results = self.db.search(graph_id=graph_id, query=query, limit=limit, scope=scope)

            facts = []
            edges = []
            nodes = []

            for item in search_results:
                if item.get("type") == "edge":
                    fact = item.get("fact", "")
                    if fact:
                        facts.append(fact)
                    edges.append({
                        "uuid": item.get("uuid", ""),
                        "name": item.get("name", ""),
                        "fact": fact,
                        "source_node_uuid": item.get("source_node_uuid", ""),
                        "target_node_uuid": item.get("target_node_uuid", ""),
                    })
                elif item.get("type") == "node":
                    nodes.append({
                        "uuid": item.get("uuid", ""),
                        "name": item.get("name", ""),
                        "labels": item.get("labels", []),
                        "summary": item.get("summary", ""),
                    })
                    # Node summaries also count as facts
                    summary = item.get("summary", "")
                    if summary:
                        facts.append(f"[{item.get('name', '')}]: {summary}")

            logger.info(f"Search completed: found {len(facts)} relevant facts")

            return SearchResult(
                facts=facts,
                edges=edges,
                nodes=nodes,
                query=query,
                total_count=len(facts)
            )

        except Exception as e:
            logger.warning(f"Graph search failed, falling back to local search: {str(e)}")
            return self._local_search(graph_id, query, limit, scope)

    def _local_search(
        self,
        graph_id: str,
        query: str,
        limit: int = 10,
        scope: str = "edges"
    ) -> SearchResult:
        """
        Local keyword matching search (fallback)

        Fetches all edges/nodes and performs local keyword matching.

        Args:
            graph_id: Graph ID
            query: Search query
            limit: Number of results to return
            scope: Search scope

        Returns:
            SearchResult: Search results
        """
        logger.info(f"Using local search: query={query[:30]}...")

        facts = []
        edges_result = []
        nodes_result = []

        # Extract query keywords (simple tokenization)
        query_lower = query.lower()
        keywords = [w.strip() for w in query_lower.replace(',', ' ').replace('，', ' ').split() if len(w.strip()) > 1]

        def match_score(text: str) -> int:
            """Calculate match score between text and query"""
            if not text:
                return 0
            text_lower = text.lower()
            # Exact query match
            if query_lower in text_lower:
                return 100
            # Keyword matching
            score = 0
            for keyword in keywords:
                if keyword in text_lower:
                    score += 10
            return score

        try:
            if scope in ["edges", "both"]:
                # Get all edges and match
                all_edges = self.get_all_edges(graph_id)
                scored_edges = []
                for edge in all_edges:
                    score = match_score(edge.fact) + match_score(edge.name)
                    if score > 0:
                        scored_edges.append((score, edge))

                # Sort by score
                scored_edges.sort(key=lambda x: x[0], reverse=True)

                for score, edge in scored_edges[:limit]:
                    if edge.fact:
                        facts.append(edge.fact)
                    edges_result.append({
                        "uuid": edge.uuid,
                        "name": edge.name,
                        "fact": edge.fact,
                        "source_node_uuid": edge.source_node_uuid,
                        "target_node_uuid": edge.target_node_uuid,
                    })

            if scope in ["nodes", "both"]:
                # Get all nodes and match
                all_nodes = self.get_all_nodes(graph_id)
                scored_nodes = []
                for node in all_nodes:
                    score = match_score(node.name) + match_score(node.summary)
                    if score > 0:
                        scored_nodes.append((score, node))

                scored_nodes.sort(key=lambda x: x[0], reverse=True)

                for score, node in scored_nodes[:limit]:
                    nodes_result.append({
                        "uuid": node.uuid,
                        "name": node.name,
                        "labels": node.labels,
                        "summary": node.summary,
                    })
                    if node.summary:
                        facts.append(f"[{node.name}]: {node.summary}")

            logger.info(f"Local search completed: found {len(facts)} relevant facts")

        except Exception as e:
            logger.error(f"Local search failed: {str(e)}")

        return SearchResult(
            facts=facts,
            edges=edges_result,
            nodes=nodes_result,
            query=query,
            total_count=len(facts)
        )

    def get_all_nodes(self, graph_id: str) -> List[NodeInfo]:
        """
        Get all nodes in the graph

        Args:
            graph_id: Graph ID

        Returns:
            List of nodes
        """
        logger.info(f"Fetching all nodes for graph {graph_id}...")

        if self.storage is not None:
            nodes = self.storage.list_nodes()
        else:
            nodes = self.db.get_all_nodes(graph_id)

        result = []
        for node in nodes:
            result.append(NodeInfo(
                uuid=self._node_value(node, "uuid_", "id") or "",
                name=self._node_value(node, "name", "name") or "",
                labels=self._node_labels(node),
                summary=self._node_value(node, "summary", "summary") or "",
                attributes=self._node_value(node, "attributes", "attributes", {}) or {}
            ))

        logger.info(f"Fetched {len(result)} nodes")
        return result

    def get_all_edges(self, graph_id: str, include_temporal: bool = True) -> List[EdgeInfo]:
        """
        Get all edges in the graph (including temporal information)

        Args:
            graph_id: Graph ID
            include_temporal: Whether to include temporal information (default True)

        Returns:
            List of edges (including created_at, valid_at, invalid_at, expired_at)
        """
        logger.info(f"Fetching all edges for graph {graph_id}...")

        if self.storage is not None:
            edges = self.storage.get_edges()
        else:
            edges = self.db.get_all_edges(graph_id)

        result = []
        for edge in edges:
            edge_info = EdgeInfo(
                uuid=self._edge_value(edge, "uuid_", "id") or "",
                name=self._edge_value(edge, "name", "relation") or "",
                fact=self._edge_value(edge, "fact", "fact") or "",
                source_node_uuid=self._edge_value(edge, "source_node_uuid", "source_id") or "",
                target_node_uuid=self._edge_value(edge, "target_node_uuid", "target_id") or ""
            )

            # Add temporal information
            if include_temporal:
                edge_info.created_at = self._edge_value(edge, "created_at", "created_at", None)
                edge_info.valid_at = self._edge_value(edge, "valid_at", "valid_at", None)
                edge_info.invalid_at = self._edge_value(edge, "invalid_at", "invalid_at", None)
                edge_info.expired_at = self._edge_value(edge, "expired_at", "expired_at", None)

            result.append(edge_info)

        logger.info(f"Fetched {len(result)} edges")
        return result

    def get_node_detail(self, graph_id: str, node_uuid: str) -> Optional[NodeInfo]:
        """
        Get detailed information for a single node

        Args:
            graph_id: Graph ID
            node_uuid: Node UUID

        Returns:
            Node information or None
        """
        logger.info(f"Fetching node detail: {node_uuid[:8]}...")

        try:
            node = self.storage.get_node(node_uuid) if self.storage is not None else self.db.get_node(graph_id, node_uuid)

            if not node:
                return None

            return NodeInfo(
                uuid=self._node_value(node, "uuid_", "id") or "",
                name=self._node_value(node, "name", "name") or "",
                labels=self._node_labels(node),
                summary=self._node_value(node, "summary", "summary") or "",
                attributes=self._node_value(node, "attributes", "attributes", {}) or {}
            )
        except Exception as e:
            logger.error(f"Failed to get node detail: {str(e)}")
            return None

    def get_node_edges(self, graph_id: str, node_uuid: str) -> List[EdgeInfo]:
        """
        Get all edges related to a node

        Args:
            graph_id: Graph ID
            node_uuid: Node UUID

        Returns:
            List of edges
        """
        logger.info(f"Fetching edges for node {node_uuid[:8]}...")

        try:
            if self.storage is not None:
                edges = self.storage.get_edges(source_id=node_uuid) + self.storage.get_edges(target_id=node_uuid)
            else:
                edges = self.db.get_node_edges(graph_id, node_uuid)

            result = []
            for edge in edges:
                result.append(EdgeInfo(
                    uuid=self._edge_value(edge, "uuid_", "id") or "",
                    name=self._edge_value(edge, "name", "relation") or "",
                    fact=self._edge_value(edge, "fact", "fact") or "",
                    source_node_uuid=self._edge_value(edge, "source_node_uuid", "source_id") or "",
                    target_node_uuid=self._edge_value(edge, "target_node_uuid", "target_id") or "",
                    created_at=self._edge_value(edge, "created_at", "created_at", None),
                    valid_at=self._edge_value(edge, "valid_at", "valid_at", None),
                    invalid_at=self._edge_value(edge, "invalid_at", "invalid_at", None),
                    expired_at=self._edge_value(edge, "expired_at", "expired_at", None)
                ))

            logger.info(f"Found {len(result)} edges related to the node")
            return result

        except Exception as e:
            logger.warning(f"Failed to get node edges: {str(e)}")
            return []

    def get_entities_by_type(
        self,
        graph_id: str,
        entity_type: str
    ) -> List[NodeInfo]:
        """
        Get entities by type

        Args:
            graph_id: Graph ID
            entity_type: Entity type (e.g., Student, PublicFigure, etc.)

        Returns:
            List of entities matching the type
        """
        logger.info(f"Fetching entities of type {entity_type}...")

        all_nodes = self.get_all_nodes(graph_id)

        filtered = []
        for node in all_nodes:
            # Check if labels contain the specified type
            if entity_type in node.labels:
                filtered.append(node)

        logger.info(f"Found {len(filtered)} entities of type {entity_type}")
        return filtered

    def get_entity_summary(
        self,
        graph_id: str,
        entity_name: str
    ) -> Dict[str, Any]:
        """
        Get relationship summary for a specified entity

        Searches for all information related to the entity and generates a summary.

        Args:
            graph_id: Graph ID
            entity_name: Entity name

        Returns:
            Entity summary information
        """
        logger.info(f"Fetching relationship summary for entity {entity_name}...")

        # First search for information related to the entity
        search_result = self.search_graph(
            graph_id=graph_id,
            query=entity_name,
            limit=20
        )

        # Try to find the entity among all nodes
        all_nodes = self.get_all_nodes(graph_id)
        entity_node = None
        for node in all_nodes:
            if node.name.lower() == entity_name.lower():
                entity_node = node
                break

        related_edges = []
        if entity_node:
            related_edges = self.get_node_edges(graph_id, entity_node.uuid)

        return {
            "entity_name": entity_name,
            "entity_info": entity_node.to_dict() if entity_node else None,
            "related_facts": search_result.facts,
            "related_edges": [e.to_dict() for e in related_edges],
            "total_relations": len(related_edges)
        }
