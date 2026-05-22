"""Project persistence adapter."""

from typing import List, Optional

from ...models.project import Project, ProjectManager


class ProjectStore:
    """Adapter around project persistence."""

    def create(self, name: str = "Unnamed Project") -> Project:
        return ProjectManager.create_project(name=name)

    def get(self, project_id: str) -> Optional[Project]:
        return ProjectManager.get_project(project_id)

    def save(self, project: Project):
        ProjectManager.save_project(project)

    def list(self, limit: int = 50) -> List[Project]:
        return ProjectManager.list_projects(limit=limit)

    def delete(self, project_id: str) -> bool:
        return ProjectManager.delete_project(project_id)

    def save_file(self, project_id: str, file_storage, original_filename: str):
        return ProjectManager.save_file_to_project(project_id, file_storage, original_filename)

    def save_extracted_text(self, project_id: str, text: str):
        ProjectManager.save_extracted_text(project_id, text)

    def get_extracted_text(self, project_id: str) -> Optional[str]:
        return ProjectManager.get_extracted_text(project_id)
