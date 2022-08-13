#!/usr/bin/env python

from databases import Database
from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    AuthenticationError,
    SimpleUser,
    requires,
)
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.applications import Starlette
from starlette.responses import RedirectResponse
from starlette.staticfiles import StaticFiles
from starlette.endpoints import HTTPEndpoint
from starlette.exceptions import HTTPException
from starlette.routing import Route, Mount
from starlette.requests import Request
from middlewares import FlashMiddleware
from google import Google

import logging
import config

# Create database instance.
database = Database(config.DATABASE_URL)

# Logger instance.
log = logging.getLogger("starlette")


class BasicAuthBackend(AuthenticationBackend):
    async def authenticate(self, conn):
        if not "email" in conn.session:
            return

        account = await database.fetch_one(
            query="""
                SELECT id, role, name, email, picture_url, domain, settings
                FROM accounts JOIN organizations ON accounts.organization_id = organizations.id 
                WHERE email = :email LIMIT 1
                """,
            values={"email": conn.session["email"]},
        )

        if not account:
            raise AuthenticationError()

        account.is_authenticated = True
        account.display_name = account.name

        return AuthCredentials(["authenticated", account.role]), account


class RootEndpoint(HTTPEndpoint):
    async def get(self, request: Request):
        if request.user.is_authenticated:
            return RedirectResponse(url=request.url_for(name="new_entry"))

        return RedirectResponse(url=request.url_for(name="sign_in"))


class SessionEndpoint(HTTPEndpoint):
    async def get(self, request: Request):
        if not "code" in request.query_params:
            request.session["next"] = request.query_params.get("next", None)
            return config.templates.TemplateResponse(
                "sign-in.html",
                {
                    "request": request,
                },
            )

        try:
            google = Google(
                request=request, redirect_uri=request.url_for(name="sign_in")
            )
            token = google.fetech_token(
                returning_uri=str(request.url.replace(scheme="https")),
                state=request.session.pop("state", None),
            )
            userinfo = google.fetch_userinfo()
        except Exception as exception:
            log.exception(msg="", exc_info=exception)
            raise HTTPException(status_code=401)

        # Save token in session.
        request.session["token"] = token

        async with database.transaction():
            organization = await database.fetch_one(
                query="SELECT id FROM organizations WHERE domain = :hd",
                values=userinfo,
            )
            if not organization:
                organization = await database.fetch_one(
                    query="""
                        INSERT INTO organizations (domain)
                        VALUES (:hd) RETURNING id
                        """,
                    values=userinfo,
                )

            account = await database.fetch_one(
                query="SELECT email FROM accounts WHERE email = :email", values=userinfo
            )
            if not account:
                account = await database.fetch_one(
                    query="""
                        INSERT INTO accounts (organization_id, email, name, picture_url)
                        VALUES (:organization_id, :email, :name, :picture_url)
                        RETURNING email
                        """,
                    values={
                        "organization_id": organization["id"],
                        "email": userinfo["email"],
                        "name": userinfo["name"],
                        "picture_url": userinfo["picture"],
                    },
                )

        request.session["email"] = account.email

        return RedirectResponse(
            url=request.session.pop("next", request.url_for(name="root"))
        )

    async def post(self, request: Request):
        google = Google(request=request, redirect_uri=request.url_for(name="sign_in"))
        authorization_url, state = google.authorization_url()
        request.session["state"] = state
        return RedirectResponse(url=authorization_url)

    @requires("authenticated")
    async def delete(self, request: Request):
        request.session.clear()
        request.flash(message="🗝️ Sessão encerrada.", type="positive")
        return RedirectResponse(url=request.url_for(name="sign_in"))


class EntriesEndpoint(HTTPEndpoint):
    @requires("authenticated")
    async def get(self, request: Request):
        return config.templates.TemplateResponse(
            "new_entry.html",
            {
                "request": request,
            },
        )

    @requires("authenticated")
    async def post(self, request: Request):
        form = await request.form()
        values = {
            "account_id": request.user.id,
            "happened_on": form["happened_on"],
            "expires_on": form["happened_on"],
            "value": form["value"],
            "residue": form["value"],
            "multiplier": 1,
        }
        await database.execute_one(
            query="""
            INSERT INTO entries (account_id, happened_on, expires_on, value, residue, multiplier)
            VALUES (:account_id, :happened_on, :expires_on, :value, :residue, :multiplier)
            """,
            values=values,
        )
        request.flash(message="✅ Registro criado.", type="positive")
        return RedirectResponse(url=request.url_for(name="new_entry"))


# Exception handler.
async def handle_exception(request: Request, exception: HTTPException | Exception):
    return config.templates.TemplateResponse(
        "error.html",
        {"request": request, "status_code": exception.status_code},
        status_code=exception.status_code,
    )


routes = [
    Mount("/static", StaticFiles(directory="static"), name="static"),
    Route("/", RootEndpoint, methods=["GET"], name="root"),
    Route("/sign-in", SessionEndpoint, methods=["GET", "POST"], name="sign_in"),
    Route("/session", SessionEndpoint, methods=["DELETE"], name="session"),
    Route("/entries/new", EntriesEndpoint, methods=["GET"], name="new_entry"),
]

# Create Starlette application.
app = Starlette(
    debug=config.DEBUG,
    on_startup=[database.connect],
    on_shutdown=[database.disconnect],
    middleware=[
        Middleware(
            SessionMiddleware,
            secret_key=config.SECRET_KEY,
            same_site="strict",
            https_only=not config.DEBUG,
        ),
        Middleware(FlashMiddleware),
        Middleware(
            AuthenticationMiddleware,
            backend=BasicAuthBackend(),
            on_error=handle_exception,
        ),
    ],
    routes=routes,
    exception_handlers={
        HTTPException: handle_exception,
        Exception: handle_exception,
    },
)

# Set application state.
app.state.debug = config.DEBUG
app.state.version = config.VERSION
app.state.revision = config.REVISION

# Run with uvicorn.
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=config.PORT,
        reload=config.DEBUG,
        debug=config.DEBUG,
    )
