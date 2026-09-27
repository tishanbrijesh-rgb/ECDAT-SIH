"""Single-origin app for the small Render demo deployment."""

from pathlib import Path

from fastapi.responses import FileResponse
from starlette.staticfiles import StaticFiles

from backend.main import app


class DashboardFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 404 and "." not in Path(path).name:
            return FileResponse(Path(self.directory) / "index.html")
        return response


app.mount("/", DashboardFiles(directory="/app/dashboard-dist", html=True), name="dashboard")
