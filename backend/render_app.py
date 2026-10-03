"""Single-origin app for the small Render demo deployment."""

from pathlib import Path

from fastapi.responses import FileResponse
from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles

from backend.main import app


class DashboardFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or "." in Path(path).name:
                raise
            return FileResponse(Path(self.directory) / "index.html")


app.mount("/", DashboardFiles(directory="/app/dashboard-dist", html=True, check_dir=False), name="dashboard")
