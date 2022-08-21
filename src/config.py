from starlette.config import Config
from starlette.datastructures import Secret
from starlette.templating import Jinja2Templates

import logging

# Configuration.
config = Config(".env")

# Enable auto reload and debug messages.
DEBUG = config("DEBUG", cast=bool, default=False)

# Port the web server will listen on.
PORT = config("PORT", cast=int, default=5000)

# Session encryption key. Minimum of 128 bytes.
SECRET_KEY = config("SECRET_KEY", cast=Secret)

# Database URL, e.g. postgresql://username:password@hostname/database
DATABASE_URL = config("DATABASE_URL", cast=Secret)

# Appication version, e.g. v1, v2, etc. but only digits.
VERSION = config("VERSION", cast=int, default=0)

# Appication revision, e.g. hash of latest commit, number of builds, etc.
REVISION = config("REVISION", cast=str, default="")

# Google API credentials.
GOOGLE_CLIENT_ID = config("GOOGLE_CLIENT_ID", cast=Secret)
GOOGLE_CLIENT_SECRET = config("GOOGLE_CLIENT_SECRET", cast=Secret)

# Setup Jinja templates.
templates = Jinja2Templates(directory="templates", auto_reload=DEBUG)

# Configure loggers.
if DEBUG:
    logging.basicConfig(level=logging.DEBUG)
