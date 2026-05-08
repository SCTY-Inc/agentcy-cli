"""Simulation state and runtime adapters."""

from typing import Any, Dict, List, Optional

from ...services.simulation_manager import SimulationManager, SimulationState
from ...services.simulation_runner import SimulationRunState, SimulationRunner


class SimulationStore:
    """Adapter around persisted simulation preparation state."""

    def __init__(self, manager: Optional[SimulationManager] = None):
        self.manager = manager or SimulationManager()

    def create(
        self,
        project_id: str,
        graph_id: str,
        enable_twitter: bool = True,
        enable_reddit: bool = True,
    ) -> SimulationState:
        return self.manager.create_simulation(
            project_id=project_id,
            graph_id=graph_id,
            enable_twitter=enable_twitter,
            enable_reddit=enable_reddit,
        )

    def get(self, simulation_id: str) -> Optional[SimulationState]:
        return self.manager.get_simulation(simulation_id)

    def save(self, state: SimulationState):
        self.manager._save_simulation_state(state)

    def prepare(self, **kwargs) -> SimulationState:
        return self.manager.prepare_simulation(**kwargs)

    def list(self, project_id: Optional[str] = None) -> List[SimulationState]:
        return self.manager.list_simulations(project_id=project_id)

    def get_profiles(self, simulation_id: str, platform: str = "reddit") -> List[Dict[str, Any]]:
        return self.manager.get_profiles(simulation_id, platform=platform)

    def get_config(self, simulation_id: str) -> Optional[Dict[str, Any]]:
        return self.manager.get_simulation_config(simulation_id)


class SimulationRuntime:
    """Adapter around the live simulation runner."""

    def start(self, **kwargs) -> SimulationRunState:
        return SimulationRunner.start_simulation(**kwargs)

    def get_run_state(self, simulation_id: str) -> Optional[SimulationRunState]:
        return SimulationRunner.get_run_state(simulation_id)

    def stop(self, simulation_id: str) -> SimulationRunState:
        return SimulationRunner.stop_simulation(simulation_id)

    def cleanup_logs(self, simulation_id: str):
        return SimulationRunner.cleanup_simulation_logs(simulation_id)
