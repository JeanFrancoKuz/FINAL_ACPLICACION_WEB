import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "clave-secreta-local")

    # Base de datos en instance/database.db (seguro y ordenado)
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(INSTANCE_DIR, 'database.db')}"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Tamaño máximo permitido para uploads (16MB)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  

    # Carpeta donde se guardarán las fotos y comprobantes
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
