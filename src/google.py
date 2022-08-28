from requests_oauthlib import OAuth2Session
from starlette.requests import Request

import datetime
import config


class Google:
    authorization_base_url = "https://accounts.google.com/o/oauth2/v2/auth"
    token_url = "https://www.googleapis.com/oauth2/v4/token"
    refresh_url = token_url
    scope = [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/calendar.events.readonly",
    ]
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    revoke_url = "https://oauth2.googleapis.com/revoke"
    validate_url = "https://www.googleapis.com/oauth2/v1/tokeninfo"
    calendar_base_url = "https://www.googleapis.com/calendar/v3/calendars"
    default_calendar_id = "pt.brazilian%23holiday@group.v.calendar.google.com"

    def __init__(self, request: Request, redirect_uri: str = None):
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
            include_granted_scopes="true",
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

    def is_holiday(self, date: datetime.date, calendar_id: str = default_calendar_id):
        """
        Use Google Calendar to check if a given date is a holiday.
        """
        response = self.session.get(f"{self.calendar_base_url}/{calendar_id}/events")
        data = response.json()
        for item in data["items"]:
            try:
                start = datetime.date.fromisoformat(item["start"]["date"])
                end = datetime.date.fromisoformat(item["end"]["date"])
            except KeyError:
                try:
                    start = datetime.datetime.fromisoformat(
                        item["start"]["dateTime"]
                    ).date()
                    end = datetime.datetime.fromisoformat(
                        item["end"]["dateTime"]
                    ).date()
                except KeyError:
                    continue

            if start <= date < end:
                return True
