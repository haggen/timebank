#!/usr/bin/env python

import os

from databases import Database, DatabaseURL
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from starlette.config import Config

# Configuration.
config = Config(".env")

PORT = config("PORT", cast=int, default=5000)
DEBUG = config("DEBUG", cast=bool, default=False)
DATABASE_URL = config("DATABASE_URL", cast=DatabaseURL)

# Setup Jinja templates.
templates = Jinja2Templates(directory="templates", auto_reload=DEBUG)

# Connect to the database.
database = Database(os.environ.get("DATABASE_URL"))

# Dashboard endpoint.
async def dashboard(request):
    employees = await database.fetch_all("SELECT * FROM employees;")
    return templates.TemplateResponse(
        "index.html.jinja", {"request": request, "employees": employees}
    )


# Create Starlette application.
app = Starlette(
    debug=DEBUG,
    routes=[
        Route("/", dashboard),
        Mount("/static", StaticFiles(directory="static"), name="static"),
    ],
    on_startup=[database.connect],
    on_shutdown=[database.disconnect],
)

# Run the application.
if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 5000))

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=DEBUG,
    )
