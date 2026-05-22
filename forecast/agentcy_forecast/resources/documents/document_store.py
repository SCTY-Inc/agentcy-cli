"""Document access adapter."""

from typing import Optional

from ...models.project import ProjectManager


class DocumentStore:
    """Provides access to extracted project text and project files."""

    def get_extracted_text(self, project_id: str) -> Optional[str]:
        return ProjectManager.get_extracted_text(project_id)

    def save_extracted_text(self, project_id: str, text: str):
        ProjectManager.save_extracted_text(project_id, text)
