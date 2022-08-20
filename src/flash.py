from starlette.requests import Request

import types


def flash(request: Request) -> dict:
    """
    Short lived session data.
    """

    if not "flash" in request.state:
        request.state.flash = request.session.pop("flash", {})

        def __getitem__(self, name):
            return (self + request.state.flash)[name]

        request.session["flash"] = {}
        request.session["flash"].__getitem__ = types.MethodType(
            __getitem__, request.session["flash"]
        )

    return request.session["flash"]


Request.flash = flash
