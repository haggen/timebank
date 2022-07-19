from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

Flash = dict[str, str]


def flash(request: Request, message: str = None, type: str = "") -> Flash | None:
    """
    Get or set flash message.
    """
    if message is None:
        return request.state.flash

    request.session["flash"] = {"type": type, "message": message}


Request.flash = flash


class FlashMiddleware(BaseHTTPMiddleware):
    """
    Pop flash message from session and store it in request.flash.
    """

    async def dispatch(self, request, call_next):
        request.state.flash = request.session.pop("flash", {})
        return await call_next(request)
