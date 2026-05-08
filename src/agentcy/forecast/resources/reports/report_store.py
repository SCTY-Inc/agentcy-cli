"""Report persistence adapter."""

from typing import Optional

from ...services.report_agent import Report, ReportManager


class ReportStore:
    """Adapter around report persistence."""

    def get(self, report_id: str) -> Optional[Report]:
        return ReportManager.get_report(report_id)

    def save(self, report: Report):
        ReportManager.save_report(report)

    def get_by_simulation(self, simulation_id: str) -> Optional[Report]:
        return ReportManager.get_report_by_simulation(simulation_id)
