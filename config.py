# config.py
import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "clave-secreta-local")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(os.path.dirname(__file__), 'instance', 'database.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
UPLOAD_FOLDER = "static/uploads"
