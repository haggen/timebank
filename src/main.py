#!/usr/bin/env python

import csv, datetime, io

from databases import Database, DatabaseURL

from starlette.config import Config
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.applications import Starlette
from starlette.endpoints import HTTPEndpoint
from starlette.templating import Jinja2Templates
from starlette.responses import RedirectResponse
from starlette.staticfiles import StaticFiles
from starlette.routing import Route, Mount
from starlette.requests import Request

from middlewares import FlashMiddleware

# Configuration.
config = Config(".env")

PORT = config("PORT", cast=int, default=5000)
DEBUG = config("DEBUG", cast=bool, default=False)
SESSION_KEY = config("SESSION_KEY")
DATABASE_URL = config("DATABASE_URL", cast=DatabaseURL)

# Setup Jinja templates.
templates = Jinja2Templates(directory="templates", auto_reload=DEBUG)

# Connect to the database.
database = Database(DATABASE_URL)

# Dashboard endpoint.
class Dashboard(HTTPEndpoint):
    async def get(self, request: Request):
        employees = await database.fetch_all("SELECT * FROM employees;")

        return templates.TemplateResponse(
            "index.html", {"request": request, "employees": employees}
        )

    async def post(self, request: Request):
        form = await request.form()

        employee = await database.fetch_one(
            "SELECT id, name FROM employees WHERE name = :employee;",
            {"employee": form["employee"]},
        )

        if not employee:
            employee = await database.fetch_one(
                "INSERT INTO employees (name) VALUES (:employee) RETURNING id, name;",
                {"employee": form["employee"]},
            )

        entries = []

        try:
            contents = await form["entries"].read()
            file = io.StringIO(contents.decode("utf-8"), newline="")
            for data in csv.reader(file):
                created_at = datetime.datetime.strptime(data[0], "%Y-%m-%d")
                expires_at = created_at + datetime.timedelta(days=90)
                entries.append(
                    {
                        "employee_id": employee.id,
                        "created_at": created_at,
                        "expires_at": expires_at,
                        "value": int(data[1]),
                    }
                )
        except (RuntimeError):
            return RedirectResponse("/400")

        async with database.transaction():
            await database.execute_many(
                """
                INSERT INTO entries (employee_id, created_at, expires_at, initial_value, spare_value)
                VALUES (:employee_id, :created_at, :expires_at, :value, :value);
                """,
                values=entries,
            )

        request.flash(
            "%d registro(s) importado(s) para o funcionário %s"
            % (
                len(entries),
                employee.name,
            ),
            "positive",
        )

        return RedirectResponse("/", status_code=303)


# BadRequest endpoint.
class BadRequest(HTTPEndpoint):
    async def get(self, request: Request):
        return templates.TemplateResponse("400.html", {"request": request})


# Create Starlette application.
app = Starlette(
    debug=DEBUG,
    on_startup=[database.connect],
    on_shutdown=[database.disconnect],
    middleware=[
        Middleware(
            SessionMiddleware,
            secret_key=SESSION_KEY,
            same_site="strict",
            https_only=not DEBUG,
        ),
        Middleware(FlashMiddleware),
    ],
    routes=[
        Route("/", Dashboard),
        Route("/400", BadRequest),
        Mount("/static", StaticFiles(directory="static"), name="static"),
    ],
)

# Run with uvicorn.
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=PORT,
        reload=DEBUG,
    )
