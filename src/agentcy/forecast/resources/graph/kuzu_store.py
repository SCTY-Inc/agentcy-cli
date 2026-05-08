"""Graph store adapter."""

from typing import Any, Dict, Optional

from ...services.graph_db import GraphDatabase


class GraphStore:
    """Thin adapter around the graph database."""

    def __init__(self, db: Optional[GraphDatabase] = None):
        self.db = db or GraphDatabase()

    def get_database(self) -> GraphDatabase:
        return self.db

    def create_graph(self, graph_id: str, name: str, description: str = "") -> str:
        return self.db.create_graph(graph_id, name, description)

    def delete_graph(self, graph_id: str):
        self.db.delete_graph(graph_id)

    def set_ontology(self, graph_id: str, ontology: Dict[str, Any]):
        self.db.set_ontology(graph_id, ontology)

    def get_ontology(self, graph_id: str):
        return self.db.get_ontology(graph_id)

    def get_graph_data(self, graph_id: str) -> Dict[str, Any]:
        return self.db.get_graph_data(graph_id)

    def get_graph_statistics(self, graph_id: str) -> Dict[str, Any]:
        return self.db.get_graph_statistics(graph_id)

    def search(self, graph_id: str, query: str, limit: int = 10, scope: str = "edges"):
        return self.db.search(graph_id, query=query, limit=limit, scope=scope)

# Backward compat alias
KuzuGraphStore = GraphStore
