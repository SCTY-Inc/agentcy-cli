"""
Graph storage abstraction and concrete backends.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, Optional

from ..utils.logger import get_logger

logger = get_logger("mirofish.graph_storage")


class StorageError(RuntimeError):
    """Raised when a graph storage operation fails."""


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _parse_json_dict(value: Any) -> Dict[str, Any]:
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _parse_json_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return [value]
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    return [str(value)]


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _node_payload(node: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(node.get("id", "")),
        "name": str(node.get("name", "")).strip(),
        "label": str(node.get("label", "Entity") or "Entity"),
        "summary": str(node.get("summary", "") or ""),
        "facts": _parse_json_list(node.get("facts", [])),
        "attributes": node.get("attributes") if isinstance(node.get("attributes"), dict) else _parse_json_dict(node.get("attributes")),
        "created_at": str(node.get("created_at", "") or ""),
        "updated_at": str(node.get("updated_at", "") or node.get("created_at", "") or ""),
    }


def _edge_payload(edge: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(edge.get("id", "")),
        "source_id": str(edge.get("source_id", "")),
        "target_id": str(edge.get("target_id", "")),
        "relation": str(edge.get("relation", "")).strip(),
        "weight": float(edge.get("weight", 1.0) or 0.0),
        "fact": str(edge.get("fact", "") or ""),
        "attributes": edge.get("attributes") if isinstance(edge.get("attributes"), dict) else _parse_json_dict(edge.get("attributes")),
        "created_at": str(edge.get("created_at", "") or ""),
        "valid_at": edge.get("valid_at"),
        "invalid_at": edge.get("invalid_at"),
        "expired_at": edge.get("expired_at"),
        "episodes": _parse_json_list(edge.get("episodes", [])),
    }


def _episode_payload(episode: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(episode.get("id", "")),
        "content": str(episode.get("content", "") or ""),
        "source": str(episode.get("source", "document") or "document"),
        "node_ids": _parse_json_list(episode.get("node_ids", [])),
        "processed": _parse_bool(episode.get("processed", False)),
        "created_at": str(episode.get("created_at", "") or ""),
    }


class GraphStorage(ABC):
    @abstractmethod
    def add_node(self, node: dict) -> str:
        ...

    @abstractmethod
    def get_node(self, node_id: str) -> Optional[dict]:
        ...

    @abstractmethod
    def get_node_by_name(self, name: str) -> Optional[dict]:
        ...

    @abstractmethod
    def update_node(self, node_id: str, updates: dict) -> bool:
        ...

    @abstractmethod
    def delete_node(self, node_id: str) -> bool:
        ...

    @abstractmethod
    def list_nodes(self, label: Optional[str] = None) -> list[dict]:
        ...

    @abstractmethod
    def add_edge(self, edge: dict) -> str:
        ...

    @abstractmethod
    def get_edges(
        self,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        relation: Optional[str] = None,
    ) -> list[dict]:
        ...

    @abstractmethod
    def add_episode(self, episode: dict) -> str:
        ...

    @abstractmethod
    def get_unprocessed_episodes(self) -> list[dict]:
        ...

    @abstractmethod
    def mark_episode_processed(self, episode_id: str) -> bool:
        ...

    @abstractmethod
    def search_nodes(self, query: str, label: Optional[str] = None, limit: int = 10) -> list[dict]:
        ...

    @abstractmethod
    def get_neighbors(self, node_id: str, depth: int = 1) -> list[dict]:
        ...

    @abstractmethod
    def get_stats(self) -> dict:
        ...

    @abstractmethod
    def close(self) -> None:
        ...


class JSONStorage(GraphStorage):
    """JSON-file fallback storage."""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)

    @property
    def _nodes_path(self) -> str:
        return os.path.join(self.data_dir, "nodes.json")

    @property
    def _edges_path(self) -> str:
        return os.path.join(self.data_dir, "edges.json")

    @property
    def _episodes_path(self) -> str:
        return os.path.join(self.data_dir, "episodes.json")

    @property
    def _metadata_path(self) -> str:
        return os.path.join(self.data_dir, "metadata.json")

    def _load_json(self, path: str, default: Any) -> Any:
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def _save_json(self, path: str, value: Any) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)

    def _load_nodes(self) -> list[dict]:
        return [_node_payload(node) for node in self._load_json(self._nodes_path, [])]

    def _save_nodes(self, nodes: Iterable[dict]) -> None:
        self._save_json(self._nodes_path, list(nodes))

    def _load_edges(self) -> list[dict]:
        return [_edge_payload(edge) for edge in self._load_json(self._edges_path, [])]

    def _save_edges(self, edges: Iterable[dict]) -> None:
        self._save_json(self._edges_path, list(edges))

    def _load_episodes(self) -> list[dict]:
        return [_episode_payload(episode) for episode in self._load_json(self._episodes_path, [])]

    def _save_episodes(self, episodes: Iterable[dict]) -> None:
        self._save_json(self._episodes_path, list(episodes))

    def add_node(self, node: dict) -> str:
        payload = _node_payload(node)
        nodes = self._load_nodes()
        for index, existing in enumerate(nodes):
            if existing["name"].lower() == payload["name"].lower():
                merged = {
                    **existing,
                    **payload,
                    "facts": list(dict.fromkeys(existing.get("facts", []) + payload["facts"])),
                    "attributes": {**existing.get("attributes", {}), **payload["attributes"]},
                    "summary": payload["summary"] or existing.get("summary", ""),
                    "label": payload["label"] or existing.get("label", "Entity"),
                }
                nodes[index] = merged
                self._save_nodes(nodes)
                return existing["id"]
        nodes.append(payload)
        self._save_nodes(nodes)
        return payload["id"]

    def get_node(self, node_id: str) -> Optional[dict]:
        for node in self._load_nodes():
            if node["id"] == node_id:
                return node
        return None

    def get_node_by_name(self, name: str) -> Optional[dict]:
        normalized = name.strip().lower()
        for node in self._load_nodes():
            if node["name"].lower() == normalized:
                return node
        return None

    def update_node(self, node_id: str, updates: dict) -> bool:
        nodes = self._load_nodes()
        for index, existing in enumerate(nodes):
            if existing["id"] != node_id:
                continue
            nodes[index] = {**existing, **_node_payload({**existing, **updates})}
            self._save_nodes(nodes)
            return True
        return False

    def delete_node(self, node_id: str) -> bool:
        nodes = self._load_nodes()
        filtered_nodes = [node for node in nodes if node["id"] != node_id]
        if len(filtered_nodes) == len(nodes):
            return False
        self._save_nodes(filtered_nodes)
        self._save_edges(
            [
                edge
                for edge in self._load_edges()
                if edge["source_id"] != node_id and edge["target_id"] != node_id
            ]
        )
        return True

    def list_nodes(self, label: Optional[str] = None) -> list[dict]:
        nodes = sorted(self._load_nodes(), key=lambda item: item.get("name", ""))
        if label:
            return [node for node in nodes if node.get("label") == label]
        return nodes

    def add_edge(self, edge: dict) -> str:
        payload = _edge_payload(edge)
        if not self.get_node(payload["source_id"]) or not self.get_node(payload["target_id"]):
            raise StorageError(
                f"Edge {payload['id']} references missing nodes: "
                f"{payload['source_id']} -> {payload['target_id']}"
            )
        edges = self._load_edges()
        edges.append(payload)
        self._save_edges(edges)
        return payload["id"]

    def get_edges(
        self,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        relation: Optional[str] = None,
    ) -> list[dict]:
        edges = self._load_edges()
        filtered = []
        for edge in edges:
            if source_id and edge["source_id"] != source_id:
                continue
            if target_id and edge["target_id"] != target_id:
                continue
            if relation and edge["relation"] != relation:
                continue
            filtered.append(edge)
        return filtered

    def add_episode(self, episode: dict) -> str:
        payload = _episode_payload(episode)
        episodes = self._load_episodes()
        episodes.append(payload)
        self._save_episodes(episodes)
        return payload["id"]

    def get_episode(self, episode_id: str) -> Optional[dict]:
        for episode in self._load_episodes():
            if episode["id"] == episode_id:
                return episode
        return None

    def get_unprocessed_episodes(self) -> list[dict]:
        return [episode for episode in self._load_episodes() if not episode.get("processed", False)]

    def mark_episode_processed(self, episode_id: str) -> bool:
        episodes = self._load_episodes()
        for index, episode in enumerate(episodes):
            if episode["id"] != episode_id:
                continue
            updated = dict(episode)
            updated["processed"] = True
            episodes[index] = updated
            self._save_episodes(episodes)
            return True
        return False

    def search_nodes(self, query: str, label: Optional[str] = None, limit: int = 10) -> list[dict]:
        query_terms = [term for term in query.lower().split() if term]
        scored = []
        for node in self.list_nodes(label=label):
            haystack = " ".join(
                [
                    node.get("name", ""),
                    node.get("label", ""),
                    node.get("summary", ""),
                    " ".join(node.get("facts", [])),
                    _json_dumps(node.get("attributes", {})),
                ]
            ).lower()
            score = sum(1 for term in query_terms if term in haystack)
            if score:
                scored.append((score, node))
        scored.sort(key=lambda item: (-item[0], item[1].get("name", "")))
        return [node for _, node in scored[:limit]]

    def get_neighbors(self, node_id: str, depth: int = 1) -> list[dict]:
        depth = max(depth, 1)
        seen = {node_id}
        frontier = {node_id}
        neighbors: list[dict] = []
        for _ in range(depth):
            next_frontier = set()
            for current in frontier:
                for edge in self.get_edges(source_id=current):
                    neighbor = self.get_node(edge["target_id"])
                    if neighbor and neighbor["id"] not in seen:
                        seen.add(neighbor["id"])
                        next_frontier.add(neighbor["id"])
                        neighbors.append(neighbor)
                for edge in self.get_edges(target_id=current):
                    neighbor = self.get_node(edge["source_id"])
                    if neighbor and neighbor["id"] not in seen:
                        seen.add(neighbor["id"])
                        next_frontier.add(neighbor["id"])
                        neighbors.append(neighbor)
            frontier = next_frontier
            if not frontier:
                break
        return neighbors

    def get_stats(self) -> dict:
        nodes = self._load_nodes()
        edges = self._load_edges()
        episodes = self._load_episodes()
        return {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "episode_count": len(episodes),
            "unprocessed_episode_count": len([episode for episode in episodes if not episode.get("processed", False)]),
        }

    def set_metadata(self, key: str, value: Any, updated_at: str) -> None:
        metadata = self._load_json(self._metadata_path, {})
        metadata[key] = {
            "value": value,
            "updated_at": updated_at,
        }
        self._save_json(self._metadata_path, metadata)

    def get_metadata(self, key: str) -> Any:
        metadata = self._load_json(self._metadata_path, {})
        entry = metadata.get(key)
        if not entry:
            return None
        return entry.get("value")

    def close(self) -> None:
        return None
