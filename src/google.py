from requests_oauthlib import OAuth2Session
from starlette.requests import Request

import config


class Google:
    authorization_base_url = "https://accounts.google.com/o/oauth2/v2/auth"
    token_url = "https://www.googleapis.com/oauth2/v4/token"
    refresh_url = token_url
    scope = [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
    ]
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    revoke_url = "https://oauth2.googleapis.com/revoke"
    validate_url = "https://www.googleapis.com/oauth2/v1/tokeninfo"

    def __init__(self, request: Request, redirect_uri: str):
        self.session = OAuth2Session(
            client_id=config.GOOGLE_CLIENT_ID,
            scope=self.scope,
            redirect_uri=redirect_uri,
            token=request.session.get("token", None),
            auto_refresh_kwargs={
                "client_id": config.GOOGLE_CLIENT_ID,
                "client_secret": config.GOOGLE_CLIENT_SECRET,
            },
            token_updater=lambda token: request.session.update(token=token),
        )

    def authorization_url(self):
        """
        Get Google authorization URL.
        """
        return self.session.authorization_url(
            url=self.authorization_base_url,
            access_type="offline",
            prompt="select_account",
        )

    def fetch_token(self, returning_uri: str, state: str):
        """
        Fetch token.
        """
        self.token = self.session.fetch_token(
            token_url=self.token_url,
            client_secret=config.GOOGLE_CLIENT_SECRET,
            authorization_response=returning_uri,
            state=state,
        )
        return self.token

    def fetch_userinfo(self):
        """
        Fetch userinfo.
        """
        response = self.session.get(url=self.userinfo_url)
        return response.json()

    def revoke_token(self):
        """
        Revoke token.
        """
        return self.session.post(url=self.revoke_url, params={"token": self.token})
