from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    UnauthenticatedUser,
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
from starlette.requests import HTTPConnection, Request

from sqlalchemy.future import select
from sqlalchemy import orm, func

from database import DatabaseMiddleware, Session, Organization, Account, Entry

from google import Google

from ext.flash import FlashMiddleware

import config
import logging
import datetime

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
                .options(orm.joinedload(Account.organization))
                .where(Account.email == conn.session["email"])
                .limit(1)
            )

        if not account:
            return AuthCredentials(), UnauthenticatedUser()

        return AuthCredentials(["authenticated", account.role]), account


class RootEndpoint(HTTPEndpoint):
    async def get(self, request: Request):
        if request.user.is_authenticated:
            return RedirectResponse(
                url=request.url_for(name="new_entry"), status_code=303
            )

        return RedirectResponse(url=request.url_for(name="sign_in"), status_code=303)


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

        if not "hd" in userinfo:
            raise HTTPException(status_code=401)

        account = await request.db.scalar(
            select(Account).where(Account.email == userinfo["email"]).limit(1)
        )

        if not account:
            account = Account(
                email=userinfo["email"],
                name=userinfo["name"],
                role="employee",
                picture=userinfo["picture"],
            )

            account.organization = await request.db.scalar(
                select(Organization)
                .where(Organization.domain == userinfo["hd"])
                .limit(1)
            )

            if not account.organization:
                account.role = "manager"
                account.organization = Organization(domain=userinfo["hd"])

            request.db.add(account)
            await request.db.commit()

        request.session["token"] = token
        request.session["email"] = account.email

        return RedirectResponse(
            url=request.session.pop("next", request.url_for(name="new_entry")),
            status_code=303,
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
    async def post(self, request: Request):
        form = await request.form()
        happened_on = datetime.date.fromisoformat(form["happened_on"])
        expires_on = happened_on + datetime.timedelta(
            days=request.user.organization.settings["expires_in"]
        )
        multiplier = 1.0
        value = int(form["value"])
        residue = round(value * multiplier)
        request.db.add(
            Entry(
                account_id=request.user.id,
                happened_on=happened_on,
                expires_on=expires_on,
                value=value,
                residue=residue,
                multiplier=multiplier,
            )
        )
        await request.db.commit()
        request.flash["alert"] = {"message": "✅ Registro criado.", "type": "positive"}
        return RedirectResponse(url=request.url_for(name="new_entry"), status_code=303)


class SummaryEndpoint(HTTPEndpoint):
    def get_period(self, value: str):
        try:
            a = datetime.date.fromisoformat(f"{value}-01")
        except ValueError:
            a = datetime.date.today().replace(day=1)

        b = a.replace(month=a.month + 1 if a.month < 12 else 1)

        return (a, b)

    @requires(["authenticated", "manager"], redirect="sign_in")
    async def get(self, request: Request):
        organization_id = request.user.organization_id
        period = self.get_period(request.query_params.get("month"))
        summary = await request.db.execute(
            select(
                Account.id,
                Account.name,
                Account.balance,
                Account.expiring_balance(*period),
            )
            .outerjoin(Account.entries)
            .where(Account.of_organization(organization_id), Account.active)
            .group_by(Account.id)
            .order_by(*Account.by_name)
        )
        return config.templates.TemplateResponse(
            "summary.html",
            {
                "request": request,
                "is_management": True,
                "summary": summary,
                "period": period,
            },
        )


class AccountsEndpoint(HTTPEndpoint):
    @requires(["authenticated", "manager"], redirect="sign_in")
    async def get(self, request: Request):
        accounts = await request.db.all(
            select(Account)
            .where(Account.of_organization(request.user.organization.id))
            .order_by(*Account.by_name)
        )
        return config.templates.TemplateResponse(
            "accounts.html",
            {
                "request": request,
                "is_management": True,
                "accounts": accounts,
            },
        )


class AccountEndpoint(HTTPEndpoint):
    @requires("authenticated", redirect="sign_in")
    async def get(self, request: Request):
        organization_id = request.user.organization_id
        account_id = request.path_params.get("id", request.user.id)
        is_management = "id" in request.path_params and request.user.is_manager

        if account_id != request.user.id and not is_management:
            raise HTTPException(status_code=404)

        account = await request.db.scalar(
            select(Account)
            .options(orm.undefer(Account.balance))
            .outerjoin(Account.entries)
            .where(Account.id == account_id)
            .group_by(Account.id)
            .limit(1)
        )

        if is_management:
            accounts = await request.db.all(
                select(Account)
                .where(Account.of_organization(organization_id))
                .order_by(*Account.by_name)
            )
        else:
            accounts = []

        entries_by_date = await request.db.all(
            select(Entry).where(Entry.of_account(account_id)).order_by(*Entry.by_date)
        )

        entries_by_expiration = await request.db.all(
            select(Entry)
            .where(
                Entry.of_account(account_id),
                Entry.active,
            )
            .order_by(*Entry.by_expiration)
        )

        return config.templates.TemplateResponse(
            "account.html",
            {
                "request": request,
                "is_management": is_management,
                "accounts": accounts,
                "account": account,
                "entries_by_date": entries_by_date,
                "entries_by_expiration": entries_by_expiration,
            },
        )


# Exception handler.
async def handle_exception(request: Request, exception: HTTPException | Exception):
    try:
        status_code = exception.status_code
    except AttributeError:
        status_code = 500
    return config.templates.TemplateResponse(
        "error.html",
        {"request": request, "status_code": status_code},
        status_code=status_code,
    )


def handle_authentication_error(conn: HTTPConnection, exc: Exception):
    raise HTTPException(status_code=401)


routes = [
    Mount("/static", StaticFiles(directory="static"), name="static"),
    Route("/", RootEndpoint, methods=["GET"], name="root"),
    Route("/sign-in", SessionEndpoint, methods=["GET"], name="sign_in"),
    Route("/oauth", OAuthEndpoint, methods=["GET"], name="oauth"),
    Route("/session", SessionEndpoint, methods=["POST", "DELETE"], name="session"),
    Route("/entries", EntriesEndpoint, methods=["GET", "POST"], name="entries"),
    Route("/entries/new", NewEntryEndpoint, methods=["GET"], name="new_entry"),
    Route("/summary", SummaryEndpoint, methods=["GET"], name="summary"),
    Route("/accounts", AccountsEndpoint, methods=["GET"], name="accounts"),
    Route("/account", AccountEndpoint, methods=["GET"], name="account"),
    Route("/accounts/{id:int}", AccountEndpoint, methods=["GET"], name="account"),
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
        Middleware(DatabaseMiddleware),
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
