"""Tool for document ingestion and ontology generation."""

from typing import Any, Dict, Iterable, Optional

from ..config import Config
from ..models.project import ProjectStatus
from ..services.ontology_generator import OntologyGenerator
from ..services.text_processor import TextProcessor
from ..utils.file_parser import FileParser
from ..utils.logger import get_logger
from ..resources.documents import DocumentStore
from ..resources.projects import ProjectStore
from ..core.session_manager import SessionManager

logger = get_logger("mirofish.tools.generate_ontology")


class GenerateOntologyTool:
    """Ingest uploaded documents and produce a project ontology."""

    def __init__(
        self,
        project_store: Optional[ProjectStore] = None,
        document_store: Optional[DocumentStore] = None,
        session_manager: Optional[SessionManager] = None,
    ):
        self.project_store = project_store or ProjectStore()
        self.document_store = document_store or DocumentStore()
        self.session_manager = session_manager or SessionManager()

    def _allowed_file(self, filename: str) -> bool:
        if not filename or "." not in filename:
            return False
        ext = filename.rsplit(".", 1)[-1].lower()
        return ext in Config.ALLOWED_EXTENSIONS

    def execute(
        self,
        simulation_requirement: str,
        uploaded_files: Iterable[Any],
        project_name: str = "Unnamed Project",
        additional_context: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not simulation_requirement:
            raise ValueError("Please provide simulation requirement (simulation_requirement)")

        uploaded_files = list(uploaded_files)
        if not uploaded_files or all(not getattr(f, "filename", None) for f in uploaded_files):
            raise ValueError("Please upload at least one document file")

        project = self.project_store.create(name=project_name)
        project.simulation_requirement = simulation_requirement
        if session_id:
            session = self.session_manager.attach(
                session_id,
                project_id=project.project_id,
                metadata={"workflow": "foresight_workbench", "phase": "ontology"},
            )
            if session is None:
                session = self.session_manager.get_or_create(
                    project_id=project.project_id,
                    metadata={"workflow": "foresight_workbench", "phase": "ontology"},
                )
        else:
            session = self.session_manager.get_or_create(
                project_id=project.project_id,
                metadata={"workflow": "foresight_workbench", "phase": "ontology"},
            )

        document_texts = []
        all_text = ""

        try:
            for file in uploaded_files:
                filename = getattr(file, "filename", None)
                if not file or not filename or not self._allowed_file(filename):
                    continue

                file_info = self.project_store.save_file(project.project_id, file, filename)
                project.files.append({
                    "filename": file_info["original_filename"],
                    "size": file_info["size"],
                })

                text = FileParser.extract_text(file_info["path"])
                text = TextProcessor.preprocess_text(text)
                document_texts.append(text)
                all_text += f"\n\n=== {file_info['original_filename']} ===\n{text}"

            if not document_texts:
                self.project_store.delete(project.project_id)
                raise ValueError("No documents were successfully processed, please check file format")

            project.total_text_length = len(all_text)
            self.document_store.save_extracted_text(project.project_id, all_text)

            ontology = OntologyGenerator().generate(
                document_texts=document_texts,
                simulation_requirement=simulation_requirement,
                additional_context=additional_context or None,
            )

            project.ontology = {
                "entity_types": ontology.get("entity_types", []),
                "edge_types": ontology.get("edge_types", []),
            }
            project.analysis_summary = ontology.get("analysis_summary", "")
            project.status = ProjectStatus.ONTOLOGY_GENERATED
            self.project_store.save(project)
            self.session_manager.attach(session.session_id, metadata={"phase": "ontology_generated"})

            logger.info(f"Ontology generated for project {project.project_id}")
            return {
                "project_id": project.project_id,
                "session_id": session.session_id,
                "project_name": project.name,
                "ontology": project.ontology,
                "analysis_summary": project.analysis_summary,
                "files": project.files,
                "total_text_length": project.total_text_length,
            }
        except Exception:
            if self.project_store.get(project.project_id) is not None:
                self.project_store.save(project)
            raise
