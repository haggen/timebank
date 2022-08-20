from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    requires,
    UnauthenticatedUser,
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
from starlette.requests import HTTPConnection, Request
from google import Google
from database import *

import datetime
import logging
import flash
import config

# Logger instance.
log = logging.getLogger("starlette")

# Authentication backend.
class BasicAuthBackend(AuthenticationBackend):
    async def authenticate(self, conn):
        if not "email" in conn.session:
            return AuthCredentials(), UnauthenticatedUser()

        account = await Account.get(Account.email == conn.session["email"])

        if not account:
            return AuthCredentials(), UnauthenticatedUser()

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
        if "next" in request.query_params:
            request.session["next"] = request.query_params["next"]
            request.flash["alert"] = {
                "message": "🔒 Você precisa se autenticar.",
                "type": "negative",
            }
        return config.templates.TemplateResponse(
            "sign_in.html",
            {
                "request": request,
            },
        )

    async def post(self, request: Request):
        google = Google(request=request, redirect_uri=request.url_for(name="oauth"))
        authorization_url, state = google.authorization_url()
        request.session["state"] = state
        return RedirectResponse(url=authorization_url, status_code=303)

    @requires("authenticated")
    async def delete(self, request: Request):
        request.session.clear()
        request.flash["alert"] = {"message": "🗝️ Sessão encerrada.", "type": "positive"}
        return RedirectResponse(url=request.url_for(name="sign_in"), status_code=303)


class OAuthEndpoint(HTTPEndpoint):
    async def get(self, request: Request):
        try:
            google = Google(request=request, redirect_uri=request.url_for(name="oauth"))
            token = google.fetch_token(
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
            organization = await Organization.get(Organization.domain == userinfo["hd"])
            if not organization:
                organization = await Organization.create(
                    Organization.domain == userinfo["hd"]
                )
                organization.is_new = True

            account = await Account.get(Account.email == userinfo["email"])
            if not account:
                account = await Account.create(
                    organization_id=organization.id,
                    role="manager" if organization.is_new else "employee",
                    email=userinfo["email"],
                    name=userinfo["name"],
                    picture=userinfo["picture"],
                )

        request.session["email"] = account.email

        return RedirectResponse(
            url=request.session.pop("next", request.url_for(name="root")),
            status_code=302,
        )


class NewEntryEndpoint(HTTPEndpoint):
    @requires("authenticated", redirect="sign_in")
    async def get(self, request: Request):
        return config.templates.TemplateResponse(
            "new_entry.html",
            {
                "request": request,
                "today": datetime.date.today(),
            },
        )


class EntriesEndpoint(HTTPEndpoint):
    @requires("authenticated", redirect="sign_in")
    async def get(self, request: Request):
        entries = await Entry.get()
        return config.templates.TemplateResponse(
            "history.html",
            {
                "request": request,
                "entries": entries,
            },
        )

    @requires("authenticated", redirect="sign_in")
    async def post(self, request: Request):
        form = await request.form()
        happened_on = datetime.date.fromisoformat(form["happened_on"])
        expires_on = happened_on + datetime.timedelta(
            days=request.user.organization.settings["expires_in"]
        )
        value = int(form["value"])
        await Entry.create(
            account_id=request.user.id,
            happened_on=happened_on,
            expires_on=expires_on,
            value=value,
            multiplier=1,
        )
        request.flash["alert"] = {"message": "✅ Registro criado.", "type": "positive"}
        return RedirectResponse(url=request.url_for(name="new_entry"), status_code=303)


# Exception handler.
async def handle_exception(request: Request, exception: HTTPException | Exception):
    request.session["email"] = ""
    return config.templates.TemplateResponse(
        "error.html",
        {"request": request, "status_code": exception.status_code},
        status_code=exception.status_code,
    )


def handle_authentication_error(conn: HTTPConnection, exc: Exception):
    raise HTTPException(status_code=401)


routes = [
    Mount("/static", StaticFiles(directory="static"), name="static"),
    Route("/", RootEndpoint, methods=["GET"], name="root"),
    Route("/sign-in", SessionEndpoint, methods=["GET", "POST"], name="sign_in"),
    Route("/oauth", OAuthEndpoint, methods=["GET"], name="oauth"),
    Route("/session", SessionEndpoint, methods=["DELETE"], name="session"),
    Route("/entries/new", NewEntryEndpoint, methods=["GET"], name="new_entry"),
    Route("/history", EntriesEndpoint, methods=["GET", "POST"], name="history"),
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
            same_site="lax" if config.DEBUG else "strict",
            https_only=not config.DEBUG,
        ),
        Middleware(
            AuthenticationMiddleware,
            backend=BasicAuthBackend(),
            on_error=handle_authentication_error,
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
        server_header=False,
        forwarded_allow_ips="*",
        reload=config.DEBUG,
        debug=config.DEBUG,
    )
