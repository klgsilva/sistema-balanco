from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.models import Usuario


bp = Blueprint("auth", __name__)


def destino_inicial(usuario):
    destinos = [
        ("painel", "main.dashboard"),
        ("lancamento", "main.lancamento"),
        ("produtos", "main.produtos"),
        ("relatorios", "main.relatorios"),
        ("usuarios", "admin.usuarios"),
        ("lojas", "admin.lojas"),
        ("corredores", "admin.corredores"),
    ]
    for permissao, endpoint in destinos:
        if usuario.can_access(permissao):
            return url_for(endpoint)
    return url_for("auth.logout")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(destino_inicial(current_user))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")
        usuario = Usuario.query.filter_by(email=email).first()

        if usuario and usuario.ativo and usuario.check_password(senha):
            login_user(usuario)
            return redirect(request.args.get("next") or destino_inicial(usuario))

        flash("E-mail ou senha invalidos.", "error")

    return render_template("auth/login.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Sessao encerrada.", "success")
    return redirect(url_for("auth.login"))
