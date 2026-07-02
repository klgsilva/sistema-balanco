# Sistema de Inventario

Versao refeita em Flask, seguindo o estilo do sistema de supervisao: login, menu lateral, telas separadas, banco SQLite, responsivo para celular e computador.

## Como rodar no VS Code

1. Abra esta pasta no VS Code:

```text
C:\Users\Klinger\Documents\Codex\2026-06-30\boa
```

2. Crie e ative o ambiente virtual:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

3. Instale as dependencias:

```powershell
pip install -r requirements.txt
```

4. Crie o banco e os dados iniciais:

```powershell
python seed.py
```

5. Rode o sistema:

```powershell
python run.py
```

6. Acesse no navegador:

```text
http://localhost:5001
```

## Login inicial

```text
Admin: admin@inventario.local
Senha: admin123
```

```text
Operador: operador@inventario.local
Senha: operador123
```

## O que ja tem

- Tela de login.
- Menu lateral igual ao estilo do sistema de supervisao.
- Painel com resumo do inventario.
- Lancamento de produto com codigo de barras manual ou camera.
- Loja com corredor e deposito como local unico.
- Preco de venda informado primeiro, custo calculado pela margem.
- Unidade e kg.
- Cadastro de corredores e usuarios para admin.
- Listagem, edicao e remocao de produtos.
- Relatorios com filtros e exportacao CSV.
- Manual de uso dentro do sistema, com passo a passo por modulo.

## Deploy no Railway

1. Suba este projeto para um repositorio no GitHub.
2. No Railway, crie um novo projeto usando "Deploy from GitHub repo".
3. Adicione um banco PostgreSQL no projeto.
4. Configure as variaveis:

```text
SECRET_KEY=uma-chave-segura
TIMEZONE=America/Manaus
```

5. O Railway usa o `railway.json` para iniciar:

```text
python seed.py && gunicorn run:app --bind 0.0.0.0:$PORT
```

O `seed.py` cria as tabelas e os dados iniciais na primeira subida. Localmente o sistema continua usando SQLite; no Railway ele usa `DATABASE_URL` do PostgreSQL.
