#!/usr/bin/env python

import csv, datetime, io
from http.client import HTTPException

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

# Useful when you're mixing database records and dicts.
class Record(dict):
    """
    Extends dict to support attribute-style access.
    """

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self[key] = value


# Dashboard endpoint.
class Dashboard(HTTPEndpoint):
    async def get(self, request: Request):
        employees = await database.fetch_all("SELECT name FROM employees;")

        entries = await database.fetch_all(
            """
            SELECT employees.name AS employee, SUM(entries.balance) AS balance 
            FROM entries 
            JOIN employees ON entries.employee_id = employees.id 
            WHERE entries.expires_on > current_date
            GROUP BY employees.name;
            """
        )

        return templates.TemplateResponse(
            "dashboard.html",
            {"request": request, "employees": employees, "entries": entries},
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

        new_entries = []

        try:
            contents = await form["entries"].read()
            file = io.StringIO(contents.decode("utf-8"), newline="")
            for data in csv.reader(file):
                happened_on = datetime.date.fromisoformat(data[0])
                expires_on = happened_on + datetime.timedelta(days=90)
                new_entries.append(
                    Record(
                        employee_id=employee.id,
                        happened_on=happened_on,
                        expires_on=expires_on,
                        value=int(data[1]),
                        balance=int(data[1]),
                    )
                )
        except RuntimeError:
            raise HTTPException(400)

        # This must be sorted before the query below.
        new_entries.sort(key=lambda entry: entry.happened_on)

        old_entries = await database.fetch_all(
            """
            SELECT id, happened_on, expires_on, balance FROM entries 
            WHERE employee_id = :employee_id 
            AND expires_on > :reference_date
            AND balance != 0 
            ORDER BY happened_on;
            """,
            {"employee_id": employee.id, "reference_date": new_entries[0].happened_on},
        )

        # Saved entries to be updated.
        changed_entries = []

        for new_entry in new_entries:
            for old_entry in old_entries:
                if old_entry.balance == 0:
                    continue

                if new_entry.happened_on > old_entry.expires_on:
                    continue

                if (old_entry.balance > 0) == (new_entry.balance > 0):
                    continue

                balance = old_entry.balance + new_entry.balance

                if balance > 0 and old_entry.balance > 0:
                    old_entry.balance = balance
                    new_entry.balance = 0
                else:
                    old_entry.balance = 0
                    new_entry.balance = balance

                # Flag for update if it was an existing entry.
                if "id" in old_entry:
                    changed_entries.append(
                        Record(
                            id=old_entry.id,
                            balance=old_entry.balance,
                        )
                    )

            # New entry must be considered in the next iteration.
            old_entries.append(new_entry)

            # Re-sort old entries in last entry was out of order.
            old_entries.sort(key=lambda entry: entry.happened_on)

        # Update and insert must either fail or succeed together.
        async with database.transaction():
            await database.execute_many(
                """
                UPDATE entries SET balance = :balance WHERE id = :id;
                """,
                values=changed_entries,
            )
            await database.execute_many(
                """
                INSERT INTO entries (employee_id, happened_on, expires_on, value, balance)
                VALUES (:employee_id, :happened_on, :expires_on, :value, :balance);
                """,
                values=new_entries,
            )

        request.flash(
            "%d registro(s) importado(s) para o funcionário %s"
            % (
                len(new_entries),
                employee.name,
            ),
            "positive",
        )

        return RedirectResponse("/", status_code=303)


# Upload endpoint.
class Upload(HTTPEndpoint):
    async def get(self, request: Request):
        employees = await database.fetch_all("SELECT id, name FROM employees;")
        return templates.TemplateResponse(
            "upload.html",
            {
                "request": request,
                "employees": employees,
            },
        )


# Employees endpoint.
class Employees(HTTPEndpoint):
    async def get(self, request: Request):
        employees = await database.fetch_all("SELECT id, name FROM employees;")
        entries = []
        employee_id = request.path_params.get("id")

        if employee_id:
            entries = await database.fetch_all(
                """
                SELECT id, happened_on, expires_on, value, balance
                FROM entries
                WHERE employee_id = :employee
                ORDER BY happened_on;
                """,
                {"employee": employee_id},
            )

        return templates.TemplateResponse(
            "employee.html",
            {
                "request": request,
                "employee_id": employee_id,
                "employees": employees,
                "entries": entries,
            },
        )


# Exception handler.
async def handle_exception(request: Request, exception: HTTPException | Exception):
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "status_code": exception.status_code},
        status_code=exception.status_code,
    )


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
        Route("/", Dashboard, name="dashboard"),
        Route("/upload", Upload, name="upload"),
        Route("/employees", Employees, name="employees"),
        Route("/employees/{id:int}", Employees, name="employee"),
        Mount("/static", StaticFiles(directory="static"), name="static"),
    ],
    exception_handlers={
        404: handle_exception,
        HTTPException: handle_exception,
        Exception: handle_exception,
    },
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
