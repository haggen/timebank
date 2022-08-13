import logging

from starlette.config import Config
from starlette.datastructures import Secret, CommaSeparatedStrings
from starlette.templating import Jinja2Templates
from databases import DatabaseURL

# Configuration.
config = Config(".env")

# Enable auto reload and debug messages.
DEBUG = config("DEBUG", cast=bool, default=False)

# Port the web server will listen on.
PORT = config("PORT", cast=int, default=5000)

# Session encryption key. Minimum of 128 bytes.
SECRET_KEY = config("SECRET_KEY", cast=Secret)

# Database URL, e.g. postgresql://username:password@hostname/database
DATABASE_URL = config("DATABASE_URL", cast=DatabaseURL)

# Appication major version, e.g. 1, 2, etc.
VERSION = config("VERSION", cast=int, default=0)

# Appication revision, i.e. git commit hash, e.g. "a1b2c3d4"
REVISION = config("REVISION", cast=str, default="-")

# Google API credentials.
GOOGLE_CLIENT_ID = config("GOOGLE_CLIENT_ID", cast=Secret)
GOOGLE_CLIENT_SECRET = config("GOOGLE_CLIENT_SECRET", cast=Secret)

# Setup Jinja templates.
templates = Jinja2Templates(directory="templates", auto_reload=DEBUG)

# Configure loggers.
if DEBUG:
    logging.getLogger("databases").setLevel(logging.DEBUG)
    logging.getLogger("authlib").setLevel(logging.DEBUG)
