import os


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
database_url = os.environ.get("DATABASE_URL")

if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "troque-esta-chave-em-producao")
    TIMEZONE = os.environ.get("TIMEZONE", "America/Manaus")
    SQLALCHEMY_DATABASE_URI = database_url or "sqlite:///" + os.path.join(BASE_DIR, "instance", "inventario.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

