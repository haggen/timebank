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
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.functions import sum, coalesce
from database import Session, Organization, Account, Entry
from google import Google
from ext.flash import FlashMiddleware

import datetime
import logging
import config

# Logger instance.
log = logging.getLogger("starlette")

# Authentication backend.
class BasicAuthBackend(AuthenticationBackend):
    async def authenticate(self, conn):
        if not "email" in conn.session:
            return AuthCredentials(), UnauthenticatedUser()

        async with Session() as session:
            account = await session.scalar(
                select(Account)
                .options(selectinload(Account.organization))
                .where(Account.email == conn.session["email"])
                .limit(1)
            )

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
            google.fetch_token(
                returning_uri=str(request.url.replace(scheme="https")),
                state=request.session.pop("state", None),
            )
            userinfo = google.fetch_userinfo()
        except Exception as exception:
            log.exception(msg="", exc_info=exception)
            raise HTTPException(status_code=401)

        if not "hd" in userinfo:
            raise HTTPException(status_code=401)

        async with Session() as session:
            async with session.begin():
                organization = await session.scalar(
                    select(Organization)
                    .where(Organization.domain == userinfo["hd"])
                    .limit(1)
                )

                if not organization:
                    organization = Organization(domain=userinfo["hd"])
                    session.add(organization)
                    organization.is_new = True

                account = await session.scalar(
                    select(Account)
                    .where(
                        Account.email == userinfo["email"],
                        Account.organization_id == organization.id,
                    )
                    .limit(1)
                )

                if not account:
                    account = Account(
                        organization_id=organization.id,
                        role=("manager" if organization.is_new else "employee"),
                        email=userinfo["email"],
                        name=userinfo["name"],
                        picture=userinfo["picture"],
                    )
                    session.add(account)

                session.commit()

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
        async with Session() as session:
            balance = await session.scalar(
                select(coalesce(sum(Entry.residue), 0).label("balance")).where(
                    Entry.account_id == request.user.id,
                    Entry.expires_on > datetime.date.today(),
                )
            )
            history = await session.scalars(
                select(Entry)
                .where(Entry.account_id == request.user.id)
                .order_by(Entry.happened_on.desc(), Entry.created_at.desc())
            )
            expirations = await session.scalars(
                select(Entry)
                .where(
                    Entry.account_id == request.user.id,
                    Entry.residue > 0,
                    Entry.expires_on > datetime.date.today(),
                )
                .order_by(Entry.expires_on, Entry.created_at)
            )
        return config.templates.TemplateResponse(
            "history.html",
            {
                "request": request,
                "balance": balance,
                "history": history.all(),
                "expirations": expirations.all(),
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
        async with Session() as session:
            async with session.begin():
                session.add(
                    Entry(
                        account_id=request.user.id,
                        happened_on=happened_on,
                        expires_on=expires_on,
                        value=value,
                        residue=value,
                        multiplier=1.0,
                    )
                )
                await session.commit()
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
        Middleware(FlashMiddleware),
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
