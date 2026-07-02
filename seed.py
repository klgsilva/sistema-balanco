from decimal import Decimal
import os
import sqlite3

from app import create_app
from app.extensions import db
from app.models import Corredor, Loja, PERMISSOES_OPERADOR_PADRAO, PERMISSOES_USUARIO, ProdutoInventario, Usuario


CORREDORES = ["Enlatados", "Molhos", "Frios", "Bebidas", "Limpeza", "Higiene", "Mercearia", "Acougue"]
LOJAS = [
    ("L01", "Alvorada"),
    ("L02", "Av Brasil"),
    ("L03", "Cachoeirinha"),
    ("L04", "Cidade Nova"),
    ("L05", "Educandos"),
    ("L06", "Fuxico"),
    ("L07", "Lirio do Vale"),
    ("L08", "Manoa"),
    ("L09", "Nova Cidade"),
    ("L10", "Ponte"),
    ("L11", "Torquato"),
    ("L12", "Zumbi"),
]


def sqlite_path(app):
    uri = app.config["SQLALCHEMY_DATABASE_URI"]
    prefix = "sqlite:///"
    if not uri.startswith(prefix):
        return None
    return uri.replace(prefix, "", 1)


def ensure_sqlite_schema(app):
    path = sqlite_path(app)
    if not path or not os.path.exists(path):
        return

    con = sqlite3.connect(path)
    try:
        usuario_cols = {row[1] for row in con.execute("PRAGMA table_info(usuario)").fetchall()}
        if "loja_id" not in usuario_cols:
            con.execute("ALTER TABLE usuario ADD COLUMN loja_id INTEGER")
        if "ver_todas_lojas" not in usuario_cols:
            con.execute("ALTER TABLE usuario ADD COLUMN ver_todas_lojas BOOLEAN NOT NULL DEFAULT 0")
        if "permissoes" not in usuario_cols:
            con.execute("ALTER TABLE usuario ADD COLUMN permissoes TEXT NOT NULL DEFAULT '[]'")

        produto_cols = {row[1] for row in con.execute("PRAGMA table_info(produto_inventario)").fetchall()}
        if "loja_id" not in produto_cols:
            con.execute("ALTER TABLE produto_inventario ADD COLUMN loja_id INTEGER")

        produto_sql = con.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='produto_inventario'"
        ).fetchone()
        if produto_sql and "uq_codigo_local_corredor" in produto_sql[0]:
            con.execute("PRAGMA foreign_keys=OFF")
            con.execute(
                """
                CREATE TABLE produto_inventario_new (
                    id INTEGER NOT NULL,
                    codigo_barras VARCHAR(80) NOT NULL,
                    nome VARCHAR(160) NOT NULL,
                    local_estoque VARCHAR(30) NOT NULL,
                    loja_id INTEGER,
                    corredor_id INTEGER,
                    origem VARCHAR(30) NOT NULL,
                    margem NUMERIC(8, 2) NOT NULL,
                    preco_venda NUMERIC(12, 2) NOT NULL,
                    preco_custo NUMERIC(12, 2) NOT NULL,
                    quantidade NUMERIC(12, 3) NOT NULL,
                    tipo_medida VARCHAR(20) NOT NULL,
                    usuario_id INTEGER,
                    criado_em DATETIME NOT NULL,
                    atualizado_em DATETIME NOT NULL,
                    PRIMARY KEY (id),
                    FOREIGN KEY(loja_id) REFERENCES loja (id),
                    FOREIGN KEY(corredor_id) REFERENCES corredor (id),
                    FOREIGN KEY(usuario_id) REFERENCES usuario (id)
                )
                """
            )
            con.execute(
                """
                INSERT INTO produto_inventario_new (
                    id, codigo_barras, nome, local_estoque, loja_id, corredor_id, origem,
                    margem, preco_venda, preco_custo, quantidade, tipo_medida, usuario_id,
                    criado_em, atualizado_em
                )
                SELECT
                    id, codigo_barras, nome, local_estoque, loja_id, corredor_id, origem,
                    margem, preco_venda, preco_custo, quantidade, tipo_medida, usuario_id,
                    criado_em, atualizado_em
                FROM produto_inventario
                """
            )
            con.execute("DROP TABLE produto_inventario")
            con.execute("ALTER TABLE produto_inventario_new RENAME TO produto_inventario")
            con.execute("CREATE INDEX IF NOT EXISTS ix_produto_inventario_codigo_barras ON produto_inventario (codigo_barras)")
            con.execute("PRAGMA foreign_keys=ON")

        con.commit()
    finally:
        con.close()


def main():
    app = create_app()
    with app.app_context():
        db.create_all()
        ensure_sqlite_schema(app)

        lojas_existentes = Loja.query.order_by(Loja.id).all()
        if len(lojas_existentes) == len(LOJAS):
            for loja, (codigo, nome) in zip(lojas_existentes, LOJAS):
                loja.codigo = codigo
                loja.nome = nome
                loja.ativa = True
        else:
            for codigo, nome in LOJAS:
                loja = Loja.query.filter_by(codigo=codigo).first()
                if loja:
                    loja.nome = nome
                    loja.ativa = True
                elif not Loja.query.filter(db.func.lower(Loja.nome) == nome.lower()).first():
                    db.session.add(Loja(nome=nome, codigo=codigo))
        db.session.commit()
        loja_padrao = Loja.query.filter_by(codigo="L01").first() or Loja.query.order_by(Loja.nome).first()

        if not Usuario.query.filter_by(email="admin@inventario.local").first():
            admin = Usuario(nome="Ricardo Klinger", email="admin@inventario.local", perfil="admin")
            admin.set_password("admin123")
            db.session.add(admin)

        if not Usuario.query.filter_by(email="operador@inventario.local").first():
            operador = Usuario(nome="Operador", email="operador@inventario.local", perfil="operador", loja_id=loja_padrao.id)
            operador.set_permissoes(PERMISSOES_OPERADOR_PADRAO)
            operador.set_password("operador123")
            db.session.add(operador)

        for nome in CORREDORES:
            if not Corredor.query.filter_by(nome=nome).first():
                db.session.add(Corredor(nome=nome))

        db.session.commit()

        admin_principal = Usuario.query.filter_by(email="admin@inventario.local").first()
        if admin_principal:
            admin_principal.perfil = "admin"
            admin_principal.ativo = True
            admin_principal.ver_todas_lojas = True
            admin_principal.loja_id = None
            admin_principal.set_permissoes(PERMISSOES_USUARIO)
        for usuario in Usuario.query.filter(Usuario.perfil != "admin").all():
            if not usuario.permissoes or usuario.permissoes == "[]":
                usuario.set_permissoes(PERMISSOES_OPERADOR_PADRAO)
            permissoes = usuario.permissoes_set
            if "editar_produto" in permissoes and "excluir_produto" not in permissoes:
                permissoes.add("excluir_produto")
                usuario.set_permissoes(permissoes)
        db.session.commit()

        Usuario.query.filter(Usuario.perfil != "admin", Usuario.loja_id.is_(None)).update({"loja_id": loja_padrao.id})
        ProdutoInventario.query.filter(ProdutoInventario.loja_id.is_(None)).update({"loja_id": loja_padrao.id})
        db.session.commit()

        if ProdutoInventario.query.count() == 0:
            corredor = Corredor.query.filter_by(nome="Molhos").first()
            usuario = Usuario.query.filter_by(email="admin@inventario.local").first()
            produtos = [
                ProdutoInventario(
                    codigo_barras="7891000000011",
                    nome="Molho de tomate tradicional",
                    local_estoque="store",
                    loja_id=loja_padrao.id,
                    corredor_id=corredor.id,
                    origem="cd",
                    margem=Decimal("20.00"),
                    preco_venda=Decimal("4.99"),
                    preco_custo=Decimal("3.99"),
                    quantidade=Decimal("24.000"),
                    tipo_medida="unit",
                    usuario_id=usuario.id,
                ),
                ProdutoInventario(
                    codigo_barras="7891000000028",
                    nome="Carne bovina acougue",
                    local_estoque="warehouse",
                    loja_id=loja_padrao.id,
                    origem="third_party",
                    margem=Decimal("30.00"),
                    preco_venda=Decimal("39.90"),
                    preco_custo=Decimal("27.93"),
                    quantidade=Decimal("12.450"),
                    tipo_medida="kg",
                    usuario_id=usuario.id,
                ),
            ]
            db.session.add_all(produtos)
            db.session.commit()

        print("Banco preparado.")
        print("Admin: admin@inventario.local / admin123")
        print("Operador: operador@inventario.local / operador123")


if __name__ == "__main__":
    main()
