"""Process-wide environment for tests importing the singleton FastAPI app.

The application database engine is created at import time, so every test module
in one pytest process must agree on the same database and authentication values.
"""

import atexit
import json
import os
import secrets
import shutil
import tempfile
from pathlib import Path

ROOT = Path(tempfile.mkdtemp(prefix="ecdat-integration-"))
PASSWORD = secrets.token_urlsafe(24)

os.environ["DATABASE_URL"] = f"sqlite:///{(ROOT / 'test.db').as_posix()}"
os.environ["ECDAT_USERS_JSON"] = json.dumps(
    {"analyst": {"role": "security_analyst", "password": PASSWORD}}
)
os.environ["ECDAT_TOKEN_SECRET"] = secrets.token_urlsafe(48)
os.environ["ECDAT_ALLOW_ROLE_HEADER"] = "true"
os.environ["ECDAT_RATE_LIMIT"] = "10000"
os.environ["ECDAT_AUTO_CREATE_TABLES"] = "true"
os.environ["ECDAT_ENV"] = "test"
os.environ["ECDAT_ALLOW_UNRESTRICTED_SCAN_ROOTS"] = "true"

atexit.register(shutil.rmtree, ROOT, True)
