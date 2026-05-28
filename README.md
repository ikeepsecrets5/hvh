# Painel Admin do Bot

## Como usar

1. Envie todos os arquivos para uma pasta no host.
2. Copie `.env.example` para `.env`.
3. Troque `PANEL_ADMIN_PASSWORD` por uma senha forte.
4. Deixe o `data.json` do bot na mesma pasta ou ajuste `BOT_DATA_PATH`.
5. Use a startup:

```bash
pip install -r requirements.txt && python app.py
```

## Login padrão

Usuário:

```txt
admin
```

Senha:

```txt
troque-essa-senha
```

Troque isso no `.env` antes de deixar online.

## Segurança

Este painel usa sessão protegida, limite de tentativas, senha com hash interno, cookies HTTPOnly e logs de ações. Mesmo assim, não deixe o link público sem senha forte.
