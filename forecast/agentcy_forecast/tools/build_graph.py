"""Tool for building a graph from a project ontology and extracted text."""

import threading
from typing import Any, Dict, Optional

from ..config import Config
from ..core.session_manager import SessionManager
from ..core.task_manager import TaskManager, TaskStatus
from ..models.project import ProjectStatus
from ..resources.documents import DocumentStore
from ..resources.projects import ProjectStore
from ..services.graph_builder import GraphBuilderService
from ..services.text_processor import TextProcessor
from ..utils.logger import get_logger

logger = get_logger("mirofish.tools.build_graph")


class BuildGraphTool:
    """Run graph construction as a background task."""

    def __init__(
        self,
        project_store: Optional[ProjectStore] = None,
        document_store: Optional[DocumentStore] = None,
        task_manager: Optional[TaskManager] = None,
        session_manager: Optional[SessionManager] = None,
    ):
        self.project_store = project_store or ProjectStore()
        self.document_store = document_store or DocumentStore()
        self.task_manager = task_manager or TaskManager()
        self.session_manager = session_manager or SessionManager()

    def start(
        self,
        project_id: str,
        graph_name: Optional[str] = None,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        force: bool = False,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        project = self.project_store.get(project_id)
        if not project:
            raise FileNotFoundError(f"Project not found: {project_id}")

        if project.status == ProjectStatus.CREATED:
            raise ValueError("Ontology not yet generated for this project, please call /ontology/generate first")

        if project.status == ProjectStatus.GRAPH_BUILDING and not force:
            raise ValueError("Graph is currently being built, please do not submit again. To force rebuild, add force: true")

        if force and project.status in [ProjectStatus.GRAPH_BUILDING, ProjectStatus.FAILED, ProjectStatus.GRAPH_COMPLETED]:
            project.status = ProjectStatus.ONTOLOGY_GENERATED
            project.graph_id = None
            project.graph_build_task_id = None
            project.error = None

        graph_name = graph_name or project.name or "MiroFish Graph"
        chunk_size = chunk_size or project.chunk_size or Config.DEFAULT_CHUNK_SIZE
        chunk_overlap = chunk_overlap or project.chunk_overlap or Config.DEFAULT_CHUNK_OVERLAP

        text = self.document_store.get_extracted_text(project_id)
        if not text:
            raise ValueError("Extracted text content not found")

        ontology = project.ontology
        if not ontology:
            raise ValueError("Ontology definition not found")

        session = self.session_manager.get_or_create(
            project_id=project_id,
            graph_id=project.graph_id,
            metadata={"workflow": "foresight_workbench", "phase": "graph"},
        )
        if session_id and session.session_id != session_id:
            session = self.session_manager.attach(session_id, project_id=project_id) or session

        task_id = self.task_manager.create_task(
            task_type="graph_build",
            metadata={"project_id": project_id, "graph_name": graph_name, "session_id": session.session_id},
        )

        project.status = ProjectStatus.GRAPH_BUILDING
        project.graph_build_task_id = task_id
        project.chunk_size = chunk_size
        project.chunk_overlap = chunk_overlap
        self.project_store.save(project)

        def run_build():
            build_logger = get_logger("mirofish.build")
            try:
                build_logger.info(f"[{task_id}] Starting graph build...")
                self.task_manager.update_task(
                    task_id,
                    status=TaskStatus.PROCESSING,
                    message="Initializing graph build service...",
                )

                builder = GraphBuilderService()

                self.task_manager.update_task(task_id, message="Splitting text into chunks...", progress=5)
                chunks = TextProcessor.split_text(text, chunk_size=chunk_size, overlap=chunk_overlap)
                total_chunks = len(chunks)

                self.task_manager.update_task(task_id, message="Creating graph...", progress=10)
                graph_id = builder.create_graph(name=graph_name)

                project.graph_id = graph_id
                self.project_store.save(project)
                self.session_manager.attach(session.session_id, project_id=project_id, graph_id=graph_id)

                self.task_manager.update_task(task_id, message="Setting ontology definition...", progress=15)
                builder.set_ontology(graph_id, ontology)

                def add_progress_callback(msg, progress_ratio):
                    progress = 15 + int(progress_ratio * 40)
                    self.task_manager.update_task(task_id, message=msg, progress=progress)

                self.task_manager.update_task(
                    task_id,
                    message=f"Starting to add {total_chunks} text chunks...",
                    progress=15,
                )
                episode_uuids = builder.add_text_batches(
                    graph_id,
                    chunks,
                    batch_size=3,
                    progress_callback=add_progress_callback,
                )

                self.task_manager.update_task(task_id, message="Processing graph data...", progress=55)

                def wait_progress_callback(msg, progress_ratio):
                    progress = 55 + int(progress_ratio * 35)
                    self.task_manager.update_task(task_id, message=msg, progress=progress)

                builder._wait_for_episodes(episode_uuids, wait_progress_callback)

                self.task_manager.update_task(task_id, message="Fetching graph data...", progress=95)
                graph_data = builder.get_graph_data(graph_id)

                project.status = ProjectStatus.GRAPH_COMPLETED
                self.project_store.save(project)
                self.session_manager.attach(session.session_id, project_id=project_id, graph_id=graph_id, metadata={"phase": "graph_completed"})

                node_count = graph_data.get("node_count", 0)
                edge_count = graph_data.get("edge_count", 0)
                self.task_manager.complete_task(
                    task_id,
                    result={
                        "project_id": project_id,
                        "session_id": session.session_id,
                        "graph_id": graph_id,
                        "node_count": node_count,
                        "edge_count": edge_count,
                        "chunk_count": total_chunks,
                    },
                )
            except Exception as exc:
                build_logger.error(f"[{task_id}] Graph build failed: {exc}")
                project.status = ProjectStatus.FAILED
                project.error = str(exc)
                self.project_store.save(project)
                self.task_manager.update_task(
                    task_id,
                    status=TaskStatus.FAILED,
                    message=f"Build failed: {exc}",
                    error=str(exc),
                )

        thread = threading.Thread(target=run_build, daemon=True)
        thread.start()

        return {
            "project_id": project_id,
            "session_id": session.session_id,
            "task_id": task_id,
            "message": "Graph build task started, check progress via /task/{task_id}",
        }
