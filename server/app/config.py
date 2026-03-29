import os
from pathlib import Path

SCORES_ROOT = Path(os.environ.get("SCORES_ROOT", Path(__file__).resolve().parent.parent / "data" / "scores"))
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")
APP_TOKEN = os.environ.get("APP_TOKEN", "dev-app-token-change-me")
SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-secret-key-in-production")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "43200"))
