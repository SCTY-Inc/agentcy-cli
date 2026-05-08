"""Tool for starting simulation runs."""

from typing import Any, Dict, Optional

from ..core.session_manager import SessionManager
from ..models.project import ProjectManager
from ..resources.projects import ProjectStore
from ..resources.simulations import SimulationRuntime, SimulationStore
from ..services.simulation_manager import SimulationStatus
from ..services.simulation_platforms import normalize_run_platform
from ..utils.logger import get_logger
from ..utils.oasis_llm import require_simulation_runtime
from .simulation_support import check_simulation_prepared

logger = get_logger("mirofish.tools.run_simulation")


class RunSimulationTool:
    """Start a prepared simulation."""

    def __init__(
        self,
        simulation_store: Optional[SimulationStore] = None,
        simulation_runtime: Optional[SimulationRuntime] = None,
        project_store: Optional[ProjectStore] = None,
        session_manager: Optional[SessionManager] = None,
    ):
        self.simulation_store = simulation_store or SimulationStore()
        self.simulation_runtime = simulation_runtime or SimulationRuntime()
        self.project_store = project_store or ProjectStore()
        self.session_manager = session_manager or SessionManager()

    def start(
        self,
        simulation_id: str,
        platform: str = "parallel",
        max_rounds: Optional[int] = None,
        enable_graph_memory_update: bool = False,
        force: bool = False,
        wait_for_commands: bool = True,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        require_simulation_runtime()
        platform = normalize_run_platform(platform, default="parallel")

        if max_rounds is not None:
            try:
                max_rounds = int(max_rounds)
            except (TypeError, ValueError):
                raise ValueError("max_rounds must be a valid integer")
            if max_rounds <= 0:
                raise ValueError("max_rounds must be a positive integer")

        state = self.simulation_store.get(simulation_id)
        if not state:
            raise FileNotFoundError(f"Simulation not found: {simulation_id}")

        session = self.session_manager.get_or_create(
            project_id=state.project_id,
            graph_id=state.graph_id,
            simulation_id=simulation_id,
            metadata={"workflow": "foresight_workbench", "phase": "simulation_run"},
        )
        if session_id and session.session_id != session_id:
            session = self.session_manager.attach(
                session_id,
                project_id=state.project_id,
                graph_id=state.graph_id,
                simulation_id=simulation_id,
            ) or session

        force_restarted = False
        if state.status != SimulationStatus.READY:
            is_prepared, _prepare_info = check_simulation_prepared(simulation_id)
            if not is_prepared:
                raise ValueError(
                    f"Simulation is not ready, current status: {state.status.value}. Please call the /prepare endpoint first"
                )

            if state.status == SimulationStatus.RUNNING:
                run_state = self.simulation_runtime.get_run_state(simulation_id)
                if run_state and run_state.runner_status.value == "running":
                    if force:
                        logger.info(f"Force mode: stopping running simulation {simulation_id}")
                        self.simulation_runtime.stop(simulation_id)
                    else:
                        raise ValueError(
                            "Simulation is currently running. Please call the /stop endpoint first, or use force=true to force restart"
                        )

            if force:
                logger.info(f"Force mode: cleaning up simulation logs {simulation_id}")
                cleanup_result = self.simulation_runtime.cleanup_logs(simulation_id)
                if not cleanup_result.get("success"):
                    logger.warning(f"Warning during log cleanup: {cleanup_result.get('errors')}")
                force_restarted = True

            state.status = SimulationStatus.READY
            self.simulation_store.save(state)

        graph_id = None
        if enable_graph_memory_update:
            graph_id = state.graph_id
            if not graph_id:
                project = ProjectManager.get_project(state.project_id)
                if project:
                    graph_id = project.graph_id
            if not graph_id:
                raise ValueError(
                    "Enabling graph memory update requires a valid graph_id. Please ensure the project graph has been built"
                )

        run_state = self.simulation_runtime.start(
            simulation_id=simulation_id,
            platform=platform,
            max_rounds=max_rounds,
            enable_graph_memory_update=enable_graph_memory_update,
            graph_id=graph_id,
            wait_for_commands=wait_for_commands,
        )

        state.status = SimulationStatus.RUNNING
        self.simulation_store.save(state)
        self.session_manager.attach(session.session_id, graph_id=graph_id or state.graph_id, metadata={"phase": "simulation_running"})

        response_data = run_state.to_dict()
        response_data["session_id"] = session.session_id
        if max_rounds:
            response_data["max_rounds_applied"] = max_rounds
        response_data["graph_memory_update_enabled"] = enable_graph_memory_update
        response_data["force_restarted"] = force_restarted
        if enable_graph_memory_update:
            response_data["graph_id"] = graph_id
        return response_data
