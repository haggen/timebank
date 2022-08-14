from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class Flash(dict):
    def __init__(self, session: dict):
        self.update(session.pop("flash", {}))
        self.session = session

    def __setitem__(self, name: str, value: any):
        super().__setitem__(name, value)
        if not "flash" in self.session:
            self.session["flash"] = {}
        self.session["flash"][name] = value


Request.flash = property(lambda request: request.state.flash)


class FlashMiddleware(BaseHTTPMiddleware):
    """
    Pop flash message from session and store it in request.flash.
    """

    async def dispatch(self, request, call_next):
        request.state.flash = Flash(request.session)
        return await call_next(request)
