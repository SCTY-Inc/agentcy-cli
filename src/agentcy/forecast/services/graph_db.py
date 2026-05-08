"""
Graph database service built on top of the GraphStorage abstraction.
"""

from __future__ import annotations

import json
import os
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .graph_storage import GraphStorage, JSONStorage
from ..config import Config
from ..utils.logger import get_logger

logger = get_logger("mirofish.graph_db")


@dataclass
class GraphNode:
    """Node in the knowledge graph."""

    uuid_: str
    name: str
    labels: List[str] = field(default_factory=lambda: ["Entity"])
    summary: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)
    facts: List[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid_,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes,
            "facts": self.facts,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class GraphEdge:
    """Edge (relationship) in the knowledge graph."""

    uuid_: str
    name: str
    fact: str = ""
    fact_type: str = ""
    source_node_uuid: str = ""
    target_node_uuid: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0
    created_at: str = ""
    valid_at: Optional[str] = None
    invalid_at: Optional[str] = None
    expired_at: Optional[str] = None
    episodes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid_,
            "name": self.name,
            "fact": self.fact,
            "fact_type": self.fact_type,
            "source_node_uuid": self.source_node_uuid,
            "target_node_uuid": self.target_node_uuid,
            "attributes": self.attributes,
            "weight": self.weight,
            "created_at": self.created_at,
            "valid_at": self.valid_at,
            "invalid_at": self.invalid_at,
            "expired_at": self.expired_at,
            "episodes": self.episodes,
        }


@dataclass
class Episode:
    """Text episode added to the graph for processing."""

    uuid_: str
    data: str
    type: str = "document"
    node_ids: List[str] = field(default_factory=list)
    processed: bool = False
    created_at: str = ""


class GraphDatabase:
    """
    Graph database facade.

    This class preserves the existing multi-graph API surface while delegating
    graph persistence to a per-graph GraphStorage implementation.
    """

    def __init__(
        self,
        base_path: Optional[str] = None,
        storage_backend: Optional[str] = None,
    ):
        _ = storage_backend
        self.base_path = base_path or Config.DATA_DIR
        os.makedirs(self.base_path, exist_ok=True)

    def _graph_dir(self, graph_id: str) -> str:
        return os.path.join(self.base_path, graph_id)

    def _make_storage(self, graph_id: str, create: bool = False) -> GraphStorage:
        graph_dir = self._graph_dir(graph_id)
        if create:
            os.makedirs(graph_dir, exist_ok=True)
        if not os.path.isdir(graph_dir):
            raise FileNotFoundError(f"Graph database not found: {graph_id}")
        return JSONStorage(graph_dir)

    def get_storage(self, graph_id: str, create: bool = False) -> GraphStorage:
        """Return the storage backend for a specific graph."""
        return self._make_storage(graph_id, create=create)

    def _node_label_to_list(self, label: str) -> List[str]:
        labels = ["Entity"]
        if label and label not in {"Entity", "Node"}:
            labels.append(label)
        return labels

    def _node_list_to_label(self, labels: List[str]) -> str:
        for label in labels:
            if label not in {"Entity", "Node"}:
                return label
        return "Entity"

    def _dict_to_node(self, node: Dict[str, Any]) -> GraphNode:
        return GraphNode(
            uuid_=node.get("id", ""),
            name=node.get("name", ""),
            labels=self._node_label_to_list(node.get("label", "Entity")),
            summary=node.get("summary", ""),
            attributes=node.get("attributes", {}),
            facts=node.get("facts", []),
            created_at=node.get("created_at", ""),
            updated_at=node.get("updated_at", ""),
        )

    def _dict_to_edge(self, edge: Dict[str, Any]) -> GraphEdge:
        return GraphEdge(
            uuid_=edge.get("id", ""),
            name=edge.get("relation", ""),
            fact=edge.get("fact", ""),
            fact_type=edge.get("relation", ""),
            source_node_uuid=edge.get("source_id", ""),
            target_node_uuid=edge.get("target_id", ""),
            attributes=edge.get("attributes", {}),
            weight=float(edge.get("weight", 1.0) or 0.0),
            created_at=edge.get("created_at", ""),
            valid_at=edge.get("valid_at"),
            invalid_at=edge.get("invalid_at"),
            expired_at=edge.get("expired_at"),
            episodes=edge.get("episodes", []),
        )

    def _dict_to_episode(self, episode: Dict[str, Any]) -> Episode:
        return Episode(
            uuid_=episode.get("id", ""),
            data=episode.get("content", ""),
            type=episode.get("source", "document"),
            node_ids=episode.get("node_ids", []),
            processed=bool(episode.get("processed", False)),
            created_at=episode.get("created_at", ""),
        )

    def _set_metadata(self, storage: GraphStorage, key: str, value: Any) -> None:
        updated_at = datetime.now().isoformat()
        if hasattr(storage, "set_metadata"):
            storage.set_metadata(key, value, updated_at)
            return
        metadata_path = os.path.join(self.base_path, f"{key}.json")
        with open(metadata_path, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)

    def _get_metadata(self, storage: GraphStorage, key: str) -> Any:
        if hasattr(storage, "get_metadata"):
            return storage.get_metadata(key)
        return None

    # ========== Graph Management ==========

    def create_graph(self, graph_id: str, name: str, description: str = "") -> str:
        storage = self.get_storage(graph_id, create=True)
        self._set_metadata(
            storage,
            "graph_meta",
            {
                "graph_id": graph_id,
                "name": name,
                "description": description,
                "created_at": datetime.now().isoformat(),
            },
        )
        self._set_metadata(storage, "ontology", {"entity_types": [], "edge_types": []})
        logger.info("Created graph: %s (%s)", graph_id, name)
        return graph_id

    def delete_graph(self, graph_id: str):
        graph_dir = self._graph_dir(graph_id)
        if os.path.isdir(graph_dir):
            shutil.rmtree(graph_dir)
            logger.info("Deleted graph: %s", graph_id)

    def graph_exists(self, graph_id: str) -> bool:
        return os.path.isdir(self._graph_dir(graph_id))

    def set_ontology(self, graph_id: str, ontology: Dict[str, Any]):
        storage = self.get_storage(graph_id)
        self._set_metadata(storage, "ontology", ontology)
        logger.info(
            "Set ontology for graph %s: %s entity types, %s edge types",
            graph_id,
            len(ontology.get("entity_types", [])),
            len(ontology.get("edge_types", [])),
        )

    def get_ontology(self, graph_id: str) -> Optional[Dict[str, Any]]:
        storage = self.get_storage(graph_id)
        ontology = self._get_metadata(storage, "ontology")
        return ontology if isinstance(ontology, dict) else None

    # ========== Episode Management ==========

    def add_episode(self, graph_id: str, data: str, type: str = "document") -> Episode:
        storage = self.get_storage(graph_id)
        episode = {
            "id": str(uuid.uuid4()),
            "content": data,
            "source": type,
            "node_ids": [],
            "processed": False,
            "created_at": datetime.now().isoformat(),
        }
        storage.add_episode(episode)
        return self._dict_to_episode(episode)

    def add_episodes_batch(self, graph_id: str, texts: List[str]) -> List[Episode]:
        storage = self.get_storage(graph_id)
        now = datetime.now().isoformat()
        episodes = []
        for text in texts:
            episode = {
                "id": str(uuid.uuid4()),
                "content": text,
                "source": "document",
                "node_ids": [],
                "processed": False,
                "created_at": now,
            }
            storage.add_episode(episode)
            episodes.append(self._dict_to_episode(episode))
        return episodes

    def mark_episode_processed(self, graph_id: str, episode_uuid: str):
        storage = self.get_storage(graph_id)
        storage.mark_episode_processed(episode_uuid)

    def get_episode(self, graph_id: str, episode_uuid: str) -> Optional[Episode]:
        storage = self.get_storage(graph_id)
        if not hasattr(storage, "get_episode"):
            return None
        episode = storage.get_episode(episode_uuid)
        return self._dict_to_episode(episode) if episode else None

    # ========== Node Operations ==========

    def add_node(
        self,
        graph_id: str,
        name: str,
        labels: List[str],
        summary: str = "",
        attributes: Optional[Dict[str, Any]] = None,
        node_uuid: Optional[str] = None,
    ) -> GraphNode:
        storage = self.get_storage(graph_id)
        node = {
            "id": node_uuid or str(uuid.uuid4()),
            "name": name,
            "label": self._node_list_to_label(labels or ["Entity"]),
            "summary": summary,
            "facts": [],
            "attributes": attributes or {},
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        node_id = storage.add_node(node)
        stored = storage.get_node(node_id)
        return self._dict_to_node(stored or node)

    def get_node(self, graph_id: str, node_uuid: str) -> Optional[GraphNode]:
        storage = self.get_storage(graph_id)
        node = storage.get_node(node_uuid)
        return self._dict_to_node(node) if node else None

    def get_node_by_name(self, graph_id: str, name: str) -> Optional[GraphNode]:
        storage = self.get_storage(graph_id)
        node = storage.get_node_by_name(name)
        return self._dict_to_node(node) if node else None

    def get_all_nodes(self, graph_id: str) -> List[GraphNode]:
        storage = self.get_storage(graph_id)
        return [self._dict_to_node(node) for node in storage.list_nodes()]

    def get_node_edges(self, graph_id: str, node_uuid: str) -> List[GraphEdge]:
        storage = self.get_storage(graph_id)
        edges = storage.get_edges(source_id=node_uuid) + storage.get_edges(target_id=node_uuid)
        seen = set()
        result = []
        for edge in edges:
            if edge["id"] in seen:
                continue
            seen.add(edge["id"])
            result.append(self._dict_to_edge(edge))
        return result

    # ========== Edge Operations ==========

    def add_edge(
        self,
        graph_id: str,
        source_node_uuid: str,
        target_node_uuid: str,
        name: str,
        fact: str = "",
        fact_type: str = "",
        attributes: Optional[Dict[str, Any]] = None,
        episode_uuid: Optional[str] = None,
    ) -> GraphEdge:
        storage = self.get_storage(graph_id)
        edge = {
            "id": str(uuid.uuid4()),
            "source_id": source_node_uuid,
            "target_id": target_node_uuid,
            "relation": name,
            "weight": 1.0,
            "fact": fact,
            "attributes": attributes or {},
            "created_at": datetime.now().isoformat(),
            "valid_at": None,
            "invalid_at": None,
            "expired_at": None,
            "episodes": [episode_uuid] if episode_uuid else [],
        }
        edge_id = storage.add_edge(edge)
        stored = next((item for item in storage.get_edges() if item["id"] == edge_id), edge)
        return self._dict_to_edge(stored)

    def get_all_edges(self, graph_id: str) -> List[GraphEdge]:
        storage = self.get_storage(graph_id)
        return [self._dict_to_edge(edge) for edge in storage.get_edges()]

    # ========== Search ==========

    def search(self, graph_id: str, query: str, limit: int = 10, scope: str = "edges") -> List[Dict[str, Any]]:
        query_terms = [term for term in query.lower().split() if term]
        results = []
        storage = self.get_storage(graph_id)

        if scope in ("edges", "both"):
            nodes = self.get_all_nodes(graph_id)
            node_map = {node.uuid_: node.name for node in nodes}
            for edge in storage.get_edges():
                haystack = f"{edge.get('relation', '')} {edge.get('fact', '')}".lower()
                score = sum(1 for term in query_terms if term in haystack)
                if not score:
                    continue
                results.append(
                    {
                        "type": "edge",
                        "uuid": edge.get("id", ""),
                        "name": edge.get("relation", ""),
                        "fact": edge.get("fact", ""),
                        "source_node_uuid": edge.get("source_id", ""),
                        "target_node_uuid": edge.get("target_id", ""),
                        "source_node_name": node_map.get(edge.get("source_id", ""), ""),
                        "target_node_name": node_map.get(edge.get("target_id", ""), ""),
                        "score": score / len(query_terms) if query_terms else 0,
                    }
                )

        if scope in ("nodes", "both"):
            for node in storage.search_nodes(query, limit=limit):
                haystack = " ".join(
                    [
                        node.get("name", ""),
                        node.get("summary", ""),
                        json.dumps(node.get("attributes", {}), ensure_ascii=False),
                    ]
                ).lower()
                score = sum(1 for term in query_terms if term in haystack)
                results.append(
                    {
                        "type": "node",
                        "uuid": node.get("id", ""),
                        "name": node.get("name", ""),
                        "labels": self._node_label_to_list(node.get("label", "Entity")),
                        "summary": node.get("summary", ""),
                        "score": score / len(query_terms) if query_terms else 0,
                    }
                )

        results.sort(key=lambda item: item.get("score", 0), reverse=True)
        return results[:limit]

    # ========== Graph Data Export ==========

    def get_graph_data(self, graph_id: str) -> Dict[str, Any]:
        nodes = self.get_all_nodes(graph_id)
        edges = self.get_all_edges(graph_id)
        node_map = {node.uuid_: node.name for node in nodes}

        nodes_data = [node.to_dict() for node in nodes]
        edges_data = []
        for edge in edges:
            item = edge.to_dict()
            item["source_node_name"] = node_map.get(edge.source_node_uuid, "")
            item["target_node_name"] = node_map.get(edge.target_node_uuid, "")
            edges_data.append(item)

        return {
            "graph_id": graph_id,
            "nodes": nodes_data,
            "edges": edges_data,
            "node_count": len(nodes_data),
            "edge_count": len(edges_data),
        }

    def get_graph_statistics(self, graph_id: str) -> Dict[str, Any]:
        nodes = self.get_all_nodes(graph_id)
        edges = self.get_all_edges(graph_id)

        type_counts: Dict[str, int] = {}
        for node in nodes:
            for label in node.labels:
                if label not in {"Entity", "Node"}:
                    type_counts[label] = type_counts.get(label, 0) + 1

        relation_counts: Dict[str, int] = {}
        for edge in edges:
            relation_counts[edge.name] = relation_counts.get(edge.name, 0) + 1

        return {
            "graph_id": graph_id,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "entity_type_counts": type_counts,
            "relationship_type_counts": relation_counts,
        }
