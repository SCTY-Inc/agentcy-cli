"""Resource loader for the workbench runtime."""

from dataclasses import dataclass

from ..resources.documents import DocumentStore
from ..resources.graph import GraphStore
from ..resources.projects import ProjectStore
from ..resources.reports import ReportStore
from ..resources.simulations import SimulationRuntime, SimulationStore


@dataclass
class WorkbenchResources:
    """Shared resources used by a workbench session."""

    project_store: ProjectStore
    document_store: DocumentStore
    graph_store: GraphStore
    simulation_store: SimulationStore
    simulation_runtime: SimulationRuntime
    report_store: ReportStore


class ResourceLoader:
    """Loads the default local resources for the workbench."""

    def load(self) -> WorkbenchResources:
        return WorkbenchResources(
            project_store=ProjectStore(),
            document_store=DocumentStore(),
            graph_store=GraphStore(),
            simulation_store=SimulationStore(),
            simulation_runtime=SimulationRuntime(),
            report_store=ReportStore(),
        )
