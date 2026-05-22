"""Session-centric orchestration for the foresight workbench."""

from typing import Any, Dict, List, Optional

from .resource_loader import ResourceLoader, WorkbenchResources
from .session_manager import SessionManager, WorkbenchSessionState
from .task_manager import TaskManager
from ..tools import (
    BuildGraphTool,
    GenerateOntologyTool,
    GenerateReportTool,
    PrepareSimulationTool,
    RunSimulationTool,
)


class WorkbenchSession:
    """A thin session wrapper around shared resources and composable tools."""

    def __init__(
        self,
        state: Optional[WorkbenchSessionState] = None,
        resource_loader: Optional[ResourceLoader] = None,
        session_manager: Optional[SessionManager] = None,
        task_manager: Optional[TaskManager] = None,
    ):
        self.session_manager = session_manager or SessionManager()
        self.task_manager = task_manager or TaskManager()
        self.resource_loader = resource_loader or ResourceLoader()
        self.resources: WorkbenchResources = self.resource_loader.load()
        self.state = state or self.session_manager.create(metadata={"workflow": "foresight_workbench"})

        self.generate_ontology_tool = GenerateOntologyTool(
            project_store=self.resources.project_store,
            document_store=self.resources.document_store,
            session_manager=self.session_manager,
        )
        self.build_graph_tool = BuildGraphTool(
            project_store=self.resources.project_store,
            document_store=self.resources.document_store,
            task_manager=self.task_manager,
            session_manager=self.session_manager,
        )
        self.prepare_simulation_tool = PrepareSimulationTool(
            simulation_store=self.resources.simulation_store,
            project_store=self.resources.project_store,
            document_store=self.resources.document_store,
            task_manager=self.task_manager,
            session_manager=self.session_manager,
        )
        self.run_simulation_tool = RunSimulationTool(
            simulation_store=self.resources.simulation_store,
            simulation_runtime=self.resources.simulation_runtime,
            project_store=self.resources.project_store,
            session_manager=self.session_manager,
        )
        self.generate_report_tool = GenerateReportTool(
            simulation_store=self.resources.simulation_store,
            project_store=self.resources.project_store,
            report_store=self.resources.report_store,
            task_manager=self.task_manager,
            session_manager=self.session_manager,
        )

    @classmethod
    def open(
        cls,
        project_id: Optional[str] = None,
        graph_id: Optional[str] = None,
        simulation_id: Optional[str] = None,
        report_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "WorkbenchSession":
        session_manager = SessionManager()
        state = session_manager.get_or_create(
            project_id=project_id,
            graph_id=graph_id,
            simulation_id=simulation_id,
            report_id=report_id,
            metadata=metadata or {"workflow": "foresight_workbench"},
        )
        return cls(state=state, session_manager=session_manager)

    @property
    def session_id(self) -> str:
        return self.state.session_id

    def to_dict(self) -> Dict[str, Any]:
        return self.state.to_dict()

    def attach(
        self,
        project_id: Optional[str] = None,
        graph_id: Optional[str] = None,
        simulation_id: Optional[str] = None,
        report_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        updated = self.session_manager.attach(
            self.session_id,
            project_id=project_id,
            graph_id=graph_id,
            simulation_id=simulation_id,
            report_id=report_id,
            metadata=metadata,
        )
        if updated is not None:
            self.state = updated
        return self.to_dict()

    def generate_ontology(
        self,
        simulation_requirement: str,
        uploaded_files: List[Any],
        project_name: str = "Unnamed Project",
        additional_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        result = self.generate_ontology_tool.execute(
            simulation_requirement=simulation_requirement,
            uploaded_files=uploaded_files,
            project_name=project_name,
            additional_context=additional_context,
            session_id=self.session_id,
        )
        self.state = self.session_manager.get(result["session_id"]) or self.state
        return result

    def start_graph_build(
        self,
        project_id: str,
        graph_name: Optional[str] = None,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        result = self.build_graph_tool.start(
            project_id=project_id,
            graph_name=graph_name,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            force=force,
            session_id=self.session_id,
        )
        self.state = self.session_manager.get(result["session_id"]) or self.state
        return result

    def create_simulation(
        self,
        project_id: str,
        graph_id: str,
        enable_twitter: bool = True,
        enable_reddit: bool = True,
    ):
        state = self.resources.simulation_store.create(
            project_id=project_id,
            graph_id=graph_id,
            enable_twitter=enable_twitter,
            enable_reddit=enable_reddit,
        )
        self.attach(
            project_id=project_id,
            graph_id=graph_id,
            simulation_id=state.simulation_id,
            metadata={"phase": "simulation_created"},
        )
        return state

    def start_simulation_preparation(
        self,
        simulation_id: str,
        entity_types: Optional[List[str]] = None,
        use_llm_for_profiles: bool = True,
        parallel_profile_count: int = 5,
        force_regenerate: bool = False,
    ) -> Dict[str, Any]:
        result = self.prepare_simulation_tool.start(
            simulation_id=simulation_id,
            entity_types=entity_types,
            use_llm_for_profiles=use_llm_for_profiles,
            parallel_profile_count=parallel_profile_count,
            force_regenerate=force_regenerate,
            session_id=self.session_id,
        )
        self.state = self.session_manager.get(result["session_id"]) or self.state
        return result

    def start_simulation_run(
        self,
        simulation_id: str,
        platform: str = "parallel",
        max_rounds: Optional[int] = None,
        enable_graph_memory_update: bool = False,
        force: bool = False,
        wait_for_commands: bool = True,
    ) -> Dict[str, Any]:
        result = self.run_simulation_tool.start(
            simulation_id=simulation_id,
            platform=platform,
            max_rounds=max_rounds,
            enable_graph_memory_update=enable_graph_memory_update,
            force=force,
            wait_for_commands=wait_for_commands,
            session_id=self.session_id,
        )
        self.state = self.session_manager.get(result["session_id"]) or self.state
        return result

    def start_report_generation(
        self,
        simulation_id: str,
        force_regenerate: bool = False,
    ) -> Dict[str, Any]:
        result = self.generate_report_tool.start(
            simulation_id=simulation_id,
            force_regenerate=force_regenerate,
            session_id=self.session_id,
        )
        self.state = self.session_manager.get(result["session_id"]) or self.state
        return result
