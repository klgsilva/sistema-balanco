from datetime import datetime
from decimal import Decimal
import json

from flask_login import UserMixin
from sqlalchemy import UniqueConstraint
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db, login_manager


PERFIS_USUARIO = {
    "admin": "Administrador",
    "operador": "Operador",
}

PERMISSOES_USUARIO = {
    "painel": "Painel",
    "lancamento": "Novo lancamento",
    "produtos": "Produtos",
    "relatorios": "Relatorios",
    "exportar_csv": "Exportar CSV",
    "editar_produto": "Editar produto",
    "excluir_produto": "Excluir produto",
    "lojas": "Cadastro de lojas",
    "corredores": "Cadastro de corredores",
    "usuarios": "Cadastro de usuarios",
}

MODULOS_PERMISSAO = {
    "Operacao": ("painel", "lancamento"),
    "Produtos": ("produtos", "editar_produto", "excluir_produto"),
    "Relatorios": ("relatorios", "exportar_csv"),
    "Cadastros": ("lojas", "corredores", "usuarios"),
}

PERMISSOES_OPERADOR_PADRAO = {"painel", "lancamento", "produtos"}

LOCAIS_ESTOQUE = {
    "store": "Loja",
    "warehouse": "Deposito",
}

ORIGENS_PRODUTO = {
    "cd": "Centro de distribuicao",
    "third_party": "Terceiros",
}

TIPOS_MEDIDA = {
    "unit": "Unidade",
    "kg": "Kg",
    "box": "Caixa",
    "bundle": "Fardo",
}

TIPOS_MEDIDA_LOJA = {"unit", "kg"}
TIPOS_MEDIDA_DEPOSITO = {"box", "bundle"}


class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), nullable=False, unique=True, index=True)
    senha_hash = db.Column(db.String(255), nullable=False)
    perfil = db.Column(db.String(30), nullable=False, default="operador")
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    loja_id = db.Column(db.Integer, db.ForeignKey("loja.id"))
    ver_todas_lojas = db.Column(db.Boolean, nullable=False, default=False)
    permissoes = db.Column(db.Text, nullable=False, default="[]")

    produtos = db.relationship("ProdutoInventario", back_populates="usuario")
    loja = db.relationship("Loja", back_populates="usuarios")

    def set_password(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_password(self, senha):
        return check_password_hash(self.senha_hash, senha)

    @property
    def is_admin(self):
        return self.perfil == "admin"

    @property
    def pode_ver_todas_lojas(self):
        return self.is_admin or self.ver_todas_lojas

    @property
    def permissoes_set(self):
        if self.is_admin:
            return set(PERMISSOES_USUARIO)
        try:
            valores = json.loads(self.permissoes or "[]")
        except json.JSONDecodeError:
            valores = []
        return {valor for valor in valores if valor in PERMISSOES_USUARIO}

    def set_permissoes(self, valores):
        permissoes = [valor for valor in valores if valor in PERMISSOES_USUARIO]
        self.permissoes = json.dumps(sorted(set(permissoes)))

    @property
    def perfil_label(self):
        return PERFIS_USUARIO.get(self.perfil, self.perfil.title())

    @property
    def is_active(self):
        return self.ativo

    def can_access(self, area):
        if self.is_admin:
            return True
        return area in self.permissoes_set


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Usuario, int(user_id))


class Corredor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False, unique=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    produtos = db.relationship("ProdutoInventario", back_populates="corredor")


class Loja(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    codigo = db.Column(db.String(30), nullable=False, unique=True)
    ativa = db.Column(db.Boolean, nullable=False, default=True)
    criada_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    usuarios = db.relationship("Usuario", back_populates="loja")
    produtos = db.relationship("ProdutoInventario", back_populates="loja")


class ProdutoInventario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo_barras = db.Column(db.String(80), nullable=False, index=True)
    nome = db.Column(db.String(160), nullable=False)
    local_estoque = db.Column(db.String(30), nullable=False, default="store")
    loja_id = db.Column(db.Integer, db.ForeignKey("loja.id"))
    corredor_id = db.Column(db.Integer, db.ForeignKey("corredor.id"))
    origem = db.Column(db.String(30), nullable=False, default="cd")
    margem = db.Column(db.Numeric(8, 2), nullable=False, default=Decimal("20.00"))
    preco_venda = db.Column(db.Numeric(12, 2), nullable=False)
    preco_custo = db.Column(db.Numeric(12, 2), nullable=False)
    quantidade = db.Column(db.Numeric(12, 3), nullable=False, default=Decimal("1.000"))
    tipo_medida = db.Column(db.String(20), nullable=False, default="unit")
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"))
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    usuario = db.relationship("Usuario", back_populates="produtos")
    loja = db.relationship("Loja", back_populates="produtos")
    corredor = db.relationship("Corredor", back_populates="produtos")

    @property
    def local_label(self):
        return LOCAIS_ESTOQUE.get(self.local_estoque, self.local_estoque)

    @property
    def origem_label(self):
        return ORIGENS_PRODUTO.get(self.origem, self.origem)

    @property
    def medida_label(self):
        labels = {
            "kg": "kg",
            "box": "cx",
            "bundle": "fardo",
        }
        return labels.get(self.tipo_medida, "un")

    @property
    def total_custo(self):
        return (self.preco_custo or Decimal("0.00")) * (self.quantidade or Decimal("0.000"))

    @property
    def total_venda(self):
        return (self.preco_venda or Decimal("0.00")) * (self.quantidade or Decimal("0.000"))
