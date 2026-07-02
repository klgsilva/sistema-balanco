from decimal import Decimal
from datetime import timedelta, timezone
import os
import sqlite3
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Flask

from app.extensions import db, login_manager, migrate


def _sqlite_path(app):
    uri = app.config["SQLALCHEMY_DATABASE_URI"]
    prefix = "sqlite:///"
    if not uri.startswith(prefix):
        return None
    return uri.replace(prefix, "", 1)


def ensure_runtime_schema(app):
    path = _sqlite_path(app)
    if not path or not os.path.exists(path):
        return
    con = sqlite3.connect(path)
    try:
        usuario_cols = {row[1] for row in con.execute("PRAGMA table_info(usuario)").fetchall()}
        if "ver_todas_lojas" not in usuario_cols:
            con.execute("ALTER TABLE usuario ADD COLUMN ver_todas_lojas BOOLEAN NOT NULL DEFAULT 0")
        if "permissoes" not in usuario_cols:
            con.execute("ALTER TABLE usuario ADD COLUMN permissoes TEXT NOT NULL DEFAULT '[]'")
        con.commit()
    finally:
        con.close()


def create_app(config_object="config.Config"):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    with app.app_context():
        ensure_runtime_schema(app)

    from app.auth.routes import bp as auth_bp
    from app.main.routes import bp as main_bp
    from app.admin.routes import bp as admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)

    @app.template_filter("brl")
    def brl(value):
        if value is None:
            value = Decimal("0.00")
        text = f"{float(value):,.2f}"
        return "R$ " + text.replace(",", "X").replace(".", ",").replace("X", ".")

    @app.template_filter("qty")
    def qty(value):
        number = float(value or 0)
        if number.is_integer():
            return str(int(number))
        return f"{number:.3f}".rstrip("0").rstrip(".").replace(".", ",")

    @app.template_filter("datetime_local")
    def datetime_local(value, formato="%d/%m/%Y %H:%M"):
        if not value:
            return "-"
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        try:
            timezone_local = ZoneInfo(app.config.get("TIMEZONE", "America/Manaus"))
        except ZoneInfoNotFoundError:
            timezone_local = timezone(timedelta(hours=-4))
        return value.astimezone(timezone_local).strftime(formato)

    return app
