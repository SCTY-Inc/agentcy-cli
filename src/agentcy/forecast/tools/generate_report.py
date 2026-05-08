"""Tool for report generation."""

import threading
import uuid
from typing import Any, Dict, Optional

from ..core.session_manager import SessionManager
from ..core.task_manager import TaskManager, TaskStatus
from ..resources.projects import ProjectStore
from ..resources.reports import ReportStore
from ..resources.simulations import SimulationStore
from ..services.report_agent import ReportAgent, ReportStatus
from ..utils.logger import get_logger

logger = get_logger("mirofish.tools.generate_report")


class GenerateReportTool:
    """Generate a report for a simulation in the background."""

    def __init__(
        self,
        simulation_store: Optional[SimulationStore] = None,
        project_store: Optional[ProjectStore] = None,
        report_store: Optional[ReportStore] = None,
        task_manager: Optional[TaskManager] = None,
        session_manager: Optional[SessionManager] = None,
    ):
        self.simulation_store = simulation_store or SimulationStore()
        self.project_store = project_store or ProjectStore()
        self.report_store = report_store or ReportStore()
        self.task_manager = task_manager or TaskManager()
        self.session_manager = session_manager or SessionManager()

    def start(
        self,
        simulation_id: str,
        force_regenerate: bool = False,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        state = self.simulation_store.get(simulation_id)
        if not state:
            raise FileNotFoundError(f"Simulation not found: {simulation_id}")

        if not force_regenerate:
            existing_report = self.report_store.get_by_simulation(simulation_id)
            if existing_report and existing_report.status == ReportStatus.COMPLETED:
                session = self.session_manager.get_or_create(
                    project_id=state.project_id,
                    graph_id=state.graph_id,
                    simulation_id=simulation_id,
                    report_id=existing_report.report_id,
                    metadata={"workflow": "foresight_workbench", "phase": "report_completed"},
                )
                return {
                    "simulation_id": simulation_id,
                    "session_id": session.session_id,
                    "report_id": existing_report.report_id,
                    "status": "completed",
                    "message": "Report already exists",
                    "already_generated": True,
                }

        project = self.project_store.get(state.project_id)
        if not project:
            raise FileNotFoundError(f"Project not found: {state.project_id}")

        graph_id = state.graph_id or project.graph_id
        if not graph_id:
            raise ValueError("Missing graph ID, please ensure the graph has been built")

        simulation_requirement = project.simulation_requirement
        if not simulation_requirement:
            raise ValueError("Missing simulation requirement description")

        session = self.session_manager.get_or_create(
            project_id=state.project_id,
            graph_id=graph_id,
            simulation_id=simulation_id,
            metadata={"workflow": "foresight_workbench", "phase": "report"},
        )
        if session_id and session.session_id != session_id:
            session = self.session_manager.attach(
                session_id,
                project_id=state.project_id,
                graph_id=graph_id,
                simulation_id=simulation_id,
            ) or session

        report_id = f"report_{uuid.uuid4().hex[:12]}"
        task_id = self.task_manager.create_task(
            task_type="report_generate",
            metadata={
                "simulation_id": simulation_id,
                "graph_id": graph_id,
                "report_id": report_id,
                "session_id": session.session_id,
            },
        )

        def run_generate():
            try:
                self.task_manager.update_task(
                    task_id,
                    status=TaskStatus.PROCESSING,
                    progress=0,
                    message="Initializing Report Agent...",
                )

                agent = ReportAgent(
                    graph_id=graph_id,
                    simulation_id=simulation_id,
                    simulation_requirement=simulation_requirement,
                )

                def progress_callback(stage, progress, message):
                    self.task_manager.update_task(
                        task_id,
                        progress=progress,
                        message=f"[{stage}] {message}",
                    )

                report = agent.generate_report_fast(progress_callback=progress_callback, report_id=report_id)
                self.report_store.save(report)

                if report.status == ReportStatus.COMPLETED:
                    self.session_manager.attach(
                        session.session_id,
                        project_id=state.project_id,
                        graph_id=graph_id,
                        simulation_id=simulation_id,
                        report_id=report.report_id,
                        metadata={"phase": "report_completed"},
                    )
                    self.task_manager.complete_task(
                        task_id,
                        result={
                            "report_id": report.report_id,
                            "simulation_id": simulation_id,
                            "status": "completed",
                            "session_id": session.session_id,
                        },
                    )
                else:
                    self.task_manager.fail_task(task_id, report.error or "Report generation failed")
            except Exception as exc:
                logger.error(f"Report generation failed: {exc}")
                self.task_manager.fail_task(task_id, str(exc))

        thread = threading.Thread(target=run_generate, daemon=True)
        thread.start()

        return {
            "simulation_id": simulation_id,
            "session_id": session.session_id,
            "report_id": report_id,
            "task_id": task_id,
            "status": "generating",
            "message": "Report generation task started, check progress via /api/report/generate/status",
            "already_generated": False,
        }
