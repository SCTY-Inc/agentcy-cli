"""
Graph Builder Service
Builds knowledge graphs using KuzuDB (embedded) + LLM-based entity extraction.
"""

import os
import shutil
import uuid
import threading
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime

from ..models.task import TaskManager, TaskStatus
from .text_processor import TextProcessor
from .graph_db import GraphDatabase
from .graph_storage import GraphStorage
from .entity_extractor import EntityExtractor
from ..utils.logger import get_logger

logger = get_logger('mirofish.graph_builder')


@dataclass
class GraphInfo:
    """Graph information"""
    graph_id: str
    node_count: int
    edge_count: int
    entity_types: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "entity_types": self.entity_types,
        }


class GraphBuilderService:
    """
    Graph Builder Service
    Uses KuzuDB for storage and LLM for entity extraction.
    """

    def __init__(self, api_key: Optional[str] = None, storage: Optional[GraphStorage] = None):
        # api_key parameter kept for backward compatibility from earlier graph backends
        self.db = GraphDatabase()
        self.storage = storage
        self.extractor = EntityExtractor(storage=storage)
        self.task_manager = TaskManager()

    def _get_storage(self, graph_id: str) -> GraphStorage:
        return self.storage or self.db.get_storage(graph_id)

    def _set_storage_metadata(self, key: str, value: Dict[str, Any]) -> None:
        if self.storage is not None and hasattr(self.storage, "set_metadata"):
            self.storage.set_metadata(key, value, datetime.now().isoformat())

    def _get_storage_metadata(self, key: str) -> Optional[Dict[str, Any]]:
        if self.storage is not None and hasattr(self.storage, "get_metadata"):
            value = self.storage.get_metadata(key)
            if isinstance(value, dict):
                return value
        return None

    def build_graph_async(
        self,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str = "MiroFish Graph",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        batch_size: int = 3
    ) -> str:
        """
        Build graph asynchronously.

        Args:
            text: Input text
            ontology: Ontology definition (from ontology generator)
            graph_name: Graph name
            chunk_size: Text chunk size
            chunk_overlap: Chunk overlap size
            batch_size: Chunks per batch for extraction

        Returns:
            Task ID
        """
        task_id = self.task_manager.create_task(
            task_type="graph_build",
            metadata={
                "graph_name": graph_name,
                "chunk_size": chunk_size,
                "text_length": len(text),
            }
        )

        thread = threading.Thread(
            target=self._build_graph_worker,
            args=(task_id, text, ontology, graph_name, chunk_size, chunk_overlap, batch_size)
        )
        thread.daemon = True
        thread.start()

        return task_id

    def _build_graph_worker(
        self,
        task_id: str,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str,
        chunk_size: int,
        chunk_overlap: int,
        batch_size: int
    ):
        """Graph build worker thread"""
        try:
            self.task_manager.update_task(
                task_id,
                status=TaskStatus.PROCESSING,
                progress=5,
                message="Starting graph build..."
            )

            # 1. Create graph
            graph_id = self.create_graph(graph_name)
            self.task_manager.update_task(
                task_id,
                progress=10,
                message=f"Graph created: {graph_id}"
            )

            # 2. Set ontology
            self.set_ontology(graph_id, ontology)
            self.task_manager.update_task(
                task_id,
                progress=15,
                message="Ontology set"
            )

            # 3. Split text into chunks
            chunks = TextProcessor.split_text(text, chunk_size, chunk_overlap)
            total_chunks = len(chunks)
            self.task_manager.update_task(
                task_id,
                progress=20,
                message=f"Text split into {total_chunks} chunks"
            )

            # 4. Extract entities and relationships from chunks
            def extraction_progress(msg, prog):
                progress = 20 + int(prog * 60)  # 20-80%
                self.task_manager.update_task(task_id, progress=progress, message=msg)

            self.task_manager.update_task(
                task_id,
                progress=20,
                message=f"Extracting entities from {total_chunks} chunks..."
            )

            # Store episodes for tracking
            storage = self._get_storage(graph_id)
            episode_uuids = []
            now = datetime.now().isoformat()
            for chunk in chunks:
                episode_id = str(uuid.uuid4())
                storage.add_episode(
                    {
                        "id": episode_id,
                        "content": chunk,
                        "source": "document",
                        "node_ids": [],
                        "processed": False,
                        "created_at": now,
                    }
                )
                episode_uuids.append(episode_id)

            # Extract entities and relationships using LLM
            extraction_result = self.extractor.extract_batch(
                chunks, ontology, progress_callback=extraction_progress
            )

            # 5. Populate graph with extracted data
            self.task_manager.update_task(
                task_id, progress=80,
                message="Populating graph with extracted entities..."
            )

            self._populate_graph(graph_id, extraction_result, episode_uuids)

            # Mark all episodes as processed
            for ep_uuid in episode_uuids:
                storage.mark_episode_processed(ep_uuid)

            # 6. Get graph info
            self.task_manager.update_task(
                task_id, progress=95,
                message="Retrieving graph info..."
            )

            graph_info = self._get_graph_info(graph_id)

            # Complete
            self.task_manager.complete_task(task_id, {
                "graph_id": graph_id,
                "graph_info": graph_info.to_dict(),
                "chunks_processed": total_chunks,
            })

        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            self.task_manager.fail_task(task_id, error_msg)

    def create_graph(self, name: str) -> str:
        """Create a graph (public method)"""
        graph_id = f"mirofish_{uuid.uuid4().hex[:16]}"
        if self.storage is not None:
            self._set_storage_metadata(
                "graph_meta",
                {
                    "graph_id": graph_id,
                    "name": name,
                    "description": "MiroFish Social Simulation Graph",
                    "created_at": datetime.now().isoformat(),
                },
            )
            return graph_id
        self.db.create_graph(graph_id, name, "MiroFish Social Simulation Graph")
        return graph_id

    def set_ontology(self, graph_id: str, ontology: Dict[str, Any]):
        """Set graph ontology (public method)"""
        if self.storage is not None:
            self._set_storage_metadata("ontology", ontology)
            return
        self.db.set_ontology(graph_id, ontology)

    def _populate_graph(
        self,
        graph_id: str,
        extraction_result: Dict[str, Any],
        episode_uuids: List[str]
    ):
        """Populate the graph with extracted entities and relationships"""
        entities = extraction_result.get("entities", [])
        relationships = extraction_result.get("relationships", [])
        storage = self._get_storage(graph_id)

        # Add entities as nodes
        entity_name_to_uuid = {}
        for entity in entities:
            name = entity.get("name", "").strip()
            if not name:
                continue
            entity_type = entity.get("type", "Entity")
            labels = ["Entity", entity_type] if entity_type != "Entity" else ["Entity"]
            summary = entity.get("summary", "")

            node_id = storage.add_node(
                {
                    "id": str(uuid.uuid4()),
                    "name": name,
                    "label": entity_type if entity_type != "Entity" else "Entity",
                    "summary": summary,
                    "facts": [],
                    "attributes": {},
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                }
            )
            entity_name_to_uuid[name.lower()] = node_id

        # Add relationships as edges
        for rel in relationships:
            source_name = rel.get("source", "").strip()
            target_name = rel.get("target", "").strip()
            rel_type = rel.get("type", "related_to")
            fact = rel.get("fact", "")

            source_uuid = entity_name_to_uuid.get(source_name.lower())
            target_uuid = entity_name_to_uuid.get(target_name.lower())

            if not source_uuid or not target_uuid:
                # Try to find or create the missing nodes
                if not source_uuid:
                    source_uuid = storage.add_node(
                        {
                            "id": str(uuid.uuid4()),
                            "name": source_name,
                            "label": "Entity",
                            "summary": "",
                            "facts": [],
                            "attributes": {},
                            "created_at": datetime.now().isoformat(),
                            "updated_at": datetime.now().isoformat(),
                        }
                    )
                    entity_name_to_uuid[source_name.lower()] = source_uuid
                if not target_uuid:
                    target_uuid = storage.add_node(
                        {
                            "id": str(uuid.uuid4()),
                            "name": target_name,
                            "label": "Entity",
                            "summary": "",
                            "facts": [],
                            "attributes": {},
                            "created_at": datetime.now().isoformat(),
                            "updated_at": datetime.now().isoformat(),
                        }
                    )
                    entity_name_to_uuid[target_name.lower()] = target_uuid

            ep_uuid = episode_uuids[0] if episode_uuids else None
            storage.add_edge(
                {
                    "id": str(uuid.uuid4()),
                    "source_id": source_uuid,
                    "target_id": target_uuid,
                    "relation": rel_type,
                    "weight": 1.0,
                    "fact": fact,
                    "attributes": {},
                    "created_at": datetime.now().isoformat(),
                    "episodes": [ep_uuid] if ep_uuid else [],
                }
            )

        logger.info(f"Graph {graph_id} populated: {len(entity_name_to_uuid)} nodes, "
                    f"{len(relationships)} edges")

    def add_text_batches(
        self,
        graph_id: str,
        chunks: List[str],
        batch_size: int = 3,
        progress_callback: Optional[Callable] = None
    ) -> List[str]:
        """
        Add text chunks to graph, extract and populate.
        Returns episode UUIDs.
        """
        # Store episodes
        storage = self._get_storage(graph_id)
        episode_uuids = []
        now = datetime.now().isoformat()
        for chunk in chunks:
            episode_id = str(uuid.uuid4())
            storage.add_episode(
                {
                    "id": episode_id,
                    "content": chunk,
                    "source": "document",
                    "node_ids": [],
                    "processed": False,
                    "created_at": now,
                }
            )
            episode_uuids.append(episode_id)

        # Get ontology for extraction
        ontology = self._get_storage_metadata("ontology") if self.storage is not None else self.db.get_ontology(graph_id)
        ontology = ontology or {"entity_types": [], "edge_types": []}

        # Extract and populate
        extraction_result = self.extractor.extract_batch(
            chunks, ontology, progress_callback=progress_callback
        )
        self._populate_graph(graph_id, extraction_result, episode_uuids)

        # Mark processed
        for ep_uuid in episode_uuids:
            storage.mark_episode_processed(ep_uuid)

        return episode_uuids

    def _wait_for_episodes(
        self,
        episode_uuids: List[str],
        progress_callback: Optional[Callable] = None,
        timeout: int = 600
    ):
        """
        Wait for episodes to be processed.
        With KuzuDB, processing is synchronous so this is a no-op,
        but kept for API compatibility with callers.
        """
        if progress_callback:
            progress_callback(f"Processing complete: {len(episode_uuids)} chunks", 1.0)

    def _get_graph_info(self, graph_id: str) -> GraphInfo:
        """Get graph information"""
        if self.storage is not None:
            raw_nodes = self.storage.list_nodes()
            raw_edges = self.storage.get_edges()
            entity_types = {
                node.get("label", "Entity")
                for node in raw_nodes
                if node.get("label") not in ("Entity", "Node", None, "")
            }
            return GraphInfo(
                graph_id=graph_id,
                node_count=len(raw_nodes),
                edge_count=len(raw_edges),
                entity_types=list(entity_types),
            )

        nodes = self.db.get_all_nodes(graph_id)
        edges = self.db.get_all_edges(graph_id)

        entity_types = set()
        for node in nodes:
            for label in node.labels:
                if label not in ("Entity", "Node"):
                    entity_types.add(label)

        return GraphInfo(
            graph_id=graph_id,
            node_count=len(nodes),
            edge_count=len(edges),
            entity_types=list(entity_types)
        )

    def get_graph_data(self, graph_id: str) -> Dict[str, Any]:
        """Get complete graph data (nodes and edges with details)"""
        if self.storage is not None:
            nodes = self.storage.list_nodes()
            edges = self.storage.get_edges()
            node_map = {node["id"]: node["name"] for node in nodes}
            return {
                "graph_id": graph_id,
                "nodes": [
                    {
                        "uuid": node["id"],
                        "name": node["name"],
                        "labels": ["Entity"] if node.get("label", "Entity") == "Entity" else ["Entity", node["label"]],
                        "summary": node.get("summary", ""),
                        "attributes": node.get("attributes", {}),
                        "facts": node.get("facts", []),
                        "created_at": node.get("created_at", ""),
                        "updated_at": node.get("updated_at", ""),
                    }
                    for node in nodes
                ],
                "edges": [
                    {
                        "uuid": edge["id"],
                        "name": edge["relation"],
                        "fact": edge.get("fact", ""),
                        "fact_type": edge.get("relation", ""),
                        "source_node_uuid": edge["source_id"],
                        "target_node_uuid": edge["target_id"],
                        "source_node_name": node_map.get(edge["source_id"], ""),
                        "target_node_name": node_map.get(edge["target_id"], ""),
                        "attributes": edge.get("attributes", {}),
                        "weight": edge.get("weight", 1.0),
                        "created_at": edge.get("created_at", ""),
                        "valid_at": edge.get("valid_at"),
                        "invalid_at": edge.get("invalid_at"),
                        "expired_at": edge.get("expired_at"),
                        "episodes": edge.get("episodes", []),
                    }
                    for edge in edges
                ],
                "node_count": len(nodes),
                "edge_count": len(edges),
            }
        return self.db.get_graph_data(graph_id)

    def delete_graph(self, graph_id: str):
        """Delete a graph"""
        if self.storage is not None:
            storage_path = getattr(self.storage, "db_path", None) or getattr(self.storage, "data_dir", None)
            self.storage.close()
            if storage_path and os.path.exists(storage_path):
                shutil.rmtree(storage_path, ignore_errors=True)
            return
        self.db.delete_graph(graph_id)
