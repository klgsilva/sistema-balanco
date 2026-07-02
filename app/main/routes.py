import csv
from decimal import Decimal, InvalidOperation
from io import BytesIO, StringIO

from flask import Blueprint, Response, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import (
    Corredor,
    Loja,
    LOCAIS_ESTOQUE,
    ORIGENS_PRODUTO,
    ProdutoInventario,
    TIPOS_MEDIDA,
    TIPOS_MEDIDA_DEPOSITO,
    TIPOS_MEDIDA_LOJA,
)


bp = Blueprint("main", __name__)

MENSAGEM_FILTRO_AMPLO = "Escolha uma loja ou informe uma busca para evitar carregar produtos de todas as lojas."
MENSAGEM_RELATORIO_LOJA = "Escolha uma loja para consultar os relatorios."
MENSAGEM_RELATORIO_PDF = "Escolha uma loja e um corredor, ou selecione Deposito, para visualizar o PDF."


def require_access(area):
    if not current_user.can_access(area):
        abort(403)


def parse_decimal(valor, casas="0.01"):
    texto = (valor or "0").strip().replace("R$", "").replace(" ", "")
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "." in texto:
        partes = texto.split(".")
        if len(partes) > 2 or len(partes[-1]) == 3:
            texto = "".join(partes)
    try:
        return Decimal(texto).quantize(Decimal(casas))
    except InvalidOperation:
        raise ValueError("Informe um valor valido.")


def parse_quantidade(valor, tipo_medida):
    texto = (valor or "0").strip().replace(" ", "")
    if tipo_medida == "kg":
        if "," in texto:
            antes, depois = texto.rsplit(",", 1)
            if "." in antes and set(depois) <= {"0"}:
                texto = antes
            else:
                texto = texto.replace(".", "").replace(",", ".")
        try:
            return Decimal(texto).quantize(Decimal("0.001"))
        except InvalidOperation:
            raise ValueError("Informe um peso valido.")
    if tipo_medida in {"box", "bundle"}:
        quantidade = parse_decimal(texto, "0.001")
        if quantidade != quantidade.to_integral_value():
            raise ValueError("Informe caixas ou fardos em quantidade inteira.")
        return quantidade.quantize(Decimal("1"))
    return parse_decimal(texto, "0.001")


def calcular_custo(preco_venda, margem):
    return (preco_venda * (Decimal("1.00") - (margem / Decimal("100")))).quantize(Decimal("0.01"))


def limpar_codigo_barras(valor):
    return "".join(caractere for caractere in (valor or "") if caractere.isdigit())


def produto_query_filtrada(args):
    query = ProdutoInventario.query
    loja_id = args.get("loja_id", type=int)
    local = args.get("local_estoque", "")
    corredor_id = args.get("corredor_id", type=int)
    busca = args.get("busca", "").strip()

    if current_user.pode_ver_todas_lojas:
        if loja_id:
            query = query.filter(ProdutoInventario.loja_id == loja_id)
    else:
        query = query.filter(ProdutoInventario.loja_id == current_user.loja_id)

    if local in LOCAIS_ESTOQUE:
        query = query.filter(ProdutoInventario.local_estoque == local)
    if corredor_id and local != "warehouse":
        query = query.filter(ProdutoInventario.corredor_id == corredor_id)
    if busca:
        like = f"%{busca}%"
        query = query.filter(
            db.or_(ProdutoInventario.nome.ilike(like), ProdutoInventario.codigo_barras.ilike(like))
        )

    return query.order_by(ProdutoInventario.criado_em.desc())


def corredores_ativos():
    return Corredor.query.filter_by(ativo=True).order_by(Corredor.nome).all()


def lojas_da_visao():
    if current_user.pode_ver_todas_lojas:
        return Loja.query.filter_by(ativa=True).order_by(Loja.nome).all()
    return [current_user.loja] if current_user.loja else []


def produto_da_visao_ou_404(produto_id):
    produto = db.session.get(ProdutoInventario, produto_id)
    if not produto:
        abort(404)
    if not current_user.pode_ver_todas_lojas and produto.loja_id != current_user.loja_id:
        abort(404)
    return produto


def loja_do_lancamento(args=None):
    if current_user.pode_ver_todas_lojas:
        loja_id = (args or request.args).get("loja_id", type=int)
        if loja_id:
            return db.session.get(Loja, loja_id)
        return None
    return current_user.loja


def totais(produtos):
    quantidade_unidade = sum(
        (p.quantidade or Decimal("0.000") for p in produtos if p.tipo_medida == "unit"),
        Decimal("0.000"),
    )
    peso_kg = sum(
        (p.quantidade or Decimal("0.000") for p in produtos if p.tipo_medida == "kg"),
        Decimal("0.000"),
    )
    quantidade_caixa = sum(
        (p.quantidade or Decimal("0.000") for p in produtos if p.tipo_medida == "box"),
        Decimal("0.000"),
    )
    quantidade_fardo = sum(
        (p.quantidade or Decimal("0.000") for p in produtos if p.tipo_medida == "bundle"),
        Decimal("0.000"),
    )
    return {
        "itens": len(produtos),
        "quantidade": quantidade_unidade,
        "quantidade_unidade": quantidade_unidade,
        "peso_kg": peso_kg,
        "quantidade_caixa": quantidade_caixa,
        "quantidade_fardo": quantidade_fardo,
        "custo": sum((p.total_custo for p in produtos), Decimal("0.00")),
        "venda": sum((p.total_venda for p in produtos), Decimal("0.00")),
    }


def filtro_foi_aplicado(args):
    return args.get("filtrar") == "1" or any(
        args.get(campo, "").strip()
        for campo in ("busca", "loja_id", "local_estoque", "corredor_id")
    )


def filtro_amplo_bloqueado(args):
    if not current_user.pode_ver_todas_lojas:
        return False
    loja_id = args.get("loja_id", type=int)
    busca = args.get("busca", "").strip()
    return not loja_id and not busca


def filtro_relatorio_bloqueado(args):
    return current_user.pode_ver_todas_lojas and not args.get("loja_id", type=int)


def relatorio_pdf_disponivel(args, produtos, filtro_aplicado, filtro_bloqueado):
    if not filtro_aplicado or filtro_bloqueado or not produtos:
        return False
    if current_user.pode_ver_todas_lojas and not args.get("loja_id", type=int):
        return False
    return bool(args.get("corredor_id", type=int) or args.get("local_estoque") == "warehouse")


def texto_pdf(valor):
    texto = str(valor or "")
    texto = texto.encode("latin-1", "replace").decode("latin-1")
    return texto.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def formatar_brl(valor):
    if valor is None:
        valor = Decimal("0.00")
    text = f"{float(valor):,.2f}"
    return "R$ " + text.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_quantidade(valor):
    number = float(valor or 0)
    if number.is_integer():
        return str(int(number))
    return f"{number:.3f}".rstrip("0").rstrip(".").replace(".", ",")


def linha_pdf(comandos, x, y, texto, tamanho=9, negrito=False):
    fonte = "F2" if negrito else "F1"
    comandos.append(f"BT /{fonte} {tamanho} Tf {x} {y} Td ({texto_pdf(texto)}) Tj ET")


def linha_horizontal_pdf(comandos, y, x1=36, x2=560):
    comandos.append(f"{x1} {y} m {x2} {y} l S")


def gerar_pdf_relatorio(produtos, grupos, totais_gerais):
    pages = []
    comandos = []
    y = 0
    margem = 36
    loja = produtos[0].loja if produtos else None

    def desenhar_cabecalho(numero_pagina):
        nonlocal y
        y = 800
        linha_pdf(comandos, margem, y, f"MARA FRIOS - {loja.nome.upper()}" if loja else "MARA FRIOS", 15, True)
        y -= 18
        linha_pdf(comandos, margem, y, f"Relatorio das folhas do balanco - Pagina: {numero_pagina}", 11, True)
        y -= 10
        linha_horizontal_pdf(comandos, y)
        y -= 18

    def desenhar_cabecalho_tabela():
        nonlocal y
        linha_pdf(comandos, margem, y, "Descricao", 8, True)
        linha_pdf(comandos, 255, y, "Barras", 8, True)
        linha_pdf(comandos, 360, y, "Custo unit", 8, True)
        linha_pdf(comandos, 445, y, "Qtde", 8, True)
        linha_pdf(comandos, 520, y, "Total", 8, True)
        linha_horizontal_pdf(comandos, y - 6)
        y -= 18

    def nova_pagina():
        nonlocal comandos, y
        if comandos:
            pages.append("\n".join(comandos))
        comandos = []
        desenhar_cabecalho(len(pages) + 1)

    def garantir(altura=16, repetir_tabela=False):
        nonlocal y
        if y < 60 + altura:
            nova_pagina()
            if repetir_tabela:
                desenhar_cabecalho_tabela()

    desenhar_cabecalho(1)
    linha_pdf(comandos, margem, y, f"Itens: {totais_gerais['itens']}  Custo total: {formatar_brl(totais_gerais['custo'])}", 10, True)
    y -= 26

    for nome, total, itens in grupos:
        garantir(90)
        linha_pdf(comandos, margem, y, nome, 12, True)
        y -= 15
        resumo = (
            f"Itens: {total['itens']} | Unid: {formatar_quantidade(total['quantidade_unidade'])} | "
            f"Kg: {formatar_quantidade(total['peso_kg'])} | Caixas: {formatar_quantidade(total['quantidade_caixa'])} | "
            f"Fardos: {formatar_quantidade(total['quantidade_fardo'])} | Custo: {formatar_brl(total['custo'])}"
        )
        linha_pdf(comandos, margem, y, resumo[:118], 8)
        y -= 16
        desenhar_cabecalho_tabela()
        for item in itens:
            garantir(20, repetir_tabela=True)
            linha_pdf(comandos, margem, y, item.nome[:42], 8, True)
            linha_pdf(comandos, 255, y, item.codigo_barras[:14], 8, True)
            linha_pdf(comandos, 360, y, formatar_brl(item.preco_custo), 8, True)
            linha_pdf(comandos, 445, y, f"{formatar_quantidade(item.quantidade)} {item.medida_label}"[:12], 8, True)
            linha_pdf(comandos, 520, y, formatar_brl(item.total_custo), 8, True)
            linha_horizontal_pdf(comandos, y - 6)
            y -= 18
        y -= 14

    if comandos:
        pages.append("\n".join(comandos))

    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        None,
    ]
    page_ids = []
    for content in pages:
        page_id = len(objetos) + 1
        content_id = page_id + 1
        page_ids.append(page_id)
        objetos.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 {len(pages) * 2 + 3} 0 R /F2 {len(pages) * 2 + 4} 0 R >> >> /Contents {content_id} 0 R >>".encode("latin-1")
        )
        stream = content.encode("latin-1", "replace")
        objetos.append(b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream")
    objetos[1] = f"<< /Type /Pages /Kids [{' '.join(f'{pid} 0 R' for pid in page_ids)}] /Count {len(page_ids)} >>".encode("latin-1")
    objetos.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objetos.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")

    buffer = BytesIO()
    buffer.write(b"%PDF-1.4\n")
    offsets = [0]
    for indice, objeto in enumerate(objetos, start=1):
        offsets.append(buffer.tell())
        buffer.write(f"{indice} 0 obj\n".encode("ascii"))
        buffer.write(objeto)
        buffer.write(b"\nendobj\n")
    xref = buffer.tell()
    buffer.write(f"xref\n0 {len(objetos) + 1}\n".encode("ascii"))
    buffer.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        buffer.write(f"{offset:010d} 00000 n \n".encode("ascii"))
    buffer.write(f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode("ascii"))
    return buffer.getvalue()


def totais_lancamento_por_bucket(loja_id, ignore_id=None):
    buckets = {}
    for corredor in corredores_ativos():
        buckets[str(corredor.id)] = {
            "label": corredor.nome,
            "itens": 0,
            "custo": Decimal("0.00"),
            "venda": Decimal("0.00"),
        }
    buckets["__warehouse__"] = {
        "label": "Deposito",
        "itens": 0,
        "custo": Decimal("0.00"),
        "venda": Decimal("0.00"),
    }

    query = ProdutoInventario.query
    query = query.filter(ProdutoInventario.loja_id == loja_id)
    if ignore_id:
        query = query.filter(ProdutoInventario.id != ignore_id)

    for item in query.all():
        key = "__warehouse__" if item.local_estoque == "warehouse" else str(item.corredor_id or "")
        if key not in buckets:
            buckets[key] = {
                "label": item.corredor.nome if item.corredor else item.local_label,
                "itens": 0,
                "custo": Decimal("0.00"),
                "venda": Decimal("0.00"),
            }
        buckets[key]["itens"] += 1
        buckets[key]["custo"] += item.total_custo
        buckets[key]["venda"] += item.total_venda

    return buckets


@bp.route("/")
@login_required
def dashboard():
    require_access("painel")
    query = ProdutoInventario.query
    if not current_user.pode_ver_todas_lojas:
        query = query.filter(ProdutoInventario.loja_id == current_user.loja_id)
    produtos = query.all()
    recentes = query.order_by(ProdutoInventario.criado_em.desc()).limit(8).all()
    por_local = {
        key: query.filter(ProdutoInventario.local_estoque == key).count()
        for key in LOCAIS_ESTOQUE
    }
    return render_template("main/dashboard.html", totais=totais(produtos), recentes=recentes, por_local=por_local)


@bp.route("/manual")
@login_required
def manual():
    return render_template("main/manual.html")


@bp.route("/lancamento", methods=["GET", "POST"])
@login_required
def lancamento():
    require_access("lancamento")
    produto = None
    selected_loja = loja_do_lancamento()
    selected_corredor_id = request.args.get("corredor_id", type=int)
    selected_bucket = request.args.get("bucket", "")
    edit_id = request.args.get("editar", type=int)
    if edit_id:
        if not current_user.can_access("editar_produto"):
            abort(403)
        produto = produto_da_visao_ou_404(edit_id)
        selected_corredor_id = produto.corredor_id
        selected_bucket = "warehouse" if produto.local_estoque == "warehouse" else ""
        selected_loja = produto.loja

    if request.method == "POST":
        produto_id = request.form.get("produto_id", type=int)
        if produto_id and not current_user.can_access("editar_produto"):
            abort(403)
        produto = produto_da_visao_ou_404(produto_id) if produto_id else ProdutoInventario()

        try:
            local_estoque = request.form.get("local_estoque", "store")
            loja_id = request.form.get("loja_id", type=int)
            selected_loja = db.session.get(Loja, loja_id) if current_user.pode_ver_todas_lojas and loja_id else current_user.loja
            corredor_id = request.form.get("corredor_id", type=int)
            tipo_medida = request.form.get("tipo_medida", "unit")
            margem = parse_decimal(request.form.get("margem"), "0.01")
            preco_venda = parse_decimal(request.form.get("preco_venda"), "0.01")
            quantidade = parse_quantidade(request.form.get("quantidade"), tipo_medida)

            if not selected_loja:
                raise ValueError("Escolha a loja deste lancamento.")
            if local_estoque not in LOCAIS_ESTOQUE:
                raise ValueError("Escolha Loja ou Deposito.")
            if local_estoque == "store" and not corredor_id:
                raise ValueError("Escolha o corredor quando o produto estiver na loja.")
            if local_estoque == "warehouse":
                corredor_id = None
            if tipo_medida not in TIPOS_MEDIDA:
                raise ValueError("Escolha o tipo de quantidade.")
            if local_estoque == "warehouse" and tipo_medida not in TIPOS_MEDIDA_DEPOSITO:
                raise ValueError("No deposito, escolha Caixa ou Fardo.")
            if local_estoque == "store" and tipo_medida not in TIPOS_MEDIDA_LOJA:
                raise ValueError("Na loja, escolha Unidade ou Kg.")
            if quantidade <= 0:
                raise ValueError("Informe uma quantidade valida.")
            if preco_venda <= 0:
                raise ValueError("Informe o preco de venda.")

            produto.codigo_barras = limpar_codigo_barras(request.form.get("codigo_barras"))
            produto.nome = request.form.get("nome", "").strip()
            produto.loja_id = selected_loja.id
            produto.local_estoque = local_estoque
            produto.corredor_id = corredor_id
            produto.origem = request.form.get("origem", "cd")
            produto.margem = margem
            produto.preco_venda = preco_venda
            produto.preco_custo = calcular_custo(preco_venda, margem)
            produto.quantidade = quantidade
            produto.tipo_medida = tipo_medida
            produto.usuario_id = current_user.id

            if not produto.codigo_barras:
                raise ValueError("Informe o codigo de barras.")
            if len(produto.codigo_barras) != 13:
                raise ValueError("O codigo de barras deve ter exatamente 13 digitos.")
            if not produto.nome:
                raise ValueError("Informe o nome do produto.")

            duplicado = ProdutoInventario.query.filter(
                ProdutoInventario.codigo_barras == produto.codigo_barras,
                ProdutoInventario.loja_id == produto.loja_id,
                ProdutoInventario.local_estoque == produto.local_estoque,
            )
            if produto.id:
                duplicado = duplicado.filter(ProdutoInventario.id != produto.id)
            item_duplicado = duplicado.first()
            if item_duplicado:
                if produto.local_estoque == "warehouse":
                    raise ValueError("Este codigo ja foi lancado no deposito desta loja.")
                corredor_nome = item_duplicado.corredor.nome if item_duplicado.corredor else "sem corredor"
                raise ValueError(f"Este codigo ja foi lancado na loja, no corredor {corredor_nome}.")

            db.session.add(produto)
            db.session.commit()
            flash("Produto salvo com sucesso.", "success")
            if produto.local_estoque == "warehouse":
                return redirect(url_for("main.lancamento", bucket="warehouse", loja_id=produto.loja_id if current_user.pode_ver_todas_lojas else None))
            return redirect(url_for("main.lancamento", corredor_id=produto.corredor_id, loja_id=produto.loja_id if current_user.pode_ver_todas_lojas else None))
        except ValueError as erro:
            flash(str(erro), "error")
            selected_corredor_id = corredor_id
            selected_bucket = "warehouse" if local_estoque == "warehouse" else ""

    return render_template(
        "main/lancamento.html",
        produto=produto,
        selected_loja=selected_loja,
        selected_corredor_id=selected_corredor_id,
        selected_bucket=selected_bucket,
        bucket_totals=totais_lancamento_por_bucket(selected_loja.id, produto.id if produto and selected_loja else None) if selected_loja else {},
        corredores=corredores_ativos(),
        lojas=lojas_da_visao(),
        locais=LOCAIS_ESTOQUE,
        origens=ORIGENS_PRODUTO,
        medidas=TIPOS_MEDIDA,
    )


@bp.route("/produtos")
@login_required
def produtos():
    require_access("produtos")
    filtro_aplicado = filtro_foi_aplicado(request.args)
    filtro_bloqueado = filtro_aplicado and filtro_amplo_bloqueado(request.args)
    lista = produto_query_filtrada(request.args).all() if filtro_aplicado and not filtro_bloqueado else []
    return render_template(
        "main/produtos.html",
        produtos=lista,
        totais=totais(lista),
        filtro_aplicado=filtro_aplicado,
        filtro_bloqueado=filtro_bloqueado,
        mensagem_filtro_bloqueado=MENSAGEM_FILTRO_AMPLO,
        corredores=corredores_ativos(),
        lojas=lojas_da_visao(),
        locais=LOCAIS_ESTOQUE,
    )


@bp.route("/produtos/<int:produto_id>/excluir", methods=["POST"])
@login_required
def excluir_produto(produto_id):
    require_access("produtos")
    require_access("excluir_produto")
    produto = produto_da_visao_ou_404(produto_id)
    db.session.delete(produto)
    db.session.commit()
    flash("Produto removido.", "success")
    return redirect(url_for("main.produtos"))


@bp.route("/relatorios")
@login_required
def relatorios():
    require_access("relatorios")
    filtro_aplicado = filtro_foi_aplicado(request.args)
    filtro_bloqueado = filtro_aplicado and filtro_relatorio_bloqueado(request.args)
    produtos = produto_query_filtrada(request.args).all() if filtro_aplicado and not filtro_bloqueado else []
    por_corredor = {}
    for produto in produtos:
        local_nome = produto.loja.nome if produto.loja else "Sem loja"
        grupo_nome = produto.corredor.nome if produto.corredor else produto.local_label
        chave = f"{local_nome} - {grupo_nome}" if current_user.pode_ver_todas_lojas else grupo_nome
        por_corredor.setdefault(chave, []).append(produto)
    grupos = [(nome, totais(itens), itens) for nome, itens in sorted(por_corredor.items())]
    return render_template(
        "main/relatorios.html",
        produtos=produtos,
        grupos=grupos,
        totais=totais(produtos),
        filtro_aplicado=filtro_aplicado,
        filtro_bloqueado=filtro_bloqueado,
        mensagem_filtro_bloqueado=MENSAGEM_RELATORIO_LOJA,
        exportar_disponivel=filtro_aplicado and not filtro_bloqueado and bool(produtos),
        pdf_disponivel=relatorio_pdf_disponivel(request.args, produtos, filtro_aplicado, filtro_bloqueado),
        mensagem_pdf=MENSAGEM_RELATORIO_PDF,
        corredores=corredores_ativos(),
        lojas=lojas_da_visao(),
        locais=LOCAIS_ESTOQUE,
    )


@bp.route("/relatorios/exportar.csv")
@login_required
def exportar_csv():
    require_access("relatorios")
    require_access("exportar_csv")
    if filtro_relatorio_bloqueado(request.args):
        flash(MENSAGEM_RELATORIO_LOJA, "error")
        return redirect(url_for("main.relatorios", **request.args))
    produtos = produto_query_filtrada(request.args).all()
    buffer = StringIO()
    writer = csv.writer(buffer, delimiter=";")
    header = ["Codigo", "Produto"]
    if current_user.pode_ver_todas_lojas:
        header.append("Loja")
    header += ["Local", "Corredor", "Quantidade", "Medida", "Venda", "Custo", "Total venda", "Total custo"]
    writer.writerow(header)
    for item in produtos:
        row = [
            item.codigo_barras,
            item.nome,
        ]
        if current_user.pode_ver_todas_lojas:
            row.append(f"{item.loja.codigo} - {item.loja.nome}" if item.loja else "Sem loja")
        row += [
            item.local_label,
            item.corredor.nome if item.corredor else "",
            str(item.quantidade).replace(".", ","),
            item.medida_label,
            str(item.preco_venda).replace(".", ","),
            str(item.preco_custo).replace(".", ","),
            str(item.total_venda.quantize(Decimal("0.01"))).replace(".", ","),
            str(item.total_custo.quantize(Decimal("0.01"))).replace(".", ","),
        ]
        writer.writerow(row)
    return Response(
        buffer.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=inventario.csv"},
    )


@bp.route("/relatorios/exportar.pdf")
@login_required
def exportar_pdf():
    require_access("relatorios")
    require_access("exportar_csv")
    filtro_aplicado = filtro_foi_aplicado(request.args)
    filtro_bloqueado = filtro_relatorio_bloqueado(request.args)
    produtos = produto_query_filtrada(request.args).all() if filtro_aplicado and not filtro_bloqueado else []
    if filtro_bloqueado:
        flash(MENSAGEM_RELATORIO_LOJA, "error")
        return redirect(url_for("main.relatorios", **request.args))
    if not relatorio_pdf_disponivel(request.args, produtos, filtro_aplicado, filtro_bloqueado):
        flash(MENSAGEM_RELATORIO_PDF, "error")
        return redirect(url_for("main.relatorios", **request.args))

    por_corredor = {}
    for produto in produtos:
        grupo_nome = produto.corredor.nome if produto.corredor else produto.local_label
        por_corredor.setdefault(grupo_nome, []).append(produto)
    grupos = [(nome, totais(itens), itens) for nome, itens in sorted(por_corredor.items())]
    pdf = gerar_pdf_relatorio(produtos, grupos, totais(produtos))
    return Response(
        pdf,
        mimetype="application/pdf",
        headers={"Content-Disposition": "inline; filename=relatorio-inventario.pdf"},
    )
