"""Tool for simulation preparation."""

import threading
from typing import Any, Dict, List, Optional

from ..core.session_manager import SessionManager
from ..core.task_manager import TaskManager, TaskStatus
from ..models.project import ProjectManager
from ..resources.documents import DocumentStore
from ..resources.projects import ProjectStore
from ..resources.simulations import SimulationStore
from ..services.entity_reader import EntityReader
from ..services.simulation_manager import SimulationStatus
from ..utils.logger import get_logger
from .simulation_support import check_simulation_prepared

logger = get_logger("mirofish.tools.prepare_simulation")

# Per-simulation lock to prevent concurrent prepare races
_preparing_lock = threading.Lock()
_preparing_simulations: set = set()


class PrepareSimulationTool:
    """Prepare simulation artifacts as a background task."""

    def __init__(
        self,
        simulation_store: Optional[SimulationStore] = None,
        project_store: Optional[ProjectStore] = None,
        document_store: Optional[DocumentStore] = None,
        task_manager: Optional[TaskManager] = None,
        session_manager: Optional[SessionManager] = None,
    ):
        self.simulation_store = simulation_store or SimulationStore()
        self.project_store = project_store or ProjectStore()
        self.document_store = document_store or DocumentStore()
        self.task_manager = task_manager or TaskManager()
        self.session_manager = session_manager or SessionManager()

    def start(
        self,
        simulation_id: str,
        entity_types: Optional[List[str]] = None,
        use_llm_for_profiles: bool = True,
        parallel_profile_count: int = 5,
        force_regenerate: bool = False,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        state = self.simulation_store.get(simulation_id)
        if not state:
            raise FileNotFoundError(f"Simulation not found: {simulation_id}")

        if not force_regenerate:
            is_prepared, prepare_info = check_simulation_prepared(simulation_id)
            if is_prepared:
                session = self.session_manager.get_or_create(
                    project_id=state.project_id,
                    graph_id=state.graph_id,
                    simulation_id=simulation_id,
                    metadata={"workflow": "foresight_workbench", "phase": "simulation_ready"},
                )
                return {
                    "simulation_id": simulation_id,
                    "session_id": session.session_id,
                    "status": "ready",
                    "message": "Preparation already complete, no need to regenerate",
                    "already_prepared": True,
                    "prepare_info": prepare_info,
                }

        with _preparing_lock:
            if simulation_id in _preparing_simulations:
                return {
                    "simulation_id": simulation_id,
                    "status": "already_preparing",
                    "message": "Preparation already in progress for this simulation",
                }
            _preparing_simulations.add(simulation_id)

        project = self.project_store.get(state.project_id)
        if not project:
            raise FileNotFoundError(f"Project not found: {state.project_id}")

        simulation_requirement = project.simulation_requirement or ""
        if not simulation_requirement:
            raise ValueError("Project is missing simulation requirement description (simulation_requirement)")

        document_text = self.document_store.get_extracted_text(state.project_id) or ""

        session = self.session_manager.get_or_create(
            project_id=state.project_id,
            graph_id=state.graph_id,
            simulation_id=simulation_id,
            metadata={"workflow": "foresight_workbench", "phase": "simulation_prepare"},
        )
        if session_id and session.session_id != session_id:
            session = self.session_manager.attach(
                session_id,
                project_id=state.project_id,
                graph_id=state.graph_id,
                simulation_id=simulation_id,
            ) or session

        try:
            reader = EntityReader()
            filtered_preview = reader.filter_defined_entities(
                graph_id=state.graph_id,
                defined_entity_types=entity_types,
                enrich_with_edges=False,
            )
            state.entities_count = filtered_preview.filtered_count
            state.entity_types = list(filtered_preview.entity_types)
            logger.info(f"Expected entity count for {simulation_id}: {state.entities_count}")
        except Exception as exc:
            logger.warning(f"Failed to prefetch entity count for {simulation_id}: {exc}")

        task_id = self.task_manager.create_task(
            task_type="simulation_prepare",
            metadata={
                "simulation_id": simulation_id,
                "project_id": state.project_id,
                "session_id": session.session_id,
            },
        )

        state.status = SimulationStatus.PREPARING
        state.error = None
        self.simulation_store.save(state)

        def run_prepare():
            try:
                self.task_manager.update_task(
                    task_id,
                    status=TaskStatus.PROCESSING,
                    progress=0,
                    message="Starting simulation environment preparation...",
                )

                stage_details = {}
                stage_weights = {
                    "reading": (0, 20),
                    "generating_profiles": (20, 70),
                    "generating_config": (70, 90),
                    "copying_scripts": (90, 100),
                }
                stage_names = {
                    "reading": "Reading graph entities",
                    "generating_profiles": "Generating Agent profiles",
                    "generating_config": "Generating simulation configuration",
                    "copying_scripts": "Preparing simulation scripts",
                }

                def progress_callback(stage, progress, message, **kwargs):
                    start, end = stage_weights.get(stage, (0, 100))
                    current_progress = int(start + (end - start) * progress / 100)
                    stage_details[stage] = {
                        "stage_name": stage_names.get(stage, stage),
                        "stage_progress": progress,
                        "current": kwargs.get("current", 0),
                        "total": kwargs.get("total", 0),
                        "item_name": kwargs.get("item_name", ""),
                    }
                    stage_index = list(stage_weights.keys()).index(stage) + 1 if stage in stage_weights else 1
                    total_stages = len(stage_weights)
                    detail = stage_details[stage]
                    progress_detail_data = {
                        "current_stage": stage,
                        "current_stage_name": stage_names.get(stage, stage),
                        "stage_index": stage_index,
                        "total_stages": total_stages,
                        "stage_progress": progress,
                        "current_item": detail["current"],
                        "total_items": detail["total"],
                        "item_description": message,
                    }
                    if detail["total"] > 0:
                        detailed_message = (
                            f"[{stage_index}/{total_stages}] {stage_names.get(stage, stage)}: "
                            f"{detail['current']}/{detail['total']} - {message}"
                        )
                    else:
                        detailed_message = f"[{stage_index}/{total_stages}] {stage_names.get(stage, stage)}: {message}"
                    self.task_manager.update_task(
                        task_id,
                        progress=current_progress,
                        message=detailed_message,
                        progress_detail=progress_detail_data,
                    )

                result_state = self.simulation_store.prepare(
                    simulation_id=simulation_id,
                    simulation_requirement=simulation_requirement,
                    document_text=document_text,
                    defined_entity_types=entity_types,
                    use_llm_for_profiles=use_llm_for_profiles,
                    progress_callback=progress_callback,
                    parallel_profile_count=parallel_profile_count,
                )

                self.session_manager.attach(session.session_id, metadata={"phase": "simulation_ready"})
                self.task_manager.complete_task(task_id, result=result_state.to_simple_dict())
            except Exception as exc:
                logger.error(f"Failed to prepare simulation {simulation_id}: {exc}")
                self.task_manager.fail_task(task_id, str(exc))
                current_state = self.simulation_store.get(simulation_id)
                if current_state:
                    current_state.status = SimulationStatus.FAILED
                    current_state.error = str(exc)
                    self.simulation_store.save(current_state)
            finally:
                # Release the simulation from preparing state
                with _preparing_lock:
                    _preparing_simulations.discard(simulation_id)

        thread = threading.Thread(target=run_prepare, daemon=True)
        thread.start()

        return {
            "simulation_id": simulation_id,
            "session_id": session.session_id,
            "task_id": task_id,
            "status": "preparing",
            "message": "Preparation task started. Query progress via /api/simulation/prepare/status",
            "already_prepared": False,
            "expected_entities_count": state.entities_count,
            "entity_types": state.entity_types,
        }
