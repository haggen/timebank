from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.requests import Request


Request.flash = property(lambda self: self.state.flash, doc="Short lived session data.")


class Flash(dict):
    """
    A dictionary-like object for storing short-lived session data.
    """

    def __setitem__(self, name: str, value: any):
        if not "flash" in self.session:
            self.session["flash"] = {}
        self.session["flash"][name] = value
        return super().__setitem__(name, value)


class FlashMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            if not "session" in scope:
                raise RuntimeError(
                    "SessionMiddleware must be installed and come before FlashMiddleware for it to work."
                )
            if not "state" in scope:
                scope["state"] = {}
            scope["state"]["flash"] = Flash(scope["session"].pop("flash", {}))
            scope["state"]["flash"].session = scope["session"]

        await self.app(scope, receive, send)
