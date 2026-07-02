import os


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
database_url = os.environ.get("DATABASE_URL")

if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "troque-esta-chave-em-producao")
    TIMEZONE = os.environ.get("TIMEZONE", "America/Manaus")
    if not database_url:
        os.makedirs(INSTANCE_DIR, exist_ok=True)
    SQLALCHEMY_DATABASE_URI = database_url or "sqlite:///" + os.path.join(INSTANCE_DIR, "inventario.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
