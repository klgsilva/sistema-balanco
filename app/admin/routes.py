from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Corredor, Loja, MODULOS_PERMISSAO, PERMISSOES_OPERADOR_PADRAO, PERMISSOES_USUARIO, Usuario


bp = Blueprint("admin", __name__, url_prefix="/admin")
ADMIN_PRINCIPAL_EMAIL = "admin@inventario.local"


def require_admin():
    if not current_user.is_admin:
        abort(403)


def require_permission(area):
    if not current_user.can_access(area):
        abort(403)


def permissoes_formulario():
    return request.form.getlist("permissoes")


@bp.route("/corredores", methods=["GET", "POST"])
@login_required
def corredores():
    require_permission("corredores")
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        if not nome:
            flash("Informe o nome do corredor.", "error")
        elif Corredor.query.filter(db.func.lower(Corredor.nome) == nome.lower()).first():
            flash("Ja existe corredor com este nome.", "error")
        else:
            db.session.add(Corredor(nome=nome))
            db.session.commit()
            flash("Corredor cadastrado.", "success")
        return redirect(url_for("admin.corredores"))

    return render_template("admin/corredores.html", corredores=Corredor.query.order_by(Corredor.nome).all())


@bp.route("/lojas", methods=["GET", "POST"])
@login_required
def lojas():
    require_permission("lojas")
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        codigo = request.form.get("codigo", "").strip().upper()
        if not nome or not codigo:
            flash("Informe nome e codigo da loja.", "error")
        elif Loja.query.filter(db.func.lower(Loja.codigo) == codigo.lower()).first():
            flash("Ja existe loja com este codigo.", "error")
        else:
            db.session.add(Loja(nome=nome, codigo=codigo))
            db.session.commit()
            flash("Loja cadastrada.", "success")
        return redirect(url_for("admin.lojas"))

    return render_template("admin/lojas.html", lojas=Loja.query.order_by(Loja.nome).all())


@bp.route("/lojas/<int:loja_id>/editar", methods=["POST"])
@login_required
def editar_loja(loja_id):
    require_permission("lojas")
    loja = db.session.get(Loja, loja_id)
    if not loja:
        abort(404)
    nome = request.form.get("nome", "").strip()
    codigo = request.form.get("codigo", "").strip().upper()
    if nome and codigo:
        loja.nome = nome
        loja.codigo = codigo
        loja.ativa = request.form.get("ativa") == "on"
        db.session.commit()
        flash("Loja atualizada.", "success")
    return redirect(url_for("admin.lojas"))


@bp.route("/corredores/<int:corredor_id>/editar", methods=["POST"])
@login_required
def editar_corredor(corredor_id):
    require_permission("corredores")
    corredor = db.session.get(Corredor, corredor_id)
    if not corredor:
        abort(404)
    nome = request.form.get("nome", "").strip()
    if nome:
        corredor.nome = nome
        corredor.ativo = request.form.get("ativo") == "on"
        db.session.commit()
        flash("Corredor atualizado.", "success")
    return redirect(url_for("admin.corredores"))


@bp.route("/usuarios", methods=["GET", "POST"])
@login_required
def usuarios():
    require_permission("usuarios")
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")
        loja_id = request.form.get("loja_id", type=int)
        if not nome or not email or not senha:
            flash("Preencha nome, e-mail e senha.", "error")
        elif not loja_id:
            flash("Escolha a loja do usuario.", "error")
        elif Usuario.query.filter_by(email=email).first():
            flash("Ja existe usuario com este e-mail.", "error")
        else:
            usuario = Usuario(
                nome=nome,
                email=email,
                perfil="operador",
                loja_id=loja_id,
                ver_todas_lojas=False,
            )
            usuario.set_permissoes(PERMISSOES_OPERADOR_PADRAO)
            usuario.set_password(senha)
            db.session.add(usuario)
            db.session.commit()
            flash("Usuario cadastrado.", "success")
            return redirect(url_for("admin.usuarios", usuario_id=usuario.id) + "#permissoes")
        return redirect(url_for("admin.usuarios"))

    usuarios_lista = Usuario.query.order_by(Usuario.nome).all()
    selected_usuario_id = request.args.get("usuario_id", type=int)
    selected_usuario = None
    if selected_usuario_id:
        selected_usuario = db.session.get(Usuario, selected_usuario_id)

    return render_template(
        "admin/usuarios.html",
        usuarios=usuarios_lista,
        selected_usuario=selected_usuario,
        permissoes=PERMISSOES_USUARIO,
        modulos_permissao=MODULOS_PERMISSAO,
        permissoes_padrao=PERMISSOES_OPERADOR_PADRAO,
        lojas=Loja.query.filter_by(ativa=True).order_by(Loja.nome).all(),
    )


@bp.route("/usuarios/<int:usuario_id>/editar", methods=["POST"])
@login_required
def editar_usuario(usuario_id):
    require_permission("usuarios")
    usuario = db.session.get(Usuario, usuario_id)
    if not usuario:
        abort(404)
    admin_principal = usuario.email == ADMIN_PRINCIPAL_EMAIL

    if admin_principal:
        usuario.nome = request.form.get("nome", usuario.nome).strip() or usuario.nome
        usuario.email = ADMIN_PRINCIPAL_EMAIL
        usuario.perfil = "admin"
        usuario.ativo = True
        usuario.ver_todas_lojas = True
        usuario.set_permissoes(PERMISSOES_USUARIO)
    else:
        usuario.nome = request.form.get("nome", usuario.nome).strip()
        usuario.email = request.form.get("email", usuario.email).strip().lower()
        usuario.perfil = "operador"
        usuario.ativo = request.form.get("ativo") == "on"
        usuario.ver_todas_lojas = request.form.get("ver_todas_lojas") == "on"
        loja_id = request.form.get("loja_id", type=int)
        if not usuario.ver_todas_lojas and not loja_id:
            flash("Escolha a loja do usuario.", "error")
            return redirect(url_for("admin.usuarios", usuario_id=usuario.id) + "#permissoes")
        usuario.loja_id = None if usuario.ver_todas_lojas else loja_id
        usuario.set_permissoes(permissoes_formulario())

    senha = request.form.get("senha", "")
    if senha:
        usuario.set_password(senha)
    db.session.commit()
    return redirect(url_for("admin.usuarios", usuario_id=usuario.id, salvo=usuario.id) + "#permissoes")
